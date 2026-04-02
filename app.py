"""
app.py — InvestIQ Streamlit Dashboard

运行：streamlit run app.py
"""

import streamlit as st
import json
import pandas as pd
from datetime import datetime

from agent.research_agent import run_research_agent, get_report_history, get_report_by_id
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
import os
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import create_engine, text
engine = create_engine(
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}",
    pool_pre_ping=True  # 每次使用前检查连接是否有效
)

# ── 页面配置 ──
st.set_page_config(
    page_title="InvestIQ — AI 投研 Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 样式 ──
st.markdown("""
<style>
.metric-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    border: 1px solid #e9ecef;
}
.tool-badge {
    display: inline-block;
    background: #e8f4fd;
    color: #1a6fa8;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    margin: 2px;
}
.report-card {
    border-left: 3px solid #4CAF50;
    padding-left: 12px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ── 侧边栏 ──
with st.sidebar:
    st.title("📈 InvestIQ")
    st.caption("AI 投资研究 Agent")
    st.divider()

    page = st.radio(
    "导航",
    ["🏠 首页", "📝 生成报告", "📚 历史报告", "📰 新闻概览", "🔧 系统状态"],
    label_visibility="collapsed"
)

    st.divider()
    ticker = st.selectbox(
        "分析标的",
        ["NVDA", "AMD", "INTC", "MSFT", "TSLA", "META"],
        index=0
    )
    st.caption(f"数据来源：SEC XBRL + NewsAPI")


    st.divider()
    st.subheader("数据更新")

    if st.button("🔄 刷新新闻", use_container_width=True):
        with st.spinner("拉取最新新闻..."):
            try:
                from tools.news_tool import fetch_and_store_news
                count = fetch_and_store_news(days_back=25, ticker=ticker)
                st.success(f"✓ 新增 {count} 条新闻")
            except Exception as e:
                st.error(f"失败：{e}")

    if st.button("📊 刷新财报", use_container_width=True):
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
                    st.info(f"数据已是最新（{count} 个季度，最新至 {latest}）")
                else:
                    fetch_and_store_filings(ticker=ticker, count=4)
                    st.success("✓ 财报数据已更新")
                    st.rerun()
            except Exception as e:
                st.error(f"失败：{e}")

    if st.button("⚡ 一键全部刷新", use_container_width=True, type="primary"):
        progress = st.progress(0, text="开始更新...")
        try:
            from tools.news_tool import fetch_and_store_news
            from tools.filing_tool import fetch_and_store_filings
            progress.progress(20, text="拉取新闻...")
            news_count = fetch_and_store_news(days_back=25, ticker=ticker)
            progress.progress(60, text="拉取财报...")
            fetch_and_store_filings(ticker=ticker, count=4)
            progress.progress(100, text="完成！")
            st.success(f"✓ 新闻 +{news_count} 条，财报已更新")
            st.rerun()
        except Exception as e:
            st.error(f"失败：{e}")


# ════════════════════════════════
# 首页
# ════════════════════════════════
if page == "🏠 首页":
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
    st.title("InvestIQ — AI 投资研究 Agent")
    st.caption("基于 ReAct 架构，自主调用多个数据工具，产出机构级研究报告")

    st.divider()

    # 关键指标卡片
    with engine.connect() as conn:
        report_count = conn.execute(text(f"SELECT COUNT(*) FROM reports WHERE ticker='{ticker}'")).scalar()
        filing_count = conn.execute(text(f"SELECT COUNT(*) FROM filings WHERE ticker='{ticker}'")).scalar()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("历史报告", f"{report_count} 份")
    with col2:
        st.metric("财报季度数据", f"{filing_count} 个季度")
    with col3:
        st.metric("可用工具", "6 个")
    with col4:
        st.metric("分析标的", ticker)

    st.divider()

    # Agent 架构说明
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Agent 工作流程")
        st.markdown("""
        这个系统是一个真正的 **ReAct Agent**，而不是固定流程的 Pipeline：

        1. **接收问题** → 用户输入投研问题
        2. **自主规划** → Claude 决定调用哪些工具、按什么顺序
        3. **工具调用** → 财报查询、新闻检索、竞品对比
        4. **观察结果** → 看到数据后决定下一步
        5. **反思循环** → 第二个 LLM 审查报告，发现不足
        6. **补充调用** → 针对缺失自动补充搜索
        7. **输出报告** → 结构化的机构级研究报告
        """)

    with col_right:
        st.subheader("可用工具")
        tools = [
            ("📊", "query_sec_filing", "SEC 财报查询"),
            ("📰", "search_news", "语义新闻检索"),
            ("📋", "get_recent_headlines", "近期标题概览"),
            ("📈", "get_financial_factors", "结构化财务因子"),
            ("🔄", "compare_quarterly_factors", "季度趋势对比"),
            ("⚡", "compare_with_competitors", "竞品横向对比"),
        ]
        for icon, name, desc in tools:
            st.markdown(f"{icon} **{name}**  \n{desc}")

    st.divider()
    # ── 财务趋势图 ──
    st.subheader(f"{ticker} 财务趋势")

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

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("季度营收（$B）", "毛利率（%）& 同比增速（%）")
        )

        fig.add_trace(go.Bar(
            x=periods, y=revenues, name="营收 ($B)",
            marker_color="#6366f1",
            text=[f"${v}B" for v in revenues],
            textposition="outside"
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=periods, y=margins, name="毛利率 (%)",
            line=dict(color="#10b981", width=2.5),
            mode="lines+markers+text",
            text=[f"{v}%" if v else "" for v in margins],
            textposition="top center"
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=periods, y=yoy_growths, name="同比增速 (%)",
            line=dict(color="#f59e0b", width=2, dash="dot"),
            mode="lines+markers",
        ), row=2, col=1)

        fig.update_layout(
            height=480,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
        st.plotly_chart(fig, use_container_width=True)

        # 关键数字摘要
        c1, c2, c3 = st.columns(3)
        c1.metric("最新季度营收", f"${revenues[-1]}B",
                  delta=f"{yoy_growths[-1]}% YoY" if yoy_growths[-1] else None)
        c2.metric("毛利率", f"{margins[-1]}%" if margins[-1] else "N/A",
                  delta=f"{round(margins[-1]-margins[-2],1)}pp" if len(margins)>=2 and margins[-1] and margins[-2] else None)
        c3.metric("数据覆盖", f"{len(periods)} 个季度")
    

    st.divider()
    # ── 竞品对比雷达图 ──
    st.subheader("竞品横向对比")

    with st.spinner("拉取竞品数据..."):
        from tools.competitor_tool import compare_with_competitors
        competitor_map = {
    "NVDA": ["AMD", "INTC"],
    "AMD":  ["NVDA", "INTC"],
    "INTC": ["NVDA", "AMD"],
    "MSFT": ["GOOGL", "AMZN"],
    "TSLA": ["F", "GM"],
    "META": ["GOOGL", "SNAP"],
}
        competitors = competitor_map.get(ticker, ["AMD", "INTC"])
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

        colors = ["#6366f1", "#f59e0b", "#94a3b8"]

        fig2 = go.Figure()
        for i, comp_ticker in enumerate(tickers):
            values = [rev_norm[i], gm_norm[i], nm_norm[i]]
            values_display = [revenues[i], gross_margins[i], net_margins[i]]
            fig2.add_trace(go.Scatterpolar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=comp_ticker,
                line=dict(color=colors[i], width=2),
                fillcolor=colors[i],
                opacity=0.25,
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
                angularaxis=dict(tickfont=dict(size=13))
            ),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            height=380,
            margin=dict(l=40, r=40, t=20, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 关键洞察文字
        if comp_result.get("insights"):
            st.caption("关键洞察")
            for insight in comp_result["insights"]:
                st.markdown(f"• {insight}")

        # 数据明细表
        with st.expander("查看原始数据"):
            df_comp = pd.DataFrame(table)
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
    else:
        st.warning("竞品数据获取失败，请检查网络连接")

    st.divider()
    # 最近报告预览
    st.subheader("最近生成的报告")
    with engine.connect() as conn:
        report_rows = conn.execute(
            text("SELECT id, ticker, question, created_at FROM reports WHERE ticker=:t ORDER BY created_at DESC LIMIT 3"),
            {"t": ticker}
        ).fetchall()
    if not report_rows:
        st.info(f"{ticker} 暂无报告，去「生成报告」页面创建第一份")
    else:
        for r in report_rows:
            st.markdown(f"""
            <div class="report-card">
            <strong>#{r[0]}</strong> {r[2][:70]}{'...' if len(r[2]) > 70 else ''}<br>
            <small style="color: gray">{str(r[3])[:16]}</small>
            </div>
            """, unsafe_allow_html=True)


# ════════════════════════════════
# 生成报告
# ════════════════════════════════
elif page == "📝 生成报告":
    #ticker = st.session_state.get("ticker", "NVDA")
    if ticker == "NVDA":
        preset_questions = {
            "自定义问题...": "",
            "📊 全面投资价值分析": "基于最新财报、竞品对比和近期新闻，NVDA 当前的投资价值如何？看多和看空的核心论点分别是什么？",
            "📉 毛利率风险": "NVDA 的毛利率下滑趋势是否值得担忧？Blackwell 良率问题有多严重？",
            "⚔️ 竞品对比分析": "从竞品对比角度看，NVDA 相对 AMD 的估值溢价是否合理？",
            "🤖 DeepSeek 威胁评估": "DeepSeek 对 NVDA 的长期需求逻辑是否构成实质威胁？",
            "🌏 出口管制风险": "NVDA 的出口管制风险有多大？中国市场收入占比及影响分析",
        }
    else:
        preset_questions = {
            "自定义问题...": "",
            "📊 全面投资价值分析": f"基于最新财报、竞品对比和近期新闻，{ticker} 当前的投资价值如何？看多和看空的核心论点分别是什么？",
            "📉 毛利率风险": f"{ticker} 的毛利率下滑趋势是否值得担忧？Blackwell 良率问题有多严重？",
            "⚔️ 竞品对比分析": f"从竞品对比角度看，{ticker} 相对 AMD 的估值溢价是否合理？",
            "🤖 DeepSeek 威胁评估": f"DeepSeek 对 {ticker} 的长期需求逻辑是否构成实质威胁？",
            "🌏 出口管制风险": f"{ticker} 的出口管制风险有多大？中国市场收入占比及影响分析",
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
        use_reflection = st.toggle("启用反思循环", value=True, help="开启后 Agent 会自动检查报告质量并补充不足")
    with col2:
        if use_reflection:
            st.caption("✓ Agent 将生成初稿 → 审查质量 → 补充信息 → 输出最终报告")
        else:
            st.caption("Agent 将直接生成报告，速度更快")

    if st.button("🚀 开始分析", type="primary", disabled=not question.strip()):

        # 实时日志容器
        st.markdown("**Agent 思考过程**")
        log_box = st.container(border=True)
        step_counter = [0]
        log_lines = []

        def on_tool_call(status, tool_name, tool_input, result):
            step_counter[0] += 1
            if status == "calling":
                line = f"⏳ **Step {step_counter[0]}** · `{tool_name}`  \n`{json.dumps(tool_input, ensure_ascii=False)[:80]}`"
                log_lines.append(("calling", line, tool_name))
            else:
                # 把最后一个 calling 改成 done
                for i in range(len(log_lines)-1, -1, -1):
                    if log_lines[i][0] == "calling" and log_lines[i][2] == tool_name:
                        preview = str(result)[:120].replace("\n", " ")
                        log_lines[i] = ("done", f"✓ **Step {step_counter[0]}** · `{tool_name}`  \n`{preview}`", tool_name)
                        break

            with log_box:
                log_box.empty()
                for _, line, _ in log_lines:
                    st.markdown(line)

        result_container = st.empty()

        try:
            result = run_research_agent(
                question=question,
                ticker=ticker,
                use_reflection=use_reflection,
                on_tool_call=on_tool_call
            )

            # 日志改成折叠
            with st.expander(f"✓ 完成 — 共 {len(result['tool_calls'])} 次工具调用", expanded=False):
                for i, call in enumerate(result["tool_calls"], 1):
                    st.markdown(f"**{i}.** `{call['tool']}`")
                    st.caption(json.dumps(call['input'], ensure_ascii=False)[:100])

            st.divider()
            st.subheader("📄 分析报告")
            st.markdown(result["answer"])

        except Exception as e:
            st.error(f"生成失败：{str(e)}")
            st.error(f"错误类型: {type(e).__name__}")
            st.error(f"详细信息: {str(e)}")
            st.error(f"Traceback:\n{traceback.format_exc()}")


# ════════════════════════════════
# 历史报告
# ════════════════════════════════
elif page == "📚 历史报告":
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
elif page == "📰 新闻概览":
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
elif page == "🔧 系统状态":
    #ticker = st.session_state.get("ticker", "NVDA")
    st.title("系统状态")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("数据库")
        try:
            with engine.connect() as conn:
                filing_rows = conn.execute(
                text(f"SELECT period, raw_text FROM filings WHERE ticker='{ticker}' ORDER BY period DESC")).fetchall()

            st.success("PostgreSQL 连接正常")
            if filing_rows:
                records = []
                for r in filing_rows:
                    d = json.loads(r[1]) if r[1] else {}
                    records.append({
            "季度": r[0],
            "毛利率(%)": d.get("gross_margin"),
            "同比增速(%)": d.get("revenue_growth_yoy"),
        })
                df = pd.DataFrame(records)
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"连接失败：{e}")

    with col2:
        st.subheader("向量数据库")
        try:
            from vector_store import get_collection
            col = get_collection("investiq_news")
            count = col.count()
            st.success(f"Chroma 连接正常")
            st.metric("新闻条数", f"{count} 条")
        except Exception as e:
            st.error(f"连接失败：{e}")

    st.divider()
    st.subheader("财务数据预览")
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT period, raw_text FROM filings WHERE ticker='{ticker}' ORDER BY period DESC LIMIT 6")
            ).fetchall()

        records = []
        for r in rows:
            d = json.loads(r[1]) if r[1] else {}
            rev = d.get("revenue")
            records.append({
                "季度": r[0],
                "营收": f"${rev/1e9:.1f}B" if rev else "N/A",
                "毛利率": f"{d.get('gross_margin')}%" if d.get('gross_margin') else "N/A",
                "同比增速": f"{d.get('revenue_growth_yoy')}%" if d.get('revenue_growth_yoy') else "N/A",
                "净利润": f"${d.get('net_income')/1e9:.1f}B" if d.get('net_income') else "N/A",
            })

        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"数据读取失败：{e}")
