#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8"]
# ///
"""extract_today.py 的测试 - 04:00 工作日窗口切分 + 12:00 总结分界逻辑。

运行：cd <skill目录> && uv run --script scripts/test_extract_today.py
"""

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
    sessions = extract_today.collect_sessions(date(2026, 7, 18), pi_dir, tmp_path / "omp-empty")
    ids = [s["session_id"] for s in sessions]
    assert ids == ["uuid-1"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
