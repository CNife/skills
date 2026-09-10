#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""
extract_today.py - 确定目标工作日，并过滤/分类 nmem 线程。

工作日窗口以 CST 04:00 为界 [工作日 04:00, 次日 04:00)：凌晨 00:00-04:00
的会话归前一工作日。"总结哪个工作日"以 12:00 为界（<12:00 昨天 / ≥12:00
今天），默认由 recap 时刻自动选择，可用位置参数或 --date 显式指定。

nmem 是会话唯一来源（多机器同步）。三种模式：
- 默认：确定目标工作日
- --filter：从 stdin 读 nmem threads list --json 输出，按 UUID v7 时间戳过滤
  窗口内线程，并把窗口内的机器会话按标题族分组（advisor 镜像 / 子代理任务 /
  上一轮 recap 自身及子代）
- --check：从 stdin 读 thread_id 列表，逐条报告开始时间（CST）与窗口归属，
  供 collector 批量复核

Usage:
    uv run --script extract_today.py                          # 目标工作日（自动）
    uv run --script extract_today.py 2026-07-09               # 指定工作日
    uv run --script extract_today.py --date 2026-07-09        # 同上，显式
    nmem threads list --limit 200 --json | uv run --script extract_today.py --filter
    printf '%s\n' omp-xxx omp-yyy | uv run --script extract_today.py --check --date 2026-07-09

Output（默认）: JSON - date.
Output（--filter）: JSON - date, total, candidates（窗口内非机器线程）,
    machine（窗口内机器会话按族分组）, excluded（窗口外线程）.
Output（--check）: 每行 <thread_id>\t<CST 时间>\t<in|out|unparseable>，首行窗口说明.

UUID v7 前 48 位（12 hex）编码会话开始时间的毫秒级 Unix 时间戳，从线程 id
直接解析，无需 REST 调用（见 CONTEXT.md「线程 ID 时间戳」）。
"""

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

# 机器会话标题族：agent 工具链自动产生、整理日报时默认跳过的线程（跳过必留痕）。
# 识别不了的标题照常进候选；发现新族先取证再补进这里。
MACHINE_TITLE_FAMILIES: list[tuple[str, re.Pattern[str]]] = [
    ("advisor", re.compile(r"^### Session update")),
    ("subagent", re.compile(r"^(?:Complete assignment thoroughly|# Target|# Change)")),
    (
        "recap",
        re.compile(
            r"收集「|事件证据收集|每日工作整理|\*\*目标工作日\*\*|\*\*主题域\*\*|日报.{0,6}核验|daily[\s-]?recap"
        ),
    ),
]


# ── helpers ───────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="确定目标工作日，并过滤/分类 nmem 线程。")
    parser.add_argument("date", nargs="?", default=None, help="目标工作日 YYYY-MM-DD（默认自动选择）")
    parser.add_argument("--date", dest="date_opt", default=None, help="同位置参数，显式指定目标工作日")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--filter", action="store_true", help="从 stdin 读 nmem JSON，按窗口过滤并分类机器会话")
    mode.add_argument("--check", action="store_true", help="从 stdin 读 thread_id 列表，逐条报告窗口归属")
    args = parser.parse_args()
    args.date = args.date_opt or args.date
    return args


def workday_window(target_workday: date) -> tuple[datetime, datetime]:
    """目标工作日的整理窗口 [当日 04:00, 次日 04:00) CST。

    工作日以 CST 04:00 为分界：凌晨 00:00-04:00 的会话归前一工作日。
    """
    start = datetime(target_workday.year, target_workday.month, target_workday.day, 4, 0, tzinfo=CST)
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


def filter_threads(threads: list[dict], window: tuple[datetime, datetime]) -> tuple[list[dict], list[dict]]:
    """按 UUID v7 时间戳过滤 nmem 线程列表。

    返回 (candidates, excluded)：candidates 是窗口内线程，excluded 是窗口外。
    无法解析 UUID v7 的线程归入 candidates（不因解析失败丢弃）。
    """
    candidates: list[dict] = []
    excluded: list[dict] = []
    start, end = window
    for t in threads:
        ts = uuid_v7_timestamp(t.get("id", ""))
        if ts is None or start <= ts < end:
            candidates.append(t)
        else:
            excluded.append(t)
    return candidates, excluded


def classify_machine(title: str) -> str | None:
    """按标题族判断机器会话，返回族名（advisor/subagent/recap）或 None。"""
    for family, pattern in MACHINE_TITLE_FAMILIES:
        if pattern.search(title):
            return family
    return None


def partition_threads(
    threads: list[dict], window: tuple[datetime, datetime]
) -> tuple[list[dict], dict[str, list[dict]], list[dict]]:
    """窗口过滤 + 机器会话分类。

    返回 (candidates, machine, excluded)：candidates 是窗口内非机器线程；
    machine 是窗口内机器线程按族分组（空族省略）；excluded 是窗口外线程。
    无法解析 UUID v7 的线程不丢弃，先归入 candidates 再参与机器分类。
    """
    candidates, excluded = filter_threads(threads, window)
    machine: dict[str, list[dict]] = {}
    human: list[dict] = []
    for t in candidates:
        family = classify_machine(t.get("title") or "")
        if family is None:
            human.append(t)
        else:
            machine.setdefault(family, []).append(t)
    return human, machine, excluded


def check_lines(thread_ids: list[str], window: tuple[datetime, datetime]) -> list[str]:
    """逐条报告线程的 CST 开始时间与窗口归属（供 collector 批量复核）。"""
    start, end = window
    lines = [f"窗口 [{start:%Y-%m-%d %H:%M}, {end:%Y-%m-%d %H:%M}) CST"]
    for tid in thread_ids:
        ts = uuid_v7_timestamp(tid)
        if ts is None:
            lines.append(f"{tid}\t?\tunparseable")
            continue
        local = ts.astimezone(CST)
        state = "in" if start <= ts < end else "out"
        lines.append(f"{tid}\t{local:%Y-%m-%d %H:%M:%S} CST\t{state}")
    return lines


# ── main ──────────────────────────────────────────────────────────────────


def main():
    args = parse_args()
    if args.date:
        target_workday = date.fromisoformat(args.date)
    else:
        target_workday = choose_target_workday(datetime.now(CST))
    window = workday_window(target_workday)

    if args.filter:
        # 从 stdin 读 nmem threads list --json 输出，按 UUID v7 窗口过滤并分类机器会话
        data = json.load(sys.stdin)
        threads = data.get("threads", data) if isinstance(data, dict) else data
        candidates, machine, excluded = partition_threads(threads, window)
        output = {
            "date": target_workday.isoformat(),
            "total": len(threads),
            "candidates": candidates,
            "machine": machine,
            "excluded": excluded,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.check:
        thread_ids = [line.strip() for line in sys.stdin if line.strip()]
        print("\n".join(check_lines(thread_ids, window)))
    else:
        print(json.dumps({"date": target_workday.isoformat()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
