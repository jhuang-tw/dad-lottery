"""下載台灣彩券官方歷史開獎資料。

資料來源：台灣彩券 JSON API
  大樂透/威力彩（依期號查詢）：
    https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result?period=113000001
    https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result?period=113000001
  三星彩/四星彩（依月份查詢）：
    https://api.taiwanlottery.com/TLCAPIWeB/Lottery/3DResult?month=2026-01&endMonth=2026-12&pageNum=1&pageSize=500
    https://api.taiwanlottery.com/TLCAPIWeB/Lottery/4DResult?month=2026-01&endMonth=2026-12&pageNum=1&pageSize=500
"""

import json
import os
import ssl
import time
import urllib.request
import urllib.error
from typing import Optional

from .games import GameDef, GAMES

# 台灣彩券 API 的 SSL 憑證有時驗證會失敗
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_BASE_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery"

# API 回傳的 content key 對照（pool 型）
_RES_KEYS = {
    "lotto649": "lotto649Res",
    "superlotto638": "superLotto638Res",
}

# 三星彩/四星彩 API 設定
_DIGIT_API = {
    "star3": {"path": "3DResult", "res_key": "lotto3DRes", "num_key": "drawNumberAppear"},
    "star4": {"path": "4DResult", "res_key": "lotto4DRes", "num_key": "drawNumberAppear"},
}


def _api_url(game: GameDef) -> str:
    return f"{_BASE_URL}/{game.api_game_id}Result"


def _fetch_period(game: GameDef, period: int) -> Optional[dict]:
    """查詢單一期號，回傳原始 dict 或 None。"""
    url = f"{_api_url(game)}?period={period}"
    req = urllib.request.Request(url, headers={"User-Agent": "LotryBacktest/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data.get("content", {})
    if content.get("totalSize", 0) == 0:
        return None
    res_key = _RES_KEYS.get(game.code, "")
    items = content.get(res_key)
    if items and len(items) > 0:
        return items[0]
    return None


def _normalize_draw(game: GameDef, raw: dict) -> Optional[dict]:
    """把 API 回傳的一期原始資料正規化成統一格式。

    API 回傳的 drawNumberSize 陣列：前 main_pick 個為主區號碼，
    最後 1 個為特別號（大樂透）或第二區號碼（威力彩）。
    """
    try:
        period = raw.get("period", 0)
        draw_date = raw.get("lotteryDate", "")
        all_nums = raw.get("drawNumberSize", [])
        if len(all_nums) < game.main_pick:
            return None

        # 主區號碼（取前 main_pick 個，排序）
        nums = sorted(int(n) for n in all_nums[:game.main_pick])

        # 特別號
        bonus = []
        if game.bonus_pick > 0 and len(all_nums) > game.main_pick:
            b = int(all_nums[game.main_pick])
            if b > 0:
                bonus.append(b)

        return {
            "term": str(period),
            "date": draw_date.split("T")[0] if "T" in draw_date else draw_date,
            "numbers": nums,
            "bonus": bonus,
        }
    except (KeyError, ValueError, TypeError):
        return None


def _fetch_digit_month(game: GameDef, year: int, month: int) -> list[dict]:
    """抓取三星彩/四星彩某月份的所有開獎紀錄（自動分頁）。"""
    cfg = _DIGIT_API[game.code]
    month_str = f"{year}-{month:02d}"
    page_size = 100
    page = 1
    results = []
    while True:
        url = (f"{_BASE_URL}/{cfg['path']}?"
               f"month={month_str}&endMonth={month_str}&pageNum={page}&pageSize={page_size}")
        req = urllib.request.Request(url, headers={"User-Agent": "LotryBacktest/1.0"})
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("content", {})
        items = content.get(cfg["res_key"], []) or []
        for raw in items:
            try:
                nums = [int(n) for n in raw[cfg["num_key"]]]
                draw_date = raw.get("lotteryDate", "")
                rec = {
                    "term": str(raw["period"]),
                    "date": draw_date.split("T")[0] if "T" in draw_date else draw_date,
                    "numbers": nums,
                }
                results.append(rec)
            except (KeyError, ValueError, TypeError):
                continue
        total = content.get("totalSize", 0)
        if page * page_size >= total:
            break
        page += 1
    return results


def download_digit_all(game: GameDef, start_year: int = 2008) -> list[dict]:
    """下載三星彩或四星彩從 start_year 到今年的所有開獎紀錄。"""
    import datetime
    today = datetime.date.today()
    results: list[dict] = []

    for year in range(start_year, today.year + 1):
        end_month = 12 if year < today.year else today.month
        year_count = 0
        for month in range(1, end_month + 1):
            try:
                recs = _fetch_digit_month(game, year, month)
                results.extend(recs)
                year_count += len(recs)
            except (urllib.error.URLError, OSError) as exc:
                print(f"  [WARN] {year}-{month:02d} 下載失敗: {exc}")
            time.sleep(0.05)
        if year_count > 0:
            print(f"  {year} 年：{year_count} 期")

    results.sort(key=lambda r: r["term"])
    return results


def download_all(game: GameDef, start_roc_year: int = 103) -> list[dict]:
    """下載指定遊戲從 start_roc_year 到今年的所有開獎紀錄。

    民國年對照：103=2014, 113=2024, 114=2025, 115=2026
    每年每遊戲大約 50~120 期。
    三星彩/四星彩請改用 download_digit_all()，或直接用 scripts/download.py。
    """
    if game.play_style == "digits":
        return download_digit_all(game)

    import datetime
    current_roc = datetime.date.today().year - 1911
    results: list[dict] = []

    for roc_year in range(start_roc_year, current_roc + 1):
        consecutive_miss = 0
        seq = 1
        year_count = 0
        while consecutive_miss < 5 and seq <= 200:
            period = roc_year * 1000000 + seq
            try:
                raw = _fetch_period(game, period)
            except (urllib.error.URLError, OSError) as exc:
                print(f"  [WARN] 期 {period} 下載失敗: {exc}")
                consecutive_miss += 1
                seq += 1
                time.sleep(0.1)
                continue

            if raw is None:
                consecutive_miss += 1
                seq += 1
                continue

            consecutive_miss = 0
            rec = _normalize_draw(game, raw)
            if rec:
                results.append(rec)
                year_count += 1
            seq += 1
            # 禮貌延遲
            time.sleep(0.05)

        if year_count > 0:
            print(f"  民國 {roc_year} 年：{year_count} 期")

    results.sort(key=lambda r: r["term"])
    return results


def save_draws(draws: list[dict], path: str) -> None:
    """將開獎紀錄存成 JSON 檔。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(draws, f, ensure_ascii=False, indent=2)
    print(f"✓ 已儲存 {len(draws)} 期 → {path}")


def load_draws(path: str) -> list[dict]:
    """從 JSON 檔載入開獎紀錄。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_data_path(game: GameDef) -> str:
    """預設資料檔路徑。"""
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    return os.path.join(base, f"{game.code}.json")
