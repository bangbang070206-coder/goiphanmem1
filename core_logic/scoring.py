import pandas as pd
from typing import Dict, Any


def _num(v):
    try:
        x = float(v)
        return x if pd.notna(x) else None
    except Exception:
        return None


def score_stock(df_with_indicators: pd.DataFrame) -> Dict[str, Any]:
    """
    Simple student-MVP technical score (max 65).

    Các tiêu chí:
    - Trend: Close > EMA20 > EMA50       : 20 điểm
    - RSI > 50                            : 15 điểm
    - Volume ratio >= 1.0                 : 15 điểm
    - Khoảng cách giá với EMA20 <= 3 ATR : 10 điểm
    - Giá tăng so với phiên trước         : 5 điểm

    Tổng tối đa: 65 điểm.
    """

    # Kiểm tra dữ liệu rỗng
    if df_with_indicators is None or df_with_indicators.empty:
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": "Không có dữ liệu giá",
            "ta_score": None
        }

    # Kiểm tra số phiên tối thiểu
    if len(df_with_indicators) < 60:
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": f"Chưa đủ dữ liệu giá ({len(df_with_indicators)}/60 phiên)",
            "ta_score": None
        }

    # Các cột bắt buộc
    required = [
        "close",
        "ema20",
        "ema50",
        "rsi14",
        "atr14",
        "volume"
    ]

    missing = [
        c
        for c in required
        if c not in df_with_indicators.columns
    ]

    if missing:
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": f"Thiếu cột chỉ báo: {', '.join(missing)}",
            "ta_score": None
        }

    # Phiên gần nhất và phiên trước
    last = df_with_indicators.iloc[-1]
    prev = df_with_indicators.iloc[-2]

    close = _num(last["close"])
    ema20 = _num(last["ema20"])
    ema50 = _num(last["ema50"])
    rsi14 = _num(last["rsi14"])
    atr14 = _num(last["atr14"])
    volume = _num(last["volume"])

    prev_close = _num(prev["close"])

    # Kiểm tra dữ liệu chỉ báo
    if any(
        v is None
        for v in [
            close,
            ema20,
            ema50,
            rsi14,
            atr14,
            volume,
            prev_close
        ]
    ):
        return {
            "status": "DATA_UNAVAILABLE",
            "reason": "Thiếu giá trị chỉ báo ở phiên gần nhất",
            "ta_score": None
        }

    # ---------------------------------------------------------
    # 1. Volume trung bình 20 phiên
    # ---------------------------------------------------------

    avg_volume_20 = None

    if len(df_with_indicators) >= 21:
        avg_volume_20 = _num(
            df_with_indicators["volume"].iloc[-21:-1].mean()
        )

    if avg_volume_20 is None or avg_volume_20 <= 0:
        avg_volume_20 = _num(
            df_with_indicators["volume"].iloc[-20:].mean()
        )

    volume_ratio = (
        volume / avg_volume_20
        if avg_volume_20 is not None and avg_volume_20 > 0
        else None
    )

    # ---------------------------------------------------------
    # 2. Khoảng cách giá tới EMA20 theo ATR
    # ---------------------------------------------------------

    distance_atr = (
        abs(close - ema20) / atr14
        if atr14 is not None and atr14 > 0
        else None
    )

    # ---------------------------------------------------------
    # 3. Giá tăng so với phiên trước
    # ---------------------------------------------------------

    up_day = close > prev_close

    # ---------------------------------------------------------
    # 4. Tính điểm
    # ---------------------------------------------------------

    # Trend: 20 điểm
    trend = 20 if close > ema20 > ema50 else 0

    # RSI: 15 điểm
    rsi_score = 15 if rsi14 > 50 else 0

    # Volume: 15 điểm
    vol_score = (
        15
        if volume_ratio is not None and volume_ratio >= 1.0
        else 0
    )

    # Khoảng cách giá - EMA20: 10 điểm
    distance_score = (
        10
        if distance_atr is not None and distance_atr <= 3.0
        else 0
    )

    # Giá tăng: 5 điểm
    up_score = 5 if up_day else 0

    technical_score = (
        trend
        + rsi_score
        + vol_score
        + distance_score
        + up_score
    )

    # ---------------------------------------------------------
    # 5. Dữ liệu raw để bot có thể hiển thị
    # ---------------------------------------------------------

    date = str(last.get("date", ""))[:10]

    raw = {
        "close": close,
        "ema20": ema20,
        "ema50": ema50,
        "atr14": atr14,
        "rsi14": rsi14,
        "volume": volume,
        "avg_volume_20": avg_volume_20,
        "volume_ratio": volume_ratio,
        "distance_atr": distance_atr,
        "up_day": up_day,
        "date": date
    }

    return {
        "status": "SUCCESS",
        "technical_score": technical_score,
        "ta_score": technical_score,
        "trend_score": trend,
        "momentum_score": rsi_score,
        "volume_score": vol_score,
        "raw": raw
    }


def calculate_percentile_rank(value, history, window=252):
    """
    Tính percentile rank của một giá trị hiện tại
    so với chuỗi dữ liệu lịch sử.

    Hàm này được giữ lại để tương thích với
    backtesting/backtest_engine.py.

    Parameters
    ----------
    value:
        Giá trị tại phiên hiện tại.

    history:
        Pandas Series chứa dữ liệu lịch sử.

    window:
        Số phiên lịch sử tối đa được sử dụng.

    Returns
    -------
    float | None:
        Percentile rank từ 0 đến 100.
    """

    # Chuyển history thành Series
    try:
        s = pd.Series(history)
    except Exception:
        return None

    # Bỏ giá trị thiếu và chuyển về số
    s = pd.to_numeric(s, errors="coerce").dropna()

    if s.empty:
        return None

    # Giới hạn số phiên lịch sử
    if window is not None and window > 0 and len(s) > window:
        s = s.iloc[-window:]

    # Chuyển giá trị hiện tại thành số
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if pd.isna(value):
        return None

    # Tính percentile rank
    percentile = (s <= value).mean() * 100

    return float(percentile)