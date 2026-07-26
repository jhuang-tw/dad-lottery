from __future__ import annotations

import datetime as dt
import io
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lotry.backtest import run_backtest  # noqa: E402
from lotry.data_loader import load_game_data  # noqa: E402
from lotry.games import GameDef, get_game  # noqa: E402
from lotry.strategies import STRATEGY_NAMES_ZH  # noqa: E402


STRATEGY_GROUPS: dict[str, list[str]] = {
    "追熱號": ["hot", "cold", "overdue", "markov", "constrained", "weighted"],
    "反著買": [
        "anti_hot",
        "anti_zone",
        "mirror",
        "anti_markov",
        "prime",
        "fibonacci",
        "echo_last",
        "anti_constraint",
        "pi",
        "anti_ensemble",
    ],
    "農民曆": ["lunar_day", "stem_branch", "wuxing", "clash", "lunar_mansion", "almanac_combined"],
    "看新聞挑": ["date_numerology", "major_event", "headline_hash", "disaster_combo", "media_rotate"],
}
BASELINE_STRATEGY = "random"
ALL_POOL_STRATEGIES = [name for names in STRATEGY_GROUPS.values() for name in names] + [BASELINE_STRATEGY]

STRATEGY_REPRESENTATIVES = {
    "追熱號": "hot",
    "反著買": "anti_hot",
    "農民曆": "almanac_combined",
    "看新聞挑": "date_numerology",
}
FAST_STRATEGIES = list(STRATEGY_REPRESENTATIVES.values()) + [BASELINE_STRATEGY]

STRATEGY_GROUP_DESCRIPTIONS = {
    "電腦選號": "完全隨機，不參考過去開獎紀錄。",
    "追熱號": "挑最近比較常開的號碼。",
    "反著買": "避開熱門選法，改選較少人注意的號碼。",
    "農民曆": "用農曆、干支和五行換算號碼。",
    "看新聞挑": "把日期或新聞事件裡的數字拿來選號。",
}

GAME_OPTIONS = {
    "大樂透": "lotto649",
    "威力彩": "superlotto638",
}

TICKET_COST = {
    "lotto649": 50,
    "superlotto638": 100,
}

SCROLL_STATE_KEY = "_lotry_scroll_to_anchor"


def request_scroll(anchor_id: str) -> None:
    st.session_state[SCROLL_STATE_KEY] = anchor_id


def render_scroll_anchor(anchor_id: str) -> None:
    st.markdown(f'<div id="{anchor_id}" class="scroll-anchor"></div>', unsafe_allow_html=True)
    if st.session_state.get(SCROLL_STATE_KEY) != anchor_id:
        return
    st.session_state.pop(SCROLL_STATE_KEY, None)
    components.html(
        f"""
        <script>
        setTimeout(() => {{
          const doc = window.parent.document;
          const target = doc.getElementById({anchor_id!r});
          if (!target) return;
                    const scroller = doc.querySelector('section[data-testid="stMain"]') || doc.scrollingElement || doc.documentElement;
                    const targetRect = target.getBoundingClientRect();
                    const scrollerRect = scroller.getBoundingClientRect ? scroller.getBoundingClientRect() : {{ top: 0 }};
                    const top = scroller.scrollTop + targetRect.top - scrollerRect.top - 16;
                    scroller.scrollTo({{ top, behavior: 'smooth' }});
        }}, 120);
        </script>
        """,
        height=0,
    )

# 獎金估算：頭/貳/參/肆獎取近年平均單人實領，其他固定獎金依官方規則。
# 索引為 (主區命中數, 特別號/第二區命中數)
PRIZE_TABLE = {
    "lotto649": {
        (6, 0): 30_000_000,  # 頭獎：近年平均單人實領約 NT$30M（已假設多人均分）
        (5, 1): 250_000,     # 貳獎：派彩平均單人實領
        (5, 0): 50_000,      # 參獎：派彩平均單人實領
        (4, 1): 14_000,      # 肆獎：按比例，API 實測近 5 年平均單人實領約 NT$14,000
        (4, 0): 2_000,       # 伍獎：自 107 年改固定 NT$2,000（107 年前浮動約 NT$2,000）
        (3, 1): 1_000,       # 陸獎（固定，API 實測 sixthAssign.perPrize=1,000）
        (3, 0): 400,         # 柒獎（固定，API 實測 seventhAssign.perPrize=400；2014 年此獎未設）
        (2, 1): 400,         # 普獎（固定，API 實測 normalAssign.perPrize=400）
    },
    "superlotto638": {
        (6, 1): 200_000_000, # 頭獎：保守估算 NT$200M（API 實測中獎者平均實領 ~NT$955M，但為保守起見用低估值）
        (6, 0): 25_000_000,  # 貳獎：按比例，API 實測近年平均單人實領約 NT$24.5M
        (5, 1): 150_000,     # 參獎（固定）
        (5, 0): 20_000,      # 肆獎（固定）
        (4, 1): 4_000,       # 伍獎（固定）
        (4, 0): 800,         # 陸獎（固定）
        (3, 1): 400,         # 柒獎（固定）
        (3, 0): 200,         # 捌獎（固定）
        (2, 1): 100,         # 玖獎（固定）
        (1, 1): 100,         # 拾獎（固定）
        (0, 1): 100,         # 普獎（固定）
    },
}

@dataclass(frozen=True)
class CustomBacktest:
    periods: int
    total_cost: int
    total_prize: int
    net: int
    avg_hits: float
    max_hits: int
    exact_hits: int
    near_hits: int
    records: pd.DataFrame


def main() -> None:
    st.set_page_config(
        page_title="爸爸的樂透實驗｜十多年資料，看看選號到底有沒有用",
        page_icon="🎲",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_style()

    render_opening()

    st.markdown('<div class="step-label">先選一個遊戲</div>', unsafe_allow_html=True)
    game_label = st.radio(
        "選擇遊戲",
        list(GAME_OPTIONS.keys()),
        horizontal=True,
        label_visibility="collapsed",
    )
    game_code = GAME_OPTIONS[game_label]
    game = get_game(game_code)

    data_path = ROOT / "data" / f"{game_code}.json"
    if not data_path.exists():
        st.error("資料檔還沒準備好，請稍後再試。")
        return

    draws = load_draws_cached(game_code, str(data_path), os.path.getmtime(data_path))
    st.caption(f"目前有 {game.name} 共 {len(draws):,} 期開獎紀錄。")

    render_custom_challenge(game, draws)

    strategy_toggle_key = f"show_strategy_{game.code}"
    with st.expander("這個實驗怎麼算？", expanded=st.session_state.get(strategy_toggle_key, False)):
        render_backtest_explainer()
        render_strategy_battle(game, str(data_path), os.path.getmtime(data_path), len(draws), strategy_toggle_key)

    render_footer_warning()


def inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --lotry-accent: #a7443a;
            --lotry-accent-dark: #7f302a;
            --lotry-gold: #c69b52;
            --lotry-ink: #24262b;
            --lotry-muted: #6e7077;
            --lotry-surface: #ffffff;
            --lotry-canvas: #f6f3ee;
            --lotry-border: #e4ded5;
            --lotry-success: #257052;
            --lotry-danger: #a7443a;
            --radius-sm: 10px;
            --radius-md: 16px;
            --radius-lg: 24px;
            --shadow-sm: 0 8px 24px rgba(47, 39, 31, .06);
            --shadow-md: 0 18px 48px rgba(47, 39, 31, .10);
            --gap-xs: .45rem;
            --gap-sm: .8rem;
            --gap-md: 1.25rem;
            --gap-lg: 1.9rem;
            --gap-xl: 3rem;
        }
        .stApp {
            color: var(--lotry-ink);
            background:
                radial-gradient(circle at 15% 0%, rgba(198, 155, 82, .13), transparent 28rem),
                linear-gradient(180deg, #fbfaf8 0%, var(--lotry-canvas) 100%);
        }
        .block-container {
            max-width: 820px;
            padding: 1.5rem 1.15rem 4rem;
        }
        #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
        header { visibility: hidden; height: 0; }
        html, body, [class*="css"], .stApp, button, input, textarea, select {
            font-family: "lotry-sans", "PingFang TC", "Microsoft JhengHei UI", "Microsoft JhengHei", sans-serif !important;
            font-size: 16px;
            font-synthesis: none;
            letter-spacing: 0;
            text-rendering: optimizeLegibility;
            -webkit-font-smoothing: antialiased;
        }
        .hero {
            position: relative;
            overflow: hidden;
            padding: clamp(1.7rem, 4vw, 2.6rem);
            margin: 0 0 var(--gap-xl);
            color: #fff;
            background:
                linear-gradient(135deg, rgba(127, 48, 42, .96), rgba(49, 39, 37, .97)),
                radial-gradient(circle at 85% 15%, rgba(198, 155, 82, .5), transparent 18rem);
            border: 1px solid rgba(255, 255, 255, .12);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-md);
        }
        .hero::after {
            content: "";
            position: absolute;
            inset: auto -5rem -8rem auto;
            width: 18rem;
            height: 18rem;
            border: 1px solid rgba(255, 255, 255, .12);
            border-radius: 50%;
        }
        .hero-kicker {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            margin-bottom: 1rem;
            color: #f1d8a7;
            font-size: .82rem;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: none;
        }
        .hero h1 {
            max-width: 650px;
            margin: 0 0 .9rem;
            color: #fff;
            font-size: clamp(2.15rem, 7vw, 3.5rem);
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: -.015em;
        }
        .hero p {
            max-width: 650px;
            margin: 0;
            color: rgba(255, 255, 255, .84);
            font-size: 1.04rem;
            font-weight: 400;
            line-height: 1.8;
        }
        .hero strong {
            color: #fff;
            font-weight: 700;
        }
        .hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: .55rem;
            margin-top: 1.4rem;
        }
        .hero-meta span {
            padding: .38rem .65rem;
            color: rgba(255, 255, 255, .9);
            background: rgba(255, 255, 255, .09);
            border: 1px solid rgba(255, 255, 255, .14);
            border-radius: 999px;
            font-size: .83rem;
            font-weight: 600;
        }
        .step-label {
            margin: var(--gap-xl) 0 var(--gap-sm);
            color: var(--lotry-ink);
            font-size: 1.32rem;
            font-weight: 800;
            letter-spacing: -.02em;
        }
        .step-label::before {
            content: "";
            display: inline-block;
            width: .55rem;
            height: .55rem;
            margin-right: .55rem;
            vertical-align: .12rem;
            background: var(--lotry-accent);
            border-radius: 50%;
        }
        .section-card,
        .simple-result-card {
            margin: var(--gap-md) 0 var(--gap-lg);
            padding: 1.35rem 1.4rem;
            background: rgba(255, 255, 255, .92);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
        }
        .section-eyebrow {
            margin-bottom: .4rem;
            color: var(--lotry-accent);
            font-size: .78rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: none;
        }
        .section-title,
        .simple-result-title {
            margin: 0 0 .5rem;
            color: var(--lotry-ink);
            font-size: 1.35rem;
            font-weight: 800;
            line-height: 1.35;
            letter-spacing: -.02em;
        }
        .section-copy,
        .quiet-note {
            margin: 0;
            color: var(--lotry-muted);
            font-size: 1rem;
            font-weight: 400;
            line-height: 1.75;
        }
        div[data-testid="stRadio"] { margin-bottom: .35rem; }
        div[data-testid="stRadio"] label { font-size: 1rem !important; font-weight: 650 !important; }
        [data-testid="stCaptionContainer"] {
            margin: .25rem 0 1rem;
            color: var(--lotry-muted) !important;
            font-size: .9rem !important;
            line-height: 1.65;
        }
        div[data-testid="stExpander"] {
            margin: var(--gap-sm) 0;
            overflow: hidden;
            background: rgba(255, 255, 255, .76);
            border: 1px solid var(--lotry-border) !important;
            border-radius: var(--radius-md) !important;
            box-shadow: 0 3px 14px rgba(47, 39, 31, .035);
        }
        div[data-testid="stExpander"] details summary {
            padding: .95rem 1.05rem !important;
            color: var(--lotry-ink) !important;
            font-size: .98rem;
            font-weight: 700;
        }
        div[data-testid="stExpander"] details[open] summary { border-bottom: 1px solid var(--lotry-border); }
        div[data-testid="stMetric"] {
            padding: .95rem .75rem;
            background: var(--lotry-surface);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
            text-align: center;
        }
        div[data-testid="stMetric"] label {
            color: var(--lotry-muted) !important;
            font-size: .88rem !important;
            font-weight: 650 !important;
        }
        div[data-testid="stMetricValue"] {
            color: var(--lotry-ink) !important;
            font-size: 1.35rem !important;
            font-weight: 800 !important;
            line-height: 1.3 !important;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
            margin: var(--gap-sm) 0 var(--gap-md);
        }
        .stat-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .stat-card {
            padding: 1rem .75rem;
            background: rgba(255, 255, 255, .9);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
            text-align: center;
        }
        .stat-card-label {
            margin-bottom: .3rem;
            color: var(--lotry-muted);
            font-size: .84rem;
            font-weight: 600;
        }
        .stat-card-value {
            color: var(--lotry-accent-dark);
            font-size: 1.2rem;
            font-weight: 800;
            line-height: 1.3;
            word-break: break-word;
        }
        .stat-card-value.neutral { color: var(--lotry-ink); }
        .selected-strip {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
            gap: .65rem;
            min-height: 4.5rem;
            margin: 0 0 var(--gap-sm);
            padding: 1rem;
            background: rgba(255, 255, 255, .82);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
        }
        .selected-label {
            margin-right: .25rem;
            color: var(--lotry-muted);
            font-size: .9rem;
            font-weight: 700;
        }
        .lottery-ball,
        .mini-ball {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.85rem;
            height: 2.85rem;
            color: #fff;
            background: linear-gradient(145deg, #bd5146, #8f342d);
            border: 1px solid rgba(81, 25, 21, .32);
            border-radius: 50%;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, .3), 0 5px 12px rgba(86, 39, 31, .16);
            font-size: 1.08rem;
            font-weight: 800;
        }
        .mini-ball {
            color: var(--lotry-ink);
            background: #fff;
            border-color: #d8b675;
        }
        div.stButton > button,
        div.stDownloadButton > button,
        div[data-testid="stDownloadButton"] > button,
        a.app-link-btn {
            min-height: 3.15rem;
            padding: 0 1.3rem;
            color: var(--lotry-ink);
            background: #fff;
            border: 1px solid #d8d1c7;
            border-radius: var(--radius-sm);
            box-shadow: 0 3px 10px rgba(47, 39, 31, .05);
            font-size: 1rem;
            font-weight: 700;
            transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
        }
        div.stButton > button:hover,
        div.stDownloadButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover,
        a.app-link-btn:hover {
            transform: translateY(-1px);
            border-color: #bdb3a6;
            box-shadow: 0 7px 18px rgba(47, 39, 31, .09);
        }
        div.stButton > button[kind="primary"] {
            color: #fff;
            background: var(--lotry-accent);
            border-color: var(--lotry-accent);
        }
        div.stButton > button[kind="primary"] p { color: #fff !important; }
        div.stButton > button:not([kind="primary"]) p,
        div.stDownloadButton > button p,
        div[data-testid="stDownloadButton"] > button p { color: var(--lotry-ink) !important; }
        a.app-link-btn {
            display: flex !important;
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            text-decoration: none !important;
        }
        a.app-link-btn.line-green { color: #fff !important; background: #168447; border-color: #168447; }
        .ball-row div.stButton { width: 100%; }
        .ball-row div.stButton > button {
            width: 100% !important;
            min-width: 0 !important;
            min-height: 2.45rem !important;
            padding: .15rem .25rem !important;
            background: rgba(255, 255, 255, .82);
            border: 1px solid #ddd6cc;
            border-radius: 9px !important;
            box-shadow: none;
            font-size: .94rem;
        }
        .ball-row div.stButton > button[kind="primary"] {
            color: #fff;
            background: var(--lotry-accent);
            border-color: var(--lotry-accent-dark);
        }
        .ball-row div.stButton > button div[data-testid="stMarkdownContainer"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        .ball-row div.stButton > button p { margin: 0 !important; font-size: .92rem !important; line-height: 1 !important; }
        .loss-box,
        .win-box {
            margin: 0 0 var(--gap-sm);
            padding: 1.6rem 1.35rem;
            background: #fff;
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-sm);
            text-align: center;
        }
        .loss-box { border-top: 4px solid var(--lotry-danger); }
        .win-box { border-top: 4px solid var(--lotry-success); }
        .loss-number,
        .win-number {
            margin-top: .75rem;
            font-size: clamp(2.5rem, 10vw, 4.2rem);
            font-weight: 800;
            line-height: 1.05;
            letter-spacing: -.04em;
        }
        .loss-number { color: var(--lotry-danger); }
        .win-number { color: var(--lotry-success); }
        .tangible-loss,
        .verdict-card,
        .strategy-note {
            margin: 0 0 var(--gap-md);
            padding: 1.05rem 1.1rem;
            color: var(--lotry-ink);
            background: rgba(255, 255, 255, .82);
            border: 1px solid var(--lotry-border);
            border-left: 4px solid var(--lotry-gold);
            border-radius: var(--radius-sm);
            font-size: .96rem;
            font-weight: 500;
            line-height: 1.75;
        }
        .verdict-card b { color: var(--lotry-accent-dark); }
        .verdict-card u {
            text-decoration-color: rgba(167, 68, 58, .45);
            text-decoration-thickness: 2px;
            text-underline-offset: 3px;
        }
        .loss-track {
            height: .55rem;
            margin: 1rem 0 .75rem;
            overflow: hidden;
            background: #eadfd9;
            border-radius: 999px;
        }
        .loss-track::after {
            content: "";
            display: block;
            width: 78%;
            height: 100%;
            background: linear-gradient(90deg, #d99a91, var(--lotry-accent));
            border-radius: inherit;
        }
        .loss-track-labels {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            color: var(--lotry-muted);
            font-size: .86rem;
            font-weight: 600;
        }
        .loading-card {
            margin: 1rem 0;
            padding: 1.3rem 1.1rem;
            background: rgba(255, 255, 255, .88);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            text-align: center;
        }
        .loading-title { margin-bottom: .55rem; color: var(--lotry-ink); font-size: 1.05rem; font-weight: 700; }
        .loading-subtitle { color: var(--lotry-muted); font-size: .9rem; line-height: 1.55; }
        .loading-balls { display: flex; justify-content: center; gap: .45rem; margin: .8rem 0; }
        .loading-ball {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2.35rem;
            height: 2.35rem;
            color: #fff;
            background: var(--lotry-accent);
            border-radius: 50%;
            font-size: .9rem;
            font-weight: 700;
            animation: ball-bounce 900ms ease-in-out infinite;
        }
        .loading-ball:nth-child(2) { animation-delay: 90ms; }
        .loading-ball:nth-child(3) { animation-delay: 180ms; }
        .loading-ball:nth-child(4) { animation-delay: 270ms; }
        .loading-ball:nth-child(5) { animation-delay: 360ms; }
        .loading-ball:nth-child(6) { animation-delay: 450ms; }
        @keyframes ball-bounce { 0%, 100% { transform: translateY(0); } 45% { transform: translateY(-.35rem); } }
        .share-cta {
            margin: var(--gap-xl) 0 var(--gap-md);
            padding: 1.35rem 1.3rem;
            color: #fff;
            background: linear-gradient(135deg, #35302d, #242321);
            border: 1px solid rgba(255, 255, 255, .08);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-sm);
            text-align: left;
        }
        .share-cta-title { margin-bottom: .35rem; color: #ecd5a8; font-size: 1.12rem; font-weight: 700; }
        .share-cta-body { color: rgba(255, 255, 255, .76); font-size: .94rem; font-weight: 400; line-height: 1.7; }
        .warning-line {
            margin: var(--gap-xl) 0 .5rem;
            padding: 1.2rem 1.25rem;
            color: var(--lotry-muted);
            background: transparent;
            border-top: 1px solid var(--lotry-border);
            border-bottom: 1px solid var(--lotry-border);
            font-size: .93rem;
            font-weight: 500;
            line-height: 1.75;
            text-align: center;
        }
        .strategy-list { display: grid; gap: .7rem; margin: var(--gap-md) 0; }
        .strategy-row {
            padding: 1rem 1.05rem;
            background: rgba(255, 255, 255, .86);
            border: 1px solid var(--lotry-border);
            border-radius: var(--radius-md);
        }
        .strategy-row-top { display: flex; align-items: baseline; justify-content: space-between; gap: .8rem; margin-bottom: .45rem; }
        .strategy-name { color: var(--lotry-ink); font-size: 1rem; font-weight: 700; }
        .strategy-loss { color: var(--lotry-accent-dark); font-size: .94rem; font-weight: 700; white-space: nowrap; }
        .strategy-desc { margin: 0 0 .6rem; color: var(--lotry-muted); font-size: .88rem; font-weight: 400; line-height: 1.55; }
        .strategy-bar-bg { height: .45rem; overflow: hidden; background: #eadfd9; border-radius: 999px; }
        .strategy-bar-fill { height: 100%; background: linear-gradient(90deg, #d99a91, var(--lotry-accent)); border-radius: inherit; }
        @media (max-width: 640px) {
            .block-container { padding: .85rem .75rem 3rem; }
            .hero { padding: 1.5rem 1.2rem 1.65rem; margin-bottom: var(--gap-lg); border-radius: 20px; }
            .hero h1 { font-size: 2.15rem; }
            .hero p { font-size: .98rem; }
            .hero-meta { gap: .4rem; }
            .step-label { margin-top: var(--gap-lg); font-size: 1.18rem; }
            .section-card, .simple-result-card { padding: 1.15rem 1rem; }
            .stat-grid.three { grid-template-columns: 1fr; }
            .stat-card { display: flex; align-items: center; justify-content: space-between; gap: .75rem; text-align: left; }
            .stat-card-label { margin: 0; }
            .lottery-ball, .mini-ball { width: 2.55rem; height: 2.55rem; font-size: 1rem; }
            .selected-strip { gap: .45rem; padding: .85rem .7rem; }
            .ball-row div.stButton > button { min-height: 2.3rem !important; }
            .share-cta { padding: 1.2rem 1.05rem; }
        }
        @media (max-width: 380px) {
            .hero h1 { font-size: 1.9rem; }
            .lottery-ball, .mini-ball { width: 2.3rem; height: 2.3rem; font-size: .9rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_opening() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">一個寫給爸爸的資料實驗</div>
          <h1>爸爸的樂透實驗</h1>
          <p>我爸算了一輩子的樂透。後來我把他相信的冷熱號、農民曆和新聞明牌寫成程式，一期一期對過十多年的開獎紀錄。<br/><strong>最後沒有找到更準的選法，只看到所有方法長期都差不多。</strong></p>
          <div class="hero-meta"><span>27 種選號方法</span><span>大樂透、威力彩</span><span>逐期回測</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner="載入歷史開獎資料…")
def load_draws_cached(game_code: str, data_path: str, data_mtime: float) -> list[dict]:
    del data_mtime
    game = get_game(game_code)
    return load_game_data(game, data_path)


def render_custom_challenge(game: GameDef, draws: list[dict]) -> None:
    quick_loading_slot = st.empty()
    if st.button("讓電腦隨機選一組", type="primary", width="stretch"):
        numbers = sorted(random_sample(game))
        set_selected_numbers(game, numbers)
        st.session_state[result_key(game)] = (numbers, run_custom_backtest_with_loading(numbers, draws, game, quick_loading_slot))
        request_scroll("lotry-result-anchor")

    with st.expander("我想自己選號"):
        st.caption(f"從 1 到 {game.main_pool} 選 {game.main_pick} 個號碼，看看如果每期都買，過去會是什麼結果。")
        selected = render_ball_picker(game)
        is_complete = len(selected) == game.main_pick
        action_cols = st.columns(2)
        with action_cols[0]:
            challenge = st.button(
                "看看過去的結果",
                type="primary" if is_complete else "secondary",
                disabled=not is_complete,
                width="stretch",
            )
        with action_cols[1]:
            if st.button("清空重選", disabled=not bool(selected), width="stretch"):
                set_selected_numbers(game, [])
                st.session_state.pop(result_key(game), None)
                st.rerun()
        result_loading_slot = st.empty()
        if not is_complete:
            st.info(f"還差 {game.main_pick - len(selected)} 個號碼。")
        elif challenge:
            numbers = sorted(selected)
            st.session_state[result_key(game)] = (numbers, run_custom_backtest_with_loading(numbers, draws, game, result_loading_slot))
            request_scroll("lotry-result-anchor")

    saved_result = st.session_state.get(result_key(game))
    if saved_result:
        render_scroll_anchor("lotry-result-anchor")
        render_custom_result(saved_result[1], saved_result[0], game)
        if game.code == "superlotto638":
            render_bonus_wheel_section(game, draws)


def render_ball_picker(game: GameDef) -> list[int]:
    key = selected_key(game)
    if key not in st.session_state:
        st.session_state[key] = []
    selected = list(st.session_state[key])
    render_selected_balls(selected, game)

    columns_per_row = 7
    st.markdown('<div class="ball-row">', unsafe_allow_html=True)
    for start in range(1, game.main_pool + 1, columns_per_row):
        cols = st.columns(columns_per_row, gap="small")
        for offset, col in enumerate(cols):
            number = start + offset
            if number > game.main_pool:
                continue
            is_selected = number in selected
            with col:
                clicked = st.button(
                    f"{number:02d}",
                    key=f"ball_{game.code}_{number}",
                    type="primary" if is_selected else "secondary",
                    width="stretch",
                )
            if clicked:
                selected = toggle_number(selected, number, game.main_pick)
                st.session_state[key] = selected
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    return selected


def render_selected_balls(selected: list[int], game: GameDef) -> None:
    if selected:
        balls = "".join(f'<span class="lottery-ball">{number:02d}</span>' for number in sorted(selected))
    else:
        balls = "<span class='quiet-note'>尚未選號</span>"
    st.markdown(
        f"""
        <div class="selected-strip">
          <span class="selected-label">已選 {len(selected)} / {game.main_pick}</span>
          {balls}
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_key(game: GameDef) -> str:
    return f"selected_balls_{game.code}"


def result_key(game: GameDef) -> str:
    return f"custom_result_{game.code}"


def bonus_wheel_key(game: GameDef) -> str:
    return f"bonus_wheel_result_{game.code}"


def set_selected_numbers(game: GameDef, numbers: list[int]) -> None:
    st.session_state[selected_key(game)] = sorted(numbers)[: game.main_pick]


def toggle_number(selected: list[int], number: int, max_count: int) -> list[int]:
    if number in selected:
        return [item for item in selected if item != number]
    if len(selected) >= max_count:
        return selected
    return selected + [number]


def random_sample(game: GameDef) -> list[int]:
    rng = random.Random()
    return rng.sample(range(1, game.main_pool + 1), game.main_pick)


def run_custom_backtest_with_loading(
    numbers: list[int],
    draws: list[dict],
    game: GameDef,
    loading_slot: st.delta_generator.DeltaGenerator,
) -> CustomBacktest:
    with loading_slot.container():
        render_loading_animation(numbers)
    result = run_custom_backtest(numbers, draws, game)
    time.sleep(0.85)
    loading_slot.empty()
    return result


def render_loading_animation(numbers: list[int]) -> None:
    balls = "".join(f'<span class="loading-ball">{number:02d}</span>' for number in numbers)
    st.markdown(
        f"""
        <div class="loading-card">
          <div class="loading-title">正在對照過去的開獎紀錄</div>
          <div class="loading-balls">{balls}</div>
          <div class="loading-subtitle">把這組號碼放進每一期，算出中獎金額和總花費。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_custom_backtest(numbers: list[int], draws: list[dict], game: GameDef) -> CustomBacktest:
    rows = []
    cumulative_net = 0
    total_prize = 0
    ticket_cost = TICKET_COST[game.code]
    pick_set = set(numbers)
    for index, draw in enumerate(draws, start=1):
        actual = set(draw["numbers"])
        bonus_set = set(draw.get("bonus", []))
        hits = len(pick_set & actual)
        bonus_hits = len(pick_set & bonus_set)
        prize = prize_for_hits(game, hits, bonus_hits)
        total_prize += prize
        cumulative_net += prize - ticket_cost
        rows.append(
            {
                "期數序": index,
                "期號": draw["term"],
                "日期": draw.get("date", ""),
                "命中數": hits,
                "中特別號": bonus_hits,
                "估算獎金": prize,
                "累計損益": cumulative_net,
            }
        )
    records = pd.DataFrame(rows)
    periods = len(draws)
    total_cost = periods * ticket_cost
    net = total_prize - total_cost
    avg_hits = float(records["命中數"].mean()) if periods else 0.0
    max_hits = int(records["命中數"].max()) if periods else 0
    exact_hits = int((records["命中數"] == game.main_pick).sum()) if periods else 0
    near_hits = int((records["命中數"] >= max(3, game.main_pick - 1)).sum()) if periods else 0
    return CustomBacktest(
        periods,
        total_cost,
        total_prize,
        net,
        avg_hits,
        max_hits,
        exact_hits,
        near_hits,
        records,
    )


def render_custom_result(result: CustomBacktest, numbers: list[int], game: GameDef) -> None:
    st.markdown('<div class="step-label">這組號碼，過去表現如何？</div>', unsafe_allow_html=True)
    result_balls = "".join(f'<span class="lottery-ball">{number:02d}</span>' for number in numbers)
    st.markdown(
        f"""
        <div class="selected-strip">
          <span class="selected-label">你選的號碼</span>
          {result_balls}
        </div>
        """,
        unsafe_allow_html=True,
    )

    is_profit = result.net > 0
    abs_amount = abs(result.net)

    if is_profit:
        st.markdown(
            f"""
            <div class="win-box">
              <div class="quiet-note">假設過去 {result.periods:,} 期每期都買一注，最後會是：</div>
              <div class="win-number">+{format_money(result.net)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="loss-box">
              <div class="quiet-note">假設過去 {result.periods:,} 期每期都買一注，最後會是：</div>
              <div class="loss-number">{format_money(result.net)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if abs_amount > 0:
        balance_note = (
            f"獎金比總成本多 <b>{format_money(abs_amount)}</b>。"
            if is_profit
            else f"總成本扣掉估算獎金後，差了 <b>{format_money(abs_amount)}</b>。"
        )
        st.markdown(
            f'<div class="tangible-loss">{balance_note}這只是這段歷史紀錄裡的結果，不代表下一期。</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="stat-grid three">
          <div class="stat-card"><div class="stat-card-label">買彩券共花</div><div class="stat-card-value">{format_money(result.total_cost)}</div></div>
          <div class="stat-card"><div class="stat-card-label">估算獎金</div><div class="stat-card-value">{format_money(result.total_prize)}</div></div>
          <div class="stat-card"><div class="stat-card-label">頭獎次數</div><div class="stat-card-value neutral">{result.exact_hits} 次</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    odds = jackpot_odds(game)
    odds_text = f"中頭獎機率約 {jackpot_pct(odds)}" if odds else ""
    jackpot_note = jackpot_assumption_text(game)
    st.caption(f"獎金以近年平均與固定獎金估算。{jackpot_note} 春節加碼與大紅包沒有算進去。{odds_text}")

    expected_avg = game.main_pick * game.main_pick / game.main_pool
    diff = result.avg_hits - expected_avg
    direction = "和隨機差不多" if abs(diff) < 0.05 else ("比隨機高一點" if diff > 0 else "比隨機低一點")

    if is_profit:
        if result.exact_hits >= 1:
            luck_line = f"這段期間剛好碰到 {result.exact_hits} 次頭獎，結果才會轉正。"
        elif result.near_hits >= 1:
            luck_line = f"這段期間剛好碰到 {result.near_hits} 次較高獎項，結果才會轉正。"
        else:
            luck_line = "這段期間的小獎剛好累積超過總成本。"
        st.markdown(
            f"""
            <div class="verdict-card">
              <b>這次算出賺錢，不代表這組號碼比較會中。</b><br/>
              {luck_line}<br/>
              頭獎機率約為 {jackpot_pct(odds)}，而且每一期都會重新開始。換一組號碼或換一段年份，結果很可能完全不同。
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="verdict-card">
              這組號碼平均每期對中 <b>{result.avg_hits:.3f}</b> 個主區號碼，隨機選號理論上約為 <b>{expected_avg:.3f}</b>。<br/>
              兩者{direction}。<br/><u>從這段歷史紀錄，看不出它有能重複出現的優勢。</u>
            </div>
            """,
            unsafe_allow_html=True,
        )

    curve = go.Figure()
    chart_dates = pd.to_datetime(result.records["日期"], errors="coerce")
    chart_date_labels = [format_chinese_date(value) for value in chart_dates]
    chart_money_labels = [format_plain_money(int(value)) for value in result.records["累計損益"]]
    line_color = "#15803d" if is_profit else "#dc2626"
    curve.add_trace(
        go.Scatter(
            x=chart_dates,
            y=result.records["累計損益"],
            customdata=list(zip(chart_date_labels, chart_money_labels, strict=True)),
            mode="lines",
            line=dict(color=line_color, width=3),
            name="所選號碼累計損益",
            hovertemplate="日期：%{customdata[0]}<br>累計損益：%{customdata[1]}<extra></extra>",
        )
    )
    chart_min = int(result.records["累計損益"].min())
    chart_max = int(result.records["累計損益"].max())
    tick_values, tick_labels = build_money_ticks(min(chart_min, 0), max(chart_max, 0))
    date_tick_values, date_tick_labels = build_date_ticks(chart_dates)
    curve.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    curve.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=None,
        yaxis_title="累計損益（NT$）",
        xaxis=dict(tickvals=date_tick_values, ticktext=date_tick_labels),
        yaxis=dict(tickvals=tick_values, ticktext=tick_labels),
    )
    if is_profit:
        st.markdown(
            f"""
            <div class="simple-result-card">
              <div class="simple-result-title">為什麼這次會賺？</div>
              <div class="quiet-note">主要是少數幾次較高獎項把結果拉了上來。平均每期對中 <b>{result.avg_hits:.3f}</b> 個主區號碼，仍接近隨機選號的 <b>{expected_avg:.3f}</b>。</div>
              <div class="loss-track-labels" style="margin-top: 1rem;">
                <span>開始：NT$ 0</span><span>現在：+{format_money(result.net)}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="simple-result-card">
              <div class="simple-result-title">這組號碼沒有特別準</div>
              <div class="quiet-note">固定買同一組號碼，過去這段期間的獎金沒有補回總成本。</div>
              <div class="loss-track"></div>
              <div class="loss-track-labels"><span>開始：NT$ 0</span><span>現在：{format_money(result.net)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="share-cta">
          <div class="share-cta-title">把結果存成圖片</div>
          <div class="share-cta-body">
            想留著或傳給家人，可以產生一張簡單的小卡。上面會清楚標示這是過去的結果，不是在預測下一期。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    card_key = f"card_png_{game.code}"
    card_signature = (
        _SHARE_CARD_VERSION,
        tuple(numbers),
        result.periods,
        result.net,
        result.total_cost,
        result.total_prize,
        result.exact_hits,
    )
    if st.button("產生結果小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):
        try:
            card_png = build_share_card(numbers, result, game)
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.session_state[card_key] = (card_signature, card_png)
            request_scroll(f"lotry-card-anchor-{game.code}")
    saved_card = st.session_state.get(card_key)
    if saved_card and saved_card[0] == card_signature:
        card_png = saved_card[1]
        render_scroll_anchor(f"lotry-card-anchor-{game.code}")
        st.image(card_png, width="stretch")
        dl_cols = st.columns(2)
        with dl_cols[0]:
            st.download_button(
                label="下載圖片",
                data=card_png,
                file_name=f"lotry_{game.code}_{'-'.join(f'{n:02d}' for n in numbers)}.png",
                mime="image/png",
                width="stretch",
                key=f"dl_card_{game.code}",
            )
        with dl_cols[1]:
            st.markdown(
                '<a class="app-link-btn line-green" '
                'href="https://social-plugins.line.me/lineit/share?url=https%3A%2F%2Flotry.tw" '
                'target="_blank" rel="noopener noreferrer">分享到 LINE</a>',
                unsafe_allow_html=True,
            )
        st.caption("手機可長按圖片儲存或分享。")

    with st.expander("看看錢怎麼一路變化"):
        st.plotly_chart(curve, width="stretch", config={"displayModeBar": False})
        st.caption("獎金包含特別號／第二區；浮動獎項用近年平均單人實領估算。春節加碼與大紅包沒有算進去，因此這張圖適合看趨勢，不適合拿來核對每一期派彩。")


def render_bonus_wheel_section(game: GameDef, draws: list[dict]) -> None:
    if game.code != "superlotto638":
        return

    st.markdown(
        """
        <div class="section-card">
          <div class="section-eyebrow">威力彩多算一種買法</div>
          <div class="section-title">第二區 1 到 8 全包，真的比較划算嗎？</div>
          <p class="section-copy">
            第二區全包的確比較常中小獎，但每期也要一次買八注。這裡沿用同一組主區號碼，看看過去的獎金能不能補回多出的成本。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.session_state.get(selected_key(game)) or []
    if len(selected) != game.main_pick:
        st.caption("請先在上方選滿 6 個主區號碼。")
        return

    if st.button("算算看第二區全包", width="stretch"):
        st.session_state[bonus_wheel_key(game)] = (
            sorted(selected),
            run_bonus_wheel_backtest(sorted(selected), draws, game),
        )
        request_scroll("lotry-bonus-result-anchor")

    saved = st.session_state.get(bonus_wheel_key(game))
    if saved and saved[0] == sorted(selected):
        render_scroll_anchor("lotry-bonus-result-anchor")
        render_bonus_wheel_result(saved[1], saved[0], game)


def run_bonus_wheel_backtest(numbers: list[int], draws: list[dict], game: GameDef) -> CustomBacktest:
    rows = []
    cumulative_net = 0
    total_prize = 0
    bonus_pool = game.bonus_pool
    ticket_cost = TICKET_COST[game.code] * bonus_pool
    pick_set = set(numbers)
    for index, draw in enumerate(draws, start=1):
        actual = set(draw["numbers"])
        hits = len(pick_set & actual)
        prize_winning_ticket = prize_for_hits(game, hits, 1)
        prize_other_tickets = prize_for_hits(game, hits, 0) * (bonus_pool - 1)
        prize = prize_winning_ticket + prize_other_tickets
        total_prize += prize
        cumulative_net += prize - ticket_cost
        rows.append(
            {
                "期數序": index,
                "期號": draw["term"],
                "日期": draw.get("date", ""),
                "命中數": hits,
                "中第二區": 1,
                "估算獎金": prize,
                "累計損益": cumulative_net,
            }
        )
    records = pd.DataFrame(rows)
    periods = len(draws)
    total_cost = periods * ticket_cost
    net = total_prize - total_cost
    avg_hits = float(records["命中數"].mean()) if periods else 0.0
    max_hits = int(records["命中數"].max()) if periods else 0
    exact_hits = int((records["命中數"] == game.main_pick).sum()) if periods else 0
    near_hits = int((records["命中數"] >= max(3, game.main_pick - 1)).sum()) if periods else 0
    return CustomBacktest(
        periods,
        total_cost,
        total_prize,
        net,
        avg_hits,
        max_hits,
        exact_hits,
        near_hits,
        records,
    )


def render_bonus_wheel_result(result: CustomBacktest, numbers: list[int], game: GameDef) -> None:
    cost_per_period = TICKET_COST[game.code] * game.bonus_pool
    result_balls = "".join(f'<span class="lottery-ball">{number:02d}</span>' for number in numbers)
    st.markdown(
        f"""
        <div class="selected-strip">
          <span class="selected-label">主區號碼</span>
          {result_balls}
          <span class="selected-label" style="margin-left:12px;">第二區 1–8 全包</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    is_profit = result.net > 0
    if is_profit:
        st.markdown(
            f"""
            <div class="win-box">
              <div class="quiet-note">
                這 {result.periods:,} 期下來，<br/>
                每期投入 {format_money(cost_per_period)} 購買八注，<br/>
                歷史回測的累計損益為
              </div>
              <div class="win-number">+{format_money(result.net)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="loss-box">
              <div class="quiet-note">
                這 {result.periods:,} 期下來，<br/>
                每期投入 {format_money(cost_per_period)} 購買八注，<br/>
                歷史回測的累計損益為
              </div>
              <div class="loss-number">{format_money(result.net)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class="stat-grid three">
          <div class="stat-card"><div class="stat-card-label">買彩券共花</div><div class="stat-card-value">{format_money(result.total_cost)}</div></div>
          <div class="stat-card"><div class="stat-card-label">估算獎金</div><div class="stat-card-value">{format_money(result.total_prize)}</div></div>
          <div class="stat-card"><div class="stat-card-label">頭獎次數</div><div class="stat-card-value neutral">{result.exact_hits} 次</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"獎金估算：{jackpot_assumption_text(game)} 春節加碼與大紅包未納入。")
    if is_profit:
        st.markdown(
            f"""
            <div class="verdict-card">
              <b>這次會賺，主要是剛好碰到少數高額獎項。</b><br/>
              第二區全包每期都多買七注；沒有較高獎項時，多出的成本通常會比小獎還多。
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="verdict-card">
              <b>比較常中，不代表最後比較划算。</b><br/>
              全包能保證其中一注對中第二區，但另外七注也都要付錢；在這段歷史紀錄裡，獎金仍沒有補回成本。
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="share-cta">
          <div class="share-cta-title">把全包結果存成圖片</div>
          <div class="share-cta-body">
            小卡會列出主區號碼、八倍成本和最後損益，方便看清楚「比較常中」和「有沒有賺」是兩件事。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bonus_card_key = f"bonus_card_png_{game.code}"
    bonus_card_signature = (
        _SHARE_CARD_VERSION,
        tuple(numbers),
        result.periods,
        result.net,
        result.total_cost,
        result.total_prize,
        result.exact_hits,
    )
    if st.button("產生全包結果小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):
        try:
            bonus_png = build_bonus_card(numbers, result, game)
        except RuntimeError as exc:
            st.error(str(exc))
        else:
            st.session_state[bonus_card_key] = (
                bonus_card_signature,
                bonus_png,
            )
            request_scroll(f"lotry-bonus-card-anchor-{game.code}")
    saved_bonus_card = st.session_state.get(bonus_card_key)
    if saved_bonus_card and saved_bonus_card[0] == bonus_card_signature:
        bonus_png = saved_bonus_card[1]
        render_scroll_anchor(f"lotry-bonus-card-anchor-{game.code}")
        st.image(bonus_png, width="stretch")
        dl_cols = st.columns(2)
        with dl_cols[0]:
            st.download_button(
                label="下載圖片",
                data=bonus_png,
                file_name=f"lotry_bonus_{game.code}_{'-'.join(f'{n:02d}' for n in numbers)}.png",
                mime="image/png",
                width="stretch",
                key=f"dl_bonus_card_{game.code}",
            )
        with dl_cols[1]:
            st.markdown(
                '<a class="app-link-btn line-green" '
                'href="https://social-plugins.line.me/lineit/share?url=https%3A%2F%2Flotry.tw" '
                'target="_blank" rel="noopener noreferrer">分享到 LINE</a>',
                unsafe_allow_html=True,
            )
        st.caption("手機可長按圖片儲存或分享。")


def prize_for_hits(game: GameDef, main_hits: int, bonus_hits: int = 0) -> int:
    table = PRIZE_TABLE.get(game.code, {})
    return table.get((main_hits, bonus_hits), 0)


def jackpot_odds(game: GameDef) -> int:
    from math import comb

    if game.main_pool <= 0 or game.main_pick <= 0:
        return 0
    main_combos = comb(game.main_pool, game.main_pick)
    if game.code == "lotto649":
        return main_combos
    if game.code == "superlotto638":
        return main_combos * max(1, game.bonus_pool)
    return main_combos


def jackpot_assumption_text(game: GameDef) -> str:
    table = PRIZE_TABLE.get(game.code, {})
    if game.code == "lotto649":
        amount = table.get((6, 0), 0)
        return (
            f"頭獎金額採近 5 年大樂透「平均單人實領」估算（約 {_md_money(amount)}），"
            "已假設多人均分。實際派彩有時上看 NT\\$ 1 億，也可能 1 人獨得，浮動很大。"
        )
    if game.code == "superlotto638":
        amount = table.get((6, 1), 0)
        return (
            f"頭獎金額採近 5 年威力彩「平均單人實領」估算（約 {_md_money(amount)}），"
            "已假設多人均分。實際派彩極端時可破 NT\\$ 20 億，也可能持續槓龜累積。"
        )
    return "頭獎金額為簡化估算。"


def _md_money(value: int) -> str:
    return format_money(value).replace("$", "\\$")

_BUNDLED_FONT_PATH = ROOT / "static" / "fonts" / "NotoSansTC-VF.ttf"
_FONT_CANDIDATES = (
    _BUNDLED_FONT_PATH,
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansTC-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("C:/Windows/Fonts/msjh.ttc"),
    Path("C:/Windows/Fonts/msjhbd.ttc"),
)
_SHARE_CARD_WIDTH = 1080
_SHARE_CARD_HEIGHT = 1200
_SHARE_CARD_VERSION = 6


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
        try:
            font.set_variation_by_axes([700.0 if bold else 400.0])
        except (AttributeError, OSError, TypeError, ValueError):
            pass
        return font
    raise RuntimeError(
        "分享小卡需要可縮放的中文字型。請確認 static/fonts/NotoSansTC-VF.ttf 已經一起提交並部署，"
        "否則雲端會產生無法閱讀的小方塊文字。"
    )


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred_size: int,
    *,
    min_size: int = 28,
    bold: bool = False,
) -> ImageFont.FreeTypeFont:
    for size in range(preferred_size, min_size - 1, -2):
        font = _load_font(size, bold=bold)
        text_width, _, _ = _text_size(draw, text, font)
        if text_width <= max_width:
            return font
    return _load_font(min_size, bold=bold)


def _draw_shadowed_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    *,
    shadow_fill: tuple[int, int, int, int] = (0, 0, 0, 70),
    shadow_offset: tuple[int, int] = (3, 3),
) -> None:
    x, y = xy
    draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow_fill)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_number_ball(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    number: int,
    size: int,
    font: ImageFont.FreeTypeFont,
) -> None:
    draw.ellipse([(x + 6, y + 8), (x + size + 6, y + size + 8)], fill=(0, 0, 0, 30))
    draw.ellipse(
        [(x, y), (x + size, y + size)],
        fill=(220, 38, 38, 255),
        outline=(153, 27, 27, 255),
        width=3,
    )
    text = f"{number:02d}"
    text_width, text_height, text_top = _text_size(draw, text, font)
    text_x = x + (size - text_width) // 2
    text_y = y + (size - text_height) // 2 - text_top
    _draw_shadowed_text(
        draw,
        (text_x, text_y),
        text,
        font,
        (255, 255, 255, 255),
        shadow_fill=(120, 0, 0, 180),
        shadow_offset=(2, 2),
    )


def _draw_money_box(
    draw: ImageDraw.ImageDraw,
    *,
    cx: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    box_fill: tuple[int, int, int, int],
    text_fill: tuple[int, int, int, int],
) -> None:
    text_width, text_height, text_top = _text_size(draw, text, font)
    box_pad_x = 60
    box_height = max(128, text_height + 56)
    box_top = y
    box_bottom = box_top + box_height
    box_left = cx - text_width // 2 - box_pad_x
    box_right = cx + text_width // 2 + box_pad_x
    text_x = cx - text_width // 2
    text_y = box_top + (box_height - text_height) // 2 - text_top
    draw.rounded_rectangle(
        [(box_left, box_top), (box_right, box_bottom)],
        radius=24,
        fill=box_fill,
    )
    draw.text((text_x, text_y), text, font=font, fill=text_fill)


def build_share_card(numbers: list[int], result: "CustomBacktest", game: GameDef) -> bytes:
    """產生 1080×1200 分享小卡。"""
    width, height = _SHARE_CARD_WIDTH, _SHARE_CARD_HEIGHT

    bg_color = (228, 224, 216, 255)
    image = Image.new("RGBA", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    cx = width // 2
    cm = 22
    card_r = 36
    header_h = cm + 246
    footer_top = 1040
    gold = (248, 199, 74, 255)

    def _dc(y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
        tw, _, _ = _text_size(draw, text, font)
        draw.text((cx - tw // 2, y), text, font=font, fill=fill)

    draw.rounded_rectangle(
        [(cm + 5, cm + 8), (width - cm + 5, height - cm + 8)],
        radius=card_r,
        fill=(60, 48, 36, 65),
    )

    draw.rounded_rectangle(
        [(cm, cm), (width - cm, height - cm)],
        radius=card_r,
        fill=(255, 252, 245, 255),
    )

    is_profit_card = result.net > 0
    header_color = (21, 128, 61, 255) if is_profit_card else (153, 27, 27, 255)
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, header_h)],
        radius=card_r,
        fill=header_color,
    )
    draw.rectangle(
        [(cm, header_h - card_r), (width - cm, header_h)],
        fill=header_color,
    )

    draw.rectangle([(cm, header_h), (width - cm, header_h + 5)], fill=gold)

    notch_r = 20
    notch_y = header_h + 2
    draw.ellipse(
        [(cm - notch_r, notch_y - notch_r), (cm + notch_r, notch_y + notch_r)],
        fill=bg_color,
    )
    draw.ellipse(
        [(width - cm - notch_r, notch_y - notch_r), (width - cm + notch_r, notch_y + notch_r)],
        fill=bg_color,
    )

    footer_color = (40, 35, 30, 255)
    draw.rectangle(
        [(cm, footer_top), (width - cm, footer_top + card_r)],
        fill=footer_color,
    )
    draw.rounded_rectangle(
        [(cm, footer_top), (width - cm, height - cm)],
        radius=card_r,
        fill=footer_color,
    )

    title_font = _load_font(78, bold=True)
    sub_font = _load_font(34)
    tag_font = _load_font(28)
    title_text = "爸爸的樂透實驗"
    tw, _, _ = _text_size(draw, title_text, title_font)
    title_shadow = (0, 50, 20, 150) if is_profit_card else (80, 0, 0, 150)
    _draw_shadowed_text(
        draw, (cx - tw // 2, cm + 30), title_text, title_font,
        (255, 255, 255, 255), shadow_fill=title_shadow, shadow_offset=(4, 4),
    )
    _dc(cm + 140, f"{game.name} · 對照過去 {result.periods:,} 期", sub_font, gold)
    tagline = "這次會賺，主要是少數幾次大獎" if is_profit_card else "這組號碼如果每期都買"
    tagline_color = (220, 255, 230, 255) if is_profit_card else (255, 220, 200, 255)
    _dc(cm + 192, tagline, tag_font, tagline_color)

    ball_size = 100
    gap = 16
    total_w = len(numbers) * ball_size + (len(numbers) - 1) * gap
    start_x = (width - total_w) // 2
    ball_y = 292
    ball_font = _load_font(50, bold=True)
    for i, num in enumerate(numbers):
        bx = start_x + i * (ball_size + gap)
        _draw_number_ball(draw, bx, ball_y, num, ball_size, ball_font)

    narrative_font = _load_font(36)
    if is_profit_card:
        _dc(410, f"拿這組號碼對過去 {result.periods:,} 期", narrative_font, (80, 75, 70, 255))
        _dc(454, "少數幾次較高獎項把結果拉到正數", narrative_font, (80, 75, 70, 255))
    else:
        _dc(410, f"拿這組號碼對過去 {result.periods:,} 期", narrative_font, (80, 75, 70, 255))
        _dc(454, "假設每一期都固定買一注", narrative_font, (80, 75, 70, 255))

    money_text = ("+" if is_profit_card else "") + format_money(result.net)
    money_font = _fit_font(draw, money_text, width - 240, 120, min_size=72, bold=True)
    box_fill = (220, 252, 231, 255) if is_profit_card else (255, 235, 235, 255)
    text_fill = (21, 128, 61, 255) if is_profit_card else (185, 28, 28, 255)
    _draw_money_box(
        draw,
        cx=cx,
        y=496,
        text=money_text,
        font=money_font,
        box_fill=box_fill,
        text_fill=text_fill,
    )

    magnitude_font = _load_font(32, bold=True)
    _dc(718, f"損益絕對值：{format_money(abs(result.net))}", magnitude_font, (120, 90, 55, 255))
    _dc(766, "這是過去的結果，不是在預測下一期", _load_font(28), (120, 115, 110, 255))

    stat_label_y = 815
    stat_value_y = 863
    stat_label_font = _load_font(30)
    stats = [
        ("花了本金", format_money(result.total_cost)),
        ("中獎領回", format_money(result.total_prize)),
        ("頭獎次數", f"{result.exact_hits} 次"),
    ]
    col_count = 3
    col_w = (width - 80) // col_count
    base_x = 40
    for i, (label, value) in enumerate(stats):
        col_cx = base_x + i * col_w + col_w // 2
        v_font = _fit_font(draw, value, col_w - 24, 38, min_size=26, bold=True)
        lw, _, _ = _text_size(draw, label, stat_label_font)
        vw, _, _ = _text_size(draw, value, v_font)
        draw.text((col_cx - lw // 2, stat_label_y), label, font=stat_label_font, fill=(120, 115, 110, 255))
        draw.text((col_cx - vw // 2, stat_value_y), value, font=v_font, fill=(30, 30, 30, 255))
    for i in range(1, col_count):
        sep_x = base_x + i * col_w
        draw.line([(sep_x, stat_label_y - 4), (sep_x, stat_value_y + 50)],
                  fill=(225, 215, 205, 255), width=2)

    draw.line([(80, 940), (width - 80, 940)], fill=(225, 215, 205, 255), width=2)

    if is_profit_card:
        cta_text = f"頭獎機率約 {jackpot_pct(jackpot_odds(game))}；每一期仍是獨立事件。"
    else:
        cta_text = "這段歷史裡，看不出它比隨機選號更有優勢。"
    cta_font = _fit_font(draw, cta_text, width - 120, 38, min_size=28, bold=True)
    cta_color = (21, 128, 61, 255) if is_profit_card else (153, 27, 27, 255)
    _dc(964, cta_text, cta_font, cta_color)

    brand_font = _load_font(30, bold=True)
    foot_font = _load_font(26)
    _dc(footer_top + 30, "爸爸的樂透實驗 · 歷史資料回測", brand_font, gold)
    _dc(footer_top + 80, "這張圖只整理過去資料，不是投注建議", foot_font, (200, 195, 185, 255))

    image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_bonus_card(numbers: list[int], result: "CustomBacktest", game: GameDef) -> bytes:
    """產生包牌（第二區全包）版本分享小卡。"""
    width, height = _SHARE_CARD_WIDTH, _SHARE_CARD_HEIGHT

    bg_color = (228, 224, 216, 255)
    image = Image.new("RGBA", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    cx = width // 2
    cm = 22
    card_r = 36
    header_h = cm + 246
    footer_top = 1020
    gold = (248, 199, 74, 255)

    def _dc(y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
        tw, _, _ = _text_size(draw, text, font)
        draw.text((cx - tw // 2, y), text, font=font, fill=fill)

    draw.rounded_rectangle(
        [(cm + 5, cm + 8), (width - cm + 5, height - cm + 8)],
        radius=card_r,
        fill=(60, 48, 36, 65),
    )

    draw.rounded_rectangle(
        [(cm, cm), (width - cm, height - cm)],
        radius=card_r,
        fill=(255, 252, 245, 255),
    )

    is_profit_card = result.net > 0
    header_color = (21, 128, 61, 255) if is_profit_card else (30, 58, 138, 255)
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, header_h)],
        radius=card_r,
        fill=header_color,
    )
    draw.rectangle(
        [(cm, header_h - card_r), (width - cm, header_h)],
        fill=header_color,
    )

    draw.rectangle([(cm, header_h), (width - cm, header_h + 5)], fill=gold)

    notch_r = 20
    notch_y = header_h + 2
    draw.ellipse(
        [(cm - notch_r, notch_y - notch_r), (cm + notch_r, notch_y + notch_r)],
        fill=bg_color,
    )
    draw.ellipse(
        [(width - cm - notch_r, notch_y - notch_r), (width - cm + notch_r, notch_y + notch_r)],
        fill=bg_color,
    )

    footer_color = (40, 35, 30, 255)
    draw.rectangle(
        [(cm, footer_top), (width - cm, footer_top + card_r)],
        fill=footer_color,
    )
    draw.rounded_rectangle(
        [(cm, footer_top), (width - cm, height - cm)],
        radius=card_r,
        fill=footer_color,
    )

    title_font = _load_font(78, bold=True)
    sub_font = _load_font(34)
    tag_font = _load_font(28)
    tw, _, _ = _text_size(draw, "爸爸的樂透實驗", title_font)
    title_shadow = (0, 50, 20, 150) if is_profit_card else (0, 20, 80, 150)
    _draw_shadowed_text(
        draw, (cx - tw // 2, cm + 30), "爸爸的樂透實驗", title_font,
        (255, 255, 255, 255), shadow_fill=title_shadow, shadow_offset=(4, 4),
    )
    _dc(cm + 140, f"{game.name} · 第二區 1–8 全包 · {result.periods:,} 期", sub_font, gold)
    tag_text = "這次會賺，主要是少數幾次大獎" if is_profit_card else "比較常中，最後有比較划算嗎？"
    tag_color = (220, 255, 230, 255) if is_profit_card else (200, 220, 255, 255)
    _dc(cm + 192, tag_text, tag_font, tag_color)

    ball_size = 100
    gap = 16
    total_w = len(numbers) * ball_size + (len(numbers) - 1) * gap
    start_x = (width - total_w) // 2
    ball_y = 292
    ball_font = _load_font(50, bold=True)
    for i, num in enumerate(numbers):
        bx = start_x + i * (ball_size + gap)
        _draw_number_ball(draw, bx, ball_y, num, ball_size, ball_font)

    label_font = _load_font(32, bold=True)
    label_color = (21, 128, 61, 255) if is_profit_card else (30, 58, 138, 255)
    _dc(398, "＋ 第二區 1 ～ 8  全包", label_font, label_color)

    narrative_font = _load_font(36)
    cost_per = TICKET_COST[game.code] * game.bonus_pool
    if is_profit_card:
        _dc(438, f"每期投入 {format_money(cost_per)} 購買八注，歷史結果為", narrative_font, (80, 75, 70, 255))
    else:
        _dc(438, f"每期投入 {format_money(cost_per)} 購買八注，{result.periods:,} 期結果為", narrative_font, (80, 75, 70, 255))

    money_text = ("+" if is_profit_card else "") + format_money(result.net)
    money_font = _fit_font(draw, money_text, width - 240, 120, min_size=72, bold=True)
    box_fill = (220, 252, 231, 255) if is_profit_card else (235, 240, 255, 255)
    text_fill = (21, 128, 61, 255) if is_profit_card else (30, 58, 138, 255)
    _draw_money_box(
        draw,
        cx=cx,
        y=498,
        text=money_text,
        font=money_font,
        box_fill=box_fill,
        text_fill=text_fill,
    )

    magnitude_font = _load_font(32, bold=True)
    _dc(718, f"損益絕對值：{format_money(abs(result.net))}", magnitude_font, (120, 90, 55, 255))
    _dc(766, "這是過去的結果，不是在預測下一期", _load_font(28), (120, 115, 110, 255))

    stat_label_y = 815
    stat_value_y = 863
    stat_label_font = _load_font(30)
    stats = [
        ("花了本金", format_money(result.total_cost)),
        ("中獎領回", format_money(result.total_prize)),
        ("頭獎次數", f"{result.exact_hits} 次"),
    ]
    col_count = 3
    col_w = (width - 80) // col_count
    base_x = 40
    for i, (label, value) in enumerate(stats):
        col_cx = base_x + i * col_w + col_w // 2
        v_font = _fit_font(draw, value, col_w - 24, 38, min_size=26, bold=True)
        lw, _, _ = _text_size(draw, label, stat_label_font)
        vw, _, _ = _text_size(draw, value, v_font)
        draw.text((col_cx - lw // 2, stat_label_y), label, font=stat_label_font, fill=(120, 115, 110, 255))
        draw.text((col_cx - vw // 2, stat_value_y), value, font=v_font, fill=(30, 30, 30, 255))
    for i in range(1, col_count):
        sep_x = base_x + i * col_w
        draw.line([(sep_x, stat_label_y - 4), (sep_x, stat_value_y + 50)],
                  fill=(225, 215, 205, 255), width=2)

    draw.line([(80, 940), (width - 80, 940)], fill=(225, 215, 205, 255), width=2)

    if is_profit_card:
        cta_text = "本次正報酬主要由少數高額獎項造成。"
    else:
        cta_text = "提高中獎頻率，不等於提高長期報酬率。"
    cta_font = _fit_font(draw, cta_text, width - 120, 38, min_size=28, bold=True)
    cta_color = (21, 128, 61, 255) if is_profit_card else (30, 58, 138, 255)
    _dc(964, cta_text, cta_font, cta_color)

    brand_font = _load_font(30, bold=True)
    foot_font = _load_font(26)
    _dc(footer_top + 30, "爸爸的樂透實驗 · 歷史資料回測", brand_font, gold)
    _dc(footer_top + 80, "這張圖只整理過去資料，不是投注建議", foot_font, (200, 195, 185, 255))

    image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def format_money(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}NT$ {abs(value):,}"


def format_plain_money(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,} 元"


def jackpot_pct(odds: int) -> str:
    """把 1/odds 換算成百分比，自動保留 2 個有效數字。"""
    if not odds:
        return ""
    import math
    pct = 1 / odds * 100
    if pct >= 1:
        return f"{pct:.1f}%"
    mag = math.floor(math.log10(pct))
    decimals = -mag + 1
    return f"{pct:.{decimals}f}%"


def format_chinese_date(value: pd.Timestamp | dt.datetime | dt.date | None) -> str:
    if value is None or pd.isna(value):
        return "日期不明"
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return f"{value.year}年{value.month}月{value.day}日"


def build_date_ticks(dates: pd.Series) -> tuple[list[pd.Timestamp], list[str]]:
    clean_dates = [date for date in dates if not pd.isna(date)]
    if not clean_dates:
        return [], []
    step = max(1, len(clean_dates) // 5)
    tick_values = clean_dates[::step][:5]
    if clean_dates[-1] not in tick_values:
        tick_values.append(clean_dates[-1])
    return tick_values, [format_chinese_date(value) for value in tick_values]


def build_money_ticks(min_value: int, max_value: int) -> tuple[list[int], list[str]]:
    span = max(1, max_value - min_value)
    target_ticks = 6
    raw_step = span / target_ticks
    # 把刻度間距吸到 1/2/5 × 10^n，避免頭獎落在 +30M 時生出上千個刻度直接卡死瀏覽器。
    magnitude = 10 ** max(0, len(str(int(raw_step))) - 1)
    for multiplier in (1, 2, 5, 10):
        step = multiplier * magnitude
        if step >= raw_step:
            break
    else:
        step = magnitude * 10
    bottom = (min_value // step) * step
    if bottom > min_value:
        bottom -= step
    top = ((max_value // step) + 1) * step
    tick_values = list(range(bottom, top + 1, step))
    if max_value not in tick_values:
        tick_values.append(max_value)
    return tick_values, [format_plain_money(value) for value in tick_values]


def render_strategy_battle(
    game: GameDef,
    data_path: str,
    data_mtime: float,
    total_periods: int,
    toggle_key: str,
) -> None:
    show_strategy = st.toggle("比較幾種常見選法", value=False, key=toggle_key)
    if not show_strategy:
        return

    st.markdown(
        """
        <div class="section-card">
          <div class="section-eyebrow">選號方法比較</div>
          <div class="section-title">熱號、農民曆、新聞明牌，哪個比較有用？</div>
          <p class="section-copy">
            每種方法都用同一段開獎紀錄、同樣的買法和成本，再和隨機選號放在一起比較。長條只是呈現最後差了多少錢，不是明牌排行榜。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    min_history = min(100, max(30, total_periods // 10))
    loading_slot = st.empty()
    loading_slot.markdown(
        '<div class="loading-card">'
        '<div class="loading-title">正在重跑幾種選號方法</div>'
        '<div class="loading-balls">'
        '<span class="loading-ball">比</span>'
        '<span class="loading-ball">對</span>'
        '<span class="loading-ball">中</span>'
        '</div>'
        '<div class="loading-subtitle">每種方法都用同一段資料和相同成本。</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    summary_df = run_strategy_battle_cached(
        game.code,
        data_path,
        data_mtime,
        min_history,
        cache_version=5,
    )
    loading_slot.empty()

    group_summary = build_group_summary(summary_df)
    render_strategy_loss_list(group_summary)

    best_row = summary_df.loc[summary_df["總損益"].idxmax()]
    worst_row = summary_df.loc[summary_df["總損益"].idxmin()]
    st.markdown(
        f"""
        <div class="strategy-note">
          這次表現最好的是「{best_row['派別']}」：{format_money(int(best_row['總損益']))}。<br/>
          最差的是「{worst_row['派別']}」：{format_money(int(worst_row['總損益']))}。但換一段年份，順序就可能改變。
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="verdict-card">
          不同遊戲、不同年份，排名都會變動。把資料拉長後，沒有任何一種方法能一直贏過隨機選號；那些小差距比較像運氣，不像真的找到規律。
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_group_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    group_order = ["電腦選號", "追熱號", "反著買", "農民曆", "看新聞挑"]
    group_summary = (
        summary_df.groupby("派別", as_index=False)["總損益"]
        .mean()
        .rename(columns={"總損益": "平均總損益"})
    )
    group_summary["派別"] = pd.Categorical(group_summary["派別"], categories=group_order, ordered=True)
    group_summary = group_summary.sort_values("派別")
    group_summary["顯示金額"] = group_summary["平均總損益"].round().astype(int).map(format_money)
    return group_summary


def render_strategy_loss_list(group_summary: pd.DataFrame) -> None:
    max_loss = max(abs(float(value)) for value in group_summary["平均總損益"])
    rows = []
    for _, row in group_summary.iterrows():
        loss = abs(float(row["平均總損益"]))
        width = 0 if max_loss == 0 else max(8, loss / max_loss * 100)
        description = STRATEGY_GROUP_DESCRIPTIONS.get(row["派別"], "")
        rows.append(
            f"<div class='strategy-row'>"
            f"<div class='strategy-row-top'>"
            f"<span class='strategy-name'>{row['派別']}</span>"
            f"<span class='strategy-loss'>平均 {row['顯示金額']}</span>"
            f"</div>"
            f"<div class='strategy-desc'>{description}</div>"
            f"<div class='strategy-bar-bg'><div class='strategy-bar-fill' style='width: {width:.1f}%'></div></div>"
            f"</div>"
        )
    st.markdown(f"<div class='strategy-list'>{''.join(rows)}</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def run_strategy_battle_cached(
    game_code: str,
    data_path: str,
    data_mtime: float,
    min_history: int,
    cache_version: int = 5,
) -> pd.DataFrame:
    del data_mtime, cache_version
    game = get_game(game_code)
    draws = load_game_data(game, data_path)
    results = run_backtest(draws, game, strategy_names=FAST_STRATEGIES, min_history=min_history, seed=42)

    group_by_strategy = {strategy: group for group, names in STRATEGY_GROUPS.items() for strategy in names}
    group_by_strategy[BASELINE_STRATEGY] = "電腦選號"
    ticket_cost = TICKET_COST[game.code]

    summaries = []
    for result in results:
        total_prize = 0
        for index, record in enumerate(result.records, start=1):
            draw = draws[min_history + index - 1]
            bonus_set = set(draw.get("bonus", []))
            bonus_hits = len(set(record.predicted) & bonus_set)
            total_prize += prize_for_hits(game, record.hits, bonus_hits)
        total_cost = len(result.records) * ticket_cost
        summaries.append(
            {
                "派別": group_by_strategy[result.strategy],
                "策略": STRATEGY_NAMES_ZH.get(result.strategy, result.strategy),
                "總損益": total_prize - total_cost,
            }
        )
    return pd.DataFrame(summaries)


def render_backtest_explainer() -> None:
    st.markdown(
        "\n".join(
            [
                "**怎麼避免偷看答案？**",
                "",
                "每一期都只使用它以前的開獎紀錄產生號碼，選完後才和當期結果比對。",
                "從第一期一路重複到最後，避免用已知答案倒推一套看起來很準的規則。",
                "",
                "**獎金怎麼估？**",
                "",
                "- 固定獎依官方規則；頭獎、貳獎等浮動獎項，採近五年平均單人實領金額。",
                "- 春節加碼與大紅包的規則逐年不同，因此沒有納入。",
                "- 金額用來比較長期成本與獎金，不是精算每一期實際派彩。",
            ]
        )
    )


def render_footer_warning() -> None:
    st.markdown(
        """
        <div class="warning-line">
          這個網站不是選號工具，只是把過去資料攤開來看。<br/>
          彩券可以當娛樂，但別把明牌當成投資方法。
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()