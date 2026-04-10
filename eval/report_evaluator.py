"""
eval/report_evaluator.py — 报告质量评估模块

对生成的研究报告按 5 个维度打分（每项 1–5 分，满分 25 分）。
使用第二个 LLM 调用（simple_chat）评估，与反思循环独立运行。
"""

import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from claude_client import simple_chat


# ── 5 个评估维度定义 ──
EVAL_DIMENSIONS = [
    {
        "key": "data_support",
        "label": "数据支撑",
        "description": "每个关键结论是否引用了具体数字（营收金额、毛利率百分比、同比增速等）",
    },
    {
        "key": "competitor_coverage",
        "label": "竞品对比",
        "description": "竞品对比部分是否涵盖至少 2 家同行，并给出可比较的具体财务指标",
    },
    {
        "key": "bull_bear_balance",
        "label": "多空平衡",
        "description": "多空双方各自是否列出至少 3 条独立论点，且每条均有数据或事件支撑",
    },
    {
        "key": "trade_clarity",
        "label": "交易建议",
        "description": "是否明确给出方向（看多/看空/中性）、目标价区间、关键跟踪指标与止损条件",
    },
    {
        "key": "news_corroboration",
        "label": "新闻佐证",
        "description": "市场情绪结论是否援引了具体近期新闻事件或分析师观点（而非泛泛而谈）",
    },
]

_GRADE_MAP = [
    (23, "A"),
    (20, "B+"),
    (17, "B"),
    (14, "C+"),
    (11, "C"),
    (0,  "D"),
]


def _total_to_grade(total: int) -> str:
    for threshold, grade in _GRADE_MAP:
        if total >= threshold:
            return grade
    return "D"


EVAL_PROMPT_TEMPLATE = """
你是一名投资研究报告质量审核员。请对以下研究报告按 5 个维度严格评分（每项 1–5 分）。

评分标准（每项）：
5 = 完全满足，有充分证据
4 = 基本满足，有小瑕疵
3 = 部分满足，明显不足
2 = 勉强涉及，缺乏实质内容
1 = 完全缺失或严重不足

5 个评估维度：
1. data_support（数据支撑）：{dim_data_support}
2. competitor_coverage（竞品对比）：{dim_competitor_coverage}
3. bull_bear_balance（多空平衡）：{dim_bull_bear_balance}
4. trade_clarity（交易建议）：{dim_trade_clarity}
5. news_corroboration（新闻佐证）：{dim_news_corroboration}

请严格按以下 JSON 格式输出，不要输出任何其他内容：

{{
  "scores": {{
    "data_support":       {{"score": <1-5>, "comment": "<一句中文评语，20字以内>"}},
    "competitor_coverage":{{"score": <1-5>, "comment": "<一句中文评语，20字以内>"}},
    "bull_bear_balance":  {{"score": <1-5>, "comment": "<一句中文评语，20字以内>"}},
    "trade_clarity":      {{"score": <1-5>, "comment": "<一句中文评语，20字以内>"}},
    "news_corroboration": {{"score": <1-5>, "comment": "<一句中文评语，20字以内>"}}
  }},
  "summary": "<整体评价，50字以内>"
}}

---
待评估报告（标的：{ticker}）：

{report_content}
"""


def evaluate_report(report_content: str, ticker: str = "") -> dict:
    """
    对报告进行质量评估。

    返回：
    {
        "scores": {
            "data_support":        {"score": int, "comment": str},
            "competitor_coverage": {"score": int, "comment": str},
            "bull_bear_balance":   {"score": int, "comment": str},
            "trade_clarity":       {"score": int, "comment": str},
            "news_corroboration":  {"score": int, "comment": str},
        },
        "total":   int,   # 5–25
        "grade":   str,   # A / B+ / B / C+ / C / D
        "summary": str,
    }
    如果 LLM 输出无法解析，返回 {"error": str}。
    """
    dim = {d["key"]: d["description"] for d in EVAL_DIMENSIONS}

    prompt = EVAL_PROMPT_TEMPLATE.format(
        dim_data_support=dim["data_support"],
        dim_competitor_coverage=dim["competitor_coverage"],
        dim_bull_bear_balance=dim["bull_bear_balance"],
        dim_trade_clarity=dim["trade_clarity"],
        dim_news_corroboration=dim["news_corroboration"],
        ticker=ticker,
        report_content=report_content[:6000],  # 避免超 token 限制
    )

    raw = simple_chat(prompt, system="你是严格的报告质量审核员，只输出合法 JSON，不附加任何说明文字。")

    # 提取 JSON（LLM 有时会在前后加 markdown 代码块）
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON 解析失败: {e}", "raw": raw}

    scores = data.get("scores", {})
    total = sum(v.get("score", 0) for v in scores.values())

    return {
        "scores": scores,
        "total": total,
        "grade": _total_to_grade(total),
        "summary": data.get("summary", ""),
    }
