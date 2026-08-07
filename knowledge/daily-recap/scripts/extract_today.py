#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# ///
"""
extract_today.py - 确定目标工作日，并可按 UUID v7 时间窗口过滤 nmem 线程。

工作日窗口以 CST 04:00 为界 [工作日 04:00, 次日 04:00)：凌晨 00:00-04:00
的会话归前一工作日。"总结哪个工作日"以 12:00 为界（<12:00 昨天 / ≥12:00
今天），默认由 recap 时刻自动选择，可用位置参数或 --date 显式指定。

nmem 是会话唯一来源（多机器同步）。本脚本确定目标工作日；--filter 模式从
stdin 读 nmem threads list --json 输出，按 UUID v7 时间戳过滤窗口内候选。

Usage:
    uv run --script extract_today.py                          # 目标工作日（自动）
    uv run --script extract_today.py 2026-07-09               # 指定工作日
    uv run --script extract_today.py --date 2026-07-09        # 同上，显式
    nmem threads list --limit 200 --json | uv run --script extract_today.py --filter
    nmem threads list --limit 200 --json | uv run --script extract_today.py --filter --date 2026-07-09

Output（默认）: JSON - date（目标工作日 YYYY-MM-DD）.
Output（--filter）: JSON - date, total, candidates（窗口内线程）, excluded（窗口外）.

UUID v7 前 48 位（12 hex）编码会话开始时间的毫秒级 Unix 时间戳，从线程 id
直接解析，无需 REST 调用（见 CONTEXT.md「线程 ID 时间戳」）。
"""

import json
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")


# ── helpers ───────────────────────────────────────────────────────────────


def parse_args() -> dict[str, str | bool | None]:
    args: dict[str, str | bool | None] = {"date": None, "filter": False}
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--date":
            i += 1
            args["date"] = sys.argv[i]
        elif arg == "--filter":
            args["filter"] = True
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


def uuid_v7_timestamp(thread_id: str) -> datetime | None:
    """从 UUID v7 线程 id 解析会话开始时间（tz-aware UTC datetime）。

    Pi/OMP 线程 id 为 UUID v7，去 pi-/omp- 前缀、去连字符后取前 12 位十六进制，
    即会话开始时间的毫秒级 Unix 时间戳。编码的是会话开始时间（UUID 生成时刻），
    不是 nmem 导入时间，对 t sync 导入的旧会话同样准确。无法解析返回 None。
    """
    if not thread_id:
        return None
    tid = thread_id.removeprefix("pi-").removeprefix("omp-").replace("-", "")
    if len(tid) < 12:
        return None
    try:
        ms = int(tid[:12], 16)
    except ValueError:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def thread_in_window(thread_id: str, window: tuple[datetime, datetime]) -> bool:
    """线程 id 的 UUID v7 时间戳是否落在工作日窗口 [start, end) 内。

    无法解析的线程 id 视为不在窗口内（返回 False）。
    """
    dt = uuid_v7_timestamp(thread_id)
    if dt is None:
        return False
    start, end = window
    return start <= dt < end


def filter_threads(
    threads: list[dict], window: tuple[datetime, datetime]
) -> tuple[list[dict], list[dict]]:
    """按 UUID v7 时间戳过滤 nmem 线程列表。

    返回 (candidates, excluded)：candidates 是窗口内线程，excluded 是窗口外。
    无法解析 UUID v7 的线程归入 candidates（不因解析失败丢弃，交 collector 复核）。
    """
    candidates: list[dict] = []
    excluded: list[dict] = []
    for t in threads:
        tid = t.get("id", "")
        ts = uuid_v7_timestamp(tid)
        if ts is None or thread_in_window(tid, window):
            candidates.append(t)
        else:
            excluded.append(t)
    return candidates, excluded


# ── main ──────────────────────────────────────────────────────────────────


def main():
    args = parse_args()
    if args["date"]:
        target_workday = date.fromisoformat(args["date"])
    else:
        target_workday = choose_target_workday(datetime.now(CST))

    if args["filter"]:
        # 从 stdin 读 nmem threads list --json 输出，按 UUID v7 窗口过滤
        data = json.load(sys.stdin)
        threads = data.get("threads", data) if isinstance(data, dict) else data
        window = workday_window(target_workday)
        candidates, excluded = filter_threads(threads, window)
        output = {
            "date": target_workday.isoformat(),
            "total": len(candidates),
            "candidates": candidates,
            "excluded": excluded,
        }
    else:
        output = {"date": target_workday.isoformat()}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
