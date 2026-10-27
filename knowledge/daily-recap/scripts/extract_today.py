#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# ///
"""
extract_today.py - 确定目标工作日，并扫描/分类 nmem 线程。

工作日窗口以 CST 04:00 为界 [工作日 04:00, 次日 04:00)：凌晨 00:00-04:00
的会话归前一工作日。"总结哪个工作日"以 12:00 为界（<12:00 昨天 / ≥12:00
今天），默认由 recap 时刻自动选择，可用位置参数或 --date 显式指定。

nmem 是会话唯一来源（多机器同步）。三种模式：
- 默认：确定目标工作日
- --scan：自己扫完全库线程、筛窗口、分机器会话、探针判族，打印可直接进
  归类审查的候选表（含跳过留痕）。列表排序不可信，所以翻到底。
- --check：从 stdin 读 thread_id 列表，逐条报告开始时间（CST）与窗口归属，
  供 collector 批量复核

Usage:
    uv run --script extract_today.py                          # 目标工作日（自动）
    uv run --script extract_today.py 2026-07-09               # 指定工作日
    uv run --script extract_today.py --date 2026-07-09        # 同上，显式
    uv run --script extract_today.py --scan --date 2026-07-09 # 候选表（整理日报第 1 步）
    printf '%s\n' omp-xxx omp-yyy | uv run --script extract_today.py --check --date 2026-07-09

Output（默认）: JSON - date.
Output（--scan）: 人读文本——目标工作日与窗口、扫描页数、机器会话跳过留痕、
    时间未知与读取失败留痕、stub 聚合行、候选表（序号 / 消息数 / 主题 / thread_id）.
Output（--check）: 每行 <thread_id>\t<CST 时间>\t<in|out|unparseable>，首行窗口说明.

线程开始时间的判定顺序（见 GLOSSARY.md「线程 ID 时间戳」）：
1. id 里的 UUID v7（前 48 位 = 毫秒戳），任意前缀（pi-/omp-/grok-…）都认
2. id 里的日期时刻（import-YYYYMMDDhhmmss-、YYYYMMDD_hhmmss_、cron_…_YYYYMMDD_hhmmss）或 epoch 秒后缀
3. 消息级 timestamp（deepseek-harness 等 id 不带时间的来源）
4. 全都判不出时，只把 created_at 能证明早于窗口的排除，其余进候选并标注时间未知
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

# 机器会话标题族：agent 工具链自动产生、整理日报时默认跳过的线程（跳过必留痕）。
# 识别不了的标题照常进候选；发现新族先取证再补进这里。
MACHINE_TITLE_FAMILIES: list[tuple[str, re.Pattern[str]]] = [
    ("advisor", re.compile(r"^### Session update")),
    ("subagent", re.compile(r"^(?:Complete assignment thoroughly|# Target|# Change)")),
    ("agent-notice", re.compile(r"^OMP custom context \(session-agent-notice\)")),
    (
        "recap",
        re.compile(
            r"收集「|事件证据收集|日报证据收集|每日工作整理|\*\*目标工作日\*\*|\*\*主题域\*\*|日报.{0,6}核验"
            r"|daily[\s-]?recap|日报采集|每日回顾|每日工作回顾"
        ),
    ),
]


# 机器会话消息族：父会话派发的任务（子代理 / 上一轮 recap 的收集器与核验 /
# no-mistakes 流水线阶段子代）。这类会话的 nmem 标题常被父会话起了友好名
# （如「为 18 个 UP 主打标并生成 …json」），与人类会话标题无从区分，
# 只能取首条 user 消息判族。
MACHINE_MESSAGE_FAMILIES: list[tuple[str, re.Pattern[str]]] = [
    # recap 子代的判据更具体，先判（否则会被通用的子代理开头吃掉）
    ("recap", re.compile(r"\*\*主题域\*\*|\*\*目标工作日\*\*|逐条核验|事件证据收集")),
    ("subagent", re.compile(r"^(?:Complete (?:the )?assignment (?:thoroughly|below)|# Target|# Change)")),
    # no-mistakes 复审/测试阶段子代：Workspace boundary 包裹的 phase 说明
    ("pipeline", re.compile(r"^Workspace boundary \(important\):")),
]

# 首条 user 消息可能是宿主注入的上下文通知，判族时跳过（不是人会话的提问）。
SYSTEM_NOTICE_PREFIX = "OMP custom context"

# 线程 id 内的 UUID v7 片段（任意前缀，如 pi-/omp-/grok-）。
UUID_V7_PATTERN = re.compile(r"([0-9a-f]{8})-([0-9a-f]{4})-7([0-9a-f]{3})-[0-9a-f]{4}-[0-9a-f]{12}")

# 线程 id 内的日期时刻（CST）：import-20260611022202-…、20260821_084541_…、cron_…_20260806_080027。
ID_DATETIME_PATTERN = re.compile(r"(?<!\d)(\d{8})[_-]?(\d{6})(?!\d)")

# 测试/探针线程的 epoch 秒后缀：omp-embed-1785391351、omp-var-3-1785391478。
ID_EPOCH_PATTERN = re.compile(r"-(1\d{9})$")

# 翻页与 stub 口径。
NMEM_PAGE_LIMIT = 200
MAX_PAGES = 100
STUB_MESSAGE_THRESHOLD = 10
NMEM_TIMEOUT_SECONDS = 30


# ── helpers ───────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="确定目标工作日，并扫描/分类 nmem 线程。")
    parser.add_argument("date", nargs="?", default=None, help="目标工作日 YYYY-MM-DD（默认自动选择）")
    parser.add_argument("--date", dest="date_opt", default=None, help="同位置参数，显式指定目标工作日")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true", help="调 nmem 翻页扫描并打印候选表（整理日报第 1 步）")
    mode.add_argument("--check", action="store_true", help="从 stdin 读 thread_id 列表，逐条报告窗口归属")
    parser.add_argument(
        "--no-probe", action="store_true", help="--scan 跳过首条消息探针（只看标题族，认不出的子代留在候选里）"
    )
    args = parser.parse_args()
    args.date = args.date_opt or args.date
    if args.date:
        try:
            args.date = date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"目标工作日必须是 YYYY-MM-DD：{args.date}")
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
    """从线程 id 里的 UUID v7 解析会话开始时间（tz-aware UTC datetime）。

    Pi/OMP 的线程 id 前缀是 UUID v7（如 omp-019fd628-514d-7000-…），前 48 位即
    会话开始时间的毫秒级 Unix 时间戳。前缀不固定（pi-/omp-/grok-…），故按 UUID
    v7 形状在 id 里查找，而不是剥固定前缀后取前 12 位。编码的是会话开始时间
    （UUID 生成时刻），不是 nmem 导入时间。找不到返回 None。
    """
    if not thread_id:
        return None
    match = UUID_V7_PATTERN.search(thread_id)
    if match is None:
        return None
    ms = int((match.group(1) + match.group(2) + "7" + match.group(3))[:12], 16)
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC)
    except OSError, OverflowError, ValueError:
        return None


def id_timestamp(thread_id: str) -> datetime | None:
    """从线程 id 里的日期时刻解析会话开始时间（tz-aware CST datetime）。

    nmem 里存在非 UUID v7 的 id：import-20260611022202-2ca97888（历史导入）、
    20260821_084541_8ac8fe（pi 早期）、cron_<hex>_20260806_080027（定时任务）。
    这些 id 自带本地时刻（CST），可直接判窗口。解析不出返回 None。
    """
    if not thread_id:
        return None
    match = ID_DATETIME_PATTERN.search(thread_id)
    if match is not None:
        try:
            return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S").replace(tzinfo=CST)
        except ValueError:
            return None
    epoch = ID_EPOCH_PATTERN.search(thread_id)
    if epoch is not None:
        try:
            return datetime.fromtimestamp(int(epoch.group(1)), tz=UTC)
        except OSError, OverflowError, ValueError:
            return None
    return None


def thread_start(thread_id: str) -> datetime | None:
    """线程开始时间：先认 UUID v7，再认 id 内嵌的日期时刻；都判不出返回 None。"""
    return uuid_v7_timestamp(thread_id) or id_timestamp(thread_id)


def message_timestamp(messages: list[dict]) -> datetime | None:
    """从 nmem 消息里取最早一条的 `timestamp`（真实消息时间，tz-aware datetime）。

    deepseek-harness 等非 UUID v7 来源的线程 id 不带时间，但消息带毫秒级
    `timestamp`（区别于 `created_at` = 导入时间）。解析失败返回 None。
    """
    stamps: list[datetime] = []
    for msg in messages:
        raw = msg.get("timestamp")
        if not raw:
            continue
        try:
            stamps.append(datetime.fromisoformat(raw))
        except ValueError:
            continue
    return min(stamps) if stamps else None


def thread_time(thread: dict) -> datetime | None:
    """线程开始时间：id 时间戳优先，其次（若已解析）消息时间兜底。"""
    return thread_start(thread.get("id", "")) or thread.get("_start")


def created_at_day(thread: dict) -> date | None:
    """nmem 列表的 created_at 日级日期（形如 "Oct 27, 2026"），解析失败返回 None。

    created_at 是导入批次日期，可能晚于会话开始（实测最多晚 52 天），也可能因
    UTC 取整早一天。因此只用于「证明早于窗口」的排除，不作窗口判定。
    """
    raw = thread.get("created_at")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%b %d, %Y").replace(tzinfo=UTC).date()
    except ValueError:
        return None


def proven_before_window(thread: dict, window: tuple[datetime, datetime]) -> bool:
    """created_at 能否证明该线程一定早于窗口（是则无需再看 id）。

    created_at - 会话开始的 CST 日期实测落在 {-1, 0, +n}，即会话开始最多比
    created_at 晚一天；所以 created_at + 1 天仍早于窗口当日，必在窗口外。
    """
    day = created_at_day(thread)
    if day is None:
        return False
    return day + timedelta(days=1) < window[0].date()


def thread_in_window(thread_id: str, window: tuple[datetime, datetime]) -> bool:
    """线程开始时间是否落在工作日窗口 [start, end) 内；判不出时间视为不在窗口内。"""
    ts = thread_start(thread_id)
    if ts is None:
        return False
    return window[0] <= ts < window[1]


def classify_machine(title: str) -> str | None:
    """按标题族判断机器会话，返回族名（advisor/subagent/recap/pipeline）或 None。"""
    for family, pattern in MACHINE_TITLE_FAMILIES:
        if pattern.search(title):
            return family
    return None


def first_message_family(content: str | None) -> str | None:
    """按首条 user 消息正文判机器族，返回族名（recap/subagent/pipeline）或 None。"""
    if not content:
        return None
    for family, pattern in MACHINE_MESSAGE_FAMILIES:
        if pattern.search(content):
            return family
    return None


# ── 窗口过滤与机器分类 ─────────────────────────────────────────────────────


def filter_threads(threads: list[dict], window: tuple[datetime, datetime]) -> tuple[list[dict], list[dict], list[dict]]:
    """按线程开始时间把线程分成三组。

    返回 (candidates, excluded, undetermined)：
    - candidates：确认落在窗口内的线程
    - excluded：确认在窗口外（含 created_at 能证明早于窗口、id 时间判不出的旧线程）
    - undetermined：id 判不出时间、created_at 也证不了早于窗口（极少数），单独留痕
    """
    candidates: list[dict] = []
    excluded: list[dict] = []
    undetermined: list[dict] = []
    start, end = window
    for thread in threads:
        ts = thread_time(thread)
        if ts is None:
            (excluded if proven_before_window(thread, window) else undetermined).append(thread)
        elif start <= ts < end:
            candidates.append(thread)
        else:
            excluded.append(thread)
    return candidates, excluded, undetermined


def resolve_undetermined(threads: list[dict]) -> int:
    """给 id 判不出时间的线程补取消息时间（写入 thread["_start"]），返回成功条数。

    只对 filter_threads 判出的 undetermined 调用（通常个位数），不是全库
    `threads show`：deepseek-harness 等来源的线程 id 无时间戳，但消息带毫秒级
    `timestamp`，是唯一能判窗口的依据。删掉本函数就会把它们静默降级成「时间未知」。
    """
    resolved = 0
    for thread in threads:
        messages, ok = fetch_thread_messages(thread["id"], limit=3)
        if not ok:
            continue
        ts = message_timestamp(messages)
        if ts is not None:
            thread["_start"] = ts
            resolved += 1
    return resolved


def partition_threads(
    threads: list[dict], window: tuple[datetime, datetime]
) -> tuple[list[dict], dict[str, list[dict]], list[dict], list[dict]]:
    """窗口过滤 + 标题族机器分类。

    返回 (human, machine, excluded, undetermined)：human 是窗口内非机器线程；
    machine 是窗口内机器线程按族分组（空族省略）。
    """
    candidates, excluded, undetermined = filter_threads(threads, window)
    machine: dict[str, list[dict]] = {}
    human: list[dict] = []
    for thread in candidates:
        family = classify_machine(thread.get("title") or "")
        if family is None:
            human.append(thread)
        else:
            machine.setdefault(family, []).append(thread)
    return human, machine, excluded, undetermined


# ── nmem 读取 ─────────────────────────────────────────────────────────────


def fetch_threads_page(offset: int, limit: int = NMEM_PAGE_LIMIT) -> list[dict]:
    """取 nmem 线程列表的一页；CLI 失败抛 RuntimeError（nmem 不可用时必须硬停）。"""
    try:
        proc = subprocess.run(
            ["nmem", "threads", "list", "--limit", str(limit), "--offset", str(offset), "--json"],
            capture_output=True,
            text=True,
            timeout=NMEM_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"nmem threads list 不可用（offset {offset}）：{exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"nmem threads list 失败（offset {offset}）：{proc.stderr.strip()[:200]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"nmem threads list 输出不是合法 JSON（offset {offset}）") from exc
    return data.get("threads", []) if isinstance(data, dict) else data


def scan_threads() -> tuple[list[dict], int]:
    """翻页取全量线程（全库扫描）。

    列表排序既不是会话时间序也不是严格导入序（实测旧会话会在几十页后出现），
    任何「提前停页」的近似都会漏掉窗口内线程，所以扫到底：实测 8600 条约 44 页、
    20 秒，成本可接受。返回 (threads, pages)。
    """
    threads: list[dict] = []
    pages = 0
    for page_index in range(MAX_PAGES):
        page = fetch_threads_page(page_index * NMEM_PAGE_LIMIT)
        pages += 1
        threads.extend(page)
        if len(page) < NMEM_PAGE_LIMIT:
            break
    return threads, pages


def fetch_thread_messages(thread_id: str, limit: int = 5) -> tuple[list[dict], bool]:
    """取线程头部消息；CLI 失败/超时/输出不合法时返回 ([], False)。"""
    try:
        proc = subprocess.run(
            ["nmem", "threads", "show", thread_id, "--limit", str(limit), "--json"],
            capture_output=True,
            text=True,
            timeout=NMEM_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return [], False
    if proc.returncode != 0:
        return [], False
    try:
        messages = json.loads(proc.stdout).get("messages") or []
    except json.JSONDecodeError, AttributeError:
        return [], False
    return messages, True


def fetch_first_message(thread_id: str) -> tuple[str | None, bool]:
    """取线程首条非系统通知的 user 消息正文。

    返回 (正文, 读取成功)：读取成功但前几条消息全被通知/助手占满时正文为 None
    （人类会话的提问常被拼进宿主通知里，属正常情形）；CLI 失败/超时/JSON 不合法
    时读取成功为 False。
    """
    messages, ok = fetch_thread_messages(thread_id)
    if not ok:
        return None, False
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if content and not content.startswith(SYSTEM_NOTICE_PREFIX):
            return content, True
    return None, True


def probe_candidates(
    candidates: list[dict], machine: dict[str, list[dict]]
) -> tuple[list[dict], dict[str, list[dict]], dict[str, object]]:
    """对标题族认不出的候选逐条取首条消息复核机器族（每条一次 nmem 调用）。

    返回 (candidates, machine, report)：判出族的候选移入 machine 对应族；
    读不出首条消息的记入 report["unreadable"]，首条消息判不出族的记入
    report["no_task_message"]，两者都仍留在 candidates（假阴性只多留一条候选，
    由归类审查这道人工门兜底）。
    """
    moved: set[str] = set()
    unreadable: list[str] = []
    undecided: list[str] = []
    for thread in candidates:
        content, ok = fetch_first_message(thread["id"])
        if not ok:
            unreadable.append(thread["id"])
            continue
        family = first_message_family(content)
        if family is None:
            undecided.append(thread["id"])
            continue
        machine.setdefault(family, []).append(thread)
        moved.add(thread["id"])
    report: dict[str, object] = {
        "probed": len(candidates),
        "reclassified": len(moved),
        "no_task_message": undecided,
        "unreadable": unreadable,
    }
    return [c for c in candidates if c.get("id") not in moved], machine, report


# ── 输出 ──────────────────────────────────────────────────────────────────


def check_lines(thread_ids: list[str], window: tuple[datetime, datetime]) -> list[str]:
    """逐条报告线程的 CST 开始时间与窗口归属（供 collector 批量复核）。

    id 判不出时间时补取消息 timestamp（deepseek-harness 等来源的 id 不带时间），
    仍判不出才报 unparseable。
    """
    start, end = window
    lines = [f"窗口 [{start:%Y-%m-%d %H:%M}, {end:%Y-%m-%d %H:%M}) CST"]
    for tid in thread_ids:
        ts = thread_start(tid)
        if ts is None:
            messages, ok = fetch_thread_messages(tid, limit=3)
            ts = message_timestamp(messages) if ok else None
        if ts is None:
            lines.append(f"{tid}\t?\tunparseable")
            continue
        local = ts.astimezone(CST)
        state = "in" if start <= ts < end else "out"
        lines.append(f"{tid}\t{local:%Y-%m-%d %H:%M:%S} CST\t{state}")
    return lines


def _clip(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def render_scan(
    target_workday: date,
    window: tuple[datetime, datetime],
    human: list[dict],
    machine: dict[str, list[dict]],
    excluded: list[dict],
    undetermined: list[dict],
    report: dict[str, object] | None,
    pages: int,
    total: int,
) -> str:
    """把扫描结果渲染成归类审查可直接用的文本候选表。"""
    start, end = window
    lines = [
        f"目标工作日：{target_workday.isoformat()}（CST 窗口 [{start:%m-%d %H:%M}, {end:%m-%d %H:%M})）",
        (
            f"扫描：{pages} 页 / {total} 条线程；"
            f"窗口内 {len(human) + sum(len(v) for v in machine.values())} 条，窗口外 {len(excluded)} 条"
        ),
    ]
    if machine:
        families = "、".join(
            f"{name}×{len(rows)}" for name, rows in sorted(machine.items(), key=lambda kv: -len(kv[1]))
        )
        lines.append(f"机器会话跳过留痕：{families}")
    if undetermined:
        lines.append(f"时间未知（id 无时间戳、created_at 也证不出窗口外）：{len(undetermined)} 条")
        for thread in undetermined:
            lines.append(f"  - {thread['id']} | {_clip(thread.get('title') or '', 40)}")
    if report is not None:
        lines.append(
            f"探针：{report['probed']} 条取首条消息，判为机器子代 {report['reclassified']} 条"
            f"（已并入上方留痕）；判不出 {len(report['no_task_message'])} 条、读取失败 "
            f"{len(report['unreadable'])} 条，均留在候选表"
        )
        for tid in report["unreadable"]:
            lines.append(f"  - 读取失败：{tid}")

    stubs = [t for t in human if (t.get("messages") or 0) < STUB_MESSAGE_THRESHOLD]
    table = [t for t in human if t not in stubs]
    lines.append("")
    lines.append(f"## 候选（{len(table)} 条，按消息数降序）")
    lines.append("")
    lines.append("| # | 消息数 | 会话主题 | thread_id |")
    lines.append("|:--:|:--:|--|--|")
    for index, thread in enumerate(sorted(table, key=lambda t: -(t.get("messages") or 0)), 1):
        title = _clip(thread.get("title") or "", 60) or "（无标题）"
        lines.append(f"| {index} | {thread.get('messages') or 0} | {title} | `{thread['id']}` |")
    if stubs:
        lines.append("")
        sample = "、".join(_clip(t.get("title") or "", 18) or "无标题" for t in stubs[:5])
        lines.append(f"另 {len(stubs)} 条 stub（消息数 <{STUB_MESSAGE_THRESHOLD}，多为测试探针，不逐条进表）：{sample}")
    if not table and not stubs:
        lines.append("")
        lines.append("目标工作日没有会话记录。")
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────


def main():
    args = parse_args()
    target_workday = args.date or choose_target_workday(datetime.now(CST))
    window = workday_window(target_workday)

    if args.scan:
        threads, pages = scan_threads()
        human, machine, excluded, undetermined = partition_threads(threads, window)
        if undetermined and not args.no_probe:
            resolve_undetermined(undetermined)
            human, machine, excluded, undetermined = partition_threads(threads, window)
        report: dict[str, object] | None = None
        if not args.no_probe and human:
            human, machine, report = probe_candidates(human, machine)
        print(render_scan(target_workday, window, human, machine, excluded, undetermined, report, pages, len(threads)))
    elif args.check:
        thread_ids = [line.strip() for line in sys.stdin if line.strip()]
        print("\n".join(check_lines(thread_ids, window)))
    else:
        print(json.dumps({"date": target_workday.isoformat()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
