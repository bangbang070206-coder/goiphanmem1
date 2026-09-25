import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import pandas as pd

from config import DEFAULT_WATCHLIST

from database.db_manager import (
    save_price_history,
    get_price_history,
    save_financial_metrics,
    get_financial_metrics,
    save_industry_classifications,
    get_industry_classifications,
)

from data_pipeline.financial_loader import (
    parse_growth_and_cfo,
    parse_current_balance_sheet,
    calculate_roe_from_statements,
)

from data_pipeline.industry_loader import (
    fetch_industry_classification,
    filter_classification,
)

from data_pipeline.rate_limiter import throttle

from vnstock import Listing


# ============================================================
# VNSTOCK CONFIG
# ============================================================

# Tắt telemetry của vnstock để giảm thông báo không cần thiết.
os.environ["VNSTOCK_TELEMETRY"] = "off"

logger = logging.getLogger(__name__)


# ============================================================
# CACHE
# ============================================================

# Cache danh sách mã niêm yết theo sàn.
_LISTING_CACHE = {}

LISTING_CACHE_TTL_HOURS = 12


# Cache phân loại ngành.
_INDUSTRY_CACHE = {
    "data": None,
    "fetched_at": None,
}


# Cache VN30.
_VN30_CACHE = {
    "data": None,
    "fetched_at": None,
}


# ============================================================
# INDUSTRY
# ============================================================

def refresh_industry_classification(
    exchange: str = "HOSE",
    force_update: bool = False,
) -> list:
    """
    Load source-reported ICB classification
    and persist it for industry scans.
    """

    cached = _INDUSTRY_CACHE.get("data")
    fetched_at = _INDUSTRY_CACHE.get("fetched_at")

    if (
        cached is not None
        and fetched_at is not None
        and not force_update
    ):
        if (
            datetime.now() - fetched_at
        ).total_seconds() < LISTING_CACHE_TTL_HOURS * 3600:
            return cached

    try:
        rows = fetch_industry_classification(
            exchange=exchange
        )

        if rows:
            save_industry_classifications(rows)

            _INDUSTRY_CACHE["data"] = rows
            _INDUSTRY_CACHE["fetched_at"] = datetime.now()

            return rows

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as exc:
        logger.warning(
            "Không tải được phân loại ngành: %s",
            exc,
        )

    return get_industry_classifications()


def fetch_tickers_by_industry(
    industry_code: str,
    exchange: str = "HOSE",
) -> list:
    """
    Lấy danh sách mã theo ngành.
    """

    from core_logic.industry import get_industry_filter

    if get_industry_filter(industry_code) is None:
        return []

    rows = refresh_industry_classification(
        exchange=exchange
    )

    return [
        row["ticker"]
        for row in filter_classification(
            rows,
            industry_code,
        )
    ]


# ============================================================
# LISTING
# ============================================================

def fetch_all_listed_tickers(
    exchange: str = "HOSE",
):
    """
    Lấy toàn bộ mã niêm yết từ vnstock.

    Mapping:
        HOSE  -> HSX
        HNX   -> HNX
        UPCOM -> UPCOM
    """

    exchange_key = str(
        exchange or "HOSE"
    ).upper().strip()

    exchange_map = {
        "HOSE": "HSX",
        "HSX": "HSX",
        "HNX": "HNX",
        "UPCOM": "UPCOM",
    }

    vnstock_exchange = exchange_map.get(
        exchange_key,
        exchange_key,
    )

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    cached = _LISTING_CACHE.get(
        exchange_key
    )

    if cached:
        return cached

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    try:
        listing = Listing(
            source="VCI"
        )

        throttle()

        df = listing.symbols_by_exchange()

        if df is None or df.empty:
            logger.warning(
                "Lỗi khi gọi vnstock Listing API: "
                "dữ liệu listing rỗng."
            )
            return []

        # vnstock hiện tại dùng "symbol".
        if "symbol" not in df.columns:
            logger.warning(
                "Listing thiếu cột 'symbol'. "
                "Các cột hiện có: %s",
                list(df.columns),
            )
            return []

        # ----------------------------------------------------
        # FILTER EXCHANGE
        # ----------------------------------------------------

        if "exchange" in df.columns:
            df = df[
                df["exchange"]
                .astype(str)
                .str.upper()
                .str.strip()
                == vnstock_exchange
            ]

        # ----------------------------------------------------
        # SYMBOLS
        # ----------------------------------------------------

        tickers = (
            df["symbol"]
            .dropna()
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )

        # Remove duplicates.
        tickers = list(
            dict.fromkeys(tickers)
        )

        if not tickers:
            logger.warning(
                "Không tìm thấy mã nào cho sàn %s "
                "(vnstock=%s).",
                exchange_key,
                vnstock_exchange,
            )
            return []

        # Cache.
        _LISTING_CACHE[
            exchange_key
        ] = tickers

        logger.info(
            "Loaded %s mã cho %s (vnstock=%s).",
            len(tickers),
            exchange_key,
            vnstock_exchange,
        )

        return tickers

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as exc:

        logger.warning(
            "Lỗi khi gọi vnstock Listing API "
            "cho %s: %s",
            exchange_key,
            exc,
        )

        return []


# ============================================================
# VN30
# ============================================================

def fetch_vn30_tickers() -> list:
    """
    Lấy danh sách VN30 hiện tại từ vnstock.
    """

    now = datetime.now()

    cached = _VN30_CACHE.get("data")
    fetched_at = _VN30_CACHE.get("fetched_at")

    if (
        cached is not None
        and fetched_at is not None
    ):
        if (
            now - fetched_at
        ).total_seconds() < LISTING_CACHE_TTL_HOURS * 3600:
            return cached

    try:

        listing = Listing(
            source="VCI"
        )

        throttle()

        result = listing.symbols_by_group(
            group="VN30"
        )

        if hasattr(result, "tolist"):
            tickers = [
                str(t).upper()
                for t in result.tolist()
            ]
        else:
            tickers = [
                str(t).upper()
                for t in result
            ]

        if not tickers:
            raise ValueError(
                "Danh sách VN30 trả về rỗng"
            )

        _VN30_CACHE["data"] = tickers
        _VN30_CACHE["fetched_at"] = now

        logger.info(
            "Đã tải %s mã VN30 từ vnstock Listing API.",
            len(tickers),
        )

        return tickers

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as exc:

        logger.warning(
            "Lỗi khi gọi VN30: %s. "
            "Dùng DEFAULT_WATCHLIST dự phòng.",
            exc,
        )

        return DEFAULT_WATCHLIST


# ============================================================
# PRICE HISTORY
# ============================================================

def fetch_stock_quote_history(
    ticker: str,
    days: int = 450,
) -> pd.DataFrame:
    """
    Thu thập dữ liệu OHLCV.

    Ưu tiên:
        1. SQLite cache
        2. vnstock API

    Nếu API lỗi:
        trả dữ liệu cache hiện có.
    """

    ticker = ticker.upper()

    df_cached = get_price_history(
        ticker,
        limit=days,
    )

    # Với 450 ngày cần khoảng 420 phiên.
    required_sessions = (
        420
        if days >= 450
        else 200
    )

    # --------------------------------------------------------
    # CACHE ĐỦ DỮ LIỆU
    # --------------------------------------------------------

    if (
        not df_cached.empty
        and len(df_cached) >= required_sessions
    ):
        return df_cached

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    try:

        end_date = datetime.now().strftime(
            "%Y-%m-%d"
        )

        calendar_days = max(
            days,
            int(required_sessions * 1.6),
        )

        start_date = (
            datetime.now()
            - timedelta(days=calendar_days)
        ).strftime("%Y-%m-%d")

        # ----------------------------------------------------
        # Ưu tiên Quote API mới
        # ----------------------------------------------------

        try:

            from vnstock.api.quote import Quote

            throttle()

            q = Quote(
                symbol=ticker,
                source="VCI",
            )

            df = q.history(
                start=start_date,
                end=end_date,
            )

        except (
            Exception,
            SystemExit,
            BaseException,
        ):

            # Fallback API cũ.
            from vnstock import Vnstock

            throttle()

            stock = Vnstock().stock(
                symbol=ticker,
                source="VCI",
            )

            df = stock.quote.history(
                start=start_date,
                end=end_date,
            )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if df is not None and not df.empty:

            df = df.rename(
                columns={
                    "time": "date",
                    "Date": "date",
                }
            )

            if "date" in df.columns:

                df["date"] = (
                    df["date"]
                    .astype(str)
                    .str[:10]
                )

                save_price_history(
                    ticker,
                    df,
                )

                return get_price_history(
                    ticker,
                    limit=days,
                )

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as exc:

        logger.warning(
            "Lỗi khi gọi API vnstock cho %s: %s. "
            "Đang dùng dữ liệu cache...",
            ticker,
            exc,
        )

    return df_cached


# ============================================================
# FINANCIAL DATA
# ============================================================

def fetch_stock_financials(
    ticker: str,
    force_update: bool = False,
) -> Dict[str, Any]:
    """
    Thu thập BCTC và tính các chỉ số TTM.

    KHÔNG dùng stock.finance.ratio() nữa.

    Lý do:
        vnstock 2.6.0 có trường hợp ratio()
        trả dữ liệu rất cũ (ví dụ HPG chỉ tới 2018).

    Thay vào đó:

        income_statement()
            -> doanh thu
            -> LNST
            -> ROE TTM

        cash_flow()
            -> CFO

        balance_sheet()
            -> vốn chủ sở hữu
            -> nợ phải trả
            -> Debt/Equity

    Các chỉ số này đều lấy từ BCTC hiện tại.
    """

    ticker = ticker.upper()

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    cached = get_financial_metrics(
        ticker
    )

    if cached and not force_update:

        return cached

    # --------------------------------------------------------
    # DEFAULT RESULT
    # --------------------------------------------------------

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

        "status": "FETCH_FAILED",
    }

    # --------------------------------------------------------
    # VNSTOCK
    # --------------------------------------------------------

    try:

        from vnstock import Vnstock

        stock = Vnstock().stock(
            symbol=ticker,
            source="VCI",
        )

        # ====================================================
        # 1. INCOME STATEMENT
        # ====================================================

        try:

            throttle()

            df_inc = (
                stock.finance.income_statement(
                    period="quarter",
                    lang="vi",
                )
            )

        except (
            Exception,
            SystemExit,
            BaseException,
        ) as exc:

            logger.warning(
                "Không lấy được income_statement "
                "cho %s: %s",
                ticker,
                exc,
            )

            df_inc = None

        # ====================================================
        # 2. CASH FLOW
        # ====================================================

        try:

            throttle()

            df_cf = (
                stock.finance.cash_flow(
                    period="quarter",
                    lang="vi",
                )
            )

        except (
            Exception,
            SystemExit,
            BaseException,
        ) as exc:

            logger.warning(
                "Không lấy được cash_flow "
                "cho %s: %s",
                ticker,
                exc,
            )

            df_cf = None

        # ====================================================
        # 3. BALANCE SHEET
        # ====================================================

        try:

            throttle()

            df_bs = (
                stock.finance.balance_sheet(
                    period="quarter",
                    lang="vi",
                )
            )

        except (
            Exception,
            SystemExit,
            BaseException,
        ) as exc:

            logger.warning(
                "Không lấy được balance_sheet "
                "cho %s: %s",
                ticker,
                exc,
            )

            df_bs = None

        # ====================================================
        # KIỂM TRA CÓ DATA THẬT HAY KHÔNG
        # ====================================================

        if (
            df_inc is None
            and df_cf is None
            and df_bs is None
        ):
            raise ValueError(
                "Không lấy được bất kỳ bảng BCTC nào."
            )

        # ====================================================
        # 4. GROWTH + CFO
        # ====================================================

        parsed_cf = parse_growth_and_cfo(
            df_inc,
            df_cf,
        )

        # ====================================================
        # 5. BALANCE SHEET
        # ====================================================

        parsed_bs = parse_current_balance_sheet(
            df_bs,
        )

        # ====================================================
        # 6. ROE
        # ====================================================

        roe_current = calculate_roe_from_statements(
            df_inc,
            df_bs,
        )

        # ====================================================
        # 7. SAVE RESULTS
        # ====================================================

        fin_metrics["roe"] = roe_current

        fin_metrics["debt_to_equity"] = (
            parsed_bs.get(
                "debt_to_equity"
            )
        )

        fin_metrics["rev_growth"] = (
            parsed_cf.get(
                "rev_growth"
            )
        )

        fin_metrics["np_growth"] = (
            parsed_cf.get(
                "np_growth"
            )
        )

        fin_metrics["cfo"] = (
            parsed_cf.get(
                "cfo"
            )
        )

        fin_metrics["report_date"] = (
            parsed_bs.get(
                "report_date"
            )
        )

        # ====================================================
        # P/E + P/B
        # ====================================================
        #
        # Strategy 3.0 hiện tại không dùng P/E/P/B.
        #
        # Vì ratio() đang có vấn đề dữ liệu cũ,
        # KHÔNG lấy P/E/P/B từ ratio() nữa.
        #

        fin_metrics["pe"] = None
        fin_metrics["pb"] = None

        # ====================================================
        # STATUS
        # ====================================================

        fin_metrics["status"] = "OK"

        logger.info(
            "BCTC %s: report=%s | ROE=%s | D/E=%s | "
            "RevGrowth=%s | NPGrowth=%s | CFO=%s",
            ticker,
            fin_metrics["report_date"],
            fin_metrics["roe"],
            fin_metrics["debt_to_equity"],
            fin_metrics["rev_growth"],
            fin_metrics["np_growth"],
            fin_metrics["cfo"],
        )

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as exc:

        logger.warning(
            "Lỗi khi cào BCTC cho %s: %s. "
            "Đánh dấu FETCH_FAILED.",
            ticker,
            exc,
        )

        fin_metrics["status"] = "FETCH_FAILED"

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    save_financial_metrics(
        fin_metrics
    )

    return fin_metrics