---
name: add-provider-models-to-pi
disable-model-invocation: true
description: 从 models.dev 或官方 API 文档拉取 provider 模型参数并适配进 pi 的 models.json（下游消费 models-dev-query）。
---

# Add Provider Models to Pi

把"往 pi 的 `models.json` 加模型"这件带判断的操作固化成可复用的执行规程。

**对应 provider（leading word）**：模型实际被托管/调用的 provider，以其 `baseUrl`/`api` 为准——不是模型的厂商。例：火山方舟（`ark.cn-beijing.volces.com`）托管了 MiniMax/Kimi，但 models.dev 里只有 `minimax.io`/`kimi.com` 厂商端点。参数必须取自**对应 provider**，否则 API 格式/窗口会错。

## 执行协议

### 1. 确认 Input

- 目标 pi provider：`/home/cnife/.pi/agent/models.json` 中已存在的 provider key，或用户要新建并命名。
- 模型清单：一个或多个模型，按 id/名称（如 `minimax-m3`、`kimi-k2.7-code`）。
- **完成标准**：目标 provider 与模型清单已明确；provider 已存在或新建名已定。

### 2. 源定位 —— 按对应 provider（托管端点）匹配

1. 读目标 pi provider 的 `baseUrl` + `api`。
2. 在 models.dev 找 `api`/`baseUrl` 与之相同的 provider：命中则取参；未命中（如方舟）则回退抓该**对应 provider**的官方 API 文档（web）。
3. 注意：models.dev 的厂商端点（minimax.io）与托管端点（方舟）是不同 provider，模型名相同也不能混用参数。

- **完成标准**：每个目标模型的参数源已确定（models.dev 命中 / 官方文档回退），并记下依据。

### 3. 适配 —— 翻译成 pi 的 model 条目

- `id`：用用户给的 id；与源确认是端点实际接受的模型名（方舟支持全小写，也接受控制台原名）。
- `name`：显示名。
- `reasoning`：来自源。
- `thinkingLevelMap`：见第 4 步三层合成。
- `input`：pi schema 仅接受 `text`/`image`；源的 `video` 等丢弃。
- `contextWindow` / `maxTokens`：以**对应 provider**官方文档为准；与 models.dev 冲突时取官方文档（如方舟 M3 为 512k 而非目录 1M）。
- `cost`：源有按 token 计价填；订阅/套餐制（如 Coding Plan）省略（pi 默认 0）。
- **完成标准**：每个模型已生成符合 pi schema 的 JSON 块，input 已去 video，context/maxTokens 取自对应 provider 官方文档。

### 4. 思考三层合成（核心难点）

1. **Layer1 Provider 机制**：端点怎么收思考参数——参考 pi `openai-completions` 对 provider/baseUrl 的 `compat` 推断逻辑（`supportsReasoningEffort`、`thinkingFormat` 等，见 pi 源码 `packages/ai/src/api/openai-completions.ts` 的 `detectCompat` 与 `packages/ai/src/types.ts`），或直接从对应 provider 官方文档确认（`reasoning_effort`？`thinking:{type}`？deepseek/zai/together 哪种格式？）。
2. **Layer2 模型能力**：模型自身支持什么——来自源（`reasoning` 否？toggle？分级？常开？）。
3. **Layer3 pi 处理**：pi 把统一 level（off/minimal/low/medium/high/xhigh/max）翻译成该 provider API 的规则（靠 `thinkingLevelMap`）：`null` 表示该档位**不支持**（pi 不展示、不可选），非 `null` 字符串表示**支持**且 pi 实际发送该端点值；`off` 特殊——选 `off` 时 pi 不发思考参数（`reasoning_effort` 置 `undefined`），故 `off` 能否选取决于其映射是否非 `null`。

- 合成：支持关闭则 `off` 映射到非 `null` 值（如 `"none"`，仅作"支持"标记，发送时仍走 `undefined`）；不支持关闭则 `off->null`。其余档位按模型实际支持情况映射成端点接受的 effort/toggle 字符串，不支持者置 `null`。同 provider 已有模型仅作交叉校验，不盲抄。
- **完成标准**：每个推理模型已列出全部 7 个档位 `off/minimal/low/medium/high/xhigh/max` 的映射值；`null`=不支持，非 `null` 字符串=支持且为端点接受值；`off` 语义已明确（支持关闭->非 `null`，不支持关闭->`null`）。

### 5. Checkpoint（push right）

跑完取参+适配，产出 **brief** 再让用户确认一次，确认后才写入：

- 将要插入的模型块（diff/表格）。
- 关键判断：参数源（models.dev 命中 / 官方文档回退）、三层思考结论（机制/能力/最终 map）、context/maxTokens 取值（与 models.dev 不同会标明）、cost 省略或填了。
- 来源链接。
- **完成标准**：brief 已呈现并经用户确认；`models.json` 写入且 `jq empty` 校验通过。

## 输出

- 修改后的 `models.json`（仅追加/更新目标 provider 的 `models` 数组）。
- 一份 brief 报告。
