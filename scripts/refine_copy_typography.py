from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "streamlit_app.py"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
CONFIG_PATH = ROOT / ".streamlit" / "config.toml"


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    return text.replace(old, new)


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")

    replacements = [
        (
            'page_title="爸爸的樂透實驗｜用歷史資料檢驗選號方法"',
            'page_title="爸爸的樂透實驗｜十多年資料，看看選號到底有沒有用"',
            "page title",
        ),
        (
            '<div class="step-label">選擇彩種</div>',
            '<div class="step-label">先選一個遊戲</div>',
            "game heading",
        ),
        (
            'st.caption(f"目前載入 {game.name} 歷史資料，共 {len(draws):,} 期。")',
            'st.caption(f"目前有 {game.name} 共 {len(draws):,} 期開獎紀錄。")',
            "data caption",
        ),
        (
            'with st.expander("方法與策略比較", expanded=st.session_state.get(strategy_toggle_key, False)):',
            'with st.expander("這個實驗怎麼算？", expanded=st.session_state.get(strategy_toggle_key, False)):',
            "method expander",
        ),
        (
            'font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif !important;\n            font-size: 16px;\n            letter-spacing: .01em;',
            'font-family: "lotry-sans", "PingFang TC", "Microsoft JhengHei UI", "Microsoft JhengHei", sans-serif !important;\n            font-size: 16px;\n            font-synthesis: none;\n            letter-spacing: 0;\n            text-rendering: optimizeLegibility;\n            -webkit-font-smoothing: antialiased;',
            "font stack",
        ),
        (
            'letter-spacing: -.035em;',
            'letter-spacing: -.015em;',
            "hero tracking",
        ),
        (
            '<div class="hero-kicker">A DATA EXPERIMENT ABOUT LOTTERY MYTHS</div>\n          <h1>爸爸的樂透實驗</h1>\n          <p>把冷熱號、農民曆、新聞事件與其他常見選號方法，放進十多年的歷史資料裡逐期驗證。<br/><strong>結果沒有明牌，只有一個可以重複檢查的答案：長期表現都接近隨機。</strong></p>\n          <div class="hero-meta"><span>27 種策略</span><span>大樂透／威力彩</span><span>Walk-forward 回測</span></div>',
            '<div class="hero-kicker">一個寫給爸爸的資料實驗</div>\n          <h1>爸爸的樂透實驗</h1>\n          <p>我爸算了一輩子的樂透。後來我把他相信的冷熱號、農民曆和新聞明牌寫成程式，一期一期對過十多年的開獎紀錄。<br/><strong>最後沒有找到更準的選法，只看到所有方法長期都差不多。</strong></p>\n          <div class="hero-meta"><span>27 種選號方法</span><span>大樂透、威力彩</span><span>逐期回測</span></div>',
            "hero copy",
        ),
        (
            'if st.button("隨機選一組並回測", type="primary", width="stretch"):',
            'if st.button("讓電腦隨機選一組", type="primary", width="stretch"):',
            "random button",
        ),
        (
            'with st.expander("自己選號"):',
            'with st.expander("我想自己選號"):',
            "manual expander",
        ),
        (
            'st.caption(f"從 1 到 {game.main_pool} 選擇 {game.main_pick} 個號碼，再執行歷史回測。")',
            'st.caption(f"從 1 到 {game.main_pool} 選 {game.main_pick} 個號碼，看看如果每期都買，過去會是什麼結果。")',
            "manual caption",
        ),
        (
            '"開始回測",',
            '"看看過去的結果",',
            "manual action",
        ),
        (
            'st.info(f"還需要選擇 {game.main_pick - len(selected)} 個號碼。")',
            'st.info(f"還差 {game.main_pick - len(selected)} 個號碼。")',
            "selection info",
        ),
        (
            '<div class="loading-title">正在執行歷史回測</div>\n          <div class="loading-balls">{balls}</div>\n          <div class="loading-subtitle">逐期比對開獎結果、估算獎金與累計損益。</div>',
            '<div class="loading-title">正在對照過去的開獎紀錄</div>\n          <div class="loading-balls">{balls}</div>\n          <div class="loading-subtitle">把這組號碼放進每一期，算出中獎金額和總花費。</div>',
            "loading copy",
        ),
        (
            '<div class="step-label">回測結果</div>',
            '<div class="step-label">這組號碼，過去表現如何？</div>',
            "result heading",
        ),
        (
            '<span class="selected-label">選擇的號碼</span>',
            '<span class="selected-label">你選的號碼</span>',
            "selected label",
        ),
        (
            '將這組號碼套用到過去 {result.periods:,} 期，並假設每期購買一注，累計損益為',
            '假設過去 {result.periods:,} 期每期都買一注，最後會是：',
            "result lead",
            2,
        ),
        (
            '    if abs_amount > 0:\n        st.markdown(\n            f\'<div class="tangible-loss">損益絕對值為 <b>{format_money(abs_amount)}</b>。此數字用來呈現歷史回測的金額規模，不代表未來結果。</div>\',\n            unsafe_allow_html=True,\n        )',
            '    if abs_amount > 0:\n        balance_note = (\n            f"獎金比總成本多 <b>{format_money(abs_amount)}</b>。"\n            if is_profit\n            else f"總成本扣掉估算獎金後，差了 <b>{format_money(abs_amount)}</b>。"\n        )\n        st.markdown(\n            f\'<div class="tangible-loss">{balance_note}這只是這段歷史紀錄裡的結果，不代表下一期。</div>\',\n            unsafe_allow_html=True,\n        )',
            "balance note",
        ),
        (
            '<div class="stat-card"><div class="stat-card-label">總共花了</div>',
            '<div class="stat-card"><div class="stat-card-label">買彩券共花</div>',
            "cost label",
            2,
        ),
        (
            '<div class="stat-card"><div class="stat-card-label">總共領回</div>',
            '<div class="stat-card"><div class="stat-card-label">估算獎金</div>',
            "prize label",
            2,
        ),
        (
            '<div class="stat-card"><div class="stat-card-label">頭獎中過</div>',
            '<div class="stat-card"><div class="stat-card-label">頭獎次數</div>',
            "jackpot label",
            2,
        ),
        (
            'st.caption(f"獎金估算：{jackpot_note} 春節加碼與大紅包未納入。{odds_text}")',
            'st.caption(f"獎金以近年平均與固定獎金估算。{jackpot_note} 春節加碼與大紅包沒有算進去。{odds_text}")',
            "prize caption",
        ),
        (
            'direction = "接近隨機期望" if abs(diff) < 0.05 else ("略高於隨機期望" if diff > 0 else "略低於隨機期望")',
            'direction = "和隨機差不多" if abs(diff) < 0.05 else ("比隨機高一點" if diff > 0 else "比隨機低一點")',
            "direction copy",
        ),
        (
            'luck_line = f"這 {result.periods:,} 期裡剛好抽到 {result.exact_hits} 次頭獎，才讓帳面看起來是正的。"',
            'luck_line = f"這段期間剛好碰到 {result.exact_hits} 次頭獎，結果才會轉正。"',
            "jackpot luck",
        ),
        (
            'luck_line = f"這 {result.periods:,} 期裡剛好中了 {result.near_hits} 次大獎，才湊到正數的。"',
            'luck_line = f"這段期間剛好碰到 {result.near_hits} 次較高獎項，結果才會轉正。"',
            "near jackpot luck",
        ),
        (
            'luck_line = f"這 {result.periods:,} 期下來小獎剛好累積到跨過本金。"',
            'luck_line = "這段期間的小獎剛好累積超過總成本。"',
            "small prize luck",
        ),
        (
            '<b>這次回測出現正報酬，不代表這組號碼具有預測能力。</b><br/>\n              {luck_line}<br/>\n              頭獎機率約為 {jackpot_pct(odds)}；每一期仍是獨立事件。更換號碼或回測區間後，結果通常會明顯改變。',
            '<b>這次算出賺錢，不代表這組號碼比較會中。</b><br/>\n              {luck_line}<br/>\n              頭獎機率約為 {jackpot_pct(odds)}，而且每一期都會重新開始。換一組號碼或換一段年份，結果很可能完全不同。',
            "profit verdict",
        ),
        (
            '這組號碼平均每期命中 <b>{result.avg_hits:.3f}</b> 個主區號碼；隨機選號的理論期望約為 <b>{expected_avg:.3f}</b>。<br/>\n              本次結果{direction}。<br/><u>差距不足以證明這組號碼具有可重現的優勢。</u>',
            '這組號碼平均每期對中 <b>{result.avg_hits:.3f}</b> 個主區號碼，隨機選號理論上約為 <b>{expected_avg:.3f}</b>。<br/>\n              兩者{direction}。<br/><u>從這段歷史紀錄，看不出它有能重複出現的優勢。</u>',
            "loss verdict",
        ),
        (
            '<div class="simple-result-title">正報酬主要來自少數高額獎項</div>\n              <div class="quiet-note">累計結果對少數高額獎項非常敏感。平均每期命中 <b>{result.avg_hits:.3f}</b> 個主區號碼，接近隨機選號的 <b>{expected_avg:.3f}</b>。</div>',
            '<div class="simple-result-title">為什麼這次會賺？</div>\n              <div class="quiet-note">主要是少數幾次較高獎項把結果拉了上來。平均每期對中 <b>{result.avg_hits:.3f}</b> 個主區號碼，仍接近隨機選號的 <b>{expected_avg:.3f}</b>。</div>',
            "profit summary",
        ),
        (
            '<div class="simple-result-title">沒有觀察到高於隨機的穩定優勢</div>\n              <div class="quiet-note">在這段歷史資料中，固定購買同一組號碼的累計報酬為負。</div>',
            '<div class="simple-result-title">這組號碼沒有特別準</div>\n              <div class="quiet-note">固定買同一組號碼，過去這段期間的獎金沒有補回總成本。</div>',
            "loss summary",
        ),
        (
            '<div class="share-cta-title">匯出這次回測</div>\n          <div class="share-cta-body">\n            可將號碼、期間、成本與損益整理成圖片，方便保存或分享。小卡呈現的是歷史模擬，不是未來預測。\n          </div>',
            '<div class="share-cta-title">把結果存成圖片</div>\n          <div class="share-cta-body">\n            想留著或傳給家人，可以產生一張簡單的小卡。上面會清楚標示這是過去的結果，不是在預測下一期。\n          </div>',
            "share copy",
        ),
        (
            'if st.button("產生回測小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):',
            'if st.button("產生結果小卡", type="primary", width="stretch", key=f"gen_card_{game.code}"):',
            "share button",
        ),
        (
            'with st.expander("查看累計損益走勢"):',
            'with st.expander("看看錢怎麼一路變化"):',
            "chart expander",
        ),
        (
            'st.caption("獎金包含特別號／第二區；頭獎採近年平均單人實領估算（已假設多人均分）。春節加碼、大紅包不納入。用途是看長期趨勢，不是精算實際金額。")',
            'st.caption("獎金包含特別號／第二區；浮動獎項用近年平均單人實領估算。春節加碼與大紅包沒有算進去，因此這張圖適合看趨勢，不適合拿來核對每一期派彩。")',
            "chart caption",
        ),
        (
            '<div class="section-eyebrow">威力彩情境試算</div>\n          <div class="section-title">第二區 1–8 全包的長期結果</div>\n          <p class="section-copy">\n            第二區全包可以提高中小獎的頻率，但每期成本也會變成八倍。這裡使用相同主區號碼，回測完整歷史資料。\n          </p>',
            '<div class="section-eyebrow">威力彩多算一種買法</div>\n          <div class="section-title">第二區 1 到 8 全包，真的比較划算嗎？</div>\n          <p class="section-copy">\n            第二區全包的確比較常中小獎，但每期也要一次買八注。這裡沿用同一組主區號碼，看看過去的獎金能不能補回多出的成本。\n          </p>',
            "bonus intro",
        ),
        (
            'if st.button("回測第二區全包", width="stretch"):',
            'if st.button("算算看第二區全包", width="stretch"):',
            "bonus button",
        ),
        (
            '<b>本次正報酬主要由少數高額獎項造成。</b><br/>\n              第二區全包會固定增加七張未中特別號的投注；若沒有高額獎項，額外成本通常會高於小獎收入。',
            '<b>這次會賺，主要是剛好碰到少數高額獎項。</b><br/>\n              第二區全包每期都多買七注；沒有較高獎項時，多出的成本通常會比小獎還多。',
            "bonus profit verdict",
        ),
        (
            '<b>提高中獎頻率，不等於提高報酬率。</b><br/>\n              第二區全包能確保其中一注命中特別號，但其餘七注仍要支付成本；在這段歷史資料中，累計報酬仍為負。',
            '<b>比較常中，不代表最後比較划算。</b><br/>\n              全包能保證其中一注對中第二區，但另外七注也都要付錢；在這段歷史紀錄裡，獎金仍沒有補回成本。',
            "bonus loss verdict",
        ),
        (
            '<div class="share-cta-title">匯出全包情境</div>\n          <div class="share-cta-body">\n            將主區號碼、八倍成本與歷史損益整理成圖片，方便比較「中獎頻率」與「實際報酬」的差別。\n          </div>',
            '<div class="share-cta-title">把全包結果存成圖片</div>\n          <div class="share-cta-body">\n            小卡會列出主區號碼、八倍成本和最後損益，方便看清楚「比較常中」和「有沒有賺」是兩件事。\n          </div>',
            "bonus share copy",
        ),
        (
            'if st.button("產生全包回測小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):',
            'if st.button("產生全包結果小卡", type="primary", width="stretch", key=f"gen_bonus_card_{game.code}"):',
            "bonus share button",
        ),
        (
            'f"{game.name} · {result.periods:,} 期歷史回測"',
            'f"{game.name} · 對照過去 {result.periods:,} 期"',
            "card subtitle",
        ),
        (
            'tagline = "正報酬來自少數高額獎項" if is_profit_card else "固定購買同一組號碼的歷史結果"',
            'tagline = "這次會賺，主要是少數幾次大獎" if is_profit_card else "這組號碼如果每期都買"',
            "card tagline",
        ),
        (
            '_dc(410, f"套用過去 {result.periods:,} 期開獎資料", narrative_font, (80, 75, 70, 255))',
            '_dc(410, f"拿這組號碼對過去 {result.periods:,} 期", narrative_font, (80, 75, 70, 255))',
            "card narrative first line",
            2,
        ),
        (
            '_dc(454, "少數高額獎項使累計結果轉為正值", narrative_font, (80, 75, 70, 255))',
            '_dc(454, "少數幾次較高獎項把結果拉到正數", narrative_font, (80, 75, 70, 255))',
            "card profit narrative",
        ),
        (
            '_dc(454, "假設每期固定購買一注", narrative_font, (80, 75, 70, 255))',
            '_dc(454, "假設每一期都固定買一注", narrative_font, (80, 75, 70, 255))',
            "card loss narrative",
        ),
        (
            '_dc(766, "歷史模擬結果，不代表下一期表現", _load_font(28), (120, 115, 110, 255))',
            '_dc(766, "這是過去的結果，不是在預測下一期", _load_font(28), (120, 115, 110, 255))',
            "card disclaimer",
        ),
        (
            'cta_text = "沒有觀察到可重現、能勝過隨機的選號優勢。"',
            'cta_text = "這段歷史裡，看不出它比隨機選號更有優勢。"',
            "card cta",
        ),
        (
            '_dc(footer_top + 80, "這是歷史模擬，不是未來預測或投注建議", foot_font, (200, 195, 185, 255))',
            '_dc(footer_top + 80, "這張圖只整理過去資料，不是投注建議", foot_font, (200, 195, 185, 255))',
            "card footer",
        ),
        (
            'f"{game.name} · 包第二區全包 · {result.periods:,} 期回測"',
            'f"{game.name} · 第二區 1–8 全包 · {result.periods:,} 期"',
            "bonus card subtitle",
        ),
        (
            'tag_text = "正報酬主要由少數高額獎項造成" if is_profit_card else "第二區全包的成本與報酬比較"',
            'tag_text = "這次會賺，主要是少數幾次大獎" if is_profit_card else "比較常中，最後有比較划算嗎？"',
            "bonus card tagline",
        ),
        (
            'show_strategy = st.toggle("執行代表策略比較", value=False, key=toggle_key)',
            'show_strategy = st.toggle("比較幾種常見選法", value=False, key=toggle_key)',
            "strategy toggle",
        ),
        (
            '<div class="section-eyebrow">代表策略比較</div>\n          <div class="section-title">相同資料、相同成本下的累計損益</div>\n          <p class="section-copy">\n            各選一種統計型、反常識型、黃曆型與事件型策略，並加入隨機選號作為基準。長條僅呈現損失規模，不代表預測排名。\n          </p>',
            '<div class="section-eyebrow">選號方法比較</div>\n          <div class="section-title">熱號、農民曆、新聞明牌，哪個比較有用？</div>\n          <p class="section-copy">\n            每種方法都用同一段開獎紀錄、同樣的買法和成本，再和隨機選號放在一起比較。長條只是呈現最後差了多少錢，不是明牌排行榜。\n          </p>',
            "strategy intro",
        ),
        (
            '<div class="loading-title">正在執行代表策略回測</div>',
            '<div class="loading-title">正在重跑幾種選號方法</div>',
            "strategy loading title",
        ),
        (
            '<div class="loading-subtitle">所有策略使用相同期間、成本與獎金假設。</div>',
            '<div class="loading-subtitle">每種方法都用同一段資料和相同成本。</div>',
            "strategy loading subtitle",
        ),
        (
            '這幾種裡面，最好的是「{best_row[\'派別\']}」：{format_money(int(best_row[\'總損益\']))}。<br/>\n          最差的是「{worst_row[\'派別\']}」：{format_money(int(worst_row[\'總損益\']))}。',
            '這次表現最好的是「{best_row[\'派別\']}」：{format_money(int(best_row[\'總損益\']))}。<br/>\n          最差的是「{worst_row[\'派別\']}」：{format_money(int(worst_row[\'總損益\']))}。但換一段年份，順序就可能改變。',
            "strategy best worst",
        ),
        (
            '這些策略的結果會因遊戲與回測期間而變動，但沒有任何一類能持續、可重現地勝過隨機基準。小幅差距應視為抽樣波動，而不是預測能力。',
            '不同遊戲、不同年份，排名都會變動。把資料拉長後，沒有任何一種方法能一直贏過隨機選號；那些小差距比較像運氣，不像真的找到規律。',
            "strategy verdict",
        ),
        (
            '"電腦選號": "電腦隨機亂選，不看任何規則。",\n    "追熱號": "看哪幾個號碼最近常開，就跟著買。",\n    "反著買": "別人常買的我不買，改挑冷門號碼。",\n    "農民曆": "看農民曆、干支、五行來挑號碼。",\n    "看新聞挑": "把今天日期、社會大事變成號碼。",',
            '"電腦選號": "完全隨機，不參考過去開獎紀錄。",\n    "追熱號": "挑最近比較常開的號碼。",\n    "反著買": "避開熱門選法，改選較少人注意的號碼。",\n    "農民曆": "用農曆、干支和五行換算號碼。",\n    "看新聞挑": "把日期或新聞事件裡的數字拿來選號。",',
            "strategy descriptions",
        ),
        (
            '"**電腦是怎麼算的？**",\n                "",\n                "為了公平起見，每一期開獎前，我們都會先把答案蓋住，",\n                "只用以前開過的號碼來猜，猜完再對答案。這樣一期一期算下來，",\n                "就不會有那種「早知道我就買什麼」的馬後炮。",\n                "",\n                "**關於獎金估算：**",\n                "",\n                "- 像頭獎、貳獎這種沒有固定金額的，我們是拿近五年的「平均一個人實領多少」來算（已經把這筆錢會被幾個人平分的情況考慮進去了），其他小獎就照官方的固定金額。",\n                "- 至於過年加碼的大紅包，因為每年規則都在變，有些資料也沒有保留，所以就**沒有算進去**。算下來一注大概差不了幾十塊，根本動搖不了「長期一直在賠錢」的現實。",\n                "- 反正樂透這東西，獎金多寡本來就都會浮動，這算出來的只是一個**長期趨勢**，讓你看看一直買會發生什麼事。",',
            '"**怎麼避免偷看答案？**",\n                "",\n                "每一期都只使用它以前的開獎紀錄產生號碼，選完後才和當期結果比對。",\n                "從第一期一路重複到最後，避免用已知答案倒推一套看起來很準的規則。",\n                "",\n                "**獎金怎麼估？**",\n                "",\n                "- 固定獎依官方規則；頭獎、貳獎等浮動獎項，採近五年平均單人實領金額。",\n                "- 春節加碼與大紅包的規則逐年不同，因此沒有納入。",\n                "- 金額用來比較長期成本與獎金，不是精算每一期實際派彩。",',
            "explainer copy",
        ),
        (
            '本頁提供歷史資料回測與機率教育，不構成投注建議。<br/>\n          彩券適合作為有限度的娛樂，不適合作為投資、財務規劃或翻身工具。',
            '這個網站不是選號工具，只是把過去資料攤開來看。<br/>\n          彩券可以當娛樂，但別把明牌當成投資方法。',
            "footer copy",
        ),
        (
            '"分享小卡需要可縮放的中文字型。請確認 assets/fonts/NotoSansTC-VF.ttf 已經一起提交並部署，"',
            '"分享小卡需要可縮放的中文字型。請確認 static/fonts/NotoSansTC-VF.ttf 已經一起提交並部署，"',
            "font error path",
        ),
        (
            '_BUNDLED_FONT_PATH = ROOT / "assets" / "fonts" / "NotoSansTC-VF.ttf"',
            '_BUNDLED_FONT_PATH = ROOT / "static" / "fonts" / "NotoSansTC-VF.ttf"',
            "bundled font path",
        ),
    ]

    for replacement in replacements:
        old, new, label, *expected = replacement
        text = replace_exact(text, old, new, label, expected[0] if expected else 1)

    text = text.replace("font-weight: 850;", "font-weight: 800;")
    text = text.replace("font-weight: 750;", "font-weight: 700;")
    text = text.replace("font-weight: 650;", "font-weight: 600;")
    text = text.replace("font-weight: 450;", "font-weight: 400;")
    text = text.replace("text-transform: uppercase;", "text-transform: none;")

    APP_PATH.write_text(text, encoding="utf-8")

    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    requirements = replace_exact(
        requirements,
        "streamlit>=1.34.0",
        "streamlit>=1.45.0",
        "Streamlit minimum version",
    )
    REQUIREMENTS_PATH.write_text(requirements, encoding="utf-8")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        """[server]\nenableStaticServing = true\n\n[[theme.fontFaces]]\nfamily = \"lotry-sans\"\nurl = \"app/static/fonts/NotoSansTC-VF.ttf\"\nstyle = \"normal\"\nweight = \"100 900\"\n\n[theme]\nfont = \"lotry-sans\"\nheadingFont = \"lotry-sans\"\nbaseFontSize = 16\n""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
