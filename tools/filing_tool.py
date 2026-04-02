"""
tools/filing_tool.py — SEC EDGAR 财报查询 Tool

改用 XBRL Financial Data API，直接获取结构化财务数据
不需要解析 HTML，数据更准确可靠
"""

import os
import sys
import json
import requests
import time
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_engine

HEADERS = {"User-Agent": "InvestIQ research@investiq.com", "Accept": "application/json"}
TICKER = os.getenv("TARGET_TICKER", "NVDA")


def get_cik(ticker: str) -> str:
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS)
    data = resp.json()
    for item in data.values():
        if item["ticker"].upper() == ticker.upper():
            return str(item["cik_str"]).zfill(10)
    raise ValueError(f"找不到 {ticker} 的 CIK")


def fetch_xbrl_facts(cik: str) -> dict:
    """
    从 SEC XBRL API 获取所有财务数据
    返回结构化 JSON，包含历史上所有季度的财务指标
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    return resp.json()


def extract_quarterly_metrics(facts: dict, ticker: str) -> list:
    """
    从 XBRL facts 中提取关键季度财务指标
    返回按季度整理的数据列表
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    def get_quarterly_values(concept: str, unit: str = "USD") -> dict:
        """提取某个财务概念的季度数据，返回 {period: value} 字典"""
        data = us_gaap.get(concept, {}).get("units", {}).get(unit, [])
        result = {}
        for item in data:
            # 只要季报（10-Q）和年报（10-K），过滤掉其他
            if item.get("form") in ("10-Q", "10-K") and item.get("frame"):
                frame = item["frame"]  # 如 CY2025Q3I 或 CY2024Q3
                end = item.get("end", "")
                result[end] = item.get("val", 0)
        return result

    # 提取关键指标
    revenues     = get_quarterly_values("Revenues")
    if not revenues:
        revenues = get_quarterly_values("RevenueFromContractWithCustomerExcludingAssessedTax")
    gross_profit = get_quarterly_values("GrossProfit")
    net_income   = get_quarterly_values("NetIncomeLoss")
    rd_expense   = get_quarterly_values("ResearchAndDevelopmentExpense")

    # 整合所有有营收数据的季度
    quarters = sorted(revenues.keys(), reverse=True)[:6]  # 最近6个季度

    results = []
    for i, period in enumerate(quarters):
        rev = revenues.get(period)
        gp  = gross_profit.get(period)
        ni  = net_income.get(period)

        # 计算同比增速（需要4个季度前的数据）
        yoy_revenue_growth = None
        if i + 4 < len(quarters):
            prev_period = quarters[i + 4]
            prev_rev = revenues.get(prev_period)
            if prev_rev and prev_rev != 0 and rev:
                yoy_revenue_growth = round((rev - prev_rev) / prev_rev * 100, 1)

        # 计算毛利率
        gross_margin = None
        if rev and gp and rev != 0:
            gross_margin = round(gp / rev * 100, 1)

        results.append({
            "ticker": ticker,
            "period": period,
            "revenue": rev,
            "gross_profit": gp,
            "net_income": ni,
            "rd_expense": rd_expense.get(period),
            "revenue_growth_yoy": yoy_revenue_growth,
            "gross_margin": gross_margin,
        })

    return results


def fetch_and_store_filings(ticker: str = TICKER, form_type: str = "10-Q", count: int = 4):
    """
    主函数：通过 XBRL API 获取财务数据并存库
    """
    print(f"正在从 XBRL API 获取 {ticker} 财务数据...")

    engine = get_engine()
    cik = get_cik(ticker)
    print(f"  CIK: {cik}")

    facts = fetch_xbrl_facts(cik)
    print(f"  ✓ 获取到 XBRL 数据")

    metrics = extract_quarterly_metrics(facts, ticker)
    print(f"  找到 {len(metrics)} 个季度的数据\n")

    for m in metrics:
        period = m["period"]

        # 把结构化数据存为 raw_text（JSON格式）
        raw_json = json.dumps(m, ensure_ascii=False)

        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO filings (ticker, form_type, period, filed_at, raw_text)
                    VALUES (:ticker, :form_type, :period, :filed_at, :raw_text)
                    ON CONFLICT (ticker, form_type, period) DO UPDATE SET
                        raw_text = EXCLUDED.raw_text
                """),
                {
                    "ticker": ticker,
                    "form_type": "10-Q",
                    "period": period,
                    "filed_at": period,
                    "raw_text": raw_json
                }
            )
            conn.commit()

        rev_b = f"${m['revenue']/1e9:.1f}B" if m['revenue'] else "N/A"
        gm    = f"{m['gross_margin']}%" if m['gross_margin'] else "N/A"
        yoy   = f"{m['revenue_growth_yoy']}%" if m['revenue_growth_yoy'] else "N/A"
        print(f"  {period} | 营收: {rev_b} | 毛利率: {gm} | 同比增速: {yoy}")

    print(f"\n✓ 完成！共存入 {len(metrics)} 个季度")
    return metrics


def query_filings(ticker: str, query_type: str = "latest", period: str = None) -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        if query_type == "latest":
            row = conn.execute(
                text("SELECT ticker, form_type, period, filed_at, raw_text FROM filings WHERE ticker=:ticker ORDER BY period DESC LIMIT 1"),
                {"ticker": ticker}
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT ticker, form_type, period, filed_at, raw_text FROM filings WHERE ticker=:ticker AND period=:period LIMIT 1"),
                {"ticker": ticker, "period": period}
            ).fetchone()

    if not row:
        return {"status": "not_found", "message": f"没有 {ticker} 的数据"}

    data = json.loads(row[4]) if row[4] else {}
    return {"status": "ok", "ticker": row[0], "form_type": row[1], "period": row[2], "filed_at": str(row[3]), **data}


def list_available_periods(ticker: str) -> list:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT form_type, period, filed_at FROM filings WHERE ticker=:t ORDER BY period DESC"),
            {"t": ticker}
        ).fetchall()
    return [{"form_type": r[0], "period": r[1], "filed_at": str(r[2])} for r in rows]


FILING_TOOL_SCHEMA = {
    "name": "query_sec_filing",
    "description": "查询公司的季度财务数据，包含营收、毛利率、净利润、研发支出、同比增速等结构化指标。数据来自 SEC XBRL API，准确可靠。",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "股票代码，如 NVDA"},
            "query_type": {"type": "string", "enum": ["latest", "period"], "description": "latest=最新，period=指定季度"},
            "period": {"type": "string", "description": "当 query_type=period 时填写，格式如 2025-10-26"}
        },
        "required": ["ticker", "query_type"]
    }
}


if __name__ == "__main__":
    metrics = fetch_and_store_filings(ticker="NVDA")

    print("\nStep 2: 测试查询...")
    result = query_filings("NVDA", "latest")
    if result["status"] == "ok":
        print(f"最新季度: {result['period']}")
        print(f"营收: ${result.get('revenue', 0)/1e9:.1f}B")
        print(f"毛利率: {result.get('gross_margin')}%")
        print(f"同比增速: {result.get('revenue_growth_yoy')}%")
    
    print("\n✓ filing_tool 测试完成")
