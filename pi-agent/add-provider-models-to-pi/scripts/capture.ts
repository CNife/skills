/**
 * capture.ts — 抓取 pi 实际发送的请求 payload 和收到的响应。
 *
 * 用途：调试 models.json 配置（thinkingLevelMap / compat / 缓存 / tool 格式）。
 * 加载：`pi --extension <path>/capture.ts --print --model <provider/model> "<task>"`
 * 日志：$PI_CAPTURE_LOG（默认 /tmp/pi-capture.log），不脱敏，调试结束删除。
 *
 * 事件组合（按触发顺序）：
 *   before_provider_headers → before_provider_request → after_provider_response
 *   message_end（user / assistant / toolResult 都会触发）
 *
 * 配对策略：before_provider_headers 开请求槽 → before_provider_request 填 payload
 *   → after_provider_response 填响应 → assistant message_end flush 完整 CALL 块
 *   user/toolResult 的 message_end 单独 flush 精简块
 *
 * 已知局限：
 * - before_provider_headers 拿不到 Authorization（pi 在事件返回后才注入 auth）
 * - 日志不脱敏，含 payload 完整内容，调试完请删除
 */
import { appendFileSync, writeFileSync, existsSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// ---- 日志路径 ----
const LOG_PATH = process.env.PI_CAPTURE_LOG ?? "/tmp/pi-capture.log";

// ---- 一次 HTTP 请求的槽 ----
interface RequestSlot {
	callIndex: number;
	startTime: string;
	headers?: Record<string, string | null>;
	payload?: unknown;
	responses: Array<{ status: number; headers: Record<string, string> }>;
}

// 尚未被 assistant message_end 消费的请求槽（按顺序）。
const pendingSlots: RequestSlot[] = [];
let callCount = 0;

function newSlot(): RequestSlot {
	callCount += 1;
	return {
		callIndex: callCount,
		startTime: new Date().toISOString(),
		responses: [],
	};
}

function appendLog(text: string): void {
	appendFileSync(LOG_PATH, text, "utf8");
}

// 屏幕分割线
const TOP = "══════════════════════════════════════════════════════════════";
const MID = "──────────────────────────────────────────────────────────────";

export default function (pi: ExtensionAPI) {
	// 启动时清空旧日志：每次新 run 重新开始
	try {
		if (existsSync(LOG_PATH)) {
			writeFileSync(LOG_PATH, "", "utf8");
		}
		appendLog(`# pi-capture log\n# started ${new Date().toISOString()}\n# LOG_PATH=${LOG_PATH}\n\n`);
	} catch (e) {
		console.error(`[capture.ts] Failed to init log at ${LOG_PATH}:`, e);
	}

	// ---- 1. 请求头（HTTP 请求链起点）----
	// 注意：实际 Authorization 等敏感头在此事件返回后才注入，故拿不到
	pi.on("before_provider_headers", (event, _ctx) => {
		try {
			const slot = newSlot();
			slot.headers = event.headers as Record<string, string | null>;
			pendingSlots.push(slot);
		} catch (e) {
			console.error("[capture.ts] before_provider_headers error:", e);
		}
	});

	// ---- 2. 请求体（已应用 thinkingLevelMap/compat 的最终 payload）----
	pi.on("before_provider_request", (event, _ctx) => {
		try {
			// 填到最近开的槽里
			const slot = pendingSlots[pendingSlots.length - 1];
			if (slot) {
				slot.payload = event.payload;
			} else {
				// 理论上不会发生（headers 先到），防御性开一个槽
				const s = newSlot();
				s.payload = event.payload;
				pendingSlots.push(s);
			}
		} catch (e) {
			console.error("[capture.ts] before_provider_request error:", e);
		}
	});

	// ---- 3. 响应状态 + 响应头（不含 body，stream consume 前触发）----
	pi.on("after_provider_response", (event, _ctx) => {
		try {
			const slot = pendingSlots[pendingSlots.length - 1];
			if (slot) {
				slot.responses.push({
					status: event.status,
					headers: event.headers as Record<string, string>,
				});
			}
		} catch (e) {
			console.error("[capture.ts] after_provider_response error:", e);
		}
	});

	// ---- 4. 最终 message（响应主来源）----
	pi.on("message_end", (event, _ctx) => {
		try {
			const msg = event.message;

			// assistant 消息：消费一个待处理请求槽，产出完整 CALL 块
			if (msg.role === "assistant") {
				const slot = pendingSlots.shift() ?? newSlot(); // 防御性
				flushAssistantBlock(slot, msg);
				return;
			}

			// user / toolResult：没有对应 provider 请求，单独 flush 精简块
			flushNonAssistantBlock(msg);
		} catch (e) {
			console.error("[capture.ts] message_end error:", e);
		}
	});
}

// ---- assistant 完整 CALL 块 ----
function flushAssistantBlock(slot: RequestSlot, msg: any): void {
	const content: any[] = msg.content ?? [];
	const textBlocks = content.filter((b: any) => b?.type === "text") as Array<{ text: string }>;
	const thinkingBlocks = content.filter((b: any) => b?.type === "thinking") as Array<{ thinking: string }>;
	const toolCalls = content.filter((b: any) => b?.type === "toolCall") as Array<{
		name: string;
		arguments: Record<string, unknown>;
	}>;

	const lines: string[] = [];
	lines.push(`╔${TOP}`);
	lines.push(`║ CALL #${slot.callIndex} — ${slot.startTime}  [assistant]`);
	lines.push(`╠${TOP}`);

	// REQUEST
	lines.push("║ [REQUEST] before_provider_request payload:");
	if (slot.payload === undefined) {
		lines.push("║   (no payload captured — event did not fire?)");
	} else {
		lines.push(indentJson(slot.payload, "║   "));
	}

	lines.push(`╠${MID}`);
	lines.push("║ [HEADERS] before_provider_headers (含敏感头，本地调试不脱敏):");
	if (slot.headers === undefined) {
		lines.push("║   (no headers captured — event did not fire?)");
	} else {
		lines.push(indentJson(slot.headers, "║   "));
	}

	lines.push(`╠${MID}`);
	lines.push("║ [RESPONSE] after_provider_response (status + headers; no body):");
	if (slot.responses.length === 0) {
		lines.push("║   (no response captured — event did not fire?)");
	} else {
		slot.responses.forEach((r, i) => {
			lines.push(`║   [${i}] HTTP ${r.status}`);
			lines.push(indentJson(r.headers, "║       "));
		});
	}

	lines.push(`╠${MID}`);
	lines.push(`║ [MESSAGE_END] role=assistant model=${msg.model ?? "—"} responseModel=${msg.responseModel ?? "—"}`);
	if (msg.stopReason !== undefined) lines.push(`║   stopReason=${msg.stopReason}`);
	if (msg.errorMessage) lines.push(`║   errorMessage=${msg.errorMessage}`);
	if (msg.usage) lines.push(`║   usage=${JSON.stringify(msg.usage)}`);
	lines.push(
		`║   content=${JSON.stringify({
			textBlocks: textBlocks.length,
			textChars: textBlocks.reduce((s, b) => s + (b.text?.length ?? 0), 0),
			thinkingBlocks: thinkingBlocks.length,
			thinkingChars: thinkingBlocks.reduce((s, b) => s + (b.thinking?.length ?? 0), 0),
			toolCalls: toolCalls.map((t) => ({
				name: t.name,
				argKeys: t.arguments ? Object.keys(t.arguments) : [],
			})),
		})}`,
	);
	lines.push("║   rawMessage=");
	lines.push(indentJson(msg, "║     "));

	lines.push(`╚${TOP}`);
	lines.push("");
	appendLog(lines.join("\n") + "\n");
}

// ---- user / toolResult 精简块 ----
function flushNonAssistantBlock(msg: any): void {
	const lines: string[] = [];
	lines.push(`╔${TOP}`);
	lines.push(`║ CALL #${callCount + 1} — ${new Date().toISOString()}  [${msg.role}]`);
	lines.push(`║ NOTE: non-assistant message_end (role=${msg.role}) — no provider request`);
	lines.push(`╠${TOP}`);
	if (msg.role === "toolResult") {
		const content: any[] = msg.content ?? [];
		const textChars = content
			.filter((b: any) => b?.type === "text")
			.reduce((s, b: any) => s + (b.text?.length ?? 0), 0);
		lines.push(`║ toolName=${msg.toolName} toolCallId=${msg.toolCallId} isError=${msg.isError} textChars=${textChars}`);
	} else if (msg.role === "user") {
		const c = msg.content;
		const preview = typeof c === "string" ? c.slice(0, 200) : JSON.stringify(c).slice(0, 200);
		lines.push(`║ user preview: ${preview}`);
	}
	lines.push(`╚${TOP}`);
	lines.push("");
	// user/toolResult 块不计入 callCount（callCount 只数真实 LLM 调用）
	appendLog(lines.join("\n") + "\n");
}

// ---- helpers ----

function indentJson(value: unknown, indent: string): string {
	const json = JSON.stringify(value, null, 2) ?? String(value);
	return json
		.split("\n")
		.map((l) => `${indent}${l}`)
		.join("\n");
}
