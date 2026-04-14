# Stock Daily Review

自动生成每日股市复盘日记。从同花顺投资账本抓取持仓数据，结合 tushare 市场数据，由 AI 汇总生成复盘文本写入 Obsidian 日记。

## 触发条件

用户输入包含以下意图时触发：
- "写日报"、"今日复盘"、"记录今天的操作"、"stock review"、"daily review"
- 需验证当前日期是交易日（通过 tushare `trade_cal` 验证）

## 数据源

### 1. 账户数据（同花顺投资账本）

```bash
cd ~/workspace/tzzb && uv run --script=scrape_tzzb.py
```

输出：`output/{date}_tzzb_data.json`

### 2. 市场数据（tushare）

```bash
# 指数数据
uv run --script=scripts/fetch_index.py --date {date}

# 板块数据
uv run --script=scripts/fetch_sectors.py --date {date}
```

### 3. 账户计算

```bash
uv run --script=scripts/calc_accounts.py --input output/{date}_tzzb_data.json
```

### 4. 市场新闻

使用 jina 搜索当日 A 股市场概况和热点新闻。

## 工作流

### Step 1: 验证交易日

调用 tushare `trade_cal` 检查今日是否为交易日。如非交易日，提示用户并终止。

### Step 2: 抓取持仓数据

```bash
cd ~/workspace/tzzb && uv run --script=scrape_tzzb.py
```

读取 `output/{date}_tzzb_data.json`，得到分账户数据。

### Step 3: 获取市场数据

并行运行：
```bash
uv run --script=scripts/fetch_index.py --date {date} > /tmp/index_data.json
uv run --script=scripts/fetch_sectors.py --date {date} > /tmp/sector_data.json
```

### Step 4: 计算账户数据

```bash
uv run --script=scripts/calc_accounts.py --input output/{date}_tzzb_data.json > /tmp/account_calc.json
```

### Step 5: 搜索市场新闻

使用 `mcp__jina__search_web` 搜索当日 A 股市场概况。

### Step 6: AI 生成市场评论

汇总以下信息生成一段简短的市场评论：
- 大盘走势（上证指数、深成指、创业板指涨跌幅）
- 热点板块（申万一级行业涨跌前3）
- 持仓涨跌概况（各账户涨跌幅、持仓个股表现）

风格参考：简洁、专业、重点突出当日关键信息。

### Step 7: 询问策略详情

展示策略账户持仓数据，询问用户：

```
策略账户当前持仓：
{展示策略账户 holdings}

请确认：
1. 全球选基策略当前持有/空仓？
2. 轮动策略当前持有/空仓？
```

计算策略累计收益和年化收益：
- 起始日期：2025-10-20
- 初始资金：20,000 元
- 累计收益 = (策略账户当前总资产 / 20000) - 1
- 年化收益 = (1 + 累计收益) ^ (365 / 持有天数) - 1

### Step 8: 组装日记

按以下模板组装完整复盘文本：

```markdown
# 今日股市复盘

{date} 星期{weekday} 股市复盘

今日收益{daily_return}%，跑赢/跑输中证全指{benchmark_diff}%，仓位{position_rate}%。

{market_commentary}

操作汇总
1. 股票：{stock_return}%，仓位{stock_position}%；{stock_trades}。
2. ETF：{etf_return}%，仓位{etf_position}%；{etf_trades}。
3. 策略：{strategy_return}%；{strategy_details}。策略累计收益{strategy_cum}%，年化收益{strategy_ann}%。
```

**字段说明：**
- `{date}`: 日期，如 `2026-04-14`
- `{weekday}`: 星期几
- `{daily_return}`: 总体当日涨跌幅
- `{benchmark_diff}`: 相对中证全指的差值
- `{position_rate}`: 总体仓位
- `{market_commentary}`: AI 生成的市场评论
- `{stock_return}`, `{stock_position}`: 股票账户涨跌幅、仓位
- `{stock_trades}`: 股票操作描述或"没有操作"
- `{etf_return}`, `{etf_position}`: ETF 账户涨跌幅、仓位
- `{etf_trades}`: ETF 操作描述或"没有操作"
- `{strategy_return}`: 策略账户涨跌幅
- `{strategy_details}`: 全球选基和轮动策略的持仓状态
- `{strategy_cum}`: 策略累计收益
- `{strategy_ann}`: 策略年化收益

**周五额外追加：**
```markdown
---

## 周度汇总

本周收益{weekly_return}%，本周中证全指{weekly_benchmark}%。
{weekly_commentary}
```

### Step 9: 写入日记

定位当天日记文件：
```
/mnt/c/Obsidian/个人/个人日记/{YYYY}/{MM}/{YYYY} 年 {M} 月 {D} 日 星期{X}.md
```

- 如已有 `# 今日股市复盘` 段落则替换
- 否则追加到文件末尾
- 如文件不存在则创建

## 脚本路径

所有脚本位于 `~/workspace/tzzb/scripts/`：
- `fetch_index.py` - 获取指数涨跌幅
- `fetch_sectors.py` - 获取板块排行
- `calc_accounts.py` - 计算账户数据

主抓取脚本位于 `~/workspace/tzzb/scrape_tzzb.py`。

## 依赖

- tushare + TUSHARE_TOKEN（自动从环境读取）
- Edge CDP (port 9222)
- Playwright
- Python 3.14+
