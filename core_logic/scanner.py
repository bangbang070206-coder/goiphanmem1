import json
import logging
import time
from datetime import datetime, timezone
from telegram.ext import ContextTypes

from config import DB_DIR, SIGNALS_SCAN_DELAY_SECONDS
from data_pipeline.fetcher import fetch_all_listed_tickers, fetch_stock_quote_history
from core_logic.strategy import evaluate_ticker

logger = logging.getLogger(__name__)

CACHE_FILE = DB_DIR / "signals_cache.json"

# ==========================================
# QUÉT ĐỊNH KỲ TOÀN THỊ TRƯỜNG (chạy nền qua JobQueue)
# - Không tính lại mỗi khi user bấm /signals nữa.
# - Chạy trong thread riêng (asyncio.to_thread) để KHÔNG làm treo bot
#   trong lúc quét (bot vẫn trả lời /start, /check... bình thường).
# ==========================================

def _save_cache_to_disk(payload: dict) -> None:
    """Lưu kết quả quét ra file JSON để /signals vẫn đọc được ngay cả khi
    bot vừa khởi động lại và job định kỳ chưa kịp chạy lần đầu."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"[Scanner] Không thể ghi cache tín hiệu ra đĩa: {e}")


def _load_cache_from_disk() -> dict:
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[Scanner] Không thể đọc cache tín hiệu từ đĩa: {e}")
    return {}


def _scan_market_sync() -> dict:
    """Phần việc NẶNG (gọi API cho từng mã) - chạy đồng bộ trong thread riêng."""
    tickers = fetch_all_listed_tickers(exchange="HOSE")
    logger.info(f"[Scanner] Bắt đầu quét định kỳ {len(tickers)} mã trên HOSE...")

    results = []
    for i, ticker in enumerate(tickers, 1):
        try:
            df = fetch_stock_quote_history(ticker, days=450)
            if df is not None and not df.empty:
                res = evaluate_ticker(ticker, df)
                results.append(res)
        except Exception as e:
            logger.warning(f"[Scanner] Lỗi khi xử lý mã {ticker}: {e}")

        if i % 50 == 0:
            logger.info(f"[Scanner] Đã xử lý {i}/{len(tickers)} mã...")

        # Nghỉ nhẹ giữa các mã để không dồn dập gọi API (đa số lần sau sẽ ăn cache SQLite nên rất nhanh)
        time.sleep(SIGNALS_SCAN_DELAY_SECONDS)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_listed": len(tickers),
        "total_scanned": len(results),
        "results": results,
    }
    logger.info(f"[Scanner] Hoàn tất: {len(results)}/{len(tickers)} mã có dữ liệu hợp lệ.")
    return payload


async def run_full_market_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback cho JobQueue. Chạy phần việc nặng trong thread riêng để không
    chặn vòng lặp async của bot (bot vẫn phản hồi tin nhắn khác trong lúc quét)."""
    import asyncio
    try:
        payload = await asyncio.to_thread(_scan_market_sync)
        context.application.bot_data["last_scan"] = payload
        _save_cache_to_disk(payload)
    except Exception as e:
        logger.error(f"[Scanner] Job quét định kỳ thất bại: {e}")


def get_latest_scan(application) -> dict:
    """Lấy kết quả quét gần nhất: ưu tiên bộ nhớ (bot_data, nhanh),
    fallback ra file cache trên đĩa (khi bot vừa khởi động lại)."""
    cached = application.bot_data.get("last_scan")
    if cached:
        return cached
    return _load_cache_from_disk()
