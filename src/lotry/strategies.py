"""推算策略：從特徵分數中選出號碼。

每個策略是一個函式，簽名為：
    strategy(draws, game, rng) -> list[int]
回傳 main_pick 個號碼（已排序）。
"""

import math
import random as _random
from collections import Counter

from .games import GameDef
from .features import (
    frequency_scores,
    cold_scores,
    gap_scores,
    tail_digit_scores,
    markov_scores,
    zone_scores,
    sum_range,
    odd_even_ratio,
    high_low_ratio,
    consecutive_stats,
    all_feature_scores,
)


# ---------------------------------------------------------------------------
# 輔助
# ---------------------------------------------------------------------------

def _weighted_sample(scores: dict[int, float], k: int, rng: _random.Random) -> list[int]:
    """依分數加權不重複抽樣 k 個號碼。"""
    items = list(scores.items())
    selected = []
    for _ in range(k):
        if not items:
            break
        nums, weights = zip(*items)
        total = sum(weights)
        if total <= 0:
            # 均勻
            idx = rng.randint(0, len(items) - 1)
        else:
            r = rng.random() * total
            cumulative = 0.0
            idx = 0
            for i, w in enumerate(weights):
                cumulative += w
                if cumulative >= r:
                    idx = i
                    break
        selected.append(items[idx][0])
        items.pop(idx)
    return sorted(selected)


def _apply_constraints(
    candidates: list[int],
    game: GameDef,
    draws: list[dict],
    rng: _random.Random,
) -> list[int]:
    """對候選號碼施加和值 / 奇偶 / 大小約束，失敗則放棄約束直接回傳。"""
    lo, hi = sum_range(draws)
    target_odd, _ = odd_even_ratio(draws)
    mid = game.main_pool / 2
    target_hi, _ = high_low_ratio(draws, game)

    # 嘗試 500 次重新排列
    best = candidates[:]
    best_penalty = float("inf")
    pool = list(range(1, game.main_pool + 1))

    for _ in range(500):
        rng.shuffle(pool)
        pick = sorted(pool[: game.main_pick])
        s = sum(pick)
        if not (lo <= s <= hi):
            continue
        odd_cnt = sum(1 for n in pick if n % 2 == 1)
        hi_cnt = sum(1 for n in pick if n > mid)
        penalty = abs(odd_cnt - target_odd) + abs(hi_cnt - target_hi)
        if penalty < best_penalty:
            best_penalty = penalty
            best = pick
            if penalty < 1.0:
                break
    return best


# ---------------------------------------------------------------------------
# 策略 1：熱號策略
# ---------------------------------------------------------------------------

def strategy_hot(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """選近期最常出現的號碼。"""
    scores = frequency_scores(draws, game, window=30)
    return _weighted_sample(scores, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 2：冷號策略
# ---------------------------------------------------------------------------

def strategy_cold(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """選近期最少出現的號碼（逆向思維）。"""
    scores = cold_scores(draws, game, window=30)
    return _weighted_sample(scores, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 3：過期號策略（遺漏值最高）
# ---------------------------------------------------------------------------

def strategy_overdue(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """選「最久沒開過」的號碼。"""
    scores = gap_scores(draws, game)
    return _weighted_sample(scores, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 4：馬可夫策略
# ---------------------------------------------------------------------------

def strategy_markov(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """依上期號碼的馬可夫轉移機率選號。"""
    scores = markov_scores(draws, game)
    return _weighted_sample(scores, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 5：約束抽樣（和值 + 奇偶 + 大小）
# ---------------------------------------------------------------------------

def strategy_constrained(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """在歷史和值 / 奇偶 / 大小比的統計範圍內隨機抽樣。"""
    pool = list(range(1, game.main_pool + 1))
    rng.shuffle(pool)
    base = sorted(pool[: game.main_pick])
    return _apply_constraints(base, game, draws, rng)


# ---------------------------------------------------------------------------
# 策略 6：加權公式（集成各特徵）
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS = {
    "hot":    0.25,
    "cold":   0.05,
    "gap":    0.20,
    "tail":   0.10,
    "markov": 0.30,
    "zone":   0.10,
}


def strategy_weighted(
    draws: list[dict],
    game: GameDef,
    rng: _random.Random,
    weights: dict[str, float] | None = None,
) -> list[int]:
    """多特徵加權公式選號。"""
    w = weights or _DEFAULT_WEIGHTS
    feat = all_feature_scores(draws, game)
    combined: dict[int, float] = {}
    for n in range(1, game.main_pool + 1):
        score = 0.0
        for fname, fw in w.items():
            score += fw * feat.get(fname, {}).get(n, 0)
        combined[n] = score
    return _weighted_sample(combined, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略 7：純隨機（對照組）
# ---------------------------------------------------------------------------

def strategy_random(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """純隨機選號，作為回測對照基準。"""
    pool = list(range(1, game.main_pool + 1))
    return sorted(rng.sample(pool, game.main_pick))


# ---------------------------------------------------------------------------
# 策略登記
# ---------------------------------------------------------------------------

STRATEGIES = {
    "hot":         strategy_hot,
    "cold":        strategy_cold,
    "overdue":     strategy_overdue,
    "markov":      strategy_markov,
    "constrained": strategy_constrained,
    "weighted":    strategy_weighted,
    "random":      strategy_random,
}

STRATEGY_NAMES_ZH = {
    "hot":         "熱號策略",
    "cold":        "冷號策略",
    "overdue":     "過期號策略",
    "markov":      "馬可夫策略",
    "constrained": "約束抽樣",
    "weighted":    "加權公式",
    "random":      "純隨機（對照）",
}

# 整合「顛覆常理」反向策略
from .contrarian import CONTRARIAN_STRATEGIES, CONTRARIAN_NAMES_ZH
STRATEGIES.update(CONTRARIAN_STRATEGIES)
STRATEGY_NAMES_ZH.update(CONTRARIAN_NAMES_ZH)

# 整合「黃曆玄學」策略（給爸爸的浪漫）
from .almanac import ALMANAC_STRATEGIES, ALMANAC_NAMES_ZH
STRATEGIES.update(ALMANAC_STRATEGIES)
STRATEGY_NAMES_ZH.update(ALMANAC_NAMES_ZH)

# 整合「大新聞事件派」策略（明牌派）
from .events import EVENT_STRATEGIES, EVENT_NAMES_ZH
STRATEGIES.update(EVENT_STRATEGIES)
STRATEGY_NAMES_ZH.update(EVENT_NAMES_ZH)

# 整合「位數型彩」策略（三星彩 / 四星彩）
from .digit_strategies import DIGIT_STRATEGIES, DIGIT_NAMES_ZH
STRATEGIES.update(DIGIT_STRATEGIES)
STRATEGY_NAMES_ZH.update(DIGIT_NAMES_ZH)


def default_strategy_names(game: GameDef) -> list[str]:
    """依遊戲型態回傳預設回測策略。"""
    if game.play_style == "digits":
        return list(DIGIT_STRATEGIES.keys())
    return [name for name in STRATEGIES.keys() if name not in DIGIT_STRATEGIES]
