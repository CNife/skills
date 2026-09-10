#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest>=8"]
# ///
"""extract_today.py 的测试 - 04:00 工作日窗口 + 12:00 总结分界 + UUID v7 时间过滤 + 机器会话分类。

运行：cd <skill目录> && uv run --script tests/test_extract_today.py
"""

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
    candidates, excluded = extract_today.filter_threads(threads, window)
    assert [c["id"] for c in candidates] == [in_id]
    assert [e["id"] for e in excluded] == [out_id]


def test_filter_threads_unparseable_goes_to_candidates():
    """无法解析 UUID v7 的线程不丢弃，归入候选由 collector 复核。"""
    window = extract_today.workday_window(date(2026, 7, 18))
    threads = [{"id": "garbage", "title": "?", "messages": 5}]
    candidates, excluded = extract_today.filter_threads(threads, window)
    assert len(candidates) == 1
    assert len(excluded) == 0


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
    candidates, machine, excluded = extract_today.partition_threads(threads, window)
    assert [c["id"] for c in candidates] == [human_id]
    assert [m["id"] for m in machine["advisor"]] == [advisor_id]
    assert [e["id"] for e in excluded] == [out_id]
    assert set(machine) == {"advisor"}  # 空族省略


# ── --check 输出 ───────────────────────────────────────────────────────────


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
