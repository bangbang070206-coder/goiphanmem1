import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from data_pipeline.rate_limiter import throttle

logger = logging.getLogger(__name__)

# ICB leaf names are mapped to application filter codes. The source code/name
# remains in every record so an unmapped source classification is auditable.
INDUSTRY_NAME_RULES = {
    "banking": ("Ngân hàng", "Banks"),
    "securities": ("Chứng khoán", "Securities"),
    "real_estate": ("Bất động sản", "Real Estate"),
    "steel": ("Thép", "Iron & Steel"),
    "oil_gas": ("Dầu khí", "Oil & Gas"),
    "electricity": ("Điện", "Electricity", "Renewable Electricity"),
    "retail": ("Bán lẻ", "Retail"),
    "chemical": ("Hóa chất", "Chemicals"),
    "transport_port": ("Vận tải", "Transportation", "Cảng biển", "Marine Ports"),
    "seafood": ("Thủy sản", "Fishing & Farming", "Food Producers"),
    "textile": ("Dệt may", "Clothing & Accessories", "Textiles"),
    "food_beverage": ("Thực phẩm", "Đồ uống", "Food & Beverage"),
    "pharmaceuticals": ("Dược phẩm", "Pharmaceuticals"),
    "construction": ("Xây dựng", "Construction & Materials"),
    "industrial_parks": ("Khu công nghiệp", "Industrial REITs", "Industrial Properties"),
    "insurance": ("Bảo hiểm", "Full Line Insurance", "Insurance"),
    "software": ("Phần mềm", "Software", "Computer Services"),
}


def _map_industry_code(icb_name: Any, en_name: Any) -> str:
    text = f"{icb_name or ''} {en_name or ''}".casefold()
    for code, names in INDUSTRY_NAME_RULES.items():
        if any(name.casefold() in text for name in names):
            return code
    return "generic"


def fetch_industry_classification(exchange: str = "HOSE") -> List[Dict[str, Any]]:
    """Fetch source industry rows and retain the leaf ICB row per ticker."""
    from vnstock import Listing

    listing = Listing(source="VCI")
    throttle()
    rows = listing.symbols_by_industries()
    if rows is None or rows.empty:
        return []

    rows = rows.copy()
    if "symbol" not in rows.columns or "icb_code" not in rows.columns:
        raise ValueError("Industry API thiếu symbol hoặc icb_code")

    if "exchange" in rows.columns:
        rows = rows[rows["exchange"].astype(str).str.upper() == exchange.upper()]
    else:
        # The industry endpoint has no exchange column in some vnstock versions.
        # Restrict it with the authoritative listing endpoint when available.
        try:
            throttle()
            exchange_rows = listing.symbols_by_exchange()
            if "ticker" in exchange_rows.columns and "exchange" in exchange_rows.columns:
                exchange_tickers = set(
                    exchange_rows.loc[
                        exchange_rows["exchange"].astype(str).str.upper() == exchange.upper(),
                        "ticker",
                    ].astype(str).str.upper()
                )
                rows = rows[rows["symbol"].astype(str).str.upper().isin(exchange_tickers)]
        except Exception as exc:
            logger.warning("Không lọc được sàn từ Listing: %s", exc)

    level_series = rows["icb_level"] if "icb_level" in rows.columns else 0
    rows["icb_level_num"] = level_series.fillna(0).astype(int) if hasattr(level_series, "fillna") else 0
    rows = rows.sort_values(["symbol", "icb_level_num"])
    rows = rows.drop_duplicates(subset=["symbol"], keep="last")

    fetched_at = datetime.now(timezone.utc).isoformat()
    result = []
    for _, row in rows.iterrows():
        ticker = str(row.get("symbol", "")).strip().upper()
        if not ticker or " " in ticker:
            continue
        result.append({
            "ticker": ticker,
            "industry_code": _map_industry_code(row.get("icb_name"), row.get("en_icb_name")),
            "industry_name": row.get("icb_name"),
            "icb_code": str(row.get("icb_code")),
            "icb_level": int(row.get("icb_level_num", 0)),
            "source": "vnstock:VCI",
            "source_version": "icb",
            "fetched_at": fetched_at,
        })
    return result


def filter_classification(rows: List[Dict[str, Any]], industry_code: str) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("industry_code") == industry_code]
