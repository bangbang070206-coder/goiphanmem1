import numpy as np
import pandas as pd
from typing import Tuple, Dict

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Tính EMA theo công thức chuẩn: hệ số 2/(N+1), khởi tạo bằng SMA N phiên đầu"""
    if len(series) < period:
        return pd.Series(np.nan, index=series.index)
    
    ema = pd.Series(index=series.index, dtype='float64')
    sma_first = series.iloc[:period].mean()
    ema.iloc[period - 1] = sma_first
    multiplier = 2.0 / (period + 1.0)
    
    for i in range(period, len(series)):
        ema.iloc[i] = (series.iloc[i] - ema.iloc[i - 1]) * multiplier + ema.iloc[i - 1]
        
    return ema

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Tính True Range và ATR theo phương pháp làm trơn Wilder (Wilder's Smoothing) hệ số 1/14"""
    if len(df) < period + 1:
        return pd.Series(np.nan, index=df.index)
        
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = pd.Series(index=df.index, dtype='float64')
    atr.iloc[period] = tr.iloc[1:period + 1].mean()
    
    alpha = 1.0 / period
    for i in range(period + 1, len(df)):
        atr.iloc[i] = atr.iloc[i - 1] * (1.0 - alpha) + tr.iloc[i] * alpha
        
    return atr

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Tính RSI 14 theo phương pháp làm trơn Wilder chuẩn"""
    if len(series) < period + 1:
        return pd.Series(np.nan, index=series.index)
        
    delta = series.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    
    avg_gain = pd.Series(index=series.index, dtype='float64')
    avg_loss = pd.Series(index=series.index, dtype='float64')
    rsi = pd.Series(index=series.index, dtype='float64')
    
    avg_gain.iloc[period] = gains.iloc[1:period + 1].mean()
    avg_loss.iloc[period] = losses.iloc[1:period + 1].mean()
    
    alpha = 1.0 / period
    for i in range(period + 1, len(series)):
        avg_gain.iloc[i] = avg_gain.iloc[i - 1] * (1.0 - alpha) + gains.iloc[i] * alpha
        avg_loss.iloc[i] = avg_loss.iloc[i - 1] * (1.0 - alpha) + losses.iloc[i] * alpha
        
        g = avg_gain.iloc[i]
        l = avg_loss.iloc[i]
        if l == 0 and g > 0:
            rsi.iloc[i] = 100.0
        elif l == 0 and g == 0:
            rsi.iloc[i] = 50.0
        else:
            rs = g / l
            rsi.iloc[i] = 100.0 - (100.0 / (1.0 + rs))
            
    return rsi

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính toàn bộ các chỉ báo kỹ thuật theo Mục 3 của Chiến lược số 1:
    - EMA20, EMA50
    - ATR14
    - RSI14
    - CP (Close Position) & VR (Volume Ratio)
    - Các đại lượng thô: X_T, X_M, X_V
    """
    df = df.copy()
    df['ema20'] = calculate_ema(df['close'], 20)
    df['ema50'] = calculate_ema(df['close'], 50)
    df['atr14'] = calculate_atr(df, 14)
    df['rsi14'] = calculate_rsi(df['close'], 14)
    
    # 1. Đại lượng xu hướng X_T = (EMA20 - EMA50) / ATR14
    df['X_T'] = (df['ema20'] - df['ema50']) / df['atr14']
    
    # 2. Đại lượng động lượng X_M = RSI14
    df['X_M'] = df['rsi14']
    
    # 3. Vị trí đóng cửa CP = (Close - Low) / (High - Low)
    hl_range = df['high'] - df['low']
    df['cp'] = np.where(hl_range > 0, (df['close'] - df['low']) / hl_range, 0.5)
    
    # 4. Khối lượng tương đối VR = Volume / SMA20(Volume)
    df['vol_sma20'] = df['volume'].rolling(window=20).mean()
    df['vr'] = np.where(df['vol_sma20'] > 0, df['volume'] / df['vol_sma20'], 0.0)
    
    # 5. Đại lượng Giá & Khối lượng X_V
    # Nếu Close <= Close_prev => X_V = 0
    # Nếu Close > Close_prev: X_V = VR * (2*CP - 1) nếu CP > 0.5, else 0
    prev_close = df['close'].shift(1)
    is_up_day = df['close'] > prev_close
    df['X_V'] = np.where(
        is_up_day & (df['cp'] > 0.5),
        df['vr'] * (2.0 * df['cp'] - 1.0),
        0.0
    )
    
    return df
