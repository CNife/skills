# grill-for-unknowns（中文版）

`grill-for-unknowns` 是一个代理技能，用于在复杂实现开始前让代理和用户达成共享理解。

它组合了：

- 以文档 / 源码为依据的计划盘问；
- 一次一问的设计访谈；
- 领域语言 / ADR 记录；
- "发现你的未知数"策略：已知的已知、已知的未知、未知的已知、未知的未知。

预期行为一句话：

> 先查真实领土，只在决策关键处盘问计划和用户，扫描盲区，把共享理解写下来，然后再动手。

## 何时使用

当代理**不应**急着直接实现时：

- 不熟悉的代码库区域；
- 不熟悉的 API / 库 / 平台文档；
- 模糊的产品 / 设计方向；
- 派发长跑子代理或编码代理前；
- 复杂的架构或领域模型决策；
- 之前因假设而失败的尝试；
- 任何需要在动手前压测的计划。

技能要求代理把四类东西分开：

- 能从文档 / 源码 / 测试 / 配置中查到的**事实**；
- 需要用户拍板的**决策**；
- 应当澄清并记录的**领域语言**；
- 可能实质改变实现的**未知数**。

## 中文化与自包含说明

本中文版忠实改编自 [nicobailon/grill-for-unknowns](https://github.com/nicobailon/grill-for-unknowns) 的固定版本 v0.1.3（commit `d8d5f4b422b8be1301dd4a515d96589eaddc5f3c`）：相对该版本**只做中文本地化和 CNife 仓库封装，不改变盘问机制**。nicobailon 版本本身改编 / 组合了 Matt Pocock 的 MIT 技能（`grilling`、`grill-with-docs`、`domain-modeling`）并吸收 Thariq 文章 "Finding Your Unknowns" 的策略；其 README 中"相对 Matt 上游的五点扩展"（覆盖访谈看不到的盲区、定义好问题的标准、自包含封装、延伸到规划边界之外、产出持久产物）归属于 nicobailon 版本，不是本中文版的原创内容。完整溯源见 `references/upstream-lineage.md`，归属与许可见 `NOTICE.md` 与 `LICENSE`。

本技能目录自包含：运行时不依赖网络或已安装的其他技能。渐进披露通过本地指针实现——主流程 `SKILL.md` 只在需要时指向本目录内的模板与附录：

- 复杂会话台账 → `templates/grill-session.md`
- 领域术语 / ADR 细则 → `references/domain-modeling-add-on.md`
- 实施记录 → `templates/implementation-notes.md`
- 长跑代理启动包 → `templates/launch-packet.md`

## 目录结构

```txt
grill-for-unknowns/
├── SKILL.md
├── README.md
├── LICENSE
├── NOTICE.md
├── references/
│   ├── upstream-lineage.md
│   └── domain-modeling-add-on.md
└── templates/
    ├── ADR.md
    ├── CONTEXT.md
    ├── grill-session.md
    ├── implementation-notes.md
    └── launch-packet.md
```

## 来源与许可

- 直接改编：nicobailon/grill-for-unknowns v0.1.3（commit `d8d5f4b422b8be1301dd4a515d96589eaddc5f3c`），<https://github.com/nicobailon/grill-for-unknowns>
- 间接来源：Matt Pocock 的 `grilling`、`grill-with-docs`、`domain-modeling` 技能（MIT）；Thariq 文章 "A Field Guide to Fable: Finding Your Unknowns"
- 许可：MIT。`LICENSE` 逐字保留上游版权声明（Matt Pocock、Nico Bailon 均为 2026）并追加 CNife 改编版权；详见 `NOTICE.md`。
