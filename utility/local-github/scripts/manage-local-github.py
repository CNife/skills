#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""管理本地 GitHub 参考库。

子命令：
  sync       抓取全部仓库：浅副本先补史，有上游的做当前分支快进（默认）
  clone      按 属主/仓库名 浅克隆一个仓库到参考库
  ensure     给出本地副本路径：缺则浅克隆，--fresh 时先补史并快进
  path       只查本地副本路径，不联网
  unshallow  补全指定仓库（或全部浅副本）的历史，不刷新代码
  list       按上次更新时间列出各仓库，标注浅副本与命名问题
  rename     把裸名目录规范为 属主@仓库名

参考库根目录取环境变量 LOCAL_GITHUB_ROOT，默认 ~/github。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

ROOT = Path(os.environ.get("LOCAL_GITHUB_ROOT") or Path.home() / "github").expanduser()
_use_color = sys.stdout.isatty()


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _use_color else s


def green(s: str) -> str:
    return _c("32", s)


def yellow(s: str) -> str:
    return _c("33", s)


def red(s: str) -> str:
    return _c("31", s)


def dim(s: str) -> str:
    return _c("2", s)


def run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout, p.stderr


def last_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""


def parse_origin(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def list_repos() -> list[Path]:
    if not ROOT.exists():
        return []
    return sorted(d for d in ROOT.iterdir() if d.is_dir() and (d / ".git").exists())


def origin_of(d: Path) -> tuple[str, str] | None:
    rc, out, _ = run(["git", "-C", str(d), "remote", "get-url", "origin"])
    if rc != 0:
        return None
    return parse_origin(out)


def find_repo(owner: str, repo: str) -> Path | None:
    """按 属主@仓库 找本地副本，大小写不敏感。"""
    wanted = f"{owner}@{repo}".lower()
    for d in list_repos():
        if d.name.lower() == wanted:
            return d
    return None


def naming_warn(d: Path) -> list[str]:
    origin = origin_of(d)
    if not origin:
        return ["无 origin 或非 GitHub 仓库"]
    expected = f"{origin[0]}@{origin[1]}"
    if d.name.lower() == expected.lower():
        return []
    return [f"命名不规范，应为 {expected}"]


def run_stream(cmd: list[str]) -> tuple[int, str]:
    """运行 git 并把 stderr 直通终端，让 git 自己画进度。返回 (退出码, stdout)。"""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=None, text=True, check=False)
    return p.returncode, p.stdout


def is_shallow(d: Path) -> bool:
    _, out, _ = run(["git", "-C", str(d), "rev-parse", "--is-shallow-repository"])
    return out.strip() == "true"


def deepen_cmd(d: Path) -> list[str]:
    """补史命令：当前分支 + 全部 tag 的完整历史。"""
    return ["git", "-C", str(d), "fetch", "--unshallow", "--tags", "--prune", "origin"]


def deepen(d: Path, *, stream: bool = False) -> str | None:
    """把浅副本补成完整历史（当前分支 + 全部 tag）。返回失败原因，成功返回 None。

    失败不阻断刷新：调用方退化回普通抓取。``stream`` 让 git 自己向终端画进度，
    此时错误已经由 git 直接输出，只回一句可打印的原因。
    """
    if stream:
        rc, _ = run_stream(deepen_cmd(d))
        return None if rc == 0 else "git 已报错"
    rc, _, err = run(deepen_cmd(d))
    return None if rc == 0 else last_line(err) or "未知错误"


class Refresh(NamedTuple):
    """一次刷新的结果：状态、说明、警告，以及本次是否补了史。"""

    status: str
    note: str
    warns: list[str]
    deepened: bool = False


def refresh(d: Path, *, unshallow: bool = True) -> Refresh:
    """补史（浅副本）、抓取、在不冲突时快进当前分支。"""
    warns = naming_warn(d)
    notes: list[str] = []
    deepened = False

    if unshallow and is_shallow(d):
        failure = deepen(d)
        if failure is None:
            notes.append("已补史")
            deepened = True
        else:
            notes.append(f"补史失败：{failure}")

    if not deepened:
        rc, _, err = run(["git", "-C", str(d), "fetch", "--prune", "origin"])
        if rc != 0:
            return Refresh("失败", join_notes([*notes, last_line(err) or "fetch 失败"]), warns)

    _, branch, _ = run(["git", "-C", str(d), "branch", "--show-current"])
    if not branch.strip():
        return Refresh("跳过", join_notes([*notes, "分离 HEAD"]), warns, deepened)

    rc, _, _ = run(["git", "-C", str(d), "rev-parse", "--abbrev-ref", "@{upstream}"])
    if rc != 0:
        return Refresh("跳过", join_notes([*notes, "无上游"]), warns, deepened)

    _, before, _ = run(["git", "-C", str(d), "rev-parse", "HEAD"])
    rc, _, err = run(["git", "-C", str(d), "merge", "--ff-only"])
    if rc != 0:
        _, ahead, _ = run(["git", "-C", str(d), "rev-list", "--count", "@{upstream}..HEAD"])
        ahead = ahead.strip()
        if ahead and ahead != "0":
            reason = f"本地领先 {ahead} 个提交，未快进"
        elif "would be overwritten" in err:
            reason = "本地改动挡住更新"
        else:
            reason = last_line(err) or "无法快进"
        return Refresh("跳过", join_notes([*notes, reason]), warns, deepened)
    _, after, _ = run(["git", "-C", str(d), "rev-parse", "HEAD"])

    if before.strip() == after.strip():
        return Refresh("已最新", join_notes(notes), warns, deepened)
    return Refresh("已更新", join_notes([f"{before.strip()[:8]} → {after.strip()[:8]}", *notes]), warns, deepened)


def join_notes(parts: list[str]) -> str:
    return "；".join(x for x in parts if x)


class Progress:
    """终端单行进度：原地刷新已完成数，收尾时清掉这一行。"""

    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.width = 0

    def tick(self, name: str) -> None:
        self.done += 1
        line = f"同步 {self.done}/{self.total}：{name}"
        pad = max(0, self.width - len(line))
        sys.stderr.write("\r" + line + " " * pad)
        sys.stderr.flush()
        self.width = max(self.width, len(line))

    def clear(self) -> None:
        if self.width:
            sys.stderr.write("\r" + " " * self.width + "\r")
            sys.stderr.flush()


def cmd_sync(keep_shallow: bool) -> int:
    repos = list_repos()
    if not repos:
        print("参考库为空")
        return 0
    progress = Progress(len(repos)) if sys.stderr.isatty() else None
    results: list[tuple[Path, Refresh]] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(refresh, d, unshallow=not keep_shallow): d for d in repos}
        for fut in as_completed(futures):
            d = futures[fut]
            results.append((d, fut.result()))
            if progress:
                progress.tick(d.name)
    if progress:
        progress.clear()
    rows = sorted((d.name, *r) for d, r in results)
    width = max(len(r[0]) for r in rows)
    counts: dict[str, int] = {}
    deepened = 0
    for name, status, note, warns, was_deepened in rows:
        counts[status] = counts.get(status, 0) + 1
        if was_deepened:
            deepened += 1
        styled = {"已更新": green(status), "已最新": dim(status), "失败": red(status)}.get(status, yellow(status))
        line = f"{name.ljust(width)}  {styled}"
        detail = join_notes([note, *warns])
        if detail:
            line += f"  {detail}"
        print(line)
    summary = "  ".join(f"{k}:{counts[k]}" for k in ("已更新", "已最新", "跳过", "失败") if k in counts)
    if deepened:
        summary += f"  补史:{deepened}"
    print(summary)
    return 0


def parse_spec(spec: str) -> tuple[str, str] | None:
    origin = parse_origin(spec)
    if origin:
        return origin
    if "@" in spec:
        owner, _, repo = spec.partition("@")
    elif "/" in spec:
        owner, _, repo = spec.partition("/")
    else:
        return None
    repo = repo.removesuffix(".git")
    if not owner or not repo:
        return None
    return owner, repo


def canonical_spec(owner: str, repo: str) -> tuple[str, str, list[str]]:
    """用 gh 取 GitHub 上的规范大小写；取不到时沿用输入。"""
    gh = shutil.which("gh")
    if not gh:
        return owner, repo, ["未找到 gh，沿用输入大小写"]
    rc, out, _ = run([gh, "api", f"repos/{owner}/{repo}", "--jq", ".full_name"])
    if rc == 0 and "/" in out:
        full_owner, full_repo = out.strip().split("/", 1)
        return full_owner, full_repo, []
    return owner, repo, ["gh 取规范大小写失败，沿用输入大小写"]


class CloneError(Exception):
    """克隆失败，消息可直接展示给用户。"""


def clone_repo(owner: str, repo: str) -> tuple[Path, bool, list[str]]:
    """克隆到参考库。返回 (目录, 是否新建, 提示)。已存在时直接返回现有目录。"""
    owner, repo, notes = canonical_spec(owner, repo)
    existing = find_repo(owner, repo)
    if existing:
        return existing, False, notes

    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / f"{owner}@{repo}"
    if target.exists():
        raise CloneError(f"目录已存在但不是仓库：{target}")

    gh = shutil.which("gh")
    if gh:
        rc, _, _ = run([gh, "repo", "clone", f"{owner}/{repo}", str(target), "--", "--depth", "1", "--no-tags"])
        if rc == 0:
            return target, True, notes
        notes.append("gh repo clone 失败，退回 git clone")

    rc, _, err = run(
        ["git", "clone", "--depth", "1", "--no-tags", f"https://github.com/{owner}/{repo}.git", str(target)]
    )
    if rc != 0:
        raise CloneError(last_line(err) or "未知错误")
    return target, True, notes


def parse_or_fail(spec: str) -> tuple[str, str] | None:
    parsed = parse_spec(spec)
    if not parsed:
        print(red(f"无法解析仓库：{spec}（请用 属主/仓库名）"), file=sys.stderr)
    return parsed


def cmd_clone(spec: str) -> int:
    parsed = parse_or_fail(spec)
    if not parsed:
        return 2
    try:
        target, created, notes = clone_repo(*parsed)
    except CloneError as e:
        print(red(f"克隆失败：{e}"))
        return 1
    for note in notes:
        print(yellow(note), file=sys.stderr)
    print(green(f"已克隆：{target}") if created else f"已存在：{target}")
    return 0


def cmd_ensure(spec: str, fresh: bool) -> int:
    """缺则克隆、有则给出路径。stdout 只有路径，诊断走 stderr。"""
    parsed = parse_or_fail(spec)
    if not parsed:
        return 2
    owner, repo = parsed
    notes: list[str] = []
    target = find_repo(owner, repo)
    if target is None:
        try:
            target, _, notes = clone_repo(owner, repo)
        except CloneError as e:
            print(red(f"克隆失败：{e}"), file=sys.stderr)
            return 1
    elif fresh:
        status, note, warns, _ = refresh(target)
        if status != "已最新":
            notes = [f"{status}：{note}" if note else status, *warns]
    for note in notes:
        print(yellow(note), file=sys.stderr)
    print(target)
    return 0


def cmd_path(spec: str) -> int:
    parsed = parse_or_fail(spec)
    if not parsed:
        return 2
    target = find_repo(*parsed)
    if target is None:
        print(red(f"参考库没有 {parsed[0]}/{parsed[1]}：{ROOT}"), file=sys.stderr)
        return 1
    print(target)
    return 0


def cmd_unshallow(specs: list[str], all_: bool) -> int:
    """补全浅副本的历史（当前分支 + 全部 tag），不刷新代码。"""
    if all_:
        targets = [d for d in list_repos() if is_shallow(d)]
        if not targets:
            print("没有浅副本")
            return 0
    else:
        if not specs:
            print(red("用法：unshallow <仓库>... 或 unshallow --all"), file=sys.stderr)
            return 2
        targets = []
        for spec in specs:
            parsed = parse_or_fail(spec)
            if not parsed:
                return 2
            target = find_repo(*parsed)
            if target is None:
                print(red(f"参考库没有 {parsed[0]}/{parsed[1]}：{ROOT}"), file=sys.stderr)
                return 1
            targets.append(target)

    failed = 0
    for d in targets:
        if not is_shallow(d):
            print(dim(f"{d.name} 已是全量"))
            continue
        print(f"补全 {d.name} 的历史…", file=sys.stderr)
        if deepen(d, stream=True) is not None:
            print(red(f"{d.name} 补史失败"), file=sys.stderr)
            failed += 1
            continue
        _, count, _ = run(["git", "-C", str(d), "rev-list", "--count", "HEAD"])
        print(f"{d.name}  已补史（{count.strip()} 个提交）")
    return 1 if failed else 0


def last_update(d: Path) -> float | None:
    """上次抓取或克隆时间：fetch 写 .git/FETCH_HEAD，clone 只写 .git/packed-refs。"""
    marks = [d / ".git" / "FETCH_HEAD", d / ".git" / "packed-refs"]
    stamps = [m.stat().st_mtime for m in marks if m.exists()]
    return max(stamps) if stamps else None


def ago(ts: float | None) -> str:
    if ts is None:
        return "从未更新"
    delta = time.time() - ts
    if delta >= 86400:
        return f"{int(delta // 86400)} 天前"
    if delta >= 3600:
        return f"{int(delta // 3600)} 小时前"
    if delta >= 60:
        return f"{int(delta // 60)} 分钟前"
    return "刚刚"


def cmd_list() -> int:
    repos = list_repos()
    if not repos:
        print("参考库为空")
        return 0
    rows = [(d.name, last_update(d), naming_warn(d), is_shallow(d)) for d in repos]
    rows.sort(key=lambda r: r[1] or 0)
    width = max(len(r[0]) for r in rows)
    for name, fetched, warns, shallow in rows:
        line = f"{name.ljust(width)}  {ago(fetched).rjust(9)}"
        if shallow:
            line += "  " + yellow("浅")
        detail = join_notes(warns)
        if detail:
            line += f"  {yellow(detail)}"
        print(line)
    return 0


def cmd_rename() -> int:
    renamed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    conflicts: list[tuple[str, str]] = []
    for d in list_repos():
        origin = origin_of(d)
        if not origin:
            skipped.append((d.name, "无 origin 或非 GitHub"))
            continue
        expected = f"{origin[0]}@{origin[1]}"
        if d.name == expected:
            continue
        if any(x.is_dir() and x != d and x.name.lower() == expected.lower() for x in ROOT.iterdir()):
            conflicts.append((d.name, expected))
            continue
        d.rename(ROOT / expected)
        renamed.append((d.name, expected))
    for old, new in renamed:
        print(f"{old} → {green(new)}")
    for name, why in skipped:
        print(yellow(f"跳过 {name}：{why}"))
    for old, new in conflicts:
        print(red(f"冲突 {old} → {new}：目标已存在"))
    print(dim(f"改名 {len(renamed)} 个，跳过 {len(skipped)} 个，冲突 {len(conflicts)} 个"))
    return 1 if conflicts else 0


def main() -> int:
    p = argparse.ArgumentParser(
        prog="manage-local-github.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd")
    ps = sub.add_parser("sync", help="抓取全部仓库并快进当前分支（默认）；浅副本先补史")
    ps.add_argument("--keep-shallow", action="store_true", help="本次跳过补史，只推进浅副本的 tip")
    pc = sub.add_parser("clone", help="浅克隆仓库到 属主@仓库名 目录")
    pc.add_argument("repo", help="属主/仓库名（也接受 属主@仓库名 或 GitHub 地址）")
    pe = sub.add_parser("ensure", help="给出本地副本路径，缺则克隆（stdout 只有路径）")
    pe.add_argument("repo", help="属主/仓库名（也接受 属主@仓库名 或 GitHub 地址）")
    pe.add_argument("--fresh", action="store_true", help="先补史并快进，副本仍不可刷新时只提示")
    pp = sub.add_parser("path", help="只查本地副本路径，不联网")
    pp.add_argument("repo", help="属主/仓库名（也接受 属主@仓库名 或 GitHub 地址）")
    pu = sub.add_parser("unshallow", help="补全指定仓库（或 --all 全部浅副本）的历史，不刷新代码")
    pu.add_argument("repos", nargs="*", metavar="仓库", help="属主/仓库名（也接受 属主@仓库名 或 GitHub 地址）")
    pu.add_argument("--all", action="store_true", dest="all_repos", help="补全参考库内全部浅副本")
    sub.add_parser("list", help="按上次更新时间列出各仓库，标注浅副本")
    sub.add_parser("rename", help="把裸名目录规范为 属主@仓库名")
    args = p.parse_args()
    if args.cmd == "sync":
        return cmd_sync(args.keep_shallow)
    if args.cmd is None:
        return cmd_sync(False)
    if args.cmd == "clone":
        return cmd_clone(args.repo)
    if args.cmd == "ensure":
        return cmd_ensure(args.repo, args.fresh)
    if args.cmd == "path":
        return cmd_path(args.repo)
    if args.cmd == "unshallow":
        return cmd_unshallow(args.repos, args.all_repos)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "rename":
        return cmd_rename()
    return 0


def _exit_if_broken_pipe() -> None:
    """被 head 之类的下游提前关掉时安静退出，像普通 Unix 过滤器一样。"""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


if __name__ == "__main__":
    _exit_if_broken_pipe()
    sys.exit(main())
