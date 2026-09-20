import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from config import PERCENTILE_WINDOW, WEIGHT_TREND, WEIGHT_MOMENTUM, WEIGHT_VOLUME

def calculate_percentile_rank(current_val: float, history_series: pd.Series) -> Optional[float]:
    """
    Tính điểm phân vị chuẩn hóa theo Mục 4 của Chiến lược số 1:
    - So sánh giá trị phiên hiện tại với đúng 252 phiên liền trước của chính mã đó.
    - Công thức: Score = (n_nhỏ_hơn + 0.5 * n_bằng) / N * 100
    - Nếu không đủ 252 quan sát hợp lệ, trả về None (DATA_UNAVAILABLE).
    """
    valid_history = history_series.dropna()
    if len(valid_history) < PERCENTILE_WINDOW:
        return None
        
    ref_window = valid_history.iloc[-PERCENTILE_WINDOW:]
    n_total = len(ref_window)
    
    n_less = (ref_window < current_val).sum()
    n_equal = (ref_window == current_val).sum()
    
    score = ((n_less + 0.5 * n_equal) / n_total) * 100.0
    return float(np.clip(score, 0.0, 100.0))

def score_stock(df_with_indicators: pd.DataFrame) -> Dict[str, Any]:
    """
    Tính điểm cho phiên đóng cửa gần nhất:
    - S_Trend (Xu hướng)
    - S_Mom (Động lượng)
    - S_Vol (Giá - Khối lượng)
    - TA_Score = Trung bình 3 nhóm
    """
    if df_with_indicators is None or len(df_with_indicators) < PERCENTILE_WINDOW + 50:
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": f"Chưa đủ dữ liệu lịch sử ({len(df_with_indicators) if df_with_indicators is not None else 0}/{PERCENTILE_WINDOW + 50} phiên)",
            "trend_score": None,
            "momentum_score": None,
            "volume_score": None,
            "ta_score": None
        }
        
    last_idx = len(df_with_indicators) - 1
    
    # Lấy giá trị của phiên đóng cửa gần nhất (phiên t)
    curr_xt = df_with_indicators['X_T'].iloc[last_idx]
    curr_xm = df_with_indicators['X_M'].iloc[last_idx]
    curr_xv = df_with_indicators['X_V'].iloc[last_idx]
    
    # 252 phiên liền trước (không chứa phiên t)
    hist_xt = df_with_indicators['X_T'].iloc[:last_idx]
    hist_xm = df_with_indicators['X_M'].iloc[:last_idx]
    hist_xv = df_with_indicators['X_V'].iloc[:last_idx]
    
    s_trend = calculate_percentile_rank(curr_xt, hist_xt)
    s_mom = calculate_percentile_rank(curr_xm, hist_xm)
    s_vol = calculate_percentile_rank(curr_xv, hist_xv)
    
    if s_trend is None or s_mom is None or s_vol is None:
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": "Thiếu dữ liệu nến để chuẩn hóa 252 phiên",
            "trend_score": s_trend,
            "momentum_score": s_mom,
            "volume_score": s_vol,
            "ta_score": None
        }
        
    ta_score = (WEIGHT_TREND * s_trend) + (WEIGHT_MOMENTUM * s_mom) + (WEIGHT_VOLUME * s_vol)
    
    return {
        "status": "SUCCESS",
        "trend_score": round(s_trend, 1),
        "momentum_score": round(s_mom, 1),
        "volume_score": round(s_vol, 1),
        "ta_score": round(ta_score, 1),
        "raw": {
            "X_T": curr_xt,
            "X_M": curr_xm,
            "X_V": curr_xv,
            "close": df_with_indicators['close'].iloc[last_idx],
            "ema20": df_with_indicators['ema20'].iloc[last_idx],
            "ema50": df_with_indicators['ema50'].iloc[last_idx],
            "atr14": df_with_indicators['atr14'].iloc[last_idx],
            "rsi14": df_with_indicators['rsi14'].iloc[last_idx],
            "vr": df_with_indicators['vr'].iloc[last_idx],
            "cp": df_with_indicators['cp'].iloc[last_idx],
            "date": str(df_with_indicators['date'].iloc[last_idx])[:10]
        }
    }
