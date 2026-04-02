"""
tools/competitor_tool.py — 竞品对比 Tool

从 SEC XBRL API 拉取竞品财务数据，和 NVDA 做横向对比。
Agent 在分析估值、市场份额、增速对比时会调用这个 Tool。

竞品列表：
- AMD  (CIK: 0000002488) — GPU 直接竞争对手
- INTC (CIK: 0000050863) — 数据中心芯片竞争对手
- QCOM (CIK: 0000804328) — AI 边缘计算竞争对手
"""

import os
import sys
import json
import requests
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_engine

HEADERS = {"User-Agent": "InvestIQ research@investiq.com", "Accept": "application/json"}

COMPETITORS = {
    "AMD":  "0000002488",
    "INTC": "0000050863",
    "QCOM": "0000804328",
    "GOOGL":"0001652044",
    "AMZN": "0001018724",
    "MSFT": "0000789019",
    "META": "0001326801",
    "SNAP": "0001564408",
    "F":    "0000037996",
    "GM":   "0000040987",
    "TSLA": "0001318605",
}


def get_cik(ticker: str) -> str:
    if ticker.upper() in COMPETITORS:
        return COMPETITORS[ticker.upper()]
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS)
    for item in resp.json().values():
        if item["ticker"].upper() == ticker.upper():
            return str(item["cik_str"]).zfill(10)
    raise ValueError(f"找不到 {ticker} 的 CIK")


def fetch_latest_metrics(ticker: str) -> dict:
    """
    获取某个竞品最近一个季度的核心财务指标
    """
    cik = get_cik(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    facts = resp.json()

    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    def get_latest(concept: str, unit: str = "USD"):
        data = us_gaap.get(concept, {}).get("units", {}).get(unit, [])
        # 只取季报，按结束日期排序
        quarterly = [d for d in data if d.get("form") in ("10-Q", "10-K") and d.get("end")]
        if not quarterly:
            return None, None
        latest = sorted(quarterly, key=lambda x: x["end"], reverse=True)[0]
        return latest.get("val"), latest.get("end")

    rev, rev_period = get_latest("Revenues")
    if not rev:
        rev, rev_period = get_latest("RevenueFromContractWithCustomerExcludingAssessedTax")

    gp, _  = get_latest("GrossProfit")
    ni, _  = get_latest("NetIncomeLoss")
    rd, _  = get_latest("ResearchAndDevelopmentExpense")

    # 计算毛利率
    gross_margin = round(gp / rev * 100, 1) if rev and gp else None

    # 净利率
    net_margin = round(ni / rev * 100, 1) if rev and ni else None

    return {
        "ticker": ticker,
        "period": rev_period,
        "revenue": rev,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "net_income": ni,
        "rd_expense": rd,
    }


def compare_with_competitors(primary_ticker: str = "NVDA", competitors: list = None) -> dict:
    """
    Agent 调用这个函数做竞品横向对比

    返回一个对比表，包含：
    - 营收规模对比
    - 毛利率对比（体现定价权差异）
    - 净利率对比（体现运营效率差异）
    - 研发投入对比（体现创新投入强度）
    """
    if competitors is None:
        competitors = ["AMD", "INTC"]

    # 获取主标的数据（从本地数据库）
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT period, raw_text FROM filings WHERE ticker=:t ORDER BY period DESC LIMIT 1"),
            {"t": primary_ticker}
        ).fetchone()

    primary_data = {"ticker": primary_ticker}
    if row:
        d = json.loads(row[1])
        primary_data.update({
            "period": row[0],
            "revenue": d.get("revenue"),
            "gross_margin": d.get("gross_margin"),
            "net_income": d.get("net_income"),
            "rd_expense": d.get("rd_expense"),
        })
        if primary_data["revenue"] and primary_data["net_income"]:
            primary_data["net_margin"] = round(
                primary_data["net_income"] / primary_data["revenue"] * 100, 1
            )

    # 获取竞品数据（从 EDGAR 实时拉取）
    results = [primary_data]
    for ticker in competitors:
        try:
            print(f"  获取 {ticker} 数据...")
            data = fetch_latest_metrics(ticker)
            results.append(data)
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})

    # 生成对比分析
    def fmt_revenue(v):
        if not v:
            return "N/A"
        if v >= 1e9:
            return f"${v/1e9:.1f}B"
        return f"${v/1e6:.0f}M"

    comparison_table = []
    for r in results:
        comparison_table.append({
            "ticker": r["ticker"],
            "period": r.get("period", "N/A"),
            "revenue": fmt_revenue(r.get("revenue")),
            "gross_margin": f"{r.get('gross_margin')}%" if r.get("gross_margin") else "N/A",
            "net_margin": f"{r.get('net_margin')}%" if r.get("net_margin") else "N/A",
            "rd_expense": fmt_revenue(r.get("rd_expense")),
        })

    # 计算 NVDA 相对优势
    insights = []
    primary = results[0]
    for comp in results[1:]:
        if comp.get("gross_margin") and primary.get("gross_margin"):
            diff = primary["gross_margin"] - comp["gross_margin"]
            insights.append(
                f"{primary_ticker} 毛利率比 {comp['ticker']} 高 {diff:.1f}ppt"
                if diff > 0 else
                f"{primary_ticker} 毛利率比 {comp['ticker']} 低 {abs(diff):.1f}ppt"
            )
        if comp.get("revenue") and primary.get("revenue"):
            ratio = primary["revenue"] / comp["revenue"]
            insights.append(f"{primary_ticker} 营收是 {comp['ticker']} 的 {ratio:.1f}x")

    return {
        "status": "ok",
        "primary": primary_ticker,
        "competitors": competitors,
        "comparison_table": comparison_table,
        "insights": insights
    }


# ── 工具定义 ──
COMPETITOR_TOOL_SCHEMA = {
    "name": "compare_with_competitors",
    "description": (
        "与竞争对手进行财务指标横向对比，包括营收规模、毛利率、净利率、研发投入。"
        "适合回答'NVDA 相比 AMD 估值是否合理'、'竞争格局如何'等问题。"
        "可对比的竞品：AMD、INTC、QCOM。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "primary_ticker": {
                "type": "string",
                "description": "主要分析标的，如 NVDA"
            },
            "competitors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "竞品列表，如 ['AMD', 'INTC']"
            }
        },
        "required": ["primary_ticker"]
    }
}


if __name__ == "__main__":
    print("测试竞品对比...")
    result = compare_with_competitors("NVDA", ["AMD", "INTC"])

    if result["status"] == "ok":
        print("\n对比表：")
        for row in result["comparison_table"]:
            print(f"  {row['ticker']:<6} | 营收: {row['revenue']:<12} | 毛利率: {row['gross_margin']:<8} | 净利率: {row['net_margin']:<8} | 研发: {row['rd_expense']}")

        print("\n关键洞察：")
        for insight in result["insights"]:
            print(f"  • {insight}")
    else:
        print(result)

    print("\n✓ competitor_tool 测试完成")
