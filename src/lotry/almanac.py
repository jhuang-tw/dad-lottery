"""黃曆派策略：用農曆、干支、五行、二十八宿、沖煞等傳統依據選號。

獻給：相信黃曆的爸爸 ❤️

以下策略用 cnlunar 萃取每天的黃曆資料，把它對應到樂透號碼。
回測時，用「該期實際開獎日的黃曆」回頭預測該期 → 看是否真的有效。

⚠️ 數學上彩券是獨立隨機事件，黃曆無法預測。
   這套策略的價值是把爸爸的『感覺』系統化，並用 1500 期歷史驗證它的真實效力。
"""

import datetime
import random as _random
from collections import defaultdict

import cnlunar

from .games import GameDef


# ---------------------------------------------------------------------------
# 黃曆資料萃取
# ---------------------------------------------------------------------------

# 生肖 → 序號（1=鼠 ... 12=豬）
ZODIAC_NUM = {
    "鼠": 1, "牛": 2, "虎": 3, "兔": 4, "龍": 5, "龙": 5, "蛇": 6,
    "馬": 7, "马": 7, "羊": 8, "猴": 9, "雞": 10, "鸡": 10, "狗": 11, "豬": 12, "猪": 12,
}

# 二十八宿排序（角亢氐房心尾箕；斗牛女虛危室壁；奎婁胃昴畢觜參；井鬼柳星張翼軫）
STAR_28 = [
    "角", "亢", "氐", "房", "心", "尾", "箕",
    "斗", "牛", "女", "虛", "虚", "危", "室", "壁",
    "奎", "婁", "娄", "胃", "昴", "畢", "毕", "觜", "參", "参",
    "井", "鬼", "柳", "星", "張", "张", "翼", "軫", "轸",
]
# 完整序號（去重後對應 1-28）
_STAR_28_ORDER = [
    "角", "亢", "氐", "房", "心", "尾", "箕",
    "斗", "牛", "女", "虛", "危", "室", "壁",
    "奎", "婁", "胃", "昴", "畢", "觜", "參",
    "井", "鬼", "柳", "星", "張", "翼", "軫",
]
_STAR_ALIASES = {"龙": "龍", "马": "馬", "鸡": "雞", "猪": "豬",
                 "虚": "虛", "娄": "婁", "毕": "畢", "参": "參",
                 "张": "張", "轸": "軫"}


def _parse_lunar(date_str: str) -> dict | None:
    """date_str: 'YYYY-MM-DD' → 回傳該日黃曆資料 dict。"""
    try:
        y, m, d = date_str.split("-")
        dt = datetime.datetime(int(y), int(m), int(d))
        a = cnlunar.Lunar(dt)
        # 二十八宿名稱（first char）
        star_name = (a.today28Star or "")[:1]
        star_name_norm = _STAR_ALIASES.get(star_name, star_name)
        try:
            star_idx = _STAR_28_ORDER.index(star_name_norm) + 1  # 1..28
        except ValueError:
            star_idx = 0
        # 沖煞生肖（"虎日冲猴" → 取「猴」）
        clash_str = a.chineseZodiacClash or ""
        clash_zodiac = clash_str[-1:] if clash_str else ""
        return {
            "lunar_day": a.lunarDay,             # 1-30
            "lunar_month": a.lunarMonth,         # 1-12
            "day_heaven": a.dayHeavenNum,        # 1-10 天干
            "day_earth": a.dayEarthNum,          # 1-12 地支
            "day_60": a.dayHeavenlyEarthNum,     # 1-60 六十甲子
            "month_heaven": a.monthHeavenNum,    # 1-10
            "month_earth": a.monthEarthNum,      # 1-12
            "year_zodiac_num": ZODIAC_NUM.get(a.chineseYearZodiac, 0),
            "clash_num": ZODIAC_NUM.get(clash_zodiac, 0),
            "star_28": star_idx,                 # 1-28 二十八宿
            "level_name": a.todayLevelName or "",
            "good_god_count": len(a.goodGodName or []),
            "bad_god_count": len(a.badGodName or []),
        }
    except Exception:
        return None


def _expand_to_pool(seeds: list[int], pool: int) -> list[int]:
    """把任意正整數種子展開成 [1, pool] 範圍內的去重清單。"""
    out: list[int] = []
    seen: set[int] = set()
    for s in seeds:
        if s <= 0:
            continue
        # 取模映射，避免 0
        v = ((s - 1) % pool) + 1
        if v not in seen:
            out.append(v)
            seen.add(v)
    return out


def _fill_random(picks: list[int], pool: int, k: int, rng: _random.Random) -> list[int]:
    """把 picks 補足到 k 個不重複號碼。"""
    seen = set(picks)
    candidates = [n for n in range(1, pool + 1) if n not in seen]
    rng.shuffle(candidates)
    while len(picks) < k and candidates:
        picks.append(candidates.pop())
    return sorted(picks[:k])


def _draw_date(draws: list[dict], rng: _random.Random | None = None) -> str:
    """取『要預測的那一期』的日期。

    回測時 rng.target_date 會由回測引擎設好（= 當期實際開獎日）。
    一般 predict 時，用最後一期日期 + 3 天當下一期粗略估計。
    """
    if rng is not None and getattr(rng, "target_date", None):
        return rng.target_date  # type: ignore[attr-defined]
    if not draws:
        return datetime.date.today().isoformat()
    last = draws[-1]["date"]
    try:
        y, m, d = last.split("-")
        dt = datetime.date(int(y), int(m), int(d)) + datetime.timedelta(days=3)
        return dt.isoformat()
    except Exception:
        return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# 策略 1：農曆日數派
# ---------------------------------------------------------------------------

def strategy_lunar_day(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """主號碼 = 農曆日；輔助 = 農曆月、月柱、年支。"""
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    seeds = [
        info["lunar_day"],
        info["lunar_day"] + 7,
        info["lunar_day"] + 14,
        info["lunar_month"] * 4,
        info["month_heaven"] * 5,
        info["year_zodiac_num"] * 3,
    ]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 2：六十甲子派
# ---------------------------------------------------------------------------

def strategy_stem_branch(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """六十甲子序號 + 天干、地支、月柱組合。"""
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    sixty = info["day_60"]
    seeds = [
        sixty,                          # 1-60
        sixty + 6,
        info["day_heaven"] * 5,         # 5,10,15...
        info["day_earth"] * 4,          # 4,8,12...
        info["month_heaven"] * 6,
        info["month_earth"] * 3,
    ]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 3：五行派（按天干五行對應區間）
# ---------------------------------------------------------------------------

# 天干五行：甲乙=木, 丙丁=火, 戊己=土, 庚辛=金, 壬癸=水
_WUXING_ZONE = {
    1: "木", 2: "木",
    3: "火", 4: "火",
    5: "土", 6: "土",
    7: "金", 8: "金",
    9: "水", 10: "水",
}


def strategy_wuxing(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """依當日天干五行偏向對應區間。"""
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    element = _WUXING_ZONE.get(info["day_heaven"], "土")
    pool_size = game.main_pool
    # 將池切五段對應五行
    seg = pool_size // 5
    zones = {
        "木": (1, seg),
        "火": (seg + 1, seg * 2),
        "土": (seg * 2 + 1, seg * 3),
        "金": (seg * 3 + 1, seg * 4),
        "水": (seg * 4 + 1, pool_size),
    }
    lo, hi = zones[element]
    primary = list(range(lo, hi + 1))
    rng.shuffle(primary)

    # 主區間取 4 個，其他區間補 2 個
    picks = primary[: max(game.main_pick - 2, 1)]
    others = [n for n in range(1, pool_size + 1) if n not in picks]
    rng.shuffle(others)
    while len(picks) < game.main_pick:
        picks.append(others.pop())
    return sorted(picks[: game.main_pick])


# ---------------------------------------------------------------------------
# 策略 4：沖煞反向派
# ---------------------------------------------------------------------------

def strategy_clash(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """避開『沖』的生肖對應號碼，從剩下選。

    生肖 X (1-12) 對應的號碼 = {X, X+12, X+24, X+36, X+48} ∩ pool
    """
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    forbidden: set[int] = set()
    cz = info["clash_num"]
    if cz > 0:
        forbidden = {cz + 12 * k for k in range(5) if 1 <= cz + 12 * k <= game.main_pool}

    # 偏好年支對應的號碼（生肖加成）
    yz = info["year_zodiac_num"]
    bonus = [yz + 12 * k for k in range(5) if 1 <= yz + 12 * k <= game.main_pool]

    pool = [n for n in range(1, game.main_pool + 1) if n not in forbidden]
    # bonus 號碼先放
    picks = [n for n in bonus if n in pool]
    rest = [n for n in pool if n not in picks]
    rng.shuffle(rest)
    while len(picks) < game.main_pick and rest:
        picks.append(rest.pop())
    return sorted(picks[: game.main_pick])


# ---------------------------------------------------------------------------
# 策略 5：二十八宿派
# ---------------------------------------------------------------------------

def strategy_lunar_mansion(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """主號 = 二十八宿序號；輔助 = 倍數 + 月柱。"""
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    star = info["star_28"] if info["star_28"] > 0 else (info["lunar_day"] % 28 + 1)
    seeds = [
        star,
        star + 7,
        star + 14,
        star + 21,
        info["lunar_month"] * 3,
        info["day_heaven"] * 4,
    ]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 6：黃曆綜合公式（爸爸專用版）
# ---------------------------------------------------------------------------

def strategy_almanac_combined(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """農曆日 + 干支 + 二十八宿 + 月柱 + 年支 各取一個號碼。"""
    info = _parse_lunar(_draw_date(draws, rng))
    if not info:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))

    # 6 個號碼分別對應 6 種黃曆元素
    seeds = [
        info["lunar_day"],                              # 農曆日
        info["day_heaven"] * 5 + info["day_earth"],     # 日柱合
        info["star_28"] if info["star_28"] > 0 else 14, # 二十八宿
        info["month_heaven"] * 4 + info["month_earth"], # 月柱合
        info["year_zodiac_num"] * 3 + info["good_god_count"],  # 年支 + 吉神數
        info["lunar_month"] * 7 + info["lunar_day"],    # 農曆月日合
    ]
    picks = _expand_to_pool(seeds, game.main_pool)
    return _fill_random(picks, game.main_pool, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 回測模式：用「當期實際開獎日」的黃曆預測該期
# ---------------------------------------------------------------------------

def make_almanac_strategy_for_backtest(strategy_fn):
    """包裝策略函式：回測時，把『下一期黃曆』替換為『當期實際黃曆』。

    因為 strategy 拿到的 draws 是回測時的歷史（不含當期），
    我們需要用當期日期計算黃曆。我們把當期日期偷藏在 history 末尾的偽 draw 裡。
    """
    def wrapped(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
        return strategy_fn(draws, game, rng)
    wrapped.__name__ = f"backtest_{strategy_fn.__name__}"
    return wrapped


# ---------------------------------------------------------------------------
# 策略登記
# ---------------------------------------------------------------------------

ALMANAC_STRATEGIES = {
    "lunar_day":         strategy_lunar_day,
    "stem_branch":       strategy_stem_branch,
    "wuxing":            strategy_wuxing,
    "clash":             strategy_clash,
    "lunar_mansion":     strategy_lunar_mansion,
    "almanac_combined":  strategy_almanac_combined,
}

ALMANAC_NAMES_ZH = {
    "lunar_day":         "農曆日數派",
    "stem_branch":       "六十甲子派",
    "wuxing":            "五行區間派",
    "clash":             "沖煞反向派",
    "lunar_mansion":     "二十八宿派",
    "almanac_combined":  "黃曆綜合派",
}
