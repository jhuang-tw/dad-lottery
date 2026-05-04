"""資料載入與快取管理。"""

from .downloader import load_draws, default_data_path
from .games import GameDef


def load_game_data(game: GameDef, path: str | None = None) -> list[dict]:
    """載入指定遊戲的歷史開獎資料。"""
    p = path or default_data_path(game)
    draws = load_draws(p)
    if game.play_style == "digits":
        for d in draws:
            d["numbers"] = _normalize_digits(d, game.main_pick)
            d["bonus"] = []
        return draws

    # 確保號碼都是 sorted int list（號碼池型遊戲不看順序）
    for d in draws:
        d["numbers"] = sorted(int(x) for x in d["numbers"])
        d["bonus"] = [int(x) for x in d.get("bonus", [])]
    return draws


def _normalize_digits(draw: dict, digits: int) -> list[int]:
    """把三星彩/四星彩資料正規化成固定長度 digit list。

    支援格式：
      {"numbers": [1, 2, 3]}
      {"numbers": "123"}
      {"number": "123"}
      {"digits": "123"}
    """
    raw = draw.get("numbers")
    if raw is None:
        raw = draw.get("number", draw.get("digits"))

    if isinstance(raw, int):
        text = str(raw).zfill(digits)
        vals = [int(ch) for ch in text]
    elif isinstance(raw, str):
        text = raw.strip().replace(" ", "").replace("-", "")
        vals = [int(ch) for ch in text]
    else:
        vals = [int(x) for x in raw]

    if len(vals) != digits:
        raise ValueError(f"位數資料長度錯誤：需要 {digits} 位，實際 {len(vals)} 位，資料={draw}")
    if any(v < 0 or v > 9 for v in vals):
        raise ValueError(f"位數資料只能是 0-9，資料={draw}")
    return vals
