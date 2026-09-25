from typing import Dict, Any, Optional
from config import (
    ROE_MIN, MAX_DEBT_TO_EQUITY,
    REVENUE_GROWTH_MIN, NET_PROFIT_GROWTH_MIN,
    CFO_MIN, MAX_STALE_DAYS,
    SECTOR_MAP, SECTOR_MAP_VERSION, SECTOR_PROFILE_THRESHOLDS
)
from datetime import datetime
from core_logic.industry import evaluate_industry


def get_sector_profile(ticker: str) -> str:
    """Trả về profile ngành cho 1 mã: NON_FINANCIAL / BANK / SECURITIES /
    INSURANCE_LIFE / INSURANCE_NONLIFE. Mặc định NON_FINANCIAL nếu không có
    trong SECTOR_MAP (Mục 6, Chiến lược v2 - "không suy ngành từ tên mã", nên
    NON_FINANCIAL là mặc định trung lập, không phải suy đoán)."""
    return SECTOR_MAP.get(str(ticker).upper(), "NON_FINANCIAL")


def _not_evaluated(profile: str, ticker: str) -> Dict[str, Any]:
    """Trạng thái cho các profile Tài chính chưa có nguồn dữ liệu chuyên ngành
    đã xác minh (NPL, CAR, vốn khả dụng, khả năng thanh toán...). Theo v2 Mục 7:
    'Nếu chưa xác minh được, trả RULES_UNVERIFIED và chặn mua; không đặt
    minimum=0 hoặc bỏ tiêu chí.' Đây KHÔNG phải kết luận doanh nghiệp yếu."""
    return {
        "is_passed": False,
        "status": "NOT_EVALUATED",
        "reason": (
            f"Mã {ticker} thuộc profile {profile} - chưa đánh giá đầy đủ vì thiếu nguồn dữ liệu "
            f"chuyên ngành đã xác minh (tỷ lệ nợ xấu/CAR cho ngân hàng, tỷ lệ vốn khả dụng cho "
            f"chứng khoán, tỷ lệ khả năng thanh toán cho bảo hiểm - xem Mục 7, Chiến lược v2). "
            f"Đây KHÔNG phải kết luận doanh nghiệp yếu kém tài chính, chỉ là chưa đủ dữ liệu để "
            f"chấm theo đúng chuẩn ngành."
        ),
        "details": {
            "capability_status": "DATA_PENDING",
            "profile": profile,
            "sector_map_version": SECTOR_MAP_VERSION,
        }
    }


def check_fundamental_criteria(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kiểm tra điều kiện BCTC theo PROFILE NGÀNH (Mục 6, Chiến lược v2) - thay cho
    danh sách loại cứng của v1. Ticker được định tuyến qua get_sector_profile():

    - NON_FINANCIAL: 5 tiêu chí đầy đủ như v1 (ROE, Nợ/VCSH, tăng trưởng DT+LNST, CFO).
    - BANK / SECURITIES / INSURANCE_*: trả NOT_EVALUATED - CHƯA chấm điểm vì thiếu
      nguồn dữ liệu chuyên ngành đã xác minh (không bịa số liệu để "cho qua").

    LƯU Ý: metrics (từ fetch_stock_financials) có thể chứa None cho các trường
    không lấy/tính được. Hàm này xử lý None tường minh: KHÔNG dùng
    dict.get(key, default) đơn thuần, vì .get() chỉ trả default khi THIẾU KEY,
    không phải khi value = None - dẫn đến crash TypeError khi so sánh None > số.
    """
    if not metrics or metrics.get("status") == "FETCH_FAILED":
        return {
            "is_passed": False,
            "status": "DATA_UNAVAILABLE",
            "reason": "Chưa có dữ liệu BCTC (gọi API thất bại)",
            "details": {}
        }

    ticker = str(metrics.get('ticker', '')).upper()
    profile = get_sector_profile(ticker)

    if profile != "NON_FINANCIAL":
        return _not_evaluated(profile, ticker)

    thresholds = SECTOR_PROFILE_THRESHOLDS["NON_FINANCIAL"]

    roe = metrics.get('roe')
    debt_to_equity = metrics.get('debt_to_equity')
    rev_growth = metrics.get('rev_growth')
    np_growth = metrics.get('np_growth')
    cfo = metrics.get('cfo')
    report_date_str = metrics.get('report_date')

    missing_fields = [name for name, v in [
        ("ROE", roe), ("Nợ/VCSH", debt_to_equity),
        ("Tăng trưởng DT", rev_growth), ("Tăng trưởng LNST", np_growth),
        ("CFO", cfo)
    ] if v is None]

    if missing_fields:
        return {
            "is_passed": False,
            "status": "DATA_INSUFFICIENT",
            "reason": f"Chưa đủ dữ liệu để đánh giá: {', '.join(missing_fields)} (không đủ số quý báo cáo cần thiết, hoặc kỳ gốc tăng trưởng không dương)",
            "details": {
                "profile": profile,
                "ROE": f"{roe*100:.1f}%" if roe is not None else "N/A",
                "Debt_to_Equity": f"{debt_to_equity:.2f}" if debt_to_equity is not None else "N/A",
                "Rev_Growth": f"{rev_growth*100:.1f}%" if rev_growth is not None else "N/A",
                "NP_Growth": f"{np_growth*100:.1f}%" if np_growth is not None else "N/A",
                "CFO": "N/A" if cfo is None else ("Dương (>0)" if cfo > 0 else "Âm (<=0)"),
                "Report_Date": report_date_str or "N/A"
            }
        }

    # Kiểm tra độ tươi của dữ liệu (Staleness)
    is_stale = False
    if report_date_str:
        try:
            rep_date = datetime.strptime(str(report_date_str)[:10], "%Y-%m-%d")
            diff_days = (datetime.now() - rep_date).days
            if diff_days > MAX_STALE_DAYS:
                is_stale = True
        except Exception:
            pass

    reasons = []

    c_roe = roe >= thresholds["roe_min"]
    if not c_roe:
        reasons.append(f"ROE TTM ({roe*100:.1f}%) < {thresholds['roe_min']*100:.0f}%")

    c_leverage = 0 <= debt_to_equity <= thresholds["max_debt_to_equity"]
    if not c_leverage:
        reasons.append(f"Nợ/VCSH ({debt_to_equity:.2f}) > {thresholds['max_debt_to_equity']}")

    c_rev = rev_growth > thresholds["rev_growth_min"]
    if not c_rev:
        reasons.append(f"Tăng trưởng DT TTM ({rev_growth*100:.1f}%) <= 0%")

    c_np = np_growth > thresholds["np_growth_min"]
    if not c_np:
        reasons.append(f"Tăng trưởng LNST TTM ({np_growth*100:.1f}%) <= 0%")

    c_cfo = cfo > thresholds["cfo_min"]
    if not c_cfo:
        reasons.append("Dòng tiền HĐKD (CFO TTM) <= 0")

    is_passed = c_roe and c_leverage and c_rev and c_np and c_cfo and not is_stale

    status = "PASSED" if is_passed else ("DATA_STALE" if is_stale else "OUT_OF_UNIVERSE")

    return {
        "is_passed": is_passed,
        "status": status,
        "reason": "; ".join(reasons) if reasons else "Đạt toàn bộ tiêu chí BCTC",
        "details": {
            "profile": profile,
            "ROE": f"{roe*100:.1f}%",
            "Debt_to_Equity": f"{debt_to_equity:.2f}",
            "Rev_Growth": f"{rev_growth*100:.1f}%",
            "NP_Growth": f"{np_growth*100:.1f}%",
            "CFO": "Dương (>0)" if c_cfo else "Âm (<=0)",
            "Report_Date": report_date_str or "N/A"
        }
    }


def check_industry_criteria(metrics: Dict[str, Any], industry_code: Optional[str]) -> Dict[str, Any]:
    """Evaluate the configured filter for one source-reported industry."""
    if not metrics or metrics.get("status") == "FETCH_FAILED":
        return {
            "is_passed": False,
            "status": "INSUFFICIENT_DATA",
            "industry_code": industry_code,
            "reason": "Không có dữ liệu tài chính hợp lệ",
            "details": {},
        }
    result = evaluate_industry(industry_code, metrics)
    result["reason"] = "; ".join(result.get("reasons", [])) or "Đạt bộ lọc ngành"
    result["details"] = result.get("groups", {})
    return result
