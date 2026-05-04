"""走樣式回測引擎（Walk-Forward Backtest）。

核心邏輯：
  1. 從第 min_history 期開始，每期往前看，用「到前一期為止」的資料產生選號。
  2. 比對當期實際開獎號碼，統計命中數。
  3. 所有策略 + 對照組一起跑，輸出比較表。
"""

import random as _random
from dataclasses import dataclass, field

from .games import GameDef
from .strategies import STRATEGIES, STRATEGY_NAMES_ZH, default_strategy_names


@dataclass
class HitRecord:
    """單期命中紀錄。"""
    term: str
    strategy: str
    predicted: list[int]
    actual: list[int]
    hits: int


@dataclass
class BacktestResult:
    """整段回測結果。"""
    game: GameDef
    strategy: str
    strategy_zh: str
    records: list[HitRecord] = field(default_factory=list)

    @property
    def total_periods(self) -> int:
        return len(self.records)

    @property
    def avg_hits(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.hits for r in self.records) / len(self.records)

    @property
    def max_hits(self) -> int:
        return max((r.hits for r in self.records), default=0)

    def hit_distribution(self) -> dict[int, int]:
        """命中數分布：{命中數: 出現次數}。"""
        dist: dict[int, int] = {}
        for r in self.records:
            dist[r.hits] = dist.get(r.hits, 0) + 1
        return dict(sorted(dist.items()))


def run_backtest(
    draws: list[dict],
    game: GameDef,
    strategy_names: list[str] | None = None,
    min_history: int = 50,
    seed: int = 42,
    trials_per_period: int = 1,
) -> list[BacktestResult]:
    """執行走樣式回測。

    Args:
        draws: 已排序的歷史開獎資料。
        game: 遊戲定義。
        strategy_names: 要回測的策略名稱，None 表示全部。
        min_history: 最少需要幾期歷史才開始回測。
        seed: 隨機種子。
        trials_per_period: 每期每策略產生幾組選號（取最佳）。
    """
    names = strategy_names or default_strategy_names(game)
    results: dict[str, BacktestResult] = {}
    for sn in names:
        results[sn] = BacktestResult(
            game=game,
            strategy=sn,
            strategy_zh=STRATEGY_NAMES_ZH.get(sn, sn),
        )

    total = len(draws)
    for i in range(min_history, total):
        history = draws[:i]
        actual_numbers = draws[i]["numbers"]
        term = draws[i]["term"]

        for sn in names:
            fn = STRATEGIES[sn]
            best_hits = -1
            best_pred: list[int] = []

            for t in range(trials_per_period):
                rng = _random.Random(seed + i * 1000 + t)
                # 把當期日期掛在 rng 上，黃曆策略會讀取（其他策略無視）
                rng.target_date = draws[i].get("date")
                pred = fn(history, game, rng)
                h = _score_prediction(pred, actual_numbers, game)
                if h > best_hits:
                    best_hits = h
                    best_pred = pred

            results[sn].records.append(HitRecord(
                term=term,
                strategy=sn,
                predicted=best_pred,
                actual=_format_actual(actual_numbers, game),
                hits=best_hits,
            ))

    return [results[sn] for sn in names]


def _score_prediction(predicted: list[int], actual: list[int], game: GameDef) -> int:
    """計算命中數。

    number_set 遊戲：集合交集。
    digits 遊戲：位置命中，順序與重複 digit 都重要。
    """
    if game.play_style == "digits":
        return sum(1 for p, a in zip(predicted, actual) if p == a)
    return len(set(predicted) & set(actual))


def _format_actual(actual: list[int], game: GameDef) -> list[int]:
    if game.play_style == "digits":
        return list(actual)
    return sorted(actual)


def format_backtest_summary(results: list[BacktestResult]) -> str:
    """格式化回測結果摘要（純文字表格）。"""
    lines = []
    lines.append("=" * 72)
    lines.append(f"  回測結果摘要：{results[0].game.name if results else '?'}")
    lines.append(f"  回測期數：{results[0].total_periods if results else 0}")
    lines.append("=" * 72)
    lines.append("")
    header = f"{'策略':<18} {'平均命中':>8} {'最高命中':>8} {'中3+':>8} {'中4+':>8} {'中5+':>8}"
    lines.append(header)
    lines.append("-" * 72)

    for r in results:
        dist = r.hit_distribution()
        hit3p = sum(v for k, v in dist.items() if k >= 3)
        hit4p = sum(v for k, v in dist.items() if k >= 4)
        hit5p = sum(v for k, v in dist.items() if k >= 5)
        label = f"{r.strategy_zh}({r.strategy})"
        lines.append(
            f"{label:<18} {r.avg_hits:>8.3f} {r.max_hits:>8d} "
            f"{hit3p:>8d} {hit4p:>8d} {hit5p:>8d}"
        )

    lines.append("-" * 72)
    lines.append("")

    # 命中分布表
    lines.append("命中數分布：")
    all_hit_vals = set()
    for r in results:
        all_hit_vals.update(r.hit_distribution().keys())
    hit_vals = sorted(all_hit_vals)

    hdr = f"{'策略':<18}" + "".join(f" {h}中{' ':>3}" for h in hit_vals)
    lines.append(hdr)
    for r in results:
        dist = r.hit_distribution()
        label = f"{r.strategy_zh[:6]}({r.strategy[:4]})"
        row = f"{label:<18}" + "".join(f" {dist.get(h, 0):>5}" for h in hit_vals)
        lines.append(row)

    lines.append("")
    if results and results[0].game.play_style == "digits":
        lines.append("📌 提醒：三星彩/四星彩此處統計的是『位置命中』，完全正確另看 max_hits。")
        lines.append(f"   位數型純隨機位置命中期望值 ≈ {results[0].game.main_pick * 0.1:.3f}")
    else:
        lines.append("📌 提醒：平均命中 ≈ main_pick × main_pick / main_pool 即為純隨機期望值。")
        lines.append(f"   此遊戲純隨機期望值 ≈ {results[0].game.main_pick * results[0].game.main_pick / results[0].game.main_pool:.3f}" if results else "")
    lines.append("")
    return "\n".join(lines)
