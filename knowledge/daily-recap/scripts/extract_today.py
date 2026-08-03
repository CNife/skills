#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# ///
"""
extract_today.py - 提取目标工作日窗口内的 Pi/OMP 会话。

工作日窗口以 CST 04:00 为界 [工作日 04:00, 次日 04:00)：凌晨 00:00-04:00
的会话归前一工作日。"总结哪个工作日"以 12:00 为界（<12:00 昨天 / ≥12:00
今天），默认由 recap 时刻自动选择，可用位置参数或 --date 显式指定。

粗筛用 UTC 文件名日期前缀（窗口 ± 1 天），精确切读 session 行 timestamp 转 CST
判断是否落在窗口内--文件名 UTC 前缀仅作粗筛，不作切分依据。

Usage:
    uv run --script extract_today.py                          # 目标工作日（自动）
    uv run --script extract_today.py 2026-07-09               # 指定工作日
    uv run --script extract_today.py --date 2026-07-09        # 同上，显式
    uv run --script extract_today.py --min-msgs 3             # 跳过 stub 会话
    uv run --script extract_today.py --exclude <uuid>         # 排除指定 session

Output: JSON to stdout — date, total（过滤后）, total_raw（窗口内未过滤）,
filtered（被 min_msgs/exclude 滤掉的窗口内会话摘要）, sessions（按 timestamp 排序）.

Each session has: agent, filepath, session_id, timestamp, time_cst, title,
cwd, project, msg_count, first_user_msg, last_assistant_summary, error.

Session JSONL is a tree (id/parentId, in-place branching); this script reads
it linearly-see references/{pi,omp}-session-format.md for why that suffices.
"""

import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ── config ────────────────────────────────────────────────────────────────
PI_SESSION_DIR = Path.home() / ".pi" / "agent" / "sessions"
OMP_SESSION_DIR = Path.home() / ".omp" / "agent" / "sessions"
CST_OFFSET = timedelta(hours=8)
CST = ZoneInfo("Asia/Shanghai")

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
    args = {"date": None, "min_msgs": 0, "exclude": None}
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--min-msgs":
            i += 1
            args["min_msgs"] = int(sys.argv[i])
        elif arg == "--exclude":
            i += 1
            args["exclude"] = sys.argv[i]
        elif arg == "--date":
            i += 1
            args["date"] = sys.argv[i]
        elif not arg.startswith("--"):
            args["date"] = arg
        i += 1
    return args


def workday_window(target_workday: date) -> tuple[datetime, datetime]:
    """目标工作日的整理窗口 [当日 04:00, 次日 04:00) CST。

    工作日以 CST 04:00 为分界：凌晨 00:00-04:00 的会话归前一工作日。
    """
    start = datetime(
        target_workday.year, target_workday.month, target_workday.day, 4, 0, tzinfo=CST
    )
    end = start + timedelta(days=1)
    return start, end


def coarse_utc_prefixes(target_workday: date) -> list[str]:
    """粗筛用的 UTC 文件名日期前缀集合（工作日窗口 ± 1 天）。

    工作日窗口 CST [04:00, 次日 04:00) 跨两个 UTC 日期；前后各扩 1 天
    防时区/文件名边界漂移。精确切分由 session_in_window 兜底，粗筛只
    要不漏（多扫几个文件代价小）。
    """
    start_utc = workday_window(target_workday)[0].astimezone(UTC)
    end_utc = workday_window(target_workday)[1].astimezone(UTC)
    first = (start_utc - timedelta(days=1)).date()
    last = (end_utc + timedelta(days=1)).date()
    prefixes = []
    d = first
    while d <= last:
        prefixes.append(d.isoformat())
        d += timedelta(days=1)
    return prefixes


def choose_target_workday(now: datetime) -> date:
    """根据 recap 时刻选择目标工作日：以 12:00 为界，<12:00 整理昨天，≥12:00 整理今天。

    04:00 是工作日窗口边界（见 workday_window），不是"总结哪个工作日"的分界点：
    凌晨 0-4 点发起总结仍整理昨天（窗口尚未结束），午后才整理当天。now 应为
    CST 时区 aware；naive 视为 CST 本地时间。
    """
    local = now.astimezone(CST) if now.tzinfo is not None else now
    workday = local.date()
    if local.hour < 12:
        workday -= timedelta(days=1)
    return workday


def _parse_utc_timestamp(ts: str) -> datetime | None:
    """Parse a UTC timestamp string to a tz-aware datetime.

    Accepts ISO 8601 (Z or +00:00 suffix, optional milliseconds) and the
    Pi/OMP filename format (2026-07-09T06-49-49-793Z). Returns None if the
    string is empty or unparseable.
    """
    if not ts:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})-\d+Z", ts)
    if m:
        ts = f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}+00:00"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def session_in_window(timestamp_utc: str, window: tuple[datetime, datetime]) -> bool:
    """会话 timestamp 是否落在工作日窗口 [start, end) 内。

    timestamp_utc 是 session 行的 UTC 时间戳（ISO 或文件名格式）。
    无法解析的时间戳视为不在窗口内（返回 False）。
    """
    dt = _parse_utc_timestamp(timestamp_utc)
    if dt is None:
        return False
    start, end = window
    return start <= dt < end


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


def find_session_files(agent_dir: Path, date_prefixes: list[str]) -> list[Path]:
    """Find session JSONL files by filename date prefix(es) (not mtime).

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
        if any(fpath.name.startswith(p) for p in date_prefixes):
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
    raw = raw.removeprefix("home-cnife-")
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


def collect_sessions(
    target_workday: date,
    pi_dir: Path,
    omp_dir: Path,
    *,
    min_msgs: int = 0,
    exclude: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """收集目标工作日窗口内的会话（粗筛多前缀 + 04:00 精确切分）。

    返回 (sessions, filtered)：sessions 是通过过滤的会话；filtered 是窗口内
    但被 min_msgs/exclude 滤掉的会话摘要（session_id/title/msg_count/reason）。
    total: 0 而 filtered 非空时是"全被过滤"，不是"当日无会话"——调用方必须
    区分，不得据此终止。

    粗筛：coarse_utc_prefixes 给出 UTC 文件名日期前缀，扫到跨 UTC 日期的
    候选文件。精确切：读 session 行 timestamp，session_in_window 判断是否
    落在 [工作日 04:00, 次日 04:00) CST。exclude/min_msgs 在切窗口后过滤。
    """
    window = workday_window(target_workday)
    prefixes = coarse_utc_prefixes(target_workday)
    sessions: list[dict] = []
    filtered: list[dict] = []

    for dir_, extractor in ((pi_dir, extract_pi_session), (omp_dir, extract_omp_session)):
        for fp in find_session_files(dir_, prefixes):
            s = extractor(fp)
            if not session_in_window(s.get("timestamp") or "", window):
                continue
            reason = None
            if exclude and s["session_id"] and exclude in s["session_id"]:
                reason = "excluded"
            elif s["msg_count"] < min_msgs:
                reason = "min_msgs"
            if reason:
                filtered.append(
                    {
                        "session_id": s["session_id"],
                        "title": s.get("title"),
                        "msg_count": s["msg_count"],
                        "reason": reason,
                    }
                )
                continue
            s["time_cst"] = utc_to_cst(s.get("timestamp") or "")
            s["project"] = project_from_cwd(s.get("cwd")) or parse_project(fp)
            sessions.append(s)

    sessions.sort(key=lambda x: x.get("timestamp") or "")
    filtered.sort(key=lambda x: x.get("msg_count") or 0)
    return sessions, filtered


# ── main ──────────────────────────────────────────────────────────────────


def main():
    args = parse_args()
    if args["date"]:
        target_workday = date.fromisoformat(args["date"])
    else:
        target_workday = choose_target_workday(datetime.now(CST))

    sessions, filtered = collect_sessions(
        target_workday,
        PI_SESSION_DIR,
        OMP_SESSION_DIR,
        min_msgs=args["min_msgs"],
        exclude=args["exclude"],
    )
    output = {
        "date": target_workday.isoformat(),
        "total": len(sessions),
        "total_raw": len(sessions) + len(filtered),
        "filtered": filtered,
        "sessions": sessions,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
