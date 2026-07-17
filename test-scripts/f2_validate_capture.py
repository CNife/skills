#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["rich>=13"]
# ///

"""
F2 — 验证 capture.ts 扩展在 pi 中正确抓取请求/响应。

测试方法：用 `pi --extension capture.ts --print` 执行一个简单任务，
检查日志文件是否包含所有预期的关键段。

断言（全部满足才算通过）：
- 日志文件存在且非空
- 日志包含 [REQUEST] before_provider_request payload
- 日志包含 [MESSAGE_END]
- 日志包含 usage 字段
- 日志包含 ╔═...═╗ 块分隔线

用法：
  uv run --script test-scripts/f2_validate_capture.py \
    [--model <provider/model>] \
    [--log-path /tmp/pi-capture.log]

示例：
  uv run --script test-scripts/f2_validate_capture.py
  uv run --script test-scripts/f2_validate_capture.py --model ark-coding-plan/minimax-m3
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

# ── Constants ────────────────────────────────────────────────────────────────

SKILL_DIR = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CAPTURE_TS = os.path.join(
    SKILL_DIR, "pi-agent", "add-provider-models-to-pi", "scripts", "capture.ts"
)
DEFAULT_MODEL = "ark-coding-plan/minimax-m3"

REQUIRED_SECTIONS: list[str] = ["before_provider_request payload", "[MESSAGE_END]", "usage=", "╔═"]

# ── Helpers ─────────────────────────────────────────────────────────────────


def _e(msg: str) -> None:
    print(f"  ❌ {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def _info(msg: str) -> None:
    print(f"  [i] {msg}", file=sys.stderr)


def check_required_sections(log_text: str) -> list[str]:
    """Return a list of missing section names."""
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in log_text:
            missing.append(section)
    return missing


def count_call_blocks(log_text: str) -> int:
    """Count the number of CALL blocks in the log."""
    return len(re.findall(r"╔═+╗", log_text))


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="F2 — 验证 capture.ts 扩展抓取行为")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型 ID（默认 {DEFAULT_MODEL}）")
    parser.add_argument(
        "--capture-ts",
        default=DEFAULT_CAPTURE_TS,
        help=f"capture.ts 路径（默认 {DEFAULT_CAPTURE_TS}）",
    )
    parser.add_argument("--log-path", default="", help="日志输出路径（默认临时文件）")
    args = parser.parse_args()

    # 验证 capture.ts 存在
    if not os.path.isfile(args.capture_ts):
        _e(f"capture.ts 不存在: {args.capture_ts}")
        return 1

    # 确定日志路径
    if args.log_path:
        log_path = args.log_path
    else:
        fd, log_path = tempfile.mkstemp(suffix=".log", prefix="pi-capture-test-")
        os.close(fd)

    _info(f"capture.ts: {args.capture_ts}")
    _info(f"model:      {args.model}")
    _info(f"log path:   {log_path}")
    print()

    # 执行 pi --extension
    env = os.environ.copy()
    env["PI_CAPTURE_LOG"] = log_path

    cmd = [
        "pi",
        "--extension",
        args.capture_ts,
        "--print",
        "--model",
        args.model,
        "Say hello in one word",
    ]

    _info(f"Running: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        _e("pi 运行超时（60s）")
        return 1
    except FileNotFoundError:
        _e("pi 命令未找到，请确认 pi 已安装并在 PATH 中")
        return 1

    # 检查 pi 退出码（非零不代表测试失败，capture 可能仍部分工作）
    if result.returncode != 0:
        _info(f"pi exited with code {result.returncode}")
        _info(f"stderr: {result.stderr.strip()[:500]}")
        # 继续检查日志，不立刻退出

    print()
    _info("--- 检查日志 ---")
    print()

    # 检查日志文件
    if not os.path.isfile(log_path):
        _e("日志文件未生成")
        return 1

    with open(log_path, encoding="utf-8", errors="replace") as f:
        log_text = f.read()

    if not log_text.strip():
        _e("日志文件为空")
        return 1

    _ok(f"日志文件存在且非空 ({len(log_text)} chars)")

    # 检查必要段
    missing = check_required_sections(log_text)
    if missing:
        for sec in missing:
            _e(f"缺少必要段: {sec!r}")
        return 1

    for sec in REQUIRED_SECTIONS:
        _ok(f"包含 {sec!r}")

    # 检查 CALL 块数量
    blocks = count_call_blocks(log_text)
    if blocks >= 1:
        _ok(f"包含至少 1 个 CALL 块（实际: {blocks}）")
    else:
        _e("没有 CALL 块")
        return 1

    print()
    _info("--- 摘要 ---")
    print()

    # 提取 usage 行做摘要
    for line in log_text.splitlines():
        if "usage=" in line:
            _info(f"usage: {line.strip()}")

    print()
    _ok("F2 验证通过 — capture.ts 抓取行为正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
