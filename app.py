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
    page_title="InvestIQ — AI 投研 Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH)


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


engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}",
    pool_pre_ping=True
)

# ── 样式 ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ══ 全局 ══ */
html, body, [class*="css"] {
    font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
}
p, li, span, div { font-size: 1rem; }
.stApp {
    background: #f0eff6;
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
/* 隐藏 Streamlit 默认顶部留白，给 option-menu 腾空间 */
[data-testid="stAppViewContainer"] > section > div:first-child {
    padding-top: 0;
}

/* ══ 侧边栏 ══ */
[data-testid="stSidebar"] {
    background: #1a1730;
}
[data-testid="stSidebar"] > div {
    padding: 0.75rem 1rem 1.5rem;
}
[data-testid="stSidebar"] * { color: #e2dff0 !important; }

/* Selectbox */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
    background: #12102a !important;
    border: 1px solid #2a2445 !important;
    border-radius: 10px !important;
    color: #f0eefa !important;
    font-weight: 600;
    font-size: 0.95rem;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] label { display: none !important; }

/* Text input */
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
    background: #12102a !important;
    border: 1px solid #2a2445 !important;
    border-radius: 10px !important;
    color: #f0eefa !important;
    font-weight: 600;
    font-size: 0.95rem;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] label { display: none !important; }

/* Caption/info/success/error text */
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #6b6080 !important;
    font-size: 0.72rem !important;
}

/* Info/success/warning boxes */
[data-testid="stSidebar"] [data-testid="stAlert"] {
    background: #12102a !important;
    border: 1px solid #2a2445 !important;
    border-radius: 10px !important;
    font-size: 0.8rem !important;
}

/* Default buttons */
[data-testid="stSidebar"] .stButton > button {
    background: #12102a;
    border: 1px solid #2a2445;
    color: #c8c0e8 !important;
    font-weight: 500;
    font-size: 0.85rem;
    border-radius: 10px;
    letter-spacing: 0.01em;
    padding: 0.45rem 1rem;
    transition: all 0.15s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #2a2445;
    border-color: #5047a0;
    color: #f0eefa !important;
}

/* Primary button */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #6c5ce7;
    border: none;
    color: #ffffff !important;
    font-weight: 700;
    border-radius: 10px;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: #5a4dd6;
}

/* Progress bar */
[data-testid="stSidebar"] [data-testid="stProgressBar"] > div {
    background: #6c5ce7 !important;
}

/* Hide default Streamlit hr in sidebar */
[data-testid="stSidebar"] hr { display: none !important; }

/* ══ 标题系统 ══ */
h1 {
    font-size: 2.4rem !important;
    font-weight: 800 !important;
    color: #12102a !important;
    letter-spacing: -0.03em !important;
    line-height: 1.15 !important;
    margin-bottom: 0.3rem !important;
}
h2 {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #12102a !important;
    letter-spacing: 0.01em !important;
    margin-top: 0.3rem !important;
}
h3 {
    font-size: 1rem !important;
    font-weight: 600 !important;
    color: #12102a !important;
}

/* ══ Top nav 背景条 ══ */
.nav-bar {
    background: #1a1730;
    border-radius: 16px;
    padding: 0.5rem 1rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ══ Landing 页 ══ */
.hero-section {
    background: #1a1730;
    border-radius: 24px;
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
    color: #a29bfe;
    margin-bottom: 1rem;
}
.hero-title {
    font-size: 3.4rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.04em;
    line-height: 1.08;
    margin-bottom: 1.25rem;
    max-width: 600px;
}
.hero-title span { color: #a29bfe; }
.hero-sub {
    font-size: 1.05rem;
    color: #9b8ec4;
    line-height: 1.65;
    max-width: 520px;
    margin-bottom: 2rem;
}
.hero-btn {
    display: inline-block;
    background: #6c5ce7;
    color: #ffffff;
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    padding: 0.8rem 2rem;
    border-radius: 50px;
    text-decoration: none;
    cursor: pointer;
    border: none;
    margin-right: 0.75rem;
}
.hero-btn-outline {
    display: inline-block;
    background: transparent;
    color: #a29bfe;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.8rem 2rem;
    border-radius: 50px;
    border: 1.5px solid #3d3660;
    cursor: pointer;
}

/* ══ Landing 功能卡 ══ */
.lp-card-light {
    background: #eae7f8;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
}
.lp-card-dark {
    background: #1a1730;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
}
.lp-card-white {
    background: #ffffff;
    border-radius: 20px;
    padding: 2rem 2rem 1.5rem;
    height: 100%;
    border: 1px solid #e4e0f0;
}
.lp-tag {
    display: inline-block;
    background: rgba(108,92,231,0.15);
    color: #6c5ce7;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.25rem 0.75rem;
    border-radius: 50px;
    margin-bottom: 1rem;
}
.lp-tag-dark {
    display: inline-block;
    background: rgba(162,155,254,0.15);
    color: #a29bfe;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.25rem 0.75rem;
    border-radius: 50px;
    margin-bottom: 1rem;
}
.lp-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #12102a;
    letter-spacing: -0.025em;
    line-height: 1.2;
    margin-bottom: 0.75rem;
}
.lp-title-dark {
    font-size: 1.5rem;
    font-weight: 800;
    color: #f0eefa;
    letter-spacing: -0.025em;
    line-height: 1.2;
    margin-bottom: 0.75rem;
}
.lp-desc {
    font-size: 0.9rem;
    color: #4a4266;
    line-height: 1.65;
}
.lp-desc-dark {
    font-size: 0.9rem;
    color: #9b8ec4;
    line-height: 1.65;
}

/* ══ 数据来源 badge strip ══ */
.source-strip {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.1rem 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
    margin-top: 1.5rem;
    border: 1px solid #e4e0f0;
    flex-wrap: wrap;
}
.source-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9b8ec4;
    font-weight: 700;
    white-space: nowrap;
}
.source-badge {
    background: #f0eff6;
    border: 1px solid #e4e0f0;
    border-radius: 8px;
    padding: 0.35rem 1rem;
    font-size: 0.85rem;
    font-weight: 700;
    color: #12102a;
    white-space: nowrap;
}

/* ══ 行情 Hero 卡 ══ */
.quote-hero {
    background: #1a1730;
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
    color: #7a708e;
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
.quote-change-pos { color: #00e5a0; font-weight: 600; font-size: 0.9rem; margin-top: 0.2rem; }
.quote-change-neg { color: #ff6b6b; font-weight: 600; font-size: 0.9rem; margin-top: 0.2rem; }
.quote-meta { color: #7a708e; font-size: 0.72rem; margin-top: 0.15rem; }
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
    color: #7a708e;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.15rem;
}
.quote-pill-value { color: #f0eefa; font-size: 0.95rem; font-weight: 700; }

/* ══ Bento 功能卡片 ══ */
.bento-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
/* 浅色卡：白色偏紫调 */
.bento-card-light {
    background: #eae7f8;
    border-radius: 18px;
    padding: 1.6rem 1.75rem;
    position: relative;
    overflow: hidden;
}
/* 深色卡：深紫近黑 */
.bento-card-dark {
    background: #1a1730;
    border-radius: 18px;
    padding: 1.6rem 1.75rem;
    position: relative;
    overflow: hidden;
}
.bento-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #9b8ec4;
    margin-bottom: 0.6rem;
}
.bento-label-dark {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #6c5ce7;
    margin-bottom: 0.6rem;
}
.bento-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #12102a;
    line-height: 1.25;
    letter-spacing: -0.02em;
    margin-bottom: 0.75rem;
}
.bento-title-dark {
    font-size: 1.25rem;
    font-weight: 800;
    color: #f0eefa;
    line-height: 1.25;
    letter-spacing: -0.02em;
    margin-bottom: 0.75rem;
}
.bento-desc {
    font-size: 0.92rem;
    color: #4a4266;
    line-height: 1.65;
}
.bento-desc-dark {
    font-size: 0.92rem;
    color: #9b8ec4;
    line-height: 1.65;
}

/* ══ 数据统计行 ══ */
.stat-strip {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.1rem 1.5rem;
    display: flex;
    gap: 2.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid #e4e0f0;
}
.stat-item-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #9b8ec4;
    margin-bottom: 0.2rem;
}
.stat-item-value {
    font-size: 1.3rem;
    font-weight: 800;
    color: #12102a;
    letter-spacing: -0.02em;
}

/* ══ 区域标题 ══ */
.section-label {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #9b8ec4;
    margin-bottom: 0.8rem;
    margin-top: 0.25rem;
}

/* ══ 图表容器 ══ */
.chart-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 1.5rem 1.5rem 0.5rem;
    margin-bottom: 1rem;
    border: 1px solid #e4e0f0;
}

/* ══ 报告列表 ══ */
.report-block {
    background: #ffffff;
    border-radius: 14px;
    padding: 1rem 1.4rem;
    border: 1px solid #e4e0f0;
}
.report-row {
    border-bottom: 1px solid #f0ecfa;
    padding: 0.6rem 0;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.report-row:last-child { border-bottom: none; }
.report-id {
    background: #eae7f8;
    color: #6c5ce7;
    font-weight: 700;
    font-size: 0.72rem;
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    white-space: nowrap;
}
.report-question { color: #12102a; font-size: 0.92rem; flex: 1; line-height: 1.4; }
.report-time { color: #9b8ec4; font-size: 0.78rem; white-space: nowrap; }

/* ══ 竞品洞察 ══ */
.insight-row {
    font-size: 0.83rem;
    color: #12102a;
    padding: 0.4rem 0;
    border-bottom: 1px solid #f0ecfa;
    line-height: 1.5;
}
.insight-row:last-child { border-bottom: none; }

/* ══ Metric 覆盖 ══ */
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    font-weight: 800 !important;
    color: #12102a !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #9b8ec4 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ══ Divider ══ */
hr { border-color: #e4e0f0 !important; margin: 1.25rem 0 !important; }

/* ══ 主按钮 ══ */
.stButton > button[kind="primary"] {
    background: #1a1730;
    border: none;
    border-radius: 50px;
    font-weight: 600;
    letter-spacing: 0.01em;
    padding: 0.55rem 1.5rem;
}
.stButton > button[kind="primary"]:hover { background: #2d2850; }
.stButton > button {
    border-radius: 10px;
}

/* ══ Expander ══ */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #e4e0f0 !important;
    border-radius: 14px !important;
}
</style>
""", unsafe_allow_html=True)


# ── 侧边栏 ──
with st.sidebar:
    # Brand
    st.markdown("""
    <div style="padding:1rem 0 0.25rem">
        <div style="font-size:1.3rem;font-weight:800;color:#f0eefa;letter-spacing:-0.03em;line-height:1">
            InvestIQ
        </div>
        <div style="font-size:0.68rem;color:#6b6080;text-transform:uppercase;letter-spacing:0.14em;margin-top:0.3rem">
            AI 投资研究平台
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#2a2445;margin:0.75rem 0"></div>', unsafe_allow_html=True)

    # ── 标的选择 ──
    st.markdown('<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:#6b6080;margin-bottom:0.4rem">分析标的</div>', unsafe_allow_html=True)
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
        _chg_color = "#00e5a0" if _chg >= 0 else "#ff6b6b"
        _arrow = "▲" if _chg >= 0 else "▼"
        st.markdown(f"""
        <div style="background:#12102a;border-radius:12px;padding:0.85rem 1rem;margin:0.5rem 0 0">
            <div style="font-size:1.4rem;font-weight:800;color:#f0eefa;letter-spacing:-0.02em;line-height:1">${_p:,.2f}</div>
            <div style="font-size:0.78rem;font-weight:600;color:{_chg_color};margin-top:0.2rem">{_arrow} {abs(_chg):.2f}% 今日</div>
            <div style="font-size:0.68rem;color:#6b6080;margin-top:0.3rem;letter-spacing:0.04em">Yahoo Finance · 5min 缓存</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#2a2445;margin:1rem 0"></div>', unsafe_allow_html=True)

    # ── 数据更新 ──
    st.markdown('<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:#6b6080;margin-bottom:0.6rem">数据更新</div>', unsafe_allow_html=True)

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

    st.markdown('<div style="height:1px;background:#2a2445;margin:1rem 0"></div>', unsafe_allow_html=True)

    if st.button("初始化新标的", use_container_width=True):
        st.session_state._setup_done = False
        st.rerun()

    # 底部数据来源说明
    st.markdown("""
    <div style="margin-top:auto;padding-top:1.5rem">
        <div style="font-size:0.65rem;color:#4a4060;line-height:1.7;letter-spacing:0.03em">
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
                "background-color": "#1a1730",
                "border-radius": "16px",
                "margin-bottom": "1.5rem",
            },
            "icon": {"color": "#a29bfe", "font-size": "1rem"},
            "nav-link": {
                "font-size": "0.9rem",
                "font-weight": "600",
                "color": "#9b8ec4",
                "padding": "0.5rem 1rem",
                "border-radius": "10px",
                "letter-spacing": "0.01em",
            },
            "nav-link-selected": {
                "background-color": "#2d2850",
                "color": "#f0eefa",
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
        flex-direction: row; gap: 0.5rem;
    }
    div[data-testid="stHorizontalBlock"] [data-testid="stRadio"] label {
        background: #1a1730; color: #9b8ec4 !important;
        border-radius: 10px; padding: 0.45rem 1rem;
        font-size: 0.9rem; font-weight: 600; cursor: pointer;
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
    <div class="hero-section">
        <div class="hero-eyebrow">AI · 投资研究平台</div>
        <div class="hero-title">让每个投资者都拥有<br><span>机构级分析师</span></div>
        <div class="hero-sub">InvestIQ 将 AI 推理、SEC 财务数据、实时新闻与竞品对比整合为一体，一个问题，即刻生成专业投研报告。</div>
    </div>
    """, unsafe_allow_html=True)

    # 核心功能三栏
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="lp-card-light">
            <div class="lp-tag">AI 研究报告</div>
            <div class="lp-title">一问即达，<br>六维分析</div>
            <div class="lp-desc">输入任意投研问题，AI 自动规划调研路径，整合财报、新闻与竞品数据，输出含宏观背景、基本面、竞品对比、市场情绪、多空论点与交易建议的完整报告。</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="lp-card-dark">
            <div class="lp-tag-dark">深度分析模式</div>
            <div class="lp-title-dark">审查员 AI，<br>你来决定</div>
            <div class="lp-desc-dark">初稿完成后，第二个 AI 扮演研究主管审查论据完整性。系统暂停并展示审查意见，由你决定是否继续深化——而非黑盒自动运行。</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="lp-card-white">
            <div class="lp-tag">实时行情</div>
            <div class="lp-title">股价、PE、<br>市值一览</div>
            <div class="lp-desc">每 5 分钟从 Yahoo Finance 同步当前股价、市盈率、远期 PE 与 52 周区间，与 AI 报告同屏对照，无需在多个窗口间切换。</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 第二行功能
    c4, c5 = st.columns(2)
    with c4:
        st.markdown("""
        <div class="lp-card-white">
            <div class="lp-tag">新闻情报中心</div>
            <div class="lp-title">语义检索，不是关键词匹配</div>
            <div class="lp-desc">向量数据库存储所有新闻，支持语义搜索——搜"数据中心需求"能命中标题含"cloud infrastructure spending"的英文文章。自动聚类为产品、财务、竞争、地缘等话题，并提供 LLM 多空情绪打分。</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown("""
        <div class="lp-card-light">
            <div class="lp-tag">竞品横向对比</div>
            <div class="lp-title">实时拉取，<br>雷达图直观呈现</div>
            <div class="lp-desc">实时调用 SEC EDGAR 数据对比同行营收规模、毛利率与净利率，标准化雷达图让相对优劣势一目了然。支持任意股票代码，不限于预设标的。</div>
        </div>
        """, unsafe_allow_html=True)

    # 数据来源 strip
    st.markdown("""
    <div class="source-strip">
        <div class="source-label">数据来源</div>
        <div class="source-badge">SEC EDGAR XBRL</div>
        <div class="source-badge">Yahoo Finance</div>
        <div class="source-badge">NewsAPI</div>
        <div class="source-badge">Chroma 向量数据库</div>
        <div class="source-badge">Claude Sonnet 4.6</div>
        <div class="source-badge">PostgreSQL</div>
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
    # ── 行情 Header ──
    mkt = get_market_data(ticker)
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")

    if mkt and mkt.get("price"):
        price = mkt["price"]
        chg = mkt.get("day_change_pct") or 0
        chg_color = "quote-change-pos" if chg >= 0 else "quote-change-neg"
        chg_arrow = "▲" if chg >= 0 else "▼"
        cap = mkt.get("market_cap")
        cap_str = f"${cap/1e9:.0f}B" if cap else "—"
        pe_str = f"{mkt['pe']:.1f}x" if mkt.get("pe") else "—"
        fpe_str = f"{mkt['forward_pe']:.1f}x" if mkt.get("forward_pe") else "—"
        hi = mkt.get("week52_high"); lo = mkt.get("week52_low")
        rng_str = f"${lo:.0f} – ${hi:.0f}" if hi and lo else "—"

        st.markdown(f"""
        <div class="quote-hero">
            <div>
                <div class="quote-ticker">{ticker}</div>
                <div class="quote-exchange">NASDAQ · 实时行情</div>
            </div>
            <div class="quote-divider"></div>
            <div>
                <div class="quote-price">${price:,.2f}</div>
                <div class="{chg_color}">{chg_arrow} {abs(chg):.2f}% 今日</div>
            </div>
            <div class="quote-divider"></div>
            <div class="quote-pill"><div class="quote-pill-label">市值</div><div class="quote-pill-value">{cap_str}</div></div>
            <div class="quote-pill"><div class="quote-pill-label">P / E</div><div class="quote-pill-value">{pe_str}</div></div>
            <div class="quote-pill"><div class="quote-pill-label">远期 P/E</div><div class="quote-pill-value">{fpe_str}</div></div>
            <div class="quote-pill"><div class="quote-pill-label">52 周区间</div><div class="quote-pill-value">{rng_str}</div></div>
            <div style="margin-left:auto"><div class="quote-meta">更新于 {now_str}</div><div class="quote-meta">来源：Yahoo Finance</div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="quote-hero">
            <div>
                <div class="quote-ticker">{ticker}</div>
                <div class="quote-exchange">行情暂时无法获取 · {now_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 功能介绍 + 数据统计 ──
    with engine.connect() as conn:
        report_count = conn.execute(text(f"SELECT COUNT(*) FROM reports WHERE ticker='{ticker}'")).scalar()
        filing_count = conn.execute(text(f"SELECT COUNT(*) FROM filings WHERE ticker='{ticker}'")).scalar()

    # Bento 网格：左列2张浅色卡，右列2张深色卡
    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown(f"""
        <div class="bento-card-light" style="margin-bottom:1rem">
            <div class="bento-label">AI 研究报告</div>
            <div class="bento-title">一问即达，<br>机构级报告</div>
            <div class="bento-desc">输入任意投研问题，AI 自动调取财报、新闻、竞品数据，生成含基本面、竞品对比、多空论点与交易建议的完整分析。</div>
        </div>
        <div class="bento-card-light">
            <div class="bento-label">新闻情报</div>
            <div class="bento-title">语义检索，<br>话题聚类</div>
            <div class="bento-desc">向量相似度匹配相关报道，自动聚类为产品、财务、地缘等话题，并提供 LLM 多空情绪分析。</div>
        </div>
        """, unsafe_allow_html=True)
    with right_col:
        st.markdown(f"""
        <div class="bento-card-dark" style="margin-bottom:1rem">
            <div class="bento-label-dark">深度分析</div>
            <div class="bento-title-dark">审查员 AI，<br>你来决定</div>
            <div class="bento-desc-dark">初稿生成后，第二个 AI 模型扮演研究主管发现论据缺口，由你选择是否继续深化——质量与效率兼顾。</div>
        </div>
        <div class="bento-card-dark">
            <div class="bento-label-dark">竞品对比</div>
            <div class="bento-title-dark">实时拉取，<br>横向基准</div>
            <div class="bento-desc-dark">实时调用 SEC EDGAR 数据，对比同行营收规模、毛利率与净利率，雷达图直观呈现相对优势。</div>
        </div>
        """, unsafe_allow_html=True)

    # 数据统计条
    st.markdown(f"""
    <div class="stat-strip">
        <div>
            <div class="stat-item-label">已存档报告</div>
            <div class="stat-item-value">{report_count} 份</div>
        </div>
        <div>
            <div class="stat-item-label">财报季度覆盖</div>
            <div class="stat-item-value">{filing_count} 个季度</div>
        </div>
        <div>
            <div class="stat-item-label">数据来源</div>
            <div class="stat-item-value" style="font-size:0.9rem">SEC · Yahoo · NewsAPI</div>
        </div>
        <div>
            <div class="stat-item-label">分析标的</div>
            <div class="stat-item-value">{ticker}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    # ── 财务趋势图 ──
    st.markdown(f'<div class="section-label">{ticker} · 财务趋势</div>', unsafe_allow_html=True)
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)

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

        _NAVY = "#12102a"
        _BLUE = "#6c5ce7"
        _TEAL = "#00e5a0"
        _GOLD = "#f0b429"
        _GRID = "rgba(18,16,42,0.06)"

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
            height=440,
            margin=dict(l=0, r=0, t=32, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=11, color=_NAVY),
                bgcolor="rgba(0,0,0,0)"
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, Helvetica Neue, Arial", color=_NAVY),
        )
        fig.update_xaxes(showgrid=False, tickfont=dict(size=11), linecolor=_GRID)
        fig.update_yaxes(showgrid=True, gridcolor=_GRID, tickfont=dict(size=11), zeroline=False)
        fig.update_annotations(font_size=11, font_color="#8899bb")
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
    st.markdown('<div class="section-label">竞品横向对比</div>', unsafe_allow_html=True)

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
        _COMP_COLORS = ["#6c5ce7", "#f0b429", "#a29bfe"]

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
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    visible=True, range=[0, 100], showticklabels=False,
                    gridcolor="rgba(15,23,41,0.08)", linecolor="rgba(15,23,41,0.08)"
                ),
                angularaxis=dict(tickfont=dict(size=12, color="#0f1729"), linecolor="rgba(15,23,41,0.1)")
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5,
                font=dict(size=11, color="#0f1729"), bgcolor="rgba(0,0,0,0)"
            ),
            height=360,
            margin=dict(l=40, r=40, t=10, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, Helvetica Neue, Arial"),
        )

        col_radar, col_insights = st.columns([3, 2])
        with col_radar:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with col_insights:
            st.markdown('<div class="section-label" style="margin-top:1rem">关键洞察</div>', unsafe_allow_html=True)
            if comp_result.get("insights"):
                insights_html = "".join(
                    f'<div class="insight-row">{ins}</div>'
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
    st.markdown('<div class="section-label">最近报告</div>', unsafe_allow_html=True)
    with engine.connect() as conn:
        report_rows = conn.execute(
            text("SELECT id, ticker, question, created_at FROM reports WHERE ticker=:t ORDER BY created_at DESC LIMIT 5"),
            {"t": ticker}
        ).fetchall()
    if not report_rows:
        st.markdown(
            f'<div class="report-block"><div style="color:#9b8ec4;font-size:0.85rem;padding:0.5rem 0">'
            f'暂无 {ticker} 报告 — 前往「生成报告」创建第一份</div></div>',
            unsafe_allow_html=True
        )
    else:
        rows_html = '<div class="report-block">'
        for r in report_rows:
            q = r[2][:85] + ("…" if len(r[2]) > 85 else "")
            t_str = str(r[3])[:16]
            rows_html += (
                f'<div class="report-row">'
                f'<span class="report-id">#{r[0]}</span>'
                f'<span class="report-question">{q}</span>'
                f'<span class="report-time">{t_str}</span>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)


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
                # 用户选择了"继续深化"
                st.success("✅ 深度分析完成：已根据审查意见补充研究")

        with st.expander(f"工具调用链（共 {len(st.session_state.get('gen_tool_calls', []))} 次）", expanded=False):
            for i, call in enumerate(st.session_state.get("gen_tool_calls", []), 1):
                lbl = _TOOL_LABELS.get(call["tool"], ("🔧", call["tool"]))
                st.markdown(f"**{i}.** {lbl[0]} {lbl[1]}")
                st.caption(_fmt_input_hint(call["tool"], call["input"]))

        st.divider()
        st.subheader("📄 分析报告")
        st.markdown(st.session_state.gen_final)

        if st.button("🔄 重新分析", use_container_width=False):
            st.session_state.gen_stage = "idle"
            for k in ["gen_draft", "gen_tool_calls", "gen_reflection", "gen_final", "gen_report_id"]:
                st.session_state.pop(k, None)
            st.rerun()


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
                    st.markdown("**情绪分布**")
                    st.markdown(
                        f"""
                        <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;margin:4px 0 16px">
                            <div style="width:{bull}%;background:#10b981"></div>
                            <div style="width:{neutral}%;background:#94a3b8"></div>
                            <div style="width:{bear}%;background:#ef4444"></div>
                        </div>
                        <div style="display:flex;gap:16px;font-size:12px;color:gray">
                            <span>🟢 看多 {bull}%</span>
                            <span>⚪ 中性 {neutral}%</span>
                            <span>🔴 看空 {bear}%</span>
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
