# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".local/share/opencode/opencode.db"
QWEN_DATA_DIR = Path.home() / ".qwen"


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


QWEN_TMP_DIR = QWEN_DATA_DIR / "tmp"
QWEN_PROJECTS_DIR = QWEN_DATA_DIR / "projects"


def _resolve_project_path(hash_str: str) -> str:
    for proj_dir in sorted(QWEN_PROJECTS_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        name = proj_dir.name[1:] if proj_dir.name.startswith("-") else proj_dir.name
        candidate = "/" + name.replace("-", "/")
        if hashlib.sha256(candidate.encode()).hexdigest() == hash_str:
            return candidate
        parts = name.split("-")
        for i in range(1, len(parts)):
            candidate = "/" + "/".join(parts[:i]) + "." + "/".join(parts[i:])
            if hashlib.sha256(candidate.encode()).hexdigest() == hash_str:
                return candidate
    return f"<unknown:{hash_str[:12]}>"


def _parse_qwen_chat(chat_path: Path, since_ts: int) -> list[dict] | None:
    turns = []
    current_turn = None

    try:
        with open(chat_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = entry.get("timestamp", "")
                if ts_str:
                    try:
                        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if int(ts_dt.timestamp() * 1000) < since_ts:
                            continue
                    except (ValueError, OSError):
                        pass

                entry_type = entry.get("type", "")

                if entry_type == "system":
                    payload = entry.get("systemPayload", {})
                    if payload.get("subtype") == "slash_command":
                        phase = payload.get("phase", "")
                        raw_cmd = payload.get("rawCommand", "")
                        if phase == "invocation" and raw_cmd and current_turn is None:
                            current_turn = {
                                "user_prompt": truncate(raw_cmd, 300),
                                "tool_calls": [],
                                "assistant_text": None,
                            }
                        elif phase == "result" and current_turn:
                            items = payload.get("outputHistoryItems", [])
                            if items:
                                output_text = "\n".join(
                                    item.get("text", "") for item in items
                                )
                                current_turn["tool_calls"].append({
                                    "tool": "command",
                                    "name": raw_cmd,
                                    "output": truncate(output_text, 200),
                                })

                elif entry_type == "user":
                    if current_turn:
                        turns.append(current_turn)
                    msg = entry.get("message", "")
                    if isinstance(msg, str):
                        prompt_text = truncate(msg, 300) if msg else "(无文本内容)"
                    elif isinstance(msg, dict):
                        parts = msg.get("parts", [])
                        texts = [p.get("text", "") for p in parts if "text" in p]
                        prompt_text = truncate(" ".join(texts), 300) if texts else "(无文本内容)"
                    else:
                        prompt_text = "(无文本内容)"
                    current_turn = {
                        "user_prompt": prompt_text,
                        "tool_calls": [],
                        "assistant_text": None,
                    }

                elif entry_type == "assistant":
                    if not current_turn:
                        continue
                    message = entry.get("message", {})
                    parts = message.get("parts", [])
                    texts = []
                    for part in parts:
                        if "text" in part:
                            texts.append(part["text"])
                        elif "functionCall" in part:
                            fc = part["functionCall"]
                            tool_name = fc.get("name", "unknown")
                            args = fc.get("args", {})
                            if tool_name == "run_shell_command":
                                current_turn["tool_calls"].append({
                                    "tool": "bash",
                                    "command": truncate(args.get("command", ""), 150),
                                    "output": None,
                                })
                            elif tool_name == "write":
                                current_turn["tool_calls"].append({
                                    "tool": "write",
                                    "path": args.get("path", args.get("file_path", "")),
                                })
                            elif tool_name in ("read_file", "read"):
                                current_turn["tool_calls"].append({
                                    "tool": "read",
                                    "path": args.get("path", args.get("file_path", "")),
                                })
                            else:
                                current_turn["tool_calls"].append({
                                    "tool": tool_name,
                                    "args": truncate(json.dumps(args, ensure_ascii=False), 100),
                                })
                    if texts:
                        current_turn["assistant_text"] = truncate(" ".join(texts), 200)

                elif entry_type == "tool_result":
                    if not current_turn:
                        continue
                    message = entry.get("message", {})
                    parts = message.get("parts", [])
                    for part in parts:
                        if "functionResponse" in part:
                            output = part["functionResponse"].get("response", {}).get("output", "")
                            for tc in reversed(current_turn["tool_calls"]):
                                if tc.get("tool") == "bash" and tc.get("output") is None:
                                    tc["output"] = truncate(output, 100)
                                    break

    except (OSError, json.JSONDecodeError):
        return None

    if current_turn:
        turns.append(current_turn)

    return turns if turns else None


def _format_qwen_tool_call(tc: dict) -> str:
    tool = tc.get("tool", "unknown")

    if tool == "bash":
        cmd = tc.get("command", "")
        output = tc.get("output")
        line = f"  → bash: {cmd}"
        if output:
            line += f"\n    输出: {output}"
        return line

    if tool == "write":
        return f"  → write: {tc.get('path', '')}"

    if tool == "read":
        return f"  → read: {tc.get('path', '')}"

    if tool == "command":
        name = tc.get("name", "")
        output = tc.get("output")
        line = f"  → command: {name}"
        if output:
            line += f"\n    输出: {output}"
        return line

    return f"  → {tool}: {tc.get('args', '')}"


def extract_qwen_sessions(since_ts: int, limit: int = 50) -> list[str]:
    if not QWEN_TMP_DIR.exists():
        return []

    session_map: dict[str, list[dict]] = {}
    hash_to_sessions: dict[str, set[str]] = {}

    for logs_file in sorted(QWEN_TMP_DIR.glob("*/logs.json")):
        tmp_hash = logs_file.parent.name
        try:
            data = json.load(open(logs_file, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        today_prefix = datetime.fromtimestamp(since_ts / 1000).strftime("%Y-%m-%d")
        for msg in data:
            ts_str = msg.get("timestamp", "")
            if not ts_str or not ts_str.startswith(today_prefix):
                continue
            sid = msg.get("sessionId")
            if not sid:
                continue
            if sid not in session_map:
                session_map[sid] = []
                hash_to_sessions.setdefault(tmp_hash, set()).add(sid)
            session_map[sid].append(msg)

    results = []
    processed = 0

    for tmp_hash, session_ids in hash_to_sessions.items():
        if processed >= limit:
            break

        project_path = _resolve_project_path(tmp_hash)

        for sid in session_ids:
            if processed >= limit:
                break

            messages = session_map[sid]
            if not messages:
                continue

            turns = None
            for chat_file in QWEN_PROJECTS_DIR.glob(f"*/chats/{sid}.jsonl"):
                turns = _parse_qwen_chat(chat_file, since_ts)
                if turns:
                    break

            if not turns:
                turns = []
                for msg in messages:
                    user_text = truncate(msg.get("message", ""), 300)
                    if user_text:
                        turns.append({
                            "user_prompt": user_text,
                            "tool_calls": [],
                            "assistant_text": None,
                        })

            if not turns:
                continue

            lines = [
                f"=== Session: (Qwen Code) {sid}",
                f"Project: {project_path}",
                "",
            ]
            for turn in turns:
                lines.append(f"[User] {turn['user_prompt']}")
                for tc in turn.get("tool_calls", []):
                    lines.append(_format_qwen_tool_call(tc))
                if turn.get("assistant_text"):
                    lines.append(f"  → text: {turn['assistant_text']}")
                lines.append("")

            results.append("\n".join(lines))
            processed += 1

    return results


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
        qwen_results = extract_qwen_sessions(since_ts, args.limit)
        if not qwen_results:
            print("今日无会话记录。")
            return
        print("--- Qwen Code 今日会话记录 ---")
        print(f"时间范围: {since_dt.strftime('%Y-%m-%d')} 00:00 起")
        print(f"会话数: {len(qwen_results)}")
        print()
        print("\n---\n".join(qwen_results))
        print("--- 记录结束 ---")
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
    remaining_limit = args.limit
    for (sid,) in sessions:
        if args.directory:
            dir_row = db.execute("SELECT directory FROM session WHERE id = ?", (sid,)).fetchone()
            if dir_row and dir_row[0] != args.directory:
                continue
        text = extract_session(db, sid, since_ts)
        if text:
            results.append(text)
            remaining_limit -= 1

    db.close()

    qwen_results = extract_qwen_sessions(since_ts, remaining_limit)
    results.extend(qwen_results)

    if not results:
        print("今日无会话记录。")
        return

    source_label = "OpenCode + Qwen Code" if qwen_results else "OpenCode"
    print(f"--- {source_label} 今日会话记录 ---")
    print(f"时间范围: {since_dt.strftime('%Y-%m-%d')} 00:00 起")
    print(f"会话数: {len(results)}")
    print()
    print("\n---\n".join(results))
    print("--- 记录结束 ---")


if __name__ == "__main__":
    main()
