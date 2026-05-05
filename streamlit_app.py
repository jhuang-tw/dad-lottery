"""Lotry Streamlit app: a data confession for lottery myths."""

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

# 各派只跑一個代表策略，讓長輩頁面不會卡（原本 27 倍 → 5 倍）。
STRATEGY_REPRESENTATIVES = {
    "追熱號": "hot",
    "反著買": "anti_hot",
    "農民曆": "almanac_combined",
    "看新聞挑": "date_numerology",
}
FAST_STRATEGIES = list(STRATEGY_REPRESENTATIVES.values()) + [BASELINE_STRATEGY]

# 每一派一句話解釋，讓套股人也看得懂。
STRATEGY_GROUP_DESCRIPTIONS = {
    "電腦選號": "電腦隨機亂選，不看任何規則。",
    "追熱號": "看哪幾個號碼最近常開，就跟著買。",
    "反著買": "別人常買的我不買，改挑冷門號碼。",
    "農民曆": "看農民曆、干支、五行來挑號碼。",
    "看新聞挑": "把今天日期、社會大事變成號碼。",
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

# This project compares strategies by main-number hits. Taiwan lottery prizes have
# special-number and pari-mutuel details, so the app uses a deliberately transparent
# fixed estimate for education rather than claiming exact accounting.
# Key = (主區命中數, 特別號/第二區命中數)
PRIZE_TABLE = {
    "lotto649": {
        (6, 0): 5_000_000,   # 頭獎（簡化估算）
        (5, 1): 150_000,     # 貳獎
        (5, 0): 20_000,      # 參獎
        (4, 1): 4_000,       # 肆獎
        (4, 0): 800,         # 伍獎
        (3, 1): 400,         # 陸獎
        (3, 0): 200,         # 柒獎
        (2, 1): 100,         # 普獎
    },
    "superlotto638": {
        (6, 1): 100_000_000, # 頭獎（簡化估算）
        (6, 0): 1_500_000,   # 貳獎
        (5, 1): 150_000,     # 參獎
        (5, 0): 20_000,      # 肆獎
        (4, 1): 4_000,       # 伍獎
        (4, 0): 800,         # 陸獎
        (3, 1): 400,         # 柒獎
        (3, 0): 200,         # 捌獎
        (2, 1): 100,         # 玖獎
        (1, 1): 100,         # 拾獎
        (0, 1): 100,         # 普獎
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
        page_title="爸爸的樂透實驗｜電腦選號就好，省下的時間多陪陪家人吧",
        page_icon="🎲",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inject_style()

    render_opening()

    st.markdown('<div class="step-label">1. 先選遊戲</div>', unsafe_allow_html=True)
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
    st.caption(f"使用 {game.name} 全部資料，共 {len(draws):,} 期。")

    render_custom_challenge(game, draws)

    strategy_toggle_key = f"show_strategy_{game.code}"
    with st.expander("想知道怎麼算？（可跳過）", expanded=st.session_state.get(strategy_toggle_key, False)):
        render_backtest_explainer()
        render_strategy_battle(game, str(data_path), os.path.getmtime(data_path), len(draws), strategy_toggle_key)

    render_footer_warning()


def inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --lotry-red: #cf2e2e;
            --lotry-red-dark: #991b1b;
            --lotry-gold: #f8c74a;
            --lotry-ink: #172033;
            --lotry-muted: #667085;
            --lotry-paper: #fffaf2;
            /* 統一垂直節奏，避免每個元件各自設定 margin 造成擁擠或鬆散 */
            --gap-xs: .4rem;
            --gap-sm: .8rem;
            --gap-md: 1.2rem;
            --gap-lg: 1.8rem;
            --gap-xl: 2.6rem;
            --radius: 14px;
            --border-strong: 2px solid #172033;
            --border-soft: 1px solid #e5e0d4;
        }
        .stApp {
            background: linear-gradient(180deg, #fff7ed 0%, #ffffff 38%, #eef2ff 100%);
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 3rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 720px;
        }
        #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
        header { visibility: hidden; height: 0; }
        html, body, [class*="css"], .stApp, button, input, textarea, select {
            font-family: "Microsoft JhengHei", "Noto Sans TC", "PingFang TC", Arial, sans-serif !important;
            font-size: 17px;
            letter-spacing: 0;
        }

        /* === HERO === */
        .hero {
            position: relative;
            overflow: hidden;
            padding: 1.8rem 1.5rem 2rem;
            background: #991b1b;
            border-radius: var(--radius);
            margin: 0 0 var(--gap-xl);
            color: #ffffff;
            box-shadow: 0 6px 18px rgba(153, 27, 27, 0.18);
        }
        .hero-kicker {
            display: inline-block;
            font-size: .95rem;
            font-weight: 900;
            color: #f8c74a;
            margin-bottom: .8rem;
            letter-spacing: .08em;
            padding: .25rem .6rem;
            border: 1.5px solid rgba(248, 199, 74, .55);
            border-radius: 999px;
        }
        .hero h1 {
            margin: 0 0 1rem 0;
            letter-spacing: 0;
            font-size: clamp(2rem, 7vw, 3rem);
            line-height: 1.2;
            font-weight: 900;
        }
        .hero p {
            font-size: 1.15rem;
            line-height: 1.75;
            margin: 0;
            font-weight: 600;
            color: #ffffff;
        }
        .hero strong {
            display: block;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1.5px solid rgba(248, 199, 74, .35);
            color: #f8c74a;
            font-size: 1.1rem;
            font-weight: 900;
            line-height: 1.65;
        }

        /* === SECTION RHYTHM === */
        .step-label {
            color: #000000;
            font-size: 1.4rem;
            font-weight: 900;
            margin: var(--gap-xl) 0 var(--gap-sm);
            border-left: 6px solid #cf2e2e;
            padding-left: 12px;
        }
        .step-label:first-child { margin-top: 0; }
        .section-card {
            padding: 1.4rem 1.3rem;
            border: var(--border-strong);
            border-radius: var(--radius);
            background: #ffffff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
            margin: var(--gap-md) 0 var(--gap-lg);
        }
        .section-eyebrow { color: #991b1b; font-weight: 900; font-size: 1rem; margin-bottom: .3rem; letter-spacing: .03em; }
        .section-title { color: #000000; font-size: 1.5rem; font-weight: 900; margin: 0 0 .5rem; line-height: 1.3; }
        .section-copy { color: #1a202c; line-height: 1.7; margin: 0; font-size: 1.1rem; font-weight: 500; }

        /* === STREAMLIT WIDGET TWEAKS === */
        div[data-testid="stRadio"] { margin-bottom: .4rem; }
        div[data-testid="stRadio"] label { font-size: 1.15rem !important; font-weight: 700 !important; }
        [data-testid="stCaptionContainer"] { margin: .2rem 0 1rem; font-size: 1rem !important; color: #475569 !important; }
        div[data-testid="stExpander"] { margin: var(--gap-sm) 0; border: 1.5px solid #cbd5e1 !important; border-radius: var(--radius) !important; }
        div[data-testid="stExpander"] details summary { font-size: 1.1rem; font-weight: 700; padding: .9rem 1rem !important; }
        div[data-testid="stExpander"] details[open] summary { border-bottom: 1px solid #e2e8f0; }
        div[data-testid="stRadio"] label,
        div[data-testid="stRadio"] label *,
        div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        div[data-testid="stExpander"] details,
        div[data-testid="stExpander"] details summary,
        div[data-testid="stExpander"] details summary *,
        div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
            color: #172033 !important;
            opacity: 1 !important;
        }
        div[data-testid="stRadio"] input[type="radio"] { opacity: 1 !important; }
        /* Streamlit 預設 metric 保留樣式以防舊位置使用，但不再主動使用 */
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: var(--border-strong);
            border-radius: var(--radius);
            padding: .9rem .6rem;
            text-align: center;
            overflow: visible !important;
        }
        div[data-testid="stMetric"] label { font-size: 1rem !important; font-weight: 900 !important; color: #000000 !important; white-space: normal !important; }
        div[data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 900 !important; color: #b91c1c !important; white-space: normal !important; word-break: break-all !important; line-height: 1.3 !important; }

        /* === STAT GRID === */
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin: var(--gap-sm) 0 var(--gap-md); }
        .stat-grid.three { grid-template-columns: 1fr 1fr 1fr; }
        .stat-card {
            background: #ffffff;
            border: 1.5px solid #cbd5e1;
            border-radius: 12px;
            padding: .9rem .6rem;
            text-align: center;
        }
        .stat-card-label { font-size: .95rem; font-weight: 700; color: #475569; margin-bottom: .25rem; }
        .stat-card-value { font-size: 1.3rem; font-weight: 900; color: #b91c1c; word-break: break-all; line-height: 1.25; }
        .stat-card-value.neutral { color: #0f172a; }

        /* === BALLS === */
        .selected-strip {
            display: flex;
            align-items: center;
            gap: .7rem;
            flex-wrap: wrap;
            justify-content: center;
            min-height: 4.2rem;
            padding: 1rem .9rem;
            border-radius: var(--radius);
            background: #fffcf0;
            border: 2px dashed #b91c1c;
            margin: 0 0 var(--gap-sm);
        }
        .selected-label { color: #1a202c; font-weight: 900; margin-right: .3rem; font-size: 1.15rem; }
        .lottery-ball {
            width: 3.1rem;
            height: 3.1rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #cf2e2e;
            color: #ffffff;
            font-weight: 900;
            font-size: 1.25rem;
            border: 2.5px solid #1a1a1a;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.18);
        }
        .mini-ball {
            width: 2.8rem;
            height: 2.8rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #000000;
            font-weight: 900;
            font-size: 1.2rem;
            background: #ffffff;
            border: 2.5px solid #f8c74a;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.15);
        }

        /* === BUTTONS === */
        div.stButton > button,
        div.stDownloadButton > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius: 12px;
            min-height: 3.4rem;
            padding: 0 1.6rem;
            font-weight: 900;
            font-size: 1.15rem;
            border: 2px solid #1a1a1a;
            background: #ffffff;
            color: #1a1a1a;
            transition: all .12s ease;
        }
        div.stButton > button:hover,
        div.stDownloadButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0, 0, 0, 0.12); }
        div.stButton > button[kind="primary"] {
            background: #cf2e2e;
            color: #ffffff;
            border-color: #1a1a1a;
        }
        div.stDownloadButton > button p,
        div[data-testid="stDownloadButton"] > button p { color: #1a1a1a !important; font-size: 1.15rem !important; font-weight: 900 !important; white-space: nowrap !important; }
        div.stButton > button:not([kind="primary"]) p { color: #1a1a1a !important; }
        div.stButton > button[kind="primary"] p { color: #ffffff !important; font-size: 1.2rem !important; font-weight: 900 !important; white-space: nowrap !important; }
        /* 自製超連結按鈕（如 LINE 分享）：與 stButton 視覺尺寸一致 */
        a.app-link-btn {
            display: flex !important;
            align-items: center;
            justify-content: center;
            min-height: 3.4rem;
            padding: 0 1.2rem;
            border-radius: 12px;
            border: 2px solid #1a1a1a;
            font-weight: 900;
            font-size: 1.15rem;
            line-height: 1.1;
            text-decoration: none !important;
            box-sizing: border-box;
            transition: all .12s ease;
        }
        a.app-link-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0, 0, 0, 0.12); }
        a.app-link-btn.line-green { background: #06C755; color: #ffffff !important; }
        .ball-row div.stButton { width: 100%; }
        .ball-row div.stButton > button {
            width: 100% !important;
            min-width: 0 !important;
            min-height: 2.6rem !important;
            padding: .25rem .4rem !important;
            font-size: 1.05rem;
            background: #ffffff;
            color: #1a1a1a;
            border: 1.5px solid #94a3b8;
            border-radius: 10px !important;
        }
        .ball-row div.stButton > button[kind="primary"] {
            background: #cf2e2e;
            color: #ffffff;
            border: 2px solid #1a1a1a;
        }
        .ball-row div.stButton > button div[data-testid="stMarkdownContainer"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        .ball-row div.stButton > button p {
            font-size: 1rem !important;
            line-height: 1 !important;
            margin: 0 !important;
            padding: 0 !important;
            white-space: nowrap !important;
            letter-spacing: 0 !important;
        }
        .ball-row div.stButton > button[kind="primary"] p { font-weight: 900 !important; color: #ffffff !important; }

        /* === RESULT CARDS === */
        .loss-box {
            padding: 1.6rem 1.4rem;
            border-radius: var(--radius);
            background: #fffafa;
            border: 2px solid #b91c1c;
            text-align: center;
            margin: 0 0 var(--gap-sm);
            box-shadow: 0 4px 12px rgba(185, 28, 28, .08);
        }
        .loss-number {
            color: #b91c1c;
            font-size: clamp(2.6rem, 11vw, 4.4rem);
            font-weight: 900;
            line-height: 1.05;
            margin-top: .8rem;
            letter-spacing: -.01em;
        }
        .quiet-note { color: #1a202c; font-size: 1.1rem; line-height: 1.65; font-weight: 600; }
        .tangible-loss {
            margin: 0 0 var(--gap-md);
            padding: 1.1rem 1rem;
            border-radius: var(--radius);
            background: #fff7ed;
            border: 2px dashed #f59e0b;
            color: #1a202c;
            font-size: 1.1rem;
            font-weight: 700;
            line-height: 1.85;
            text-align: center;
        }
        .tangible-loss .emoji { font-size: 1.5rem; margin-right: .3rem; }
        .verdict-card {
            margin: 0 0 var(--gap-md);
            padding: 1.3rem 1.2rem;
            border-radius: var(--radius);
            background: #fffcf0;
            border: 2px solid #b91c1c;
            color: #1a202c;
            font-weight: 700;
            line-height: 1.75;
            font-size: 1.1rem;
        }
        .verdict-card b { color: #991b1b; }
        .verdict-card u { text-decoration-color: #cf2e2e; text-decoration-thickness: 2px; text-underline-offset: 3px; }
        .simple-result-card {
            margin: 0 0 var(--gap-md);
            padding: 1.4rem 1.2rem;
            border-radius: var(--radius);
            background: #ffffff;
            border: var(--border-strong);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
        }
        .simple-result-title { color: #000000; font-size: 1.25rem; font-weight: 900; margin-bottom: .6rem; line-height: 1.4; }
        .loss-track { height: .9rem; border-radius: 999px; background: linear-gradient(90deg, #fee2e2, #ef4444); margin: 1rem 0 .7rem; }
        .loss-track-labels { display: flex; justify-content: space-between; color: #1a202c; font-size: 1rem; font-weight: 900; }

        /* === LOADING === */
        .loading-card {
            margin: 1rem 0;
            padding: 1.4rem 1.2rem;
            border-radius: var(--radius);
            background: #fffcf0;
            border: 2px solid #b91c1c;
            text-align: center;
        }
        .loading-title { color: #000000; font-weight: 900; font-size: 1.2rem; margin-bottom: .7rem; }
        .loading-subtitle { color: #1a202c; font-size: 1rem; font-weight: 600; line-height: 1.55; }
        .loading-balls { display: flex; justify-content: center; gap: .55rem; margin: .8rem 0; }
        .loading-ball {
            width: 2.7rem;
            height: 2.7rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: 900;
            font-size: 1.05rem;
            background: #cf2e2e;
            border: 2px solid #1a1a1a;
            animation: ball-bounce 900ms ease-in-out infinite;
        }
        .loading-ball:nth-child(2) { animation-delay: 90ms; }
        .loading-ball:nth-child(3) { animation-delay: 180ms; }
        .loading-ball:nth-child(4) { animation-delay: 270ms; }
        .loading-ball:nth-child(5) { animation-delay: 360ms; }
        .loading-ball:nth-child(6) { animation-delay: 450ms; }
        @keyframes ball-bounce {
            0%, 100% { transform: translateY(0); }
            45% { transform: translateY(-.45rem); }
        }

        /* === SHARE CTA === */
        .share-cta {
            margin: var(--gap-xl) 0 var(--gap-md);
            padding: 1.5rem 1.3rem;
            border-radius: var(--radius);
            background: linear-gradient(135deg, #1e3a5f 0%, #172033 100%);
            color: #ffffff;
            text-align: center;
            border: 2.5px solid #f8c74a;
            box-shadow: 0 6px 18px rgba(23, 32, 51, .18);
        }
        .share-cta-title { font-size: 1.4rem; font-weight: 900; margin-bottom: .5rem; color: #f8c74a; line-height: 1.4; }
        .share-cta-body { font-size: 1.05rem; font-weight: 600; line-height: 1.7; color: #ffffff; }

        /* === FOOTER WARNING === */
        .warning-line {
            margin: var(--gap-xl) 0 .5rem;
            padding: 1.4rem 1.2rem;
            border-radius: var(--radius);
            color: #ffffff;
            background: #b91c1c;
            border: 2px solid #1a1a1a;
            font-size: 1.2rem;
            font-weight: 800;
            text-align: center;
            line-height: 1.7;
        }

        /* === STRATEGY BATTLE === */
        .strategy-note {
            margin: var(--gap-md) 0;
            padding: 1.1rem 1rem;
            border-radius: var(--radius);
            background: #e0f2fe;
            border: 1.5px solid #0369a1;
            color: #0c4a6e;
            font-weight: 700;
            font-size: 1.05rem;
            line-height: 1.65;
        }
        .strategy-list { display: grid; gap: .7rem; margin: var(--gap-md) 0; }
        .strategy-row {
            padding: 1rem 1rem;
            background: #ffffff;
            border: 1.5px solid #cbd5e1;
            border-radius: var(--radius);
            margin-bottom: 0;
        }
        .strategy-row-top {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: .8rem;
            margin-bottom: .45rem;
        }
        .strategy-name { font-size: 1.15rem; color: #000000; font-weight: 900; }
        .strategy-loss { font-size: 1.1rem; color: #b91c1c; font-weight: 900; white-space: nowrap; }
        .strategy-desc { font-size: 1rem; color: #475569; font-weight: 600; line-height: 1.55; margin: 0 0 .55rem; }
        .strategy-bar-bg { height: .8rem; border-radius: 999px; background: #fee2e2; overflow: hidden; }
        .strategy-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f87171, #b91c1c); }

        /* === MOBILE === */
        @media (max-width: 640px) {
            html, body, [class*="css"], .stApp, button, input, textarea, select { font-size: 17px !important; }
            .block-container { padding-left: .75rem; padding-right: .75rem; padding-top: .6rem; }
            .hero { padding: 1.4rem 1.1rem 1.6rem; margin-bottom: var(--gap-lg); }
            .hero h1 { font-size: 2.1rem; }
            .hero p { font-size: 1.05rem; line-height: 1.7; }
            .hero strong { font-size: 1rem; margin-top: .8rem; padding-top: .8rem; }
            .step-label { font-size: 1.2rem; margin-top: var(--gap-lg); }
            .section-card { padding: 1.1rem 1rem; }
            .section-title { font-size: 1.3rem; }
            .section-copy { font-size: 1rem; }
            .loss-box { padding: 1.3rem 1rem; }
            .verdict-card, .simple-result-card { padding: 1.1rem .95rem; font-size: 1rem; }
            .tangible-loss { font-size: 1rem; padding: 1rem .9rem; }
            .stat-grid.three { grid-template-columns: 1fr 1fr; }
            .stat-card-value { font-size: 1.15rem; }
            .stat-card-label { font-size: .9rem; }
            .lottery-ball { width: 2.7rem; height: 2.7rem; font-size: 1.1rem; border-width: 2px; }
            .selected-strip { padding: .85rem .7rem; gap: .5rem; }
            .selected-label { font-size: 1.05rem; }
            div.stButton > button { font-size: 1.1rem; min-height: 3.2rem; padding: 0 1.2rem; }
            div.stButton > button[kind="primary"] p { font-size: 1.1rem !important; }
            .ball-row div.stButton > button { min-height: 2.4rem !important; padding: .2rem .3rem !important; font-size: 1rem; }
            .ball-row div.stButton > button p { font-size: .95rem !important; }
            .share-cta { padding: 1.3rem 1.1rem; }
            .share-cta-title { font-size: 1.2rem; }
            .share-cta-body { font-size: 1rem; }
            .warning-line { padding: 1.2rem 1rem; font-size: 1.1rem; }
            .strategy-row { padding: .9rem .85rem; }
            .strategy-name { font-size: 1.05rem; }
            .strategy-loss { font-size: 1rem; }
        }
        @media (max-width: 380px) {
            .hero h1 { font-size: 1.85rem; }
            .lottery-ball { width: 2.4rem; height: 2.4rem; font-size: 1rem; }
            .ball-row div.stButton > button { min-height: 2.2rem !important; font-size: .9rem; }
        }

        /* hide Material icon name that leaks as text in expander headers */
        [data-testid="stExpanderToggleIcon"] { display: none !important; }
        [data-testid="stIconMaterial"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_opening() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">給長輩的真心話</div>
          <h1>爸爸的樂透實驗</h1>
          <p>我們把大家常聽到的明牌，全部拿去對對看歷年的開獎結果。<br/><strong>說句老實話：交給電腦選號就好，省下算牌的時間，多陪陪家人吧！</strong></p>
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
    if st.button("電腦幫我選，馬上看結果", type="primary", width="stretch"):
        numbers = sorted(random_sample(game))
        set_selected_numbers(game, numbers)
        st.session_state[result_key(game)] = (numbers, run_custom_backtest_with_loading(numbers, draws, game, quick_loading_slot))
        request_scroll("lotry-result-anchor")

    with st.expander("我要自己挑號碼（可跳過）"):
        st.caption(f"從 1 到 {game.main_pool} 任選 {game.main_pick} 顆球，選滿後按「看我的結果」。")
        selected = render_ball_picker(game)
        is_complete = len(selected) == game.main_pick
        action_cols = st.columns(2)
        with action_cols[0]:
            challenge = st.button(
                "看我的結果",
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
            st.info(f"還差 {game.main_pick - len(selected)} 顆球。")
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
          <div class="loading-title">正在跑 12 年歷史資料…</div>
          <div class="loading-balls">{balls}</div>
          <div class="loading-subtitle">正在把這組號碼一期一期重算，馬上給你看結果。</div>
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
    return CustomBacktest(periods, total_cost, total_prize, net, avg_hits, max_hits, exact_hits, near_hits, records)


def render_custom_result(result: CustomBacktest, numbers: list[int], game: GameDef) -> None:
    st.markdown('<div class="step-label">3. 看結果</div>', unsafe_allow_html=True)
    result_balls = "".join(f'<span class="lottery-ball">{number:02d}</span>' for number in numbers)
    st.markdown(
        f"""
        <div class="selected-strip">
          <span class="selected-label">你的明牌</span>
          {result_balls}
        </div>
        """,
        unsafe_allow_html=True,
    )
    abs_loss = abs(result.net)
    st.markdown(
        f"""
        <div class="loss-box">
          <div class="quiet-note">如果這 {result.periods:,} 期你都照著買，<br/>一路買到現在會變成…</div>
          <div class="loss-number">{format_money(result.net)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # 具象化損失：讓長輩「感受到」這筆錢能做什麼
    if abs_loss > 0:
        dinners = abs_loss // 300
        trips = abs_loss // 15000
        tangible_parts = []
        if dinners >= 1:
            tangible_parts.append(f'<span class="emoji">🍲</span> 請全家吃 <b>{dinners:,}</b> 頓好料')
        if trips >= 1:
            tangible_parts.append(f'<span class="emoji">✈️</span> 帶爸媽出去玩 <b>{trips:,}</b> 趟國內旅行')
        if tangible_parts:
            st.markdown(
                '<div class="tangible-loss">'
                '這些錢本來可以⋯<br/>'
                + '<br/>'.join(tangible_parts)
                + '</div>',
                unsafe_allow_html=True,
            )
    st.markdown(
        f"""
        <div class="stat-grid three">
          <div class="stat-card"><div class="stat-card-label">總共花了</div><div class="stat-card-value">{format_money(result.total_cost)}</div></div>
          <div class="stat-card"><div class="stat-card-label">總共領回</div><div class="stat-card-value">{format_money(result.total_prize)}</div></div>
          <div class="stat-card"><div class="stat-card-label">頭獎中過</div><div class="stat-card-value neutral">{result.exact_hits} 次</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    expected_avg = game.main_pick * game.main_pick / game.main_pool
    diff = result.avg_hits - expected_avg
    direction = "幾乎一模一樣" if abs(diff) < 0.05 else ("好一點點而已" if diff > 0 else "還比較差一點")
    st.markdown(
        f"""
        <div class="verdict-card">
          算下來，這組號碼平均每一期才中 <b>{result.avg_hits:.3f}</b> 顆球，<br/>
          跟閉著眼睛用電腦選號（<b>{expected_avg:.3f}</b> 顆）其實差不多啦！<br/>
          兩邊結果{direction}，<br/><u>最重要的一點是：不管是哪一種，到頭來都還是賠錢。</u>
        </div>
        """,
        unsafe_allow_html=True,
    )

    curve = go.Figure()
    chart_dates = pd.to_datetime(result.records["日期"], errors="coerce")
    chart_date_labels = [format_chinese_date(value) for value in chart_dates]
    chart_money_labels = [format_plain_money(int(value)) for value in result.records["累計損益"]]
    curve.add_trace(
        go.Scatter(
            x=chart_dates,
            y=result.records["累計損益"],
            customdata=list(zip(chart_date_labels, chart_money_labels, strict=True)),
            mode="lines",
            line=dict(color="#dc2626", width=3),
            name="你的明牌累計損益",
            hovertemplate="日期：%{customdata[0]}<br>累計損益：%{customdata[1]}<extra></extra>",
        )
    )
    tick_values, tick_labels = build_money_ticks(int(result.records["累計損益"].min()), 0)
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
    st.markdown(
        f"""
        <div class="simple-result-card">
          <div class="simple-result-title">說句真心話：這組號碼真的沒有比較好中</div>
          <div class="quiet-note">如果每一期都傻傻跟著買，<br/>辛苦賺來的錢就只會越來越少。</div>
          <div class="loss-track"></div>
          <div class="loss-track-labels"><span>開始：NT$ 0</span><span>現在：{format_money(result.net)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # --- 分享小卡 ---
    st.markdown(
        """
        <div class="share-cta">
          <div class="share-cta-title">把這個結果傳給親朋好友</div>
          <div class="share-cta-body">
            產生一張圖片，傳到賴（LINE）的家庭群組或是臉書。<br/>
            提醒身邊的人，這世界上真的沒有穩中的明牌。
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
    if st.button("📸 生成分享小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):
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
                label="💾 下載圖片",
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
                'target="_blank" rel="noopener noreferrer">💬 分享到 LINE</a>',
                unsafe_allow_html=True,
            )
        st.caption("💡 長按圖片也可以直接儲存或分享到任何 App")
    # --- 走勢圖 ---
    with st.expander("想看累計走勢圖（可跳過）"):
        st.plotly_chart(curve, width="stretch", config={"displayModeBar": False})
        st.caption("獎金為簡化估算，已將特別號／第二區計入；頭獎金額會浮動，用途是看趨勢，不是精算實際金額。")


def render_bonus_wheel_section(game: GameDef, draws: list[dict]) -> None:
    """包牌（僅特別號／第二區）試算：每期把整區號碼全買，看會賠多少。"""
    if game.code != "superlotto638":
        return

    st.markdown(
        """
        <div class="section-card">
          <div class="section-eyebrow">加碼試算</div>
          <div class="section-title">如果「包牌」只包特別號呢？</div>
          <p class="section-copy">
            常聽人說：「第二區全包就穩中啦！」<br/>
            真的嗎？點下去看看實際上會賠多少。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.session_state.get(selected_key(game)) or []
    if len(selected) != game.main_pick:
        st.caption("先在上面選滿 6 顆主區號碼，這個試算才知道你的明牌是哪組。")
        return

    if st.button("包第二區（1–8 全買）試算", width="stretch"):
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
    """每期買 bonus_pool 張票，每張只差第二區號碼，保證一定中第二區。"""
    rows = []
    cumulative_net = 0
    total_prize = 0
    bonus_pool = game.bonus_pool
    ticket_cost = TICKET_COST[game.code] * bonus_pool  # 一期買 bonus_pool 張
    pick_set = set(numbers)
    for index, draw in enumerate(draws, start=1):
        actual = set(draw["numbers"])
        hits = len(pick_set & actual)
        # 整個第二區都包，必中 1 個第二區號碼，其餘 (bonus_pool - 1) 張是 bonus=0
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
    return CustomBacktest(periods, total_cost, total_prize, net, avg_hits, max_hits, exact_hits, near_hits, records)


def render_bonus_wheel_result(result: CustomBacktest, numbers: list[int], game: GameDef) -> None:
    cost_per_period = TICKET_COST[game.code] * game.bonus_pool
    result_balls = "".join(f'<span class="lottery-ball">{number:02d}</span>' for number in numbers)
    st.markdown(
        f"""
        <div class="selected-strip">
          <span class="selected-label">主區明牌</span>
          {result_balls}
          <span class="selected-label" style="margin-left:12px;">＋第二區 1–8 全包</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="loss-box">
          <div class="quiet-note">
            這 {result.periods:,} 期下來，<br/>
            每期都花 {format_money(cost_per_period)} 霸氣全包第二區，<br/>
            雖然號稱「每期保證中普獎 100 元」，<br/>但其實…
          </div>
          <div class="loss-number">{format_money(result.net)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-grid three">
          <div class="stat-card"><div class="stat-card-label">總共花了</div><div class="stat-card-value">{format_money(result.total_cost)}</div></div>
          <div class="stat-card"><div class="stat-card-label">總共領回</div><div class="stat-card-value">{format_money(result.total_prize)}</div></div>
          <div class="stat-card"><div class="stat-card-label">頭獎中過</div><div class="stat-card-value neutral">{result.exact_hits} 次</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="verdict-card">
          <b>全包確實保證中獎，<br/>但中一張 100 元，代表其他 7 張都是做白工，<br/>扣掉本金照樣賠。</b><br/>
          以為靠「穩中」就能賺錢？這筆帳恐怕算錯囉。
        </div>
        """,
        unsafe_allow_html=True,
    )
    # --- 包牌分享小卡 ---
    st.markdown(
        """
        <div class="share-cta">
          <div class="share-cta-title">把這個結果傳給親朋好友</div>
          <div class="share-cta-body">
            把「全包也在賠」的真相產成一張圖，<br/>
            傳給那些說「包牌穩中」的人看看！
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
    if st.button("📸 生成包牌分享小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):
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
                label="💾 下載圖片",
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
                'target="_blank" rel="noopener noreferrer">💬 分享到 LINE</a>',
                unsafe_allow_html=True,
            )
        st.caption("💡 長按圖片也可以直接儲存或分享到任何 App")


def prize_for_hits(game: GameDef, main_hits: int, bonus_hits: int = 0) -> int:
    table = PRIZE_TABLE.get(game.code, {})
    return table.get((main_hits, bonus_hits), 0)


# 優先使用倉庫內附的 Noto Sans TC；沒有可縮放中文字型時不要產生小方塊壞圖。
_BUNDLED_FONT_PATH = ROOT / "assets" / "fonts" / "NotoSansTC-VF.ttf"
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
_SHARE_CARD_VERSION = 4


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
        # 變數字型：拉粗筆畫。一般字型不支援時直接略過。
        try:
            font.set_variation_by_axes([700.0 if bold else 400.0])
        except (AttributeError, OSError, TypeError, ValueError):
            pass
        return font
    raise RuntimeError(
        "分享小卡需要可縮放的中文字型。請確認 assets/fonts/NotoSansTC-VF.ttf 已經一起提交並部署，"
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
    """產生 1080×1200 的 PNG 分享小卡，帶圓角卡片框、落陰影與票根齒口裝飾。"""
    width, height = _SHARE_CARD_WIDTH, _SHARE_CARD_HEIGHT

    # ── 圖片底色：溫暖淺灰，讓卡片「浮」起來 ──
    bg_color = (228, 224, 216, 255)
    image = Image.new("RGBA", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    cx = width // 2
    cm = 22       # 卡片到圖邊的邊距
    card_r = 36   # 圓角半徑
    header_h = cm + 246   # header 底部絕對 y（= 268）
    footer_top = 1040     # footer 頂部絕對 y
    gold = (248, 199, 74, 255)

    def _dc(y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
        tw, _, _ = _text_size(draw, text, font)
        draw.text((cx - tw // 2, y), text, font=font, fill=fill)

    # ── 1. 卡片落陰影（偏移 + 半透明暖褐）──
    draw.rounded_rectangle(
        [(cm + 5, cm + 8), (width - cm + 5, height - cm + 8)],
        radius=card_r,
        fill=(60, 48, 36, 65),
    )

    # ── 2. 卡片本體（米白底色，帶圓角）──
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, height - cm)],
        radius=card_r,
        fill=(255, 252, 245, 255),
    )

    # ── 3. 頂部紅色 Header（上圓角、下平）──
    header_color = (153, 27, 27, 255)
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, header_h)],
        radius=card_r,
        fill=header_color,
    )
    # 把 header 底部的圓角區域填平
    draw.rectangle(
        [(cm, header_h - card_r), (width - cm, header_h)],
        fill=header_color,
    )

    # ── 4. 金色分隔線 ──
    draw.rectangle([(cm, header_h), (width - cm, header_h + 5)], fill=gold)

    # ── 5. 票根齒口（分隔線兩側各挖一個半圓，模仿實體票根）──
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

    # ── 6. Footer（上平、下圓角）──
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

    # ── 7. Header 文字 ──
    title_font = _load_font(78, bold=True)
    sub_font = _load_font(34)
    tag_font = _load_font(28)
    title_text = "爸爸的樂透實驗"
    tw, _, _ = _text_size(draw, title_text, title_font)
    _draw_shadowed_text(
        draw, (cx - tw // 2, cm + 30), title_text, title_font,
        (255, 255, 255, 255), shadow_fill=(80, 0, 0, 150), shadow_offset=(4, 4),
    )
    _dc(cm + 140, f"{game.name} · {result.periods:,} 期歷史回測", sub_font, gold)
    _dc(cm + 192, "每一期都照著買，買到現在的真實結果", tag_font, (255, 220, 200, 255))

    # ── 8. 號碼球 ──
    ball_size = 100
    gap = 16
    total_w = len(numbers) * ball_size + (len(numbers) - 1) * gap
    start_x = (width - total_w) // 2
    ball_y = 292
    ball_font = _load_font(50, bold=True)
    for i, num in enumerate(numbers):
        bx = start_x + i * (ball_size + gap)
        _draw_number_ball(draw, bx, ball_y, num, ball_size, ball_font)

    # ── 9. 敘事文字 ──
    narrative_font = _load_font(36)
    _dc(410, f"如果這 {result.periods:,} 期都照著買", narrative_font, (80, 75, 70, 255))
    _dc(454, "一路買到現在會變成⋯", narrative_font, (80, 75, 70, 255))

    # ── 10. 虧損金額框 ──
    money_text = format_money(result.net)
    money_font = _fit_font(draw, money_text, width - 240, 120, min_size=72, bold=True)
    _draw_money_box(
        draw,
        cx=cx,
        y=496,
        text=money_text,
        font=money_font,
        box_fill=(255, 235, 235, 255),
        text_fill=(185, 28, 28, 255),
    )

    # ── 11. 具象化損失 ──
    abs_loss = abs(result.net)
    tangible_font = _load_font(34, bold=True)
    if abs_loss > 0:
        dinners = abs_loss // 300
        trips = abs_loss // 15000
        lines: list[str] = []
        if dinners >= 1:
            lines.append(f"・這些錢能請全家吃 {dinners:,} 頓好料")
        if trips >= 1:
            lines.append(f"・能帶爸媽出去玩 {trips:,} 趟國內旅行")
        for i, line in enumerate(lines[:2]):
            _dc(705 + i * 52, line, tangible_font, (180, 100, 20, 255))

    # ── 12. 三欄統計數字 ──
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

    # ── 13. 主分隔線 ──
    draw.line([(80, 940), (width - 80, 940)], fill=(225, 215, 205, 255), width=2)

    # ── 14. 結語 CTA ──
    cta_text = "交給電腦選就好，省下的時間多陪陪家人吧。"
    cta_font = _fit_font(draw, cta_text, width - 120, 38, min_size=28, bold=True)
    _dc(964, cta_text, cta_font, (153, 27, 27, 255))

    # ── 15. Footer 品牌文字 ──
    brand_font = _load_font(30, bold=True)
    foot_font = _load_font(26)
    _dc(footer_top + 30, "爸爸的樂透實驗 · 用資料破除明牌迷思", brand_font, gold)
    _dc(footer_top + 80, "分享給身邊的親朋好友，別再花冤枉錢買明牌了", foot_font, (200, 195, 185, 255))

    image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_bonus_card(numbers: list[int], result: "CustomBacktest", game: GameDef) -> bytes:
    """產生包牌（第二區全包）版本分享小卡，1080×1200，帶圓角卡片框與票根齒口。"""
    width, height = _SHARE_CARD_WIDTH, _SHARE_CARD_HEIGHT

    bg_color = (228, 224, 216, 255)
    image = Image.new("RGBA", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    cx = width // 2
    cm = 22
    card_r = 36
    header_h = cm + 246   # = 268
    footer_top = 1020
    gold = (248, 199, 74, 255)

    def _dc(y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, int, int, int]) -> None:
        tw, _, _ = _text_size(draw, text, font)
        draw.text((cx - tw // 2, y), text, font=font, fill=fill)

    # ── 1. 卡片落陰影 ──
    draw.rounded_rectangle(
        [(cm + 5, cm + 8), (width - cm + 5, height - cm + 8)],
        radius=card_r,
        fill=(60, 48, 36, 65),
    )

    # ── 2. 卡片本體 ──
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, height - cm)],
        radius=card_r,
        fill=(255, 252, 245, 255),
    )

    # ── 3. 頂部深藍 Header（上圓角、下平）──
    header_color = (30, 58, 138, 255)
    draw.rounded_rectangle(
        [(cm, cm), (width - cm, header_h)],
        radius=card_r,
        fill=header_color,
    )
    draw.rectangle(
        [(cm, header_h - card_r), (width - cm, header_h)],
        fill=header_color,
    )

    # ── 4. 金色分隔線 ──
    draw.rectangle([(cm, header_h), (width - cm, header_h + 5)], fill=gold)

    # ── 5. 票根齒口 ──
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

    # ── 6. Footer（上平、下圓角）──
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

    # ── 7. Header 文字 ──
    title_font = _load_font(78, bold=True)
    sub_font = _load_font(34)
    tag_font = _load_font(28)
    tw, _, _ = _text_size(draw, "爸爸的樂透實驗", title_font)
    _draw_shadowed_text(
        draw, (cx - tw // 2, cm + 30), "爸爸的樂透實驗", title_font,
        (255, 255, 255, 255), shadow_fill=(0, 20, 80, 150), shadow_offset=(4, 4),
    )
    _dc(cm + 140, f"{game.name} · 包第二區全包 · {result.periods:,} 期回測", sub_font, gold)
    _dc(cm + 192, "每期花 8 倍本金全包第二區，到底賺還是賠？", tag_font, (200, 220, 255, 255))

    # ── 8. 號碼球 ──
    ball_size = 100
    gap = 16
    total_w = len(numbers) * ball_size + (len(numbers) - 1) * gap
    start_x = (width - total_w) // 2
    ball_y = 292
    ball_font = _load_font(50, bold=True)
    for i, num in enumerate(numbers):
        bx = start_x + i * (ball_size + gap)
        _draw_number_ball(draw, bx, ball_y, num, ball_size, ball_font)

    # 「＋第二區 1–8 全包」標籤
    label_font = _load_font(32, bold=True)
    _dc(398, "＋ 第二區 1 ～ 8  全包", label_font, (30, 58, 138, 255))

    # ── 9. 敘事文字 ──
    narrative_font = _load_font(36)
    cost_per = TICKET_COST[game.code] * game.bonus_pool
    _dc(438, f"每期花 {format_money(cost_per)} 全包，{result.periods:,} 期下來⋯", narrative_font, (80, 75, 70, 255))

    # ── 10. 虧損金額框 ──
    money_text = format_money(result.net)
    money_font = _fit_font(draw, money_text, width - 240, 120, min_size=72, bold=True)
    _draw_money_box(
        draw,
        cx=cx,
        y=498,
        text=money_text,
        font=money_font,
        box_fill=(235, 240, 255, 255),
        text_fill=(30, 58, 138, 255),
    )

    # ── 11. 具象化損失 ──
    abs_loss = abs(result.net)
    tangible_font = _load_font(34, bold=True)
    if abs_loss > 0:
        dinners = abs_loss // 300
        trips = abs_loss // 15000
        lines: list[str] = []
        if dinners >= 1:
            lines.append(f"・這些錢能請全家吃 {dinners:,} 頓好料")
        if trips >= 1:
            lines.append(f"・能帶爸媽出去玩 {trips:,} 趟國內旅行")
        for i, line in enumerate(lines[:2]):
            _dc(705 + i * 52, line, tangible_font, (180, 100, 20, 255))

    # ── 12. 三欄統計數字 ──
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

    # ── 13. 主分隔線 ──
    draw.line([(80, 940), (width - 80, 940)], fill=(225, 215, 205, 255), width=2)

    # ── 14. 結語 CTA ──
    cta_text = "包牌不是秘訣，只是賠更多的方法。"
    cta_font = _fit_font(draw, cta_text, width - 120, 38, min_size=28, bold=True)
    _dc(964, cta_text, cta_font, (30, 58, 138, 255))

    # ── 15. Footer 品牌文字 ──
    brand_font = _load_font(30, bold=True)
    foot_font = _load_font(26)
    _dc(footer_top + 30, "爸爸的樂透實驗 · 用資料破除明牌迷思", brand_font, gold)
    _dc(footer_top + 80, "分享給身邊的親朋好友，別再花冤枉錢買明牌了", foot_font, (200, 195, 185, 255))

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
    bottom = (min_value // 10_000) * 10_000
    if bottom > min_value:
        bottom -= 10_000
    tick_values = list(range(bottom, max_value + 1, 10_000))
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
    show_strategy = st.toggle("看各種選法最後賺賠", value=False, key=toggle_key)
    if not show_strategy:
        return

    st.markdown(
        """
        <div class="section-card">
          <div class="section-eyebrow">進階</div>
          <div class="section-title">各種選法最後賺賠</div>
          <p class="section-copy">
            四種代表方法 + 電腦選號各跑一次，看最後賠多少。<br/>
            紅條越長代表賠越多，沒有紅條才是真的贏。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    min_history = min(100, max(30, total_periods // 10))
    loading_slot = st.empty()
    loading_slot.markdown(
        '<div class="loading-card">'
        '<div class="loading-title">正在整理各派最後結果⋯</div>'
        '<div class="loading-balls">'
        '<span class="loading-ball">比</span>'
        '<span class="loading-ball">對</span>'
        '<span class="loading-ball">中</span>'
        '</div>'
        '<div class="loading-subtitle">每一派各跑一千多期，稍等幾秒</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    summary_df = run_strategy_battle_cached(
        game.code,
        data_path,
        data_mtime,
        min_history,
        cache_version=3,
    )
    loading_slot.empty()

    group_summary = build_group_summary(summary_df)
    render_strategy_loss_list(group_summary)

    best_row = summary_df.loc[summary_df["總損益"].idxmax()]
    worst_row = summary_df.loc[summary_df["總損益"].idxmin()]
    st.markdown(
        f"""
        <div class="strategy-note">
          這幾種裡面，最好的是「{best_row['派別']}」：{format_money(int(best_row['總損益']))}。<br/>
          最差的是「{worst_row['派別']}」：{format_money(int(worst_row['總損益']))}。
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="verdict-card">
          看出來了嗎？<br/>不管用哪一種派別，最後都沒有辦法穩定賺錢。<br/>
          這就是隨機的現實：<br/>坊間傳說滿天飛，但中獎機率是不聽故事的。
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
    cache_version: int = 3,
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
        """
        **怎麼算：** 每一期開獎前，先把答案蓋住，
        只用前面的資料選號，再對答案。每一期都照同樣規則重跑。

        這樣可以避免開獎後才說「早知道應該買這組」的事後解釋。
        """
    )


def render_footer_warning() -> None:
    st.markdown(
        """
        <div class="warning-line">
          買彩券是一種樂趣，但千萬別迷信明牌，<br/>
          因為開獎號碼說到底就只是機率而已。<br/>
          <span style="font-size:.9em; opacity:.85;">把買明牌的錢省下來，帶家人去吃頓好料的吧！</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()