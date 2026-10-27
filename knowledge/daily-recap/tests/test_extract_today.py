#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest>=8"]
# ///
"""extract_today.py 的测试 - 04:00 工作日窗口 + 12:00 总结分界 + UUID v7 时间过滤 + 机器会话分类。

运行：cd <skill目录> && uv run --script tests/test_extract_today.py
"""

import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 测试在 tests/，脚本目录不在 sys.path；显式加入以便 import 被测模块。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_today
import pytest

CST = ZoneInfo("Asia/Shanghai")


def _make_thread_id(dt_utc: datetime, prefix: str = "omp") -> str:
    """构造 UUID v7 thread id：前 48 位（12 hex）= 毫秒时间戳，版本位 = 7。"""
    ms = int(dt_utc.timestamp() * 1000)
    hex_ms = f"{ms:012x}"
    return f"{prefix}-{hex_ms[:8]}-{hex_ms[8:]}-7000-8000-000000000000"


# ── 工作日窗口 ──────────────────────────────────────────────────────────────


def test_workday_window_spans_04_to_next_day_04():
    """目标工作日的窗口是 [当日 04:00, 次日 04:00) CST。"""
    start, end = extract_today.workday_window(date(2026, 7, 18))
    assert start == datetime(2026, 7, 18, 4, 0, tzinfo=CST)
    assert end == datetime(2026, 7, 19, 4, 0, tzinfo=CST)


# ── 目标工作日选择 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hour, minute, expected",
    [
        (0, 30, date(2026, 7, 17)),  # 凌晨 0-4 点：昨天（窗口仍在进行）
        (2, 0, date(2026, 7, 17)),  # 凌晨 2:00：昨天
        (4, 0, date(2026, 7, 17)),  # 04:00 窗口边界，仍 <12:00：昨天
        (8, 35, date(2026, 7, 17)),  # 早上 08:35（曾出错场景）：昨天
        (11, 59, date(2026, 7, 17)),  # 11:59 仍 <12:00：昨天
        (12, 0, date(2026, 7, 18)),  # 12:00 边界（闭，≥12:00）：今天
        (14, 0, date(2026, 7, 18)),  # 午后：今天
        (22, 0, date(2026, 7, 18)),  # 晚间：今天
    ],
)
def test_choose_target_workday(hour, minute, expected):
    """以 12:00 为界：<12:00 整理昨天，≥12:00 整理今天。

    04:00 是工作日窗口边界（workday_window），不是"总结哪个工作日"的分界点。
    """
    now = datetime(2026, 7, 18, hour, minute, tzinfo=CST)
    assert extract_today.choose_target_workday(now) == expected


# ── UUID v7 时间戳解析 ──────────────────────────────────────────────────────


def test_uuid_v7_timestamp_roundtrip():
    """构造的 UUID v7 thread id 能解析回原始 UTC 时间（毫秒精度）。"""
    dt = datetime(2026, 7, 18, 2, 0, 0, tzinfo=UTC)
    thread_id = _make_thread_id(dt)
    parsed = extract_today.uuid_v7_timestamp(thread_id)
    assert parsed == dt


def test_uuid_v7_timestamp_strips_prefix():
    """pi- 和 omp- 前缀都能正确剥离。"""
    dt = datetime(2026, 7, 18, 2, 0, 0, tzinfo=UTC)
    assert extract_today.uuid_v7_timestamp(_make_thread_id(dt, "pi")) == dt
    assert extract_today.uuid_v7_timestamp(_make_thread_id(dt, "omp")) == dt


def test_uuid_v7_timestamp_invalid():
    """空/垃圾/过短 id 返回 None。"""
    assert extract_today.uuid_v7_timestamp("") is None
    assert extract_today.uuid_v7_timestamp("garbage") is None
    assert extract_today.uuid_v7_timestamp("omp-short") is None
    assert extract_today.uuid_v7_timestamp(None) is None
    # 纯 hex id 前 12 位是合法十六进制但时间戳越界（真实数据里出现过），不得抛出
    assert extract_today.uuid_v7_timestamp("ef834aab18d0") is None


def test_uuid_v7_timestamp_any_prefix():
    """前缀不止 pi-/omp-：grok- 等任意前缀的 UUID v7 也要认出来。"""
    dt = datetime(2026, 7, 18, 2, 0, 0, tzinfo=UTC)
    assert extract_today.uuid_v7_timestamp(_make_thread_id(dt, "grok")) == dt


@pytest.mark.parametrize(
    "thread_id, expected",
    [
        # 历史导入线程：import-YYYYMMDDhhmmss-<hex>，时刻按 CST
        ("import-20260611022202-2ca97888", datetime(2026, 6, 11, 2, 22, 2, tzinfo=CST)),
        # pi 早期线程：YYYYMMDD_hhmmss_<hex>
        ("20260821_084541_8ac8fe", datetime(2026, 8, 21, 8, 45, 41, tzinfo=CST)),
        # 定时任务：cron_<hex>_YYYYMMDD_hhmmss
        ("cron_db9054a389fb_20260806_080027", datetime(2026, 8, 6, 8, 0, 27, tzinfo=CST)),
        # 测试/探针线程：omp-<name>-<epoch 秒>
        ("omp-embed-1785391351", datetime(2026, 7, 30, 6, 2, 31, tzinfo=UTC)),
        # 时间不可能合法时不崩，返回 None
        ("import-20261331000000-deadbeef", None),
        ("diag-1", None),
        ("ef834aab18d0", None),
    ],
)
def test_id_timestamp_from_embedded_datetime(thread_id, expected):
    """无 UUID v7 的 id 用内嵌日期时刻兜底判时间，按 CST 解释。"""
    assert extract_today.id_timestamp(thread_id) == expected


def test_thread_start_prefers_uuid_v7():
    """两种时间都在时用 UUID v7（毫秒精度、编码会话开始时刻）。"""
    dt = datetime(2026, 7, 18, 2, 0, 0, tzinfo=UTC)
    assert extract_today.thread_start(_make_thread_id(dt)) == dt


def test_message_timestamp_parses_messages_and_takes_earliest():
    """消息级 timestamp 是唯一的兜底时间源：取最早一条，Z 与 +00:00 都认。"""
    messages = [
        {"timestamp": "2026-10-20T13:30:52.927000+00:00"},
        {"timestamp": "2026-10-20T13:28:00Z"},
        {"timestamp": "not-a-time"},
        {},
    ]
    assert extract_today.message_timestamp(messages) == datetime(2026, 10, 20, 13, 28, tzinfo=UTC)
    assert extract_today.message_timestamp([]) is None


def test_resolve_undetermined_recovers_window_membership(monkeypatch):
    """id 无时间戳的线程靠消息 timestamp 判出窗口，而不是被当成「时间未知」。

    deepseek-harness 的线程 id 是 `deepseek-harness-<uuid>`，不带任何时间信息。
    """
    window = extract_today.workday_window(date(2026, 7, 18))
    threads = [
        {"id": "deepseek-harness-6162441e-68f3-409e-845e-7e293b9e7b41", "title": "dsh 会话同步", "messages": 79},
        {"id": "diag-1", "title": "空线程", "messages": 0},
    ]
    monkeypatch.setattr(
        extract_today,
        "fetch_thread_messages",
        lambda tid, limit=5: (([{"timestamp": "2026-07-18T02:00:00Z"}] if tid.startswith("deepseek") else []), True),
    )

    candidates, excluded, undetermined = extract_today.filter_threads(threads, window)
    assert candidates == [] and excluded == []
    assert len(undetermined) == 2  # 两个都判不出时间

    assert extract_today.resolve_undetermined(undetermined) == 1
    candidates, excluded, undetermined = extract_today.filter_threads(threads, window)
    assert [c["id"] for c in candidates] == ["deepseek-harness-6162441e-68f3-409e-845e-7e293b9e7b41"]
    assert [u["id"] for u in undetermined] == ["diag-1"]
    # id 时间戳仍优先于消息时间
    assert extract_today.thread_time(
        {"id": _make_thread_id(datetime(2026, 7, 1, tzinfo=UTC)), "_start": datetime(2026, 7, 18, 2, tzinfo=UTC)}
    ) == datetime(2026, 7, 1, tzinfo=UTC)


# ── 线程窗口判定 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "dt_utc, expected",
    [
        # 窗口 [2026-07-18 04:00 CST, 2026-07-19 04:00 CST) = UTC [07-17 20:00, 07-18 20:00)
        (datetime(2026, 7, 18, 2, 0, tzinfo=UTC), True),  # CST 07-18 10:00 窗口内
        (datetime(2026, 7, 17, 19, 0, tzinfo=UTC), False),  # CST 07-18 03:00 凌晨归前日
        (datetime(2026, 7, 18, 19, 0, tzinfo=UTC), True),  # CST 07-19 03:00 次日凌晨
        (datetime(2026, 7, 18, 21, 0, tzinfo=UTC), False),  # CST 07-19 05:00 窗口外
        (datetime(2026, 7, 17, 20, 0, tzinfo=UTC), True),  # CST 07-18 04:00 左边界闭
        (datetime(2026, 7, 18, 20, 0, tzinfo=UTC), False),  # CST 07-19 04:00 右边界开
    ],
)
def test_thread_in_window(dt_utc, expected):
    thread_id = _make_thread_id(dt_utc)
    window = extract_today.workday_window(date(2026, 7, 18))
    assert extract_today.thread_in_window(thread_id, window) is expected


def test_thread_in_window_invalid_id():
    """无法解析的线程 id 视为不在窗口内。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    assert extract_today.thread_in_window("", window) is False
    assert extract_today.thread_in_window("garbage", window) is False


# ── 回归：12:00 前当前会话在窗口外 ──────────────────────────────────────────


def test_recap_before_noon_current_session_outside_window():
    """12:00 前跑 recap：目标工作日是昨天，当前会话必然在窗口外。

    回归实测事故：08-03 08:46 CST 跑 recap，目标工作日 08-02，
    窗口 [08-02 04:00, 08-03 04:00) CST；当前会话 08:46 CST 在窗口外。
    技能曾用"当前会话必在窗口内"反证空集--该前提在 12:00 前恒不成立。
    """
    now = datetime(2026, 8, 3, 8, 46, tzinfo=CST)
    target = extract_today.choose_target_workday(now)
    assert target == date(2026, 8, 2)
    window = extract_today.workday_window(target)
    # 当前会话 08:46 CST = 00:46 UTC，构造对应 UUID v7 thread id
    current_thread = _make_thread_id(datetime(2026, 8, 3, 0, 46, 16, tzinfo=UTC))
    assert extract_today.thread_in_window(current_thread, window) is False


# ── 批量线程过滤 ────────────────────────────────────────────────────────────


def test_filter_threads_splits_by_window():
    """窗口内线程归候选，窗口外归排除。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    in_id = _make_thread_id(datetime(2026, 7, 18, 2, 0, tzinfo=UTC))
    out_id = _make_thread_id(datetime(2026, 7, 18, 21, 0, tzinfo=UTC))
    threads = [{"id": in_id, "title": "窗口内", "messages": 50}, {"id": out_id, "title": "窗口外", "messages": 30}]
    candidates, excluded, undetermined = extract_today.filter_threads(threads, window)
    assert [c["id"] for c in candidates] == [in_id]
    assert [e["id"] for e in excluded] == [out_id]
    assert undetermined == []


def test_filter_threads_non_v7_ids_are_parsed_from_id_datetime():
    """id 不是 UUID v7 但自带日期时刻时照样判窗口（import-/pi 早期/cron）。

    回归实测：nmem 里 391 条无 v7 的旧线程曾全部落进候选，把候选表灌成 507 条。
    """
    window = extract_today.workday_window(date(2026, 7, 18))
    threads = [
        {"id": "import-20260718103000-2ca97888", "title": "历史导入", "messages": 40},
        {"id": "20260718_180000_8ac8fe", "title": "pi 早期", "messages": 40},
    ]
    candidates, _, _ = extract_today.filter_threads(threads, window)
    assert [c["id"] for c in candidates] == ["import-20260718103000-2ca97888", "20260718_180000_8ac8fe"]

    old = [{"id": "import-20260611022202-2ca97888", "title": "两个月前", "messages": 40}]
    candidates, excluded, _ = extract_today.filter_threads(old, window)
    assert candidates == []
    assert [e["id"] for e in excluded] == ["import-20260611022202-2ca97888"]


def test_filter_threads_undetermined_only_when_created_at_cannot_prove_old():
    """id 判不出时间时：created_at 能证明早于窗口就排除，否则留在 undetermined 留痕。

    created_at 是导入批次日期，实测可能比会话开始早一天、晚最多 52 天，
    所以只有 created_at + 1 天仍早于窗口当日才算"证明在窗口外"。
    """
    window = extract_today.workday_window(date(2026, 7, 18))
    threads = [
        {"id": "ef834aab18d0", "title": "老线程", "messages": 9, "created_at": "May 20, 2026"},
        {"id": "ef834aab18d1", "title": "近期导入", "messages": 30, "created_at": "Jul 18, 2026"},
        {"id": "ef834aab18d2", "title": "无 created_at", "messages": 30},
        {"id": "ef834aab18d3", "title": "窗口前一天导入", "messages": 30, "created_at": "Jul 17, 2026"},
    ]
    candidates, excluded, undetermined = extract_today.filter_threads(threads, window)
    assert candidates == []
    assert [e["id"] for e in excluded] == ["ef834aab18d0"]
    assert [u["id"] for u in undetermined] == ["ef834aab18d1", "ef834aab18d2", "ef834aab18d3"]


# ── 机器会话分类 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "title, family",
    [
        ("### Session update  [skill-prompt] ...", "advisor"),
        ("Complete assignment thoroughly:\n\n# Target\n调研 gh CLI", "subagent"),
        ("# Target\n调研 gh CLI", "subagent"),
        ("# Change\n...", "subagent"),
        ("收集「桌面系统与硬件」2026-09-05 事件证据", "recap"),
        ("语音与桌面环境事件证据收集", "recap"),
        ("执行 daily-recap 技能整理日报", "recap"),
        ("执行 2026-09-05 每日工作整理", "recap"),
        ("**目标工作日**: 2026-09-05", "recap"),
        ("**主题域**: SNP 功能分流 XLSX 转 Markdown", "recap"),
        ("2026-09-04 日报数据核验", "recap"),
        ("执行每日回顾技能", "recap"),
        ("整理 2026-09-30 每日工作回顾", "recap"),
        ("doujin-voice 主题域 2026-09-30 日报证据收集", "recap"),
        ("日报采集：2026-09-22 事件汇总", "recap"),
        ("HPC 巡检与数据整理", None),
        ("翻译 The Harness Playbook", None),
        ("", None),
    ],
)
def test_classify_machine(title, family):
    """标题族命中归入对应机器族；普通（人类）标题返回 None。"""
    assert extract_today.classify_machine(title) == family


def test_partition_threads_splits_machine_and_human():
    """窗口过滤与机器分类合成：人类进 candidates，机器按族进 machine，窗口外进 excluded。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    human_id = _make_thread_id(datetime(2026, 7, 18, 2, 0, tzinfo=UTC))
    advisor_id = _make_thread_id(datetime(2026, 7, 18, 3, 0, tzinfo=UTC))
    out_id = _make_thread_id(datetime(2026, 7, 18, 21, 0, tzinfo=UTC))
    threads = [
        {"id": human_id, "title": "HPC 巡检", "messages": 42},
        {"id": advisor_id, "title": "### Session update  [skill-prompt]", "messages": 12},
        {"id": out_id, "title": "窗口外的普通会话", "messages": 8},
    ]
    candidates, machine, excluded, undetermined = extract_today.partition_threads(threads, window)
    assert [c["id"] for c in candidates] == [human_id]
    assert [m["id"] for m in machine["advisor"]] == [advisor_id]
    assert [e["id"] for e in excluded] == [out_id]
    assert undetermined == []
    assert set(machine) == {"advisor"}  # 空族省略


# ── 首条消息判族（--probe） ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "content, family",
    [
        # 父会话派发的子代理任务：标题被起了友好名，只能靠首条消息认出来
        ("Complete assignment thoroughly:\n\n# Target\nout/tags/part07.json", "subagent"),
        ("# Target\n调研 gh CLI", "subagent"),
        # 上一轮 recap 的收集器/核验子代同样带友好标题，且判据更具体，优先归 recap
        ("Complete assignment thoroughly:\n\n**主题域**: genome-assembly\n**目标工作日**: 2026-10-23", "recap"),
        ("Complete the assignment below thoroughly:\n\n# Target\n...", "subagent"),
        ("**主题域**: CKB 日报", "recap"),
        ("Complete assignment thoroughly:\n\n逐条核验下列待写入日报的声称", "recap"),
        # no-mistakes 流水线阶段子代：友好标题认不出，靠 Workspace boundary 开头认
        ("Workspace boundary (important):\n- Confine your work to ...", "pipeline"),
        # 人类提问与空内容都不算机器族
        ("opencli 有操作b站的适配器吗", None),
        ("这个仓库是干嘛的？", None),
        (None, None),
        ("", None),
    ],
)
def test_first_message_family(content, family):
    """首条 user 消息按任务提示判族；人类提问返回 None。"""
    assert extract_today.first_message_family(content) == family


class _FakeCompleted:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _thread_json(*messages: tuple[str, str]) -> str:
    return json.dumps({"messages": [{"role": role, "content": content} for role, content in messages]})


def test_fetch_first_message_skips_host_notices(monkeypatch):
    """宿主注入的通知消息（OMP custom context）跳过，取其后第一条人类/任务提问。"""
    monkeypatch.setattr(
        extract_today.subprocess,
        "run",
        lambda *a, **kw: _FakeCompleted(
            _thread_json(
                ("user", "OMP custom context (xdev-mount-notice):\n<system-notice>"),
                ("assistant", "[thinking]"),
                ("user", "这个仓库是干嘛的？"),
            )
        ),
    )
    assert extract_today.fetch_first_message("omp-x") == ("这个仓库是干嘛的？", True)


def test_fetch_first_message_only_notices(monkeypatch):
    """前几条消息全被通知占满时读取成功、正文为 None（人类会话的常见形态，不是读取失败）。"""
    monkeypatch.setattr(
        extract_today.subprocess,
        "run",
        lambda *a, **kw: _FakeCompleted(_thread_json(("user", "OMP custom context (skill-prompt): ..."))),
    )
    assert extract_today.fetch_first_message("omp-x") == (None, True)


@pytest.mark.parametrize("outcome", ["nonzero", "bad_json", "timeout"])
def test_fetch_first_message_read_failure(monkeypatch, outcome):
    """CLI 非零退出 / 输出不是合法 JSON / 超时都算读取失败。"""

    def fake_run(*args, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd="nmem", timeout=extract_today.NMEM_TIMEOUT_SECONDS)
        if outcome == "nonzero":
            return _FakeCompleted("", returncode=1)
        return _FakeCompleted("not json")

    monkeypatch.setattr(extract_today.subprocess, "run", fake_run)
    assert extract_today.fetch_first_message("omp-x") == (None, False)


def test_probe_candidates_moves_only_identified_tasks(monkeypatch):
    """--scan 探针：判出族的候选移入对应机器族，读不出的与判不出族的一律留在候选。"""
    ids = {
        name: _make_thread_id(datetime(2026, 7, 18, hour, 0, tzinfo=UTC))
        for name, hour in [("sub", 2), ("recap", 4), ("human", 6), ("broken", 8), ("pipeline", 10)]
    }
    candidates = [{"id": tid, "title": name, "messages": 20} for name, tid in ids.items()]
    candidates.append({"id": "garbage", "title": "遗留", "messages": 20})
    replies = {
        ids["sub"]: ("# Target\n子代理任务", True),
        ids["recap"]: ("**主题域**: genome-assembly", True),
        ids["pipeline"]: ("Workspace boundary (important):\n- Confine...", True),
        ids["human"]: (None, True),
        ids["broken"]: (None, False),
    }
    monkeypatch.setattr(
        extract_today, "fetch_first_message", lambda tid: replies.get(tid, ("opencli 有适配器吗", True))
    )

    human, machine, report = extract_today.probe_candidates(candidates, {})

    assert [c["id"] for c in machine["subagent"]] == [ids["sub"]]
    assert [c["id"] for c in machine["recap"]] == [ids["recap"]]
    assert [c["id"] for c in machine["pipeline"]] == [ids["pipeline"]]
    # 读不出的、首条消息判不出族的、id 时间判不出的都留在候选（假阴性由人工门兜底）
    assert sorted(c["id"] for c in human) == sorted([ids["human"], ids["broken"], "garbage"])
    assert report["probed"] == 6
    assert report["reclassified"] == 3
    assert report["no_task_message"] == [ids["human"], "garbage"]
    assert report["unreadable"] == [ids["broken"]]


def test_probe_candidates_reuses_title_machine_families(monkeypatch):
    """探针不覆盖标题族已判出的机器会话：探针结果并入同一族。"""
    sub_id = _make_thread_id(datetime(2026, 7, 18, 2, 0, tzinfo=UTC))
    monkeypatch.setattr(extract_today, "fetch_first_message", lambda tid: ("# Target\n任务", True))
    machine = {"subagent": [{"id": "title-caught", "title": "x24h_c", "messages": 11}]}

    human, machine, report = extract_today.probe_candidates(
        [{"id": sub_id, "title": "为 18 个 UP 主打标", "messages": 30}], machine
    )

    assert human == []
    assert [c["id"] for c in machine["subagent"]] == ["title-caught", sub_id]
    assert report["reclassified"] == 1


# ── 翻页扫描 ───────────────────────────────────────────────────────────────


def _page(ids: list[str]) -> list[dict]:
    return [{"id": tid, "title": tid, "messages": 20} for tid in ids]


def test_scan_threads_reads_every_page(monkeypatch):
    """全库扫描：不按时间提前停页（实测旧会话会出现在几十页后）。"""
    page_full = _page([f"omp-x{i}" for i in range(extract_today.NMEM_PAGE_LIMIT)])
    pages = [page_full, page_full, _page(["omp-last"])]
    offsets: list[int] = []

    def fake_page(offset, limit=extract_today.NMEM_PAGE_LIMIT):
        offsets.append(offset)
        return pages[len(offsets) - 1]

    monkeypatch.setattr(extract_today, "fetch_threads_page", fake_page)
    threads, pages_read = extract_today.scan_threads()

    assert pages_read == 3
    assert offsets == [0, 200, 400]
    assert len(threads) == 2 * extract_today.NMEM_PAGE_LIMIT + 1


def test_scan_threads_reads_short_last_page(monkeypatch):
    """最后一页不足一页就是到底，不再开销一次 nmem 调用。"""
    monkeypatch.setattr(extract_today, "fetch_threads_page", lambda offset, limit=200: _page(["omp-x"]))
    threads, pages_read = extract_today.scan_threads()
    assert pages_read == 1
    assert len(threads) == 1


@pytest.mark.parametrize("outcome", ["nonzero", "bad_json", "timeout"])
def test_fetch_threads_page_fails_loud(monkeypatch, outcome):
    """nmem 不可用/非零退出/坏 JSON 必须硬停，不能静默当成空列表。"""

    def fake_run(*args, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd="nmem", timeout=extract_today.NMEM_TIMEOUT_SECONDS)
        return _FakeCompleted("" if outcome == "nonzero" else "not json", returncode=0 if outcome == "bad_json" else 1)

    monkeypatch.setattr(extract_today.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        extract_today.scan_threads()


# ── 归类审查表渲染 ─────────────────────────────────────────────────────────


def test_render_scan_marks_skips_and_aggregates_stubs():
    """表里只有正常候选；机器跳过留痕、stub 聚合行、时间未知行都在表外。"""
    window = extract_today.workday_window(date(2026, 7, 18))

    def thread(name, messages):
        return {"id": _make_thread_id(datetime(2026, 7, 18, 2, 0, tzinfo=UTC)), "title": name, "messages": messages}

    human = [thread("Sub2API 部署", 120), thread("日报补充", 40), thread("测试探针", 3)]
    machine = {"advisor": [{"id": "omp-a", "title": "### Session update", "messages": 9}]}
    report = {"probed": 3, "reclassified": 1, "no_task_message": [], "unreadable": []}
    text = extract_today.render_scan(date(2026, 7, 18), window, human, machine, [], [], report, pages=2, total=400)

    assert "目标工作日：2026-07-18" in text
    assert "机器会话跳过留痕：advisor×1" in text
    assert "| 1 | 120 | Sub2API 部署 |" in text
    assert "| 2 | 40 | 日报补充 |" in text
    assert "测试探针 |" not in text  # stub 不逐条进表
    assert "另 1 条 stub" in text


def test_render_scan_empty_workday():
    """窗口内没有会话时明确说没有，不留空白表。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    text = extract_today.render_scan(date(2026, 7, 18), window, [], {}, [], [], None, pages=1, total=200)
    assert "目标工作日没有会话记录。" in text


# ── --check 输出 ───────────────────────────────────────────────────────────


def test_check_lines_falls_back_to_message_timestamp(monkeypatch):
    """id 不带时间的线程在 --check 里也靠消息 timestamp 判窗口，而不是报 unparseable。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    monkeypatch.setattr(
        extract_today, "fetch_thread_messages", lambda tid, limit=5: ([{"timestamp": "2026-07-18T02:00:00Z"}], True)
    )
    lines = extract_today.check_lines(["deepseek-harness-abc"], window)
    assert lines[1].endswith("\tin")
    assert "unparseable" not in lines[1]


def test_check_lines_reports_attribution():
    """--check 行：每条线程的 CST 时间 + in/out/unparseable，首行是窗口说明。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    in_id = _make_thread_id(datetime(2026, 7, 18, 2, 0, tzinfo=UTC))
    out_id = _make_thread_id(datetime(2026, 7, 18, 21, 0, tzinfo=UTC))
    lines = extract_today.check_lines([in_id, out_id, "garbage"], window)
    assert lines[0].startswith("窗口 [")
    assert lines[1].startswith(in_id + "\t")
    assert lines[1].endswith("\tin")
    assert lines[2].endswith("\tout")
    assert lines[3] == "garbage\t?\tunparseable"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
