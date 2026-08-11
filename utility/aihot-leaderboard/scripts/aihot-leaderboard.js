#!/usr/bin/env node
/**
 * aihot-leaderboard.js — 抓取 AIHOT 大模型排行榜总榜（前 30 名）。
 *
 * 反爬说明：aihot.virxact.com 有 EO_Bot_Ssid 反爬（curl/无头浏览器被拦，code 567），
 * 必须跑在真实浏览器会话里。本脚本为 CommonJS 模块，由 xd://browser 的 run code
 * 用 require 从磁盘加载后调用（见下方用法），无需粘贴本文件全文。
 *
 * 数据来源页：/leaderboard
 * 每行 DOM：`a.lb-row`，叶子节点文本依次为：
 *   排名 / 模型 / 厂商 / "上线" / 日期 / "评测" / 完整度% / "输入" / $ / "输出" / $ / 共识分
 *   （订阅制模型如 Qwen3.8 Max 无输入/输出价，为 "$6/月起"）
 *
 * 用法（xd://browser run 的 code 字段执行，name=main）：
 *   const path = require('path'), os = require('os');
 *   const dir = path.join(os.homedir(), '.agents/skills/aihot-leaderboard/scripts');
 *   const file = path.join(dir, 'aihot-leaderboard.js');
 *   delete require.cache[require.resolve(file)];
 *   const { extractLeaderboard } = require(file);
 *   return extractLeaderboard(page);
 *
 * 返回：{ output, count, first, rows }，rows 为 30 行完整数据（含每行 url，可作
 *   aihot-model.js 的 slug 来源）；同时写入 JSON 文件（options.output 可覆盖，默认
 *   /tmp/aihot-leaderboard.json）。
 *
 * 依赖：无（仅用浏览器页面上下文原生 API + Node 内置 fs）。
 */
'use strict';

const fs = require('fs');

const DEFAULT_OUTPUT = '/tmp/aihot-leaderboard.json';

async function extractLeaderboard(page, options = {}) {
  const output = options.output || DEFAULT_OUTPUT;

  // 总榜页 URL 以 /leaderboard 结尾；methodology/详情页含额外路径段，需重新跳转
  const isBoardPage = /\/leaderboard$/.test(page.url());
  if (!isBoardPage) {
    await page.goto('https://aihot.virxact.com/leaderboard', {
      waitUntil: 'networkidle2',
      timeout: 45000,
    });
  }
  await new Promise((r) => setTimeout(r, 1500));

  const rows = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a.lb-row')).map((r) => {
      const leaves = Array.from(r.querySelectorAll('*'))
        .filter((e) => e.children.length === 0)
        .map((e) => (e.innerText || '').trim())
        .filter(Boolean);
      // 解析叶子序列；带 "上线"/"评测"/"输入"/"输出" 标签
      const pick = (label) => {
        const i = leaves.indexOf(label);
        return i > -1 ? leaves[i + 1] : null;
      };
      const hasLabel = leaves.some((t) => t === '输入' || t === '输出');
      return {
        rank: leaves[0] || null,
        model: leaves[1] || null,
        provider: leaves[2] || null,
        release_date: pick('上线'),
        completeness: pick('评测'),
        price: hasLabel
          ? { input: pick('输入'), output: pick('输出') }
          : { note: leaves.find((t) => t.includes('月起')) || null },
        consensus_score: leaves[leaves.length - 1] || null,
        url: r.getAttribute('href') || null,
      };
    });
  });

  fs.writeFileSync(output, JSON.stringify(rows, null, 2));
  return { output, count: rows.length, first: rows[0], rows };
}

module.exports = { extractLeaderboard };
