# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///
"""
审计 Hermes Agent 技能使用频率，生成清理建议。

使用 uv 运行：
    uv run audit-hermes-agent-skills.py

依赖自动管理：uv 会根据上方的 inline metadata 自动创建临时环境并安装 pyyaml。
"""

import sqlite3
import json
import math
import os
import shutil
import tarfile
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Tuple, Set

try:
    import yaml
except ImportError:
    print("错误: 需要 pyyaml 库。请使用 'uv run audit-hermes-agent-skills.py' 运行此脚本。")
    print("uv 会自动安装依赖。")
    raise SystemExit(1)

# ─── 路径配置 ────────────────────────────────────────────────────────────────
HERMES_HOME = Path.home() / ".hermes"
STATE_DB = HERMES_HOME / "state.db"
SKILLS_DIR = HERMES_HOME / "skills"
CONFIG_PATH = HERMES_HOME / "config.yaml"
AGENTS_SKILLS = Path.home() / ".agents" / "skills"
BUILTIN_SKILLS = HERMES_HOME / "hermes-agent" / "skills"
BACKUP_DIR = SKILLS_DIR / ".audit-backups"

# ─── 时间窗口定义 ────────────────────────────────────────────────────────────
TIME_WINDOWS = {
    "last_3d": 3 * 86400,
    "last_7d": 7 * 86400,
    "last_30d": 30 * 86400,
    "last_90d": 90 * 86400,
}

# ─── 热度衰减参数 ────────────────────────────────────────────────────────────
DECAY_PARAMS = {
    "lambda_3d": math.log(2) / 3.0,
    "lambda_7d": math.log(2) / 7.0,
    "lambda_30d": math.log(2) / 30.0,
    "lambda_90d": math.log(2) / 90.0,
}

COMPOSITE_WEIGHTS = {
    "score_3d": 0.50,
    "score_7d": 0.25,
    "score_30d": 0.15,
    "score_90d": 0.10,
}


def get_current_timestamp() -> float:
    return datetime.now().timestamp()


# ─── 技能扫描 ────────────────────────────────────────────────────────────────
def scan_all_skills() -> Dict[str, dict]:
    """扫描所有已安装技能"""
    skills = {}
    _EXCLUDED = frozenset((".git", ".github", ".hub", ".audit-backups"))

    def scan_directory(base_dir: Path, default_source: str):
        if not base_dir.exists():
            return
        for skill_md in base_dir.rglob("SKILL.md"):
            if any(part in _EXCLUDED for part in skill_md.parts):
                continue
            skill_dir = skill_md.parent
            name = skill_dir.name
            if name in skills:
                continue

            parent = skill_dir.parent
            category = parent.name if parent != base_dir else None

            source = default_source
            if default_source == "standalone":
                for cat in BUILTIN_SKILLS.iterdir():
                    if cat.is_dir() and (cat / name / "SKILL.md").exists():
                        source = "builtin"
                        break

            skills[name] = {
                "dir": str(skill_dir),
                "source": source,
                "category": category,
                "installed_at": datetime.fromtimestamp(
                    skill_dir.stat().st_mtime
                ).strftime("%Y-%m-%d"),
            }

    scan_directory(SKILLS_DIR, "standalone")

    if AGENTS_SKILLS.exists():
        scan_directory(AGENTS_SKILLS, "external")
        for skill_md in AGENTS_SKILLS.rglob("SKILL.md"):
            if any(part in _EXCLUDED for part in skill_md.parts):
                continue
            name = skill_md.parent.name
            if name in skills and skills[name]["source"] == "standalone":
                skills[name]["source"] = "external"

    return skills


# ─── 数据库查询 ──────────────────────────────────────────────────────────────
def count_skill_calls(now_ts: float) -> Dict[str, dict]:
    """统计每个技能的调用次数"""
    if not STATE_DB.exists():
        return {}

    conn = sqlite3.connect(str(STATE_DB))
    cur = conn.cursor()

    cur.execute("""
        SELECT tool_calls, timestamp FROM messages
        WHERE tool_calls IS NOT NULL
        AND (tool_calls LIKE '%skill_view%' OR tool_calls LIKE '%skill_manage%')
    """)

    stats = {}
    for tool_calls_json, timestamp in cur.fetchall():
        try:
            items = json.loads(tool_calls_json)
            for item in items:
                fn = item.get("function", {}).get("name", "")
                if fn in ("skill_view", "skill_manage"):
                    args = json.loads(item.get("function", {}).get("arguments", "{}"))
                    name = args.get("name", "")
                    if not name:
                        continue

                    if name not in stats:
                        stats[name] = {
                            "skill_view": 0,
                            "skill_manage": 0,
                            "timestamps": [],
                        }

                    if fn == "skill_view":
                        stats[name]["skill_view"] += 1
                    else:
                        stats[name]["skill_manage"] += 1

                    stats[name]["timestamps"].append(timestamp)
        except:
            continue

    for name, data in stats.items():
        ts_list = data["timestamps"]
        for window, seconds in TIME_WINDOWS.items():
            cutoff = now_ts - seconds
            count = sum(1 for ts in ts_list if ts >= cutoff)
            data[window] = count

    conn.close()
    return stats


# ─── 热度计算 ────────────────────────────────────────────────────────────────
def calc_decay_score(timestamps: List[float], now_ts: float, lambda_val: float) -> float:
    if not timestamps:
        return 0.0
    score = 0.0
    for ts in timestamps:
        days_ago = (now_ts - ts) / 86400.0
        score += math.exp(-lambda_val * days_ago)
    return round(score, 3)


def calc_heat(timestamps: List[float], now_ts: float) -> Dict[str, float]:
    return {
        "score_3d": calc_decay_score(timestamps, now_ts, DECAY_PARAMS["lambda_3d"]),
        "score_7d": calc_decay_score(timestamps, now_ts, DECAY_PARAMS["lambda_7d"]),
        "score_30d": calc_decay_score(timestamps, now_ts, DECAY_PARAMS["lambda_30d"]),
        "score_90d": calc_decay_score(timestamps, now_ts, DECAY_PARAMS["lambda_90d"]),
    }


def calc_composite_score(heat_scores: Dict[str, float]) -> float:
    score = 0.0
    for key, weight in COMPOSITE_WEIGHTS.items():
        score += heat_scores.get(key, 0.0) * weight
    return round(score, 3)


def get_heat_level(heat_scores: Dict[str, float], window_counts: Dict[str, int]) -> Tuple[str, str]:
    if window_counts.get("last_3d", 0) > 0 and heat_scores.get("score_3d", 0) > 2:
        level = "🔥 活跃"
    elif window_counts.get("last_7d", 0) > 0 and heat_scores.get("score_7d", 0) > 1:
        level = "🟢 常用"
    elif window_counts.get("last_30d", 0) > 0:
        level = "🟡 偶尔"
    elif window_counts.get("last_90d", 0) > 0:
        level = "🟠 历史"
    elif sum(window_counts.get(w, 0) for w in TIME_WINDOWS) > 0:
        level = "⚪ 冷备"
    else:
        level = "❌ 零调用"

    s3 = heat_scores.get("score_3d", 0)
    s7 = heat_scores.get("score_7d", 0)
    s30 = heat_scores.get("score_30d", 0)
    s90 = heat_scores.get("score_90d", 0)

    if s3 > s7 * 0.8:
        trend = "↑ 上升"
    elif s7 < s30 * 0.3 and s30 > 0:
        trend = "↓ 衰退"
    elif s30 < s90 * 0.2 and s90 > 0:
        trend = "⬇ 冷却"
    else:
        trend = "→ 稳定"

    return level, trend


# ─── 报告生成 ────────────────────────────────────────────────────────────────
def generate_report(
    skills: Dict[str, dict],
    call_stats: Dict[str, dict],
    now_ts: float
) -> Tuple[str, dict]:
    lines = []
    lines.append("# 🔍 Hermes Agent 技能审计报告")
    lines.append("")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    all_skills_data = []
    for name, info in skills.items():
        stats = call_stats.get(name, {})
        timestamps = stats.get("timestamps", [])
        heat = calc_heat(timestamps, now_ts)
        composite = calc_composite_score(heat)
        window_counts = {w: stats.get(w, 0) for w in TIME_WINDOWS}
        level, trend = get_heat_level(heat, window_counts)

        all_skills_data.append({
            "name": name,
            "source": info["source"],
            "category": info.get("category"),
            "installed_at": info["installed_at"],
            "skill_view": stats.get("skill_view", 0),
            "skill_manage": stats.get("skill_manage", 0),
            "total_calls": stats.get("skill_view", 0) + stats.get("skill_manage", 0),
            "last_3d": window_counts["last_3d"],
            "last_7d": window_counts["last_7d"],
            "last_30d": window_counts["last_30d"],
            "last_90d": window_counts["last_90d"],
            "score_3d": heat["score_3d"],
            "score_7d": heat["score_7d"],
            "score_30d": heat["score_30d"],
            "score_90d": heat["score_90d"],
            "composite": composite,
            "level": level,
            "trend": trend,
            "timestamps": timestamps,
        })

    all_skills_data.sort(key=lambda x: x["composite"], reverse=True)

    level_counts = defaultdict(int)
    source_counts = defaultdict(int)
    for s in all_skills_data:
        level_counts[s["level"]] += 1
        source_counts[s["source"]] += 1

    lines.append("## 📊 概览")
    lines.append("")
    lines.append(f"- **总技能数**: {len(all_skills_data)}")
    lines.append(f"- 🔥 活跃: {level_counts.get('🔥 活跃', 0)}")
    lines.append(f"- 🟢 常用: {level_counts.get('🟢 常用', 0)}")
    lines.append(f"- 🟡 偶尔: {level_counts.get('🟡 偶尔', 0)}")
    lines.append(f"- 🟠 历史: {level_counts.get('🟠 历史', 0)}")
    lines.append(f"- ⚪ 冷备: {level_counts.get('⚪ 冷备', 0)}")
    lines.append(f"- ❌ 零调用: {level_counts.get('❌ 零调用', 0)}")
    lines.append("")
    lines.append(f"- 📦 内置 (builtin): {source_counts.get('builtin', 0)}")
    lines.append(f"- 🔗 外部 (external): {source_counts.get('external', 0)}")
    lines.append(f"- 📁 独立 (standalone): {source_counts.get('standalone', 0)}")
    lines.append("")

    # 活跃技能 TOP 20
    active_skills = [s for s in all_skills_data if s["total_calls"] > 0]
    lines.append("## 🔥 活跃技能 TOP 20")
    lines.append("")
    lines.append("| # | 技能 | 来源 | 近3d | 近7d | 近30d | 全部 | 热度分 | 趋势 |")
    lines.append("|---|------|------|------|------|-------|------|--------|------|")
    for i, s in enumerate(active_skills[:20], 1):
        lines.append(
            f"| {i} | {s['name']} | {s['source']} | "
            f"{s['last_3d']} | {s['last_7d']} | {s['last_30d']} | "
            f"{s['total_calls']} | {s['composite']} | {s['trend']} |"
        )
    lines.append("")

    if len(active_skills) > 20:
        lines.append("<details>")
        lines.append("<summary>查看全部活跃技能</summary>")
        lines.append("")
        lines.append("| # | 技能 | 来源 | 近3d | 近7d | 近30d | 全部 | 热度分 | 趋势 |")
        lines.append("|---|------|------|------|------|-------|------|--------|------|")
        for i, s in enumerate(active_skills[20:], 21):
            lines.append(
                f"| {i} | {s['name']} | {s['source']} | "
                f"{s['last_3d']} | {s['last_7d']} | {s['last_30d']} | "
                f"{s['total_calls']} | {s['composite']} | {s['trend']} |"
            )
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # 零调用技能
    zero_skills = [s for s in all_skills_data if s["total_calls"] == 0]
    zero_external = [s for s in zero_skills if s["source"] in ("external", "standalone")]
    zero_builtin = [s for s in zero_skills if s["source"] == "builtin"]

    if zero_external:
        lines.append("## 🗑️ 建议删除（external/standalone + 零调用）")
        lines.append("")
        lines.append("| # | 技能 | 来源 | 安装时间 | 分类 |")
        lines.append("|---|------|------|---------|------|")
        for i, s in enumerate(zero_external, 1):
            lines.append(
                f"| {i} | {s['name']} | {s['source']} | "
                f"{s['installed_at']} | {s['category'] or '-'} |"
            )
        lines.append("")

    if zero_builtin:
        lines.append("## ⚠️ 建议禁用（builtin + 零调用）")
        lines.append("")

        by_category = defaultdict(list)
        for s in zero_builtin:
            cat = s["category"] or "uncategorized"
            by_category[cat].append(s)

        sorted_cats = sorted(by_category.items(), key=lambda x: -len(x[1]))

        lines.append("| # | 分类 | 技能数 | 示例 |")
        lines.append("|---|------|--------|------|")
        for i, (cat, cat_skills) in enumerate(sorted_cats, 1):
            examples = ", ".join(s["name"] for s in cat_skills[:3])
            if len(cat_skills) > 3:
                examples += f" +{len(cat_skills) - 3}"
            lines.append(f"| {i} | {cat} | {len(cat_skills)} | {examples} |")
        lines.append("")

        lines.append("<details>")
        lines.append("<summary>查看完整禁用列表</summary>")
        lines.append("")
        lines.append("```yaml")
        lines.append("# 将追加到 ~/.hermes/config.yaml")
        lines.append("skills:")
        lines.append("  disabled:")
        for cat, cat_skills in sorted_cats:
            lines.append(f"    # {cat} ({len(cat_skills)} skills)")
            for s in sorted(cat_skills, key=lambda x: x["name"]):
                lines.append(f"    - {s['name']}")
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("## 📝 清理操作汇总")
    lines.append("")
    lines.append(f"- **删除外部/独立技能**: {len(zero_external)} 个")
    lines.append(f"- **禁用内置技能**: {len(zero_builtin)} 个")
    lines.append(f"- **总计清理**: {len(zero_skills)} 个技能")
    lines.append("")

    json_data = {
        "generated_at": datetime.now().isoformat(),
        "total_skills": len(all_skills_data),
        "level_counts": dict(level_counts),
        "skills": [
            {k: v for k, v in s.items() if k != "timestamps"}
            for s in all_skills_data
        ],
        "delete_candidates": [s["name"] for s in zero_external],
        "disable_candidates": [s["name"] for s in zero_builtin],
    }

    return "\n".join(lines), json_data


# ─── 备份功能 ────────────────────────────────────────────────────────────────
def backup_skills(skill_names: List[str], skills_info: Dict[str, dict]) -> Tuple[str, List[str], float]:
    """备份指定技能到 ~/.hermes/skills/.audit-backups/"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"skills-backup-{timestamp}.tar.gz"

    backed_up = []
    with tarfile.open(str(backup_file), "w:gz") as tar:
        for name in skill_names:
            info = skills_info.get(name, {})
            dir_path = info.get("dir", "")
            if not dir_path or not Path(dir_path).exists():
                continue
            tar.add(dir_path, arcname=name)
            backed_up.append(name)

    size_mb = backup_file.stat().st_size / 1024 / 1024
    return str(backup_file), backed_up, round(size_mb, 2)


# ─── 执行清理 ────────────────────────────────────────────────────────────────
def execute_cleanup(
    delete_names: List[str],
    disable_names: List[str],
    skills_info: Dict[str, dict],
    dry_run: bool = True
) -> dict:
    result = {
        "deleted": [],
        "failed_delete": [],
        "disabled": [],
        "failed_disable": [],
        "backup_file": None,
        "backup_size_mb": 0,
    }

    all_cleanup = delete_names + disable_names
    if all_cleanup:
        backup_file, backed_up, size_mb = backup_skills(all_cleanup, skills_info)
        result["backup_file"] = backup_file
        result["backup_size_mb"] = size_mb
        print(f"\n✅ 已备份 {len(backed_up)} 个技能到: {backup_file} ({size_mb} MB)")

    if not dry_run:
        for name in delete_names:
            info = skills_info.get(name, {})
            dir_path = info.get("dir", "")
            if not dir_path:
                result["failed_delete"].append(name)
                continue
            try:
                if Path(dir_path).is_symlink():
                    Path(dir_path).unlink()
                else:
                    shutil.rmtree(dir_path)
                result["deleted"].append(name)
                print(f"  🗑️ 已删除: {name}")
            except Exception as e:
                result["failed_delete"].append(name)
                print(f"  ❌ 删除失败: {name} - {e}")
    else:
        for name in delete_names:
            result["deleted"].append(name)
            print(f"  [DRY RUN] 将删除: {name}")

    if not dry_run:
        try:
            with open(CONFIG_PATH) as f:
                config = yaml.safe_load(f) or {}

            config.setdefault("skills", {})
            existing_disabled = set(config["skills"].get("disabled", []))
            new_disabled = existing_disabled | set(disable_names)
            config["skills"]["disabled"] = sorted(new_disabled)

            with open(CONFIG_PATH, "w") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            result["disabled"] = list(new_disabled - existing_disabled)
            print(f"  ⚠️  已禁用 {len(result['disabled'])} 个内置技能")
        except Exception as e:
            result["failed_disable"] = disable_names
            print(f"  ❌ 修改 config.yaml 失败: {e}")
    else:
        for name in disable_names:
            result["disabled"].append(name)
            print(f"  [DRY RUN] 将禁用: {name}")

    return result


# ─── 主函数 ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Hermes Agent 技能审计工具")
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="只生成报告，不执行实际清理（默认）"
    )
    parser.add_argument(
        "--execute", action="store_false", dest="dry_run",
        help="执行实际清理操作（先备份）"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="报告输出路径（默认打印到 stdout）"
    )
    parser.add_argument(
        "--json-output", type=str, default=None,
        help="JSON 数据输出路径"
    )
    args = parser.parse_args()

    print("🔍 开始审计 Hermes Agent 技能...")
    now_ts = get_current_timestamp()

    print("  📂 扫描已安装技能...")
    skills = scan_all_skills()
    print(f"     找到 {len(skills)} 个技能")

    print("  📊 查询数据库调用记录...")
    call_stats = count_skill_calls(now_ts)
    print(f"     找到 {len(call_stats)} 个有调用记录的技能")

    print("  📝 生成审计报告...")
    report, json_data = generate_report(skills, call_stats, now_ts)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\n✅ 报告已保存到: {args.output}")
    else:
        print("\n" + report)

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ JSON 数据已保存到: {args.json_output}")

    print("\n" + "=" * 60)
    print("📋 审计完成摘要")
    print("=" * 60)
    print(f"  总技能数: {json_data['total_skills']}")
    print(f"  有调用记录: {len(call_stats)}")
    print(f"  零调用: {json_data['level_counts'].get('❌ 零调用', 0)}")
    print(f"  建议删除: {len(json_data['delete_candidates'])}")
    print(f"  建议禁用: {len(json_data['disable_candidates'])}")
    print("=" * 60)

    if args.dry_run:
        print("\n💡 当前为 DRY RUN 模式，未执行任何清理操作")
        print("   使用 --execute 参数执行实际清理（将先备份）")

    return json_data


if __name__ == "__main__":
    main()
