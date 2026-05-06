"""
app_styles.py — InvestIQ Terminal 主题
用法：在 app.py 顶部 from app_styles import inject_terminal_css; inject_terminal_css()
"""
import streamlit as st


def inject_terminal_css():
    """注入彭博终端风格的全局 CSS。替换 app.py 中现有的 st.markdown(<style>...) 块。"""
    st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Noto+Sans+SC:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">

<style>
:root {
  --bg-0:#07090c; --bg-1:#0c1015; --bg-2:#11161d; --bg-3:#181f29;
  --line:#1f2733; --line-2:#2a3442;
  --text-0:#f5f7fa; --text-1:#c9d1dc; --text-2:#8893a4; --text-3:#5d6878;
  --up:#00d68f; --up-glow:rgba(0,214,143,.18);
  --down:#ff4d6d; --down-glow:rgba(255,77,109,.18);
  --gold:#d4a647; --accent:#4d7cff; --accent-2:#8a6dff;
}

/* ══ 全局 ══ */
html, body, [class*="css"] {
  font-family:"IBM Plex Sans","Noto Sans SC",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  font-size:14.5px; letter-spacing:.01em;
  font-feature-settings:"tnum" 1,"ss01" 1;
  -webkit-font-smoothing:antialiased;
}
.stApp { background:var(--bg-0) !important; }
.block-container { padding-top:.5rem; padding-bottom:3rem; max-width:1480px; }
[data-testid="stAppViewContainer"] { background:var(--bg-0); }
[data-testid="stAppViewContainer"] > section > div:first-child { padding-top:0; }
[data-testid="stHeader"] {
  background:var(--bg-0) !important;
  border-bottom:1px solid var(--line) !important;
}
[data-testid="stToolbar"] { filter: invert(1) brightness(0.6); }

.stApp::before {
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background-image:
    linear-gradient(rgba(255,255,255,.012) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.012) 1px, transparent 1px);
  background-size:48px 48px;
}

p,li,span,div,label { color:var(--text-1); }
.mono, .mono * { font-family:"IBM Plex Mono",ui-monospace,monospace !important; font-feature-settings:"tnum" 1; }
.up { color:var(--up) !important; }
.down { color:var(--down) !important; }
.muted { color:var(--text-2) !important; }
.dim { color:var(--text-3) !important; }

/* scrollbar */
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-thumb { background:#222b38; border-radius:4px; }
::-webkit-scrollbar-track { background:transparent; }

/* ══ 标题 ══ */
h1 { font-size:2rem !important; font-weight:600 !important; color:var(--text-0) !important;
     letter-spacing:-.02em !important; margin-bottom:.3rem !important; }
h2 { font-size:1.05rem !important; font-weight:500 !important; color:var(--text-0) !important; }
h3 { font-size:.92rem !important; font-weight:500 !important; color:var(--text-0) !important; }

/* ══ 侧边栏 ══ */
[data-testid="stSidebar"] { background:var(--bg-1); border-right:1px solid var(--line); }
[data-testid="stSidebar"] > div { padding:.75rem 1rem 1.5rem; }
[data-testid="stSidebar"] * { color:var(--text-1) !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {
  background:var(--bg-2) !important; border:1px solid var(--line) !important;
  border-radius:6px !important; color:var(--text-0) !important;
  font-family:"IBM Plex Mono",monospace !important; font-weight:500;
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input {
  background:var(--bg-2) !important; border:1px solid var(--line) !important;
  border-radius:6px !important; color:var(--text-0) !important;
}
[data-testid="stSidebar"] .stButton > button {
  background:var(--bg-2); border:1px solid var(--line);
  color:var(--text-1) !important; font-weight:500; font-size:.82rem;
  border-radius:6px; padding:.45rem 1rem;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background:var(--bg-3); border-color:var(--line-2);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background:linear-gradient(180deg,rgba(212,166,71,.22),rgba(212,166,71,.08));
  border:1px solid var(--gold); color:var(--gold) !important; font-weight:600;
}

/* ══ 跑马灯 ══ */
@keyframes ticker { from{transform:translateX(0)} to{transform:translateX(-50%)} }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes spin { to{transform:rotate(360deg)} }
@keyframes shimmer { 0%{background-position:-400px 0} 100%{background-position:400px 0} }

.tape-bar {
  background:var(--bg-1); border-bottom:1px solid var(--line);
  height:34px; overflow:hidden; position:relative;
  margin:-.5rem -1rem 1rem; display:flex; align-items:center;
}
.tape-label {
  position:absolute; left:0; top:0; bottom:0; width:160px; z-index:2;
  background:linear-gradient(90deg, var(--bg-1) 70%, transparent);
  display:flex; align-items:center; gap:8px; padding-left:14px;
  font-family:"IBM Plex Mono",monospace; font-size:11px;
  color:var(--text-2); letter-spacing:.15em;
}
.live-dot {
  display:inline-block; width:6px; height:6px; border-radius:50%;
  background:var(--up); box-shadow:0 0 10px var(--up);
  animation:blink 1.6s ease-in-out infinite;
}
.tape-track {
  display:flex; gap:34px; animation:ticker 80s linear infinite;
  white-space:nowrap; padding-left:170px;
}
.tape-item { display:flex; align-items:center; gap:8px; font-size:12px; }
.tape-item .sym { color:var(--text-2); letter-spacing:.05em; }
.tape-item .px  { font-family:"IBM Plex Mono",monospace; color:var(--text-0); }
.tape-item .ch  { font-family:"IBM Plex Mono",monospace; font-size:11px; }

/* ══ 顶部 nav ══ */
.iq-topnav {
  background:var(--bg-1); border:1px solid var(--line); border-radius:8px;
  padding:.4rem .75rem; margin-bottom:1rem;
  display:flex; align-items:center; gap:.4rem;
}

/* ══ Hero 报价 ══ */
.quote-hero {
  background:var(--bg-1); border:1px solid var(--line); border-radius:8px;
  padding:1.5rem 1.75rem; margin-bottom:1rem; position:relative; overflow:hidden;
}
.quote-hero::after {
  content: attr(data-ticker); position:absolute; right:-30px; top:-50px;
  font-size:200px; font-weight:700; color:rgba(255,255,255,.018);
  letter-spacing:-.06em; pointer-events:none;
  font-family:"IBM Plex Mono",monospace;
}
.quote-row { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; position:relative; }
.quote-ticker {
  font-family:"IBM Plex Mono",monospace; font-size:28px; font-weight:600;
  letter-spacing:.02em; color:var(--text-0); margin:0;
}
.quote-tag {
  display:inline-block; font-size:10px; color:var(--text-3); letter-spacing:.18em;
  padding:2px 6px; border:1px solid var(--line-2); border-radius:3px;
  margin-left:8px; vertical-align:middle;
}
.quote-name { font-size:13px; color:var(--text-1); margin-top:4px; }
.quote-sector { font-size:11.5px; color:var(--text-3); margin-top:2px; }
.quote-price-big {
  font-family:"IBM Plex Mono",monospace; font-size:42px; font-weight:500;
  line-height:1; white-space:nowrap;
}
.chip-up {
  font-family:"IBM Plex Mono",monospace; font-size:13px; padding:3px 8px;
  border-radius:3px; background:var(--up-glow); color:var(--up);
}
.chip-down {
  font-family:"IBM Plex Mono",monospace; font-size:13px; padding:3px 8px;
  border-radius:3px; background:var(--down-glow); color:var(--down);
}

/* ══ 52 周区间滑标 ══ */
.range-bar {
  position:relative; height:6px; background:var(--bg-3); border-radius:3px; margin-top:8px;
}
.range-fill {
  position:absolute; left:0; top:0; bottom:0; border-radius:3px; opacity:.5;
  background:linear-gradient(90deg,var(--down) 0%,var(--gold) 50%,var(--up) 100%);
}
.range-pin {
  position:absolute; top:-3px; width:12px; height:12px; border-radius:50%;
  background:var(--gold); box-shadow:0 0 0 3px rgba(212,166,71,.2);
  transform:translateX(-6px);
}

/* ══ KPI 条 ══ */
.kpi-strip { display:flex; gap:10px; margin-bottom:1rem; }
.kpi-card {
  flex:1; padding:14px 16px; background:var(--bg-1);
  border:1px solid var(--line); border-radius:8px;
}
.kpi-card.accent-up { border-top:2px solid var(--up); }
.kpi-card.accent-down { border-top:2px solid var(--down); }
.kpi-label {
  font-size:10.5px; letter-spacing:.18em; color:var(--text-3); margin-bottom:8px;
}
.kpi-value {
  font-family:"IBM Plex Mono",monospace; font-size:20px; font-weight:500;
  color:var(--text-0); line-height:1;
}
.kpi-sub {
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; color:var(--text-2); margin-top:6px;
}

/* ══ 通用 panel ══ */
.iq-panel {
  background:var(--bg-1); border:1px solid var(--line); border-radius:8px;
  margin-bottom:1rem; overflow:hidden;
}
.iq-panel-head {
  padding:14px 18px; border-bottom:1px solid var(--line);
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
}
.iq-panel-body { padding:18px 22px; }

.eyebrow {
  font-size:10.5px; letter-spacing:.2em; color:var(--text-3);
}
.badge-ai {
  font-family:"IBM Plex Mono",monospace; font-size:9.5px; padding:2px 6px;
  border:1px solid var(--accent); color:var(--accent);
  border-radius:3px; letter-spacing:.15em; white-space:nowrap;
}
.badge-soft {
  font-family:"IBM Plex Mono",monospace; font-size:9.5px; padding:1px 5px;
  border:1px solid var(--line-2); border-radius:2px;
  color:var(--text-2); letter-spacing:.05em;
}

/* ══ AI 信号灯 ══ */
.signal-buy  { color:var(--up); }
.signal-sell { color:var(--down); }
.signal-hold { color:var(--gold); }
.signal-big {
  font-family:"IBM Plex Mono",monospace; font-size:34px; font-weight:600;
  line-height:1; letter-spacing:.05em; text-align:center;
}
.signal-bar {
  height:4px; background:var(--bg-3); border-radius:2px; margin-top:6px; overflow:hidden;
}
.signal-bar > div { height:100%; border-radius:2px; }

/* ══ 新闻条 ══ */
.news-row {
  padding:12px 18px; border-bottom:1px solid var(--line);
  display:grid; grid-template-columns:56px 1fr; gap:12px; cursor:pointer;
}
.news-row:last-child { border-bottom:none; }
.news-time {
  font-family:"IBM Plex Mono",monospace; font-size:10px; color:var(--text-3);
  letter-spacing:.05em; padding-top:2px;
}
.news-title { font-size:13px; line-height:1.45; color:var(--text-0); margin-bottom:4px; }
.news-body  { font-size:11.5px; line-height:1.5; color:var(--text-2); }

/* ══ 状态栏 ══ */
.iq-statusbar {
  height:28px; border-top:1px solid var(--line); background:var(--bg-1);
  display:flex; align-items:center; padding:0 16px; gap:18px;
  font-family:"IBM Plex Mono",monospace; font-size:10.5px; color:var(--text-3);
  margin:1rem -1rem -2rem;
}

/* ══ Streamlit 元素改色 ══ */
[data-testid="stMetricValue"] {
  font-family:"IBM Plex Mono",monospace !important;
  font-size:1.35rem !important; font-weight:500 !important;
  color:var(--text-0) !important; letter-spacing:.02em !important;
}
[data-testid="stMetricLabel"] {
  font-size:10.5px !important; text-transform:uppercase;
  letter-spacing:.18em; color:var(--text-3) !important;
}
[data-testid="stMetricDelta"] { font-family:"IBM Plex Mono",monospace !important; }

[data-testid="stExpander"] {
  background:var(--bg-1) !important; border:1px solid var(--line) !important;
  border-radius:8px !important;
}
[data-testid="stExpander"] summary { color:var(--text-1) !important; }

div[data-baseweb="tab-list"] {
  background:var(--bg-1); border:1px solid var(--line); border-radius:8px;
  padding:4px; gap:0;
}
div[data-baseweb="tab"] {
  color:var(--text-2) !important; font-size:13px;
  background:transparent; border-radius:4px; padding:6px 14px;
}
div[data-baseweb="tab"][aria-selected="true"] {
  background:var(--bg-3) !important; color:var(--text-0) !important;
}

hr { border-color:var(--line) !important; margin:1rem 0 !important; }

/* 按钮 */
.stButton > button {
  background:var(--bg-2); border:1px solid var(--line); color:var(--text-1) !important;
  border-radius:6px; font-weight:500;
}
.stButton > button:hover { background:var(--bg-3); border-color:var(--line-2); }
.stButton > button[kind="primary"] {
  background:linear-gradient(180deg,rgba(212,166,71,.22),rgba(212,166,71,.08));
  border:1px solid var(--gold); color:var(--gold) !important; font-weight:600;
}

/* Plotly 容器透明 */
.js-plotly-plot, .plot-container { background:transparent !important; }
</style>
""", unsafe_allow_html=True)
