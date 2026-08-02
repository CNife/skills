#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.11"
# ///
"""herdr-subagent - 用 herdr 驱动 pi 子代理的薄运行时。

把 herdr 的 agent 协调原语 + pi 的启动参数复用成一个薄子代理运行时，不造框架。
每个子代理是一个真实 pi 跑在 herdr pane 里——可见、可聚焦、可 send-keys 介入。

五个原语由主代理组合（异步默认）：

    spawn <.md> [--name N]   读 .md 翻译成 pi 启动参数、mktemp 建临时目录、
                             herdr pane split + agent start --kind pi。
                             输出 {name, pane, workdir, jsonl}。
    task <name> <任务>        任务写进 workdir/task.md + 发固定交付协议提示词，非阻塞。
                             输出 {sent}。
    wait <name>... [--timeout MS]   轮询命名的子代理，谁先 settled 返回谁
                             （idle/done/blocked/stalled）。输出 {name, state}。
    result <name>            从该子代理的会话 JSONL 抽最终 assistant 全文。
                             空结果回退 herdr agent read transcript。输出 {text}。
    close <name>             herdr pane close + 删临时目录 + 注销；幂等。输出 {ok}。

调用形态（<技能目录> = 本文件 location 的 dirname 的父目录）::

    uv run --script <技能目录>/scripts/subagent.py spawn explorer.md
    uv run --script <技能目录>/scripts/subagent.py task explorer "探索 src/ 结构"
    uv run --script <技能目录>/scripts/subagent.py wait explorer --timeout 120000
    uv run --script <技能目录>/scripts/subagent.py result explorer
    uv run --script <技能目录>/scripts/subagent.py close explorer

frontmatter 契约（认几个核心字段，其余运行时接管）：body -> 系统提示词角色文件路径
（默认 --append-system-prompt，system-prompt-mode: replace 时 --system-prompt）；
model -> --model；thinking -> --thinking；tools -> --tools 白名单；
deny-tools -> --exclude-tools；name/description/spawning/auto-exit/session-mode 忽略。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── 结构化错误 ───────────────────────────────────────────────────────────────


def _die(type: str, message: str, *, exit_code: int = 1, **detail) -> None:
    """结构化错误输出到 stdout（固定 JSON）并 exit。"""
    obj = {"error": True, "type": type, "message": message, **detail}
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(exit_code)


class _ArgParser(argparse.ArgumentParser):
    """argparse 出错时走结构化 JSON 输出（而非默认 stderr usage + exit 2）。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        _die("usage", message, exit_code=2)


class HerdrError(Exception):
    """herdr CLI 返回的错误（服务端错误 exit 1，含 code/message）。"""

    def __init__(self, code: str, message: str, exit_code: int = 1):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


# ── 纯翻译器（主 seam，无需 herdr）───────────────────────────────────────────

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def parse_agent_md(path: Path) -> tuple[dict, str]:
    """拆 agent .md 为 (frontmatter_dict, body_str)。

    frontmatter：开头的 ---\\n...\\n--- 块，行级 ``key: value``（扁平标量，无嵌套）。
    body：闭合 --- 之后的所有内容（含其后的空行，原样保留）。
    无 frontmatter（首行非 ---）时 frontmatter 为空 dict、整体当 body。
    """
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    fm: dict[str, str] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        close = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        if close is not None:
            for ln in lines[1:close]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    fm[k.strip()] = v.strip()
            body_start = close + 1
    body = "\n".join(lines[body_start:])
    return fm, body


def derive_name(path: Path) -> str:
    """文件名 stem -> 合法 herdr agent 名。

    herdr 名须匹配 ``[a-z][a-z0-9_-]{0,31}``：小写、非法字符替成 ``-``、
    截断到 28 字符（留余量给唯一性后缀 -2/-3）。首字符非字母则前缀 ``agent-``。
    """
    stem = Path(path).stem.lower()
    cleaned = []
    for ch in stem:
        if ch.isalnum() or ch in "_-":
            cleaned.append(ch)
        else:
            cleaned.append("-")
    name = "".join(cleaned)
    if not name or not name[0].isalpha():
        name = "agent-" + name
    return name[:28]


def _split_tools(raw: str) -> list[str]:
    """逗号分隔的工具列表：剥空格、过滤空段。"""
    return [p.strip() for p in raw.split(",") if p.strip()]


def build_pi_args(frontmatter: dict, role_file: Path) -> list[str]:
    """frontmatter -> pi CLI 参数列表（不含 argv[0]/'pi'，不含 --session-dir）。

    - body -> ``--append-system-prompt <role_file>``（默认）/ ``--system-prompt``（replace）
    - model -> ``--model``
    - thinking -> ``--thinking``
    - tools -> ``--tools`` 白名单（逗号空格已剥）
    - deny-tools -> ``--exclude-tools``
    - 忽略：name/description/spawning/auto-exit/session-mode
    """
    args: list[str] = []
    mode = (frontmatter.get("system-prompt-mode") or "").strip().lower()
    role_str = str(role_file)
    if mode == "replace":
        args += ["--system-prompt", role_str]
    else:
        args += ["--append-system-prompt", role_str]
    model = (frontmatter.get("model") or "").strip()
    if model:
        args += ["--model", model]
    thinking = (frontmatter.get("thinking") or "").strip()
    if thinking:
        args += ["--thinking", thinking]
    tools_raw = (frontmatter.get("tools") or "").strip()
    if tools_raw:
        tools = _split_tools(tools_raw)
        if tools:
            args += ["--tools", ",".join(tools)]
    deny_raw = (frontmatter.get("deny-tools") or "").strip()
    if deny_raw:
        deny = _split_tools(deny_raw)
        if deny:
            args += ["--exclude-tools", ",".join(deny)]
    return args


# ── herdr 辅助 ───────────────────────────────────────────────────────────────


def _run_herdr(args: list[str], *, timeout: int = 120) -> dict | None:
    """跑 herdr 子命令，返回解析后的 JSON（含 .result）。

    成功（exit 0）：stdout 为 JSON 则返回之，空或非 JSON 返回 None。
    服务端错误（exit 1）/语法错误（exit 2）：stderr 为 JSON ``{"error":{...}}``，
    抛 HerdrError(code, message)。
    """
    proc = subprocess.run(
        ["herdr", *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        raw = proc.stderr.strip() or proc.stdout.strip()
        code, msg = "herdr_error", raw or f"herdr exit {proc.returncode}"
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and isinstance(obj.get("error"), dict):
                code = obj["error"].get("code", code)
                msg = obj["error"].get("message", msg)
        except (json.JSONDecodeError, ValueError):
            pass
        raise HerdrError(code, msg, proc.returncode)
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _agent_get(name: str) -> dict:
    """herdr agent get <name> -> agent 对象（含 agent_status/pane_id/agent_session）。

    agent_not_found 时抛 HerdrError（调用方按需捕获）。
    """
    obj = _run_herdr(["agent", "get", name])
    if obj is None:
        return {}
    return (obj.get("result") or {}).get("agent") or {}


def _agent_get_or_none(name: str) -> dict | None:
    """agent get；agent_not_found 返回 None，其它错误抛 HerdrError。"""
    try:
        return _agent_get(name)
    except HerdrError as e:
        if e.code == "agent_not_found":
            return None
        raise


def _agent_read_text(name: str, *, lines: int = 200) -> str:
    """herdr agent read（返回纯文本 transcript，非 JSON）。失败抛 HerdrError。"""
    proc = subprocess.run(
        ["herdr", "agent", "read", name, "--source", "recent-unwrapped", "--lines", str(lines)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raw = proc.stderr.strip() or proc.stdout.strip()
        raise HerdrError("agent_read_failed", raw or f"exit {proc.returncode}", proc.returncode)
    return proc.stdout


def _is_valid_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def _name_taken(name: str) -> bool:
    return _agent_get_or_none(name) is not None


def _unique_name(base: str) -> str:
    """base 已被占用则追加 -2/-3... 直到唯一（且合法）。"""
    if not _name_taken(base):
        return base
    i = 2
    while True:
        suffix = f"-{i}"
        cand = base[: 32 - len(suffix)] + suffix
        if not _name_taken(cand):
            return cand
        i += 1


def _extract_pane_id(split_obj: dict | None) -> str | None:
    if not split_obj:
        return None
    pane = (split_obj.get("result") or {}).get("pane") or {}
    return pane.get("pane_id")


def _agent_start(name: str, pane_id: str, pi_args: list[str]) -> None:
    """herdr agent start --kind pi，带 shell 落定重试（竞态 "not available shell"）。"""
    last: HerdrError | None = None
    for _ in range(6):
        try:
            _run_herdr(
                [
                    "agent",
                    "start",
                    name,
                    "--kind",
                    "pi",
                    "--pane",
                    pane_id,
                    "--timeout",
                    "30000",
                    "--",
                    *pi_args,
                ],
                timeout=60,
            )
            return
        except HerdrError as e:
            last = e
            if "shell" in (e.message or "").lower():
                time.sleep(0.7)
                continue
            raise
    assert last is not None
    raise last


# ── 注册表（name -> pane_id/workdir/md_path，清理用，运行时以 herdr 活态为准）──


def _registry_path() -> Path:
    env = os.environ.get("HERDR_SUBAGENT_REGISTRY")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "herdr-subagent" / "registry.json"


def _registry_load() -> dict:
    p = _registry_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _registry_save(d: dict) -> None:
    p = _registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


# ── result 抽取（跨依赖 pi-session-query，公开 API，未截断）──────────────────


def _query_py() -> Path | None:
    """定位 pi-session-query 的 query.py：env > 仓库/安装的同级技能路径。"""
    env = os.environ.get("PI_SESSION_QUERY_SCRIPT")
    if env and Path(env).is_file():
        return Path(env)
    sibling = (
        Path(__file__).parent / ".." / ".." / "pi-session-query" / "scripts" / "query.py"
    ).resolve()
    if sibling.is_file():
        return sibling
    installed = Path.home() / ".agents" / "skills" / "pi-session-query" / "scripts" / "query.py"
    if installed.is_file():
        return installed
    return None


# 只用 s.entries + s.leaf()（公开 API），手动回溯 parentId 取最后 assistant 的未截断 text。
_EXTRACT_SCRIPT = """\
import sys
by_id = {e.get('id'): e for e in s.entries if e.get('id')}
leaf_id = s.leaf()['id']
chain = []
cur = by_id.get(leaf_id)
while cur is not None:
    chain.append(cur)
    pid = cur.get('parentId')
    cur = by_id.get(pid) if pid else None
for e in reversed(chain):
    if e.get('type') == 'message':
        m = e.get('message') or {}
        if m.get('role') == 'assistant':
            c = m.get('content')
            if isinstance(c, str):
                sys.stdout.write(c)
            elif isinstance(c, list):
                sys.stdout.write(''.join(b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text'))
            break
"""


def _extract_result_text(jsonl: Path) -> str:
    """用 pi-session-query 抽会话主路径上最后 assistant 消息的全文（未截断）。"""
    qpy = _query_py()
    if qpy is None:
        return ""
    proc = subprocess.run(
        ["uv", "run", "--script", str(qpy), str(jsonl), "-c", _EXTRACT_SCRIPT],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


# ── 五个原语 ─────────────────────────────────────────────────────────────────


def cmd_spawn(md_path: str, name: str | None = None) -> dict:
    p = Path(md_path).expanduser()
    if not p.is_file():
        _die("file_not_found", f"agent 定义文件不存在: {md_path}", exit_code=2, path=str(md_path))
    fm, body = parse_agent_md(p)
    base = (name or derive_name(p)).strip().lower()
    if not _is_valid_name(base):
        _die("usage", f"非法 agent 名 {base!r}（须匹配 [a-z][a-z0-9_-]{{0,31}}）", exit_code=2)
    uname = _unique_name(base) if name is None else base

    workdir = Path(tempfile.mkdtemp(prefix=f"herdr-subagent-{uname}-"))
    role_file = workdir / "role.md"
    role_file.write_text(body, encoding="utf-8")
    pi_args = [*build_pi_args(fm, role_file), "--session-dir", str(workdir)]

    split = _run_herdr(
        ["pane", "split", "--current", "--direction", "right", "--cwd", os.getcwd(), "--no-focus"]
    )
    pane_id = _extract_pane_id(split)
    if not pane_id:
        shutil.rmtree(workdir, ignore_errors=True)
        _die("spawn_failed", f"pane split 未返回 pane_id: {split!r}")

    try:
        _agent_start(uname, pane_id, pi_args)
    except HerdrError as e:
        shutil.rmtree(workdir, ignore_errors=True)
        try:
            _run_herdr(["pane", "close", pane_id])
        except HerdrError:
            pass
        _die("spawn_failed", f"agent start 失败: {e.message}", code=e.code)

    reg = _registry_load()
    reg[uname] = {"pane_id": pane_id, "workdir": str(workdir), "md_path": str(p)}
    _registry_save(reg)

    jsonl: str | None = None
    agent = _agent_get_or_none(uname)
    if agent is not None:
        jsonl = (agent.get("agent_session") or {}).get("value")
    return {"name": uname, "pane": pane_id, "workdir": str(workdir), "jsonl": jsonl}


def cmd_task(name: str, task_text: str) -> dict:
    reg = _registry_load()
    entry = reg.get(name)
    if not entry:
        _die("not_found", f"未注册的子代理: {name}", exit_code=2, name=name)
    workdir = Path(entry["workdir"])
    (workdir / "task.md").write_text(task_text, encoding="utf-8")
    prompt = (
        f"你的任务在 {workdir / 'task.md'}（绝对路径），读它并执行。"
        f"你的最终回复就是交付结果——不要把结果写入文件。"
    )
    try:
        _run_herdr(["agent", "prompt", name, prompt])
    except HerdrError as e:
        if e.code == "agent_not_found":
            _die("agent_not_found", f"子代理不在线（可能已退出）: {name}", name=name)
        raise
    return {"sent": True}


def cmd_wait(names: list[str], timeout_ms: int = 120000) -> dict:
    deadline = time.monotonic() + timeout_ms / 1000.0
    poll = 1.0
    while True:
        states: dict[str, str] = {}
        for nm in names:
            agent = _agent_get_or_none(nm)
            if agent is None:
                return {"name": nm, "state": "done"}  # 已退出
            states[nm] = agent.get("agent_status", "unknown")
        for nm in names:
            if states[nm] in ("idle", "done", "blocked"):
                return {"name": nm, "state": states[nm]}
        if time.monotonic() >= deadline:
            for nm in names:
                if states.get(nm) in ("working", "unknown"):
                    return {"name": nm, "state": "stalled"}
            return {"name": names[0], "state": "stalled"}
        time.sleep(poll)


def cmd_result(name: str) -> dict:
    jsonl: str | None = None
    agent = _agent_get_or_none(name)
    if agent is not None:
        jsonl = (agent.get("agent_session") or {}).get("value")
    if not jsonl:
        entry = _registry_load().get(name)
        if entry:
            wd = Path(entry["workdir"])
            files = sorted(wd.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                jsonl = str(files[0])

    text = ""
    if jsonl and Path(jsonl).is_file():
        text = _extract_result_text(Path(jsonl))
    if not text:
        try:
            text = _agent_read_text(name)
        except HerdrError:
            pass
    return {"text": text}


def cmd_close(name: str) -> dict:
    reg = _registry_load()
    entry = reg.get(name)

    pane_id: str | None = None
    agent = _agent_get_or_none(name)
    if agent is not None:
        pane_id = agent.get("pane_id")
    if entry:
        pane_id = pane_id or entry.get("pane_id")
    workdir = entry.get("workdir") if entry else None

    if pane_id:
        try:
            _run_herdr(["pane", "close", pane_id])
        except HerdrError:
            pass  # 已不在，幂等
    if workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    if name in reg:
        reg.pop(name, None)
        _registry_save(reg)
    return {"ok": True}


# ── CLI 派发 ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = _ArgParser(prog="subagent.py", description="herdr-subagent 薄子代理运行时")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("spawn", help="启动子代理")
    ps.add_argument("md", help="agent 定义 .md 路径")
    ps.add_argument("--name", default=None, help="指定 agent 名（默认从文件名派生）")

    pt = sub.add_parser("task", help="下发任务（非阻塞）")
    pt.add_argument("name", help="子代理名")
    pt.add_argument("task", nargs="+", help="任务文本（多段以空格连接）")

    pw = sub.add_parser("wait", help="等待任一子代理 settled")
    pw.add_argument("names", nargs="+", help="子代理名（一个或多个）")
    pw.add_argument("--timeout", type=int, default=120000, help="超时毫秒（默认 120000）")

    pr = sub.add_parser("result", help="抽取最终回复")
    pr.add_argument("name", help="子代理名")

    pc = sub.add_parser("close", help="回收子代理（幂等）")
    pc.add_argument("name", help="子代理名")

    args = parser.parse_args()
    try:
        if args.cmd == "spawn":
            out = cmd_spawn(args.md, args.name)
        elif args.cmd == "task":
            out = cmd_task(args.name, " ".join(args.task))
        elif args.cmd == "wait":
            out = cmd_wait(args.names, args.timeout)
        elif args.cmd == "result":
            out = cmd_result(args.name)
        elif args.cmd == "close":
            out = cmd_close(args.name)
        else:  # pragma: no cover - argparse 已拦截
            _die("usage", f"未知子命令: {args.cmd}", exit_code=2)
        print(json.dumps(out, ensure_ascii=False))
    except HerdrError as e:
        _die(e.code, e.message, exit_code=1)
    except SystemExit:
        raise
    except Exception as e:
        _die("internal", f"{type(e).__name__}: {e}", exit_code=1)


if __name__ == "__main__":
    main()
