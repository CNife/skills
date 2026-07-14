#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# ///
"""
extract_today.py - Extract today's session files from Pi and OMP directories.

Usage:
    uv run --script extract_today.py                          # today (UTC date)
    uv run --script extract_today.py 2026-07-09               # specific date
    uv run --script extract_today.py --min-msgs 3             # skip stub sessions
    uv run --script extract_today.py --exclude <uuid>         # exclude current session

Output: JSON to stdout with sessions array sorted by timestamp.

Each session has: agent, filepath, session_id, timestamp, time_cst, title,
cwd, project, msg_count, first_user_msg, last_assistant_summary, error.

Session JSONL is a tree - entries link via id/parentId, with in-place
branching (see references/pi-session-format.md, references/omp-session-format.md).
This script reads it linearly: msg_count counts messages across all branches,
and last_assistant_summary is the physically-last assistant message. This is
acceptable for --min-msgs stub filtering because stubs never branch, and
append-only branching keeps the last line close to the current leaf.
"""

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────
PI_SESSION_DIR = Path.home() / ".pi" / "agent" / "sessions"
OMP_SESSION_DIR = Path.home() / ".omp" / "agent" / "sessions"
CST_OFFSET = timedelta(hours=8)

# OMP emits extra entry types (model changes, compaction, branch summaries,
# extension messages, ...) that Pi does not route through its message stream.
# Skip them so msg_count reflects conversational messages only.
OMP_SKIP_TYPES = frozenset(
    {
        "model_change",
        "thinking_level_change",
        "compaction",
        "branch_summary",
        "custom_message",
        "session_init",
        "mode_change",
        "custom",
    }
)


# ── helpers ───────────────────────────────────────────────────────────────


def parse_args():
    args = {"date": date.today().isoformat(), "min_msgs": 0, "exclude": None}
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--min-msgs":
            i += 1
            args["min_msgs"] = int(sys.argv[i])
        elif arg == "--exclude":
            i += 1
            args["exclude"] = sys.argv[i]
        elif not arg.startswith("--"):
            args["date"] = arg
        i += 1
    return args


def utc_to_cst(utc_ts: str) -> str:
    """Convert a UTC timestamp to CST (UTC+8) time string HH:MM."""
    if not utc_ts:
        return "?"
    try:
        dt = datetime.fromisoformat(utc_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            # Filename format: 2026-07-09T06-49-49-793Z
            m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})-\d+Z", utc_ts)
            if m:
                dt_str = f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}+00:00"
                dt = datetime.fromisoformat(dt_str)
            else:
                return "?"
        except (ValueError, TypeError):
            return "?"
    cst = dt + CST_OFFSET
    return f"{cst.hour:02d}:{cst.minute:02d} CST"


def find_session_files(agent_dir: Path, date_prefix: str) -> list[Path]:
    """Find session JSONL files by filename date prefix (not mtime).

    OMP stores each session as a <timestamp>_<uuid>/ directory holding a main
    <timestamp>_<uuid>.jsonl plus sub-agent files (__advisor.jsonl, Verify*.jsonl,
    ...). Only the main file's name starts with the date prefix, so sub-agent
    files are intentionally excluded: they are auxiliary tasks that don't change
    the session's conclusion. See references/omp-session-format.md.
    """
    if not agent_dir.is_dir():
        return []
    files = []
    for fpath in agent_dir.rglob("*.jsonl"):
        if fpath.name.startswith(date_prefix):
            files.append(fpath)
    return sorted(files)


def project_from_cwd(cwd: str | None) -> str | None:
    """Derive project name from session cwd (relative to home dir)."""
    if not cwd:
        return None
    home = str(Path.home())
    if cwd.startswith(home + "/"):
        return cwd[len(home) + 1 :]
    if cwd.startswith(home):
        return cwd[len(home) :]
    return cwd


def parse_project(filepath: Path) -> str:
    """
    Derive a readable project name from the session directory path.

    Session dirs use -- as separator: --home-cnife-code-foo-- -> code/foo
    """
    parts = filepath.parts
    try:
        idx = parts.index("sessions")
        raw = parts[idx + 1] if idx + 1 < len(parts) else "?"
    except ValueError:
        return "?"

    # Strip outer -- and split
    raw = raw.strip("-")
    # home-cnife- prefix -> drop
    if raw.startswith("home-cnife-"):
        raw = raw[len("home-cnife-") :]
    # mnt-c- prefix -> /mnt/c/
    if raw.startswith("mnt-c-"):
        return "/mnt/c/" + raw[len("mnt-c-") :]
    # tmp-herdr-harness-* -> tmp (boot sessions)
    if raw.startswith("tmp-herdr-harness"):
        return "tmp"
    # Handle relative paths like code/onereason/backend
    raw = raw.replace("--", "/")
    return raw


# ── Per-session extraction ────────────────────────────────────────────────


def _extract_text(content) -> str:
    """Concatenate text blocks from a message content field."""
    if isinstance(content, list):
        return " ".join(
            c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
        )
    return content if isinstance(content, str) else ""


def extract_session(
    filepath: Path,
    *,
    agent: str,
    title_type: str,
    title_field: str,
    skip_types: frozenset[str] = frozenset(),
) -> dict:
    """Extract session info from a Pi/OMP JSONL file (shared linear parser).

    Per-format differences are parameterized:
    - title_type / title_field: where the title lives
      (pi: session_info.name; omp: title.title)
    - skip_types: entry types to skip entirely (omp emits several)
    """
    result = {
        "agent": agent,
        "filepath": str(filepath),
        "session_id": None,
        "timestamp": None,
        "title": None,
        "cwd": None,
        "msg_count": 0,
        "first_user_msg": None,
        "last_assistant_summary": None,
        "error": None,
    }

    try:
        with open(filepath) as f:
            lines = f.readlines()
    except (OSError, PermissionError) as e:
        result["error"] = str(e)
        return result

    last_assistant_text = None
    first_user_found = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        t = obj.get("type", "")
        if t in skip_types:
            continue

        if t == "session":
            result["session_id"] = obj.get("id")
            result["timestamp"] = obj.get("timestamp")
            result["cwd"] = obj.get("cwd")
        elif t == title_type:
            name = obj.get(title_field)
            if name:
                result["title"] = name
        elif t == "message":
            msg = obj.get("message", {})
            role = msg.get("role", "")
            text = _extract_text(msg.get("content", []))
            result["msg_count"] += 1
            if role == "user" and not first_user_found and text.strip():
                result["first_user_msg"] = text[:300]
                first_user_found = True
            if role == "assistant" and text.strip():
                last_assistant_text = text

    if last_assistant_text:
        result["last_assistant_summary"] = last_assistant_text[:500]

    return result


def extract_pi_session(filepath: Path) -> dict:
    """Extract session info from a Pi Agent JSONL file."""
    return extract_session(filepath, agent="pi", title_type="session_info", title_field="name")


def extract_omp_session(filepath: Path) -> dict:
    """Extract session info from an OMP JSONL file."""
    return extract_session(
        filepath, agent="omp", title_type="title", title_field="title", skip_types=OMP_SKIP_TYPES
    )


# ── main ──────────────────────────────────────────────────────────────────


def main():
    args = parse_args()
    day = args["date"]
    min_msgs = args["min_msgs"]
    exclude_uuid = args["exclude"]

    pi_files = find_session_files(PI_SESSION_DIR, day)
    omp_files = find_session_files(OMP_SESSION_DIR, day)

    sessions = []

    for fp in pi_files:
        s = extract_pi_session(fp)
        if exclude_uuid and s["session_id"] and exclude_uuid in s["session_id"]:
            continue
        if s["msg_count"] < min_msgs:
            continue
        s["time_cst"] = utc_to_cst(s.get("timestamp") or "")
        s["project"] = project_from_cwd(s.get("cwd")) or parse_project(fp)
        sessions.append(s)

    for fp in omp_files:
        s = extract_omp_session(fp)
        if exclude_uuid and s["session_id"] and exclude_uuid in s["session_id"]:
            continue
        if s["msg_count"] < min_msgs:
            continue
        s["time_cst"] = utc_to_cst(s.get("timestamp") or "")
        s["project"] = project_from_cwd(s.get("cwd")) or parse_project(fp)
        sessions.append(s)

    # Sort by timestamp
    sessions.sort(key=lambda x: x.get("timestamp") or "")

    output = {"date": day, "total": len(sessions), "sessions": sessions}

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
