"""Lotry Streamlit app: a data confession for lottery myths."""

from __future__ import annotations

import datetime as dt
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


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
        page_title="爸爸的樂透實驗｜電腦選號就好，剩下的是愛",
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
        }
        .stApp {
            background:
                linear-gradient(180deg, #fff7ed 0%, #ffffff 38%, #eef2ff 100%);
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 760px;
        }
        #MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
        header { visibility: hidden; height: 0; }
        html, body, [class*="css"], .stApp, button, input, textarea, select {
            font-family: "Microsoft JhengHei", "Noto Sans TC", "PingFang TC", Arial, sans-serif !important;
            font-size: 17px;
            letter-spacing: 0;
        }
        .hero {
            position: relative;
            overflow: hidden;
            padding: 1.6rem 1.5rem 1.8rem;
            background: linear-gradient(135deg, #7f1d1d 0%, #b91c1c 54%, #f59e0b 130%);
            border-radius: 8px;
            margin-bottom: 1.2rem;
            color: white;
            box-shadow: 0 24px 70px rgba(127,29,29,.25);
        }
        .hero-kicker { font-size: .82rem; font-weight: 800; opacity: .86; margin-bottom: .5rem; letter-spacing: .04em; }
        .hero h1 { margin: 0 0 .75rem 0; letter-spacing: 0; font-size: clamp(1.7rem, 6vw, 3rem); line-height: 1.18; }
        .hero p { font-size: 1.05rem; line-height: 1.85; margin: 0; }
        .hero strong { color: #fff2b8; }
        .hero-balls { display: flex; gap: .55rem; margin-top: 1.35rem; flex-wrap: wrap; }
        .mini-ball {
            width: 2.55rem;
            height: 2.55rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #7f1d1d;
            font-weight: 900;
            background: radial-gradient(circle at 32% 28%, #ffffff 0 18%, #ffe08a 20% 62%, #f59e0b 100%);
            box-shadow: inset -8px -8px 14px rgba(127,29,29,.18), 0 9px 18px rgba(0,0,0,.18);
        }
        .section-card {
            padding: 1.25rem;
            border: 1px solid rgba(148,163,184,.28);
            border-radius: 8px;
            background: rgba(255,255,255,.82);
            box-shadow: 0 14px 38px rgba(15,23,42,.07);
            margin: 1rem 0 1.25rem;
        }
        .step-label {
            color: var(--lotry-ink);
            font-size: 1.32rem;
            font-weight: 900;
            margin: 1.1rem 0 .35rem;
        }
        .section-eyebrow { color: var(--lotry-red-dark); font-weight: 900; font-size: .88rem; margin-bottom: .25rem; }
        .section-title { color: var(--lotry-ink); font-size: 1.5rem; font-weight: 900; margin: 0 0 .35rem; }
        .section-copy { color: var(--lotry-muted); line-height: 1.75; margin: 0; font-size: 1rem; }
        div[data-testid="stSidebar"] { background: #fff7ed; }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid rgba(148,163,184,.28);
            border-radius: 8px;
            padding: .9rem 1rem;
            box-shadow: 0 10px 28px rgba(15,23,42,.05);
            text-align: center;
        }
        div[data-testid="stMetric"] label { font-size: .92rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.45rem !important; }
        .selected-strip {
            display: flex;
            align-items: center;
            gap: .6rem;
            flex-wrap: wrap;
            justify-content: center;
            min-height: 3.6rem;
            padding: .8rem .95rem;
            border-radius: 8px;
            background: #fff7ed;
            border: 1px dashed rgba(185,28,28,.35);
            margin: .4rem 0 .9rem;
        }
        .selected-label { color: #7f1d1d; font-weight: 900; margin-right: .25rem; font-size: 1rem; }
        .lottery-ball {
            width: 2.7rem;
            height: 2.7rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at 32% 25%, #ffffff 0 16%, #fee2e2 18% 48%, #dc2626 100%);
            color: #7f1d1d;
            font-weight: 900;
            font-size: 1rem;
            box-shadow: inset -7px -7px 13px rgba(127,29,29,.26), 0 8px 16px rgba(185,28,28,.18);
        }
        div.stButton > button {
            border-radius: 999px;
            min-height: 3rem;
            padding: 0 1rem;
            font-weight: 900;
            font-size: 1.02rem;
            border: 1px solid rgba(185,28,28,.28);
            box-shadow: 0 8px 18px rgba(15,23,42,.06);
        }
        div.stButton > button[kind="primary"] {
            background: radial-gradient(circle at 32% 24%, #ffffff 0 14%, #fecaca 17% 48%, #dc2626 100%);
            color: #7f1d1d;
            border-color: #dc2626;
        }
        .ball-row div[data-testid="column"] { padding: 2px !important; }
        div[class*="st-key-ball_"] {
            display: flex;
            justify-content: center;
        }
        div[class*="st-key-ball_"] div.stButton {
            width: 3.08rem !important;
            height: 3.08rem !important;
        }
        div[class*="st-key-ball_"] div.stButton > button {
            width: 3.08rem !important;
            height: 3.08rem !important;
            min-height: 3.08rem !important;
            padding: 0 !important;
            border-radius: 50% !important;
        }
        div[class*="st-key-ball_"] div.stButton p { margin: 0 !important; }
        .ball-row div.stButton > button {
            min-height: 3rem;
            min-width: 0;
            padding: 0;
            font-size: 1.05rem;
            border-radius: 50%;
            aspect-ratio: 1 / 1;
            background: radial-gradient(circle at 32% 24%, #ffffff 0 15%, #fff7ed 18% 50%, #f5d7bd 100%);
            color: #7f1d1d;
            border-color: rgba(185,28,28,.28);
        }
        .ball-row div.stButton > button[kind="primary"] {
            background: radial-gradient(circle at 30% 23%, #ffffff 0 13%, #fecaca 16% 42%, #ef4444 72%, #b91c1c 100%);
            color: #7f1d1d;
            border-color: #ef4444;
            box-shadow: inset -6px -6px 12px rgba(127,29,29,.28), 0 10px 22px rgba(185,28,28,.22);
        }
        .loss-box {
            padding: 1.25rem 1.25rem 1.4rem;
            border-radius: 8px;
            background: linear-gradient(135deg, #fff1f1, #fff7ed);
            border: 1px solid #f2b8b8;
            box-shadow: 0 14px 36px rgba(185,28,28,.11);
            text-align: center;
        }
        .loss-number {
            color: #b91c1c;
            font-size: clamp(2.2rem, 9vw, 3.6rem);
            font-weight: 900;
            line-height: 1.05;
            letter-spacing: -.01em;
        }
        .quiet-note { color: #57534e; font-size: .98rem; line-height: 1.65; }
        .verdict-card {
            padding: 1.1rem 1.2rem;
            border-radius: 8px;
            background: #fff7ed;
            border: 1px solid rgba(185,28,28,.18);
            color: #7f1d1d;
            font-weight: 700;
            line-height: 1.7;
            margin-top: .8rem;
            font-size: 1.02rem;
        }
        .warning-line {
            margin-top: 2rem;
            padding: 1.4rem 1.5rem;
            border-radius: 8px;
            color: #7f1d1d;
            background: linear-gradient(135deg, #fff7ed, #ffffff);
            border: 1px solid rgba(185,28,28,.22);
            font-size: 1.18rem;
            font-weight: 700;
            text-align: center;
            box-shadow: 0 14px 40px rgba(15,23,42,.07);
            line-height: 1.7;
        }
        .loading-card {
            margin: .85rem 0 1rem;
            padding: 1.15rem;
            border-radius: 8px;
            background: #fff7ed;
            border: 1px solid rgba(185,28,28,.18);
            text-align: center;
            box-shadow: 0 12px 30px rgba(15,23,42,.07);
        }
        .loading-title { color: #7f1d1d; font-weight: 900; font-size: 1.16rem; margin-bottom: .65rem; }
        .loading-subtitle { color: #57534e; font-size: .98rem; line-height: 1.55; }
        .loading-balls { display: flex; justify-content: center; gap: .55rem; margin: .8rem 0; }
        .loading-ball {
            width: 2.35rem;
            height: 2.35rem;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #7f1d1d;
            font-weight: 900;
            background: radial-gradient(circle at 32% 25%, #ffffff 0 16%, #fee2e2 18% 48%, #dc2626 100%);
            box-shadow: inset -6px -6px 12px rgba(127,29,29,.26), 0 8px 16px rgba(185,28,28,.18);
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
        .strategy-note {
            padding: 1rem 1.1rem;
            border-radius: 8px;
            background: #eef2ff;
            border: 1px solid rgba(37,99,235,.18);
            color: #1e3a8a;
            font-weight: 800;
            line-height: 1.65;
            margin: .75rem 0 1rem;
        }
        .simple-result-card {
            margin: .85rem 0 1rem;
            padding: 1.1rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid rgba(148,163,184,.28);
            box-shadow: 0 10px 28px rgba(15,23,42,.05);
        }
        .simple-result-title { color: var(--lotry-ink); font-size: 1.18rem; font-weight: 900; margin-bottom: .5rem; }
        .loss-track {
            height: .82rem;
            border-radius: 999px;
            background: linear-gradient(90deg, #fee2e2, #ef4444);
            margin: .9rem 0 .65rem;
        }
        .loss-track-labels {
            display: flex;
            justify-content: space-between;
            gap: .75rem;
            color: #57534e;
            font-size: .95rem;
            font-weight: 800;
        }
        .strategy-list { display: grid; gap: .75rem; margin: .9rem 0 1rem; }
        .strategy-row {
            padding: .95rem 1rem;
            border-radius: 8px;
            background: #ffffff;
            border: 1px solid rgba(148,163,184,.28);
            box-shadow: 0 8px 22px rgba(15,23,42,.05);
        }
        .strategy-row-top {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: .8rem;
            margin-bottom: .55rem;
        }
        .strategy-name { color: var(--lotry-ink); font-weight: 900; }
        .strategy-loss { color: #b91c1c; font-weight: 900; white-space: nowrap; }
        .strategy-desc { color: #57534e; font-size: .92rem; line-height: 1.55; margin: .2rem 0 .55rem; }
        .strategy-bar-bg { height: .72rem; border-radius: 999px; background: #fee2e2; overflow: hidden; }
        .strategy-bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #f87171, #b91c1c); }
        @media (max-width: 640px) {
            .block-container { padding-left: .8rem; padding-right: .8rem; }
            .hero { padding: 1.4rem 1.2rem 1.5rem; }
            div.stButton > button { font-size: .98rem; }
            div[class*="st-key-ball_"] div.stButton,
            div[class*="st-key-ball_"] div.stButton > button { width: 2.8rem !important; height: 2.8rem !important; min-height: 2.8rem !important; }
            .ball-row div.stButton > button { font-size: .98rem; min-height: 2.7rem; }
            .lottery-ball { width: 2.45rem; height: 2.45rem; font-size: .92rem; }
            div[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
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
          <div class="hero-kicker">給爸爸的一個答案</div>
          <h1>爸爸的樂透實驗</h1>
          <p>把明牌放回台灣彩券全部歷史重跑。<strong>電腦選號就好，剩下的是愛。</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner="載入歷史開獎資料...")
def load_draws_cached(game_code: str, data_path: str, data_mtime: float) -> list[dict]:
    del data_mtime
    game = get_game(game_code)
    return load_game_data(game, data_path)


def render_custom_challenge(game: GameDef, draws: list[dict]) -> None:
    quick_loading_slot = st.empty()
    if st.button("電腦幫我選，馬上看結果", type="primary", use_container_width=True):
        numbers = sorted(random_sample(game))
        set_selected_numbers(game, numbers)
        st.session_state[result_key(game)] = (numbers, run_custom_backtest_with_loading(numbers, draws, game, quick_loading_slot))
        st.session_state[f"scroll_{game.code}"] = True

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
                use_container_width=True,
            )
        with action_cols[1]:
            if st.button("清空重選", disabled=not bool(selected), use_container_width=True):
                set_selected_numbers(game, [])
                st.session_state.pop(result_key(game), None)
                st.rerun()
        result_loading_slot = st.empty()
        if not is_complete:
            st.info(f"還差 {game.main_pick - len(selected)} 顆球。")
        elif challenge:
            numbers = sorted(selected)
            st.session_state[result_key(game)] = (numbers, run_custom_backtest_with_loading(numbers, draws, game, result_loading_slot))
            st.session_state[f"scroll_{game.code}"] = True

    saved_result = st.session_state.get(result_key(game))
    if saved_result:
        if st.session_state.pop(f"scroll_{game.code}", False):
            st.components.v1.html(
                "<script>setTimeout(function(){"
                "var target=window.parent.document.getElementById('lotry-result-anchor');"
                "if(target)target.scrollIntoView({behavior:'smooth',block:'start'});"
                "},300);</script>",
                height=0,
            )
        st.markdown('<div id="lotry-result-anchor"></div>', unsafe_allow_html=True)
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
                    use_container_width=True,
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
          <div class="loading-title">正在跑 12 年歷史資料...</div>
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
    st.markdown(
        f"""
        <div class="loss-box">
          <div class="quiet-note">這 {result.periods:,} 期每期都買一次，到今天的結果</div>
          <div class="loss-number">{format_money(result.net)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_cols = st.columns(3)
    metric_cols[0].metric("總共花了", format_money(result.total_cost))
    metric_cols[1].metric("總共領回", format_money(result.total_prize))
    metric_cols[2].metric("頭獎中過", f"{result.exact_hits} 次")

    expected_avg = game.main_pick * game.main_pick / game.main_pool
    diff = result.avg_hits - expected_avg
    direction = "幾乎一樣" if abs(diff) < 0.05 else ("略多一點點" if diff > 0 else "略少一點點")
    st.markdown(
        f"""
        <div class="verdict-card">
          這組明牌平均每期中 <b>{result.avg_hits:.3f}</b> 個號碼，
          純粹亂選平均大約是 <b>{expected_avg:.3f}</b>。
          差距是{direction}，<u>沒有改變最後賠錢的結果</u>。
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
          <div class="simple-result-title">一句話：這組號碼沒有把機率變好</div>
          <div class="quiet-note">從第一期買到現在，錢一路慢慢變少。</div>
          <div class="loss-track"></div>
          <div class="loss-track-labels"><span>開始：NT$ 0</span><span>現在：{format_money(result.net)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("想看累計走勢圖（可跳過）"):
        st.plotly_chart(curve, use_container_width=True, config={"displayModeBar": False})
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
            很多人說：「我每一期把特別號全包，就一定中。」
            按下面看看實際會賠多少錢。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.session_state.get(selected_key(game)) or []
    if len(selected) != game.main_pick:
        st.caption("先在上面選滿 6 顆主區號碼，這個試算才知道你的明牌是哪組。")
        return

    if st.button("包第二區（1–8 全買）試算", use_container_width=True):
        st.session_state[bonus_wheel_key(game)] = (
            sorted(selected),
            run_bonus_wheel_backtest(sorted(selected), draws, game),
        )

    saved = st.session_state.get(bonus_wheel_key(game))
    if saved and saved[0] == sorted(selected):
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
                        這 {result.periods:,} 期，每期都花 {format_money(cost_per_period)} 包整個第二區，
            雖然「每期都中第二區普獎 100 元」，但結果是
          </div>
          <div class="loss-number">{format_money(result.net)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_cols = st.columns(3)
    metric_cols[0].metric("總共花了", format_money(result.total_cost))
    metric_cols[1].metric("總共領回", format_money(result.total_prize))
    metric_cols[2].metric("頭獎中過", f"{result.exact_hits} 次")
    st.markdown(
        """
        <div class="verdict-card">
          <b>包第二區一定中，但一張中 100 元、其他 7 張零元，扣掉成本還是賠錢。</b>
          想用「保證中獎」翻盤的直覺，數學上不會成立。
        </div>
        """,
        unsafe_allow_html=True,
    )


def prize_for_hits(game: GameDef, main_hits: int, bonus_hits: int = 0) -> int:
    table = PRIZE_TABLE.get(game.code, {})
    return table.get((main_hits, bonus_hits), 0)


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

    st.markdown('<div id="strategy-result-anchor"></div>', unsafe_allow_html=True)
    st.components.v1.html(
        "<script>setTimeout(function(){"
        "var target=window.parent.document.getElementById('strategy-result-anchor');"
        "if(target)target.scrollIntoView({behavior:'smooth',block:'start'});"
        "},150);</script>",
        height=0,
    )

    st.markdown(
        """
        <div class="section-card">
          <div class="section-eyebrow">進階</div>
          <div class="section-title">各種選法最後賺賠</div>
          <p class="section-copy">
            四種代表方法 + 電腦選號各跑一次，看最後賠多少。
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
          重點不是哪條線漂亮，而是每種方法最後都沒有穩定變成正收益。
          這就是隨機：故事很多，機率不會因為故事改變。
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
          人很會替隨機找故事，<br/>但故事不會改變機率。
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()