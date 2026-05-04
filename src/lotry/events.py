"""大新聞事件派策略（明牌派）。

民間有種傳統：發生重大事件（地震、空難、政治新聞）就去『拆字』『拆數字』
從新聞裡找明牌。本模組把這個直覺系統化：

  1. 日期數字學派 — 把開獎日的西元年/月/日/星期/民國年拆解成號碼
  2. 重大事件對照派 — 內建 30+ 件台灣重大事件，看開獎日距離哪個事件最近
     就用那個事件的關鍵數字（傷亡數、強度、日期）當明牌
  3. 頭條雜湊派 — 用日期 hash 模擬「當天頭條的字數」之類的偽新聞特徵

⚠️ 真實新聞 API 無法回溯 1500 期歷史，所以我們用『可重現的偽新聞訊號』。
   這正好證明：所謂明牌靈不靈，本質就是隨機數的另一個分身。
"""

import datetime
import hashlib
import random as _random

from .games import GameDef


# ---------------------------------------------------------------------------
# 內建台灣重大事件資料庫（精選 30 件，含關鍵數字）
# ---------------------------------------------------------------------------
# 格式：(西元日期, 事件簡稱, 關鍵數字 list)
TW_MAJOR_EVENTS: list[tuple[str, str, list[int]]] = [
    ("1999-09-21", "921 大地震",      [9, 21, 7, 3, 2415]),  # 規模 7.3，2415 罹難
    ("2009-08-08", "莫拉克八八風災",   [8, 8, 8, 6, 67, 4]),  # 67 罹難 691 失蹤
    ("2014-07-31", "高雄氣爆",        [7, 31, 32, 321]),     # 32 死
    ("2014-07-23", "復興航空馬公空難", [7, 23, 48]),          # 48 死
    ("2015-02-04", "復興 235 號班機", [2, 4, 235, 43]),      # 43 死
    ("2016-02-06", "美濃地震維冠倒塌", [2, 6, 6, 4, 117]),   # 117 死
    ("2018-02-06", "花蓮 0206 地震",  [2, 6, 6, 0, 17]),
    ("2018-10-21", "普悠瑪事故",      [10, 21, 18, 215]),    # 18 死
    ("2021-04-02", "太魯閣號事故",    [4, 2, 49, 408]),     # 49 死 408 號車
    ("2024-04-03", "花蓮 0403 強震",  [4, 3, 7, 2, 18]),
    ("2003-03-14", "SARS 爆發",      [3, 14, 73]),         # 台灣 73 死
    ("2020-01-21", "新冠首例",        [1, 21, 19]),         # COVID-19
    ("2003-08-15", "全台大停電 8.15", [8, 15]),
    ("2017-08-15", "815 大停電",     [8, 15, 668]),         # 668 萬戶停電
    ("2022-03-03", "303 大停電",      [3, 3, 549]),
    ("2024-04-15", "415 大停電",      [4, 15]),
    ("2000-05-20", "首次政黨輪替",    [5, 20]),
    ("2008-05-20", "二次政黨輪替",    [5, 20]),
    ("2016-01-16", "首位女總統當選",  [1, 16, 689]),
    ("2024-01-13", "賴清德當選",      [1, 13]),
    ("2014-03-18", "太陽花學運",      [3, 18, 50]),
    ("2019-06-09", "香港反送中",      [6, 9, 103]),
    ("2022-08-02", "裴洛西訪台",      [8, 2]),
    ("2011-03-11", "日本 311 海嘯",   [3, 11, 9, 18500]),
    ("2008-05-12", "汶川大地震",      [5, 12, 8, 69227]),
    ("2001-09-11", "美國 911 事件",   [9, 11]),
    ("2020-01-26", "Kobe 直升機空難", [1, 26, 24, 8]),
    ("2022-09-18", "918 池上地震",    [9, 18, 6, 8]),
    ("2009-02-27", "新店氣爆",        [2, 27, 4]),
    ("2015-06-27", "八仙塵爆",        [6, 27, 15, 499]),    # 15 死 499 傷
]


def _parse_date(s: str) -> datetime.date | None:
    try:
        y, m, d = s.split("-")
        return datetime.date(int(y), int(m), int(d))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def _expand_to_pool(seeds: list[int], pool: int) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for s in seeds:
        if s <= 0:
            continue
        v = ((s - 1) % pool) + 1
        if v not in seen:
            out.append(v)
            seen.add(v)
    return out


def _fill_random(picks: list[int], pool: int, k: int, rng: _random.Random) -> list[int]:
    seen = set(picks)
    candidates = [n for n in range(1, pool + 1) if n not in seen]
    rng.shuffle(candidates)
    while len(picks) < k and candidates:
        picks.append(candidates.pop())
    return sorted(picks[:k])


def _target_date(draws: list[dict], rng: _random.Random | None = None) -> datetime.date:
    """取要預測那期的開獎日（回測時由 rng.target_date 提供）。"""
    if rng is not None and getattr(rng, "target_date", None):
        d = _parse_date(rng.target_date)  # type: ignore[attr-defined]
        if d:
            return d
    if not draws:
        return datetime.date.today()
    last = _parse_date(draws[-1]["date"])
    if last:
        return last + datetime.timedelta(days=3)
    return datetime.date.today()


# ---------------------------------------------------------------------------
# 1) 日期數字學派
# ---------------------------------------------------------------------------

def strategy_date_numerology(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """把日期拆成各種數字組合：年月日、民國年、星期、年積日。"""
    d = _target_date(draws, rng)
    roc_year = d.year - 1911
    seeds = [
        d.day,
        d.month,
        d.month + d.day,
        roc_year,
        roc_year + d.month,
        d.weekday() + 1,
        d.timetuple().tm_yday,           # 一年中的第幾天
        d.timetuple().tm_yday // 7,      # 第幾週
        (d.year % 100),
        (d.year % 100) + d.day,
    ]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 2) 重大事件對照派
# ---------------------------------------------------------------------------

def strategy_major_event(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """找開獎日『最接近』哪個重大事件，用該事件的關鍵數字當明牌。"""
    target = _target_date(draws, rng)
    best_event = None
    best_diff = 10 ** 9
    for date_str, name, nums in TW_MAJOR_EVENTS:
        ed = _parse_date(date_str)
        if ed is None:
            continue
        diff = abs((target - ed).days)
        # 偏好「當週同月日」(週年事件) — 月日相同則 diff 算成 0
        if ed.month == target.month and ed.day == target.day:
            diff = 0
        if diff < best_diff:
            best_diff = diff
            best_event = (date_str, name, nums)

    if best_event is None:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    _, _, nums = best_event
    # 加入相鄰事件當補充
    seeds = list(nums)
    # 補上目標日期的數字
    seeds.extend([target.day, target.month, target.day + target.month])
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 3) 頭條雜湊派（偽新聞特徵）
# ---------------------------------------------------------------------------

def strategy_headline_hash(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """用日期 SHA256 模擬『當天頭條字數/字頻特徵』，取前若干字元映射到號碼。

    這正是『新聞明牌』背後的本質：把不確定的雜訊雜湊成數字。
    """
    d = _target_date(draws, rng)
    h = hashlib.sha256(d.isoformat().encode("utf-8")).digest()
    seeds: list[int] = []
    for i in range(0, len(h), 2):
        n = (h[i] << 8 | h[i + 1])
        seeds.append((n % game.main_pool) + 1)
        if len(seeds) >= game.main_pick * 3:
            break
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 4) 災害強度派（事件數字 × 開獎日數字學交乘）
# ---------------------------------------------------------------------------

def strategy_disaster_combo(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """取最近 N 件事件的關鍵數字平均，再與當天日期混合。"""
    target = _target_date(draws, rng)
    # 取目標日 ±365 天內所有事件
    nearby: list[int] = []
    for date_str, _, nums in TW_MAJOR_EVENTS:
        ed = _parse_date(date_str)
        if ed and abs((target - ed).days) < 365:
            nearby.extend(nums)
    if not nearby:
        # 退回所有事件
        for _, _, nums in TW_MAJOR_EVENTS:
            nearby.extend(nums)

    # 與當天日期數字混合
    nearby.append(target.day * target.month)
    nearby.append(target.day + target.year % 100)
    rng.shuffle(nearby)
    picks = _expand_to_pool(nearby, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 5) 媒體輪播派（隨日期 rotate 事件清單）
# ---------------------------------------------------------------------------

def strategy_media_rotate(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """每次選一個事件當主軸，依日期決定（模擬媒體當日主打議題）。"""
    target = _target_date(draws, rng)
    idx = (target.toordinal() // 3) % len(TW_MAJOR_EVENTS)
    _, _, nums = TW_MAJOR_EVENTS[idx]
    seeds = list(nums) + [target.day, target.month + target.day]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略登記
# ---------------------------------------------------------------------------

EVENT_STRATEGIES = {
    "date_numerology":  strategy_date_numerology,
    "major_event":      strategy_major_event,
    "headline_hash":    strategy_headline_hash,
    "disaster_combo":   strategy_disaster_combo,
    "media_rotate":     strategy_media_rotate,
}

EVENT_NAMES_ZH = {
    "date_numerology":  "日期數字學",
    "major_event":      "重大事件對照",
    "headline_hash":    "頭條雜湊派",
    "disaster_combo":   "災害交乘派",
    "media_rotate":     "媒體輪播派",
}
