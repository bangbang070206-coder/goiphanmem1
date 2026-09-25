import pandas as pd
from typing import Dict, Any

def _num(v):
    try:
        x = float(v)
        return x if pd.notna(x) else None
    except Exception:
        return None

def score_stock(df_with_indicators: pd.DataFrame) -> Dict[str, Any]:
    """Simple student-MVP technical score (max 65), no 252-session percentile."""
    if df_with_indicators is None or df_with_indicators.empty:
        return {"status": "DATA_UNAVAILABLE", "reason": "Không có dữ liệu giá", "ta_score": None}
    if len(df_with_indicators) < 60:
        return {"status": "DATA_UNAVAILABLE", "reason": f"Chưa đủ dữ liệu giá ({len(df_with_indicators)}/60 phiên)", "ta_score": None}

    required = ["close", "ema20", "ema50", "rsi14", "atr14", "volume"]
    missing = [c for c in required if c not in df_with_indicators.columns]
    if missing:
        return {"status": "DATA_UNAVAILABLE", "reason": f"Thiếu cột chỉ báo: {', '.join(missing)}", "ta_score": None}

    last = df_with_indicators.iloc[-1]
    prev = df_with_indicators.iloc[-2]
    close, ema20, ema50, rsi14, atr14, volume = [_num(last[c]) for c in required]
    prev_close = _num(prev["close"])
    if any(v is None for v in [close, ema20, ema50, rsi14, atr14, volume, prev_close]):
        return {"status": "DATA_UNAVAILABLE", "reason": "Thiếu giá trị chỉ báo ở phiên gần nhất", "ta_score": None}

    avg_volume_20 = _num(df_with_indicators["volume"].iloc[-21:-1].mean()) if len(df_with_indicators) >= 21 else None
    if avg_volume_20 is None or avg_volume_20 <= 0:
        avg_volume_20 = _num(df_with_indicators["volume"].iloc[-20:].mean())
    volume_ratio = volume / avg_volume_20 if avg_volume_20 and avg_volume_20 > 0 else None
    distance_atr = abs(close - ema20) / atr14 if atr14 and atr14 > 0 else None
    up_day = close > prev_close

    trend = 20 if close > ema20 > ema50 else 0
    rsi_score = 15 if rsi14 > 50 else 0
    vol_score = 15 if volume_ratio is not None and volume_ratio >= 1.0 else 0
    distance_score = 10 if distance_atr is not None and distance_atr <= 3.0 else 0
    up_score = 5 if up_day else 0
    technical_score = trend + rsi_score + vol_score + distance_score + up_score

    date = str(last.get("date", ""))[:10]
    raw = {"close": close, "ema20": ema20, "ema50": ema50, "atr14": atr14, "rsi14": rsi14,
           "volume": volume, "avg_volume_20": avg_volume_20, "volume_ratio": volume_ratio,
           "distance_atr": distance_atr, "up_day": up_day, "date": date}
    return {"status": "SUCCESS", "technical_score": technical_score, "ta_score": technical_score,
            "trend_score": trend, "momentum_score": rsi_score, "volume_score": vol_score, "raw": raw}
def calculate_percentile_rank(series, window=252):
    """
    Legacy compatibility helper for the existing backtest engine.
    Returns the percentile rank of the latest value in the series.
    """
    import pandas as pd

    s = pd.Series(series).dropna()

    if s.empty:
        return None

    if window and len(s) > window:
        s = s.iloc[-window:]

    last_value = s.iloc[-1]

    return float((s <= last_value).mean() * 100)