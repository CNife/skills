#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["json-five"]
# ///
"""管理 OpenCode 的 permission.bash 权限规则（保留 JSONC 注释）。"""

import argparse
import sys
from pathlib import Path

import json5
from json5.dumper import ModelDumper
from json5.loader import ModelLoader, loads
from json5.model import DoubleQuotedString, JSONObject

DEFAULT_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
ACTIONS = ("allow", "ask", "deny")


def load_model(path: Path):
    """加载 JSONC 文件为可编辑的模型树（保留所有注释）。"""
    if not path.exists():
        print(f"配置文件不存在: {path}")
        sys.exit(1)
    content = path.read_text(encoding="utf-8")
    return loads(content, loader=ModelLoader())


def find_bash_obj(model) -> JSONObject:
    """导航到 permission.bash 对象，缺失时自动创建。"""
    root = model.value
    if not isinstance(root, JSONObject):
        print("配置文件根节点不是 JSON 对象")
        sys.exit(1)

    # 找 permission 键
    perm_idx = None
    for i, key in enumerate(root.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == "permission":
            perm_idx = i
            break

    if perm_idx is None:
        # 创建 permission 段
        perm_obj = JSONObject(keys=[], values=[])
        root.keys.append(DoubleQuotedString(characters="permission", raw_value='"permission"'))
        root.values.append(perm_obj)
        perm_idx = len(root.keys) - 1

    perm_obj = root.values[perm_idx]
    if not isinstance(perm_obj, JSONObject):
        print("permission 段不是 JSON 对象")
        sys.exit(1)

    # 找 bash 键
    bash_idx = None
    for i, key in enumerate(perm_obj.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == "bash":
            bash_idx = i
            break

    if bash_idx is None:
        # 创建 bash 段，设兜底规则
        bash_obj = JSONObject(keys=[], values=[])
        bash_obj.keys.append(DoubleQuotedString(characters="*", raw_value='"*"'))
        bash_obj.values.append(DoubleQuotedString(characters="ask", raw_value='"ask"'))
        perm_obj.keys.append(DoubleQuotedString(characters="bash", raw_value='"bash"'))
        perm_obj.values.append(bash_obj)
        bash_idx = len(perm_obj.keys) - 1

    bash_obj = perm_obj.values[bash_idx]
    if not isinstance(bash_obj, JSONObject):
        print("permission.bash 段不是 JSON 对象")
        sys.exit(1)

    return bash_obj


def find_rule_index(bash_obj: JSONObject, rule: str) -> int | None:
    """在 bash 对象中查找规则的索引。"""
    for i, key in enumerate(bash_obj.keys):
        if isinstance(key, DoubleQuotedString) and key.characters == rule:
            return i
    return None


def cmd_add(args):
    """添加权限规则。"""
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    if find_rule_index(bash_obj, args.rule) is not None:
        print(f"规则已存在: {args.rule} → {args.action}")
        return

    bash_obj.keys.append(DoubleQuotedString(characters=args.rule, raw_value=f'"{args.rule}"'))
    bash_obj.values.append(DoubleQuotedString(characters=args.action, raw_value=f'"{args.action}"'))

    args.config.write_text(json5.dumps(model, dumper=ModelDumper()), encoding="utf-8")
    print(f"已添加: {args.rule} → {args.action}")
    print(f"\n注意: 修改配置后需要重启 OpenCode 才能生效。")


def cmd_remove(args):
    """删除权限规则。"""
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    idx = find_rule_index(bash_obj, args.rule)
    if idx is None:
        print(f"规则不存在: {args.rule}")
        return

    del bash_obj.keys[idx]
    del bash_obj.values[idx]

    args.config.write_text(json5.dumps(model, dumper=ModelDumper()), encoding="utf-8")
    print(f"已删除: {args.rule}")
    print(f"\n注意: 修改配置后需要重启 OpenCode 才能生效。")


def cmd_list(args):
    """列出 permission.bash 规则。"""
    model = load_model(args.config)
    bash_obj = find_bash_obj(model)

    if not bash_obj.keys:
        print("permission.bash 为空")
        return

    print(f"配置文件: {args.config}")
    print(f"{'规则':<40} {'动作':<10}")
    print("-" * 52)
    for key, val in zip(bash_obj.keys, bash_obj.values):
        rule = key.characters if isinstance(key, DoubleQuotedString) else str(key)
        action = val.characters if isinstance(val, DoubleQuotedString) else str(val)
        print(f"{rule:<40} {action:<10}")


def cmd_list_all(args):
    """列出所有 permission 规则。"""
    model = load_model(args.config)
    root = model.value
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


def main():
    parser = argparse.ArgumentParser(description="管理 OpenCode permission.bash 规则")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_p = subparsers.add_parser("add", help="添加权限规则")
    add_p.add_argument("rule", help='规则模式，如 "kubectl get *"')
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
