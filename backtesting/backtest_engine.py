import pandas as pd
import numpy as np
from typing import List, Dict, Any
from core_logic.indicators import calculate_indicators
from core_logic.scoring import calculate_percentile_rank
from config import (
    PERCENTILE_WINDOW, TA_SCORE_BUY_THRESHOLD,
    STOP_ATR_MULTIPLE, TARGET_ATR_MULTIPLE
)

def run_backtest_single_stock(
    ticker: str, 
    df: pd.DataFrame, 
    lookback_days: int = 120,
    is_fundamental_passed: bool = True
) -> Dict[str, Any]:
    """
    Chạy kiểm thử lịch sử (Backtest) cho 1 mã cổ phiếu trong 3-6 tháng (khoảng 60-120 phiên):
    - Áp dụng các quy tắc mua/bán của Chiến lược số 1
    - Tín hiệu phiên t -> Mua tại Open phiên t+1
    - Thoát vị thế khi chạm Stoploss, Target hoặc thủng EMA50
    """
    if df is None or len(df) < PERCENTILE_WINDOW + 50:
        return {"ticker": ticker, "trades": [], "summary": {"total_trades": 0}}
        
    df_ind = calculate_indicators(df)
    
    trades = []
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    stop_loss = 0.0
    target_price = 0.0
    atr0 = 0.0
    is_partial = False
    
    start_idx = max(PERCENTILE_WINDOW + 50, len(df_ind) - lookback_days)
    
    for i in range(start_idx, len(df_ind) - 1):
        # Kiểm tra phiên t (đóng cửa phiên hôm nay)
        curr_row = df_ind.iloc[i]
        next_row = df_ind.iloc[i + 1] # Phiên t+1
        
        # Nếu đang có vị thế -> Kiểm tra quy tắc bán
        if in_position:
            high_next = next_row['high']
            low_next = next_row['low']
            close_next = next_row['close']
            ema50_next = next_row['ema50']
            date_next = str(next_row['date'])[:10]
            
            # 1. Cắt lỗ
            if low_next <= stop_loss:
                exit_p = min(stop_loss, next_row['open'])
                ret = (exit_p - entry_price) / entry_price
                trades.append({
                    "type": "STOP_LOSS",
                    "entry_price": entry_price,
                    "exit_price": exit_p,
                    "return_pct": ret * 100,
                    "holding_days": i + 1 - entry_idx,
                    "date": date_next
                })
                in_position = False
                continue
                
            # 2. Thủng EMA50
            elif close_next < ema50_next:
                exit_p = close_next
                ret = (exit_p - entry_price) / entry_price
                trades.append({
                    "type": "EXIT_EMA50",
                    "entry_price": entry_price,
                    "exit_price": exit_p,
                    "return_pct": ret * 100,
                    "holding_days": i + 1 - entry_idx,
                    "date": date_next
                })
                in_position = False
                continue
                
            # 3. Chạm Target chốt lời 50%
            elif high_next >= target_price and not is_partial:
                is_partial = True
                stop_loss = max(stop_loss, entry_price) # Dời stop lên hòa vốn
                
        # Nếu chưa có vị thế -> Kiểm tra tín hiệu MUA
        else:
            if not is_fundamental_passed:
                continue
                
            # Tính điểm phân vị tại phiên t
            curr_xt = curr_row['X_T']
            curr_xm = curr_row['X_M']
            curr_xv = curr_row['X_V']
            
            hist_xt = df_ind['X_T'].iloc[i - PERCENTILE_WINDOW:i]
            hist_xm = df_ind['X_M'].iloc[i - PERCENTILE_WINDOW:i]
            hist_xv = df_ind['X_V'].iloc[i - PERCENTILE_WINDOW:i]
            
            s_t = calculate_percentile_rank(curr_xt, hist_xt)
            s_m = calculate_percentile_rank(curr_xm, hist_xm)
            s_v = calculate_percentile_rank(curr_xv, hist_xv)
            
            if s_t is None or s_m is None or s_v is None:
                continue
                
            ta_score = (s_t + s_m + s_v) / 3.0
            
            # Điều kiện mua bắt buộc
            cond_trend = (curr_row['close'] > curr_row['ema50']) and (curr_row['ema20'] > curr_row['ema50'])
            cond_price = (curr_row['cp'] > 0.5)
            cond_vol = (curr_row['vr'] > 1.0)
            cond_score = (ta_score >= TA_SCORE_BUY_THRESHOLD)
            
            if cond_trend and cond_price and cond_vol and cond_score:
                # Mua tại Open của phiên t+1
                entry_price = next_row['open']
                atr0 = curr_row['atr14']
                
                # Chống mua đuổi: Nếu Open > Close + 0.5*ATR thì hủy lệnh
                if entry_price > curr_row['close'] + 0.5 * atr0:
                    continue
                    
                stop_loss = entry_price - (STOP_ATR_MULTIPLE * atr0)
                target_price = entry_price + (TARGET_ATR_MULTIPLE * atr0)
                in_position = True
                is_partial = False
                entry_idx = i + 1
                
    # Nếu còn lệnh mở ở cuối kỳ backtest
    if in_position:
        last_close = df_ind['close'].iloc[-1]
        ret = (last_close - entry_price) / entry_price
        trades.append({
            "type": "OPEN_POSITION",
            "entry_price": entry_price,
            "exit_price": last_close,
            "return_pct": ret * 100,
            "holding_days": len(df_ind) - entry_idx,
            "date": str(df_ind['date'].iloc[-1])[:10]
        })
        
    # Tính toán các chỉ số thống kê
    total_trades = len(trades)
    if total_trades == 0:
        return {"ticker": ticker, "trades": [], "summary": {"total_trades": 0, "win_rate": 0, "total_return": 0}}
        
    returns = [t['return_pct'] for t in trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    total_return = sum(returns)
    avg_gain = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    
    return {
        "ticker": ticker,
        "trades": trades,
        "summary": {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 1),
            "total_return": round(total_return, 1),
            "avg_gain": round(avg_gain, 1),
            "avg_loss": round(avg_loss, 1),
            "win_count": len(wins),
            "loss_count": len(losses)
        }
    }
