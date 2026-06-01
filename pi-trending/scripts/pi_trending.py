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
MAX_SEARCH_PAGES = 6
TRENDING_SMOOTHING = 100  # prevent division-by-zero for new packages

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


def _json_get(url: str, timeout: int = 15) -> dict[str, Any] | list | None:
    """GET a JSON endpoint with retries."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            if attempt == 2:
                return None
            time.sleep(0.5 * (attempt + 1))
    return None


def _json_get_bulk(urls: list[str], max_workers: int = 8) -> list[dict[str, Any] | None]:
    """Fetch multiple URLs in parallel."""
    results: list[dict[str, Any] | None] = [None] * len(urls)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for i, url in enumerate(urls):
            futures[pool.submit(_json_get, url)] = i
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


def fetch_top_packages(need: int) -> list[PiPackage]:
    """Fetch top N pi packages by weekly downloads.

    逐页获取 npm search API 结果，收集到至少 need 个包后停止。
    """
    all_pkgs: list[PiPackage] = []
    total = 0
    page = 0

    while True:
        offset = page * SEARCH_PAGE_SIZE
        url = f"{NPM_SEARCH}?text=keywords:pi-package&size={SEARCH_PAGE_SIZE}&from={offset}"
        data = _json_get(url)
        if data is None:
            _warn(f"搜索 API 第 {page + 1} 页请求失败，终止")
            break

        objects = data.get("objects", [])
        if not objects:
            break

        if page == 0:
            total = data.get("total", 0)
            _vlog(f"npm 搜索到 {total} 个 pi 包，正在获取数据...")

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

        # Sort by weekly downloads descending after each page
        all_pkgs.sort(key=lambda p: p.weekly, reverse=True)
        current_top_n = all_pkgs[:need]

        _vlog(
            f"  第 {page + 1} 页: {len(objects)} 个包 (累计 {len(all_pkgs)}，top {need} 最低周下载 {current_top_n[-1].weekly:,})"
        )

        # Stop condition: we have enough candidates AND
        # the highest weekly on this new page is lower than
        # our current #need-th candidate (meaning no new page can overtake)
        if len(all_pkgs) >= need:
            page_max_weekly = max(obj.get("downloads", {}).get("weekly", 0) for obj in objects)
            need_th_weekly = current_top_n[-1].weekly
            if page_max_weekly < need_th_weekly:
                _vlog(
                    f"  ✓ top {need} 候选包已确定 (第 {page + 2} 页最高周下载 {page_max_weekly} < 候选门槛 {need_th_weekly})"
                )
                break

        # Safety: limit pages even if convergence hasn't happened
        if page >= MAX_SEARCH_PAGES - 1:
            break

        page += 1

    return all_pkgs[:need]


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
        if data and isinstance(data, dict) and "error" not in data:
            for idx, p in batch:
                if p.name in data:
                    results[idx] = data[p.name]
        # Brief pause to avoid rate limiting
        time.sleep(0.1)

    # Fetch scoped packages individually
    scoped_urls = []
    for _, p in scoped:
        scoped_urls.append(f"{range_url}/{_urlencode_pkg(p.name)}")

    scoped_responses = _json_get_bulk(scoped_urls, max_workers=5)
    for (idx, _p), resp in zip(scoped, scoped_responses, strict=True):
        if resp and isinstance(resp, dict) and "error" not in resp and "downloads" in resp:
            results[idx] = resp

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
        pkg.score = (
            (this_week**2) / (prev_week + TRENDING_SMOOTHING)
            if (prev_week + TRENDING_SMOOTHING) > 0
            else 0.0
        )

    return packages


# ── Output ────────────────────────────────────────────────────────────────────


def render_markdown(packages: list[PiPackage]) -> None:
    """Render trending packages as a Markdown table (LLM-friendly)."""
    today = _today_str()

    lines = [f"# 🔥 Pi Agent 最新热门包 ({today})"]
    lines.append("| # | 包名 | 类型 | 作者 | 周下载 | 趋势分 |")
    lines.append("|---|---|---|---|---|---|")
    for rank, pkg in enumerate(packages, 1):
        lines.append(
            f"| {rank} | `{pkg.name}` | {pkg.pkg_type} | {pkg.author} "
            f"| {pkg.weekly:,} | {pkg.score:,.0f} |"
        )
    lines.append(f"\n> Top {len(packages)} · 更新于 {today} · 数据: npm registry")

    print("\n".join(lines))


def render_json(packages: list[PiPackage]) -> None:
    """Render trending packages as JSON."""
    output = []
    for pkg in packages:
        output.append(
            {
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
    parser.add_argument("--max", type=int, default=20, help="显示前 N 个结果 (默认 20)")
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

    # ── Phase 1: fetch top candidates (3x max for trending computation) ──
    max_candidates = args.max * 3
    candidates = fetch_top_packages(max_candidates)
    if not candidates:
        _warn("未获取到任何 pi 包，请检查网络")
        sys.exit(1)

    # ── Phase 3: fetch download range data for candidates ──
    candidates = _fetch_range_data(candidates)

    # ── Phase 4: filter, sort, truncate ──
    if args.pkg_type != "all":
        candidates = [p for p in candidates if p.pkg_type == args.pkg_type]

    candidates.sort(key=lambda p: p.score, reverse=True)
    results = candidates[: args.max]

    # ── Phase 5: output ──
    if not results:
        msg = (
            f"未找到类型为 '{args.pkg_type}' 的 trending 包"
            if args.pkg_type != "all"
            else "未找到 trending 包"
        )
        _warn(msg)
        sys.exit(0)

    if args.json:
        render_json(results)
    else:
        render_markdown(results)


if __name__ == "__main__":
    main()
