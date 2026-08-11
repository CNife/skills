#!/usr/bin/env node
/**
 * aihot-leaderboard.js — 抓取 AIHOT 大模型排行榜总榜（前 30 名）。
 *
 * 反爬说明：aihot.virxact.com 有 EO_Bot_Ssid 反爬（curl/无头浏览器被拦，code 567），
 * 必须跑在真实浏览器会话里。本脚本设计为粘贴进 omp 的 xd://browser（action=run,
 * name=main）的 code 字段执行，页面上下文里同源 fetch / DOM 可用。
 *
 * 数据来源页：/leaderboard
 * 每行 DOM：`a.lb-row`，叶子节点文本依次为：
 *   排名 / 模型 / 厂商 / "上线" / 日期 / "评测" / 完整度% / "输入" / $ / "输出" / $ / 共识分
 *   （订阅制模型如 Qwen3.8 Max 无输入/输出价，为 "$6/月起"）
 * 输出：JSON 写入 /tmp/aihot-leaderboard.json（可改 OUTPUT）。
 *
 * 用法：
 *   1. xd://browser open https://aihot.virxact.com/leaderboard
 *   2. 把本文件内容粘贴到 xd://browser run 的 code 字段执行
 *   3. 结果在 /tmp/aihot-leaderboard.json
 */
const OUTPUT = '/tmp/aihot-leaderboard.json';

async function main() {
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

  const fs = require('fs');
  fs.writeFileSync(OUTPUT, JSON.stringify(rows, null, 2));
  return JSON.stringify({ output: OUTPUT, count: rows.length, first: rows[0] });
}

return main();
