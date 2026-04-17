#!/usr/bin/env python3
"""Obsidian 日记辅助脚本：路径计算、文件创建、待办查询。

用法:
    python3 scripts/obsidian-helper.py --vault work --action locate
    python3 scripts/obsidian-helper.py --vault personal --action locate
    python3 scripts/obsidian-helper.py --vault work --action create
    python3 scripts/obsidian-helper.py --vault work --action todos
    python3 scripts/obsidian-helper.py --vault work --action recent --days 10
"""

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timedelta

VAULTS = {
    "work": {
        "base": "/mnt/c/Obsidian/工作",
        "diary_dir": "工作日志",
        "template": "日志模板.md",
        "exclude_meta": {"AGENTS.md", "任务.md", "日志模板.md"},
    },
    "personal": {
        "base": "/mnt/c/Obsidian/个人",
        "diary_dir": "个人日记",
        "template": "日记模板.md",
        "exclude_meta": {"AGENTS.md"},
    },
}

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
        with open(fpath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                m = todo_pattern.match(line)
                if m and m.group(1) == " ":
                    todos.append(
                        {
                            "file": rel_path,
                            "line": line_no,
                            "content": m.group(2).strip(),
                        }
                    )

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

    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"FILE={target}")
    print(f"SIZE={len(content)}")
    print("--- CONTENT ---")
    print(content)


def main():
    parser = argparse.ArgumentParser(description="Obsidian 日记辅助脚本")
    parser.add_argument(
        "--vault",
        choices=VAULTS.keys(),
        required=True,
        help="目标 vault：work（工作日志）或 personal（个人日记）",
    )
    parser.add_argument(
        "--action",
        choices=["locate", "create", "todos", "recent", "read"],
        required=True,
        help="操作类型",
    )
    parser.add_argument("--days", type=int, default=7, help="扫描天数（用于 todos/recent）")
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
    }

    actions[args.action]()


if __name__ == "__main__":
    main()
