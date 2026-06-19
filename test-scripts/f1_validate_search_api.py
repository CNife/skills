#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
F1 — 验证 npm search API 的下载数字段能否替代 range API 计算趋势分。

方法：用同一候选池分别跑 search-only 公式和 range 公式，比较 top-30 榜单的
overlap（交集比例）和 Spearman 秩相关系数。结论决定后续走向：
  - 可替代 (overlap≥0.85 且 Spearman≥0.8) → F2a：删 range API
  - 不可替代 → F2b：加缓存层
"""

from __future__ import annotations

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
RISING_MIN_WEEKLY = 200
TOP_K = 30

# ponytail: thresholds fixed per research decision (overlap≥0.85 AND spearman≥0.8)
OVERLAP_THRESHOLD = 0.85
SPEARMAN_THRESHOLD = 0.8

# Type keywords (same as pi_trending.py)
TYPE_KEYWORDS: dict[str, list[str]] = {
    "extension": ["pi-extension", "extension"],
    "skill": ["pi-skill", "skill"],
    "theme": ["pi-theme", "theme"],
    "prompt": ["pi-prompt", "prompt", "prompt-template"],
}

# ── Logging ──────────────────────────────────────────────────────────────────


def _vlog(msg: str) -> None:
    print(f"[F1] {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"[F1] ⚠ {msg}", file=sys.stderr)


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class PiPackage:
    name: str
    description: str
    author: str
    weekly: int
    monthly: int
    pkg_type: str
    score: float = 0.0
    this_week: int = 0
    prev_week: int = 0


# ── Network helpers ──────────────────────────────────────────────────────────


def _urlencode_pkg(name: str) -> str:
    return name.replace("@", "%40").replace("/", "%2F")


def _json_get(url: str, timeout: int = 15, retries: int = 3) -> dict[str, Any] | list | None:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
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


# ── Type / author helpers ────────────────────────────────────────────────────


def _determine_type(keywords: list[str] | None) -> str:
    if not keywords:
        return "package"
    kw_lower = [k.lower() for k in keywords]
    for ptype, type_kws in TYPE_KEYWORDS.items():
        for tk in type_kws:
            if tk in kw_lower:
                return ptype
    return "package"


def _get_author(pkg: dict) -> str:
    maintainers = pkg.get("maintainers", [])
    if maintainers:
        return maintainers[0].get("username", "?")
    return pkg.get("publisher", {}).get("username", "?")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ── Phase 0: Probe search API fields ─────────────────────────────────────────


def probe_search_api() -> bool:
    """Hit search API and print available download fields.

    Returns True if 'monthly' field exists (F2a feasibility).
    """
    url = f"{NPM_SEARCH}?text=keywords:pi-package&size=1&sort=popularity"
    data = _json_get(url)
    if data is None:
        _warn("探针请求失败")
        return False

    objects = data.get("objects", [])
    if not objects:
        _warn("探针未返回任何包")
        return False

    dl = objects[0].get("downloads", {})
    keys = list(dl.keys())
    _vlog(f"search API response downloads keys: {keys}")
    _vlog(f"values: {dict(dl)}")

    has_monthly = "monthly" in dl
    if has_monthly:
        _vlog("✓ monthly 字段存在 — F2a 可行")
    else:
        _warn("✗ monthly 字段缺失 — F2a 不可行")
    return has_monthly


# ── Phase 1: Fetch candidates ────────────────────────────────────────────────


def fetch_candidates() -> list[PiPackage]:
    """Fetch pi packages from npm search API (2 pages, sort=popularity)."""
    all_pkgs: list[PiPackage] = []
    total = 0
    page = 0
    max_pages = 2

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
                monthly=dl.get("monthly", 0),
                pkg_type=_determine_type(p.get("keywords")),
            )
            all_pkgs.append(pkg)

        _vlog(f"  第 {page + 1} 页: {len(objects)} 个包 (累计 {len(all_pkgs)})")
        page += 1

    all_pkgs.sort(key=lambda p: p.weekly, reverse=True)
    return all_pkgs


# ── Phase 2: Search-only score formulas ──────────────────────────────────────


def score_search_formula_a(pkg: PiPackage) -> float:
    """Formula (a): monthly / weekly ratio."""
    if pkg.weekly == 0:
        return 0.0
    return pkg.monthly / pkg.weekly


def score_search_formula_b(pkg: PiPackage) -> float:
    """Formula (b): (monthly - weekly) / (weekly + 10), same +10 smoothing."""
    if pkg.weekly == 0:
        return 0.0
    return (pkg.monthly - pkg.weekly) / (pkg.weekly + 10)


def compute_search_scores(
    packages: list[PiPackage], use_formula_b: bool
) -> list[PiPackage]:
    """Score rising candidates using search-only data (no range API calls)."""
    scorer = score_search_formula_b if use_formula_b else score_search_formula_a
    for pkg in packages:
        pkg.score = scorer(pkg)
    packages.sort(key=lambda p: p.score, reverse=True)
    return packages


# ── Phase 3: Range-based scores (duplicate of pi_trending.py _fetch_range_data) ──


def compute_range_scores(packages: list[PiPackage]) -> list[PiPackage]:
    """Fetch 14-day download range data, compute range-based trending scores.

    Score formula: ln(this_week+1) * max(0, this_week-prev_week) / (prev_week+10)
    """
    if not packages:
        return packages

    today = _today_str()
    fourteen_days_ago = (datetime.now(UTC) - timedelta(days=14)).strftime("%Y-%m-%d")
    range_url = f"{NPM_DOWNLOADS}/range/{fourteen_days_ago}:{today}"

    _vlog(f"获取 {len(packages)} 个候选包的下载趋势数据 (range API)...")

    unscoped = [(i, p) for i, p in enumerate(packages) if not p.name.startswith("@")]
    scoped = [(i, p) for i, p in enumerate(packages) if p.name.startswith("@")]

    results: dict[int, dict] = {}

    # Batch unscoped
    batch_size = 80
    unscoped_batches = [unscoped[i : i + batch_size] for i in range(0, len(unscoped), batch_size)]

    for batch_idx, batch in enumerate(unscoped_batches):
        names_comma = ",".join(p.name for _, p in batch)
        url = f"{range_url}/{names_comma}"
        data = _json_get(url)
        if not data or not isinstance(data, dict) or "error" in data:
            names = [p.name for _, p in batch]
            first = ", ".join(names[:5])
            _warn(
                f"批量获取下载数据失败 ({len(names)} 个包): {first}{'…' if len(names) > 5 else ''}"
            )
            # Don't raise — just skip this batch for F1
            continue
        for idx, p in batch:
            if p.name in data:
                results[idx] = data[p.name]
        _vlog(f"  批量 {batch_idx + 1}/{len(unscoped_batches)}: {len(batch)} 个包")
        time.sleep(0.1)

    # Scoped individually
    if scoped:
        _vlog(f"  逐一获取 {len(scoped)} 个有作用域包 (8 线程并行)...")
        scoped_urls = [f"{range_url}/{_urlencode_pkg(p.name)}" for _, p in scoped]
        scoped_responses = _json_get_bulk(scoped_urls, max_workers=8, timeout=15)
        success = 0
        for (idx, _p), resp in zip(scoped, scoped_responses, strict=True):
            if resp and isinstance(resp, dict) and "error" not in resp and "downloads" in resp:
                results[idx] = resp
                success += 1
        _vlog(f"  有作用域包完成: {success}/{len(scoped)}")

    # Calculate scores
    scored = 0
    for i, pkg in enumerate(packages):
        if i not in results:
            continue
        days = results[i].get("downloads", [])
        if not days or len(days) < 7:
            continue

        sorted_days = sorted(days, key=lambda d: d["day"])
        if len(sorted_days) >= 14:
            prev_week = sum(d["downloads"] for d in sorted_days[:7])
            this_week = sum(d["downloads"] for d in sorted_days[7:])
        elif len(sorted_days) >= 7:
            cutoff = len(sorted_days) - 7
            prev_week = sum(d["downloads"] for d in sorted_days[:cutoff])
            this_week = sum(d["downloads"] for d in sorted_days[cutoff:])
        else:
            continue

        pkg.this_week = this_week
        pkg.prev_week = prev_week
        delta = max(0, this_week - prev_week)
        pkg.score = math.log1p(this_week) * delta / (prev_week + 10)
        scored += 1

    _vlog(f"  range 评分完成: {scored}/{len(packages)} 个包")
    packages.sort(key=lambda p: p.score, reverse=True)
    return packages


# ── Phase 4: Compare top-k lists ─────────────────────────────────────────────


def spearman_rank(x: list[str], y: list[str]) -> float:
    """Hand-calculate Spearman rank correlation for overlapping items.

    Uses formula: rho = 1 - 6*sum(d^2) / (n*(n^2-1))
    Only considers items present in both lists.
    Returns NaN if fewer than 2 overlapping items.
    """
    set_x, set_y = set(x), set(y)
    overlap = list(set_x & set_y)
    n = len(overlap)
    if n < 2:
        return float("nan")

    rank_x = {name: i for i, name in enumerate(x)}
    rank_y = {name: i for i, name in enumerate(y)}

    d_squared_sum = sum((rank_x[name] - rank_y[name]) ** 2 for name in overlap)
    return 1.0 - (6.0 * d_squared_sum) / (n * (n**2 - 1))


def compare_lists(
    search_list: list[PiPackage], range_list: list[PiPackage], k: int = TOP_K
) -> tuple[float, float, list[str], list[str]]:
    """Compare top-k names from two scored lists.

    Returns (overlap, spearman, search_names, range_names).
    """
    search_names = [p.name for p in search_list[:k]]
    range_names = [p.name for p in range_list[:k]]

    set_s, set_r = set(search_names), set(range_names)
    intersection = set_s & set_r
    overlap = len(intersection) / max(len(search_names), len(range_names))

    sp = spearman_rank(search_names, range_names)

    return overlap, sp, search_names, range_names


# ── Phase 5: Output & Conclusion ─────────────────────────────────────────────


def print_list_comparison(
    label: str,
    overlap: float,
    spearman: float,
    search_names: list[str],
    range_names: list[str],
) -> bool:
    """Print comparison results. Returns True if replaceable."""
    print(f"\n{'='*60}")
    print(f"公式: {label}")
    print(f"{'='*60}")
    print(f"  Overlap (top-{TOP_K}):       {overlap:.3f}  (阈值 ≥{OVERLAP_THRESHOLD})")
    print(f"  Spearman (top-{TOP_K}):       {spearman:.3f}  (阈值 ≥{SPEARMAN_THRESHOLD})")

    meet_overlap = overlap >= OVERLAP_THRESHOLD
    meet_spearman = spearman >= SPEARMAN_THRESHOLD if not math.isnan(spearman) else False
    replaceable = meet_overlap and meet_spearman

    print(f"  Overlap {'✓' if meet_overlap else '✗'}  Spearman {'✓' if meet_spearman else '✗'}")
    print(f"  → {'可替代' if replaceable else '不可替代'}")

    # Print top-30 side by side
    print(f"\n  Top-{TOP_K} 对比:")
    print(f"  {'#':>2}  {'search-only':<40} {'range':<40}")
    print(f"  {'--':>2}  {'-'*40} {'-'*40}")
    for i in range(TOP_K):
        s = search_names[i] if i < len(search_names) else ""
        r = range_names[i] if i < len(range_names) else ""
        marker = " ←→" if s == r else ""
        print(f"  {i+1:>2}  {s:<40} {r:<40}{marker}")

    return replaceable


def print_conclusion(best_label: str, best_ok: bool) -> None:
    """Print final conclusion for the pipeline decision."""
    print(f"\n{'='*60}")
    print("  结论")
    print(f"{'='*60}")
    if best_ok:
        print(f"  ✅ 可替代 — 使用 {best_label}")
        print("  后续: F2a — 删 range API 调用, 改用 search-only 公式")
    else:
        print("  ❌ 不可替代 — 未达到阈值")
        print("  后续: F2b — 在 range API 前加 tempfile 缓存层")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    _vlog("F1 验证 — 判断 search API 能否替代 range API")
    _vlog(f"阈值: overlap≥{OVERLAP_THRESHOLD} 且 Spearman≥{SPEARMAN_THRESHOLD}")
    print("F1 验证报告")

    # ── Phase 0: Probe ──
    print(f"\n{'='*60}")
    print("  Phase 0: 探针 (探测 search API downloads 字段)")
    print(f"{'='*60}")
    has_monthly = probe_search_api()
    if not has_monthly:
        print("\n  ✗ monthly 字段缺失 — F2a 不可行，无需继续验证")
        print("  结论: NOT REPLACEABLE — search API 缺少 monthly 字段")
        print("  后续: F2b — 加缓存层")
        return

    # ── Phase 1: Fetch candidates ──
    print(f"\n{'='*60}")
    print("  Phase 1: 采集候选包")
    print(f"{'='*60}")
    candidates = fetch_candidates()
    if not candidates:
        _warn("未获取到任何包，退出")
        sys.exit(1)
    print(f"  候选包总数: {len(candidates)}")

    # Filter rising candidates
    rising_candidates = [p for p in candidates if p.weekly >= RISING_MIN_WEEKLY]
    print(f"  新锐候选 (weekly≥{RISING_MIN_WEEKLY}): {len(rising_candidates)}")

    # ── Phase 2: Search-only scores ──
    print(f"\n{'='*60}")
    print("  Phase 2: 计算 search-only 分数 (两种公式)")
    print(f"{'='*60}")

    # Formula A
    search_a = compute_search_scores(
        [PiPackage(**p.__dict__) for p in rising_candidates], use_formula_b=False
    )
    print("  公式 (a) monthly/weekly: 完成")

    # Formula B
    search_b = compute_search_scores(
        [PiPackage(**p.__dict__) for p in rising_candidates], use_formula_b=True
    )
    print("  公式 (b) (monthly-weekly)/(weekly+10): 完成")

    # ── Phase 3: Range-based scores ──
    print(f"\n{'='*60}")
    print("  Phase 3: 计算 range API 分数 (基准)")
    print(f"{'='*60}")
    range_results = compute_range_scores(
        [PiPackage(**p.__dict__) for p in rising_candidates]
    )
    print("  range API 评分: 完成")

    # ── Phase 4-5: Compare + Conclusion ──
    print(f"\n{'='*60}")
    print("  Phase 4-5: 对比 & 结论")
    results: list[tuple[str, bool]] = []

    for label, search_scores in [
        ("(a) monthly / weekly", search_a),
        ("(b) (monthly - weekly) / (weekly + 10)", search_b),
    ]:
        overlap, sp, s_names, r_names = compare_lists(search_scores, range_results)
        ok = print_list_comparison(label, overlap, sp, s_names, r_names)
        results.append((label, ok))

    # Pick best (any formula that's replaceable)
    best_label, best_ok = max(results, key=lambda x: x[1])
    print_conclusion(best_label, best_ok)


if __name__ == "__main__":
    main()
