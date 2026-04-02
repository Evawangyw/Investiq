# InvestIQ — AI Investment Research Agent

> 基于 ReAct 架构的自主投资研究 Agent，能够自主规划工具调用路径，产出机构级研究报告。

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-purple) ![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)

---

## 系统架构

```
用户问题
    ↓
ReAct Agent（Claude Sonnet 4.6）
    ↓ 自主规划工具调用顺序
    ├── query_sec_filing      → SEC EDGAR XBRL API → PostgreSQL
    ├── get_financial_factors → 结构化财务因子
    ├── compare_quarterly_factors → 季度趋势对比
    ├── get_recent_headlines  → Chroma 向量数据库
    ├── search_news           → 语义检索（余弦相似度）
    └── compare_with_competitors → 竞品横向对比
    ↓
反思循环（Reflection）
    ↓ 第二个 LLM 审查报告初稿
    ↓ 发现不足 → 触发第二轮工具调用
    ↓
结构化研究报告
    ↓
Streamlit Dashboard
```

---

## 核心功能

### 🤖 ReAct Agent
- 接受自然语言投研问题，自主规划工具调用路径
- 8-12 次工具调用产出一份完整报告
- 实时显示每步工具调用日志

### 🔄 反思循环（Reflection）
- 生成初稿后，第二个 LLM 调用审查报告质量
- 自动识别：缺少数据支撑、竞品对比不完整、多空论点失衡
- 针对缺失自动补充工具调用，产出最终版本

### 📊 数据层
- **SEC XBRL API**：直接获取结构化财务数据（营收、毛利率、净利润、研发支出）
- **NewsAPI**：实时新闻抓取，存入 Chroma 向量数据库
- **语义检索**：用 Embedding 做语义匹配，找到真正相关的新闻

### 📈 Dashboard（Streamlit）
- 营收 & 毛利率趋势折线图
- 竞品对比雷达图（动态切换对比对象）
- 新闻概览：列表 / 话题聚类 / 市场情绪分析
- 历史报告管理，按标的分类
- 一键刷新数据
- 多标的支持（NVDA、AMD、MSFT、TSLA、META）

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| LLM | Claude Sonnet 4.6 | Agent 推理 + 反思循环 |
| 向量数据库 | Chroma | 新闻语义存储与检索 |
| 关系型数据库 | PostgreSQL | 财报数据 + 报告存储 |
| 数据来源 | SEC EDGAR XBRL API | 结构化财务数据（免费） |
| 新闻 | NewsAPI | 实时新闻抓取 |
| 前端 | Streamlit + Plotly | Dashboard |

---

## 项目结构

```
investiq/
├── app.py                  # Streamlit Dashboard
├── claude_client.py        # Claude API + ReAct 循环
├── db.py                   # PostgreSQL 连接 + 表结构
├── vector_store.py         # Chroma 向量数据库封装
├── setup_check.py          # 环境验证
├── tools/
│   ├── filing_tool.py      # SEC EDGAR 财报查询
│   ├── news_tool.py        # 新闻抓取 + 语义检索
│   ├── factor_tool.py      # 结构化财务因子
│   └── competitor_tool.py  # 竞品横向对比
└── agent/
    └── research_agent.py   # ReAct Agent + 反思循环
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```
ANTHROPIC_API_KEY=sk-ant-api03-...   # console.anthropic.com
NEWS_API_KEY=...                      # newsapi.org（免费）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=investiq
DB_USER=你的用户名
DB_PASSWORD=
TARGET_TICKER=NVDA
TARGET_COMPANY=NVIDIA
```

### 3. 初始化数据库

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE investiq;"

# 验证所有组件
python setup_check.py
```

### 4. 拉取初始数据

```bash
# 财报数据
python -m tools.filing_tool

# 新闻数据
python3 -c "from tools.news_tool import fetch_and_store_news; fetch_and_store_news(days_back=25)"
```

### 5. 启动 Dashboard

```bash
streamlit run app.py
```

打开 `http://localhost:8501`

---

## 关键设计决策

**为什么用两层推理而不是直接 RAG？**

直接把原文喂给 LLM 效果差。第一层先把财报文本转成结构化因子（营收增速、毛利率、管理层措辞），第二层才让 LLM 做跨源推理。信噪比更高，报告质量显著提升。

**为什么用 XBRL API 而不是解析财报 HTML？**

SEC 的 HTML 财报结构复杂，解析容易出错（经历过：拉到的是法律套话而不是财务数据）。XBRL API 直接返回结构化 JSON，数据准确，不需要任何 HTML 解析。

**反思循环为什么有价值？**

真实投研流程是"分析师写初稿 → 主管审阅 → 返回修改"。反思循环用代码实现了这个流程：第二个 LLM 扮演严苛主管，检查论据是否充分、竞品对比是否完整、多空是否平衡，不足则触发第二轮工具调用补充。

**为什么用 Chroma 存新闻而不是 PostgreSQL？**

新闻检索需要语义匹配，不是关键词匹配。问"数据中心需求放缓"能找到标题写"cloud infrastructure spending decline"的文章。PostgreSQL 的 LIKE 查询做不到这一点。

---

## 已知局限性

- NewsAPI 免费账号只能查近 30 天新闻，且每天 100 次请求上限
- 竞品数据实时从 SEC 拉取，网络较慢时可能超时
- 报告质量依赖新闻数据库的覆盖度，建议每天定时刷新新闻

---

## 后续计划

- [ ] 每日自动生成日报（定时任务）
- [ ] 报告导出 PDF
- [ ] 扩展更多数据源（SEC 8-K 重大事件、期权情绪）
- [ ] 支持自定义标的和竞品组合
