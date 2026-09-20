from typing import Dict, Any, Optional
import pandas as pd
from core_logic.indicators import calculate_indicators
from core_logic.scoring import score_stock
from core_logic.fundamental_filter import check_fundamental_criteria
from database.db_manager import get_financial_metrics
from config import TA_SCORE_BUY_THRESHOLD

def evaluate_ticker(ticker: str, df_price: pd.DataFrame) -> Dict[str, Any]:
    """
    Đánh giá toàn diện một mã cổ phiếu theo Mục 5 của Chiến lược số 1:
    - Bước 1: Kiểm tra BCTC (Fundamental Filter)
    - Bước 2: Tính chỉ báo kỹ thuật
    - Bước 3: Chấm điểm 3 nhóm (Percentile 252 phiên)
    - Bước 4: Xác định trạng thái (OUT_OF_UNIVERSE, WATCHLIST, BUY_CANDIDATE)
    """
    result = {
        "ticker": ticker.upper(),
        "status": "WATCHLIST",
        "signal": "HOLD",
        "fundamental": {},
        "technical": {},
        "scoring": {},
        "reasons": []
    }
    
    # 1. Kiểm tra BCTC
    fin_data = get_financial_metrics(ticker)
    if not fin_data:
        from data_pipeline.fetcher import fetch_stock_financials
        fin_data = fetch_stock_financials(ticker)
        
    fin_eval = check_fundamental_criteria(fin_data)
    result["fundamental"] = fin_eval
    
    if not fin_eval["is_passed"]:
        result["status"] = fin_eval["status"]  # OUT_OF_UNIVERSE hoặc DATA_STALE / DATA_UNAVAILABLE
        result["reasons"].append(f"Chưa đạt lọc BCTC: {fin_eval['reason']}")
        # Vẫn tiếp tục tính điểm kỹ thuật để người dùng tra cứu tham khảo nếu muốn
    
    # 2. Kiểm tra Dữ liệu giá
    if df_price is None or len(df_price) < 50:
        result["status"] = "DATA_UNAVAILABLE"
        result["reasons"].append("Dữ liệu giá không đủ để tính toán chỉ báo")
        return result
        
    # 3. Tính toán chỉ báo kỹ thuật
    df_ind = calculate_indicators(df_price)
    
    # 4. Chấm điểm 3 nhóm kỹ thuật
    score_res = score_stock(df_ind)
    result["scoring"] = score_res
    
    if score_res.get("status") != "SUCCESS":
        if result["status"] != "OUT_OF_UNIVERSE":
            result["status"] = "DATA_UNAVAILABLE"
        result["reasons"].append(score_res.get("reason", "Lỗi chấm điểm kỹ thuật"))
        return result
        
    raw = score_res["raw"]
    close = raw["close"]
    ema20 = raw["ema20"]
    ema50 = raw["ema50"]
    vr = raw["vr"]
    cp = raw["cp"]
    ta_score = score_res["ta_score"]
    
    result["technical"] = {
        "close": close,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "atr14": round(raw["atr14"], 2),
        "rsi14": round(raw["rsi14"], 1),
        "vr": round(vr, 2),
        "cp": round(cp, 2),
        "date": raw["date"]
    }
    
    # 5. Kiểm tra điều kiện mua bắt buộc (Mục 5 trong chiến lược)
    cond_trend = (close > ema50) and (ema20 > ema50)
    cond_price = (cp > 0.5)
    cond_vol = (vr > 1.0)
    cond_score = (ta_score is not None and ta_score >= TA_SCORE_BUY_THRESHOLD)
    
    tech_passed = cond_trend and cond_price and cond_vol and cond_score
    
    if fin_eval["is_passed"]:
        if tech_passed:
            result["status"] = "BUY_CANDIDATE"
            result["signal"] = "BUY"
            result["reasons"].append(f"Đạt bộ lọc BCTC và thỏa mãn toàn bộ điều kiện MUA (TA_Score = {ta_score} >= {TA_SCORE_BUY_THRESHOLD})")
        else:
            result["status"] = "WATCHLIST"
            failed_conds = []
            if not cond_trend:
                failed_conds.append("Xu hướng chưa đạt (yêu cầu Close > EMA50 và EMA20 > EMA50)")
            if not cond_price:
                failed_conds.append("Nến chưa đóng ở nửa trên thân nến (CP <= 0.5)")
            if not cond_vol:
                failed_conds.append(f"Khối lượng chưa bùng nổ (VR = {vr:.2f} <= 1.0)")
            if not cond_score:
                failed_conds.append(f"Điểm kỹ thuật ({ta_score}) chưa đạt ngưỡng {TA_SCORE_BUY_THRESHOLD}")
            result["reasons"].extend(failed_conds)
            
    return result
