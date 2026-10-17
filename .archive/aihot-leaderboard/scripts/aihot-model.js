#!/usr/bin/env node
/**
 * aihot-model.js - 抓取 AIHOT 单个模型在各家来源榜单的明细成绩。
 *
 * 数据来源页：/leaderboard/<slug>（slug 见总榜每行的 a.lb-row href，如 claude-opus-5）
 * 页面头部：.lb-detail-overall（共识分 strong、当前名次 b）
 * 每行 DOM：.lb-score-list-row -> .lb-score-list-source（榜单名 strong + 运营方 small）、
 *   .lb-score-list-rank、.lb-score-list-value、.lb-score-list-model、.lb-score-list-link
 *   缺评行带 is-missing class（"- 暂无评估"）
 *
 * 返回：{ output, slug, score, rank, rows }，rows 为该模型在全部来源条目的明细；
 *   同时写入 JSON 文件（options.output 可覆盖，默认 /tmp/aihot-model-<slug>.json）。
 *
 * 依赖：无（仅用浏览器页面上下文原生 API + Node 内置 fs）。
 * 用法与反爬见 SKILL.md。
 */
'use strict';

const fs = require('fs');

async function extractModel(page, options = {}) {
  const slug = options.slug;
  if (!slug) {
    throw new Error('extractModel 需要 options.slug（总榜 a.lb-row href 末段，如 claude-opus-5）');
  }
  const output = options.output || `/tmp/aihot-model-${slug}.json`;
  const url = `https://aihot.virxact.com/leaderboard/${slug}`;

  // 精确匹配：/leaderboard/<slug> 结尾；methodology/总榜页需重新跳转
  const isModelPage = new RegExp(`/leaderboard/${slug}$`).test(page.url());
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

  fs.writeFileSync(output, JSON.stringify(data, null, 2));
  return {
    output,
    slug,
    score: data.score,
    rank: data.rank,
    rows: data.rows,
  };
}

module.exports = { extractModel };
