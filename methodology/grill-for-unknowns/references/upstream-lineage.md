# 上游溯源：有据盘问 + 发现未知数

本技能把三份 Matt Pocock 上游技能与 Thariq 的 "Finding Your Unknowns" 文章改编组合成一个代理技能。

## 直接改编基线

本中文版忠实改编译自 nicobailon/grill-for-unknowns 的固定版本：

- 版本：v0.1.3
- commit：`d8d5f4b422b8be1301dd4a515d96589eaddc5f3c`
- 仓库：<https://github.com/nicobailon/grill-for-unknowns>

相对该版本只做中文本地化和 CNife 仓库封装（目录迁移、README / NOTICE / LICENSE 配套），不改变盘问机制。

## 来源技能

- `grill-with-docs`：<https://github.com/mattpocock/skills/blob/main/skills/engineering/grill-with-docs/SKILL.md>
  - 极简组合式技能：跑一次 `/grilling` 会话，同时使用 `/domain-modeling`。
  - 重要含义：真实行为来自"无休止访谈 + 领域模型维护"的组合。
- `grilling`：<https://github.com/mattpocock/skills/blob/main/skills/productivity/grilling/SKILL.md>
  - 对计划 / 设计的每个方面持续盘问，直到达成共享理解。
  - 按决策树一个分支一个分支走。
  - 一次只问一个问题。
  - 每个问题都给出推荐答案。
  - 代码库中的事实自己查；决策属于用户。
  - 共享理解确认前不落地计划。
- `domain-modeling`：<https://github.com/mattpocock/skills/tree/main/skills/engineering/domain-modeling>
  - 设计推进时构建 / 打磨领域术语。
  - 立即质疑模糊或冲突的语言。
  - 用代码交叉验证主张。
  - 领域术语结晶时同步更新 `CONTEXT.md`。
  - 只为难以逆转、没有上下文会让人惊讶、且是真实权衡结果的决策提供 ADR。

## 正在吸收的文章策略

Thariq 的文章把代理编码质量定义为发现以下两者之间的差距：

- **地图**：提示词、计划、假设、技能、文档摘录、代理当前心智模型。
- **领土**：真实代码库、API、产品 / 领域约束、部署环境、测试、用户品味、审查者预期。

该差距被分为：

- 已知的已知
- 已知的未知
- 未知的已知
- 未知的未知

文章的具体战术：盲区扫描、头脑风暴 / 原型、一次一问的访谈、把参照 / 源码当规格、实施计划、实施笔记、讲解、测验。

## 本改编

`grill-for-unknowns` 因此应表现为组合式技能：

1. 跑 `grilling` 的盘问访谈循环。
2. 维护来自 `domain-modeling` 的领域模型 / 共享语言台账。
3. 问用户之前先用文档 / 源码 / 测试落地事实主张。
4. 用已知 / 未知分类法在实施前找出隐藏假设。
5. 术语结晶时持久化到 `CONTEXT.md`，重大权衡决策在适当时写入 ADR。
6. 用户在共享理解确认前不落地，除非用户明确要求带标注假设继续。

## 面向维护者的编写笔记

改编上游技能的经验教训。这是对未来编辑本技能包的指导，不是技能的运行时行为：

- **检查完整的上游组合。** 改编技能 / 文章 / 框架时不要只看头条文件。`grill-with-docs` 看起来很小，但真实行为来自它链接的 `grilling` + `domain-modeling` 技能及其支持文件。
- **把新写的技能当作第一版。** 对照源材料重读一遍，在宣告完成前问自己：还缺什么依赖、支持文件、模板或行为？
- **保留归属与许可。** 在 `README.md` 保留归属，在 `LICENSE` 保留上游许可 / 版权声明。不要只留下本地改编者的版权而删掉上游版权。

## 许可

本技能目录内的 `../LICENSE` 逐字保留上游 MIT 授权文本及 Matt Pocock、Nico Bailon 的 2026 版权声明，并追加 CNife 的改编版权。仓库根 LICENSE 不替代技能内 LICENSE。
