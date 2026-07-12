# 搜索源分类索引

## 目录

- [AI 源](#ai-源) — 可直接问答的 AI 助手
- [技术 / 学术](#技术--学术) — 论文、代码、开发者社区
- [社交媒体](#社交媒体) — 原始帖子、社区讨论
- [资讯 / 新闻](#资讯--新闻) — 新闻、百科、知识
- [购物](#购物) — 商品搜索、价格、好价
- [媒体 / 娱乐](#媒体--娱乐) — 视频、电影、播客
- [求职](#求职) — 职位、招聘
- [金融](#金融) — 股票、加密货币、行情
- [旅游](#旅游) — 目的地、酒店、出行
- [其他](#其他) — 书籍、词典、健康等垂直源

---

## AI 源

可进行对话式问答的 AI 站点。选源决策（何时用 grok/doubao/gemini、串行不并行）见 SKILL.md 步骤 2；查询词构造见 SKILL.md 步骤 4。

### 首选（三选一）

`grok` · `doubao` · `gemini`

### 备选 AI 源

| 站点 | 适用场景 |
|------|----------|
| `deepseek` | 中文深度问答、技术问题 |
| `chatgpt` | 通用英文问答（web 版） |
| `claude` | 英文分析、长文处理 |
| `yuanbao` | 中文问答（腾讯混元） |
| `qwen` | 中文问答（通义千问） |
| `notebooklm` | 文档分析、长文总结 |

## 技术分类索引

用于论文、代码、开发者社区、开源信息。

### 论文 / 学术

| 站点 | 适用 | 备注 |
|------|------|------|
| `arxiv` | 预印本论文、AI/CS 研究 | 按作者/关键词搜索 |
| `google-scholar` | 学术引用检索 | 获取引用信息 |
| `baidu-scholar` | 中文学术搜索 | 百度学术 |
| `cnki` | 中国知网论文 | 海外版 |
| `wanfang` | 万方数据库 | 中文学术 |
| `pubmed` | 生物医学论文 | NCBI 数据库 |
| `openreview` | AI 会议审稿 | 同行评审 |
| `openalex` | 开放学术索引 | 综合学术数据 |
| `dblp` | CS 出版物索引 | 按作者查询 |

### 开发者社区

| 站点 | 适用 |
|------|------|
| `stackoverflow` | 具体报错、API 用法、代码问题 |
| `hackernews` | 技术社区讨论、创业话题 |
| `reddit` | 英文社区问答、经验贴 |
| `linux-do` | 中文 AI/开源技术社区 |
| `v2ex` | 中文技术社区 |
| `devto` | 开发者文章 |
| `lobsters` | 技术链接聚合 |
| `lesswrong` | 理性思考、AI 安全 |

### 包管理 / 开源

| 站点 | 适用 |
|------|------|
| `npm` | npm 包查询 |
| `pypi` | Python 包查询 |
| `crates` | Rust crate 查询 |
| `dockerhub` | Docker 镜像查询 |
| `goproxy` | Go 模块信息 |
| `nuget` | .NET 包查询 |
| `rubygems` | Ruby gem 查询 |
| `packagist` | PHP 包查询 |
| `homebrew` | macOS Homebrew 包查询 |
| `gitee` | 国内 Git 仓库搜索 |

### 标准 / 安全

| 站点 | 适用 |
|------|------|
| `rfc` | RFC 标准文档 |
| `nvd` | 漏洞数据库 |
| `osv` | 开源漏洞库 |
| `mdn` | Web 开发文档 |
| `endoflife` | 软件生命周期/EOL 日期 |

## 路由提示：

- 「论文」「研究」→ `arxiv`（英文）或 `cnki`（中文）
- 「报错」「API 怎么用」→ `stackoverflow`
- 「社区怎么看」→ `hackernews`、`reddit`、`v2ex`
- 「这个包的信息」→ 对应的包管理站点

---

## 社交媒体

用于需要原始帖子、用户内容、社区讨论时。

| 站点 | 适用 | 地区/语境 |
|------|------|-----------|
| `twitter` | 原始帖子、实时动态、英文舆论 | 全球 |
| `weibo` | 微博热点、话题、中文舆论 | 国内 |
| `xiaohongshu` | 生活方式、穿搭、旅行、真实体验笔记 | 国内 |
| `zhihu` | 中文深度问答、行业经验 | 国内 |
| `tieba` | 兴趣圈子、贴吧讨论 | 国内 |
| `douyin` | 抖音短视频、热点 | 国内 |
| `bilibili` | B站视频、弹幕、社区 | 国内 |
| `bluesky` | 去中心化社交 | 全球 |
| `facebook` | 社交网络 | 全球 |
| `instagram` | 图片社交 | 全球 |
| `rednote` | 小红书（英文名） | 国内 |
| `jike` | 即刻社区 | 国内 |
| `hupu` | 虎扑体育社区 | 国内 |
| `maimai` | 脉脉职场社交 | 国内 |
| `zsxq` | 知识星球 | 国内 |
| `tiktok` | 海外短视频 | 全球 |

## 路由提示：

- 用户明确说平台名 → 直接用该站点
- 「国外网友怎么看」→ `twitter`、`reddit`
- 「国内怎么讨论」→ `weibo`、`zhihu`
- 「真实体验/种草」→ `xiaohongshu`
- 「短视频/热点」→ `douyin` 或 `tiktok`

---

## 资讯 / 新闻

| 站点 | 适用 |
|------|------|
| `google` | 通用网页搜索、跨站点兜底 |
| `duckduckgo` | 隐私友好的网页搜索 |
| `brave` | Brave 搜索 |
| `wikipedia` | 名词解释、背景知识、历史事实 |
| `wikidata` | 结构化知识库 |
| `bbc` | 国际新闻 |
| `reuters` | 路透社新闻 |
| `bloomberg` | 商业/财经新闻 |
| `36kr` | 中文科技/创业资讯 |
| `toutiao` | 今日头条 |
| `sinafinance` | 新浪财经新闻 |
| `substack` | 独立作者文章 |
| `medium` | 英文博客平台 |
| `producthunt` | 新产品发现 |

## 路由提示：

- 「查一下 XX 是什么」→ `wikipedia`
- 「最新新闻」→ `google`（英文）或 `toutiao`/`36kr`（中文）
- 「财经/商业新闻」→ `bloomberg`（英文）或 `sinafinance`（中文）

---

## 购物

| 站点 | 适用 |
|------|------|
| `amazon` | 全球商品搜索、价格参考 |
| `taobao` | 淘宝商品搜索 |
| `jd` | 京东商品搜索 |
| `smzdm` | 什么值得买——好价、优惠、导购 |
| `coupang` | 韩国电商 |
| `xianyu` | 闲鱼二手交易 |
| `1688` | 阿里巴巴批发 |

## 路由提示：

- 全球商品 → `amazon`
- 国内好价/导购 → `smzdm`
- 国内商品搜索 → `taobao` 或 `jd`
- 二手 → `xianyu`

---

## 媒体 / 娱乐

| 站点 | 适用 |
|------|------|
| `youtube` | 英文视频、教程、评测 |
| `bilibili` | 中文视频、教程、UP 主内容 |
| `imdb` | 电影、剧集、演员、评分 |
| `douban` | 中文电影/书籍/音乐口碑 |
| `spotify` | 音乐流媒体 |
| `apple-podcasts` | 播客搜索 |
| `xiaoyuzhou` | 小宇宙播客（中文） |
| `tvmaze` | 剧集信息 |
| `steam` | 游戏平台 |
| `pixiv` | 插画/同人社区 |
| `suno` | AI 音乐生成 |

---

## 求职

| 站点 | 适用 |
|------|------|
| `boss` | BOSS直聘——国内职位搜索 |
| `51job` | 前程无忧 |
| `linkedin` | 全球职位、英文岗位 |
| `indeed` | 全球职位聚合 |
| `nowcoder` | 牛客网——校招/技术岗位 |

## 路由提示：

- 国内岗位 → `boss` 或 `51job`
- 海外/外企岗位 → `linkedin` 或 `indeed`
- 校招/技术岗 → `nowcoder`

---

## 金融

| 站点 | 适用 |
|------|------|
| `xueqiu` | 雪球——股票讨论、行情 |
| `binance` | 加密货币交易 |
| `coingecko` | 加密货币行情 |
| `defillama` | DeFi 数据 |
| `barchart` | 期权/期货数据 |
| `yahoo-finance` | 美股行情 |
| `eastmoney` | 东方财富——A股数据 |
| `ths` | 同花顺 |

---

## 旅游

| 站点 | 适用 |
|------|------|
| `ctrip` | 携程——机票、酒店、目的地 |
| `booking` | Booking.com——全球酒店 |

**路由提示：** 中文旅行先搜 `doubao` 做粗检索，需要具体票务/酒店再补 `ctrip`。

---

## 其他

### 书籍 / 阅读

| 站点 | 适用 |
|------|------|
| `weread` | 微信读书——中文书籍搜索 |
| `weread-official` | 微信读书官方 API（需 API Key） |
| `zlibrary` | 电子书搜索 |

### 健康 / 医疗

| 站点 | 适用 |
|------|------|
| `pubmed` | 生物医学论文 |
| `openfda` | FDA 药品数据 |

### 实用工具

| 站点 | 适用 |
|------|------|
| `dictionary` | 英文词义、例句 |
| `youdao` | 有道翻译/词典 |
| `wttr` | 天气查询（命令行） |
| `rest-countries` | 国家信息 API |
| `oeis` | 整数序列百科 |

### 其他垂直站

| 站点 | 适用 |
|------|------|
| `dianping` | 大众点评——本地生活 |
| `flomo` | 浮墨笔记 |
| `mubu` | 幕布大纲笔记 |
| `band` | Band 社群 |
| `uisdc` | UI 设计社区 |
| `uiverse` | UI 组件库 |
| `web` | 通用网页抓取 |

### 未分类（按需探索）

以下站点不在上述分类中，当用户明确提及时可直接使用：

`12306`（火车票）、`aibase`（AI 日报）、`antigravity`（AI 编程）、`chaoxing`（学习通）、`discord-app`（Discord）、`flathub`（Linux 应用）、`gov-law`（法律法规）、`gov-policy`（政策文件）、`hf`（HuggingFace）、`jimeng`（即梦 AI）、`ke`（贝壳找房）、`linkedin-learning`、`maven`、`ones`、`onereason-frontend`、`opencode`、`paperreview`、`powerchina`、`quark`（夸克）、`sinablog`（新浪博客）、`tdx`（通达信）、`xiaoe`（小鹅通）、`yahoo`、`zhejianglab`
