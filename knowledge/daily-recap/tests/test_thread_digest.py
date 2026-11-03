#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest>=8"]
# ///
"""thread_digest.py 的测试 - 前言剥离 + 截断 + 首尾/全用户选取 + 离线摘要。

运行：cd <skill目录> && uv run --script tests/test_thread_digest.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest
import thread_digest


def _thread(roles: list[str], size: int = 400) -> dict:
    messages = [
        {"index": position, "role": role, "content": f"{role}-{position}-" + "x" * size}
        for position, role in enumerate(roles)
    ]
    return {"id": "omp-test", "title": "测试线程", "total_messages": len(messages), "messages": messages}


# ── 前言剥离与截断 ──────────────────────────────────────────────────────────


def test_clean_strips_system_notice_block():
    text = "开头\n<system-notice>\n设备清单变了\n</system-notice>\n正文"
    assert "<system-notice>" not in thread_digest.clean(text)
    assert "设备清单变了" not in thread_digest.clean(text)
    assert "正文" in thread_digest.clean(text)


def test_clean_marks_omp_context_header():
    text = "OMP custom context (skill-prompt):\n[IMPORTANT: User invoked]\n正文"
    cleaned = thread_digest.clean(text)
    assert "OMP custom context" not in cleaned
    assert "[skill-prompt follows]" in cleaned


def test_truncate_reports_dropped_length():
    text = "a" * 100
    cut = thread_digest.truncate(text, 10)
    assert cut.startswith("a" * 10)
    assert "+90 chars" in cut
    assert thread_digest.truncate("short", 10) == "short"


# ── 选取 ────────────────────────────────────────────────────────────────────


def test_selection_keeps_head_and_tail():
    messages = _thread(["user", "assistant"] * 5)["messages"]
    assert thread_digest.select_positions(messages, head=2, tail=2, all_users=False) == [0, 1, 8, 9]


def test_selection_adds_only_user_messages_in_middle():
    roles = ["user", "assistant", "assistant", "user", "assistant", "assistant"]
    messages = _thread(roles)["messages"]
    assert thread_digest.select_positions(messages, head=1, tail=1, all_users=True) == [0, 3, 5]


def test_selection_clamps_when_thread_shorter_than_window():
    messages = _thread(["user", "assistant"])["messages"]
    assert thread_digest.select_positions(messages, head=12, tail=12, all_users=False) == [0, 1]


# ── 输出形态 ────────────────────────────────────────────────────────────────


def test_digest_reports_gap_and_stats():
    data = _thread(["user", "assistant", "assistant", "user", "assistant", "assistant"])
    output = thread_digest.digest(data, chars=20, head=1, tail=1)
    assert "## 测试线程" in output
    assert "id=omp-test messages=6" in output
    assert "--- (4 条未选中)" in output
    assert "[选中 2/6 条 | head=1 tail=1 all_users=False chars=20]" in output


def test_digest_falls_back_to_placeholder_title():
    data = {"id": "omp-x", "messages": []}
    output = thread_digest.digest(data)
    assert "## (无标题)" in output
    assert "messages=0" in output


# ── 离线入口 ────────────────────────────────────────────────────────────────


def test_from_json_prints_digest(tmp_path: Path, capsys):
    path = tmp_path / "thread.json"
    path.write_text(json.dumps(_thread(["user", "assistant"]), ensure_ascii=False), encoding="utf-8")
    assert thread_digest.main(["--from-json", str(path)]) == 0
    output = capsys.readouterr().out
    assert "## 测试线程" in output
    assert "#0 user" in output


def test_missing_targets_error(capsys):
    try:
        thread_digest.main([])
    except SystemExit as exit_error:
        assert exit_error.code == 2
    else:
        raise AssertionError("无参数时应以退出码 2 结束")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
