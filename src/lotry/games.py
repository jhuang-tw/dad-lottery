"""遊戲定義：大樂透 / 威力彩 / 三星彩 / 四星彩 規則常數。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameDef:
    """一種彩券的規則定義。"""
    name: str           # 中文名
    code: str           # 內部代碼
    main_pool: int      # 主區號碼上限
    main_pick: int      # 主區要選幾個
    bonus_pool: int     # 特別號上限（0 = 無特別號）
    bonus_pick: int     # 特別號要選幾個
    api_game_id: str    # 台灣彩券官網 API 的 game 參數
    play_style: str = "number_set"  # number_set=不重複號碼池；digits=位數型彩


LOTTO649 = GameDef(
    name="大樂透",
    code="lotto649",
    main_pool=49,
    main_pick=6,
    bonus_pool=49,     # 特別號從同一池 1-49
    bonus_pick=1,
    api_game_id="Lotto649",
)

SUPER_LOTTO638 = GameDef(
    name="威力彩",
    code="superlotto638",
    main_pool=38,
    main_pick=6,
    bonus_pool=8,      # 第二區 1-8
    bonus_pick=1,
    api_game_id="SuperLotto638",
)

STAR3 = GameDef(
    name="三星彩",
    code="star3",
    main_pool=9,       # 每一位 0-9，這裡代表最大 digit
    main_pick=3,       # 百/十/個三位
    bonus_pool=0,
    bonus_pick=0,
    api_game_id="Lotto3D",
    play_style="digits",
)

STAR4 = GameDef(
    name="四星彩",
    code="star4",
    main_pool=9,       # 每一位 0-9，這裡代表最大 digit
    main_pick=4,       # 千/百/十/個四位
    bonus_pool=0,
    bonus_pick=0,
    api_game_id="Lotto4D",
    play_style="digits",
)

GAMES = {
    "lotto649": LOTTO649,
    "superlotto638": SUPER_LOTTO638,
    "star3": STAR3,
    "star4": STAR4,
}


def get_game(code: str) -> GameDef:
    """依代碼取得遊戲定義，不存在則 raise KeyError。"""
    return GAMES[code]
