"""
tools/factor_tool.py — 因子计算 Tool（简化版）

现在财务数字已经直接从 XBRL API 获取，这个 Tool 的职责变成：
1. 读取已有的结构化财务数据
2. 用 LLM 判断情绪/风险（这是 LLM 真正擅长的部分）
3. 对比季度变化趋势
"""

import os
import sys
import json
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_engine
from tools.filing_tool import query_filings, list_available_periods


def get_factors(ticker: str, period: str = None) -> dict:
    """直接从 filings 表读取结构化财务因子"""
    result = query_filings(ticker, query_type="period" if period else "latest", period=period)
    if result["status"] != "ok":
        return result
    return {
        "status": "ok",
        "ticker": result["ticker"],
        "period": result["period"],
        "revenue": result.get("revenue"),
        "revenue_growth_yoy": result.get("revenue_growth_yoy"),
        "gross_margin": result.get("gross_margin"),
        "net_income": result.get("net_income"),
        "rd_expense": result.get("rd_expense"),
    }


def compare_factors(ticker: str) -> dict:
    """对比最近两个季度的变化"""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT period, raw_text FROM filings WHERE ticker=:t ORDER BY period DESC LIMIT 2"),
            {"t": ticker}
        ).fetchall()

    if len(rows) < 2:
        return {"status": "insufficient_data", "message": "需要至少两个季度的数据"}

    def parse(row):
        d = json.loads(row[1]) if row[1] else {}
        return row[0], d

    p1, d1 = parse(rows[0])
    p2, d2 = parse(rows[1])

    def chg(new, old):
        if new is None or old is None:
            return "unknown"
        diff = new - old
        arrow = "↑" if diff > 0 else "↓"
        return f"{arrow} {diff:+.1f}"

    return {
        "status": "ok",
        "ticker": ticker,
        "latest_period": p1,
        "previous_period": p2,
        "revenue": {
            "latest": d1.get("revenue"),
            "previous": d2.get("revenue"),
            "change": chg(d1.get("revenue"), d2.get("revenue"))
        },
        "revenue_growth_yoy": {
            "latest": d1.get("revenue_growth_yoy"),
            "previous": d2.get("revenue_growth_yoy"),
        },
        "gross_margin": {
            "latest": d1.get("gross_margin"),
            "previous": d2.get("gross_margin"),
            "change": chg(d1.get("gross_margin"), d2.get("gross_margin"))
        },
    }


FACTOR_TOOL_SCHEMA = {
    "name": "get_financial_factors",
    "description": "获取公司结构化财务因子：营收、毛利率、净利润、研发支出、同比增速。数据直接来自 SEC XBRL，准确可靠。",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "股票代码，如 NVDA"},
            "period": {"type": "string", "description": "季度，如 2025-10-26，不填则取最新"}
        },
        "required": ["ticker"]
    }
}

COMPARE_TOOL_SCHEMA = {
    "name": "compare_quarterly_factors",
    "description": "对比最近两个季度的财务指标变化，判断趋势方向。",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "股票代码"}
        },
        "required": ["ticker"]
    }
}


if __name__ == "__main__":
    print("测试因子查询...")
    result = get_factors("NVDA")
    if result["status"] == "ok":
        rev = result.get("revenue")
        print(f"最新季度: {result['period']}")
        print(f"  营收:     ${rev/1e9:.1f}B" if rev else "  营收: N/A")
        print(f"  毛利率:   {result.get('gross_margin')}%")
        print(f"  同比增速: {result.get('revenue_growth_yoy')}%")
    else:
        print(result["message"])

    print("\n测试季度对比...")
    cmp = compare_factors("NVDA")
    if cmp["status"] == "ok":
        print(f"{cmp['previous_period']} → {cmp['latest_period']}")
        gm = cmp["gross_margin"]
        print(f"  毛利率: {gm['previous']}% → {gm['latest']}%  {gm['change']}")
    else:
        print(cmp["message"])

    print("\n✓ factor_tool 测试完成")
