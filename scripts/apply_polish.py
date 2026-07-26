from __future__ import annotations

import re
import textwrap
from pathlib import Path

APP_PATH = Path("streamlit_app.py")


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def build_style() -> str:
    css = r"""
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
    font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif !important;
    font-size: 16px;
    letter-spacing: .01em;
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
    text-transform: uppercase;
}
.hero h1 {
    max-width: 650px;
    margin: 0 0 .9rem;
    color: #fff;
    font-size: clamp(2.15rem, 7vw, 3.5rem);
    font-weight: 850;
    line-height: 1.15;
    letter-spacing: -.035em;
}
.hero p {
    max-width: 650px;
    margin: 0;
    color: rgba(255, 255, 255, .84);
    font-size: 1.04rem;
    font-weight: 450;
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
    text-transform: uppercase;
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
    font-weight: 450;
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
    font-weight: 850;
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
    font-weight: 650;
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
.loading-title { margin-bottom: .55rem; color: var(--lotry-ink); font-size: 1.05rem; font-weight: 750; }
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
    font-weight: 750;
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
.share-cta-title { margin-bottom: .35rem; color: #ecd5a8; font-size: 1.12rem; font-weight: 750; }
.share-cta-body { color: rgba(255, 255, 255, .76); font-size: .94rem; font-weight: 450; line-height: 1.7; }
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
.strategy-name { color: var(--lotry-ink); font-size: 1rem; font-weight: 750; }
.strategy-loss { color: var(--lotry-accent-dark); font-size: .94rem; font-weight: 750; white-space: nowrap; }
.strategy-desc { margin: 0 0 .6rem; color: var(--lotry-muted); font-size: .88rem; font-weight: 450; line-height: 1.55; }
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
"""
    return textwrap.indent(textwrap.dedent(css).strip(), "        ")


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")

    style_pattern = re.compile(r"        <style>\n.*?\n        </style>", re.DOTALL)
    text, count = style_pattern.subn(build_style(), text, count=1)
    if count != 1:
        raise RuntimeError(f"style block: expected one match, found {count}")

    replacements = [
        (
            'page_title="爸爸的樂透實驗｜電腦選號就好，省下的時間多陪陪家人吧"',
            'page_title="爸爸的樂透實驗｜用歷史資料檢驗選號方法"',
            "page title",
        ),
        ('<div class="step-label">1. 先選遊戲</div>', '<div class="step-label">選擇彩種</div>', "game heading"),
        ('st.caption(f"使用 {game.name} 全部資料，共 {len(draws):,} 期。")', 'st.caption(f"目前載入 {game.name} 歷史資料，共 {len(draws):,} 期。")', "draw caption"),
        ('with st.expander("想知道怎麼算？（可跳過）", expanded=st.session_state.get(strategy_toggle_key, False)):', 'with st.expander("方法與策略比較", expanded=st.session_state.get(strategy_toggle_key, False)):', "method expander"),
        (
            '''        <div class="hero">
          <div class="hero-kicker">給長輩的真心話</div>
          <h1>爸爸的樂透實驗</h1>
          <p>我們把台灣人常用的那些算牌法，全部拿去對過十幾年來的開獎紀錄。<br/><strong>說句老實話：交給電腦選號就好，省下算牌的時間，多陪陪家人吧！</strong></p>
        </div>''',
            '''        <div class="hero">
          <div class="hero-kicker">A DATA EXPERIMENT ABOUT LOTTERY MYTHS</div>
          <h1>爸爸的樂透實驗</h1>
          <p>把冷熱號、農民曆、新聞事件與其他常見選號方法，放進十多年的歷史資料裡逐期驗證。<br/><strong>結果沒有明牌，只有一個可以重複檢查的答案：長期表現都接近隨機。</strong></p>
          <div class="hero-meta"><span>27 種策略</span><span>大樂透／威力彩</span><span>Walk-forward 回測</span></div>
        </div>''',
            "hero copy",
        ),
        ('if st.button("電腦幫我選，馬上看結果", type="primary", width="stretch"):', 'if st.button("隨機選一組並回測", type="primary", width="stretch"):', "random cta"),
        ('with st.expander("我要自己挑號碼（可跳過）"):', 'with st.expander("自己選號"):', "manual expander"),
        ('st.caption(f"從 1 到 {game.main_pool} 任選 {game.main_pick} 顆球，選滿後按「看我的結果」。")', 'st.caption(f"從 1 到 {game.main_pool} 選擇 {game.main_pick} 個號碼，再執行歷史回測。")', "picker caption"),
        ('"看我的結果",', '"開始回測",', "manual cta"),
        ('st.info(f"還差 {game.main_pick - len(selected)} 顆球。")', 'st.info(f"還需要選擇 {game.main_pick - len(selected)} 個號碼。")', "remaining info"),
        ('<div class="loading-title">正在對這十幾年來的答案…</div>', '<div class="loading-title">正在執行歷史回測</div>', "loading title"),
        ('<div class="loading-subtitle">電腦正在把這組號碼每一期都對過一遍，馬上就好。</div>', '<div class="loading-subtitle">逐期比對開獎結果、估算獎金與累計損益。</div>', "loading subtitle"),
        ('st.markdown(\'<div class="step-label">3. 看結果</div>\', unsafe_allow_html=True)', 'st.markdown(\'<div class="step-label">回測結果</div>\', unsafe_allow_html=True)', "result heading"),
        ('<span class="selected-label">你的明牌</span>', '<span class="selected-label">選擇的號碼</span>', "selected label"),
        ('<div class="quiet-note">要是這 {result.periods:,} 期你每一期都照著買，<br/>算到今天，你的錢會變成…</div>', '<div class="quiet-note">將這組號碼套用到過去 {result.periods:,} 期，並假設每期購買一注，累計損益為</div>', "result lead"),
        (
            '''    if abs_amount > 0:
        dinners = abs_amount // 300
        trips = abs_amount // 15000
        tangible_parts = []
        if dinners >= 1:
            tangible_parts.append(f'<span class="emoji">🍲</span> 全家吃 <b>{dinners:,}</b> 頓好料')
        if trips >= 1:
            tangible_parts.append(f'<span class="emoji">✈️</span> 帶爸媽去 <b>{trips:,}</b> 趟國內旅行')
        if tangible_parts:
            lead = "這筆錢相當於⋯" if is_profit else "這些錢本來可以⋯"
            st.markdown(
                '<div class="tangible-loss">'
                + lead + '<br/>'
                + '<br/>'.join(tangible_parts)
                + '</div>',
                unsafe_allow_html=True,
            )''',
            '''    if abs_amount > 0:
        st.markdown(
            f'<div class="tangible-loss">損益絕對值為 <b>{format_money(abs_amount)}</b>。此數字用來呈現歷史回測的金額規模，不代表未來結果。</div>',
            unsafe_allow_html=True,
        )''',
            "tangible comparison",
        ),
        ('st.caption(f"📒 算法說明：{jackpot_note} 春節加碼、大紅包不納入計算。{odds_text}")', 'st.caption(f"獎金估算：{jackpot_note} 春節加碼與大紅包未納入。{odds_text}")', "assumption caption"),
        ('direction = "幾乎一樣" if abs(diff) < 0.05 else ("好一點點而已" if diff > 0 else "還比較差一點")', 'direction = "接近隨機期望" if abs(diff) < 0.05 else ("略高於隨機期望" if diff > 0 else "略低於隨機期望")', "direction copy"),
        (
            '''            <div class="verdict-card">
              ⚠️ <b>先別太高興。</b><br/>
              {luck_line}<br/>
              中頭獎的機率是 {jackpot_pct(odds)}，下一期一樣從零開始。<br/>
              你換組號碼或換個年份試試看就知道，大部分的結果都是賠錢收場。
            </div>''',
            '''            <div class="verdict-card">
              <b>這次回測出現正報酬，不代表這組號碼具有預測能力。</b><br/>
              {luck_line}<br/>
              頭獎機率約為 {jackpot_pct(odds)}；每一期仍是獨立事件。更換號碼或回測區間後，結果通常會明顯改變。
            </div>''',
            "profit verdict",
        ),
        (
            '''            <div class="verdict-card">
              算下來，這組號碼平均每一期才中 <b>{result.avg_hits:.3f}</b> 顆球，<br/>
              跟閉著眼睛讓電腦選（<b>{expected_avg:.3f}</b> 顆）其實差不多啦！<br/>
              兩邊比起來{direction}。<br/><u>但最現實的是：管你用哪種方法，買到最後都是賠錢。</u>
            </div>''',
            '''            <div class="verdict-card">
              這組號碼平均每期命中 <b>{result.avg_hits:.3f}</b> 個主區號碼；隨機選號的理論期望約為 <b>{expected_avg:.3f}</b>。<br/>
              本次結果{direction}。<br/><u>差距不足以證明這組號碼具有可重現的優勢。</u>
            </div>''',
            "loss verdict",
        ),
        ('name="你的明牌累計損益",', 'name="所選號碼累計損益",', "chart name"),
        ('<div class="simple-result-title">帳面好看，是因為那幾次大獎撐起來的</div>', '<div class="simple-result-title">正報酬主要來自少數高額獎項</div>', "profit card title"),
        ('<div class="quiet-note">拿掉那幾次中獎，其他期加起來一樣是越買越少。<br/>\n                平均每期只中 <b>{result.avg_hits:.3f}</b> 顆球，跟電腦亂選的 <b>{expected_avg:.3f}</b> 顆差不多啦！</div>', '<div class="quiet-note">累計結果對少數高額獎項非常敏感。平均每期命中 <b>{result.avg_hits:.3f}</b> 個主區號碼，接近隨機選號的 <b>{expected_avg:.3f}</b>。</div>', "profit card copy"),
        ('<div class="simple-result-title">說句真心話：這組號碼沒有比較容易中</div>', '<div class="simple-result-title">沒有觀察到高於隨機的穩定優勢</div>', "loss card title"),
        ('<div class="quiet-note">要是每一期都傻傻跟著買，<br/>辛苦錢只會一點一滴變少而已。</div>', '<div class="quiet-note">在這段歷史資料中，固定購買同一組號碼的累計報酬為負。</div>', "loss card copy"),
        (
            '''        <div class="share-cta">
          <div class="share-cta-title">把結果傳給親朋好友</div>
          <div class="share-cta-body">
            存成一張圖片，傳到賴（LINE）的家庭群組或是臉書。<br/>
            提醒身邊的人，世界上真的沒有穩中的明牌。
          </div>
        </div>''',
            '''        <div class="share-cta">
          <div class="share-cta-title">匯出這次回測</div>
          <div class="share-cta-body">
            可將號碼、期間、成本與損益整理成圖片，方便保存或分享。小卡呈現的是歷史模擬，不是未來預測。
          </div>
        </div>''',
            "share section",
        ),
        ('if st.button("📸 生成分享小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):', 'if st.button("產生回測小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):', "share card button"),
        ('label="💾 下載圖片",', 'label="下載圖片",', "download label"),
        ('target="_blank" rel="noopener noreferrer">💬 分享到 LINE</a>', 'target="_blank" rel="noopener noreferrer">分享到 LINE</a>', "line label"),
        ('st.caption("💡 長按圖片也可以直接分享給其他 App")', 'st.caption("手機可長按圖片儲存或分享。")', "image hint"),
        ('with st.expander("想看累計走勢圖（可跳過）"):', 'with st.expander("查看累計損益走勢"):', "chart expander"),
        (
            '''        <div class="section-card">
          <div class="section-eyebrow">加碼試算</div>
          <div class="section-title">如果「包牌」只包特別號呢？</div>
          <p class="section-copy">
            常聽人說：「第二區全包就穩中啦！」<br/>
            真的嗎？點下去看看實際上會賠多少。
          </p>
        </div>''',
            '''        <div class="section-card">
          <div class="section-eyebrow">威力彩情境試算</div>
          <div class="section-title">第二區 1–8 全包的長期結果</div>
          <p class="section-copy">
            第二區全包可以提高中小獎的頻率，但每期成本也會變成八倍。這裡使用相同主區號碼，回測完整歷史資料。
          </p>
        </div>''',
            "bonus intro",
        ),
        ('st.caption("先在上面選滿 6 顆主區號碼，這個試算才知道你的明牌是哪組。")', 'st.caption("請先在上方選滿 6 個主區號碼。")', "bonus caption"),
        ('if st.button("包第二區（1–8 全買）試算", width="stretch"):', 'if st.button("回測第二區全包", width="stretch"):', "bonus cta"),
        ('<span class="selected-label">主區明牌</span>', '<span class="selected-label">主區號碼</span>', "bonus selected label"),
        ('<span class="selected-label" style="margin-left:12px;">＋第二區 1–8 全包</span>', '<span class="selected-label" style="margin-left:12px;">第二區 1–8 全包</span>', "bonus suffix"),
        ('每期花 {format_money(cost_per_period)} 全包第二區，<br/>\n                帳面上竟然是正的…', '每期投入 {format_money(cost_per_period)} 購買八注，<br/>\n                歷史回測的累計損益為', "bonus profit lead"),
        ('每期都花 {format_money(cost_per_period)} 霸氣全包第二區，<br/>\n                雖然號稱「每期保證中普獎 100 元」，<br/>但其實…', '每期投入 {format_money(cost_per_period)} 購買八注，<br/>\n                歷史回測的累計損益為', "bonus loss lead"),
        ('st.caption(f"📒 算法說明：{jackpot_assumption_text(game)} 春節加碼、大紅包不納入計算。")', 'st.caption(f"獎金估算：{jackpot_assumption_text(game)} 春節加碼與大紅包未納入。")', "bonus assumption"),
        (
            '''            <div class="verdict-card">
              ⚠️ <b>全包能賺，是因為這 {result.periods:,} 期裡剛好有抽到大獎。</b><br/>
              其他 7 張都是陪跑的，沒中大獎的時候只能拿 100 元普獎。<br/>
              拉長 12 年來看，絕大多數情況是賠的。
            </div>''',
            '''            <div class="verdict-card">
              <b>本次正報酬主要由少數高額獎項造成。</b><br/>
              第二區全包會固定增加七張未中特別號的投注；若沒有高額獎項，額外成本通常會高於小獎收入。
            </div>''',
            "bonus profit verdict",
        ),
        (
            '''            <div class="verdict-card">
              <b>全包確實保證中獎，<br/>但中一張 100 元，代表其他 7 張都是做白工，<br/>扣掉本金照樣賠。</b><br/>
              以為靠「穩中」就能賺錢？這算盤恐怕打錯囉。
            </div>''',
            '''            <div class="verdict-card">
              <b>提高中獎頻率，不等於提高報酬率。</b><br/>
              第二區全包能確保其中一注命中特別號，但其餘七注仍要支付成本；在這段歷史資料中，累計報酬仍為負。
            </div>''',
            "bonus loss verdict",
        ),
        (
            '''        <div class="share-cta">
          <div class="share-cta-title">把結果傳給親朋好友</div>
          <div class="share-cta-body">
            把「全包也在賠」的真相存成一張圖，<br/>
            傳給那些說「包牌穩中」的長輩或朋友看看！
          </div>
        </div>''',
            '''        <div class="share-cta">
          <div class="share-cta-title">匯出全包情境</div>
          <div class="share-cta-body">
            將主區號碼、八倍成本與歷史損益整理成圖片，方便比較「中獎頻率」與「實際報酬」的差別。
          </div>
        </div>''',
            "bonus share section",
        ),
        ('if st.button("📸 生成包牌分享小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):', 'if st.button("產生全包回測小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):', "bonus card button"),
        ('st.caption("💡 長按圖片也可以直接儲存，或分享給其他 App")', 'st.caption("手機可長按圖片儲存或分享。")', "bonus image hint"),
        ('_SHARE_CARD_VERSION = 5', '_SHARE_CARD_VERSION = 6', "card version"),
        ('tagline = "帳面好看，靠的是那幾次大獎撐出來的" if is_profit_card else "每一期都照著買，買到現在的真實結果"', 'tagline = "正報酬來自少數高額獎項" if is_profit_card else "固定購買同一組號碼的歷史結果"', "card tagline"),
        ('_dc(410, f"這 {result.periods:,} 期下來帳面是正的", narrative_font, (80, 75, 70, 255))\n        _dc(454, "但拿掉那幾次大獎，其實一樣在賠", narrative_font, (80, 75, 70, 255))', '_dc(410, f"套用過去 {result.periods:,} 期開獎資料", narrative_font, (80, 75, 70, 255))\n        _dc(454, "少數高額獎項使累計結果轉為正值", narrative_font, (80, 75, 70, 255))', "card profit narrative"),
        ('_dc(410, f"要是這 {result.periods:,} 期每一期都照著買", narrative_font, (80, 75, 70, 255))\n        _dc(454, "算到今天你的錢會變成⋯", narrative_font, (80, 75, 70, 255))', '_dc(410, f"套用過去 {result.periods:,} 期開獎資料", narrative_font, (80, 75, 70, 255))\n        _dc(454, "假設每期固定購買一注", narrative_font, (80, 75, 70, 255))', "card loss narrative"),
        (
            '''    abs_amount = abs(result.net)
    tangible_font = _load_font(34, bold=True)
    if abs_amount > 0:
        dinners = abs_amount // 300
        trips = abs_amount // 15000
        lines: list[str] = []
        prefix = "・這筆錢相當於" if is_profit_card else "・這些錢能"
        if dinners >= 1:
            lines.append(f"{prefix}替家裡加菜 {dinners:,} 次")
        if trips >= 1:
            lines.append(f"{prefix}帶爸媽出去玩 {trips:,} 趟國內旅行")
        for i, line in enumerate(lines[:2]):
            _dc(705 + i * 52, line, tangible_font, (180, 100, 20, 255))''',
            '''    magnitude_font = _load_font(32, bold=True)
    _dc(718, f"損益絕對值：{format_money(abs(result.net))}", magnitude_font, (120, 90, 55, 255))
    _dc(766, "歷史模擬結果，不代表下一期表現", _load_font(28), (120, 115, 110, 255))''',
            "card amount context",
        ),
        ('cta_text = f"中頭獎機率 {jackpot_pct(jackpot_odds(game))}，別把好運當實力。"', 'cta_text = f"頭獎機率約 {jackpot_pct(jackpot_odds(game))}；每一期仍是獨立事件。"', "card profit cta"),
        ('cta_text = "交給電腦選就好，省下的時間多陪陪家人吧。"', 'cta_text = "沒有觀察到可重現、能勝過隨機的選號優勢。"', "card loss cta"),
        ('_dc(footer_top + 30, "爸爸的樂透實驗 · 用資料破除明牌迷思", brand_font, gold)', '_dc(footer_top + 30, "爸爸的樂透實驗 · 歷史資料回測", brand_font, gold)', "card footer brand"),
        ('_dc(footer_top + 80, "傳給身邊的親朋好友，別再花冤枉錢買明牌了", foot_font, (200, 195, 185, 255))', '_dc(footer_top + 80, "這是歷史模擬，不是未來預測或投注建議", foot_font, (200, 195, 185, 255))', "card footer disclaimer"),
        ('tag_text = "帳面能正，全靠那幾次大獎撐起來的" if is_profit_card else "每期花 8 倍本金全包第二區，到底賺還是賠？"', 'tag_text = "正報酬主要由少數高額獎項造成" if is_profit_card else "第二區全包的成本與報酬比較"', "bonus card tag"),
        ('_dc(438, f"每期花 {format_money(cost_per)} 全包，帳面上竟然是正的⋯", narrative_font, (80, 75, 70, 255))', '_dc(438, f"每期投入 {format_money(cost_per)} 購買八注，歷史結果為", narrative_font, (80, 75, 70, 255))', "bonus card profit narrative"),
        ('_dc(438, f"每期花 {format_money(cost_per)} 全包，{result.periods:,} 期下來⋯", narrative_font, (80, 75, 70, 255))', '_dc(438, f"每期投入 {format_money(cost_per)} 購買八注，{result.periods:,} 期結果為", narrative_font, (80, 75, 70, 255))', "bonus card loss narrative"),
        ('cta_text = "全包能賺，全靠運氣抽中大獎而已。"', 'cta_text = "本次正報酬主要由少數高額獎項造成。"', "bonus card profit cta"),
        ('cta_text = "包牌不是秘訣，只是賠更多的方法。"', 'cta_text = "提高中獎頻率，不等於提高長期報酬率。"', "bonus card loss cta"),
        ('show_strategy = st.toggle("看各種選法最後賺賠", value=False, key=toggle_key)', 'show_strategy = st.toggle("執行代表策略比較", value=False, key=toggle_key)', "strategy toggle"),
        (
            '''        <div class="section-card">
          <div class="section-eyebrow">進階</div>
          <div class="section-title">各種選法最後賺賠</div>
          <p class="section-copy">
            四種代表方法 + 電腦選號各跑一次，看最後賠多少。<br/>
            紅條越長代表賠越多，沒有紅條才是真的贏。
          </p>
        </div>''',
            '''        <div class="section-card">
          <div class="section-eyebrow">代表策略比較</div>
          <div class="section-title">相同資料、相同成本下的累計損益</div>
          <p class="section-copy">
            各選一種統計型、反常識型、黃曆型與事件型策略，並加入隨機選號作為基準。長條僅呈現損失規模，不代表預測排名。
          </p>
        </div>''',
            "strategy intro",
        ),
        ('<div class="loading-title">正在整理各派最後結果⋯</div>', '<div class="loading-title">正在執行代表策略回測</div>', "strategy loading title"),
        ('<div class="loading-subtitle">每一派各跑一千多期，稍等幾秒</div>', '<div class="loading-subtitle">所有策略使用相同期間、成本與獎金假設。</div>', "strategy loading subtitle"),
        (
            '''        <div class="verdict-card">
          看出來了嗎？<br/>不管用哪一種派別，最後都沒有辦法穩定賺錢。<br/>
          這就是隨機的現實：<br/>坊間傳說滿天飛，但中獎機率是不聽故事的。
        </div>''',
            '''        <div class="verdict-card">
          這些策略的結果會因遊戲與回測期間而變動，但沒有任何一類能持續、可重現地勝過隨機基準。小幅差距應視為抽樣波動，而不是預測能力。
        </div>''',
            "strategy verdict",
        ),
        (
            '''def render_backtest_explainer() -> None:
    st.markdown(
        "\n".join(
            [
                "**電腦是怎麼算的？**",
                "",
                "為了公平起見，每一期開獎前，我們都會先把答案蓋住，",
                "只用以前開過的號碼來猜，猜完再對答案。這樣一期一期算下來，",
                "就不會有那種「早知道我就買什麼」的馬後炮。",
                "",
                "**關於獎金估算：**",
                "",
                "- 像頭獎、貳獎這種沒有固定金額的，我們是拿近五年的「平均一個人實領多少」來算（已經把這筆錢會被幾個人平分的情況考慮進去了），其他小獎就照官方的固定金額。",
                "- 至於過年加碼的大紅包，因為每年規則都在變，有些資料也沒有保留，所以就**沒有算進去**。算下來一注大概差不了幾十塊，根本動搖不了「長期一直在賠錢」的現實。",
                "- 反正樂透這東西，獎金多寡本來就都會浮動，這算出來的只是一個**長期趨勢**，讓你看看一直買會發生什麼事。",
            ]
        )
    )''',
            '''def render_backtest_explainer() -> None:
    st.markdown(
        "\n".join(
            [
                "**回測方式**",
                "",
                "每一期都只使用該期以前的資料產生號碼，再和當期實際結果比對。這種 walk-forward 方法可以避免策略偷看未來，也能降低事後挑規則造成的偏誤。",
                "",
                "**獎金假設**",
                "",
                "- 浮動獎項使用近五年平均單人實領金額估算，固定獎項依遊戲規則計算。",
                "- 春節加碼與大紅包因規則及資料口徑不一致，未納入回測。",
                "- 結果適合比較長期趨勢，不應視為實際派彩精算或未來預測。",
            ]
        )
    )''',
            "backtest explainer",
        ),
        (
            '''        <div class="warning-line">
          買彩券是一種樂趣，但千萬別迷信明牌，<br/>
          因為開獎號碼說到底就只是機率而已。<br/>
          <span style="font-size:.9em; opacity:.85;">把買明牌的錢省下來，帶家人去吃頓好料吧！</span>
        </div>''',
            '''        <div class="warning-line">
          本頁提供歷史資料回測與機率教育，不構成投注建議。<br/>
          彩券適合作為有限度的娛樂，不適合作為投資、財務規劃或翻身工具。
        </div>''',
            "footer warning",
        ),
    ]

    for old, new, label in replacements:
        text = replace_exact(text, old, new, label)

    APP_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
