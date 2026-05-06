"""
app_components.py — InvestIQ Terminal 渲染组件
所有函数返回/渲染 HTML 字符串，配合 app_styles.py 的 CSS 使用。
"""
import time
import html as _html
import streamlit as st


# ─────────────────────────────────────────────
# 工具调用流（Agent ReAct 推理过程的可视化）
# ─────────────────────────────────────────────

# 工具中文名映射（与 research_agent.py 的 ALL_TOOLS 对齐）
_TOOL_LABELS = {
    "query_sec_filing":          ("📄", "查询 SEC 财报"),
    "search_news":               ("📰", "语义检索新闻"),
    "get_recent_headlines":      ("📡", "获取近期头条"),
    "get_financial_factors":     ("📊", "提取财务因子"),
    "compare_quarterly_factors": ("📈", "对比季度趋势"),
    "compare_with_competitors":  ("⚔️", "与竞品横向对比"),
}


def make_tool_stream_callback(slot):
    """
    返回一个 on_tool_call 回调，传给 research_agent.run_pass1 / run_research_agent。
    每次 Agent 调用工具时，把这一步追加渲染到 slot 容器里。

    用法：
        slot = st.container()
        cb = make_tool_stream_callback(slot)
        result = run_research_agent(question, ticker, on_tool_call=cb)
    """
    state = {"steps": [], "t0": time.time()}

    def _render():
        rows = ""
        for i, step in enumerate(state["steps"], 1):
            icon, label = _TOOL_LABELS.get(step["tool"], ("⚙️", step["tool"]))
            params = step.get("input", {})
            param_str = " · ".join(
                f'<span style="color:var(--text-3)">{k}</span>=<span class="mono" style="color:var(--text-1)">{_html.escape(str(v))[:48]}</span>'
                for k, v in list(params.items())[:3]
            )
            status = step.get("status", "running")
            if status == "done":
                badge = '<span class="mono up" style="font-size:10px">✓ DONE</span>'
                dot = '<span style="color:var(--up)">●</span>'
            elif status == "error":
                badge = '<span class="mono down" style="font-size:10px">✗ ERROR</span>'
                dot = '<span style="color:var(--down)">●</span>'
            else:
                badge = '<span class="mono" style="font-size:10px; color:var(--gold)">▸ RUNNING</span>'
                dot = '<span style="color:var(--gold); animation:blink 1s infinite">●</span>'

            elapsed = step.get("elapsed", 0)
            elapsed_str = f"{elapsed:.2f}s" if elapsed else "—"

            rows += f"""
            <div style="display:grid; grid-template-columns:28px 1fr auto 60px;
                        gap:10px; padding:10px 16px; border-bottom:1px solid var(--line);
                        align-items:center;">
              <div class="mono" style="font-size:10px; color:var(--text-3); text-align:right">
                {dot}&nbsp;{i:02d}
              </div>
              <div style="min-width:0">
                <div style="font-size:12.5px; color:var(--text-0); margin-bottom:2px">
                  <span style="margin-right:6px">{icon}</span>{label}
                  <span class="mono" style="font-size:10px; color:var(--text-3); margin-left:8px">{step["tool"]}</span>
                </div>
                <div style="font-size:11px; line-height:1.4">{param_str}</div>
              </div>
              <div>{badge}</div>
              <div class="mono" style="font-size:10px; color:var(--text-3); text-align:right">
                {elapsed_str}
              </div>
            </div>
            """

        slot.markdown(f"""
        <div class="iq-panel" style="margin-bottom:1rem">
          <div class="iq-panel-head">
            <span class="badge-ai">AGENT · REACT TRACE</span>
            <span style="font-size:13px; color:var(--text-0); white-space:nowrap">推理过程实时流</span>
            <span style="flex:1"></span>
            <span class="mono" style="font-size:10.5px; color:var(--text-3); white-space:nowrap">
              已调用 {len(state["steps"])} 个工具 · 总耗时 {time.time()-state["t0"]:.1f}s
            </span>
          </div>
          <div>{rows or '<div style="padding:18px 22px; color:var(--text-3); font-size:12px">等待 Agent 启动…</div>'}</div>
        </div>
        """, unsafe_allow_html=True)

    def callback(event: str, payload: dict):
        # event: 'start' | 'end' | 'error' —— 由 research_agent 触发
        if event == "start":
            state["steps"].append({
                "tool": payload.get("tool", "?"),
                "input": payload.get("input", {}),
                "status": "running",
                "_t": time.time(),
            })
        elif event in ("end", "error"):
            if state["steps"]:
                last = state["steps"][-1]
                last["status"] = "done" if event == "end" else "error"
                last["elapsed"] = time.time() - last.get("_t", time.time())
        _render()

    # 立即渲染空 panel
    _render()
    return callback


def render_static_tool_trace(tool_calls: list):
    """报告生成后，用静态形式回放工具调用列表（已完成态）。"""
    if not tool_calls:
        return
    rows = ""
    for i, c in enumerate(tool_calls, 1):
        tool = c.get("tool", "?")
        icon, label = _TOOL_LABELS.get(tool, ("⚙️", tool))
        params = c.get("input", {})
        param_str = " · ".join(
            f'<span style="color:var(--text-3)">{k}</span>=<span class="mono" style="color:var(--text-1)">{_html.escape(str(v))[:48]}</span>'
            for k, v in list(params.items())[:3]
        )
        rows += f"""
        <div style="display:grid; grid-template-columns:28px 1fr auto;
                    gap:10px; padding:9px 16px; border-bottom:1px solid var(--line);
                    align-items:center;">
          <div class="mono" style="font-size:10px; color:var(--up); text-align:right">●&nbsp;{i:02d}</div>
          <div>
            <div style="font-size:12.5px; color:var(--text-0); margin-bottom:2px">
              <span style="margin-right:6px">{icon}</span>{label}
              <span class="mono" style="font-size:10px; color:var(--text-3); margin-left:8px">{tool}</span>
            </div>
            <div style="font-size:11px; line-height:1.4">{param_str}</div>
          </div>
          <div><span class="mono up" style="font-size:10px">✓ DONE</span></div>
        </div>
        """
    st.markdown(f"""
    <div class="iq-panel" style="margin-bottom:1rem">
      <div class="iq-panel-head">
        <span class="badge-ai">AGENT · REACT TRACE</span>
        <span style="font-size:13px; color:var(--text-0)">工具调用回放</span>
        <span style="flex:1"></span>
        <span class="mono" style="font-size:10.5px; color:var(--text-3)">共 {len(tool_calls)} 步</span>
      </div>
      <div>{rows}</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 报告打字机渲染（流式呈现 markdown）
# ─────────────────────────────────────────────

def render_typewriter_report(slot, markdown_text: str, *,
                             chunk_chars: int = 6, frame_delay: float = 0.012,
                             eyebrow: str = "AI · DEEP RESEARCH",
                             title: str = "多智能体投研报告",
                             right: str = ""):
    """
    把已生成的报告 markdown 用打字机效果渲染到 slot 容器里。
    生成完成后在 Streamlit 端调用一次即可（动画在主线程模拟 streaming）。

    chunk_chars: 每帧追加多少字符（越大越快）
    frame_delay: 每帧间隔秒数（越小越快）
    """
    if not markdown_text:
        slot.warning("报告为空。")
        return

    head_html = f"""
    <div class="iq-panel">
      <div class="iq-panel-head">
        <span class="badge-ai">{_html.escape(eyebrow)}</span>
        <span style="font-size:13.5px; font-weight:500; color:var(--text-0); white-space:nowrap">{_html.escape(title)}</span>
        <span style="flex:1"></span>
        <span class="mono" style="font-size:10.5px; color:var(--text-3); white-space:nowrap">{_html.escape(right)}</span>
      </div>
      <div class="iq-panel-body" style="min-height:200px">
    """
    cursor = '<span style="display:inline-block; width:8px; height:16px; background:var(--gold); margin-left:2px; vertical-align:text-bottom; animation:blink 1s steps(1) infinite"></span>'

    n = len(markdown_text)
    pos = 0
    while pos < n:
        pos = min(n, pos + chunk_chars)
        partial = markdown_text[:pos]
        is_done = pos >= n
        # Streamlit 不支持在 markdown 中混合 HTML wrapper + markdown 内容
        # 所以我们用两次 markdown 调用：HTML 头 + markdown 主体 + HTML 尾。
        # 用 slot.empty() 容器整体重写。
        with slot.container():
            st.markdown(head_html, unsafe_allow_html=True)
            st.markdown(partial + ("" if is_done else cursor), unsafe_allow_html=True)
            st.markdown("</div></div>", unsafe_allow_html=True)
        if not is_done:
            time.sleep(frame_delay)


# ─────────────────────────────────────────────
# 决策摘要 → 信号卡 / 雷达图 / 多空对比
# ─────────────────────────────────────────────

def render_decision_block(decision: dict):
    """
    一站式渲染 research_agent.extract_decision() 的输出：
    - 顶部 BUY/HOLD/SELL 信号卡（含目标价/止损/期限）
    - 下方多空双栏论点对比
    - 关键跟踪指标 chips

    decision 为 None / 空时优雅降级，不渲染任何东西。
    """
    if not decision:
        st.info("本次报告未生成结构化决策摘要，仅展示 markdown 正文。")
        return

    # 顶部信号卡
    render_signal_card(
        signal=decision.get("signal", "HOLD"),
        score=decision.get("score", 50),
        summary=decision.get("thesis", "—"),
        target=decision.get("target_price", ""),
        stop=decision.get("stop_loss", ""),
    )

    # 期限 + 关键指标
    horizon = decision.get("horizon", "")
    metrics = decision.get("key_metrics", [])
    if horizon or metrics:
        chips = "".join(
            f'<span class="badge-soft" style="margin-right:6px; padding:3px 8px">{_html.escape(m)}</span>'
            for m in metrics
        )
        st.markdown(f"""
        <div style="display:flex; gap:14px; align-items:center; padding:10px 0 14px; flex-wrap:wrap">
          <span class="eyebrow">持仓期限</span>
          <span class="mono" style="font-size:13px; color:var(--gold)">{_html.escape(horizon)}</span>
          <span style="width:1px; height:14px; background:var(--line)"></span>
          <span class="eyebrow">需跟踪指标</span>
          <span>{chips}</span>
        </div>
        """, unsafe_allow_html=True)

    # 多空双栏
    bulls = decision.get("bull_points", [])
    bears = decision.get("bear_points", [])
    if bulls or bears:
        bull_items = "".join(
            f'<li style="margin:6px 0; line-height:1.5; font-size:13px">{_html.escape(b)}</li>' for b in bulls
        ) or '<li style="color:var(--text-3)">—</li>'
        bear_items = "".join(
            f'<li style="margin:6px 0; line-height:1.5; font-size:13px">{_html.escape(b)}</li>' for b in bears
        ) or '<li style="color:var(--text-3)">—</li>'
        st.markdown(f"""
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:1rem">
          <div class="iq-panel" style="margin:0">
            <div class="iq-panel-head" style="border-bottom:2px solid var(--up)">
              <span class="badge-soft" style="border-color:var(--up); color:var(--up)">▲ BULL</span>
              <span style="font-size:13px; color:var(--text-0)">看多论点</span>
            </div>
            <div class="iq-panel-body">
              <ul style="margin:0; padding-left:18px; color:var(--text-1)">{bull_items}</ul>
            </div>
          </div>
          <div class="iq-panel" style="margin:0">
            <div class="iq-panel-head" style="border-bottom:2px solid var(--down)">
              <span class="badge-soft" style="border-color:var(--down); color:var(--down)">▼ BEAR</span>
              <span style="font-size:13px; color:var(--text-0)">看空论点</span>
            </div>
            <div class="iq-panel-body">
              <ul style="margin:0; padding-left:18px; color:var(--text-1)">{bear_items}</ul>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)


def render_decision_radar(decision: dict, height: int = 340):
    """
    用 Plotly 把 decision['radar'] 画成 6 维雷达图（终端配色）。
    decision['radar'] = {"基本面": 0-10, "成长性": 0-10, ...}
    """
    radar = (decision or {}).get("radar") or {}
    if not radar:
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        return

    cats = list(radar.keys())
    vals = [float(radar.get(k, 0)) for k in cats]
    cats_closed = cats + cats[:1]
    vals_closed = vals + vals[:1]

    sig = (decision.get("signal") or "HOLD").upper()
    color = {"BUY": "#00d68f", "SELL": "#ff4d6d"}.get(sig, "#d4a647")

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_closed, theta=cats_closed, fill="toself",
        line=dict(color=color, width=2),
        fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba")
                  if color.startswith("rgb") else color + "30",
        name=f"{decision.get('signal','HOLD')} 信号",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 10], visible=True, tickvals=[2, 4, 6, 8, 10])),
        showlegend=False,
    )
    plotly_terminal_layout(fig, height=height)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# 顶部全球行情跑马灯静态数据（也可改为后端动态拉取）
GLOBAL_TAPE = [
    ("SPX", "6,124.30", "+0.42%", "up"),
    ("NDX", "22,019.55", "+0.71%", "up"),
    ("DJI", "44,180.12", "+0.18%", "up"),
    ("RUT", "2,318.40", "-0.21%", "down"),
    ("VIX", "13.84", "-2.05%", "down"),
    ("BTC", "98,210", "+1.34%", "up"),
    ("ETH", "3,612", "+0.88%", "up"),
    ("WTI", "72.18", "-0.55%", "down"),
    ("GOLD", "2,844", "+0.31%", "up"),
    ("DXY", "104.21", "-0.12%", "down"),
    ("UST10Y", "4.31%", "+2bp", "up"),
    ("USDJPY", "153.40", "-0.18%", "down"),
    ("USDCNH", "7.184", "+0.05%", "up"),
]


def render_tape(items=None):
    """全局行情跑马灯。在 nav 上方调用一次。"""
    items = items or GLOBAL_TAPE
    items_dup = items + items  # 无缝循环
    track_html = "".join(
        f'<div class="tape-item">'
        f'<span class="sym">{sym}</span>'
        f'<span class="px">{px}</span>'
        f'<span class="ch {cls}">{ch}</span>'
        f'</div>'
        for sym, px, ch, cls in items_dup
    )
    st.markdown(f"""
    <div class="tape-bar">
      <div class="tape-label"><span class="live-dot"></span>LIVE · 全球行情</div>
      <div class="tape-track">{track_html}</div>
    </div>
    """, unsafe_allow_html=True)


def render_quote_hero(ticker: str, mkt: dict, name: str = "", sector: str = ""):
    """终端风 Hero 报价区。
    mkt: get_market_data 返回的字典，含 price/day_change_pct/week52_low/week52_high/market_cap/pe/forward_pe
    """
    price = mkt.get("price") or 0
    chg = mkt.get("day_change_pct") or 0
    up = chg >= 0
    arrow = "▲" if up else "▼"
    chip_cls = "chip-up" if up else "chip-down"
    color_cls = "up" if up else "down"
    delta_dollar = price * chg / 100

    lo = mkt.get("week52_low") or 0
    hi = mkt.get("week52_high") or 0
    pos = ((price - lo) / (hi - lo) * 100) if (hi and lo and hi > lo) else 50
    pos = max(0, min(100, pos))

    st.markdown(f"""
    <div class="quote-hero" data-ticker="{ticker}">
      <div class="quote-row">
        <div style="min-width:0; flex:1">
          <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px">
            <span class="quote-ticker">{ticker}</span>
            <span class="quote-tag">NASDAQ · USD</span>
            <span class="live-dot"></span>
            <span style="font-size:11px; color:var(--text-2)">开盘中</span>
          </div>
          <div class="quote-name">{name} <span style="color:var(--text-3)">{('· ' + sector) if sector else ''}</span></div>
        </div>
        <div style="text-align:right; flex-shrink:0; white-space:nowrap">
          <div class="quote-price-big {color_cls}">${price:,.2f}</div>
          <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:10px">
            <span class="{chip_cls} mono">{arrow} {abs(chg):.2f}%</span>
            <span class="mono" style="font-size:13px; color:var(--text-2)">
              {'+' if up else '-'}${abs(delta_dollar):,.2f}
            </span>
          </div>
        </div>
      </div>

      <div style="border-top:1px solid var(--line); padding-top:14px; margin-top:18px">
        <div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:8px">
          <span style="font-size:11px; color:var(--text-3); letter-spacing:.15em; white-space:nowrap">52 周区间</span>
          <span class="mono" style="font-size:11px; color:var(--text-2); white-space:nowrap">当前位于 {pos:.0f}%</span>
        </div>
        <div class="range-bar">
          <div class="range-fill" style="width:{pos}%"></div>
          <div class="range-pin" style="left:{pos}%"></div>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:6px">
          <span class="mono down" style="font-size:11px">${lo:.2f}</span>
          <span class="mono up" style="font-size:11px">${hi:.2f}</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpi_strip(kpis):
    """6 个 KPI 卡条带。
    kpis: List[dict(label, value, sub, accent)] —— accent 可为 'up'/'down'/None
    """
    cards = ""
    for k in kpis:
        cls = "kpi-card"
        if k.get("accent") == "up": cls += " accent-up"
        elif k.get("accent") == "down": cls += " accent-down"
        sub = f'<div class="kpi-sub">{k.get("sub","")}</div>' if k.get("sub") else ""
        cards += f"""
        <div class="{cls}">
          <div class="kpi-label">{k['label']}</div>
          <div class="kpi-value">{k['value']}</div>
          {sub}
        </div>"""
    st.markdown(f'<div class="kpi-strip">{cards}</div>', unsafe_allow_html=True)


def kpis_from_market(mkt: dict, financials: dict = None):
    """从 get_market_data + 财报字典构造 KPI 列表。financials 可包含 revenue_growth_yoy / gross_margin / net_margin。"""
    fin = financials or {}
    cap = mkt.get("market_cap")
    cap_str = (f"${cap/1e12:.2f}T" if cap and cap >= 1e12
               else f"${cap/1e9:.0f}B" if cap else "—")
    pe = mkt.get("pe"); fpe = mkt.get("forward_pe")
    pe_s = f"{pe:.1f}×" if pe else "—"
    fpe_s = f"远期 PE  {fpe:.1f}×" if fpe else "—"

    rev_g = fin.get("revenue_growth_yoy")
    gm = fin.get("gross_margin")
    nm = fin.get("net_margin")

    return [
        {"label": "市值 MKT CAP", "value": cap_str, "sub": "美元 · USD"},
        {"label": "市盈率 P/E (TTM)", "value": pe_s, "sub": fpe_s},
        {"label": "营收增速 YoY", "value": (f"{rev_g:+.1f}%" if rev_g else "—"),
         "sub": "季度 · GAAP", "accent": "up" if (rev_g and rev_g > 0) else "down" if rev_g else None},
        {"label": "毛利率 GROSS", "value": (f"{gm:.1f}%" if gm else "—"), "sub": "最近一季"},
        {"label": "净利率 NET", "value": (f"{nm:.1f}%" if nm else "—"), "sub": "最近一季",
         "accent": "up" if (nm and nm > 0) else None},
        {"label": "今日波动", "value": (f"{(mkt.get('day_change_pct') or 0):+.2f}%"), "sub": "Yahoo · 5m 缓存"},
    ]


def render_panel_open(eyebrow: str = "", title: str = "", right: str = ""):
    """打开一个 iq-panel；调用 render_panel_close 关闭。"""
    eb = f'<span class="badge-ai">{eyebrow}</span>' if eyebrow else ""
    rt = f'<span class="mono" style="margin-left:auto; font-size:10.5px; color:var(--text-3); white-space:nowrap">{right}</span>' if right else ""
    st.markdown(f"""
    <div class="iq-panel">
      <div class="iq-panel-head">
        {eb}
        <span style="font-size:13.5px; font-weight:500; color:var(--text-0); white-space:nowrap">{title}</span>
        {rt}
      </div>
      <div class="iq-panel-body">
    """, unsafe_allow_html=True)


def render_panel_close():
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_signal_card(signal: str, score: int, summary: str, target: str = "", stop: str = ""):
    """AI 信号卡片：BUY/HOLD/SELL + 置信度条 + 目标价/止损。"""
    signal = (signal or "HOLD").upper()
    cls = {"BUY": "signal-buy", "SELL": "signal-sell"}.get(signal, "signal-hold")
    bar_color = {"BUY": "var(--up)", "SELL": "var(--down)"}.get(signal, "var(--gold)")
    target_html = f'目标价 <span class="mono up">{target}</span>  ' if target else ""
    stop_html = f'止损 <span class="mono down">{stop}</span>' if stop else ""
    st.markdown(f"""
    <div class="iq-panel" style="display:grid; grid-template-columns:180px 1fr; gap:0;">
      <div style="padding:22px 20px; border-right:1px solid var(--line); text-align:center">
        <div class="eyebrow" style="margin-bottom:8px">AI 综合信号</div>
        <div class="signal-big {cls}">{signal}</div>
        <div class="mono" style="font-size:11px; color:var(--text-2); margin-top:8px">置信度 {score}/100</div>
        <div class="signal-bar"><div style="width:{score}%; background:{bar_color}"></div></div>
      </div>
      <div style="padding:18px 22px">
        <div class="eyebrow" style="margin-bottom:8px">核心论点</div>
        <p style="margin:0 0 10px; font-size:14px; line-height:1.6; color:var(--text-1)">{summary}</p>
        <div style="font-size:11.5px; color:var(--text-2)">{target_html}{stop_html}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_status_bar(extra: str = ""):
    """底部状态栏。"""
    st.markdown(f"""
    <div class="iq-statusbar">
      <span style="display:flex; align-items:center; gap:6px">
        <span class="live-dot"></span><span>所有数据源在线</span>
      </span>
      <span>SEC EDGAR ✓</span>
      <span>Yahoo ✓</span>
      <span>NewsAPI ✓</span>
      <span>Chroma ✓</span>
      <span>Postgres ✓</span>
      <span style="flex:1"></span>
      <span>{extra}</span>
      <span style="color:var(--text-2)">本平台仅用于信息提供, 不构成任何投资建议</span>
    </div>
    """, unsafe_allow_html=True)


def plotly_terminal_layout(fig, height=360):
    """把 Plotly figure 改造成终端深色配色。直接修改 fig 并返回。"""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Noto Sans SC", color="#c9d1dc", size=11),
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(font=dict(color="#c9d1dc"), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,.04)", zerolinecolor="rgba(255,255,255,.04)",
                     linecolor="rgba(255,255,255,.08)", tickfont=dict(color="#8893a4"))
    fig.update_yaxes(gridcolor="rgba(255,255,255,.04)", zerolinecolor="rgba(255,255,255,.04)",
                     linecolor="rgba(255,255,255,.08)", tickfont=dict(color="#8893a4"))
    # 雷达图（polar）
    try:
        fig.update_polars(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(gridcolor="rgba(255,255,255,.06)", linecolor="rgba(255,255,255,.06)",
                            tickfont=dict(color="#5d6878")),
            angularaxis=dict(gridcolor="rgba(255,255,255,.06)", linecolor="rgba(255,255,255,.08)",
                             tickfont=dict(color="#c9d1dc", size=12)),
        )
    except Exception:
        pass
    return fig


# 终端风 Plotly 颜色板（金/绿/红/蓝）
TERMINAL_COLORS = {
    "gold": "#d4a647",
    "up": "#00d68f",
    "down": "#ff4d6d",
    "accent": "#4d7cff",
    "accent2": "#8a6dff",
    "grid": "rgba(255,255,255,.06)",
    "text": "#c9d1dc",
    "text_dim": "#5d6878",
}
