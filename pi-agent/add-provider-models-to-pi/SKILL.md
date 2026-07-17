---
name: add-provider-models-to-pi
disable-model-invocation: true
description: 从 models.dev 或官方 API 文档拉取 provider 模型参数并适配进 pi 的 models.json，再通过 agentic 测试验证配置正确性并固定（下游消费 models-dev-query）。
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
2. 用 models-dev-query 技能查 models.dev，找 `api`/`baseUrl` 与之相同的 provider：命中则取参；未命中（如方舟）则回退抓该**对应 provider**的官方 API 文档（web）。
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

### 5. Checkpoint

跑完取参+适配，产出 **brief** 再让用户确认一次，确认后才写入：

- 将要插入的模型块（diff/表格）。
- 关键判断：参数源（models.dev 命中 / 官方文档回退）、三层思考结论（机制/能力/最终 map）、context/maxTokens 取值（与 models.dev 不同会标明）、cost 省略或填了。
- 来源链接。
- **完成标准**：brief 已呈现并经用户确认；`models.json` 写入且 `jq empty` 校验通过。

---

**验证阶段（步骤 6–9）：测试-抓取-循环-固定**--写入配置后立即验证，用 `capture.ts` 扩展抓取 pi 实际发送的请求和响应，通过 ≤3 轮测试-改进循环收敛到正确配置，最终固定。

**前提**：步骤 5 已写入 `models.json` 且 `jq empty` 通过；`capture.ts` 位于技能 `scripts/capture.ts`。

### 6. 运行 agentic 测试

用 `pi --extension` 临时加载 `capture.ts`，执行一个 agentic 任务（多轮工具调用），
一次性覆盖四个调试维度：

```bash
PI_CAPTURE_LOG=/tmp/pi-verify-<provider>.log \
  pi --extension <skill-dir>/scripts/capture.ts \
  --print --model <provider>/<model> \
  '用 bash 工具列出 /tmp 目录下的前 5 个文件名，然后告诉我一共多少个'
```

- `<skill-dir>` 替换为本技能实际路径（`fd add-provider-models-to-pi` 定位）。
- 注意用 `--print`（非交互模式），事件自动触发。
- 日志写入 `PI_CAPTURE_LOG` 指定路径（默认 `/tmp/pi-capture.log`）。
- **完成标准**：pi 正常完成请求、日志文件已生成非空。

### 7. 抓取调试

读取日志文件，按 CALL 块分析以下四维度：

| 维度 | 请求侧（payload）证据 | 响应侧（message_end）证据 |
|---|---|---|
| **基础链路** | payload 含 messages、model 正确 | `stopReason` 非 error，status=200 |
| **思考参数** | payload 含 `thinking` / `reasoning_effort` 字段 | `thinkingBlocks>0`，thinking 文本可见 |
| **tool 格式** | payload 含 `tools[]`（function 定义） | `stopReason=toolUse` + `toolCalls` 非空 |
| **缓存** | — | 多轮请求第 2+ 轮 `cacheRead>0` 命中 |

日志中一个完整 assistant CALL 块的示例结构：

```text
╔══════════════════════════════════════════════════════════════
║ CALL #1 — 2026-07-17T01:47:34.244Z  [assistant]
╠══════════════════════════════════════════════════════════════
║ [REQUEST] before_provider_request payload:
║   { ...完整请求 JSON，含 model/messages/tools/thinking/max_tokens... }
╠──────────────────────────────────────────────────────────────
║ [HEADERS] before_provider_headers (不含 Authorization，见注):
╠──────────────────────────────────────────────────────────────
║ [RESPONSE] after_provider_response (status + headers; no body):
║   [0] HTTP 200
║       { "content-type": "text/event-stream", ... }
╠──────────────────────────────────────────────────────────────
║ [MESSAGE_END] role=assistant model=... responseModel=...
║   stopReason=toolUse
║   usage={"input":6,"output":86,"cacheRead":0,"cacheWrite":12321,...}
║   content={...thinkingBlocks, toolCalls...}
╚══════════════════════════════════════════════════════════════
```

**注意事项**：

- `before_provider_headers` 事件拿不到 Authorization——pi 在事件返回后才注入 auth。
  该事件是扩展 mutate headers 的入口，非读取实际发送头。调试 API key 靠"跑通与否"判断。
- user / toolResult 的 `message_end` 单独成精简块（无 provider 段），可忽略。
- 日志不脱敏（含 payload 里的 system prompt 全文、messages），调试结束删除。
- **完成标准**：四维度均已检查，确认有无问题或明确问题所在。

### 8. 循环改进

如果步骤 7 发现配置问题，进入改进循环：

1. **回退**：配置问题需恢复时，用步骤 5 的备份或 `git diff models.json` 还原。
2. **调整**：根据步骤 7 的发现修正 `models.json` 配置：
   - `thinkingLevelMap` 档位映射错 → 调整第 4 步得出的映射。
   - `compat` 推断不对 → 显式设置 `compat` 字段覆盖自动推断。
   - 其他字段错 → 按第 3 步重新适配。
3. **重测**：重复步骤 6--用 `PI_CAPTURE_LOG` 覆盖旧日志，确认问题已解决。
4. **上限**：≤3 轮。超过 3 轮仍未通过，**暂停**并向用户报告：
   - 当前抓取发现（哪些维度通过、哪些失败）。
   - 已尝试的调整及其效果。
   - 待排查的配置问题。
   - 回滚：从备份或 git 恢复步骤 5 前的 `models.json`。

一轮定义：一次 `pi --extension capture.ts --print` 运行 + 日志分析。
同轮内多次运行（修复后重测）仍算同一轮。

- **完成标准**：配置问题已解决 或 超限暂停向用户报告。

### 9. 固定

配置验证通过后固定最终结果：

1. **清除扩展**：调试完成后，确认 `models.json` 未引用 `capture.ts`（无 `--extension` 依赖）。
2. **校验**：`jq empty /home/cnife/.pi/agent/models.json` 确保 JSON 有效。
3. **确认**：`pi --list-models 2>&1 | grep <provider>` 确认新模型可见。
4. **清理**：删除临时日志文件：`rm -f /tmp/pi-verify-<provider>.log`。
5. **简报**：告知用户：已添加的模型列表、已通过的测试维度、capture.ts 保留位置（后续排查可复用）。

- **完成标准**：models.json 有效、模型在 pi 中可见、日志已清理、用户已被告知结果。

## 输出

- 修改后的 `models.json`（仅追加/更新目标 provider 的 `models` 数组）。
- 验证通过的最终配置（已确认 thinkingLevelMap / compat / 缓存均正确）。
- 一份包含配置摘要 & 测试结论的 brief 报告。
- `capture.ts` 扩展（保留于 `scripts/capture.ts`，后续排查可复用的附属资产）。
