#!/usr/bin/env node
/**
 * aihot-model.js — 抓取 AIHOT 单个模型在各家来源榜单的明细成绩。
 *
 * 反爬说明：aihot.virxact.com 有 EO_Bot_Ssid 反爬（curl/无头浏览器被拦，code 567），
 * 必须跑在真实浏览器会话里。本脚本设计为粘贴进 omp 的 xd://browser（action=run,
 * name=main）的 code 字段执行，页面上下文里同源 fetch / DOM 可用。
 *
 * 数据来源页：/leaderboard/<slug>（slug 见总榜每行的 a.lb-row href，如 claude-opus-5）
 * 页面头部：.lb-detail-overall（共识分 strong、当前名次 b）
 * 每行 DOM：.lb-score-list-row → .lb-score-list-source（榜单名 strong + 运营方 small）、
 *   .lb-score-list-rank、.lb-score-list-value、.lb-score-list-model、.lb-score-list-link
 *   缺评行带 is-missing class（"— 暂无评估"）
 * 输出：JSON 写入 /tmp/aihot-model-<slug>.json（可改 OUTPUT）。
 *
 * 用法（改 slug 后粘贴）：
 *   1. xd://browser open https://aihot.virxact.com/leaderboard
 *   2. 把本文件内容粘贴到 xd://browser run 的 code 字段执行
 *   3. 结果在 /tmp/aihot-model-<slug>.json
 */
const SLUG = 'claude-opus-5'; // ← 改成目标模型的 slug（总榜 a.lb-row 的 href 末段）
const OUTPUT = `/tmp/aihot-model-${SLUG}.json`;

async function main() {
  const url = `https://aihot.virxact.com/leaderboard/${SLUG}`;
  // 精确匹配：/leaderboard/<slug> 结尾；methodology/总榜页需重新跳转
  const isModelPage = new RegExp(`/leaderboard/${SLUG}$`).test(page.url());
  if (!isModelPage) {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
  }
  await new Promise((r) => setTimeout(r, 1500));

  const data = await page.evaluate(() => {
    const out = {};
    const overall = document.querySelector('.lb-detail-overall');
    if (overall) {
      out.score = overall.querySelector('strong')?.innerText.trim() || null;
      const b = overall.querySelector('b');
      out.rank = b ? (b.innerText.trim().match(/\d+/) || [null])[0] : null;
    }
    out.rows = Array.from(document.querySelectorAll('.lb-score-list-row')).map((r) => {
      const src = r.querySelector('.lb-score-list-source');
      let source = null;
      let sourceSub = null;
      if (src) {
        source = src.querySelector('strong')?.innerText.trim() || (src.innerText || '').trim();
        sourceSub = src.querySelector('small')?.innerText.trim() || null;
      }
      const cellText = (el) => {
        if (!el) return null;
        return (el.querySelector('strong')?.innerText || el.innerText || '').trim();
      };
      return {
        source,
        sourceSub,
        rank: cellText(r.querySelector('.lb-score-list-rank')) || null,
        value: cellText(r.querySelector('.lb-score-list-value')) || null,
        model: cellText(r.querySelector('.lb-score-list-model')) || null,
        url: r.querySelector('.lb-score-list-link')?.getAttribute('href') || null,
        missing: r.className.includes('is-missing'),
      };
    });
    return out;
  });

  const fs = require('fs');
  fs.writeFileSync(OUTPUT, JSON.stringify(data, null, 2));
  return JSON.stringify({ output: OUTPUT, slug: SLUG, score: data.score, rank: data.rank, rows: data.rows.length });
}

return main();
