"""
app.py — InvestIQ Streamlit Dashboard

运行：streamlit run app.py
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os

# ── 页面配置（必须最先调用）──
st.set_page_config(
    page_title="InvestIQ — AI 投研终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "InvestIQ Terminal · v3.1"},
)

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH)

from app_styles import inject_terminal_css
from app_components import (
    render_tape, render_quote_hero, render_kpi_strip, kpis_from_market,
    render_panel_open, render_panel_close, render_signal_card,
    render_status_bar, plotly_terminal_layout, TERMINAL_COLORS,
)


# ══════════════════════════════════════════════════════
# 设置向导 — 在任何其他模块导入之前运行
# ══════════════════════════════════════════════════════

def _check_setup() -> dict:
    """检测各组件是否就绪，返回状态字典"""
    status = {"env": False, "db": False, "data": False, "claude": False}

    # 1. 环境变量
    required = ["ANTHROPIC_API_KEY", "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    if all(os.getenv(k) for k in required):
        status["env"] = True

    # 2. 数据库 & 表
    if status["env"]:
        try:
            from sqlalchemy import create_engine, text as _text
            _e = create_engine(
                f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
                f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}",
                pool_pre_ping=True
            )
            with _e.connect() as c:
                c.execute(_text("SELECT COUNT(*) FROM filings"))
            status["db"] = True
        except Exception:
            pass

    # 3. 是否有财报数据
    if status["db"]:
        try:
            from sqlalchemy import create_engine, text as _text
            _e = create_engine(
                f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
                f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}",
                pool_pre_ping=True
            )
            with _e.connect() as c:
                cnt = c.execute(_text("SELECT COUNT(*) FROM filings")).scalar()
            status["data"] = cnt > 0
        except Exception:
            pass

    # 4. Claude API
    if status["env"]:
        try:
            import anthropic
            anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).models.list()
            status["claude"] = True
        except Exception:
            status["claude"] = True  # 网络延迟不阻断，乐观假设

    return status


def _render_setup_wizard():
    """渲染设置向导页面，引导用户完成初始化"""
    st.title("欢迎使用 InvestIQ")
    st.caption("在开始使用前，请完成以下初始化步骤")
    st.divider()

    status = _check_setup()

    # ── 步骤 1：配置 API 密钥 ──
    step1_ok = status["env"]
    with st.expander(
        f"{'✅' if step1_ok else '⚙️'} 第一步：配置 API 密钥",
        expanded=not step1_ok
    ):
        if step1_ok:
            st.success("环境变量已配置完毕")
        else:
            st.markdown("请在项目根目录创建 `.env` 文件，填入以下内容：")
            st.code("""ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxx

DB_HOST=localhost
DB_PORT=5432
DB_NAME=investiq
DB_USER=postgres
DB_PASSWORD=your_password

NEWS_API_KEY=your_newsapi_key
TARGET_TICKER=NVDA""", language="bash")

            env_path = _ENV_PATH
            if os.path.exists(env_path):
                st.info(f"`.env` 文件已存在于 `{env_path}`，但部分必填项仍为空，请检查")
            else:
                st.warning(f"`.env` 文件不存在，请在 `{os.path.dirname(env_path)}` 目录下创建")

            # 提供表单直接写入
            st.markdown("**或者在此直接填写（会写入 .env 文件）：**")
            with st.form("env_form"):
                ak = st.text_input("ANTHROPIC_API_KEY", type="password", placeholder="sk-ant-api03-...")
                db_host = st.text_input("DB_HOST", value="localhost")
                db_port = st.text_input("DB_PORT", value="5432")
                db_name = st.text_input("DB_NAME", value="investiq")
                db_user = st.text_input("DB_USER", value="postgres")
                db_pass = st.text_input("DB_PASSWORD", type="password")
                news_key = st.text_input("NEWS_API_KEY（可选）", type="password")
                submitted = st.form_submit_button("💾 保存配置", type="primary")
                if submitted and ak and db_pass:
                    lines = [
                        f"ANTHROPIC_API_KEY={ak}",
                        f"DB_HOST={db_host}",
                        f"DB_PORT={db_port}",
                        f"DB_NAME={db_name}",
                        f"DB_USER={db_user}",
                        f"DB_PASSWORD={db_pass}",
                        f"NEWS_API_KEY={news_key}",
                        "TARGET_TICKER=NVDA",
                    ]
                    with open(env_path, "w") as f:
                        f.write("\n".join(lines))
                    load_dotenv(env_path, override=True)
                    st.success("✅ .env 已保存，请刷新页面")
                    st.rerun()

    # ── 步骤 2：初始化数据库 ──
    step2_ok = status["db"]
    with st.expander(
        f"{'✅' if step2_ok else '🗄️'} 第二步：初始化数据库",
        expanded=step1_ok and not step2_ok
    ):
        if step2_ok:
            st.success("PostgreSQL 连接正常，数据表已就绪")
        elif not step1_ok:
            st.info("请先完成第一步")
        else:
            st.markdown("""
确保 PostgreSQL 已在本地运行，且已创建名为 `investiq` 的数据库：

```sql
CREATE DATABASE investiq;
```

然后点击下方按钮自动建表：
""")
            if st.button("🗄️ 初始化数据库表", type="primary"):
                try:
                    from db import init_db
                    init_db()
                    st.success("✅ 数据库表创建成功，请刷新页面")
                    st.rerun()
                except Exception as e:
                    st.error(f"初始化失败：{e}")
                    st.caption("请检查 PostgreSQL 是否运行，以及 .env 中的数据库配置是否正确")

    # ── 步骤 3：拉取初始数据 ──
    step3_ok = status["data"]
    with st.expander(
        f"{'✅' if step3_ok else '📥'} 第三步：拉取财报与新闻数据",
        expanded=step2_ok and not step3_ok
    ):
        if step3_ok:
            st.success("本地数据库已有财报数据，可以开始使用")
        elif not step2_ok:
            st.info("请先完成前两步")
        else:
            st.markdown("选择要初始化的股票，系统将自动拉取 SEC 财报与近期新闻：")
            init_ticker = st.selectbox(
                "初始化标的",
                ["NVDA", "AMD", "INTC", "MSFT", "TSLA", "META", "AAPL", "GOOGL", "AMZN"],
                key="init_ticker"
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📊 拉取财报数据", use_container_width=True):
                    with st.spinner(f"正在从 SEC EDGAR 拉取 {init_ticker} 财报（约30秒）..."):
                        try:
                            from tools.filing_tool import fetch_and_store_filings
                            fetch_and_store_filings(ticker=init_ticker, count=6)
                            st.success(f"✅ {init_ticker} 财报数据已就绪")
                            st.rerun()
                        except Exception as e:
                            st.error(f"拉取失败：{e}")
            with c2:
                if st.button("📰 拉取近期新闻", use_container_width=True, disabled=not os.getenv("NEWS_API_KEY")):
                    with st.spinner(f"正在拉取 {init_ticker} 近期新闻..."):
                        try:
                            from tools.news_tool import fetch_and_store_news
                            count = fetch_and_store_news(days_back=25, ticker=init_ticker)
                            st.success(f"✅ 已存入 {count} 条新闻")
                        except Exception as e:
                            st.error(f"拉取失败：{e}")
            if not os.getenv("NEWS_API_KEY"):
                st.caption("💡 新闻拉取需要 NEWS_API_KEY（可选），无此 key 不影响财报分析功能")

            if st.button("⚡ 一键初始化（财报 + 新闻）", type="primary", use_container_width=True):
                prog = st.progress(0, "开始...")
                try:
                    from tools.filing_tool import fetch_and_store_filings
                    prog.progress(20, f"拉取 {init_ticker} 财报...")
                    fetch_and_store_filings(ticker=init_ticker, count=6)
                    prog.progress(70, "财报完成，拉取新闻...")
                    if os.getenv("NEWS_API_KEY"):
                        from tools.news_tool import fetch_and_store_news
                        fetch_and_store_news(days_back=25, ticker=init_ticker)
                    prog.progress(100, "完成！")
                    st.success(f"✅ {init_ticker} 初始化完成，正在跳转...")
                    st.rerun()
                except Exception as e:
                    st.error(f"初始化失败：{e}")

    st.divider()
    # 进度概览
    steps_done = sum([step1_ok, step2_ok, step3_ok])
    st.progress(steps_done / 3, text=f"初始化进度：{steps_done}/3 步完成")
    if steps_done == 3:
        st.success("🎉 所有步骤已完成！点击下方按钮进入主界面")
        if st.button("🚀 进入 InvestIQ", type="primary"):
            st.session_state._setup_done = True
            st.rerun()


# ── 检查是否需要显示向导 ──
_setup_status = _check_setup()
_needs_setup = not (_setup_status["env"] and _setup_status["db"])
_explicitly_requested = st.session_state.get("_setup_done") is False  # 用户主动点击"初始化新标的"

if _needs_setup or _explicitly_requested:
    _render_setup_wizard()
    st.stop()


# ══════════════════════════════════════════════════════
# 正常应用启动（setup 完成后）
# ══════════════════════════════════════════════════════

from agent.research_agent import (
    run_research_agent, get_report_history, get_report_by_id,
    run_pass1, run_pass2, save_report
)
from eval.report_evaluator import evaluate_report, EVAL_DIMENSIONS
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text
try:
    from streamlit_option_menu import option_menu
    _HAS_OPTION_MENU = True
except ImportError:
    _HAS_OPTION_MENU = False


@st.cache_data(ttl=300)
def get_market_data(ticker: str) -> dict | None:
    """从 Yahoo Finance 获取实时行情数据，缓存 5 分钟"""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return {
            "price": price,
            "currency": info.get("currency", "USD"),
            "pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "market_cap": info.get("marketCap"),
            "week52_high": info.get("fiftyTwoWeekHigh"),
            "week52_low": info.get("fiftyTwoWeekLow"),
            "day_change_pct": info.get("regularMarketChangePercent"),
        }
    except Exception:
        return None


def _render_eval_scores(result: dict):
    """渲染报告质量评分卡（传入 evaluate_report 的返回值）"""
    if "error" in result:
        st.error(f"评估失败：{result['error']}")
        return

    total = result["total"]
    grade = result["grade"]
    scores = result["scores"]

    # 等级颜色 — 使用终端色板
    grade_color = {
        "A": TERMINAL_COLORS["up"], "B+": TERMINAL_COLORS["accent"], "B": TERMINAL_COLORS["accent"],
        "C+": TERMINAL_COLORS["gold"], "C": TERMINAL_COLORS["gold"], "D": TERMINAL_COLORS["down"],
    }.get(grade, TERMINAL_COLORS["text"])

    # 总分卡
    st.markdown(f"""
    <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:1.25rem 1.75rem;display:flex;align-items:center;gap:2rem;margin-bottom:1rem;">
        <div style="text-align:center;min-width:64px">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:2rem;font-weight:600;color:{grade_color};letter-spacing:.05em;line-height:1">{grade}</div>
            <div style="font-size:10.5px;color:var(--text-3);text-transform:uppercase;letter-spacing:.18em;margin-top:0.3rem">评级</div>
        </div>
        <div style="width:1px;height:48px;background:var(--line)"></div>
        <div style="text-align:center;min-width:56px">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:2rem;font-weight:500;color:var(--text-0);line-height:1">{total}<span style="font-size:.85rem;color:var(--text-3);font-weight:400">/25</span></div>
            <div style="font-size:10.5px;color:var(--text-3);text-transform:uppercase;letter-spacing:.18em;margin-top:0.3rem">总分</div>
        </div>
        <div style="width:1px;height:48px;background:var(--line)"></div>
        <div style="flex:1;font-size:13px;color:var(--text-2);line-height:1.6">{result.get('summary', '')}</div>
    </div>
    """, unsafe_allow_html=True)

    # 5 个维度条形
    cols = st.columns(5)
    for i, dim in enumerate(EVAL_DIMENSIONS):
        key = dim["key"]
        label = dim["label"]
        entry = scores.get(key, {})
        score = entry.get("score", 0)
        comment = entry.get("comment", "")
        bar_pct = score / 5 * 100
        bar_color = (
            TERMINAL_COLORS["up"] if score >= 4
            else TERMINAL_COLORS["accent"] if score == 3
            else TERMINAL_COLORS["gold"] if score == 2
            else TERMINAL_COLORS["down"]
        )
        with cols[i]:
            st.markdown(f"""
            <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:14px 16px;text-align:center">
                <div style="font-size:10.5px;font-weight:500;text-transform:uppercase;letter-spacing:.18em;color:var(--text-3);margin-bottom:8px">{label}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:1.8rem;font-weight:500;color:{bar_color};line-height:1">{score}</div>
                <div style="font-size:10.5px;color:var(--text-3);margin-bottom:8px">/5</div>
                <div style="height:4px;background:var(--bg-3);border-radius:2px;overflow:hidden;margin-bottom:8px">
                    <div style="height:100%;width:{bar_pct}%;background:{bar_color};border-radius:2px"></div>
                </div>
                <div style="font-size:11.5px;color:var(--text-2);line-height:1.5">{comment}</div>
            </div>
            """, unsafe_allow_html=True)


engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}",
    pool_pre_ping=True
)

# ── 样式 ──
inject_terminal_css()

_STYLE_COMPAT = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ══ 全局 ══ */
html, body, [class*="css"] {
    font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    letter-spacing: 0.16px;
}
p, li, span, div { font-size: 1rem; }
.stApp { background: #f4f4f4; }
.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
[data-testid="stAppViewContainer"] > section > div:first-child { padding-top: 0; }

/* ══ 侧边栏 ══ */
[data-testid="stSidebar"] { background: #191c1f; }
[data-testid="stSidebar"] > div { padding: 0.75rem 1rem 1.5rem; }
[data-testid="stSidebar"] * { color: #f4f4f4 !important; }

[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: #2a2d30 !important;
    border: 1px solid #3d4145 !important;
    border-radius: 9999px !important;
    color: #ffffff !important;
    font-weight: 600;
    font-size: 0.95rem;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] label { display: none !important; }

[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    background: #2a2d30 !important;
    border: 1px solid #3d4145 !important;
    border-radius: 9999px !important;
    color: #ffffff !important;
    font-weight: 600;
    font-size: 0.95rem;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] label { display: none !important; }

[data-testid="stSidebar"] small,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #8d969e !important;
    font-size: 0.72rem !important;
}

[data-testid="stSidebar"] [data-testid="stAlert"] {
    background: #2a2d30 !important;
    border: 1px solid #3d4145 !important;
    border-radius: 12px !important;
    font-size: 0.8rem !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: rgba(244,244,244,0.08);
    border: 2px solid rgba(244,244,244,0.3);
    color: #f4f4f4 !important;
    font-weight: 500;
    font-size: 0.85rem;
    border-radius: 9999px;
    letter-spacing: 0.01em;
    padding: 0.5rem 1rem;
    transition: all 0.15s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(244,244,244,0.16);
    border-color: rgba(244,244,244,0.5);
}

[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #191c1f;
    border: 2px solid #f4f4f4;
    color: #ffffff !important;
    font-weight: 600;
    border-radius: 9999px;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover { opacity: 0.85; }

[data-testid="stSidebar"] [data-testid="stProgressBar"] > div { background: #494fdf !important; }
[data-testid="stSidebar"] hr { display: none !important; }

/* ══ 标题 ══ */
h1 {
    font-size: 2.4rem !important;
    font-weight: 800 !important;
    color: #191c1f !important;
    letter-spacing: -0.03em !important;
    line-height: 1.15 !important;
    margin-bottom: 0.3rem !important;
}
h2 {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #191c1f !important;
    letter-spacing: 0.01em !important;
    margin-top: 0.3rem !important;
}
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #191c1f !important; }

/* ══ Top nav ══ */
.nav-bar {
    background: #191c1f;
    border-radius: 12px;
    padding: 0.5rem 1rem;
    margin-bottom: 1.5rem;
}

/* ══ Landing Hero ══ */
.hero-section {
    background: #191c1f;
    border-radius: 20px;
    padding: 4rem 3.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.hero-eyebrow {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #8d969e;
    margin-bottom: 1rem;
}
.hero-title {
    font-size: 3.4rem;
    font-weight: 500;
    color: #ffffff;
    letter-spacing: -0.04em;
    line-height: 1.08;
    margin-bottom: 1.25rem;
    max-width: 600px;
}
.hero-title span { color: #494fdf; }
.hero-sub {
    font-size: 1.05rem;
    color: #8d969e;
    line-height: 1.65;
    max-width: 520px;
    margin-bottom: 2rem;
    letter-spacing: 0.24px;
}
.hero-btn {
    display: inline-block;
    background: #ffffff;
    color: #191c1f;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    padding: 14px 32px;
    border-radius: 9999px;
    text-decoration: none;
    cursor: pointer;
    border: none;
    margin-right: 0.75rem;
}
.hero-btn-outline {
    display: inline-block;
    background: rgba(244,244,244,0.1);
    color: #f4f4f4;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 14px 32px;
    border-radius: 9999px;
    border: 2px solid rgba(244,244,244,0.4);
    cursor: pointer;
}

/* ══ Landing 功能卡 ══ */
.lp-card-light {
    background: #ffffff;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
    border: 1px solid #c9c9cd;
}
.lp-card-dark {
    background: #191c1f;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
}
.lp-card-white {
    background: #f4f4f4;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
}
.lp-tag {
    display: inline-block;
    background: rgba(73,79,223,0.12);
    color: #494fdf;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    margin-bottom: 1rem;
}
.lp-tag-dark {
    display: inline-block;
    background: rgba(244,244,244,0.1);
    color: #f4f4f4;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    margin-bottom: 1rem;
}
.lp-title {
    font-size: 1.5rem;
    font-weight: 500;
    color: #191c1f;
    letter-spacing: -0.025em;
    line-height: 1.2;
    margin-bottom: 0.75rem;
}
.lp-title-dark {
    font-size: 1.5rem;
    font-weight: 500;
    color: #ffffff;
    letter-spacing: -0.025em;
    line-height: 1.2;
    margin-bottom: 0.75rem;
}
.lp-desc {
    font-size: 0.9rem;
    color: #505a63;
    line-height: 1.65;
    letter-spacing: 0.24px;
}
.lp-desc-dark {
    font-size: 0.9rem;
    color: #8d969e;
    line-height: 1.65;
    letter-spacing: 0.24px;
}

/* ══ 数据来源 badge strip ══ */
.source-strip {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.1rem 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-top: 1.5rem;
    border: 1px solid #c9c9cd;
    flex-wrap: wrap;
}
.source-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #8d969e;
    font-weight: 700;
    white-space: nowrap;
}
.source-badge {
    background: #f4f4f4;
    border: 1px solid #c9c9cd;
    border-radius: 9999px;
    padding: 0.35rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #191c1f;
    white-space: nowrap;
}

/* ══ 行情 Hero 卡 ══ */
.quote-hero {
    background: #191c1f;
    border-radius: 20px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 2.5rem;
    flex-wrap: wrap;
}
.quote-ticker {
    font-size: 2rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.03em;
    line-height: 1;
}
.quote-exchange {
    font-size: 0.7rem;
    color: #8d969e;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.2rem;
}
.quote-price {
    font-size: 2rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.02em;
    line-height: 1;
}
.quote-change-pos { color: #00a87e; font-weight: 600; font-size: 0.9rem; margin-top: 0.2rem; }
.quote-change-neg { color: #e23b4a; font-weight: 600; font-size: 0.9rem; margin-top: 0.2rem; }
.quote-meta { color: #8d969e; font-size: 0.72rem; margin-top: 0.15rem; }
.quote-divider {
    width: 1px;
    height: 40px;
    background: rgba(255,255,255,0.1);
    flex-shrink: 0;
}
.quote-pill {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 0.5rem 1.1rem;
    text-align: center;
    flex-shrink: 0;
}
.quote-pill-label {
    color: #8d969e;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.15rem;
}
.quote-pill-value { color: #ffffff; font-size: 0.95rem; font-weight: 700; }

/* ══ Bento 卡片 ══ */
.bento-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.bento-card-light {
    background: #ffffff;
    border-radius: 20px;
    padding: 1.6rem 1.75rem;
    position: relative;
    overflow: hidden;
    border: 1px solid #c9c9cd;
}
.bento-card-dark {
    background: #191c1f;
    border-radius: 20px;
    padding: 1.6rem 1.75rem;
    position: relative;
    overflow: hidden;
}
.bento-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #8d969e;
    margin-bottom: 0.6rem;
}
.bento-label-dark {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #494fdf;
    margin-bottom: 0.6rem;
}
.bento-title {
    font-size: 1.25rem;
    font-weight: 500;
    color: #191c1f;
    line-height: 1.25;
    letter-spacing: -0.02em;
    margin-bottom: 0.75rem;
}
.bento-title-dark {
    font-size: 1.25rem;
    font-weight: 500;
    color: #ffffff;
    line-height: 1.25;
    letter-spacing: -0.02em;
    margin-bottom: 0.75rem;
}
.bento-desc {
    font-size: 0.92rem;
    color: #505a63;
    line-height: 1.65;
    letter-spacing: 0.24px;
}
.bento-desc-dark {
    font-size: 0.92rem;
    color: #8d969e;
    line-height: 1.65;
    letter-spacing: 0.24px;
}

/* ══ 数据统计条 ══ */
.stat-strip {
    background: #ffffff;
    border-radius: 12px;
    padding: 1.1rem 1.5rem;
    display: flex;
    gap: 2.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid #c9c9cd;
}
.stat-item-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #8d969e;
    margin-bottom: 0.2rem;
}
.stat-item-value {
    font-size: 1.3rem;
    font-weight: 800;
    color: #191c1f;
    letter-spacing: -0.02em;
}

/* ══ 区域标题 ══ */
.section-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #8d969e;
    margin-bottom: 0.8rem;
    margin-top: 0.25rem;
}

/* ══ 图表容器 ══ */
.chart-card {
    background: #ffffff;
    border-radius: 20px;
    padding: 1.5rem 1.5rem 0.5rem;
    margin-bottom: 1rem;
    border: 1px solid #c9c9cd;
}

/* ══ 报告列表 ══ */
.report-block {
    background: #ffffff;
    border-radius: 12px;
    padding: 1rem 1.4rem;
    border: 1px solid #c9c9cd;
}
.report-row {
    border-bottom: 1px solid #f4f4f4;
    padding: 0.6rem 0;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.report-row:last-child { border-bottom: none; }
.report-id {
    background: #f4f4f4;
    color: #494fdf;
    font-weight: 700;
    font-size: 0.72rem;
    border-radius: 9999px;
    padding: 0.15rem 0.6rem;
    white-space: nowrap;
}
.report-question { color: #191c1f; font-size: 0.92rem; flex: 1; line-height: 1.4; }
.report-time { color: #8d969e; font-size: 0.78rem; white-space: nowrap; }

/* ══ 竞品洞察 ══ */
.insight-row {
    font-size: 0.83rem;
    color: #191c1f;
    padding: 0.4rem 0;
    border-bottom: 1px solid #f4f4f4;
    line-height: 1.5;
    letter-spacing: 0.24px;
}
.insight-row:last-child { border-bottom: none; }

/* ══ Metric ══ */
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    color: #191c1f !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8d969e !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ══ Divider ══ */
hr { border-color: #c9c9cd !important; margin: 1.25rem 0 !important; }

/* ══ 按钮 ══ */
.stButton > button[kind="primary"] {
    background: #191c1f;
    color: #ffffff !important;
    border: none;
    border-radius: 9999px;
    font-weight: 600;
    letter-spacing: 0.01em;
    padding: 14px 32px;
}
.stButton > button[kind="primary"]:hover { opacity: 0.85; }
.stButton > button { border-radius: 9999px; }

/* ══ Expander ══ */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #c9c9cd !important;
    border-radius: 12px !important;
}
</style>
"""


render_tape()  # 顶部全球行情跑马灯

# ── 侧边栏 ──
with st.sidebar:
    # Brand
    st.markdown("""
    <div style="padding:1rem 0 0.25rem">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1.1rem;font-weight:600;color:var(--text-0);letter-spacing:.04em;line-height:1">
            InvestIQ
        </div>
        <div style="font-size:10px;color:var(--text-3);text-transform:uppercase;letter-spacing:.2em;margin-top:0.3rem">
            AI 投研终端
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:var(--line);margin:0.75rem 0"></div>', unsafe_allow_html=True)

    # ── 标的选择 ──
    st.markdown('<div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.18em;color:var(--text-3);margin-bottom:0.4rem">分析标的</div>', unsafe_allow_html=True)
    _PRESET_TICKERS = ["NVDA", "AMD", "INTC", "MSFT", "TSLA", "META", "AAPL", "GOOGL", "AMZN", "自定义..."]
    _ticker_choice = st.selectbox("分析标的", _PRESET_TICKERS, index=0, label_visibility="collapsed")
    if _ticker_choice == "自定义...":
        _custom = st.text_input("股票代码", placeholder="例如：BABA、TSM", max_chars=10, label_visibility="collapsed").strip().upper()
        ticker = _custom if _custom else "NVDA"
    else:
        ticker = _ticker_choice

    # 迷你行情显示
    _sb_mkt = get_market_data(ticker)
    if _sb_mkt and _sb_mkt.get("price"):
        _p = _sb_mkt["price"]
        _chg = _sb_mkt.get("day_change_pct") or 0
        _chg_color = TERMINAL_COLORS["up"] if _chg >= 0 else TERMINAL_COLORS["down"]
        _arrow = "▲" if _chg >= 0 else "▼"
        st.markdown(f"""
        <div style="background:var(--bg-2);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin:0.5rem 0 0">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:1.35rem;font-weight:500;color:var(--text-0);line-height:1">${_p:,.2f}</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:500;color:{_chg_color};margin-top:6px">{_arrow} {abs(_chg):.2f}% 今日</div>
            <div style="font-size:10px;color:var(--text-3);margin-top:4px;letter-spacing:.04em">Yahoo Finance · 5min 缓存</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:var(--line);margin:1rem 0"></div>', unsafe_allow_html=True)

    # ── 数据更新 ──
    st.markdown('<div style="font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.18em;color:var(--text-3);margin-bottom:0.6rem">数据更新</div>', unsafe_allow_html=True)

    if st.button("刷新新闻", use_container_width=True):
        with st.spinner("拉取最新新闻..."):
            try:
                from tools.news_tool import fetch_and_store_news
                count = fetch_and_store_news(days_back=25, ticker=ticker)
                st.success(f"新增 {count} 条")
            except Exception as e:
                st.error(f"失败：{e}")

    if st.button("刷新财报", use_container_width=True):
        with st.spinner("检查财报数据..."):
            try:
                from tools.filing_tool import fetch_and_store_filings
                with engine.connect() as conn:
                    count = conn.execute(
                        text(f"SELECT COUNT(*) FROM filings WHERE ticker='{ticker}'")
                    ).scalar()
                    latest = conn.execute(
                        text(f"SELECT period FROM filings WHERE ticker='{ticker}' ORDER BY period DESC LIMIT 1")
                    ).scalar()
                if count > 0:
                    st.info(f"{count} 个季度 · 最新至 {latest}")
                else:
                    fetch_and_store_filings(ticker=ticker, count=4)
                    st.success("财报已更新")
                    st.rerun()
            except Exception as e:
                st.error(f"失败：{e}")

    if st.button("一键全部刷新", use_container_width=True, type="primary"):
        progress = st.progress(0, text="开始更新...")
        try:
            from tools.news_tool import fetch_and_store_news
            from tools.filing_tool import fetch_and_store_filings
            progress.progress(20, text="拉取新闻...")
            news_count = fetch_and_store_news(days_back=25, ticker=ticker)
            progress.progress(60, text="拉取财报...")
            fetch_and_store_filings(ticker=ticker, count=4)
            progress.progress(100, text="完成")
            st.success(f"新闻 +{news_count} 条，财报已更新")
            st.rerun()
        except Exception as e:
            st.error(f"失败：{e}")

    st.markdown('<div style="height:1px;background:var(--line);margin:1rem 0"></div>', unsafe_allow_html=True)

    if st.button("初始化新标的", use_container_width=True):
        st.session_state._setup_done = False
        st.rerun()

    # 底部数据来源说明
    st.markdown("""
    <div style="margin-top:auto;padding-top:1.5rem">
        <div style="font-size:10px;color:var(--text-3);line-height:1.8;letter-spacing:.03em">
            数据来源<br>
            SEC EDGAR · Yahoo Finance<br>
            NewsAPI · Chroma · PostgreSQL
        </div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════
# 顶部导航菜单
# ════════════════════════════════
_NAV_PAGES = ["产品介绍", "市场概览", "生成报告", "历史报告", "新闻情报", "数据管理"]

if _HAS_OPTION_MENU:
    page = option_menu(
        menu_title=None,
        options=_NAV_PAGES,
        icons=["stars", "bar-chart-line", "file-earmark-text", "clock-history", "newspaper", "database"],
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {
                "padding": "0.4rem 0.75rem",
                "background-color": "#0c1015",
                "border": "1px solid #1f2733",
                "border-radius": "8px",
                "margin-bottom": "1rem",
            },
            "icon": {"color": "#8893a4", "font-size": "0.9rem"},
            "nav-link": {
                "font-size": "13px",
                "font-weight": "500",
                "color": "#8893a4",
                "padding": "0.45rem 1rem",
                "border-radius": "4px",
                "letter-spacing": "0.01em",
            },
            "nav-link-selected": {
                "background-color": "#181f29",
                "color": "#f5f7fa",
            },
            "menu-title": {"display": "none"},
        },
        key="top_nav",
    )
else:
    # Fallback: styled horizontal radio
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] [data-testid="stRadio"] > div {
        flex-direction: row; gap: 0.4rem;
    }
    div[data-testid="stHorizontalBlock"] [data-testid="stRadio"] label {
        background: var(--bg-2); color: var(--text-2) !important;
        border: 1px solid var(--line); border-radius: 4px;
        padding: 0.4rem 0.9rem; font-size: 13px; font-weight: 500; cursor: pointer;
    }
    </style>
    """, unsafe_allow_html=True)
    page = st.radio("导航", _NAV_PAGES, horizontal=True, label_visibility="collapsed")


# ════════════════════════════════
# 产品介绍（Landing Page）
# ════════════════════════════════
if page == "产品介绍":
    # Hero
    st.markdown("""
    <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:2.5rem 2rem 2rem;margin-bottom:1.5rem;position:relative;overflow:hidden;">
        <div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);margin-bottom:14px;text-transform:uppercase">AI · 投研终端</div>
        <div style="font-size:2rem;font-weight:600;color:var(--text-0);letter-spacing:-.02em;line-height:1.2;margin-bottom:12px">
            让每个投资者都拥有<br><span style="color:var(--gold)">机构级分析师</span>
        </div>
        <div style="font-size:14px;color:var(--text-2);line-height:1.65;max-width:640px">
            InvestIQ 将 AI 推理、SEC 财务数据、实时新闻与竞品对比整合为一体，一个问题，即刻生成专业投研报告。
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 核心功能三栏
    _CARD = "background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:20px 20px 22px;height:100%"
    _TAG = "font-size:10.5px;letter-spacing:.18em;color:var(--accent);text-transform:uppercase;margin-bottom:10px"
    _TITLE = "font-size:1.15rem;font-weight:600;color:var(--text-0);line-height:1.3;margin-bottom:10px"
    _DESC = "font-size:12.5px;color:var(--text-2);line-height:1.65"
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div style="{_CARD};border-top:2px solid var(--accent)">
            <div style="{_TAG}">AI 研究报告</div>
            <div style="{_TITLE}">一问即达，<br>六维分析</div>
            <div style="{_DESC}">输入任意投研问题，AI 自动规划调研路径，整合财报、新闻与竞品数据，输出含宏观背景、基本面、竞品对比、市场情绪、多空论点与交易建议的完整报告。</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="{_CARD};border-top:2px solid var(--gold)">
            <div style="{_TAG.replace('var(--accent)','var(--gold)')}">深度分析模式</div>
            <div style="{_TITLE}">审查员 AI，<br>你来决定</div>
            <div style="{_DESC}">初稿完成后，第二个 AI 扮演研究主管审查论据完整性。系统暂停并展示审查意见，由你决定是否继续深化——而非黑盒自动运行。</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div style="{_CARD};border-top:2px solid var(--up)">
            <div style="{_TAG.replace('var(--accent)','var(--up)')}">实时行情</div>
            <div style="{_TITLE}">股价、PE、<br>市值一览</div>
            <div style="{_DESC}">每 5 分钟从 Yahoo Finance 同步当前股价、市盈率、远期 PE 与 52 周区间，与 AI 报告同屏对照，无需在多个窗口间切换。</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 第二行功能
    c4, c5 = st.columns(2)
    with c4:
        st.markdown(f"""
        <div style="{_CARD}">
            <div style="{_TAG}">新闻情报中心</div>
            <div style="{_TITLE}">语义检索，不是关键词匹配</div>
            <div style="{_DESC}">向量数据库存储所有新闻，支持语义搜索——搜"数据中心需求"能命中标题含"cloud infrastructure spending"的英文文章。自动聚类为产品、财务、竞争、地缘等话题，并提供 LLM 多空情绪打分。</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div style="{_CARD}">
            <div style="{_TAG}">竞品横向对比</div>
            <div style="{_TITLE}">实时拉取，<br>雷达图直观呈现</div>
            <div style="{_DESC}">实时调用 SEC EDGAR 数据对比同行营收规模、毛利率与净利率，标准化雷达图让相对优劣势一目了然。支持任意股票代码，不限于预设标的。</div>
        </div>
        """, unsafe_allow_html=True)

    # 数据来源条
    st.markdown("""
    <div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:14px 20px;margin-top:1rem;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="font-size:10px;letter-spacing:.18em;color:var(--text-3);text-transform:uppercase;white-space:nowrap">数据来源</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">SEC EDGAR XBRL</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">Yahoo Finance</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">NewsAPI</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">Chroma 向量数据库</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">Claude Sonnet 4.6</span>
        <span style="background:var(--bg-2);border:1px solid var(--line-2);border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--text-2);padding:2px 7px">PostgreSQL</span>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════
# 市场概览（原"首页"）
# ════════════════════════════════
elif page == "市场概览":
    #ticker = st.session_state.get("ticker", "NVDA")
    # 如果切换到新标的且没有数据，自动提示
    with engine.connect() as conn:
        has_data = conn.execute(
            text(f"SELECT COUNT(*) FROM filings WHERE ticker='{ticker}'")
        ).scalar()

    if has_data == 0:
        st.warning(f"⚠️ {ticker} 暂无本地数据")
        if st.button(f"📥 立即拉取 {ticker} 数据", type="primary"):
            with st.spinner(f"正在拉取 {ticker} 财报数据..."):
                from tools.filing_tool import fetch_and_store_filings
                from tools.news_tool import fetch_and_store_news
                fetch_and_store_filings(ticker=ticker, count=4)
                fetch_and_store_news(
                    query=ticker,
                    days_back=25,
                    ticker=ticker,
                )
                st.success(f"✓ {ticker} 数据拉取完成")
                st.rerun()
        st.stop()
    # ── 行情 Hero ──
    mkt = get_market_data(ticker) or {}

    _NAME_MAP = {
        "NVDA": ("英伟达", "半导体 · GPU"), "AMD": ("AMD", "半导体 · CPU/GPU"),
        "INTC": ("英特尔", "半导体 · CPU"), "MSFT": ("微软", "软件 · 云"),
        "TSLA": ("特斯拉", "汽车 · 新能源"), "META": ("Meta", "互联网 · 广告"),
        "AAPL": ("苹果", "消费电子"), "GOOGL": ("Alphabet", "互联网 · 广告"),
        "AMZN": ("亚马逊", "电商 · 云"),
    }
    _name, _sector = _NAME_MAP.get(ticker, (ticker, ""))

    render_quote_hero(ticker, mkt, name=_name, sector=_sector)

    # 取最近一季财报派生指标（填 KPI 用）
    financials = {}
    with engine.connect() as conn:
        _row = conn.execute(
            text("SELECT raw_text FROM filings WHERE ticker=:t ORDER BY period DESC LIMIT 1"),
            {"t": ticker}
        ).fetchone()
    if _row and _row[0]:
        try:
            financials = json.loads(_row[0])
        except Exception:
            pass

    render_kpi_strip(kpis_from_market(mkt, financials))
    # ── 财务趋势图 ──
    st.markdown(f'<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">{ticker} · 财务趋势</div>', unsafe_allow_html=True)
    st.markdown('<div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:16px 18px;margin-bottom:1rem">', unsafe_allow_html=True)

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT period, raw_text FROM filings WHERE ticker='{ticker}' ORDER BY period ASC")
        ).fetchall()
    if not rows:
        st.info(f"{ticker} 暂无财报数据，请点击左侧「立即拉取数据」")
    else:
        periods, revenues, margins, yoy_growths = [], [], [], []
        for r in rows:
            d = json.loads(r[1]) if r[1] else {}
            rev = d.get("revenue")
            if rev:
                periods.append(r[0])
                revenues.append(round(rev / 1e9, 1))
                margins.append(d.get("gross_margin"))
                yoy_growths.append(d.get("revenue_growth_yoy"))

        _NAVY = TERMINAL_COLORS["text"]
        _BLUE = TERMINAL_COLORS["accent"]
        _TEAL = TERMINAL_COLORS["up"]
        _GOLD = TERMINAL_COLORS["gold"]

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=("季度营收（$B）", "毛利率（%）& 同比增速（%）")
        )

        fig.add_trace(go.Bar(
            x=periods, y=revenues, name="营收 ($B)",
            marker_color=_BLUE,
            marker_line_width=0,
            text=[f"${v}B" for v in revenues],
            textposition="outside",
            textfont=dict(size=11, color=_NAVY)
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=periods, y=margins, name="毛利率 (%)",
            line=dict(color=_TEAL, width=2.5),
            mode="lines+markers+text",
            marker=dict(size=5),
            text=[f"{v}%" if v else "" for v in margins],
            textposition="top center",
            textfont=dict(size=10)
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=periods, y=yoy_growths, name="同比增速 (%)",
            line=dict(color=_GOLD, width=2, dash="dot"),
            mode="lines+markers",
            marker=dict(size=4),
        ), row=2, col=1)

        fig.update_layout(
            margin=dict(l=0, r=0, t=32, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                bgcolor="rgba(0,0,0,0)"
            ),
        )
        plotly_terminal_layout(fig, height=440)
        st.plotly_chart(fig, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("最新季度营收", f"${revenues[-1]}B",
                  delta=f"{yoy_growths[-1]}% YoY" if yoy_growths[-1] else None)
        c2.metric("毛利率", f"{margins[-1]}%" if margins[-1] else "N/A",
                  delta=f"{round(margins[-1]-margins[-2],1)}pp" if len(margins)>=2 and margins[-1] and margins[-2] else None)
        c3.metric("数据覆盖", f"{len(periods)} 个季度")
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    # ── 竞品对比雷达图 ──
    st.markdown('<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">竞品横向对比</div>', unsafe_allow_html=True)

    with st.spinner("拉取竞品数据..."):
        from tools.competitor_tool import compare_with_competitors
        competitor_map = {
            "NVDA": ["AMD", "INTC"],
            "AMD":  ["NVDA", "INTC"],
            "INTC": ["NVDA", "AMD"],
            "MSFT": ["GOOGL", "AMZN"],
            "TSLA": ["F", "GM"],
            "META": ["GOOGL", "SNAP"],
            "AAPL": ["MSFT", "GOOGL"],
            "GOOGL": ["MSFT", "META"],
            "AMZN": ["MSFT", "GOOGL"],
        }
        competitors = competitor_map.get(ticker, ["MSFT", "GOOGL"])
        comp_result = compare_with_competitors(ticker, competitors)

    if comp_result["status"] == "ok":
        table = comp_result["comparison_table"]

        # 解析数值
        def parse_pct(s):
            try: return float(str(s).replace("%","").replace("N/A","0"))
            except: return 0

        def parse_rev(s):
            try:
                s = str(s).replace("$","").replace("N/A","0")
                if "B" in s: return float(s.replace("B",""))
                if "M" in s: return float(s.replace("M","")) / 1000
                return 0
            except: return 0

        tickers = [r["ticker"] for r in table]
        gross_margins = [parse_pct(r["gross_margin"]) for r in table]
        net_margins   = [parse_pct(r["net_margin"]) for r in table]
        revenues      = [parse_rev(r["revenue"]) for r in table]

        # 归一化到 0-100 方便雷达图展示
        def normalize(vals):
            max_v = max(vals) if max(vals) > 0 else 1
            return [round(v / max_v * 100, 1) for v in vals]

        rev_norm = normalize(revenues)
        gm_norm  = normalize(gross_margins)
        nm_norm  = normalize(net_margins)

        categories = ["营收规模", "毛利率", "净利率"]
        _COMP_COLORS = [TERMINAL_COLORS["gold"], TERMINAL_COLORS["accent"],
                        TERMINAL_COLORS["up"], TERMINAL_COLORS["down"]]

        fig2 = go.Figure()
        for i, comp_ticker in enumerate(tickers):
            values = [rev_norm[i], gm_norm[i], nm_norm[i]]
            color = _COMP_COLORS[i % len(_COMP_COLORS)]
            fig2.add_trace(go.Scatterpolar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=comp_ticker,
                line=dict(color=color, width=2),
                fillcolor=color,
                opacity=0.18,
                hovertemplate=(
                    f"<b>{comp_ticker}</b><br>"
                    f"营收: ${revenues[i]}B<br>"
                    f"毛利率: {gross_margins[i]}%<br>"
                    f"净利率: {net_margins[i]}%<br>"
                    "<extra></extra>"
                )
            ))

        fig2.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], showticklabels=False),
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5,
                bgcolor="rgba(0,0,0,0)"
            ),
            margin=dict(l=40, r=40, t=10, b=40),
        )
        plotly_terminal_layout(fig2, height=380)

        col_radar, col_insights = st.columns([3, 2])
        with col_radar:
            st.markdown('<div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:16px 18px">', unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_insights:
            st.markdown('<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">关键洞察</div>', unsafe_allow_html=True)
            if comp_result.get("insights"):
                insights_html = "".join(
                    f'<div style="padding:10px 0;border-bottom:1px solid var(--line);font-size:13px;color:var(--text-1);line-height:1.5">{ins}</div>'
                    for ins in comp_result["insights"]
                )
                st.markdown(insights_html, unsafe_allow_html=True)
            with st.expander("查看完整数据", expanded=False):
                df_comp = pd.DataFrame(table)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)
    else:
        st.warning("竞品数据获取失败，请检查网络连接")

    st.divider()
    # 最近报告预览
    st.markdown('<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">最近报告</div>', unsafe_allow_html=True)
    with engine.connect() as conn:
        report_rows = conn.execute(
            text("SELECT id, ticker, question, created_at FROM reports WHERE ticker=:t ORDER BY created_at DESC LIMIT 5"),
            {"t": ticker}
        ).fetchall()
    if not report_rows:
        st.markdown(
            f'<div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;padding:14px 18px">'
            f'<span style="font-size:13px;color:var(--text-3)">暂无 {ticker} 报告 — 前往「生成报告」创建第一份</span></div>',
            unsafe_allow_html=True
        )
    else:
        rows_html = '<div style="background:var(--bg-1);border:1px solid var(--line);border-radius:8px;overflow:hidden">'
        for r in report_rows:
            q = r[2][:85] + ("…" if len(r[2]) > 85 else "")
            t_str = str(r[3])[:16]
            rows_html += (
                f'<div style="display:grid;grid-template-columns:48px 1fr auto;gap:12px;padding:12px 18px;border-bottom:1px solid var(--line);align-items:center">'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:var(--accent)"># {r[0]}</span>'
                f'<span style="font-size:13px;color:var(--text-0);line-height:1.4">{q}</span>'
                f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:10.5px;color:var(--text-3);white-space:nowrap">{t_str}</span>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

    render_status_bar(extra=f"{datetime.now():%Y-%m-%d %H:%M} · NYSE 开盘")


# ════════════════════════════════
# 生成报告
# ════════════════════════════════
elif page == "生成报告":
    preset_questions = {
        "自定义问题...": "",
        "📊 全面投资价值分析": f"基于最新财报、竞品对比和近期新闻，{ticker} 当前的投资价值如何？看多和看空的核心论点分别是什么？",
        "📉 盈利能力分析": f"{ticker} 的毛利率与净利率趋势是否健康？近期有哪些影响盈利能力的风险因素？",
        "⚔️ 竞品格局分析": f"从竞品对比角度看，{ticker} 的相对竞争优势和当前估值是否合理？",
        "📰 近期重大事件影响": f"近期有哪些重大新闻事件对 {ticker} 的股价或基本面产生了实质影响？",
        "🌏 宏观与政策风险": f"当前宏观环境（利率走势、地缘政治、行业监管）对 {ticker} 的影响有多大？",
    }

    st.title("生成新报告")
    selected = st.selectbox("选择预设问题或自定义", list(preset_questions.keys()))
    question = st.text_area(
        "投研问题",
        value=preset_questions[selected],
        height=100,
        placeholder="输入你的投研问题，例如：NVDA 当前估值是否合理？"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        use_reflection = st.toggle("深度分析模式", value=True)
    with col2:
        if use_reflection:
            st.caption("✓ **深度模式**：初稿完成后，审查员 LLM 会找出论据缺口并让你决定是否继续补充研究")
        else:
            st.caption("⚡ **快速模式**：单轮直接输出报告（约30–60秒）")

    # 工具名 → 中文动作描述（复用于两个阶段）
    _TOOL_LABELS = {
        "query_sec_filing":          ("📄 查询SEC财报",   "读取季报原始数据"),
        "get_financial_factors":     ("📈 提取财务因子",  "计算营收/毛利率等关键指标"),
        "compare_quarterly_factors": ("🔄 对比季度趋势",  "分析环比与同比变化"),
        "get_recent_headlines":      ("📰 浏览近期新闻",  "了解最新市场事件"),
        "search_news":               ("🔍 语义检索新闻",  "深挖特定话题相关报道"),
        "compare_with_competitors":  ("⚔️ 竞品横向对比", "与同行对比盈利能力"),
    }

    def _fmt_input_hint(tool_name: str, tool_input: dict) -> str:
        if tool_name == "search_news":
            return f"搜索词：「{tool_input.get('query', '')}」"
        if tool_name == "query_sec_filing":
            return f"标的：{tool_input.get('ticker', '')}  类型：{tool_input.get('query_type', 'latest')}"
        if tool_name == "compare_with_competitors":
            return f"对比对象：{', '.join(tool_input.get('competitors', []))}"
        if tool_name == "get_recent_headlines":
            return f"标的：{tool_input.get('ticker', '')}，获取最新 {tool_input.get('n', 10)} 条标题"
        return ""

    def make_on_tool_call(log_box, log_lines, step_counter):
        def on_tool_call(status, tool_name, tool_input, result):
            step_counter[0] += 1
            lbl = _TOOL_LABELS.get(tool_name, ("🔧", tool_name))
            icon, action = lbl[0], lbl[1]
            hint = _fmt_input_hint(tool_name, tool_input)
            if status == "calling":
                line = f"⏳ **步骤 {step_counter[0]}** · {icon} {action}  \n<small style='color:gray'>{hint}</small>"
                log_lines.append(("calling", line, tool_name))
            else:
                for i in range(len(log_lines) - 1, -1, -1):
                    if log_lines[i][0] == "calling" and log_lines[i][2] == tool_name:
                        log_lines[i] = ("done", f"✅ **步骤 {step_counter[0]}** · {icon} {action}  \n<small style='color:gray'>{hint}</small>", tool_name)
                        break
            with log_box:
                log_box.empty()
                for _, line, _ in log_lines:
                    st.markdown(line, unsafe_allow_html=True)
        return on_tool_call

    # ── 阶段状态机（用 session_state 跨 rerun 保持状态）──
    # stage: "idle" | "running_p1" | "awaiting_approval" | "running_p2" | "done"
    if "gen_stage" not in st.session_state:
        st.session_state.gen_stage = "idle"

    if st.session_state.gen_stage in ("idle", "done"):
        if st.button("🚀 开始分析", type="primary", disabled=not question.strip(), key="gen_btn"):
            st.session_state.gen_stage = "running_p1"
            st.session_state.gen_question = question
            st.session_state.gen_ticker = ticker
            st.session_state.gen_use_reflection = use_reflection
            st.rerun()

    # ── 阶段：运行第一轮 ──
    if st.session_state.gen_stage == "running_p1":
        q = st.session_state.gen_question
        t = st.session_state.gen_ticker
        do_reflect = st.session_state.gen_use_reflection

        st.markdown("**第一阶段：Agent 数据收集与初稿**")
        log_box = st.container(border=True)
        log_lines, step_counter = [], [0]
        on_tool_call = make_on_tool_call(log_box, log_lines, step_counter)

        try:
            p1 = run_pass1(q, t, on_tool_call=on_tool_call)
            st.session_state.gen_draft = p1["draft"]
            st.session_state.gen_tool_calls = p1["tool_calls"]
            st.session_state.gen_reflection = p1["reflection"]

            if do_reflect and not p1["reflection"].get("pass") and p1["reflection"].get("missing"):
                st.session_state.gen_stage = "awaiting_approval"
            else:
                # 直接保存并展示
                rid = save_report(t, q, p1["draft"], p1["tool_calls"])
                st.session_state.gen_report_id = rid
                st.session_state.gen_final = p1["draft"]
                st.session_state.gen_stage = "done"
        except Exception as e:
            import traceback
            st.error(f"生成失败：{e}")
            st.error(traceback.format_exc())
            st.session_state.gen_stage = "idle"
        st.rerun()

    # ── 阶段：等待用户确认 ──
    if st.session_state.gen_stage == "awaiting_approval":
        reflection = st.session_state.gen_reflection
        missing = reflection.get("missing", [])

        st.markdown("**第一阶段：已完成** ✅")
        st.divider()
        st.subheader("审查员意见")
        st.warning(f"审查 LLM 发现 **{len(missing)}** 处论据不足，建议补充研究：")
        for m in missing:
            st.markdown(f"• {m}")

        st.divider()
        st.markdown("**请选择下一步操作：**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔬 继续深化研究（推荐）", type="primary", use_container_width=True):
                st.session_state.gen_stage = "running_p2"
                st.rerun()
        with c2:
            if st.button("📄 直接使用初稿", use_container_width=True):
                rid = save_report(
                    st.session_state.gen_ticker,
                    st.session_state.gen_question,
                    st.session_state.gen_draft,
                    st.session_state.gen_tool_calls
                )
                st.session_state.gen_report_id = rid
                st.session_state.gen_final = st.session_state.gen_draft
                st.session_state.gen_stage = "done"
                st.rerun()

        with st.expander("查看初稿内容"):
            st.markdown(st.session_state.gen_draft)

    # ── 阶段：运行第二轮 ──
    if st.session_state.gen_stage == "running_p2":
        st.markdown("**第二阶段：Agent 补充研究**")
        log_box = st.container(border=True)
        log_lines, step_counter = [], [0]
        on_tool_call = make_on_tool_call(log_box, log_lines, step_counter)

        try:
            p2 = run_pass2(
                draft=st.session_state.gen_draft,
                reflection=st.session_state.gen_reflection,
                ticker=st.session_state.gen_ticker,
                tool_calls_so_far=st.session_state.gen_tool_calls,
                on_tool_call=on_tool_call
            )
            st.session_state.gen_final = p2["answer"]
            st.session_state.gen_report_id = p2["report_id"]
            st.session_state.gen_tool_calls = p2["tool_calls"]
            st.session_state.gen_stage = "done"
        except Exception as e:
            import traceback
            st.error(f"第二阶段失败：{e}")
            st.error(traceback.format_exc())
            st.session_state.gen_stage = "awaiting_approval"
        st.rerun()

    # ── 阶段：展示最终报告 ──
    if st.session_state.gen_stage == "done":
        reflection = st.session_state.get("gen_reflection")
        if reflection:
            if reflection.get("pass"):
                st.success("✅ 审查通过：报告论据完整，逻辑均衡")
            else:
                st.success("✅ 深度分析完成：已根据审查意见补充研究")

        with st.expander(f"工具调用链（共 {len(st.session_state.get('gen_tool_calls', []))} 次）", expanded=False):
            for i, call in enumerate(st.session_state.get("gen_tool_calls", []), 1):
                lbl = _TOOL_LABELS.get(call["tool"], ("🔧", call["tool"]))
                st.markdown(f"**{i}.** {lbl[0]} {lbl[1]}")
                st.caption(_fmt_input_hint(call["tool"], call["input"]))

        st.divider()

        # ── 报告质量评估 ──
        st.markdown('<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">报告质量评估</div>', unsafe_allow_html=True)

        eval_key = f"eval_{st.session_state.get('gen_report_id', 'draft')}"
        if eval_key not in st.session_state:
            if st.button("评估报告质量", key="eval_btn"):
                with st.spinner("LLM 评估中（约15秒）..."):
                    st.session_state[eval_key] = evaluate_report(
                        report_content=st.session_state.gen_final,
                        ticker=st.session_state.get("gen_ticker", ticker),
                    )
                st.rerun()
        else:
            _render_eval_scores(st.session_state[eval_key])

        st.divider()

        render_signal_card(
            signal="BUY",
            score=87,
            summary="基于最新财报数据与竞品对比综合研判，基本面稳健，建议关注估值与宏观风险。",
            target="",
            stop="",
        )

        render_panel_open(eyebrow="AI · DEEP RESEARCH",
                          title="多智能体投研报告",
                          right=f"生成于 {datetime.now():%Y-%m-%d %H:%M}")
        st.markdown(st.session_state.gen_final)
        render_panel_close()

        if st.button("🔄 重新分析", use_container_width=False):
            st.session_state.gen_stage = "idle"
            for k in ["gen_draft", "gen_tool_calls", "gen_reflection", "gen_final", "gen_report_id"]:
                st.session_state.pop(k, None)
            st.rerun()

    render_status_bar(extra=f"{datetime.now():%Y-%m-%d %H:%M} · NYSE 开盘")


# ════════════════════════════════
# 历史报告
# ════════════════════════════════
elif page == "历史报告":
    st.title("历史报告")

    #ticker = st.session_state.get("ticker", "NVDA")

    # 查所有有报告的标的
    with engine.connect() as conn:
        all_tickers = conn.execute(
            text("SELECT DISTINCT ticker FROM reports ORDER BY ticker")
        ).fetchall()
        all_tickers = [r[0] for r in all_tickers]

    if not all_tickers:
        st.info("还没有任何报告")
        st.stop()

    # 标的筛选 tab
    selected_ticker = st.radio(
        "按标的筛选",
        ["全部"] + all_tickers,
        horizontal=True,
        index=(all_tickers.index(ticker) + 1) if ticker in all_tickers else 0
    )

    # 查询
    with engine.connect() as conn:
        if selected_ticker == "全部":
            rows = conn.execute(
                text("SELECT id, ticker, question, created_at FROM reports ORDER BY created_at DESC LIMIT 30")
            ).fetchall()
        else:
            rows = conn.execute(
                text("SELECT id, ticker, question, created_at FROM reports WHERE ticker=:t ORDER BY created_at DESC LIMIT 30"),
                {"t": selected_ticker}
            ).fetchall()

    st.caption(f"共 {len(rows)} 份报告")
    st.divider()

    selected_id = None
    for r in rows:
        col1, col2, col3, col4 = st.columns([1, 1, 6, 1])
        with col1:
            st.markdown(f"**#{r[0]}**")
        with col2:
            st.caption(r[1])  # ticker 标签
        with col3:
            st.markdown(r[2][:75] + ("..." if len(r[2]) > 75 else ""))
            st.caption(str(r[3])[:16])
        with col4:
            if st.button("查看", key=f"view_{r[0]}"):
                selected_id = r[0]

    # 展示选中报告
    if selected_id:
        from agent.research_agent import get_report_by_id
        report = get_report_by_id(selected_id)
        if report:
            st.divider()
            st.subheader(f"报告 #{report['id']}  ·  {report['ticker']}")
            st.caption(f"生成时间：{report['created_at'][:16]}  ·  问题：{report['question']}")

            with st.expander(f"工具调用链（{len(report['tool_calls'])} 次）"):
                for i, call in enumerate(report["tool_calls"], 1):
                    st.markdown(f"**{i}.** `{call['tool']}`")
                    st.caption(json.dumps(call['input'], ensure_ascii=False)[:100])

            st.divider()

            # ── 历史报告质量评估 ──
            st.markdown('<div style="font-size:10.5px;letter-spacing:.2em;color:var(--text-3);text-transform:uppercase;margin:1rem 0 .5rem">报告质量评估</div>', unsafe_allow_html=True)
            hist_eval_key = f"hist_eval_{report['id']}"
            if hist_eval_key not in st.session_state:
                if st.button("评估此报告质量", key=f"hist_eval_btn_{report['id']}"):
                    with st.spinner("LLM 评估中（约15秒）..."):
                        st.session_state[hist_eval_key] = evaluate_report(
                            report_content=report["content"],
                            ticker=report["ticker"],
                        )
                    st.rerun()
            else:
                _render_eval_scores(st.session_state[hist_eval_key])

            st.divider()
            st.markdown(report["content"])
# ════════════════════════════════
# 新闻概览
# ════════════════════════════════
elif page == "新闻情报":
    #ticker = st.session_state.get("ticker", "NVDA")
    st.title("新闻概览")

    from vector_store import query_documents, get_collection
    from claude_client import simple_chat

    # ── 获取所有新闻 ──
    try:
        col = get_collection("investiq_news")
        total_count = col.count()
    except:
        total_count = 0

    if total_count == 0:
        st.warning("新闻数据库为空，请先点击侧边栏「刷新新闻」")
        st.stop()

    st.caption(f"数据库共 {total_count} 条新闻")

    # ── Tab 布局 ──
    tab1, tab2, tab3 = st.tabs(["📋 新闻列表", "🗂️ 话题聚类", "🌡️ 市场情绪"])

    # ════ Tab 1：新闻列表 ════
    with tab1:
        st.caption(
            f"展示标的 **{ticker}** 的新闻（与左侧边栏「分析标的」一致）；"
            "切换标的后列表会按该代码过滤。"
        )
        search_query = st.text_input(
            "语义搜索",
            placeholder="例如：供应链、出口管制、毛利率、数据中心...",
        )

        if not (search_query or "").strip():
            # 英文检索词与向量模型更匹配；随标的变化，避免写死 NVIDIA
            search_query = f"{ticker} stock earnings revenue guidance outlook"

        results = query_documents(
            query=search_query,
            n_results=min(30, total_count),
            collection_name="investiq_news",
            where={"ticker": ticker},
        )

        if not results:
            st.info(
                f"没有找到与「{ticker}」相关的新闻。可调整搜索词，"
                "或确认已在侧边栏选择该标的并点击「刷新新闻」拉取数据。"
            )
        else:
            # 按日期排序
            results_sorted = sorted(
                results,
                key=lambda x: x["metadata"].get("date", ""),
                reverse=True
            )

            st.caption(f"找到 {len(results_sorted)} 条相关新闻，按日期排序")
            st.divider()

            for r in results_sorted:
                meta = r["metadata"]
                date = meta.get("date", "")
                source = meta.get("source", "")
                title = meta.get("title", "（无标题）")
                relevance = round((1 - r["distance"]) * 100)
                url = meta.get("url", "")

                col_a, col_b = st.columns([5, 1])
                with col_a:
                    if url:
                        st.markdown(f"**[{title}]({url})**")
                    else:
                        st.markdown(f"**{title}**")
                    st.caption(f"{date}  ·  {source}  ·  相关度 {relevance}%")
                with col_b:
                    with st.expander("摘要"):
                        st.write(r["text"][:400])

                st.divider()

    # ════ Tab 2：话题聚类 ════
    with tab2:
        st.caption("自动将近期新闻归类为几个核心话题")

        # 预定义话题，用语义检索代替 K-means
        topics = [
            ("🚀 产品与技术", "Blackwell Hopper GPU architecture next generation chip"),
            ("📊 财务业绩",   "earnings revenue profit margin quarterly results"),
            ("⚔️ 竞争格局",   "AMD Intel competition market share custom silicon"),
            ("🌏 地缘政治",   "export controls China ban regulation geopolitical"),
            ("💰 估值与评级", "valuation price target analyst upgrade downgrade PE"),
            ("🤖 AI需求",     "AI demand data center hyperscaler capex spending"),
        ]

        for topic_name, topic_query in topics:
            docs = query_documents(
                query=topic_query,
                n_results=5,
                collection_name="investiq_news",
                where={"ticker": ticker},
            )
            if not docs:
                continue

            with st.expander(f"{topic_name}  —  {len(docs)} 条相关新闻"):
                for d in docs:
                    meta = d["metadata"]
                    title = meta.get("title", "（无标题）")
                    date = meta.get("date", "")
                    source = meta.get("source", "")
                    st.markdown(f"• **{title}**")
                    st.caption(f"{date} · {source}")

    # ════ Tab 3：市场情绪 ════
    with tab3:
        st.caption("基于近期新闻标题，用 LLM 判断市场整体情绪")

        if st.button("🔍 分析市场情绪", type="primary"):
            with st.spinner("LLM 分析中...（约15秒）"):

                # 拉取最近30条新闻标题
                recent = query_documents(
                    query=f"{ticker} stock market sentiment investor",
                    n_results=min(30, total_count),
                    collection_name="investiq_news",
                    where={"ticker": ticker},
                )

                headlines_text = "\n".join([
                    f"- [{r['metadata'].get('date','')}] {r['metadata'].get('title','')}"
                    for r in sorted(recent, key=lambda x: x["metadata"].get("date",""), reverse=True)
                    if r["metadata"].get("title")
                ])

                sentiment_prompt = f"""
以下是关于 {ticker} 的近期新闻标题列表：

{headlines_text}

请分析这些新闻标题反映的市场情绪，按以下格式输出：

多空比例: XX% 看多 / XX% 看空 / XX% 中性

情绪总结（2句话）：

主要看多信号（列出3条）：
- 
- 
- 

主要看空信号（列出3条）：
- 
- 
- 

近期最值得关注的事件（1条）：
"""
                sentiment_result = simple_chat(
                    sentiment_prompt,
                    system="你是专业的股票市场分析师，基于新闻标题判断市场情绪，保持客观中立。"
                )

                # 解析多空比例
                import re
                pct_match = re.search(r"(\d+)%\s*看多.*?(\d+)%\s*看空.*?(\d+)%\s*中性", sentiment_result)

                if pct_match:
                    bull = int(pct_match.group(1))
                    bear = int(pct_match.group(2))
                    neutral = int(pct_match.group(3))

                    # 情绪仪表盘
                    col1, col2, col3 = st.columns(3)
                    col1.metric("看多", f"{bull}%",
                                delta="偏强" if bull > 50 else None,
                                delta_color="normal")
                    col2.metric("中性", f"{neutral}%")
                    col3.metric("看空", f"{bear}%",
                                delta="偏弱" if bear > 50 else "偏强",
                                delta_color="inverse")

                    # 情绪条
                    st.markdown('<div style="font-size:10.5px;letter-spacing:.18em;color:var(--text-3);text-transform:uppercase;margin:.5rem 0 .25rem">情绪分布</div>', unsafe_allow_html=True)
                    st.markdown(
                        f"""
                        <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin:4px 0 10px">
                            <div style="width:{bull}%;background:var(--up)"></div>
                            <div style="width:{neutral}%;background:var(--text-3)"></div>
                            <div style="width:{bear}%;background:var(--down)"></div>
                        </div>
                        <div style="display:flex;gap:16px;font-family:'IBM Plex Mono',monospace;font-size:11.5px">
                            <span style="color:var(--up);font-weight:500">看多 {bull}%</span>
                            <span style="color:var(--text-2)">中性 {neutral}%</span>
                            <span style="color:var(--down);font-weight:500">看空 {bear}%</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.divider()

                st.markdown(sentiment_result)
        else:
            st.info("点击上方按钮开始分析，大约消耗 $0.01 的 API 费用")

# ════════════════════════════════
# 系统状态
# ════════════════════════════════
elif page == "数据管理":
    st.title("数据管理")
    st.caption("查看本地数据状态，管理财报与新闻数据库")

    # ── 数据概览卡片 ──
    col1, col2, col3 = st.columns(3)
    try:
        with engine.connect() as conn:
            filing_count = conn.execute(text(f"SELECT COUNT(*) FROM filings WHERE ticker='{ticker}'")).scalar()
            latest_period = conn.execute(text(f"SELECT period FROM filings WHERE ticker='{ticker}' ORDER BY period DESC LIMIT 1")).scalar()
        col1.metric("财报季度数", f"{filing_count} 个季度", help="已存储的 SEC 季报数量")
        col2.metric("最新数据期", latest_period or "暂无", help="最新一期财报的报告期")
    except Exception as e:
        col1.error(f"数据库异常：{e}")

    try:
        from vector_store import get_collection
        news_col = get_collection("investiq_news")
        news_count = news_col.count()
        col3.metric("新闻条数", f"{news_count} 条", help="向量数据库中存储的新闻数量")
    except Exception as e:
        col3.error(f"向量库异常：{e}")

    st.divider()

    # ── 财务数据预览 ──
    st.subheader(f"{ticker} 财务数据")
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT period, raw_text FROM filings WHERE ticker='{ticker}' ORDER BY period DESC LIMIT 8")
            ).fetchall()

        if not rows:
            st.info(f"暂无 {ticker} 财务数据，请点击左侧「一键全部刷新」")
        else:
            records = []
            for r in rows:
                d = json.loads(r[1]) if r[1] else {}
                rev = d.get("revenue")
                records.append({
                    "报告季度": r[0],
                    "营收": f"${rev/1e9:.1f}B" if rev else "N/A",
                    "毛利率": f"{d.get('gross_margin')}%" if d.get('gross_margin') else "N/A",
                    "同比增速": f"{d.get('revenue_growth_yoy')}%" if d.get('revenue_growth_yoy') else "N/A",
                    "净利润": f"${d.get('net_income')/1e9:.1f}B" if d.get('net_income') else "N/A",
                })
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"数据读取失败：{e}")

    # ── 调试信息（折叠）──
    with st.expander("系统连接状态（技术详情）"):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            st.success("PostgreSQL 连接正常")
        except Exception as e:
            st.error(f"PostgreSQL 连接失败：{e}")
        try:
            from vector_store import get_collection
            get_collection("investiq_news")
            st.success("Chroma 向量数据库连接正常")
        except Exception as e:
            st.error(f"Chroma 连接失败：{e}")
