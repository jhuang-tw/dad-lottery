"""三星彩 / 四星彩專用策略。

三星彩與四星彩是『位數型彩』：
  - 三星彩：百位、十位、個位，每位 0-9，可重複，順序重要。
  - 四星彩：千位、百位、十位、個位，每位 0-9，可重複，順序重要。

因此不能沿用大樂透/威力彩的集合交集邏輯。
這裡的命中數採『位置命中』：預測 123、開獎 153 => 百位和個位中 2 位。
"""

import datetime
import random as _random
from collections import Counter, defaultdict

from .games import GameDef


def _digit_columns(draws: list[dict], digits: int) -> list[list[int]]:
    cols = [[] for _ in range(digits)]
    for draw in draws:
        nums = draw["numbers"]
        if len(nums) != digits:
            continue
        for pos, digit in enumerate(nums):
            cols[pos].append(int(digit))
    return cols


def _weighted_digit(scores: dict[int, float], rng: _random.Random) -> int:
    items = [(digit, max(score, 1e-6)) for digit, score in scores.items()]
    total = sum(score for _, score in items)
    r = rng.random() * total
    acc = 0.0
    for digit, score in items:
        acc += score
        if acc >= r:
            return digit
    return items[-1][0]


def _target_date(draws: list[dict], rng: _random.Random | None = None) -> datetime.date:
    if rng is not None and getattr(rng, "target_date", None):
        try:
            return datetime.date.fromisoformat(rng.target_date)  # type: ignore[attr-defined]
        except ValueError:
            pass
    if draws:
        try:
            return datetime.date.fromisoformat(draws[-1]["date"]) + datetime.timedelta(days=1)
        except (KeyError, ValueError):
            pass
    return datetime.date.today()


# ---------------------------------------------------------------------------
# 策略 1：位置熱碼
# ---------------------------------------------------------------------------

def strategy_digit_hot(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """每個位置選近期最常出現的 digit。"""
    cols = _digit_columns(draws[-80:], game.main_pick)
    out = []
    for col in cols:
        cnt = Counter(col)
        mx = max(cnt.values()) if cnt else 1
        scores = {d: cnt.get(d, 0) / mx for d in range(10)}
        out.append(_weighted_digit(scores, rng))
    return out


# ---------------------------------------------------------------------------
# 策略 2：位置冷碼
# ---------------------------------------------------------------------------

def strategy_digit_cold(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """每個位置選近期最少出現的 digit。"""
    cols = _digit_columns(draws[-80:], game.main_pick)
    out = []
    for col in cols:
        cnt = Counter(col)
        mx = max(cnt.values()) if cnt else 1
        scores = {d: 1.0 - (cnt.get(d, 0) / mx) + 0.01 for d in range(10)}
        out.append(_weighted_digit(scores, rng))
    return out


# ---------------------------------------------------------------------------
# 策略 3：位置馬可夫
# ---------------------------------------------------------------------------

def strategy_digit_markov(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """同一位置上一期 digit -> 下一期 digit 的轉移。"""
    if len(draws) < 2:
        return strategy_digit_random(draws, game, rng)

    trans = [defaultdict(Counter) for _ in range(game.main_pick)]
    for prev, nxt in zip(draws[:-1], draws[1:]):
        for pos in range(game.main_pick):
            trans[pos][prev["numbers"][pos]][nxt["numbers"][pos]] += 1

    last = draws[-1]["numbers"]
    out = []
    for pos, prev_digit in enumerate(last):
        cnt = trans[pos].get(prev_digit, Counter())
        total = sum(cnt.values()) or 1
        scores = {d: cnt.get(d, 0) / total for d in range(10)}
        out.append(_weighted_digit(scores, rng))
    return out


# ---------------------------------------------------------------------------
# 策略 4：和值約束
# ---------------------------------------------------------------------------

def strategy_digit_sum_band(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """產生符合近期 digit 和值區間的組合。"""
    recent = draws[-120:]
    sums = [sum(draw["numbers"]) for draw in recent]
    if not sums:
        return strategy_digit_random(draws, game, rng)
    avg = sum(sums) / len(sums)
    var = sum((s - avg) ** 2 for s in sums) / len(sums)
    sigma = var ** 0.5
    lo = avg - 1.2 * sigma
    hi = avg + 1.2 * sigma

    best = None
    best_penalty = float("inf")
    for _ in range(300):
        pick = [rng.randint(0, 9) for _ in range(game.main_pick)]
        total = sum(pick)
        penalty = 0.0 if lo <= total <= hi else min(abs(total - lo), abs(total - hi))
        if penalty < best_penalty:
            best = pick
            best_penalty = penalty
            if penalty == 0:
                break
    return best or strategy_digit_random(draws, game, rng)


# ---------------------------------------------------------------------------
# 策略 5：鏡像反向
# ---------------------------------------------------------------------------

def strategy_digit_mirror(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """把上一期每位 digit 做 9-d 反向。"""
    if not draws:
        return strategy_digit_random(draws, game, rng)
    return [9 - d for d in draws[-1]["numbers"]]


# ---------------------------------------------------------------------------
# 策略 6：日期數字學
# ---------------------------------------------------------------------------

def strategy_digit_date(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """用開獎日的年月日拆成 digit。"""
    d = _target_date(draws, rng)
    text = f"{d.year:04d}{d.month:02d}{d.day:02d}{d.timetuple().tm_yday:03d}"
    start = (d.toordinal() + game.main_pick) % (len(text) - game.main_pick + 1)
    return [int(ch) for ch in text[start:start + game.main_pick]]


# ---------------------------------------------------------------------------
# 策略 7：綜合公式
# ---------------------------------------------------------------------------

def strategy_digit_weighted(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """位置熱碼 + 位置冷碼 + 馬可夫的簡單集成。"""
    hot_cols = _digit_columns(draws[-80:], game.main_pick)

    markov_pick = strategy_digit_markov(draws, game, _random.Random(rng.randint(0, 10**9)))
    out = []
    for pos in range(game.main_pick):
        hot_cnt = Counter(hot_cols[pos])
        mx = max(hot_cnt.values()) if hot_cnt else 1
        scores = {}
        for d in range(10):
            hot = hot_cnt.get(d, 0) / mx
            cold = 1.0 - hot + 0.01
            markov = 1.0 if d == markov_pick[pos] else 0.0
            scores[d] = 0.45 * hot + 0.25 * cold + 0.30 * markov
        out.append(_weighted_digit(scores, rng))
    return out


# ---------------------------------------------------------------------------
# 策略 8：純隨機
# ---------------------------------------------------------------------------

def strategy_digit_random(draws: list[dict], game: GameDef, rng: _random.Random) -> list[int]:
    """每位 0-9 均勻隨機，可重複。"""
    _ = draws
    return [rng.randint(0, 9) for _ in range(game.main_pick)]


DIGIT_STRATEGIES = {
    "digit_hot":       strategy_digit_hot,
    "digit_cold":      strategy_digit_cold,
    "digit_markov":    strategy_digit_markov,
    "digit_sum_band":  strategy_digit_sum_band,
    "digit_mirror":    strategy_digit_mirror,
    "digit_date":      strategy_digit_date,
    "digit_weighted":  strategy_digit_weighted,
    "digit_random":    strategy_digit_random,
}

DIGIT_NAMES_ZH = {
    "digit_hot":       "位數熱碼",
    "digit_cold":      "位數冷碼",
    "digit_markov":    "位數馬可夫",
    "digit_sum_band":  "位數和值帶",
    "digit_mirror":    "位數鏡像",
    "digit_date":      "日期數字學",
    "digit_weighted":  "位數綜合公式",
    "digit_random":    "純隨機（對照）",
}


def generate_digit_picks(
    draws: list[dict],
    game: GameDef,
    n_picks: int = 5,
    seed: int | None = None,
) -> list[dict]:
    rng = _random.Random(seed)
    order = [
        "digit_weighted",
        "digit_markov",
        "digit_hot",
        "digit_cold",
        "digit_sum_band",
        "digit_mirror",
        "digit_date",
        "digit_random",
    ]
    picks = []
    for name in order[:n_picks]:
        fn = DIGIT_STRATEGIES[name]
        pred = fn(draws, game, _random.Random(rng.randint(0, 10**9)))
        picks.append({
            "numbers": pred,
            "basis": DIGIT_NAMES_ZH[name],
        })
    return picks


def format_digit_picks(picks: list[dict], game: GameDef) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"  {game.name} — 下一期推薦號碼")
    lines.append("=" * 60)
    lines.append("")
    for i, pick in enumerate(picks, 1):
        nums = "".join(str(d) for d in pick["numbers"])
        spaced = "  ".join(str(d) for d in pick["numbers"])
        lines.append(f"  第 {i} 組：{nums}    ({spaced})")
        lines.append(f"         依據：{pick['basis']}")
        lines.append("")
    lines.append("⚠️  三星彩/四星彩是位數型隨機事件，以上僅供娛樂與回測展示。")
    lines.append("")
    return "\n".join(lines)
