#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""
thread_digest.py - 把 nmem 线程压成 collector 可读的紧凑文本。

`nmem threads show <id> --json` 原样取回会把每条消息的完整正文（含首条 1-13 KB
的 system-notice / 技能提示前言）倒进上下文：30 条约 57 KB，500 条的线程约
950 KB。`--content-limit` 在 --json 下不生效（人读输出才生效），所以截断要在
取回后自己做。本脚本一次取回、本地截断、剥前言，按「首 N + 尾 N（+ 可选全部
用户消息）」输出，标题与消息总数单独成行便于 collector 记来源指针。

Usage:
    uv run --script thread_digest.py <thread_id> [<thread_id> ...]
    uv run --script thread_digest.py <thread_id> --all-users --chars 900
    uv run --script thread_digest.py --from-json saved.json

Output: 人读文本——每条线程一段：标题、id、消息总数，随后逐条 `--- #<index> <role>`
    与截断后的正文，末尾一行选中统计。取数失败打印到 stderr，其余线程照常输出。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_CHARS = 700
DEFAULT_HEAD = 20
DEFAULT_TAIL = 20

SYSTEM_BLOCK = re.compile(r"<system-notice>.*?</system-notice>", re.DOTALL)
CONTEXT_HEADER = re.compile(r"^OMP custom context \([^)]*\):[ \t]*$", re.MULTILINE)
BLANK_RUN = re.compile(r"\n{3,}")


def clean(text: str) -> str:
    """剥掉机器前言：system-notice 整块与 OMP custom context 的标签行。"""
    text = SYSTEM_BLOCK.sub("[stripped system-notice]", text)
    text = CONTEXT_HEADER.sub("[skill-prompt follows]", text)
    return BLANK_RUN.sub("\n\n", text).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...[+{len(text) - limit} chars]"


def select_positions(messages: list[dict[str, Any]], head: int, tail: int, all_users: bool) -> list[int]:
    """首 head 条 + 尾 tail 条；all_users 时再并入中段的全部 user 消息。"""
    total = len(messages)
    keep = set(range(min(head, total))) | set(range(max(total - tail, 0), total))
    if all_users:
        keep |= {pos for pos, message in enumerate(messages) if message.get("role") == "user"}
    return sorted(keep)


def digest(
    data: dict[str, Any],
    chars: int = DEFAULT_CHARS,
    head: int = DEFAULT_HEAD,
    tail: int = DEFAULT_TAIL,
    all_users: bool = False,
) -> str:
    messages: list[dict[str, Any]] = data.get("messages") or []
    title = (data.get("title") or "").strip() or "(无标题)"
    thread_id = data.get("id") or "?"
    total = data.get("total_messages") or data.get("message_count") or len(messages)

    lines = [f"## {title}", f"id={thread_id} messages={total}"]
    positions = select_positions(messages, head, tail, all_users)
    previous = -1
    for pos in positions:
        if previous >= 0 and pos > previous + 1:
            lines.append(f"--- ({pos - previous - 1} 条未选中)")
        message = messages[pos]
        index = message.get("index", pos)
        role = message.get("role", "?")
        lines.append(f"--- #{index} {role}")
        lines.append(truncate(clean(str(message.get("content") or "")), chars))
        previous = pos
    lines.append(
        f"[选中 {len(positions)}/{len(messages)} 条 | head={head} tail={tail} all_users={all_users} chars={chars}]"
    )
    return "\n".join(lines)


def fetch(thread_id: str, limit: int) -> dict[str, Any]:
    command = ["nmem", "threads", "show", thread_id, "--json", "--limit", str(limit)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or f"nmem exit {result.returncode}"
        raise RuntimeError(detail)
    return json.loads(result.stdout)


def load_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 nmem 线程压成紧凑摘要")
    parser.add_argument("thread_ids", nargs="*", help="nmem thread id（可多个）")
    parser.add_argument("--chars", type=int, default=DEFAULT_CHARS, help=f"每条消息截断字数（默认 {DEFAULT_CHARS}）")
    parser.add_argument("--head", type=int, default=DEFAULT_HEAD, help=f"取首 N 条（默认 {DEFAULT_HEAD}）")
    parser.add_argument("--tail", type=int, default=DEFAULT_TAIL, help=f"取尾 N 条（默认 {DEFAULT_TAIL}）")
    parser.add_argument("--all-users", action="store_true", help="额外并入中段的全部 user 消息")
    parser.add_argument("--limit", type=int, default=100000, help="单次 nmem 取回的消息上限（默认全取）")
    parser.add_argument("--from-json", help="离线摘要一份已保存的 threads show JSON（- 读 stdin），供测试与复核用")
    args = parser.parse_args(argv)

    if not args.thread_ids and not args.from_json:
        parser.error("需要至少一个 thread id，或 --from-json")

    if args.from_json:
        print(digest(load_json(args.from_json), args.chars, args.head, args.tail, args.all_users))
        return 0

    failures = 0
    for thread_id in args.thread_ids:
        try:
            data = fetch(thread_id, args.limit)
        except (RuntimeError, json.JSONDecodeError, OSError) as error:
            print(f"{thread_id}: 取数失败: {error}", file=sys.stderr)
            failures += 1
            continue
        print(digest(data, args.chars, args.head, args.tail, args.all_users))
        print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
