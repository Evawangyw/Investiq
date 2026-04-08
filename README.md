# InvestIQ — AI 投资研究 Agent

> 基于 ReAct 架构的自主投研 Agent，能够自主规划工具调用路径、进行人机协同审查，产出机构级研究报告。

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-purple) ![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)

---

## 系统架构

```
用户问题
    ↓
ReAct Agent（Claude Sonnet 4.6）
    ↓ 自主规划工具调用顺序
    ├── SEC 财报查询       → SEC EDGAR XBRL API → PostgreSQL
    ├── 提取财务因子       → 结构化营收/毛利率/增速指标
    ├── 对比季度趋势       → 环比/同比变化分析
    ├── 浏览近期新闻       → Chroma 向量数据库
    ├── 语义检索新闻       → 余弦相似度匹配
    └── 竞品横向对比       → 实时拉取同行 SEC 数据
    ↓
反思循环（Reflection Loop）
    ↓ 第二个 LLM 审查报告初稿，输出结构化缺口分析
    ↓ ── 人机协同检查点 ──
    ↓ 用户选择：继续深化研究 / 直接使用初稿
    ↓ 如继续：针对缺失触发第二轮工具调用
    ↓
结构化研究报告（含执行摘要 + 6大分析模块）
    ↓
Streamlit Dashboard（实时行情 + 图表 + 报告管理）
```

---

## 核心功能

### 🤖 ReAct Agent
- 接受自然语言投研问题，自主规划工具调用路径
- 每份报告调用 8–12 次工具，覆盖财务、新闻、竞品三类数据源
- 实时显示每步操作的中文可读进度（"语义检索新闻 → 搜索词：出口管制"），而非原始 JSON

### 🔄 反思循环 + 人机协同
- 初稿生成后，第二个 LLM 扮演"严苛主管"审查报告质量
- 自动识别：缺少数据支撑、竞品对比不完整、多空论点失衡
- **人机协同检查点**：将审查结论呈现给用户，由用户决定是否继续补充研究，而非全自动运行

### 📊 数据层
- **SEC XBRL API**：结构化财务数据（营收、毛利率、净利润、研发支出）
- **Yahoo Finance**：实时股价、PE、市值、52周区间（5分钟缓存）
- **NewsAPI + Chroma**：新闻抓取 + 向量语义检索

### 📈 Dashboard
- 实时行情卡片（股价、PE、预期PE、市值）
- 营收 & 毛利率趋势图，竞品雷达图
- 新闻列表 / 话题聚类 / LLM 市场情绪分析
- 历史报告管理，按标的分类查看
- 支持任意股票代码（预设 + 自定义输入）

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| LLM | Claude Sonnet 4.6 | Agent 推理 + 反思审查 |
| 向量数据库 | Chroma | 新闻语义存储与检索 |
| 关系型数据库 | PostgreSQL | 财报数据 + 报告存储 |
| 行情数据 | Yahoo Finance (yfinance) | 实时股价、PE、市值 |
| 财务数据 | SEC EDGAR XBRL API | 结构化季报数据（免费） |
| 新闻 | NewsAPI | 实时新闻抓取（可选） |
| 前端 | Streamlit + Plotly | Dashboard + 交互可视化 |

---

## 项目结构

```
investiq/
├── app.py                  # Streamlit Dashboard（含内置设置向导）
├── claude_client.py        # Claude API 封装 + ReAct 循环
├── db.py                   # PostgreSQL 连接 + 表结构初始化
├── vector_store.py         # Chroma 向量数据库封装
├── setup_check.py          # 命令行环境验证（可选）
├── requirements.txt
├── tools/
│   ├── filing_tool.py      # SEC EDGAR 财报查询
│   ├── news_tool.py        # 新闻抓取 + 语义检索
│   ├── factor_tool.py      # 结构化财务因子提取
│   └── competitor_tool.py  # 竞品横向对比
└── agent/
    └── research_agent.py   # ReAct Agent + 反思循环 + 人机协同接口
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备 PostgreSQL

确保本地 PostgreSQL 已运行，并创建数据库：

```bash
psql -U postgres -c "CREATE DATABASE investiq;"
```

### 3. 启动应用

```bash
streamlit run app.py
```

打开 `http://localhost:8501`，应用会自动检测配置状态并显示**设置向导**。

---

## 设置向导（首次启动）

第一次运行时，应用会自动进入三步初始化流程，无需手动执行任何脚本。

### 第一步：配置 API 密钥

向导提供**在线表单**，直接填写后点击保存，会自动写入 `.env` 文件：

| 字段 | 来源 | 是否必填 |
|------|------|------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | ✅ 必填 |
| `DB_HOST / PORT / NAME / USER / PASSWORD` | 本地 PostgreSQL 配置 | ✅ 必填 |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org)（免费注册） | 可选 |

也可以手动创建 `.env` 文件：

```
ANTHROPIC_API_KEY=sk-ant-api03-...

DB_HOST=localhost
DB_PORT=5432
DB_NAME=investiq
DB_USER=postgres
DB_PASSWORD=your_password

NEWS_API_KEY=your_newsapi_key   # 可选，不填则跳过新闻功能
TARGET_TICKER=NVDA
```

### 第二步：初始化数据库

点击向导中的"初始化数据库表"按钮，自动创建以下三张表：

- `filings` — SEC 季报原始数据
- `factors` — LLM 提炼的结构化财务因子
- `reports` — Agent 生成的研究报告

### 第三步：拉取初始数据

选择第一个要分析的股票，点击**"⚡ 一键初始化"**，自动完成：

1. 从 SEC EDGAR 拉取最近 6 个季度财报
2. 拉取近 25 天新闻（需要 NEWS_API_KEY）

完成后点击"进入 InvestIQ"即可开始使用。

---

## 添加新标的

进入应用后，在侧边栏点击**"➕ 初始化新标的"**，重新进入数据拉取步骤，选择新股票代码后一键拉取。

也可以直接使用侧边栏的"📊 刷新财报"和"🔄 刷新新闻"按钮对当前标的更新数据。

---

## 关键设计决策

**为什么用两层推理而不是直接 RAG？**

直接把原文喂给 LLM 效果差。第一层先把财报文本转成结构化因子（营收增速、毛利率、管理层措辞），第二层才让 LLM 做跨源推理。信噪比更高，报告质量显著提升。

**为什么用 XBRL API 而不是解析财报 HTML？**

SEC 的 HTML 财报结构复杂，解析容易出错。XBRL API 直接返回结构化 JSON，数据准确，不需要任何 HTML 解析。

**反思循环为什么设计成人机协同而非全自动？**

投资决策高风险，全自动补充研究可能引入偏差而用户无从察觉。将审查结论透明地呈现给用户，由用户决定是否继续，既保留了 Agent 的智能，也保留了人的判断权。这也更真实地模拟了"分析师初稿 → 主管审阅 → 决定是否返工"的实际流程。

**为什么用 Chroma 存新闻而不是 PostgreSQL？**

新闻检索需要语义匹配，不是关键词匹配。问"数据中心需求放缓"能找到标题写"cloud infrastructure spending decline"的文章。PostgreSQL 的 LIKE 查询做不到这一点。

---

## 已知局限

- NewsAPI 免费账号只能查近 30 天新闻，每天 100 次请求上限；无 API key 时新闻功能不可用，但财报分析不受影响
- 竞品数据实时从 SEC 拉取，网络较慢时可能超时
- 报告质量依赖新闻数据库覆盖度，建议每天通过侧边栏"一键全部刷新"保持数据新鲜

---

## 后续计划

- [ ] 每日自动日报（定时调度 Agent）
- [ ] 多 Agent 分工架构（财务 Agent / 新闻 Agent / 综合 Agent）
- [ ] 报告导出 PDF
- [ ] 扩展数据源（SEC 8-K 重大事件、期权情绪）
