# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".local/share/opencode/opencode.db"


def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def extract_user_text(msg: dict, part: dict | None) -> str:
    if part and part.get("type") == "text":
        return truncate(part.get("text", ""), 300)
    return "(无文本内容)"


def format_tool_call(part: dict) -> str:
    tool = part.get("tool", "unknown")
    state = part.get("state", {})
    status = state.get("status", "unknown")

    if tool == "bash" and status == "completed":
        cmd = truncate(state.get("input", {}).get("command", ""), 150)
        output = truncate(state.get("output", ""), 100)
        line = f"  → bash: {cmd}"
        if output:
            line += f"\n    输出: {output}"
        return line

    if tool == "write" and status == "completed":
        path = state.get("input", {}).get("path", "")
        content = state.get("input", {}).get("content", "")
        lines_changed = content.count("\n") + 1 if content else 0
        return f"  → write: {path} (+{lines_changed} lines)"

    if tool == "read" and status == "completed":
        path = state.get("input", {}).get("path", "")
        return f"  → read: {path}"

    if tool == "edit" and status == "completed":
        path = state.get("input", {}).get("path", "")
        return f"  → edit: {path}"

    input_preview = truncate(json.dumps(state.get("input", {}), ensure_ascii=False), 100)
    output_preview = truncate(state.get("output", ""), 100)
    line = f"  → {tool}: {input_preview}"
    if output_preview:
        line += f"\n    输出: {output_preview}"
    return line


def extract_session(db: sqlite3.Connection, session_id: str, since_ts: int) -> str | None:
    row = db.execute(
        "SELECT id, title, directory, time_created, time_updated FROM session WHERE id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return None

    rows = db.execute(
        """
        SELECT m.data as msg_data, p.data as part_data
        FROM message m
        LEFT JOIN part p ON p.message_id = m.id
        WHERE m.session_id = ? AND m.time_created >= ?
        ORDER BY m.time_created, p.time_created
        """,
        (session_id, since_ts),
    ).fetchall()

    turns = []
    current_turn = None
    for msg_data, part_data in rows:
        msg = json.loads(msg_data)
        part = json.loads(part_data) if part_data else None

        if msg["role"] == "user":
            if current_turn:
                turns.append(current_turn)
            current_turn = {
                "user_prompt": extract_user_text(msg, part),
                "tool_calls": [],
                "assistant_text": None,
            }
        elif part and current_turn:
            if part["type"] == "tool":
                current_turn["tool_calls"].append(part)
            elif part["type"] == "text":
                current_turn["assistant_text"] = truncate(part.get("text", ""), 200)

    if current_turn:
        turns.append(current_turn)

    if not turns:
        return None

    lines = [
        f"=== Session: {row[1]} ({row[0]})",
        f"Project: {row[2]}",
        "",
    ]
    for turn in turns:
        lines.append(f"[User] {turn['user_prompt']}")
        for tc in turn["tool_calls"]:
            lines.append(format_tool_call(tc))
        if turn.get("assistant_text"):
            lines.append(f"  → text: {turn['assistant_text']}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", type=str, default="today")
    parser.add_argument("--directory", type=str)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if args.since == "today":
        since_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        since_dt = datetime.fromisoformat(args.since)
    since_ts = int(since_dt.timestamp() * 1000)

    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        return

    db = sqlite3.connect(DB_PATH)

    sessions = db.execute(
        """
        SELECT id FROM session
        WHERE time_updated >= ? AND parent_id IS NULL
        ORDER BY time_created DESC
        LIMIT ?
        """,
        (since_ts, args.limit),
    ).fetchall()

    results = []
    for (sid,) in sessions:
        if args.directory:
            dir_row = db.execute("SELECT directory FROM session WHERE id = ?", (sid,)).fetchone()
            if dir_row and dir_row[0] != args.directory:
                continue
        text = extract_session(db, sid, since_ts)
        if text:
            results.append(text)

    db.close()

    if not results:
        print("今日无会话记录。")
        return

    print("--- OpenCode 今日会话记录 ---")
    print(f"时间范围: {since_dt.strftime('%Y-%m-%d')} 00:00 起")
    print(f"会话数: {len(results)}")
    print()
    print("\n---\n".join(results))
    print("--- 记录结束 ---")


if __name__ == "__main__":
    main()
