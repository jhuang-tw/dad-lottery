"""特徵工程：從歷史開獎序列中萃取統計特徵。

每個特徵函式接收「到目前為止的所有歷史期」，回傳一個
{號碼: 分數} 字典，分數越高代表「越值得選」。
"""

from collections import Counter, defaultdict
import math

from .games import GameDef


# ---------------------------------------------------------------------------
# 輔助
# ---------------------------------------------------------------------------

def _all_numbers(draws: list[dict]) -> list[list[int]]:
    """取出所有期的主區號碼。"""
    return [d["numbers"] for d in draws]


# ---------------------------------------------------------------------------
# 1) 頻率分析 — 熱號 / 冷號
# ---------------------------------------------------------------------------

def frequency_scores(draws: list[dict], game: GameDef, window: int = 30) -> dict[int, float]:
    """近 window 期的出現頻率（歸一化到 0-1）。"""
    recent = _all_numbers(draws)[-window:]
    cnt = Counter()
    for nums in recent:
        cnt.update(nums)
    mx = max(cnt.values()) if cnt else 1
    return {n: cnt.get(n, 0) / mx for n in range(1, game.main_pool + 1)}


def cold_scores(draws: list[dict], game: GameDef, window: int = 30) -> dict[int, float]:
    """冷號分數：1 - 頻率分數。"""
    hot = frequency_scores(draws, game, window)
    return {n: 1.0 - v for n, v in hot.items()}


# ---------------------------------------------------------------------------
# 2) 遺漏值（Gap）
# ---------------------------------------------------------------------------

def gap_scores(draws: list[dict], game: GameDef) -> dict[int, float]:
    """每個號碼距離上次出現的期數，歸一化。"""
    last_seen: dict[int, int] = {}
    for i, d in enumerate(draws):
        for n in d["numbers"]:
            last_seen[n] = i
    total = len(draws)
    gaps = {}
    for n in range(1, game.main_pool + 1):
        g = total - last_seen.get(n, -1) - 1
        gaps[n] = g
    mx = max(gaps.values()) if gaps else 1
    return {n: gaps[n] / mx for n in gaps}


# ---------------------------------------------------------------------------
# 3) 和值區間偏好
# ---------------------------------------------------------------------------

def sum_range(draws: list[dict], window: int = 50) -> tuple[float, float]:
    """近 window 期主區號碼和值的 mean ± 1.5σ。"""
    recent = _all_numbers(draws)[-window:]
    sums = [sum(ns) for ns in recent]
    if not sums:
        return (0, 999)
    mu = sum(sums) / len(sums)
    var = sum((s - mu) ** 2 for s in sums) / len(sums)
    sigma = math.sqrt(var) if var > 0 else 1.0
    return (mu - 1.5 * sigma, mu + 1.5 * sigma)


# ---------------------------------------------------------------------------
# 4) 奇偶比
# ---------------------------------------------------------------------------

def odd_even_ratio(draws: list[dict], window: int = 50) -> tuple[float, float]:
    """近 window 期平均的 (奇數個數, 偶數個數)。"""
    recent = _all_numbers(draws)[-window:]
    if not recent:
        return (3.0, 3.0)
    odds = [sum(1 for n in ns if n % 2 == 1) for ns in recent]
    avg_odd = sum(odds) / len(odds)
    avg_even = len(recent[0]) - avg_odd
    return (avg_odd, avg_even)


# ---------------------------------------------------------------------------
# 5) 大小比（以中位數分界）
# ---------------------------------------------------------------------------

def high_low_ratio(draws: list[dict], game: GameDef, window: int = 50) -> tuple[float, float]:
    """近 window 期平均的 (大號個數, 小號個數)。"""
    mid = game.main_pool / 2
    recent = _all_numbers(draws)[-window:]
    if not recent:
        return (3.0, 3.0)
    highs = [sum(1 for n in ns if n > mid) for ns in recent]
    avg_hi = sum(highs) / len(highs)
    return (avg_hi, len(recent[0]) - avg_hi)


# ---------------------------------------------------------------------------
# 6) 連號偵測
# ---------------------------------------------------------------------------

def consecutive_stats(draws: list[dict], window: int = 50) -> float:
    """近 window 期平均連號對數。"""
    recent = _all_numbers(draws)[-window:]
    if not recent:
        return 0.0
    pairs = []
    for ns in recent:
        s = sorted(ns)
        p = sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)
        pairs.append(p)
    return sum(pairs) / len(pairs)


# ---------------------------------------------------------------------------
# 7) 尾數分布
# ---------------------------------------------------------------------------

def tail_digit_scores(draws: list[dict], game: GameDef, window: int = 50) -> dict[int, float]:
    """近 window 期各尾數(0-9)出現頻率 → 映射回每個號碼。"""
    recent = _all_numbers(draws)[-window:]
    tail_cnt: dict[int, int] = defaultdict(int)
    total = 0
    for ns in recent:
        for n in ns:
            tail_cnt[n % 10] += 1
            total += 1
    if total == 0:
        return {n: 0.5 for n in range(1, game.main_pool + 1)}
    tail_freq = {t: c / total for t, c in tail_cnt.items()}
    mx = max(tail_freq.values()) if tail_freq else 1
    scores = {}
    for n in range(1, game.main_pool + 1):
        scores[n] = tail_freq.get(n % 10, 0) / mx
    return scores


# ---------------------------------------------------------------------------
# 8) 簡易馬可夫轉移
# ---------------------------------------------------------------------------

def markov_scores(draws: list[dict], game: GameDef, order: int = 1) -> dict[int, float]:
    """一階馬可夫：上期出現的號碼「下一期最常伴隨」的號碼得分高。

    order 目前只支援 1。
    """
    all_nums = _all_numbers(draws)
    if len(all_nums) < 2:
        return {n: 0.5 for n in range(1, game.main_pool + 1)}

    # 建轉移計數
    trans: dict[int, Counter] = defaultdict(Counter)
    for i in range(len(all_nums) - 1):
        prev_set = all_nums[i]
        next_set = all_nums[i + 1]
        for p in prev_set:
            for nx in next_set:
                trans[p][nx] += 1

    # 用最後一期算分
    last = all_nums[-1]
    scores: dict[int, float] = defaultdict(float)
    for p in last:
        total = sum(trans[p].values()) if trans[p] else 1
        for n, c in trans[p].items():
            scores[n] += c / total

    mx = max(scores.values()) if scores else 1
    return {n: scores.get(n, 0) / mx for n in range(1, game.main_pool + 1)}


# ---------------------------------------------------------------------------
# 9) 區間分布（十位數分區）
# ---------------------------------------------------------------------------

def zone_scores(draws: list[dict], game: GameDef, window: int = 50) -> dict[int, float]:
    """依十位數分區(0x, 1x, 2x …)的出現頻率映射回號碼。"""
    recent = _all_numbers(draws)[-window:]
    zone_cnt: dict[int, int] = defaultdict(int)
    total = 0
    for ns in recent:
        for n in ns:
            zone_cnt[n // 10] += 1
            total += 1
    if total == 0:
        return {n: 0.5 for n in range(1, game.main_pool + 1)}
    zone_freq = {z: c / total for z, c in zone_cnt.items()}
    mx = max(zone_freq.values()) if zone_freq else 1
    return {n: zone_freq.get(n // 10, 0) / mx for n in range(1, game.main_pool + 1)}


# ---------------------------------------------------------------------------
# 彙總：取得全部特徵分數
# ---------------------------------------------------------------------------

def all_feature_scores(draws: list[dict], game: GameDef) -> dict[str, dict[int, float]]:
    """回傳 {特徵名: {號碼: 分數}} 字典。"""
    return {
        "hot":    frequency_scores(draws, game),
        "cold":   cold_scores(draws, game),
        "gap":    gap_scores(draws, game),
        "tail":   tail_digit_scores(draws, game),
        "markov": markov_scores(draws, game),
        "zone":   zone_scores(draws, game),
    }
