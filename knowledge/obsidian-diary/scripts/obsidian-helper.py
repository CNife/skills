#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Obsidian 日记上下文输出脚本。

用法:
    uv run obsidian-helper.py --vault work
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
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


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


def compute_paths(vault_cfg: dict, date: datetime | None = None) -> dict:
    date = date or datetime.now()
    month_dir = f"{vault_cfg['base']}/{vault_cfg['diary_dir']}/{date.year}/{date.month:02d}"
    filename = f"{date.year}年{date.month}月{date.day}日{WEEKDAYS[date.weekday()]}.md"
    return {
        "diary_path": f"{month_dir}/{filename}",
        "month_dir": month_dir,
        "template_path": f"{vault_cfg['base']}/{vault_cfg['diary_dir']}/{vault_cfg['template']}",
        "date": date.isoformat(),
    }


def _scan_todos(cfg: dict, days: int = 14) -> list[dict]:
    base = cfg["base"]
    diary_base = f"{base}/{cfg['diary_dir']}"
    cutoff = datetime.now() - timedelta(days=days)
    todo_pattern = re.compile(r"^\s*-\s*\[([ ^>!/?~br])\]\s+(.+)$")

    results = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in cfg.get("exclude_meta", set()):
                continue
            fpath = os.path.join(root, fname)
            if datetime.fromtimestamp(os.path.getmtime(fpath)) < cutoff:
                continue
            rel = os.path.relpath(fpath, base)
            with open(fpath, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    m = todo_pattern.match(line)
                    if m and m.group(1) == " ":
                        results.append(
                            {"file": rel, "line": line_no, "content": m.group(2).strip()}
                        )
    return results


def _scan_recent(cfg: dict, days: int = 10, limit: int = 3) -> list[tuple]:
    base = cfg["base"]
    diary_base = f"{base}/{cfg['diary_dir']}"
    cutoff = datetime.now() - timedelta(days=days)
    exclude = cfg.get("exclude_meta", set())

    results = []
    for root, _, filenames in os.walk(diary_base):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            if fname.endswith("模板.md") or fname in exclude:
                continue
            fpath = os.path.join(root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                results.append((mtime, fpath))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:limit] if limit > 0 else results


def main():
    parser = argparse.ArgumentParser(description="Obsidian 日记上下文输出")
    parser.add_argument(
        "--vault", required=True, help="目标 vault（取决于配置文件中定义的 vault 名称）"
    )
    args = parser.parse_args()

    vaults = _load_vaults()
    if args.vault not in vaults:
        print(f"ERROR: Unknown vault '{args.vault}'", file=sys.stderr)
        print(f"Available: {', '.join(vaults.keys())}", file=sys.stderr)
        sys.exit(1)

    cfg = vaults[args.vault]
    paths = compute_paths(cfg)
    today = paths["diary_path"]
    exists = os.path.exists(today)

    # 自动创建：日记不存在时从模板复制
    if not exists:
        if os.path.exists(paths["template_path"]):
            os.makedirs(paths["month_dir"], exist_ok=True)
            shutil.copy2(paths["template_path"], today)
            exists = True
        else:
            print(f"ERROR: Template not found: {paths['template_path']}", file=sys.stderr)
            sys.exit(1)

    # 1. 路径信息
    print(f"DIARY_PATH={today}")
    print(f"DIARY_EXISTS={'true' if exists else 'false'}")
    print(f"DATE={paths['date']}")

    # 3. 未完成待办
    todos = _scan_todos(cfg)
    if todos:
        print(f"\n--- TODOS ({len(todos)}) ---")
        for t in todos:
            print(f"{t['file']}:{t['line']} | {t['content']}")
    else:
        print("\n--- TODOS ---")
        print("NO_TODOS")

    # 4. 近期日记（前 3 篇，前 30 行）
    recent = _scan_recent(cfg)
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

    # 5. 今日日记全文
    print("\n--- TODAY ---")
    if exists:
        with open(today, encoding="utf-8") as f:
            print(f.read().strip())
    else:
        print("(empty)")


if __name__ == "__main__":
    main()
