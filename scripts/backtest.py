"""回測所有策略。

用法：
    python scripts/backtest.py --game lotto649
    python scripts/backtest.py --game superlotto638 --min-history 100
    python scripts/backtest.py --game star3 --data data/star3.json
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lotry.games import get_game, GAMES
from lotry.data_loader import load_game_data
from lotry.backtest import run_backtest, format_backtest_summary


def main():
    parser = argparse.ArgumentParser(description="回測台灣彩券推算策略")
    parser.add_argument(
        "--game", required=True, choices=list(GAMES.keys()),
        help="遊戲代碼：lotto649 / superlotto638 / star3 / star4",
    )
    parser.add_argument(
        "--data", default=None,
        help="歷史資料 JSON 路徑（預設 data/<game>.json）",
    )
    parser.add_argument(
        "--min-history", type=int, default=50,
        help="最少需要幾期歷史才開始回測（預設 50）",
    )
    parser.add_argument(
        "--strategies", nargs="*", default=None,
        help="只回測指定策略（預設全部）",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="隨機種子（預設 42）",
    )
    args = parser.parse_args()

    game = get_game(args.game)
    print(f"載入 {game.name} 歷史資料 ...")
    draws = load_game_data(game, args.data)
    print(f"共 {len(draws)} 期")

    if len(draws) < args.min_history + 1:
        print(f"⚠️  資料不足 {args.min_history + 1} 期，無法回測。")
        return

    print(f"開始回測（min_history={args.min_history}, seed={args.seed}）...")
    results = run_backtest(
        draws, game,
        strategy_names=args.strategies,
        min_history=args.min_history,
        seed=args.seed,
    )

    print()
    print(format_backtest_summary(results))

    # 印出每個策略中 3+ 的個別紀錄
    for r in results:
        good = [rec for rec in r.records if rec.hits >= 3]
        if good:
            print(f"\n{r.strategy_zh}({r.strategy}) 中3+紀錄：")
            for rec in good[:20]:  # 最多印 20 筆
                if game.play_style == "digits":
                    pred_str = "".join(str(n) for n in rec.predicted)
                    act_str = "".join(str(n) for n in rec.actual)
                    marks = "".join("✓" if p == a else "·" for p, a in zip(rec.predicted, rec.actual))
                    print(f"  第{rec.term}期 預測[{pred_str}] 開獎[{act_str}] "
                          f"位置命中{rec.hits}位[{marks}]")
                else:
                    pred_str = " ".join(f"{n:02d}" for n in rec.predicted)
                    act_str = " ".join(f"{n:02d}" for n in rec.actual)
                    matched = sorted(set(rec.predicted) & set(rec.actual))
                    match_str = " ".join(f"{n:02d}" for n in matched)
                    print(f"  第{rec.term}期 預測[{pred_str}] 開獎[{act_str}] "
                          f"命中{rec.hits}個[{match_str}]")


if __name__ == "__main__":
    main()
