#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""extract_today.py 的测试 - 04:00 工作日窗口切分 + 12:00 总结分界逻辑。

运行：cd <skill目录> && uv run --script tests/test_extract_today.py
"""

import sys
from pathlib import Path

# 测试在 tests/，脚本目录不在 sys.path；显式加入以便 import 被测模块。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import extract_today
import pytest

CST = ZoneInfo("Asia/Shanghai")


def test_workday_window_spans_04_to_next_day_04():
    """目标工作日的窗口是 [当日 04:00, 次日 04:00) CST。"""
    start, end = extract_today.workday_window(date(2026, 7, 18))
    assert start == datetime(2026, 7, 18, 4, 0, tzinfo=CST)
    assert end == datetime(2026, 7, 19, 4, 0, tzinfo=CST)


@pytest.mark.parametrize(
    "utc_ts, expected",
    [
        # 窗口 [2026-07-18 04:00 CST, 2026-07-19 04:00 CST) = UTC [07-17 20:00, 07-18 20:00)
        ("2026-07-18T02:00:00Z", True),  # CST 07-18 10:00 窗口内
        ("2026-07-17T19:00:00Z", False),  # CST 07-18 03:00 凌晨归前日
        ("2026-07-18T19:00:00Z", True),  # CST 07-19 03:00 次日凌晨
        ("2026-07-18T21:00:00Z", False),  # CST 07-19 05:00 窗口外
        ("2026-07-17T20:00:00Z", True),  # CST 07-18 04:00 左边界闭
        ("2026-07-18T20:00:00Z", False),  # CST 07-19 04:00 右边界开
        ("2026-07-18T02:00:00.123Z", True),  # 带毫秒
        ("2026-07-18T02:00:00+00:00", True),  # +00:00 后缀
        ("2026-07-18T02-00-00-000Z", True),  # 文件名格式
        ("", False),  # 空时间戳
        ("garbage", False),  # 无法解析
    ],
)
def test_session_in_window(utc_ts, expected):
    window = extract_today.workday_window(date(2026, 7, 18))
    assert extract_today.session_in_window(utc_ts, window) is expected


def test_coarse_utc_prefixes_covers_window_plus_one_day_margin():
    """粗筛前缀覆盖工作日窗口的 UTC 日期，前后各扩 1 天防边界漂移。

    目标 2026-07-18 CST，窗口 UTC [07-17 20:00, 07-18 20:00)，
    前缀 {07-16, 07-17, 07-18, 07-19}。
    """
    prefixes = extract_today.coarse_utc_prefixes(date(2026, 7, 18))
    assert prefixes == ["2026-07-16", "2026-07-17", "2026-07-18", "2026-07-19"]


def test_coarse_utc_prefixes_crosses_month_boundary():
    """跨月边界：目标 2026-07-01 窗口跨 6/7 月，前缀含 06-29..07-02。"""
    prefixes = extract_today.coarse_utc_prefixes(date(2026, 7, 1))
    assert prefixes == ["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02"]


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


def _make_pi_session(root, fname_ts, uuid, ts_iso, title, n_msgs=3):
    """构造 pi 会话 jsonl：root/<proj>/<fname_ts>_<uuid>.jsonl。"""
    proj = root / "home-cnife-code-testproj"
    proj.mkdir(parents=True, exist_ok=True)
    fpath = proj / f"{fname_ts}_{uuid}.jsonl"
    session_line = json.dumps(
        {"type": "session", "id": uuid, "timestamp": ts_iso, "cwd": "/home/cnife/code/testproj"}
    )
    lines = [session_line, json.dumps({"type": "session_info", "name": title})]
    for i in range(n_msgs):
        role = "user" if i % 2 == 0 else "assistant"
        msg = {
            "type": "message",
            "message": {"role": role, "content": [{"type": "text", "text": f"msg {i}"}]},
        }
        lines.append(json.dumps(msg))
    fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fpath


def test_collect_sessions_keeps_only_workday_window(tmp_path):
    """端到端：粗筛多前缀扫到跨 UTC 日期文件，04:00 精确切分只留窗口内。

    目标工作日 2026-07-18 CST，窗口 UTC [07-17 20:00, 07-18 20:00)。
    """
    pi_dir = tmp_path / "pi-sessions"
    _make_pi_session(
        pi_dir, "2026-07-18T02-00-00-000Z", "uuid-1", "2026-07-18T02:00:00.000Z", "窗口内 CST10:00"
    )
    _make_pi_session(
        pi_dir,
        "2026-07-17T19-00-00-000Z",
        "uuid-2",
        "2026-07-17T19:00:00.000Z",
        "窗口外 CST03:00 凌晨",
    )
    _make_pi_session(
        pi_dir,
        "2026-07-18T21-00-00-000Z",
        "uuid-3",
        "2026-07-18T21:00:00.000Z",
        "窗口外 CST次日05:00",
    )
    sessions, filtered = extract_today.collect_sessions(
        date(2026, 7, 18), pi_dir, tmp_path / "omp-empty"
    )
    ids = [s["session_id"] for s in sessions]
    assert ids == ["uuid-1"]
    assert filtered == []  # 窗口外会话不算"被过滤"，只有窗口内被滤的才可见


def test_collect_sessions_surfaces_filtered_sessions(tmp_path):
    """min_msgs/exclude 过滤掉的窗口内会话必须可见（防假空集）。

    total: 0 若由过滤造成，调用方应能从 filtered 看到被滤会话，
    而不是误判"目标工作日无会话"直接终止。
    """
    pi_dir = tmp_path / "pi-sessions"
    _make_pi_session(
        pi_dir,
        "2026-07-18T02-00-00-000Z",
        "uuid-1",
        "2026-07-18T02:00:00.000Z",
        "实质会话",
        n_msgs=12,
    )
    _make_pi_session(
        pi_dir,
        "2026-07-18T03-00-00-000Z",
        "uuid-2",
        "2026-07-18T03:00:00.000Z",
        "短 stub",
        n_msgs=2,
    )
    _make_pi_session(
        pi_dir,
        "2026-07-18T04-00-00-000Z",
        "uuid-3",
        "2026-07-18T04:00:00.000Z",
        "被排除会话",
        n_msgs=15,
    )
    sessions, filtered = extract_today.collect_sessions(
        date(2026, 7, 18), pi_dir, tmp_path / "omp-empty", min_msgs=10, exclude="uuid-3"
    )
    assert [s["session_id"] for s in sessions] == ["uuid-1"]
    by_id = {f["session_id"]: f for f in filtered}
    assert set(by_id) == {"uuid-2", "uuid-3"}
    assert by_id["uuid-2"]["reason"] == "min_msgs"
    assert by_id["uuid-2"]["msg_count"] == 2
    assert by_id["uuid-3"]["reason"] == "excluded"


def test_recap_before_noon_current_session_outside_window():
    """12:00 前跑 recap：目标工作日是昨天，当前会话必然在窗口外。

    回归实测事故：08-03 08:46 CST 跑 recap，目标工作日 08-02，
    窗口 [08-02 04:00, 08-03 04:00) CST；当前会话 08:46 CST 在窗口外。
    技能曾用"当前会话必在窗口内"反证空集——该前提在 12:00 前恒不成立。
    """
    now = datetime(2026, 8, 3, 8, 46, tzinfo=CST)
    target = extract_today.choose_target_workday(now)
    assert target == date(2026, 8, 2)
    window = extract_today.workday_window(target)
    # 当前会话 timestamp（UTC）= 08-03 00:46Z = 08:46 CST
    assert extract_today.session_in_window("2026-08-03T00:46:16.000Z", window) is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
