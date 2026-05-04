#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Obsidian 日记辅助脚本：路径计算、文件创建、待办查询。

用法:
    uv run obsidian-helper.py --vault work --action context
    uv run obsidian-helper.py --vault work --action locate
    uv run obsidian-helper.py --vault work --action create
    uv run obsidian-helper.py --vault work --action todos
    uv run obsidian-helper.py --vault work --action recent --days 10
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "cnife-skills" / "obsidian-diary.json"


def _load_vaults() -> dict[str, dict]:
    if not CONFIG_PATH.exists():
        print("CONFIG_MISSING=true", file=sys.stdout)
        print(f"CONFIG_PATH={CONFIG_PATH}", file=sys.stdout)
        print("", file=sys.stdout)
        print("Obsidian diary configuration not found.", file=sys.stdout)
        print(f"Please create {CONFIG_PATH} with the following structure:", file=sys.stdout)
        print(file=sys.stdout)
        print(
            json.dumps(
                {
                    "vaults": {
                        "work": {
                            "base": "/path/to/obsidian/work-vault",
                            "diary_dir": "工作日志",
                            "template": "日志模板.md",
                            "exclude_meta": ["AGENTS.md", "任务.md", "日志模板.md"],
                        },
                        "personal": {
                            "base": "/path/to/obsidian/personal-vault",
                            "diary_dir": "个人日记",
                            "template": "日记模板.md",
                            "exclude_meta": ["AGENTS.md"],
                        },
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stdout,
        )
        sys.exit(1)

    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)

    vaults = {}
    for name, cfg in data.get("vaults", {}).items():
        vaults[name] = {
            "base": cfg["base"],
            "diary_dir": cfg["diary_dir"],
            "template": cfg["template"],
            "exclude_meta": set(cfg.get("exclude_meta", [])),
        }
    return vaults


VAULTS: dict[str, dict] = {}
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def compute_paths(vault_cfg: dict, date: datetime | None = None) -> dict:
    date = date or datetime.now()
    base = vault_cfg["base"]
    diary_dir = vault_cfg["diary_dir"]
    template_name = vault_cfg["template"]

    month_dir = f"{base}/{diary_dir}/{date.year}/{date.month:02d}"
    weekday = WEEKDAYS[date.weekday()]
    filename = f"{date.year}年{date.month}月{date.day}日{weekday}.md"
    diary_path = f"{month_dir}/{filename}"
    template_path = f"{base}/{diary_dir}/{template_name}"

    return {
        "diary_path": diary_path,
        "month_dir": month_dir,
        "template_path": template_path,
        "date": date.isoformat(),
    }


def action_locate(vault_name: str):
    cfg = VAULTS[vault_name]
    paths = compute_paths(cfg)

    exists = os.path.exists(paths["diary_path"])
    template_exists = os.path.exists(paths["template_path"])

    print(f"DIARY_PATH={paths['diary_path']}")
    print(f"DIARY_EXISTS={'true' if exists else 'false'}")
    print(f"MONTH_DIR={paths['month_dir']}")
    print(f"TEMPLATE_PATH={paths['template_path']}")
    print(f"TEMPLATE_EXISTS={'true' if template_exists else 'false'}")


def action_create(vault_name: str):
    cfg = VAULTS[vault_name]
    paths = compute_paths(cfg)

    if os.path.exists(paths["diary_path"]):
        print("EXISTS=true")
        print(f"PATH={paths['diary_path']}")
        return

    os.makedirs(paths["month_dir"], exist_ok=True)

    if not os.path.exists(paths["template_path"]):
        print(f"ERROR: Template not found: {paths['template_path']}", file=sys.stderr)
        sys.exit(1)

    shutil.copy2(paths["template_path"], paths["diary_path"])
    print("CREATED=true")
    print(f"PATH={paths['diary_path']}")


def action_todos(vault_name: str, days: int = 7):
    cfg = VAULTS[vault_name]
    base = cfg["base"]
    diary_dir = cfg["diary_dir"]
    diary_base = f"{base}/{diary_dir}"

    cutoff = datetime.now() - timedelta(days=days)
    todo_pattern = re.compile(r"^\s*-\s*\[([ ^>!/?~br])\]\s+(.+)$")

    files = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in cfg.get("exclude_meta", set()):
                continue
            fpath = os.path.join(root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append((mtime, fpath))

    files.sort(key=lambda x: x[0], reverse=True)

    todos = []
    for _, fpath in files:
        rel_path = os.path.relpath(fpath, base)
        with open(fpath, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                m = todo_pattern.match(line)
                if m and m.group(1) == " ":
                    todos.append({"file": rel_path, "line": line_no, "content": m.group(2).strip()})

    if not todos:
        print("NO_TODOS")
        return

    print(f"TODO_COUNT={len(todos)}")
    print("--- TODOS ---")
    for t in todos:
        print(f"{t['file']}:{t['line']} | {t['content']}")


def action_recent(vault_name: str, days: int = 10, limit: int = 0):
    cfg = VAULTS[vault_name]
    base = cfg["base"]
    diary_dir = cfg["diary_dir"]
    diary_base = f"{base}/{diary_dir}"

    cutoff = datetime.now() - timedelta(days=days)
    exclude = cfg.get("exclude_meta", set())

    files = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in exclude:
                continue
            fpath = os.path.join(root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append((mtime, fpath))

    files.sort(key=lambda x: x[0], reverse=True)
    if limit > 0:
        files = files[:limit]

    print(f"RECENT_COUNT={len(files)}")
    print("--- RECENT ---")
    for mtime, fpath in files:
        print(f"{mtime.strftime('%m-%d %H:%M')} {fpath}")


def action_read(vault_name: str, file_path: str | None = None):
    cfg = VAULTS[vault_name]
    target = file_path or compute_paths(cfg)["diary_path"]

    if not os.path.exists(target):
        print(f"FILE_NOT_FOUND={target}")
        return

    with open(target, encoding="utf-8") as f:
        content = f.read()

    print(f"FILE={target}")
    print(f"SIZE={len(content)}")
    print("--- CONTENT ---")
    print(content)


def _scan_todos(cfg: dict, days: int = 14) -> list[dict]:
    base = cfg["base"]
    diary_base = f"{base}/{cfg['diary_dir']}"
    cutoff = datetime.now() - timedelta(days=days)
    todo_pattern = re.compile(r"^\s*-\s*\[([ ^>!/?~br])\]\s+(.+)$")

    files = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in cfg.get("exclude_meta", set()):
                continue
            fpath = os.path.join(root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append((mtime, fpath))

    files.sort(key=lambda x: x[0], reverse=True)

    todos = []
    for _, fpath in files:
        rel_path = os.path.relpath(fpath, base)
        with open(fpath, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                m = todo_pattern.match(line)
                if m and m.group(1) == " ":
                    todos.append({"file": rel_path, "line": line_no, "content": m.group(2).strip()})
    return todos


def _scan_recent(cfg: dict, days: int = 10, limit: int = 3) -> list[tuple]:
    base = cfg["base"]
    diary_base = f"{base}/{cfg['diary_dir']}"
    cutoff = datetime.now() - timedelta(days=days)
    exclude = cfg.get("exclude_meta", set())

    files = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in exclude:
                continue
            fpath = os.path.join(root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append((mtime, fpath))

    files.sort(key=lambda x: x[0], reverse=True)
    return files[:limit] if limit > 0 else files


def _read_rules(vault_name: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ref_file = os.path.join(script_dir, "..", "references", f"{vault_name}-log.md")
    if not os.path.exists(ref_file):
        ref_file = os.path.join(script_dir, "..", "references", f"{vault_name}-diary.md")
    if os.path.exists(ref_file):
        with open(ref_file, encoding="utf-8") as f:
            return f.read().strip()
    return ""


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")


def _print_outline(
    lines: list[str], diary_path: str, max_summary_lines: int = 3, max_line_chars: int = 100
):
    total = len(lines)
    print(f"(共 {total} 行)")

    heading_indices = []
    for i, line in enumerate(lines):
        if HEADING_RE.match(line):
            heading_indices.append(i)

    print("\n## 大纲")
    for idx in heading_indices:
        print(f"{idx + 1}: {lines[idx].rstrip()}")

    print("\n## 内容摘要")
    for hi_idx, h_start in enumerate(heading_indices):
        h_end = heading_indices[hi_idx + 1] if hi_idx + 1 < len(heading_indices) else len(lines)
        heading_text = lines[h_start].rstrip()
        print(f"\n{h_start + 1}: {heading_text}")
        summary_count = 0
        for i in range(h_start + 1, h_end):
            if summary_count >= max_summary_lines:
                break
            stripped = lines[i].strip()
            if not stripped or HEADING_RE.match(stripped):
                continue
            if stripped.startswith("```"):
                continue
            display = stripped[:max_line_chars]
            if len(stripped) > max_line_chars:
                display += "..."
            print(f"{i + 1}: {display}")
            summary_count += 1

    print(
        f'\n💡 用 Read 工具读取感兴趣段落，例：Read(filePath="{diary_path}", offset=行号, limit=30)'
    )


def action_context(vault_name: str, days: int = 14):
    cfg = VAULTS[vault_name]
    paths = compute_paths(cfg)
    today = paths["diary_path"]
    exists = os.path.exists(today)

    print(f"DIARY_PATH={today}")
    print(f"DIARY_EXISTS={'true' if exists else 'false'}")
    print(f"DATE={paths['date']}")

    rules = _read_rules(vault_name)
    if rules:
        print("\n--- RULES ---")
        print(rules)

    todos = _scan_todos(cfg, days)
    if todos:
        print(f"\n--- TODOS ({len(todos)}) ---")
        for t in todos:
            print(f"{t['file']}:{t['line']} | {t['content']}")
    else:
        print("\n--- TODOS ---")
        print("NO_TODOS")

    recent = _scan_recent(cfg, days=10, limit=3)
    if recent:
        print(f"\n--- RECENT ({len(recent)}) ---")
        for mtime, fpath in recent:
            if fpath == today:
                continue
            with open(fpath, encoding="utf-8") as f:
                lines = f.readlines()[:30]
            rel = os.path.relpath(fpath, cfg["base"])
            print(f"\n## {rel} ({mtime.strftime('%m-%d %H:%M')})")
            for line in lines:
                print(line, end="")
            if len(lines) == 30:
                print("\n... (截断)")

    print("\n--- TODAY ---")
    if exists:
        with open(today, encoding="utf-8") as f:
            lines = f.readlines()
        _print_outline(lines, today)
    else:
        print("(empty - needs creation)")


def main():
    global VAULTS
    VAULTS = _load_vaults()

    parser = argparse.ArgumentParser(description="Obsidian 日记辅助脚本")
    parser.add_argument(
        "--vault",
        choices=VAULTS.keys(),
        required=True,
        help="目标 vault（取决于配置文件中定义的 vault 名称）",
    )
    parser.add_argument(
        "--action",
        choices=["locate", "create", "todos", "recent", "read", "context"],
        required=True,
        help="操作类型",
    )
    parser.add_argument("--days", type=int, default=7, help="扫描天数（用于 todos/recent/context）")
    parser.add_argument("--file", type=str, default=None, help="文件路径（用于 read）")
    parser.add_argument(
        "--limit", type=int, default=0, help="最大返回数量（用于 recent，0=不限制）"
    )

    args = parser.parse_args()

    actions = {
        "locate": lambda: action_locate(args.vault),
        "create": lambda: action_create(args.vault),
        "todos": lambda: action_todos(args.vault, args.days),
        "recent": lambda: action_recent(args.vault, args.days, args.limit),
        "read": lambda: action_read(args.vault, args.file),
        "context": lambda: action_context(args.vault, args.days),
    }

    actions[args.action]()


if __name__ == "__main__":
    main()
