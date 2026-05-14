---
name: arch-wsl-cleanup
description: >-
  Free up disk space on Arch Linux WSL through layered cleanup: cache purge,
  orphan removal, package audit, and large file scanning. Use whenever the
  user mentions disk space, cleanup, storage, package review, or wants to
  shrink their WSL footprint — even if they just say "空间不够", "磁盘满了",
  "WSL 太大了", or "clean up my system". Prefer this skill over ad-hoc
  cleanup commands on Arch WSL.
---

# Arch WSL Disk Cleanup

Guide systematic disk space cleanup on Arch Linux WSL systems.
Follow a layered approach: start with safe cache cleanup, then review
installed packages, then scan for large files and directories.

## Pre-flight Checks

1. Confirm the environment is Arch Linux: `head -3 /etc/os-release`
2. Check if running in WSL: `grep -qi microsoft /proc/version`
3. Check current disk usage: `df -h /`
4. Identify available package managers: `which pacman yay paru 2>/dev/null`

**Record baseline** for the final report — save the output of `df -h /` and:
```bash
du -sh /var/cache/pacman/pkg/ ~/.cache/ 2>/dev/null
```

## Phase 1: Safe Cleanup (zero risk, execute directly)

Only delete caches and orphaned packages — no installed software is affected.

### 1.1 Package manager caches

```bash
# pacman package cache (keep current installed versions)
sudo pacman -Sc --noconfirm

# AUR build cache — use whichever helper is installed
yay -Sc --noconfirm 2>/dev/null || paru -Sc --noconfirm 2>/dev/null

# For aggressive cleanup (clear ALL cache including current versions):
# sudo pacman -Scc --noconfirm
```

### 1.2 Orphaned dependencies

```bash
# List orphans (no package depends on them)
pacman -Qdtq

# Remove them (guard against empty list)
orphans=$(pacman -Qdtq)
[ -n "$orphans" ] && sudo pacman -Rns --noconfirm $orphans || echo "无孤儿包"
```

### 1.3 Language package manager caches

Run whichever tools the user has installed:

```bash
# Python - uv
uv cache clean

# Python - pip
pip cache purge

# Node.js - npm
npm cache clean --force

# Node.js - bun
bun pm cache rm 2>/dev/null || rm -rf ~/.bun/install/cache/

# Rust - cargo
cargo cache --cleanup
# Or directly: rm -rf ~/.cargo/registry/cache ~/.cargo/registry/index
```

### 1.4 System logs

```bash
# Compress journalctl to 50M
sudo journalctl --vacuum-size=50M

# Delete old rotated logs
sudo find /var/log -type f \( -name "*.gz" -o -name "*.[0-9]" -o -name "*.old" \) -delete
```

## Phase 2: Package Review (requires user confirmation)

### 2.1 Package statistics

```bash
echo "总包数: $(pacman -Qq | wc -l)"
echo "手动安装: $(pacman -Qe | wc -l)"
echo "AUR/外来包: $(pacman -Qm | wc -l)"

# Total installed size (script path is relative to this skill directory)
uv run --script scripts/calc_package_size.py
```

### 2.2 List manually installed packages

```bash
LC_ALL=C pacman -Qei | awk '
  /^Name/{name=$3}
  /^Installed Size/{
    val=$4; unit=$5
    if (unit=="GiB") mib=val*1024
    else if (unit=="KiB") mib=val/1024
    else mib=val
    printf "%.0f MiB | %s\n", mib, name
  }
' | sort -t'|' -k1 -rn
```

Present results as a sorted table. **Never auto-delete packages** — always ask the user to confirm which ones to remove.

## Phase 3: Full Disk Scan

### 3.1 Top-level directory scan

```bash
# Use -x to stay on the current filesystem (critical on WSL!)
du -hx --max-depth=1 / 2>/dev/null | sort -rh | head -20
```

**Critical**: Always use `du -x` — without it, WSL will traverse mounted Windows partitions (`/mnt/c`, etc.) and report inflated sizes.

### 3.2 User directory deep scan

```bash
# Largest directories under $HOME
du -hx --max-depth=2 "$HOME" 2>/dev/null | sort -rh | head -30

# Recurse into common subdirectories (skip if they don't exist)
for dir in "$HOME/.cache" "$HOME/code" "$HOME/github"; do
  [ -d "$dir" ] && du -hx --max-depth=2 "$dir" 2>/dev/null | sort -rh | head -15
done
```

### 3.3 Large file search

```bash
# System-wide files larger than 50MB
find /usr /opt /var -type f -size +50M -exec du -sh {} + 2>/dev/null | sort -rh | head -20
```

## Phase 4: Targeted Cleanup

### Safe to delete directly

| Pattern | Examples |
|---|---|
| `~/.cache/<tool>/` | Playwright, camoufox, huggingface, go-build, jedi, node-gyp, telemetry caches |
| `**/build/` | Compilation output directories |
| `**/node_modules/` | Reinstallable via package manager |
| `**/.venv/` | Rebuildable with uv/venv |

### Require user confirmation

- Manually installed packages from Phase 2
- `~/service/`, `~/software/`, or similar user-stored directories
- Project code directories
- AI tool data directories (e.g., `.genericagent/`)

### Use commands for specific targets

```bash
# Go caches
go clean -cache -modcache

# Direct directory deletion
rm -rf <target-directory>
```

## Phase 5: WSL VHDX Compaction (manual — guide the user)

After cleanup inside WSL, the virtual disk file (ext4.vhdx) on Windows does not
shrink automatically. The user must perform these steps **manually** outside WSL.

Walk the user through:

1. **TRIM the filesystem** (run inside WSL):
   ```bash
   sudo fstrim -v /
   ```

2. **Shut down WSL** (run in Windows PowerShell):
   ```powershell
   wsl --shutdown
   ```

3. **Compact the VHDX** — choose one method (run in Windows PowerShell as Administrator):

   **Option A: diskpart**
   ```powershell
   diskpart
   # In diskpart:
   select vdisk file="C:\Users\<username>\AppData\Local\Packages\...\LocalState\ext4.vhdx"
   compact vdisk
   exit
   ```

   **Option B: Hyper-V PowerShell cmdlet**
   ```powershell
   Optimize-VHD -Path "C:\Users\<username>\AppData\Local\Packages\...\LocalState\ext4.vhdx" -Mode Full
   ```

   The exact VHDX path depends on the WSL distribution — help the user locate it.

## Post-cleanup Verification

```bash
# Check disk usage again
df -h /

# Show remaining cache sizes
du -sh /var/cache/pacman/pkg/ ~/.cache/yay/ 2>/dev/null
```

## Reporting Format

Report results to the user as a table (use the baseline recorded in Pre-flight):

| Item | Before | After | Freed |
|---|---|---|---|
| pacman cache | X GiB | Y GiB | Z GiB |

End with a total freed amount summary.

## Safety Rules

1. **Never auto-delete packages** — always require user confirmation
2. **Never touch `/mnt/`** — those are Windows partitions
3. **Always use `du -x`** — prevents counting mounted filesystems
4. **rm -rf path blacklist** — never rm -rf system directories: `/`, `/home`, `/etc`, `/usr`, `/var`, `/boot`, `/opt`, `/srv`, `/root`. Only delete their subdirectories (e.g. `~/.cache/playwright`).
5. **Handle permissions** — some operations need sudo, some (like bun cache) may need `rm -rf` instead of CLI commands
