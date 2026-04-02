"""
tools/news_tool.py — 新闻抓取 + 语义检索 Tool

两件事：
1. fetch_and_store_news() — 从 NewsAPI 拉取新闻，存入 Chroma 向量数据库
2. search_news()          — 语义检索新闻，这个函数会被 Agent 调用

运行测试：python -m tools.news_tool
"""

import os
import sys
import hashlib
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vector_store import add_documents, query_documents

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
TICKER = os.getenv("TARGET_TICKER", "NVDA")
COMPANY = os.getenv("TARGET_COMPANY", "NVIDIA")


# ─────────────────────────────────────────────
# Part 1: 拉取新闻并存入 Chroma
# ─────────────────────────────────────────────

def fetch_and_store_news(query: str = None, days_back: int = 30, page_size: int = 50, ticker: str = None):
    """
    从 NewsAPI 拉取新闻并存入 Chroma
    
    - query     搜索关键词，默认结合 ticker 生成
    - days_back 往前拉几天的新闻，免费账号最多30天
    - page_size 每次最多拉多少条，免费账号上限100
    - ticker    写入元数据的标的代码；默认用环境变量 TARGET_TICKER
    """
    if not NEWS_API_KEY:
        raise ValueError("缺少 NEWS_API_KEY，请在 .env 里配置")

    sym = (ticker or TICKER).upper()
    if query is None:
        query = f"{sym} OR stock OR earnings"
    
    # 计算日期范围
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    print(f"拉取新闻: {query}")
    print(f"时间范围: {from_date} 到 {to_date}")
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": page_size,
        "apiKey": NEWS_API_KEY
    }
    
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    
    if data.get("status") != "ok":
        raise ValueError(f"NewsAPI 错误: {data.get('message', '未知错误')}")
    
    articles = data.get("articles", [])
    print(f"获取到 {len(articles)} 篇文章")
    
    if not articles:
        print("没有找到相关新闻")
        return 0
    
    # 处理并存入 Chroma
    texts, metadatas, ids = [], [], []
    
    for article in articles:
        # 拼接标题 + 摘要作为存储文本
        title = article.get("title") or ""
        description = article.get("description") or ""
        content = article.get("content") or ""
        
        # 过滤掉空内容
        full_text = f"{title}. {description} {content[:500]}".strip()
        if len(full_text) < 30:
            continue
        
        # 用 URL 的 hash 作为唯一 ID，避免重复存储
        url_hash = hashlib.md5((article.get("url") or full_text).encode()).hexdigest()[:16]
        doc_id = f"news_{sym}_{url_hash}"
        
        published_at = article.get("publishedAt", "")[:10]  # 只取日期部分
        
        texts.append(full_text)
        metadatas.append({
            "ticker": sym,
            "source": article.get("source", {}).get("name", "unknown"),
            "date": published_at,
            "url": article.get("url", ""),
            "title": title[:100]
        })
        ids.append(doc_id)
    
    if texts:
        add_documents(texts, metadatas, ids, collection_name="investiq_news")
        print(f"✓ 存入 {len(texts)} 篇新闻到 Chroma")
    
    return len(texts)


# ─────────────────────────────────────────────
# Part 2: Agent 调用的语义检索函数
# ─────────────────────────────────────────────

def search_news(query: str, ticker: str = TICKER, n_results: int = 5, days_filter: int = None) -> dict:
    """
    Agent 调用这个函数做语义检索
    
    参数：
    - query       自然语言查询，如 "NVIDIA 数据中心业务增长"
    - ticker      过滤特定股票的新闻
    - n_results   返回几条
    - days_filter 只看最近几天，None 表示不过滤
    
    返回最相关的新闻列表，按相关度排序
    """
    # 构建 Chroma 的元数据过滤条件
    where = {"ticker": ticker}
    
    results = query_documents(
        query=query,
        n_results=n_results,
        collection_name="investiq_news",
        where=where
    )
    
    if not results:
        return {
            "status": "not_found",
            "message": f"没有找到关于 {ticker} 的相关新闻，请先运行 fetch_and_store_news()"
        }
    
    # 如果要过滤日期，在返回结果里做筛选
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        results = [r for r in results if r["metadata"].get("date", "") >= cutoff]
    
    # 格式化返回给 Agent 的内容
    formatted = []
    for r in results:
        formatted.append({
            "title": r["metadata"].get("title", ""),
            "date": r["metadata"].get("date", ""),
            "source": r["metadata"].get("source", ""),
            "text": r["text"][:600],          # 控制 token 用量
            "relevance": round(1 - r["distance"], 3)  # 转成相关度分数，越高越相关
        })
    
    return {
        "status": "ok",
        "query": query,
        "ticker": ticker,
        "count": len(formatted),
        "articles": formatted
    }


def get_recent_headlines(ticker: str = TICKER, n: int = 10) -> dict:
    """
    获取最近 n 条新闻标题，让 Agent 了解近期有什么重要事件
    用于 Agent 规划阶段：先看看最近发生了什么，再决定深挖哪个方向
    """
    results = query_documents(
        query=f"{ticker} latest news earnings revenue",
        n_results=n,
        collection_name="investiq_news",
        where={"ticker": ticker}
    )
    
    if not results:
        return {"status": "not_found", "message": "暂无新闻数据"}
    
    # 按日期排序
    sorted_results = sorted(results, key=lambda x: x["metadata"].get("date", ""), reverse=True)
    
    headlines = []
    for r in sorted_results:
        headlines.append({
            "date": r["metadata"].get("date", ""),
            "title": r["metadata"].get("title", ""),
            "source": r["metadata"].get("source", "")
        })
    
    return {"status": "ok", "ticker": ticker, "headlines": headlines}


# ── 工具定义（注册给 Claude 用的 schema）──
NEWS_TOOL_SCHEMA = {
    "name": "search_news",
    "description": (
        "语义检索公司相关新闻。根据查询内容返回最相关的新闻文章，"
        "适合回答关于市场情绪、近期事件、分析师观点、竞争动态的问题。"
        "比关键词搜索更智能，能理解语义相关性。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询，如 'NVIDIA 数据中心需求前景' 或 '市场对 AI 芯片的担忧'"
            },
            "ticker": {
                "type": "string",
                "description": "股票代码，如 NVDA"
            },
            "n_results": {
                "type": "integer",
                "description": "返回条数，默认5，最多10",
                "default": 5
            },
            "days_filter": {
                "type": "integer",
                "description": "只看最近几天的新闻，不填则不限制"
            }
        },
        "required": ["query", "ticker"]
    }
}

HEADLINES_TOOL_SCHEMA = {
    "name": "get_recent_headlines",
    "description": "获取某股票最近的新闻标题列表，用于快速了解近期有哪些重要事件，再决定深入调查哪个方向。",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "股票代码"},
            "n": {"type": "integer", "description": "条数，默认10", "default": 10}
        },
        "required": ["ticker"]
    }
}


# ── 直接运行 = 拉取数据 + 测试检索 ──
if __name__ == "__main__":
    print("=" * 40)
    print("Step 1: 拉取 NVDA 新闻")
    print("=" * 40)
    count = fetch_and_store_news(days_back=30)
    
    print("\n" + "=" * 40)
    print("Step 2: 测试语义检索")
    print("=" * 40)
    
    test_queries = [
        "NVIDIA data center revenue growth",
        "AI chip demand outlook",
        "NVIDIA earnings beat expectations"
    ]
    
    for q in test_queries:
        print(f"\n查询: {q}")
        result = search_news(q, n_results=2)
        if result["status"] == "ok":
            for article in result["articles"]:
                print(f"  [{article['relevance']}] {article['date']} | {article['title'][:60]}")
        else:
            print(f"  {result['message']}")
    
    print("\n" + "=" * 40)
    print("Step 3: 测试最近标题")
    print("=" * 40)
    headlines = get_recent_headlines("NVDA", n=5)
    if headlines["status"] == "ok":
        for h in headlines["headlines"]:
            print(f"  {h['date']} | {h['source'][:15]:<15} | {h['title'][:55]}")
    
    print("\n✓ Day 5-6 完成")
