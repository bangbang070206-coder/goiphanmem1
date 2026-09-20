import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pandas as pd

from config import DEFAULT_WATCHLIST
from database.db_manager import (
    save_price_history, get_price_history,
    save_financial_metrics, get_financial_metrics
)
from data_pipeline.financial_loader import parse_financial_ratio, parse_growth_and_cfo
from data_pipeline.anti_blocking import safe_request
from data_pipeline.rate_limiter import throttle

# Tắt telemetry của vnstock để tăng tốc
os.environ['VNSTOCK_TELEMETRY'] = 'off'
logger = logging.getLogger(__name__)

# Cache đơn giản trong bộ nhớ cho danh sách mã niêm yết (tránh gọi API mỗi lần /signals)
_LISTING_CACHE = {"data": None, "fetched_at": None}
LISTING_CACHE_TTL_HOURS = 12  # Làm mới danh sách mã mỗi 12 giờ

def fetch_all_listed_tickers(exchange: str = "HOSE") -> list:
    """
    Gọi API vnstock (Listing) để lấy TOÀN BỘ danh sách mã cổ phiếu đang niêm yết,
    thay vì dùng danh sách cứng DEFAULT_WATCHLIST.
    Có cache trong bộ nhớ (TTL 12h) để tránh gọi API lặp lại liên tục trong ngày.
    """
    now = datetime.now()
    cached = _LISTING_CACHE.get("data")
    fetched_at = _LISTING_CACHE.get("fetched_at")

    if cached is not None and fetched_at is not None:
        if (now - fetched_at).total_seconds() < LISTING_CACHE_TTL_HOURS * 3600:
            return cached

    try:
        from vnstock import Listing
        listing = Listing(source='VCI')

        throttle()
        try:
            # Ưu tiên lọc đúng sàn (mặc định HOSE, theo phạm vi Chiến lược số 1)
            df = listing.symbols_by_exchange()
            if df is not None and not df.empty and 'exchange' in df.columns:
                df = df[df['exchange'].astype(str).str.upper() == exchange.upper()]
        except Exception:
            df = listing.all_symbols()

        if df is None or df.empty or 'ticker' not in df.columns:
            raise ValueError("Danh sách mã trả về rỗng hoặc thiếu cột 'ticker'")

        tickers = df['ticker'].dropna().astype(str).str.upper().unique().tolist()
        _LISTING_CACHE["data"] = tickers
        _LISTING_CACHE["fetched_at"] = now
        logger.info(f"Đã tải {len(tickers)} mã niêm yết từ vnstock Listing API (sàn {exchange}).")
        return tickers

    except (Exception, SystemExit, BaseException) as e:
        logger.warning(f"Lỗi khi gọi vnstock Listing API: {e}. Dùng DEFAULT_WATCHLIST dự phòng.")
        return DEFAULT_WATCHLIST

_VN30_CACHE = {"data": None, "fetched_at": None}

def fetch_vn30_tickers() -> list:
    """
    Gọi API vnstock (Listing.symbols_by_group) để lấy danh sách 30 mã trong rổ VN30
    tại thời điểm thực - dùng cho chế độ quét nhanh (live, không cần chờ job nền).
    """
    now = datetime.now()
    cached = _VN30_CACHE.get("data")
    fetched_at = _VN30_CACHE.get("fetched_at")
    if cached is not None and fetched_at is not None:
        if (now - fetched_at).total_seconds() < LISTING_CACHE_TTL_HOURS * 3600:
            return cached

    try:
        from vnstock import Listing
        listing = Listing(source='VCI')
        throttle()
        result = listing.symbols_by_group(group='VN30')

        if hasattr(result, 'tolist'):
            tickers = [str(t).upper() for t in result.tolist()]
        else:
            tickers = [str(t).upper() for t in result]

        if not tickers:
            raise ValueError("Danh sách VN30 trả về rỗng")

        _VN30_CACHE["data"] = tickers
        _VN30_CACHE["fetched_at"] = now
        logger.info(f"Đã tải {len(tickers)} mã VN30 từ vnstock Listing API.")
        return tickers

    except (Exception, SystemExit, BaseException) as e:
        logger.warning(f"Lỗi khi gọi vnstock Listing.symbols_by_group('VN30'): {e}. Dùng DEFAULT_WATCHLIST dự phòng.")
        return DEFAULT_WATCHLIST

def fetch_stock_quote_history(ticker: str, days: int = 450) -> pd.DataFrame:
    """
    Thu thập dữ liệu nến lịch sử OHLCV:
    - Ưu tiên 1: Đọc ngay từ SQLite cache cục bộ (phản hồi trong 0.002s, không tốn quota API)
    - Ưu tiên 2: Nếu chưa có trong cache thì mới gọi API để lưu vào database
    """
    ticker = ticker.upper()
    df_cached = get_price_history(ticker, limit=days)
    
    # Nếu cache đã có sẵn dữ liệu lịch sử hợp lệ (>= 200 nến), sử dụng ngay lập tức
    if not df_cached.empty and len(df_cached) >= 200:
        return df_cached

    # Gọi API vnstock để nạp dữ liệu lần đầu nếu DB chưa có
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        try:
            from vnstock.api.quote import Quote
            throttle()
            q = Quote(symbol=ticker, source='VCI')
            df = q.history(start=start_date, end=end_date)
        except (Exception, SystemExit, BaseException):
            from vnstock import Vnstock
            throttle()
            stock = Vnstock().stock(symbol=ticker, source='VCI')
            df = stock.quote.history(start=start_date, end=end_date)
        
        if df is not None and not df.empty:
            # Chuẩn hóa tên cột
            df = df.rename(columns={
                'time': 'date',
                'Date': 'date'
            })
            if 'date' in df.columns:
                df['date'] = df['date'].astype(str).str[:10]
                save_price_history(ticker, df)
                return get_price_history(ticker, limit=days)
    except (Exception, SystemExit, BaseException) as e:
        logger.warning(f"Lỗi khi gọi API vnstock cho {ticker}: {e}. Đang dùng dữ liệu cache...")
        
    # Trả về dữ liệu trong cache nếu API lỗi
    return df_cached

def fetch_stock_financials(ticker: str, force_update: bool = False) -> Dict[str, Any]:
    """
    Thu thập dữ liệu Báo cáo tài chính và tính toán chỉ số TTM:
    - Kiểm tra SQLite cache trước (chu kỳ BCTC tính theo quý, cache 30 ngày)
    - Gọi vnstock lấy tỷ số tài chính, KQKD và LCTT
    """
    ticker = ticker.upper()
    cached = get_financial_metrics(ticker)
    
    if cached and not force_update:
        # Nếu đã có trong DB thì sử dụng lại
        return cached

    # Khung dữ liệu mặc định: KHÔNG bịa số liệu tài chính giả định.
    # Trước đây bản cũ đặt sẵn roe=0.18, debt_to_equity=0.85, is_passed=1... ngay cả khi
    # chưa gọi API thành công -> nếu API lỗi, hệ thống âm thầm coi mã đó "ĐẠT BCTC" bằng
    # số liệu bịa, sai lệch nghiêm trọng cho một hệ thống ra tín hiệu Mua/Bán thật.
    # Giờ: nếu không lấy được dữ liệu thật, các trường ở None -> fundamental_filter.py
    # sẽ báo rõ "DATA_UNAVAILABLE" thay vì ngộ nhận là đã ĐẠT.
    fin_metrics = {
        "ticker": ticker,
        "report_date": None,
        "roe": None,
        "debt_to_equity": None,
        "rev_growth": None,
        "np_growth": None,
        "cfo": None,
        "eps": None,
        "pe": None,
        "pb": None,
        "status": "FETCH_FAILED"
    }

    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol=ticker, source='VCI')
        
        # 1. Lấy bảng tỷ số tài chính
        throttle()
        df_ratio = stock.finance.ratio(period='quarter', lang='vi')
        parsed_ratio = parse_financial_ratio(df_ratio)
        
        # 2. Lấy bảng KQKD và Lưu chuyển tiền tệ
        try:
            throttle()
            df_inc = stock.finance.income_statement(period='quarter', lang='vi')
        except Exception:
            df_inc = None
            
        try:
            throttle()
            df_cf = stock.finance.cash_flow(period='quarter', lang='vi')
        except Exception:
            df_cf = None
            
        parsed_cf = parse_growth_and_cfo(df_inc, df_cf)
        
        fin_metrics["roe"] = parsed_ratio.get("roe")
        fin_metrics["debt_to_equity"] = parsed_ratio.get("debt_to_equity")
        fin_metrics["pe"] = parsed_ratio.get("pe")
        fin_metrics["pb"] = parsed_ratio.get("pb")
        fin_metrics["report_date"] = parsed_ratio.get("report_date")
        fin_metrics["rev_growth"] = parsed_cf["rev_growth"]
        fin_metrics["np_growth"] = parsed_cf["np_growth"]
        fin_metrics["cfo"] = parsed_cf["cfo"]
        fin_metrics["status"] = "OK"
        
    except (Exception, SystemExit, BaseException) as e:
        logger.warning(f"Lỗi khi cào BCTC cho {ticker}: {e}. Đánh dấu DATA_UNAVAILABLE thay vì dùng số liệu bịa.")
        fin_metrics["status"] = "FETCH_FAILED"
        
    # Lưu vào SQLite (kể cả khi fetch thất bại, để không tốn công gọi lại API ngay lập tức -
    # nhưng lưu ý: fetch_stock_financials không tự cache 30 ngày cho trạng thái FETCH_FAILED,
    # nên lần gọi tiếp theo sẽ thử lại. Cần chỉnh get_financial_metrics/save_financial_metrics
    # trong database/db_manager.py nếu muốn có TTL riêng cho trạng thái lỗi.)
    save_financial_metrics(fin_metrics)
    return fin_metrics
