"""顛覆常理策略集（Contrarian Strategies）

核心思想：故意違反人類直覺、群體偏好與統計慣性。
這些策略的 hypothesis 是：
  1. 大多數人會跟著「常理」(熱號、平衡組合) 投注 → 即使中獎也要分獎金
  2. 真實隨機抽號其實「不偏好」常理組合，所以反向操作不會更差
  3. 偶爾會出現極端開獎（全奇/全冷/連號爆），反向策略能抓到這些尾巴事件

⚠️ 這仍是「對隨機事件的猜測」，期望值依然 = 純隨機。
   設計目的是給「相信玄學/反主流」的長輩一個系統化的浪漫公式。
"""

import math
import random as _random
from collections import Counter, defaultdict

from .games import GameDef
from .features import (
    frequency_scores,
    gap_scores,
    markov_scores,
    zone_scores,
    sum_range,
    _all_numbers,
)


# ---------------------------------------------------------------------------
# 共用：依分數加權抽樣（與 strategies.py 一致）
# ---------------------------------------------------------------------------

def _weighted_sample(scores: dict[int, float], k: int, rng: _random.Random) -> list[int]:
    items = [(n, max(s, 1e-6)) for n, s in scores.items()]
    selected = []
    for _ in range(k):
        if not items:
            break
        nums, weights = zip(*items)
        total = sum(weights)
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


def _topk_with_jitter(scores: dict[int, float], k: int, rng: _random.Random, top_n: int = 15) -> list[int]:
    """從前 top_n 名隨機抽 k 個，避免每次都選一樣。"""
    sorted_nums = sorted(scores.items(), key=lambda x: -x[1])
    pool = [n for n, _ in sorted_nums[:max(top_n, k)]]
    rng.shuffle(pool)
    return sorted(pool[:k])


# ---------------------------------------------------------------------------
# 1) 反熱號（極端冷號）：最近一年都沒怎麼出現的號
# ---------------------------------------------------------------------------

def strategy_anti_hot(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """選最近 100 期出現次數最少的號碼。"""
    recent = _all_numbers(draws)[-100:]
    cnt = Counter()
    for nums in recent:
        cnt.update(nums)
    # 完全沒出現的得最高分
    scores = {n: 1.0 / (1 + cnt.get(n, 0)) for n in range(1, game.main_pool + 1)}
    return _topk_with_jitter(scores, game.main_pick, rng, top_n=12)


# ---------------------------------------------------------------------------
# 2) 反區間：選歷史最少踩到的區間
# ---------------------------------------------------------------------------

def strategy_anti_zone(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """區間分數越低 → 反向選越優先。"""
    z = zone_scores(draws, game, window=80)
    inv = {n: 1.0 - v + 0.01 for n, v in z.items()}
    return _weighted_sample(inv, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 3) 鏡像翻轉：把上期號碼鏡射 n → pool+1-n
# ---------------------------------------------------------------------------

def strategy_mirror(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """直接把上期號碼鏡射過來。"""
    if not draws:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))
    last = draws[-1]["numbers"]
    mirrored = sorted({game.main_pool + 1 - n for n in last})
    # 若鏡射後不足（極端情況），補隨機
    if len(mirrored) < game.main_pick:
        remain = [n for n in range(1, game.main_pool + 1) if n not in mirrored]
        rng.shuffle(remain)
        mirrored = sorted(mirrored + remain[: game.main_pick - len(mirrored)])
    return mirrored[: game.main_pick]


# ---------------------------------------------------------------------------
# 4) 反馬可夫：上期號碼「最少跟著出現」的號
# ---------------------------------------------------------------------------

def strategy_anti_markov(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """馬可夫分數越低 → 反向越優先。"""
    m = markov_scores(draws, game)
    inv = {n: 1.0 - v + 0.01 for n, v in m.items()}
    return _weighted_sample(inv, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 5) 質數結界：只從質數池抽
# ---------------------------------------------------------------------------

def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(math.isqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def strategy_prime(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """全部從質數池抽號。"""
    primes = [n for n in range(1, game.main_pool + 1) if _is_prime(n)]
    if len(primes) >= game.main_pick:
        return sorted(rng.sample(primes, game.main_pick))
    # 質數不足則補非質數
    rest = [n for n in range(1, game.main_pool + 1) if n not in primes]
    rng.shuffle(rest)
    return sorted(primes + rest[: game.main_pick - len(primes)])


# ---------------------------------------------------------------------------
# 6) 費氏神秘：偏好費氏數列號
# ---------------------------------------------------------------------------

def _fibonacci_set(limit: int) -> set[int]:
    fib = {1, 2}
    a, b = 1, 2
    while b <= limit:
        a, b = b, a + b
        if a <= limit:
            fib.add(a)
    return fib


def strategy_fibonacci(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """費氏數列得高分；不足時補相鄰號碼。"""
    fib = _fibonacci_set(game.main_pool)
    fib_list = sorted(fib)
    if len(fib_list) >= game.main_pick:
        return sorted(rng.sample(fib_list, game.main_pick))
    # 不足，把相鄰也算進來
    extended = set(fib_list)
    for f in fib_list:
        if f - 1 >= 1:
            extended.add(f - 1)
        if f + 1 <= game.main_pool:
            extended.add(f + 1)
    pool = sorted(extended)
    if len(pool) >= game.main_pick:
        return sorted(rng.sample(pool, game.main_pick))
    rest = [n for n in range(1, game.main_pool + 1) if n not in pool]
    rng.shuffle(rest)
    return sorted(pool + rest[: game.main_pick - len(pool)])


# ---------------------------------------------------------------------------
# 7) Echo Last：直接複製上期（賭「重複開出」這種反直覺事件）
# ---------------------------------------------------------------------------

def strategy_echo_last(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """直接押上期號碼。"""
    if not draws:
        pool = list(range(1, game.main_pool + 1))
        return sorted(rng.sample(pool, game.main_pick))
    return sorted(draws[-1]["numbers"])[: game.main_pick]


# ---------------------------------------------------------------------------
# 8) 反約束：故意違反和值/奇偶/大小常規
# ---------------------------------------------------------------------------

def strategy_anti_constraint(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """挑歷史「不會出現」的極端組合：和值極大或極小、全奇或全偶。"""
    lo, hi = sum_range(draws)
    pool = list(range(1, game.main_pool + 1))

    best: list[int] | None = None
    best_score = -1.0

    for _ in range(800):
        rng.shuffle(pool)
        pick = sorted(pool[: game.main_pick])
        s = sum(pick)
        odd = sum(1 for n in pick if n % 2 == 1)
        even = game.main_pick - odd
        # 反常識分數：和值越偏離區間、奇偶越偏（全奇或全偶）越好
        sum_dev = max(lo - s, s - hi, 0)
        odd_dev = abs(odd - game.main_pick / 2)
        consec = sum(1 for i in range(len(pick) - 1) if pick[i + 1] - pick[i] == 1)
        score = sum_dev * 0.05 + odd_dev * 0.5 + consec * 0.3
        if score > best_score:
            best_score = score
            best = pick

    return best or sorted(rng.sample(list(range(1, game.main_pool + 1)), game.main_pick))


# ---------------------------------------------------------------------------
# 9) Pi Digits：用圓周率小數位生成號碼（玄學派）
# ---------------------------------------------------------------------------

# 圓周率前 200 位（夠用了）
_PI_DIGITS = (
    "1415926535897932384626433832795028841971693993751058209749445923"
    "0781640628620899862803482534211706798214808651328230664709384460"
    "9550582231725359408128481117450284102701938521105559644622948954"
    "9303819644288109756659334461284756482337867831652712019091"
)


def strategy_pi(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """從 π 小數位中依序取 2 位數，落在 [1, main_pool] 內就採用，去重直到湊滿。"""
    # 用回測期數當位移，讓每期都不同
    offset = (len(draws) * 7) % (len(_PI_DIGITS) - 60)
    digits = _PI_DIGITS[offset:] + _PI_DIGITS[:offset]
    picked: list[int] = []
    seen: set[int] = set()
    i = 0
    while len(picked) < game.main_pick and i < len(digits) - 1:
        n = int(digits[i:i + 2])
        if 1 <= n <= game.main_pool and n not in seen:
            picked.append(n)
            seen.add(n)
        i += 1
    # 若 π 用完仍不足（理論上不會），補隨機
    while len(picked) < game.main_pick:
        n = rng.randint(1, game.main_pool)
        if n not in seen:
            picked.append(n)
            seen.add(n)
    return sorted(picked)


# ---------------------------------------------------------------------------
# 10) 反加權集成：把所有「合理」特徵分數倒過來
# ---------------------------------------------------------------------------

def strategy_anti_ensemble(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """把熱號/馬可夫/區間都倒過來，做一個全面反向集成。"""
    hot = frequency_scores(draws, game, window=30)
    mk = markov_scores(draws, game)
    zn = zone_scores(draws, game, window=80)
    gp = gap_scores(draws, game)

    combined: dict[int, float] = {}
    for n in range(1, game.main_pool + 1):
        # 熱號越低越好(0.3) + 馬可夫越低越好(0.3) + 區間越低越好(0.2) + 遺漏越久越好(0.2)
        score = (
            0.30 * (1.0 - hot.get(n, 0))
            + 0.30 * (1.0 - mk.get(n, 0))
            + 0.20 * (1.0 - zn.get(n, 0))
            + 0.20 * gp.get(n, 0)
        )
        combined[n] = score

    return _weighted_sample(combined, game.main_pick, rng)


# ---------------------------------------------------------------------------
# 策略登記
# ---------------------------------------------------------------------------

CONTRARIAN_STRATEGIES = {
    "anti_hot":         strategy_anti_hot,
    "anti_zone":        strategy_anti_zone,
    "mirror":           strategy_mirror,
    "anti_markov":      strategy_anti_markov,
    "prime":            strategy_prime,
    "fibonacci":        strategy_fibonacci,
    "echo_last":        strategy_echo_last,
    "anti_constraint":  strategy_anti_constraint,
    "pi":               strategy_pi,
    "anti_ensemble":    strategy_anti_ensemble,
}

CONTRARIAN_NAMES_ZH = {
    "anti_hot":         "反熱號",
    "anti_zone":        "反區間",
    "mirror":           "鏡像翻轉",
    "anti_markov":      "反馬可夫",
    "prime":            "質數結界",
    "fibonacci":        "費氏神秘",
    "echo_last":        "上期重押",
    "anti_constraint":  "反常識組合",
    "pi":               "圓周率玄學",
    "anti_ensemble":    "反向集成",
}
