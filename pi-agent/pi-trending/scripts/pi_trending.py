#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
pi-trending — 发现 Pi Agent 生态中最近最火的包。

数据源：npm registry (pi 包本质是含 pi-package keyword 的 npm 包)
算法：trending_score = this_week² / (prev_week + 100)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

NPM_SEARCH = "https://registry.npmjs.org/-/v1/search"
NPM_DOWNLOADS = "https://api.npmjs.org/downloads"
SEARCH_PAGE_SIZE = 250
RISING_MIN_WEEKLY = 200  # 新锐榜候选池最低周下载门槛

# Type keywords (in order of precedence)
TYPE_KEYWORDS: dict[str, list[str]] = {
    "extension": ["pi-extension", "extension"],
    "skill": ["pi-skill", "skill"],
    "theme": ["pi-theme", "theme"],
    "prompt": ["pi-prompt", "prompt", "prompt-template"],
}

# ── Logging ─────────────────────────────────────────────────────────────────

VERBOSE = False  # set by --verbose flag in main()


def _vlog(msg: str) -> None:
    """Log to stderr when --verbose is set."""
    if VERBOSE:
        print(f"[pi-trending] {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    """Print a warning/error to stderr (always visible)."""
    print(f"[pi-trending] ⚠ {msg}", file=sys.stderr)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class PiPackage:
    name: str
    description: str
    author: str
    weekly: int
    pkg_type: str
    score: float = 0.0
    this_week: int = 0  # downloads last 7 days
    prev_week: int = 0  # downloads previous 7 days


# ── Network helpers ──────────────────────────────────────────────────────────


def _urlencode_pkg(name: str) -> str:
    """URL-encode a package name for npm API (handles scoped packages)."""
    return name.replace("@", "%40").replace("/", "%2F")


def _json_get(url: str, timeout: int = 15, retries: int = 3) -> dict[str, Any] | list | None:
    """GET a JSON endpoint with retries.

    HTTP 429 (rate limited) gets longer exponential backoff.
    Other failures use linear backoff.
    """
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — exponential backoff with random jitter
                if attempt == retries - 1:
                    return None
                time.sleep(2**attempt + random.random())
            else:
                if attempt == retries - 1:
                    return None
                time.sleep(0.5 * (attempt + 1))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            if attempt == retries - 1:
                return None
            time.sleep(0.5 * (attempt + 1))
    return None


def _json_get_bulk(
    urls: list[str], max_workers: int = 8, timeout: int = 15
) -> list[dict[str, Any] | None]:
    """Fetch multiple URLs in parallel."""
    results: list[dict[str, Any] | None] = [None] * len(urls)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for i, url in enumerate(urls):
            futures[pool.submit(_json_get, url, timeout)] = i
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = None
    return results


# ── Determine package type ────────────────────────────────────────────────────


def _determine_type(keywords: list[str] | None) -> str:
    """Determine pi package type from npm keywords."""
    if not keywords:
        return "package"
    kw_lower = [k.lower() for k in keywords]
    for ptype, type_kws in TYPE_KEYWORDS.items():
        for tk in type_kws:
            if tk in kw_lower:
                return ptype
    return "package"


def _get_author(pkg: dict) -> str:
    """Extract author name from npm package metadata.

    Prefer maintainers over publisher (publisher can be 'GitHub Actions').
    """
    maintainers = pkg.get("maintainers", [])
    if maintainers:
        return maintainers[0].get("username", "?")
    return pkg.get("publisher", {}).get("username", "?")


# ── Fetch phase 1: search API ────────────────────────────────────────────────


def fetch_top_packages(max_pages: int = 2) -> list[PiPackage]:
    """Fetch pi packages from npm search API, sorted by popularity.

    按周下载量降序采集 pi 包，最多取 max_pages 页。
    """
    all_pkgs: list[PiPackage] = []
    total = 0
    page = 0

    while page < max_pages:
        offset = page * SEARCH_PAGE_SIZE
        url = f"{NPM_SEARCH}?text=keywords:pi-package&size={SEARCH_PAGE_SIZE}&from={offset}&sort=popularity"
        data = _json_get(url)
        if data is None:
            _warn(f"搜索 API 第 {page + 1} 页请求失败，终止")
            break

        objects = data.get("objects", [])
        if not objects:
            break

        if page == 0:
            total = data.get("total", 0)
            _vlog(f"npm 搜索到 {total} 个 pi 包 (sort=popularity)")

        for obj in objects:
            p = obj.get("package", {})
            dl = obj.get("downloads", {})
            pkg = PiPackage(
                name=p.get("name", "?"),
                description=p.get("description", ""),
                author=_get_author(p),
                weekly=dl.get("weekly", 0),
                pkg_type=_determine_type(p.get("keywords")),
            )
            all_pkgs.append(pkg)

        _vlog(f"  第 {page + 1} 页: {len(objects)} 个包 (累计 {len(all_pkgs)})")
        page += 1

    # Sort by weekly downloads descending for mainstream list
    all_pkgs.sort(key=lambda p: p.weekly, reverse=True)
    return all_pkgs


# ── Fetch phase 2: download range data ───────────────────────────────────────


def _today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _fetch_range_data(packages: list[PiPackage]) -> list[PiPackage]:
    """Fetch 14-day download range data for candidate packages, update scores."""
    if not packages:
        return packages

    today = _today_str()
    fourteen_days_ago = (datetime.now(UTC) - timedelta(days=14)).strftime("%Y-%m-%d")
    range_url = f"{NPM_DOWNLOADS}/range/{fourteen_days_ago}:{today}"

    _vlog(f"获取 {len(packages)} 个候选包的下载趋势数据...")

    # Separate scoped and unscoped
    unscoped = [(i, p) for i, p in enumerate(packages) if not p.name.startswith("@")]
    scoped = [(i, p) for i, p in enumerate(packages) if p.name.startswith("@")]

    # We'll store results keyed by index
    results: dict[int, dict] = {}

    # Batch unscoped (max 100 per batch for URL length safety)
    batch_size = 80
    unscoped_batches = [unscoped[i : i + batch_size] for i in range(0, len(unscoped), batch_size)]

    for _batch_idx, batch in enumerate(unscoped_batches):
        names_comma = ",".join(p.name for _, p in batch)
        url = f"{range_url}/{names_comma}"
        data = _json_get(url)
        if not data or not isinstance(data, dict) or "error" in data:
            names = [p.name for _, p in batch]
            first = ", ".join(names[:5])
            raise RuntimeError(
                f"批量获取下载数据失败 ({len(names)} 个包): {first}{'…' if len(names) > 5 else ''}"
            )
        for idx, p in batch:
            if p.name in data:
                results[idx] = data[p.name]
        _vlog(f"  批量 {_batch_idx + 1}/{len(unscoped_batches)}: {len(batch)} 个包")
        time.sleep(0.1)

    # Fetch scoped packages individually
    _vlog(f"  逐一获取 {len(scoped)} 个有作用域包 (8 线程并行)...")
    scoped_urls = []
    for _, p in scoped:
        scoped_urls.append(f"{range_url}/{_urlencode_pkg(p.name)}")

    scoped_responses = _json_get_bulk(scoped_urls, max_workers=8, timeout=15)
    success = 0
    for (idx, _p), resp in zip(scoped, scoped_responses, strict=True):
        if resp and isinstance(resp, dict) and "error" not in resp and "downloads" in resp:
            results[idx] = resp
            success += 1
    if success < len(scoped):
        _vlog(
            f"  有作用域包完成: {success}/{len(scoped)} 成功 ({len(scoped) - success} 个被限流跳过，不影响主流榜)"
        )
    else:
        _vlog(f"  有作用域包完成: {success}/{len(scoped)} 成功")

    # Calculate trending scores
    for i, pkg in enumerate(packages):
        if i not in results:
            continue
        days = results[i].get("downloads", [])
        if not days or len(days) < 7:
            continue

        # Last 7 days = most recent 7, previous 7 = the 7 before that
        sorted_days = sorted(days, key=lambda d: d["day"])
        if len(sorted_days) >= 14:
            prev_week = sum(d["downloads"] for d in sorted_days[:7])
            this_week = sum(d["downloads"] for d in sorted_days[7:])
        elif len(sorted_days) >= 7:
            # If only 7-13 days of data, still calculate
            cutoff = len(sorted_days) - 7
            prev_week = sum(d["downloads"] for d in sorted_days[:cutoff])
            this_week = sum(d["downloads"] for d in sorted_days[cutoff:])
        else:
            continue

        pkg.this_week = this_week
        pkg.prev_week = prev_week
        delta = max(0, this_week - prev_week)
        pkg.score = math.log1p(this_week) * delta / (prev_week + 10)

    return packages


# ── Output ────────────────────────────────────────────────────────────────────


def render_markdown(mainstream: list[PiPackage], rising: list[PiPackage]) -> None:
    """Render two Markdown tables: mainstream (by weekly downloads) and rising (by growth score).

    The description column contains the raw English description from npm.
    When presenting to the user, the AI SHALL translate each description
    into Chinese and simplify it to ≤20 characters for readability.
    """
    today = _today_str()

    lines = [f"# 🔥 Pi Agent 最新热门包 ({today})"]

    # Mainstream table
    lines.append("\n## 主流榜")
    lines.append("| # | 包名 | 作者 | 本周下载量 | 一句话介绍 |")
    lines.append("|---|---|---|---|---|")
    for rank, pkg in enumerate(mainstream, 1):
        desc = pkg.description if pkg.description else "（未提供描述）"
        lines.append(f"| {rank} | `{pkg.name}` | {pkg.author} | {pkg.weekly:,} | {desc} |")
    lines.append(f"\n> Top {len(mainstream)} · 按本周下载量排序")

    # Rising table
    lines.append("\n## 新锐榜")
    lines.append("| # | 包名 | 作者 | 趋势分 | 一句话介绍 |")
    lines.append("|---|---|---|---|---|")
    for rank, pkg in enumerate(rising, 1):
        desc = pkg.description if pkg.description else "（未提供描述）"
        lines.append(f"| {rank} | `{pkg.name}` | {pkg.author} | {pkg.score:,.0f} | {desc} |")
    lines.append(f"\n> Top {len(rising)} · 更新于 {today} · 数据: npm registry")

    print("\n".join(lines))


def render_json(mainstream: list[PiPackage], rising: list[PiPackage]) -> None:
    """Render dual-list trending packages as JSON."""
    output = []
    for pkg in mainstream:
        output.append(
            {
                "list_type": "mainstream",
                "name": pkg.name,
                "type": pkg.pkg_type,
                "author": pkg.author,
                "weekly_downloads": pkg.weekly,
                "trending_score": None,
                "this_week": None,
                "prev_week": None,
                "description": pkg.description,
            }
        )
    for pkg in rising:
        output.append(
            {
                "list_type": "rising",
                "name": pkg.name,
                "type": pkg.pkg_type,
                "author": pkg.author,
                "weekly_downloads": pkg.weekly,
                "trending_score": round(pkg.score, 1),
                "this_week": pkg.this_week,
                "prev_week": pkg.prev_week,
                "description": pkg.description,
            }
        )
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="发现 Pi Agent 生态中最新的热门包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  pi-trending.py                          # 输出 Top 20 Markdown 表格
  pi-trending.py --max 10                 # 只显示前 10
  pi-trending.py --type extension         # 只看扩展
  pi-trending.py --verbose                # 显示详细 API 调用日志
  pi-trending.py --json                   # JSON 格式输出
        """,
    )
    parser.add_argument(
        "--max", type=int, default=20, help="同时设置主流榜和新锐榜的显示条数 (默认 20)"
    )
    parser.add_argument(
        "--mainstream-max", type=int, default=None, help="主流榜显示条数 (默认同 --max)"
    )
    parser.add_argument(
        "--rising-max", type=int, default=None, help="新锐榜显示条数 (默认同 --max)"
    )
    parser.add_argument(
        "--type",
        dest="pkg_type",
        default="all",
        choices=["all", "extension", "skill", "theme", "prompt"],
        help="按包类型过滤: extension, skill, theme, prompt (默认 all)",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出 (替代 Markdown 表格)")
    parser.add_argument(
        "--verbose", action="store_true", help="显示详细的 API 调用和流程日志 (默认不显示)"
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    global VERBOSE
    VERBOSE = args.verbose

    # Determine per-list counts from args
    mainstream_max = args.mainstream_max if args.mainstream_max is not None else args.max
    rising_max = args.rising_max if args.rising_max is not None else args.max

    # ── Phase 1: fetch candidate pool (fixed 2 pages, sort=popularity) ──
    candidates = fetch_top_packages(max_pages=2)
    if not candidates:
        _warn("未获取到任何 pi 包，请检查网络")
        sys.exit(1)

    # Apply type filter to shared pool before list splitting
    if args.pkg_type != "all":
        candidates = [p for p in candidates if p.pkg_type == args.pkg_type]

    # ── Phase 2: mainstream list (from search API data, zero extra cost) ──
    mainstream = sorted(candidates, key=lambda p: p.weekly, reverse=True)[:mainstream_max]

    # ── Phase 3: filter rising candidate pool by min weekly threshold ──
    rising_candidates = [p for p in candidates if p.weekly >= RISING_MIN_WEEKLY]
    dropped = len(candidates) - len(rising_candidates)
    if dropped:
        _vlog(
            f"新锐候选池过滤: {len(candidates)} → {len(rising_candidates)} (过滤 {dropped} 个低下载包)"
        )

    # ── Phase 4: fetch download range data for rising list ──
    try:
        rising_candidates = _fetch_range_data(rising_candidates)
    except RuntimeError as e:
        _warn(str(e))
        sys.exit(1)

    # ── Phase 5: rising list (from range API data) ──
    rising = sorted(rising_candidates, key=lambda p: p.score, reverse=True)[:rising_max]

    # ── Phase 6: output ──
    if args.json:
        render_json(mainstream, rising)
    else:
        render_markdown(mainstream, rising)


if __name__ == "__main__":
    main()
