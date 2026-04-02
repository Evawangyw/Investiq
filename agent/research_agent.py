"""
agent/research_agent.py — ReAct 投研 Agent（含反思循环）
"""

import os
import sys
import json
from datetime import datetime
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claude_client import agent_chat, simple_chat
from db import get_engine

from tools.filing_tool import query_filings, FILING_TOOL_SCHEMA
from tools.news_tool import search_news, get_recent_headlines, NEWS_TOOL_SCHEMA, HEADLINES_TOOL_SCHEMA
from tools.factor_tool import get_factors, compare_factors, FACTOR_TOOL_SCHEMA, COMPARE_TOOL_SCHEMA
from tools.competitor_tool import compare_with_competitors, COMPETITOR_TOOL_SCHEMA


ALL_TOOLS = [
    FILING_TOOL_SCHEMA,
    NEWS_TOOL_SCHEMA,
    HEADLINES_TOOL_SCHEMA,
    FACTOR_TOOL_SCHEMA,
    COMPARE_TOOL_SCHEMA,
    COMPETITOR_TOOL_SCHEMA,   # Week 3 新增
]


def tool_executor(tool_name: str, tool_input: dict):
    if tool_name == "query_sec_filing":
        return query_filings(
            ticker=tool_input.get("ticker", "NVDA"),
            query_type=tool_input.get("query_type", "latest"),
            period=tool_input.get("period")
        )
    elif tool_name == "search_news":
        return search_news(
            query=tool_input["query"],
            ticker=tool_input.get("ticker", "NVDA"),
            n_results=tool_input.get("n_results", 5),
            days_filter=tool_input.get("days_filter")
        )
    elif tool_name == "get_recent_headlines":
        return get_recent_headlines(
            ticker=tool_input.get("ticker", "NVDA"),
            n=tool_input.get("n", 10)
        )
    elif tool_name == "get_financial_factors":
        return get_factors(
            ticker=tool_input.get("ticker", "NVDA"),
            period=tool_input.get("period")
        )
    elif tool_name == "compare_quarterly_factors":
        return compare_factors(ticker=tool_input.get("ticker", "NVDA"))
    elif tool_name == "compare_with_competitors":
        return compare_with_competitors(
            primary_ticker=tool_input.get("primary_ticker", "NVDA"),
            competitors=tool_input.get("competitors", ["AMD", "INTC"])
        )
    else:
        return {"error": f"未知工具: {tool_name}"}


SYSTEM_PROMPT = """
你是一名专业的股票研究分析师，专注于科技股深度研究。

可用工具：
- query_sec_filing: 查询 SEC 财报
- get_financial_factors: 获取结构化财务因子
- compare_quarterly_factors: 对比季度变化趋势
- get_recent_headlines: 获取近期新闻标题
- search_news: 语义检索相关新闻
- compare_with_competitors: 与竞争对手横向对比财务指标

分析流程：
1. get_recent_headlines 了解近期事件
2. get_financial_factors + compare_quarterly_factors 看基本面趋势
3. compare_with_competitors 做竞品横向对比（这是区别普通报告的关键）
4. search_news 深挖具体话题
5. 必要时 query_sec_filing 查原始数据

输出报告格式（严格遵守）：
## 宏观背景
（行业趋势和市场环境，2-3句）

## 基本面分析
（必须包含具体数字：营收、毛利率、增速、与上季度对比）

## 竞品对比
（NVDA vs AMD vs INTC 的关键指标对比，体现相对竞争优势）

## 市场情绪
（近期新闻、分析师观点、重要事件）

## 核心分歧
（多空双方论点，每方至少3条，必须有数据支撑）

## 交易建议
（明确方向：看多/看空/中性 + 目标价区间 + 关键跟踪指标 + 止损条件）

要求：每个结论必须有数据或新闻支撑，交易建议必须明确。
"""

# ─────────────────────────────────────────────
# 反思循环（Week 3 新增核心功能）
# ─────────────────────────────────────────────

REFLECTION_PROMPT = """
你是一名严苛的投资研究主管，正在审阅下属分析师提交的研究报告初稿。

检查报告是否存在以下问题：
1. 关键结论缺乏具体数据支撑
2. 竞品对比是否完整
3. 多空论点是否平衡
4. 交易建议是否明确

请按以下格式输出，最多列出 2 个最重要的缺失点：

VERDICT: PASS 或 NEEDS_IMPROVEMENT

如果是 NEEDS_IMPROVEMENT：
MISSING:
- [最重要的缺失点1]
- [次重要的缺失点2]

SEARCH_SUGGESTIONS:
- [补充搜索关键词1]
- [补充搜索关键词2]

如果报告已经足够完整，只输出：
VERDICT: PASS

报告内容：
{report_draft}
"""


def reflect_on_report(report_draft: str) -> dict:
    """
    让第二个 LLM 调用审查报告初稿
    返回：{"pass": True} 或 {"pass": False, "missing": [...], "search_suggestions": [...]}
    """
    prompt = REFLECTION_PROMPT.format(report_draft=report_draft)
    feedback = simple_chat(prompt, system="你是严格的投资研究主管，只关注报告质量问题。")

    if "VERDICT: PASS" in feedback and "NEEDS_IMPROVEMENT" not in feedback:
        print("  ✓ 反思结果：报告通过审查")
        return {"pass": True}

    # 解析缺失点和搜索建议
    missing = []
    suggestions = []

    lines = feedback.split("\n")
    in_missing = False
    in_suggestions = False

    for line in lines:
        line = line.strip()
        if "MISSING:" in line:
            in_missing = True
            in_suggestions = False
        elif "SEARCH_SUGGESTIONS:" in line:
            in_missing = False
            in_suggestions = True
        elif line.startswith("- ") and in_missing:
            missing.append(line[2:])
        elif line.startswith("- ") and in_suggestions:
            suggestions.append(line[2:])

    print(f"  ✗ 反思结果：需要补充 {len(missing)} 处内容")
    for m in missing:
        print(f"    • {m}")

    return {"pass": False, "missing": missing, "search_suggestions": suggestions}


def run_research_agent(question: str, ticker: str = "NVDA", use_reflection: bool = True, on_tool_call=None) -> dict:
    """
    运行投研 Agent（含反思循环）

    流程：
    1. Agent 第一轮：调用工具收集信息，生成报告初稿
    2. Reflection：第二个 LLM 审查初稿，找出缺失
    3. Agent 第二轮（如需要）：针对缺失补充搜索，完善报告
    4. 保存最终报告
    """
    print(f"\n{'='*50}")
    print(f"问题: {question}")
    print(f"标的: {ticker}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    full_question = f"请分析 {ticker} 股票。具体问题：{question}"

    # ── 第一轮：生成初稿 ──
    print("\n【第一轮】生成报告初稿...")
    result = agent_chat(
        question=full_question,
        tools=ALL_TOOLS,
        tool_executor=tool_executor,
        system=SYSTEM_PROMPT,
        on_tool_call=on_tool_call
    )
    draft = result["answer"]
    all_tool_calls = result["tool_calls"]

    # ── 反思循环 ──
    final_report = draft
    if use_reflection:
        print("\n【反思循环】审查报告质量...")
        reflection = reflect_on_report(draft)

        if not reflection["pass"] and reflection.get("search_suggestions"):
            print("\n【第二轮】根据反思结果补充信息...")

            supplement_q = (
                f"你之前生成了一份关于 {ticker} 的分析报告，有以下内容需要补充：\n"
                + "\n".join(f"- {m}" for m in reflection["missing"][:2])
                + f"\n\n请用 2-3 次工具调用补充这些信息，然后输出完整的最终报告。"
                f"\n\n之前的初稿：\n{draft[:3000]}..."
            )

            result2 = agent_chat(
                question=supplement_q,
                tools=ALL_TOOLS,
                tool_executor=tool_executor,
                system=SYSTEM_PROMPT,
                max_steps=4,     # 限制第二轮最多4步
                on_tool_call=on_tool_call
            )
            final_report = result2["answer"]
            all_tool_calls += result2["tool_calls"]
            print(f"  第二轮工具调用：{len(result2['tool_calls'])} 次")

    # ── 打印摘要 ──
    print(f"\n{'─'*30}")
    print(f"工具调用总计：{len(all_tool_calls)} 次")
    for i, call in enumerate(all_tool_calls, 1):
        print(f"  {i}. {call['tool']}({list(call['input'].keys())})")

    # ── 保存报告 ──
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                INSERT INTO reports (ticker, question, content, tool_calls)
                VALUES (:ticker, :question, :content, :tool_calls)
                RETURNING id
            """),
            {
                "ticker": ticker,
                "question": question,
                "content": final_report,
                "tool_calls": json.dumps(all_tool_calls, ensure_ascii=False)
            }
        ).fetchone()
        conn.commit()
        report_id = row[0]

    print(f"\n✓ 报告已保存（ID: {report_id}）")
    print(f"{'='*50}\n")
    print(final_report)

    return {
        "answer": final_report,
        "tool_calls": all_tool_calls,
        "report_id": report_id
    }


def get_report_history(ticker: str = "NVDA", limit: int = 10) -> list:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, ticker, question, created_at FROM reports WHERE ticker=:ticker ORDER BY created_at DESC LIMIT :limit"),
            {"ticker": ticker, "limit": limit}
        ).fetchall()
    return [{"id": r[0], "ticker": r[1], "question": r[2], "created_at": str(r[3])} for r in rows]


def get_report_by_id(report_id: int) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM reports WHERE id=:id"),
            {"id": report_id}
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "ticker": row[1], "question": row[2],
        "content": row[3],
        "tool_calls": json.loads(row[4]) if row[4] else [],
        "created_at": str(row[5])
    }


if __name__ == "__main__":
    result = run_research_agent(
        question="基于最新财报、竞品对比和近期新闻，NVDA 当前估值是否合理？看多和看空的核心论点分别是什么？",
        ticker="NVDA",
        use_reflection=True
    )
    print(f"\n报告 ID: {result['report_id']}")
