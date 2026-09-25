import json
import logging
from collections import Counter
from datetime import datetime, timezone
from telegram.ext import ContextTypes

from config import DB_DIR, MARKET_EXCHANGES
from data_pipeline.fetcher import fetch_all_listed_tickers, fetch_stock_quote_history
from core_logic.strategy import evaluate_ticker

logger = logging.getLogger(__name__)
CACHE_FILE = DB_DIR / "signals_cache.json"


def _save_cache_to_disk(payload: dict) -> None:
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


def _fetch_market_universe() -> tuple[list[str], dict[str, int]]:
    """Fetch each exchange explicitly so a hidden single-exchange fallback is visible."""
    all_tickers: list[str] = []
    exchange_counts: dict[str, int] = {}

    for exchange in MARKET_EXCHANGES:
        try:
            raw = fetch_all_listed_tickers(exchange=exchange) or []
            tickers = [str(t).upper().strip() for t in raw if str(t).strip()]
            exchange_counts[exchange] = len(tickers)
            all_tickers.extend(tickers)
            logger.info(f"[Scanner] Universe {exchange}: {len(tickers)} mã")
        except Exception as exc:
            exchange_counts[exchange] = 0
            logger.exception(f"[Scanner] Không lấy được universe {exchange}: {exc}")

    # Deduplicate while keeping exchange order stable.
    unique = list(dict.fromkeys(all_tickers))
    return unique, exchange_counts


def _build_funnel(results: list[dict], no_price_data: int) -> dict:
    counter = Counter()
    for r in results:
        counter["evaluated"] += 1
        if r.get("prefilter_status") == "PASS":
            counter["prefilter_pass"] += 1
        elif r.get("prefilter_status") == "FAIL":
            counter["prefilter_fail"] += 1

        fstatus = str(r.get("fundamental_status", "NOT_EVALUATED"))
        if fstatus == "PASSED":
            counter["fundamental_pass"] += 1
        elif fstatus not in {"NOT_EVALUATED", ""}:
            counter["fundamental_checked_nonpass"] += 1

        if r.get("technical_status") == "PASS":
            counter["full_ta_pass"] += 1
        if r.get("status") == "BUY_CANDIDATE":
            counter["buy_candidate"] += 1
        if r.get("status") == "TECHNICAL_ONLY":
            counter["technical_only"] += 1
        if r.get("status") == "RESEARCH":
            counter["research"] += 1

    counter["no_price_data"] = no_price_data
    return dict(counter)


def _scan_market_sync() -> dict:
    """Scan configured exchanges with a measurable prefilter/fundamental/TA funnel."""
    tickers, exchange_counts = _fetch_market_universe()
    logger.info(
        "[Scanner] Bắt đầu quét %s mã trên %s",
        len(tickers),
        ", ".join(MARKET_EXCHANGES),
    )

    results = []
    no_price_data = 0

    for i, ticker in enumerate(tickers, 1):
        try:
            df = fetch_stock_quote_history(ticker, days=450)
            if df is None or df.empty:
                no_price_data += 1
                continue
            results.append(evaluate_ticker(ticker, df))
        except Exception as exc:
            logger.warning(f"[Scanner] Lỗi khi xử lý mã {ticker}: {exc}")

        if i % 50 == 0:
            logger.info(f"[Scanner] Đã xử lý {i}/{len(tickers)} mã...")

    funnel = _build_funnel(results, no_price_data)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exchanges": list(MARKET_EXCHANGES),
        "exchange_counts": exchange_counts,
        "total_listed": len(tickers),
        "total_scanned": len(results),
        "funnel": funnel,
        "results": results,
    }
    logger.info(
        "[Scanner] Hoàn tất: universe=%s, evaluated=%s, funnel=%s",
        len(tickers),
        len(results),
        funnel,
    )
    return payload


async def run_full_market_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    import asyncio
    try:
        payload = await asyncio.to_thread(_scan_market_sync)
        save_scan_result(
            context.application,
            payload["results"],
            payload["total_listed"],
            metadata={
                "exchanges": payload.get("exchanges", []),
                "exchange_counts": payload.get("exchange_counts", {}),
                "funnel": payload.get("funnel", {}),
            },
        )
    except Exception as e:
        logger.error(f"[Scanner] Job quét định kỳ thất bại: {e}")


def save_scan_result(application, results: list, total_listed: int, metadata: dict | None = None) -> dict:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_listed": total_listed,
        "total_scanned": len(results),
        "results": results,
    }
    if metadata:
        payload.update(metadata)
    application.bot_data["last_scan"] = payload
    _save_cache_to_disk(payload)
    return payload


def is_scan_fresh(application, max_age_minutes: int = 20) -> bool:
    scan = get_latest_scan(application)
    if not scan or not scan.get("results") or not scan.get("timestamp"):
        return False
    try:
        ts = datetime.fromisoformat(scan["timestamp"])
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        return age_minutes < max_age_minutes
    except Exception:
        return False


def get_latest_scan(application) -> dict:
    cached = application.bot_data.get("last_scan")
    if cached:
        return cached
    return _load_cache_from_disk()
