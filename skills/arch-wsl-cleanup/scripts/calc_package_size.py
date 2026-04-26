#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Calculate total installed package size on Arch Linux."""
import subprocess

UNIT_TO_MIB = {"B": 1 / (1024 * 1024), "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}

out = subprocess.run(["pacman", "-Qi"], capture_output=True, text=True, check=True)
total_mib = 0
for line in out.stdout.split("\n"):
    if line.startswith("Installed Size"):
        parts = line.split(":")[-1].strip().split()
        val, unit = float(parts[0]), parts[1]
        total_mib += val * UNIT_TO_MIB.get(unit, 1)
print(f"总安装大小: {total_mib / 1024:.2f} GiB ({total_mib:.0f} MiB)")
