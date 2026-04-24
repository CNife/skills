#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Add/modify permission rules in Qwen Code's settings.json."""

import argparse
import json
import sys
from pathlib import Path

ACTIONS = ("allow", "ask", "deny")
DEFAULT_CONFIG = Path.home() / ".qwen" / "settings.json"


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"Config not found: {path}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_rule(config: dict, rule: str, action: str) -> tuple[dict, bool]:
    """Add a rule to config. Returns (updated_config, was_new)."""
    permissions = config.setdefault("permissions", {})
    rules_list = permissions.setdefault(action, [])

    if rule in rules_list:
        return config, False

    rules_list.append(rule)
    return config, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Add permission rule to Qwen Code settings.json")
    parser.add_argument("rule", help='Rule string, e.g. "Bash(git *)"')
    parser.add_argument(
        "--action", choices=ACTIONS, default="allow", help="Permission action (default: allow)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to settings.json (default: ~/.qwen/settings.json)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    config, was_new = add_rule(config, args.rule, args.action)

    if not was_new:
        print(f"Rule already exists: {args.rule} → {args.action}")
        return

    save_config(args.config, config)

    permissions = config["permissions"][args.action]
    print(f"Added rule: {args.rule} → {args.action}")
    print(f"Current {args.action} rules: {json.dumps(permissions, ensure_ascii=False)}")
    print("\nNote: Restart Qwen Code (/exit then re-launch) for changes to take effect.")


if __name__ == "__main__":
    main()
