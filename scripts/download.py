"""下載台灣彩券歷史開獎資料。

用法：
  python scripts/download.py --game lotto649
  python scripts/download.py --game superlotto638 --since 103
  python scripts/download.py --game star3
  python scripts/download.py --game star4 --since-year 2008
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lotry.games import get_game, GAMES
from lotry.downloader import download_all, download_digit_all, save_draws, default_data_path


def main():
    parser = argparse.ArgumentParser(description="下載台灣彩券歷史開獎資料")
    parser.add_argument(
        "--game", required=True, choices=list(GAMES.keys()),
        help="遊戲代碼：lotto649 / superlotto638 / star3 / star4",
    )
    parser.add_argument(
        "--since", type=int, default=103,
        help="起始民國年（大樂透/威力彩用，預設 103 = 2014年）",
    )
    parser.add_argument(
        "--since-year", type=int, default=2008,
        help="起始西元年（三星彩/四星彩用，預設 2008）",
    )
    parser.add_argument(
        "--output", default=None,
        help="輸出 JSON 路徑（預設 data/<game>.json）",
    )
    args = parser.parse_args()

    game = get_game(args.game)
    out = args.output or default_data_path(game)

    if game.play_style == "digits":
        print(f"正在下載 {game.name} 開獎資料（{args.since_year} 年起）...")
        draws = download_digit_all(game, start_year=args.since_year)
    else:
        print(f"正在下載 {game.name} 開獎資料（民國 {args.since} 年起）...")
        draws = download_all(game, start_roc_year=args.since)

    print(f"共取得 {len(draws)} 期")

    if draws:
        save_draws(draws, out)
    else:
        print("⚠️  沒有取得任何資料，請確認網路連線。")


if __name__ == "__main__":
    main()
