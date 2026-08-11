#!/usr/bin/env node
/**
 * aihot-sources.js — 抓取 AIHOT 全部来源官方榜单（12 张评测榜单，10 家独立来源）。
 *
 * 反爬说明：aihot.virxact.com 有 EO_Bot_Ssid 反爬（curl/无头浏览器被拦，code 567），
 * 必须跑在真实浏览器会话里。本脚本为 CommonJS 模块，由 xd://browser 的 run code
 * 用 require 从磁盘加载后调用（见下方用法），无需粘贴本文件全文。
 *
 * 数据来源页：/leaderboard/methodology
 * 交互：左侧 `.lb-source-nav button` 点击切换来源；部分来源有 `.lb-source-signal-tabs`
 *       子 tab（如 llm2014 Agent / llm2014 推理）。SPA 切换，URL 不变。
 *
 * 用法（xd://browser run 的 code 字段执行，name=main）：
 *   <SCRIPTS_DIR> = 本技能 scripts 目录（= SKILL.md 所在目录下的 scripts/；
 *   用 read skill://aihot-leaderboard 或搜索 aihot-leaderboard/SKILL.md 定位，勿预设安装目录）
 *   const file = '<SCRIPTS_DIR>/aihot-sources.js';
 *   delete require.cache[require.resolve(file)];
 *   const { extractSources } = require(file);
 *   return extractSources(page);
 *
 * 返回：{ output, counts }（数据量大，rows 不内联）；完整 JSON 写入 options.output
 *   指定文件（默认 /tmp/aihot-sources.json），用 read 读取。
 *
 * 依赖：无（仅用浏览器页面上下文原生 API + Node 内置 fs）。
 */
'use strict';

const fs = require('fs');

const DEFAULT_OUTPUT = '/tmp/aihot-sources.json';

// 来源按钮文本 → 规范名。按钮 innerText 可能带说明文字，用 startsWith 匹配。
// 顺序即点击顺序；同一运营方的多张榜单在组内平分权重（服务端计算，这里只取数据）。
const SOURCES = [
  'AA Index',
  'Epoch ECI',
  'LiveBench',
  'LMArena',
  'EQ-Bench',
  'Vals Index',
  'APEX-Agents',
  "Agents' Last Exam",
  'DeepSWE v1.1',
  'llm2014',
];

async function extractSources(page, options = {}) {
  const output = options.output || DEFAULT_OUTPUT;

  // 精确匹配：methodology 页 URL 以 /leaderboard/methodology 结尾
  if (!/\/leaderboard\/methodology$/.test(page.url())) {
    await page.goto('https://aihot.virxact.com/leaderboard/methodology', {
      waitUntil: 'networkidle2',
      timeout: 45000,
    });
  }
  await new Promise((r) => setTimeout(r, 1500));

  const all = {};
  for (const srcName of SOURCES) {
    // 点击来源按钮
    const clicked = await page.evaluate((name) => {
      const btns = Array.from(document.querySelectorAll('.lb-source-nav button'));
      const target = btns.find((b) => (b.innerText || '').trim().startsWith(name));
      if (!target) return false;
      target.click();
      return true;
    }, srcName);
    if (!clicked) {
      all[srcName] = { error: 'source button not found' };
      continue;
    }
    await new Promise((r) => setTimeout(r, 1200));

    // 该来源下可能的子 tab（如 llm2014 Agent / llm2014 推理）
    const subTabs = await page.evaluate(() => {
      const tabs = document.querySelector('.lb-source-signal-tabs');
      if (!tabs) return [];
      return Array.from(tabs.querySelectorAll('button')).map((b) =>
        (b.innerText || '').trim()
      );
    });

    if (subTabs.length === 0) {
      all[srcName] = await extractCurrentTable(page);
    } else {
      all[srcName] = {};
      for (const sub of subTabs) {
        await page.evaluate((name) => {
          const tabs = document.querySelector('.lb-source-signal-tabs');
          const target = Array.from(tabs.querySelectorAll('button')).find(
            (b) => (b.innerText || '').trim() === name
          );
          if (target) target.click();
        }, sub);
        await new Promise((r) => setTimeout(r, 1000));
        all[srcName][sub] = await extractCurrentTable(page);
      }
    }
  }

  fs.writeFileSync(output, JSON.stringify(all, null, 2));
  const counts = {};
  for (const [k, v] of Object.entries(all)) {
    counts[k] = Array.isArray(v)
      ? v.length
      : Object.fromEntries(Object.entries(v).map(([s, rows]) => [s, rows.length]));
  }
  return { output, counts };
}

async function extractCurrentTable(page) {
  return page.evaluate(() => {
    // 表头下的模型行
    const rows = Array.from(document.querySelectorAll('.lb-source-model-row'));
    return rows.map((r) => {
      const cell = (sel) => {
        const el = r.querySelector(sel);
        return el ? (el.innerText || '').trim() : null;
      };
      const rank = cell('.lb-source-model-rank');
      const name = cell('.lb-source-model-name');
      const provider = cell('.lb-source-model-provider');
      const scoreEl = r.querySelector('.lb-source-model-score');
      const score = scoreEl ? (scoreEl.querySelector('strong')?.innerText || '').trim() : null;
      const ci = scoreEl ? (scoreEl.querySelector('small')?.innerText || '').trim() : null;
      return { rank, model: name, provider, score, confidence_interval: ci || null };
    });
  });
}

module.exports = { extractSources };
