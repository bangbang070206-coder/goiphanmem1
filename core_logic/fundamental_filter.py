from typing import Dict, Any, Optional
from config import (
    ROE_MIN, MAX_DEBT_TO_EQUITY, 
    REVENUE_GROWTH_MIN, NET_PROFIT_GROWTH_MIN, 
    CFO_MIN, MAX_STALE_DAYS, EXCLUDED_SECTOR_TICKERS
)
from datetime import datetime

def check_fundamental_criteria(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kiểm tra 6 điều kiện BCTC theo Mục 2 của Chiến lược số 1:
    1. Vốn & Lợi nhuận: VCSH > 0, LNST mẹ TTM > 0
    2. Hiệu quả vốn: ROE TTM >= 15%
    3. Tăng trưởng: Doanh thu TTM tăng > 0%, LNST mẹ TTM tăng > 0%
    4. Đòn bẩy: Tổng nợ / VCSH <= 1.5
    5. Dòng tiền: CFO TTM > 0
    6. Độ mới của dữ liệu: Không quá 180 ngày

    LƯU Ý: metrics (từ fetch_stock_financials) giờ có thể chứa None cho các trường
    không lấy/tính được (thay vì số liệu bịa như bản cũ). Hàm này xử lý None một
    cách tường minh: KHÔNG dùng dict.get(key, default) đơn thuần, vì .get() chỉ trả
    về default khi THIẾU KEY, không phải khi value = None - dẫn đến crash TypeError
    khi so sánh None > số. Thiếu dữ liệu được báo là DATA_INSUFFICIENT, không bị
    hiểu nhầm thành "trượt tiêu chí" (OUT_OF_UNIVERSE) hay "đạt" một cách sai lệch.
    """
    if not metrics or metrics.get("status") == "FETCH_FAILED":
        return {
            "is_passed": False,
            "status": "DATA_UNAVAILABLE",
            "reason": "Chưa có dữ liệu BCTC (gọi API thất bại)",
            "details": {}
        }

    ticker = str(metrics.get('ticker', '')).upper()
    if ticker in EXCLUDED_SECTOR_TICKERS:
        return {
            "is_passed": False,
            "status": "OUT_OF_SCOPE",
            "reason": (
                f"Mã {ticker} thuộc nhóm Ngân hàng/Chứng khoán/Bảo hiểm - nằm ngoài phạm vi "
                f"bộ lọc BCTC này (Mục 2, Chiến lược số 1). Chỉ số Nợ/VCSH <= 1.5 không phản "
                f"ánh đúng bản chất kinh doanh của nhóm ngành tài chính."
            ),
            "details": {}
        }

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
            "reason": f"Chưa đủ dữ liệu để đánh giá: {', '.join(missing_fields)} (không đủ số quý báo cáo cần thiết)",
            "details": {
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
    
    # 1. ROE >= 15%
    c_roe = roe >= ROE_MIN
    if not c_roe:
        reasons.append(f"ROE TTM ({roe*100:.1f}%) < {ROE_MIN*100:.0f}%")
        
    # 2. Đòn bẩy Tổng nợ/VCSH <= 1.5
    c_leverage = 0 <= debt_to_equity <= MAX_DEBT_TO_EQUITY
    if not c_leverage:
        reasons.append(f"Nợ/VCSH ({debt_to_equity:.2f}) > {MAX_DEBT_TO_EQUITY}")
        
    # 3. Tăng trưởng Doanh thu TTM > 0%
    c_rev = rev_growth > REVENUE_GROWTH_MIN
    if not c_rev:
        reasons.append(f"Tăng trưởng DT TTM ({rev_growth*100:.1f}%) <= 0%")
        
    # 4. Tăng trưởng LNST TTM > 0%
    c_np = np_growth > NET_PROFIT_GROWTH_MIN
    if not c_np:
        reasons.append(f"Tăng trưởng LNST TTM ({np_growth*100:.1f}%) <= 0%")
        
    # 5. Dòng tiền CFO TTM > 0
    c_cfo = cfo > CFO_MIN
    if not c_cfo:
        reasons.append("Dòng tiền HĐKD (CFO TTM) <= 0")
        
    is_passed = c_roe and c_leverage and c_rev and c_np and c_cfo and not is_stale
    
    status = "PASSED" if is_passed else ("DATA_STALE" if is_stale else "OUT_OF_UNIVERSE")
    
    return {
        "is_passed": is_passed,
        "status": status,
        "reason": "; ".join(reasons) if reasons else "Đạt toàn bộ tiêu chí BCTC",
        "details": {
            "ROE": f"{roe*100:.1f}%",
            "Debt_to_Equity": f"{debt_to_equity:.2f}",
            "Rev_Growth": f"{rev_growth*100:.1f}%",
            "NP_Growth": f"{np_growth*100:.1f}%",
            "CFO": "Dương (>0)" if c_cfo else "Âm (<=0)",
            "Report_Date": report_date_str or "N/A"
        }
    }
