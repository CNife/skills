#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["json-five"]
# ///
"""管理 OpenCode 的 permission 权限规则（保留 JSONC 注释）。

功能：
  - add: 添加单条或多条规则，自动备份 + 格式化
  - remove: 删除规则，自动备份 + 格式化
  - list: 列出 permission.bash 规则
  - list-all: 列出所有 permission 类别
  - format: 格式化 bash 规则（一行一条），不做增删
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import json5
from json5.dumper import ModelDumper
from json5.loader import ModelLoader, loads
from json5.model import DoubleQuotedString, JSONObject

DEFAULT_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
ACTIONS = ("allow", "ask", "deny")


# ─── 格式化 ───────────────────────────────────────────────────

def format_bash_section(text: str) -> str:
    """确保 permission.bash 中每条规则独占一行。

    检测 bash 段内同一行含多条 "key": "value" 的情况并拆分。
    仅在 bash 段内生效，不影响其他 JSON 对象。
    """
    lines = text.split("\n")

    # 定位 bash 段边界
    in_bash = False
    depth = 0
    bash_start = None
    bash_end = None

    for i, line in enumerate(lines):
        if not in_bash:
            if re.search(r'"bash"\s*:', line):
                in_bash = True
                bash_start = i
                depth += line.count("{") - line.count("}")
        else:
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                bash_end = i
                break

    if bash_start is None or bash_end is None:
        return text

    # 拆分 bash 段内单行多条规则
    result = []
    for i, line in enumerate(lines):
        if bash_start < i < bash_end:
            pairs = list(re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', line))
            if len(pairs) > 1:
                leading = line[: pairs[0].start()]
                for j, m in enumerate(pairs):
                    k, v = m.group(1), m.group(2)
                    comma = "," if j < len(pairs) - 1 or i == bash_end - 1 else ""
                    result.append(f'{leading}"{k}": "{v}"{comma}')
                continue
        result.append(line)

    return "\n".join(result)


# ─── 备份 ─────────────────────────────────────────────────────

def backup_config(path: Path) -> Path | None:
    """创建带时间戳的备份文件。"""
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = path.with_suffix(f".jsonc.{ts}.bak")
    backup.write_text(path.read_text("utf-8"), "utf-8")
    return backup


# ─── JSON 模型操作 ─────────────────────────────────────────────

def load_model(path: Path):
    """加载 JSONC 文件为可编辑的模型树（保留所有注释）。"""
    if not path.exists():
        print(f"配置文件不存在: {path}")
        sys.exit(1)
    return loads(path.read_text("utf-8"), loader=ModelLoader())


def _ensure_section(root: JSONObject, key_name: str) -> int:
    """在 JSONObject 中查找键索引，缺失时创建空 JSONObject。"""
    for i, key in enumerate(root.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == key_name:
            return i
    obj = JSONObject(keys=[], values=[])
    root.keys.append(DoubleQuotedString(characters=key_name, raw_value=f'"{key_name}"'))
    root.values.append(obj)
    return len(root.keys) - 1


def find_bash_obj(model) -> JSONObject:
    """导航到 permission.bash 对象，缺失时自动创建。"""
    root = model.value
    if not isinstance(root, JSONObject):
        print("配置文件根节点不是 JSON 对象")
        sys.exit(1)

    perm_idx = _ensure_section(root, "permission")
    perm_obj = root.values[perm_idx]
    if not isinstance(perm_obj, JSONObject):
        print("permission 段不是 JSON 对象")
        sys.exit(1)

    bash_idx = _ensure_section(perm_obj, "bash")
    bash_obj = perm_obj.values[bash_idx]
    if not isinstance(bash_obj, JSONObject):
        print("permission.bash 段不是 JSON 对象")
        sys.exit(1)

    # 新创建的 bash 段加兜底规则
    if not bash_obj.keys:
        bash_obj.keys.append(DoubleQuotedString(characters="*", raw_value='"*"'))
        bash_obj.values.append(DoubleQuotedString(characters="ask", raw_value='"ask"'))

    return bash_obj


def find_rule_index(bash_obj: JSONObject, rule: str) -> int | None:
    """在 bash 对象中查找规则的索引。"""
    for i, key in enumerate(bash_obj.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == rule:
            return i
    return None


def _write_and_format(config_path: Path, model):
    """序列化模型 → 格式化 → 写入文件。"""
    raw = json5.dumps(model, dumper=ModelDumper())
    formatted = format_bash_section(raw)
    config_path.write_text(formatted, "utf-8")


# ─── 命令实现 ─────────────────────────────────────────────────

def cmd_add(args):
    """添加单条或多条权限规则。"""
    backup_config(args.config)
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    added = 0
    skipped = 0
    for rule in args.rules:
        if find_rule_index(bash_obj, rule) is not None:
            print(f"规则已存在: {rule} → {args.action}")
            skipped += 1
            continue
        bash_obj.keys.append(
            DoubleQuotedString(characters=rule, raw_value=f'"{rule}"')
        )
        bash_obj.values.append(
            DoubleQuotedString(characters=args.action, raw_value=f'"{args.action}"')
        )
        added += 1

    _write_and_format(args.config, model)

    if added:
        print(f"已添加 {added} 条规则 → {args.action}")
    print(f"注意: 修改配置后需要重启 OpenCode 才能生效。")


def cmd_remove(args):
    """删除权限规则。"""
    backup_config(args.config)
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    idx = find_rule_index(bash_obj, args.rule)
    if idx is None:
        print(f"规则不存在: {args.rule}")
        return

    del bash_obj.keys[idx]
    del bash_obj.values[idx]

    _write_and_format(args.config, model)
    print(f"已删除: {args.rule}")
    print(f"注意: 修改配置后需要重启 OpenCode 才能生效。")


def cmd_list(args):
    """列出 permission.bash 规则。"""
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    if not bash_obj.keys:
        print("permission.bash 为空")
        return

    print(f"配置文件: {args.config}")
    print(f"{'规则':<45} {'动作':<10}")
    print("-" * 57)
    for key, val in zip(bash_obj.keys, bash_obj.values):
        rule = key.characters if isinstance(key, DoubleQuotedString) else str(key)
        action = val.characters if isinstance(val, DoubleQuotedString) else str(val)
        print(f"{rule:<45} {action:<10}")


def cmd_list_all(args):
    """列出所有 permission 规则。"""
    model = load_model(args.config)
    root = model.value
    if not isinstance(root, JSONObject):
        print(f"配置文件根节点不是 JSON 对象")
        sys.exit(1)

    perm_idx = None
    for i, key in enumerate(root.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == "permission":
            perm_idx = i
            break

    if perm_idx is None:
        print("未配置 permission 段")
        return

    perm_obj = root.values[perm_idx]
    if not isinstance(perm_obj, JSONObject):
        print(f"permission: {perm_obj}")
        return

    print(f"配置文件: {args.config}")
    for key, val in zip(perm_obj.keys, perm_obj.values):
        tool_name = key.characters if isinstance(key, DoubleQuotedString) else str(key)
        if isinstance(val, DoubleQuotedString):
            print(f"  {tool_name}: {val.characters}")
        elif isinstance(val, JSONObject):
            print(f"  {tool_name}:")
            for k, v in zip(val.keys, val.values):
                rule = k.characters if isinstance(k, DoubleQuotedString) else str(k)
                action = v.characters if isinstance(v, DoubleQuotedString) else str(v)
                print(f"    {rule}: {action}")


def cmd_format(args):
    """格式化 bash 规则（一行一条），不做增删。"""
    if not args.config.exists():
        print(f"配置文件不存在: {args.config}")
        sys.exit(1)

    backup_config(args.config)
    text = args.config.read_text("utf-8")
    formatted = format_bash_section(text)
    args.config.write_text(formatted, "utf-8")
    print(f"已格式化: {args.config}")
    print(f"注意: 修改配置后需要重启 OpenCode 才能生效。")


# ─── 入口 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="管理 OpenCode permission 规则")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add（支持多规则）
    add_p = subparsers.add_parser("add", help="添加权限规则（支持多条）")
    add_p.add_argument("rules", nargs="+", help='规则模式，如 "kubectl get *" "kubectl describe *"')
    add_p.add_argument("--action", choices=ACTIONS, default="allow", help="权限动作（默认: allow）")
    add_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="配置文件路径")
    add_p.set_defaults(func=cmd_add)

    # remove
    rm_p = subparsers.add_parser("remove", help="删除权限规则")
    rm_p.add_argument("rule", help="要删除的规则模式")
    rm_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="配置文件路径")
    rm_p.set_defaults(func=cmd_remove)

    # list
    ls_p = subparsers.add_parser("list", help="列出 permission.bash 规则")
    ls_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="配置文件路径")
    ls_p.set_defaults(func=cmd_list)

    # list-all
    la_p = subparsers.add_parser("list-all", help="列出所有 permission 规则")
    la_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="配置文件路径")
    la_p.set_defaults(func=cmd_list_all)

    # format
    fmt_p = subparsers.add_parser("format", help="格式化 bash 规则（一行一条，自动备份）")
    fmt_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="配置文件路径")
    fmt_p.set_defaults(func=cmd_format)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
