# /// script
# dependencies = ["typer>=0.12"]
# ///

"""
chezmoi-sync 辅助工具

dotfiles 同步的核心操作封装。每个 subcommand 输出结构化文本供 agent 解析使用。

Usage:
    uv run --script scripts/chezmoi-sync.py status    # 双层级状态检测
    uv run --script scripts/chezmoi-sync.py diff      # 展示 chezmoi diff 摘要
    uv run --script scripts/chezmoi-sync.py re-add    # 智能 re-add
    uv run --script scripts/chezmoi-sync.py commit    # 提交变更
    uv run --script scripts/chezmoi-sync.py verify    # 最终验证
    uv run --script scripts/chezmoi-sync.py fetch     # git fetch 远程
    uv run --script scripts/chezmoi-sync.py pull      # git pull（含冲突处理）
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="chezmoi-sync",
    no_args_is_help=True,
    help="dotfiles 同步核心操作",
)

# ── Error codes ────────────────────────────────────────────────────────────
EXIT_CLEAN = 0
EXIT_HAS_CHANGES = 2  # 有变更（非错误，但需要处理）
EXIT_ERROR = 1        # 真正错误


# ── Helpers ────────────────────────────────────────────────────────────────

def _chz(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """执行 chezmoi 命令"""
    return subprocess.run(
        ["chezmoi", *args],
        capture_output=True, text=True,
        check=check,
    )


def _chz_git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """执行 chezmoi git -- <args>"""
    return subprocess.run(
        ["chezmoi", "git", "--", *args],
        capture_output=True, text=True,
        check=check,
    )


def _source_path() -> str:
    """获取 chezmoi 源目录路径"""
    r = _chz("source-path", check=True)
    return r.stdout.strip()


def _fmt_dt(ts: int) -> str:
    """Unix 时间戳 → 可读字符串"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _bold(s: str) -> str:
    """简易粗体（兼容终端和 agent 输出）"""
    return f"**{s}**"


def _header(title: str) -> str:
    return f"\n─── {title} {'─' * max(0, 48 - len(title))}"


def _entry(emoji: str, label: str, value: str = "") -> str:
    if value:
        return f"{emoji} {label}: {value}"
    return f"{emoji} {label}"


# ── Subcommands ─────────────────────────────────────────────────────────────

@app.command()
def fetch() -> None:
    """🔄 git fetch 远程"""
    src = _source_path()
    os.chdir(src)

    r = _chz_git("fetch", "origin")
    if r.returncode != 0:
        typer.secho(f"❌ fetch 失败:\n{r.stderr}", err=True, fg=typer.colors.RED)
        raise typer.Exit(EXIT_ERROR)

    # 检查远程是否有新提交
    r_new = _chz_git("log", "--oneline", "HEAD..origin/main")
    ahead = _chz_git("log", "--oneline", "origin/main..HEAD")
    new_count = len(r_new.stdout.strip().split("\n")) if r_new.stdout.strip() else 0
    ahead_count = len(ahead.stdout.strip().split("\n")) if ahead.stdout.strip() else 0

    print(_header("远程状态"))
    print(_entry("", "HEAD", _chz_git("rev-parse", "--short", "HEAD").stdout.strip()))
    print(_entry("", "origin/main", _chz_git("rev-parse", "--short", "origin/main").stdout.strip()))

    if new_count > 0:
        print(f"\n⬇️  远程有 {new_count} 个新提交:")
        for line in r_new.stdout.strip().split("\n"):
            print(f"   {line}")
    else:
        print(_entry("✅", "远程无新提交"))

    if ahead_count > 0:
        print(f"\n⬆️  本地有 {ahead_count} 个待推送:")
        for line in ahead.stdout.strip().split("\n"):
            print(f"   {line}")
    else:
        print(_entry("✅", "本地无待推送"))

    # 输出结构化标记供 agent 解析
    print(f"\n__new_remote={new_count}")
    print(f"__ahead_local={ahead_count}")


@app.command()
def pull() -> None:
    """⬇️  git pull —autostash —rebase，含冲突处理"""
    src = _source_path()
    os.chdir(src)

    print(_header("拉取远程变更"))
    r = _chz_git("pull", "--autostash", "--rebase", check=False)
    if r.returncode == 0:
        print(_entry("✅", "拉取成功"))
        print("\n__pull_ok=1")
        return

    # ── 冲突处理 ────────────────────────────────────────────────────────
    typer.secho("⚠️  拉取冲突，进入分析...", err=True, fg=typer.colors.YELLOW)

    # 找出冲突文件
    conflicts_r = _chz_git("diff", "--name-only", "--diff-filter=U")
    conflicted = [f for f in conflicts_r.stdout.strip().split("\n") if f]

    if not conflicted:
        typer.secho("  未检测到冲突文件，可能是 rebase 失败的其他原因", err=True)
        print(f"\n__pull_ok=0")
        print(f"__pull_error={r.stderr.strip()}")
        return

    print(f"🔍 {len(conflicted)} 个冲突文件:")
    auto_resolved = []
    needs_user = []

    for fp in conflicted:
        fpath = Path(fp)
        print(f"\n  📄 {fp}")
        if not fpath.exists():
            print("     ⏭️  文件已删除，需用户确认")
            needs_user.append(fp)
            continue

        # 收集时间戳
        local_mtime = fpath.stat().st_mtime
        local_mtime_hr = _fmt_dt(int(local_mtime))
        print(f"     mtime: {local_mtime_hr}")

        # 冲突块预览
        conflict_text = fpath.read_text()
        for line in conflict_text.split("\n"):
            if line.startswith("<<<<<<<") or line.startswith("=======") or line.startswith(">>>>>>>"):
                print(f"     {line[:60]}")

        # 启发式判断
        local_commit_r = _chz_git("log", "-1", "--format=%ct", "HEAD", "--", fp)
        remote_commit_r = _chz_git("log", "-1", "--format=%ct", "origin/main", "--", fp)
        local_commit_ts = int(local_commit_r.stdout.strip() or "0")
        remote_commit_ts = int(remote_commit_r.stdout.strip() or "0")
        now = int(time.time())
        days_since_local = (now - local_commit_ts) // 86400 if local_commit_ts > 0 else 999

        print(f"     本地提交: {_fmt_dt(local_commit_ts) if local_commit_ts > 0 else 'N/A'}")
        print(f"     远程提交: {_fmt_dt(remote_commit_ts) if remote_commit_ts > 0 else 'N/A'}")

        if remote_commit_ts > local_commit_ts and days_since_local > 7:
            print("     ✅ 远程变更显著更新，采用远程")
            _chz_git("checkout", "--theirs", "--", fp)
            _chz_git("add", fp)
            auto_resolved.append(f"✅ {fp} (远程)")
        elif local_commit_ts >= remote_commit_ts and days_since_local < 1:
            print("     ✅ 本地刚刚变更，采用本地")
            _chz_git("checkout", "--ours", "--", fp)
            _chz_git("add", fp)
            auto_resolved.append(f"✅ {fp} (本地)")
        else:
            print("     🤔 需要用户裁决")
            needs_user.append(fp)

    if auto_resolved:
        print(f"\n🟢 自动解决:")
        for item in auto_resolved:
            print(f"  {item}")

    if needs_user:
        print(f"\n🟡 需用户裁决 ({len(needs_user)}):")
        for f in needs_user:
            print(f"  {f}")
        print(f"\n__needs_user={' '.join(needs_user)}")

    # 检查是否所有冲突已解决，继续 rebase
    remaining = _chz_git("diff", "--name-only", "--diff-filter=U")
    if not remaining.stdout.strip():
        _chz_git("rebase", "--continue", check=False)
        print(_entry("✅", "冲突解决，拉取完成"))
        print("\n__pull_ok=1")
    else:
        print("\n__pull_ok=0")


@app.command()
def status() -> None:
    """📊 双层级状态检测：git status + chezmoi status"""
    src = _source_path()
    os.chdir(src)

    print(_header("层 1：源仓库 git 状态"))
    git_st = _chz_git("status", "--porcelain")
    git_changes = [l for l in git_st.stdout.strip().split("\n") if l.strip()]

    if git_changes:
        print(f"📝 {len(git_changes)} 个文件待提交:")
        for line in git_changes:
            print(f"  {line}")
        # 详细统计
        diff_st = _chz_git("diff", "--stat")
        if diff_st.stdout.strip():
            print(f"\n  {diff_st.stdout.strip()}")
    else:
        print(_entry("✅", "源仓库无未提交变更"))

    print(_header("层 2：chezmoi 状态（源 vs home 差异）"))
    chz_st = _chz("status")
    chz_lines = [l for l in chz_st.stdout.strip().split("\n") if l.strip()]

    if chz_lines:
        print(f"📝 {len(chz_lines)} 个文件有差异:")
        for line in chz_lines:
            print(f"  {line}")
    else:
        print(_entry("✅", "源与 home 一致，无差异"))

    # 汇总标记供 agent 解析
    has_git = 1 if git_changes else 0
    has_chz = 1 if chz_lines else 0
    print(f"\n__has_git_changes={has_git}")
    print(f"__has_chezmoi_changes={has_chz}")

    if has_git or has_chz:
        raise typer.Exit(EXIT_HAS_CHANGES)


@app.command()
def diff() -> None:
    """📋 展示 chezmoi diff 摘要（源 vs home）"""
    r = _chz("diff")
    if not r.stdout.strip():
        print(_entry("✅", "源与 home 完全一致"))
        return

    lines = r.stdout.strip().split("\n")
    print(_header("chezmoi diff（源 → home）"))

    # 提取文件级变更摘要
    files = {}
    current_file = None
    for line in lines:
        if line.startswith("diff --git a/"):
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else parts[0]
            files[current_file] = {"add": 0, "del": 0, "mode": ""}
        elif line.startswith("old mode"):
            if current_file:
                files[current_file]["mode"] = f"{line.split()[-1]} → "
        elif line.startswith("new mode"):
            if current_file:
                files[current_file]["mode"] += line.split()[-1]
        elif line.startswith("@@") and current_file:
            # 统计增减行
            pass
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            files[current_file]["add"] += 1
        elif line.startswith("-") and not line.startswith("---") and current_file:
            files[current_file]["del"] += 1

    for fp, info in files.items():
        mode_info = f" (权限: {info['mode']})" if info["mode"] else ""
        print(f"\n  📄 {fp}{mode_info}")
        print(f"     +{info['add']}/-{info['del']} 行")

    # 展示详细 diff（截取前 60 行避免过长）
    print(_header("diff 详情"))
    for line in lines[:60]:
        if line.startswith("+") and not line.startswith("+++"):
            typer.secho(f"  {line}", fg=typer.colors.GREEN)
        elif line.startswith("-") and not line.startswith("---"):
            typer.secho(f"  {line}", fg=typer.colors.RED)
        else:
            print(f"  {line}")

    if len(lines) > 60:
        print(f"  ... 共 {len(lines)} 行，截取前 60 行")

    print(f"\n__diff_files={len(files)}")


@app.command()
def re_add(
    paths: Optional[list[str]] = typer.Argument(
        None,
        help="要 re-add 的文件路径（chezmoi 目标路径，如 .config/rpiv-pi/models.json）。默认所有有差异的文件",
    ),
    direction: Optional[str] = typer.Option(
        None,
        "--direction", "-d",
        help="强制指定方向: home（home→源，即 re-add）/ source（源→home，即 apply）",
    ),
) -> None:
    """📥 智能 re-add：检测差异、比较时间戳、自动或标记需确认"""
    src = _source_path()
    os.chdir(src)

    # 获取 chezmoi status
    st_r = _chz("status")
    status_lines = [l for l in st_r.stdout.strip().split("\n") if l.strip()]

    if not status_lines:
        print(_entry("✅", "无差异，无需 re-add"))
        print("__re_add_count=0")
        return

    # 解析目标文件
    targets = []
    for line in status_lines:
        # 格式: "MM .config/xxx/yyy.json"
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            fp = parts[1]
            if paths:
                if fp in paths:
                    targets.append(fp)
            else:
                targets.append(fp)

    if not targets:
        print(_entry("✅", "未匹配到目标文件"))
        print("__re_add_count=0")
        return

    auto_re_add = []
    needs_decision = []
    applied = []

    for fp in targets:
        print(f"\n  📄 {fp}")
        home_path = Path.home() / fp
        if not home_path.exists():
            print("     ⏭️  home 文件不存在，跳过")
            continue

        # home 文件 mtime
        home_mtime = home_path.stat().st_mtime

        # 源仓库中该文件的最近提交时间
        commit_r = _chz_git("log", "-1", "--format=%ct", "HEAD", "--", f"dot_{fp.replace('/', '/')}")
        # 试一下可能的源路径变体
        src_path_variants = [
            f"dot_{fp.replace('/', '/')}",
            f"dot_{fp.rsplit('/', 1)[0] if '/' in fp else ''}/private_{fp.rsplit('/', 1)[-1] if '/' in fp else f'private_{fp}'}",
        ]

        source_commit_ts = 0
        for sp in src_path_variants[:1]:  # 先用标准路径
            cr = _chz_git("log", "-1", "--format=%ct", "HEAD", "--", sp)
            if cr.stdout.strip():
                source_commit_ts = int(cr.stdout.strip())
                break

        # 如果没找到源路径，在 git ls-files 中查找
        if source_commit_ts == 0:
            ls_r = _chz_git("ls-files", "--", f"*{fp.split('/')[-1]}")
            matched = [l for l in ls_r.stdout.strip().split("\n") if l]
            if matched:
                cr = _chz_git("log", "-1", "--format=%ct", "HEAD", "--", matched[0])
                if cr.stdout.strip():
                    source_commit_ts = int(cr.stdout.strip())

        home_mtime_hr = _fmt_dt(int(home_mtime))
        source_ts_hr = _fmt_dt(source_commit_ts) if source_commit_ts > 0 else "N/A"

        print(f"     home mtime:    {home_mtime_hr}")
        print(f"     源仓库提交:    {source_ts_hr}")

        if direction == "home":
            # 强制 re-add
            r = _chz("re-add", str(home_path))
            if r.returncode == 0:
                auto_re_add.append(fp)
                print(f"     ✅ re-add 完成（强制）")
            else:
                print(f"     ❌ re-add 失败: {r.stderr.strip()}")
        elif direction == "source":
            # 强制 apply
            r = _chz("apply")
            if r.returncode == 0:
                applied.append(fp)
                print(f"     ⚠️  apply 完成（强制 — 源覆盖 home）")
            else:
                print(f"     ❌ apply 失败: {r.stderr.strip()}")
        elif source_commit_ts == 0:
            # 源无历史 → 新文件，安全方向 re-add
            r = _chz("re-add", str(home_path))
            if r.returncode == 0:
                auto_re_add.append(fp)
                print(f"     ✅ re-add 完成（新文件，自动）")
            else:
                print(f"     ❌ re-add 失败: {r.stderr.strip()}")
        elif home_mtime > source_commit_ts:
            # home 更新 → re-add
            r = _chz("re-add", str(home_path))
            if r.returncode == 0:
                auto_re_add.append(fp)
                print(f"     ✅ re-add 完成（home 更新）")
            else:
                print(f"     ❌ re-add 失败: {r.stderr.strip()}")
        else:
            # 源更新 → 需要决策
            needs_decision.append(fp)
            print(f"     🤔 源比 home 新，需确认方向")
            print(f"     选项: apply（源→home）| re-add（home→源）")

    # 报告
    if auto_re_add:
        print(f"\n🟢 自动 re-add ({len(auto_re_add)}):")
        for f in auto_re_add:
            print(f"  ✅ {f}")

    if applied:
        print(f"\n⚠️  apply ({len(applied)}):")
        for f in applied:
            print(f"  ⚠️  {f}")

    if needs_decision:
        print(f"\n🟡 需决策 ({len(needs_decision)}):")
        for f in needs_decision:
            print(f"  🤔 {f}")
        print("\n  请在 SKILL.md 流程中询问用户：apply（源→home）还是 re-add（home→源）？")

    print(f"\n__re_add_done={len(auto_re_add)}")
    print(f"__applied={len(applied)}")
    print(f"__needs_decision={' '.join(needs_decision)}")

    if needs_decision and not direction:
        raise typer.Exit(EXIT_HAS_CHANGES)


@app.command()
def commit(
    msg: Optional[str] = typer.Option(None, "--message", "-m", help="自定义提交信息"),
) -> None:
    """📝 add + commit，自动生成提交信息"""
    src = _source_path()
    os.chdir(src)

    # add all
    _chz_git("add", "-A", check=False)

    # 检查是否有变更
    st = _chz_git("status", "--porcelain")
    if not st.stdout.strip():
        print(_entry("✅", "无变更需提交"))
        print("__committed=0")
        return

    # 生成提交信息
    if msg:
        commit_msg = msg
    else:
        changed_files = _chz_git("diff", "--cached", "--name-only")
        files = [f for f in changed_files.stdout.strip().split("\n") if f]
        if len(files) > 20:
            commit_msg = f"sync: 更新 {len(files)} 个 dotfiles"
        else:
            commit_msg = f"sync: {' '.join(files)}"

    print(_header("提交"))
    print(f"  信息: {commit_msg}")
    print(f"  文件 ({len(files) if not msg else '?'}):")
    if not msg:
        for f in files:
            print(f"    {f}")

    typer.confirm("  确认提交？", default=True, abort=True)

    r = _chz_git("commit", "-m", commit_msg)
    if r.returncode == 0:
        print(_entry("✅", f"提交成功: {commit_msg}"))
        print(f"\n__committed=1")
        print(f"__commit_msg={commit_msg}")
    else:
        typer.secho(f"❌ 提交失败:\n{r.stderr}", err=True, fg=typer.colors.RED)
        print(f"\n__committed=0")
        print(f"__commit_error={r.stderr.strip()}")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def push() -> None:
    """⬆️  git push"""
    src = _source_path()
    os.chdir(src)

    print(_header("推送"))
    r = _chz_git("push", "origin", "main")
    if r.returncode == 0:
        print(_entry("✅", "推送成功"))
        print("__pushed=1")
    else:
        typer.secho(f"❌ 推送失败:\n{r.stderr}", err=True, fg=typer.colors.RED)
        if "rejected" in r.stderr:
            print("  提示: 远程有更新，先拉再推")
        print("\n__pushed=0")
        raise typer.Exit(EXIT_ERROR)


@app.command()
def verify() -> None:
    """🔍 最终状态验证：确认本地 ↔ 远程一致"""
    src = _source_path()
    os.chdir(src)

    print(_header("同步完成"))
    head = _chz_git("rev-parse", "--short", "HEAD").stdout.strip()
    origin = _chz_git("rev-parse", "--short", "origin/main").stdout.strip()

    print(f"  HEAD:      {head}")
    print(f"  origin/main: {origin}")

    if head == origin:
        print(_entry("✅", "本地 ↔ 远程 一致"))
        print("__synced=1")
    else:
        print(_entry("⚠️", "本地与远程不同步"))
        print("__synced=0")

    print(_header("最近提交"))
    log_r = _chz_git("log", "--oneline", "-5")
    for line in log_r.stdout.strip().split("\n"):
        print(f"  {line}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
