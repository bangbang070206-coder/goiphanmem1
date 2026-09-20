from typing import Dict, Any

def check_exit_conditions(
    position: Dict[str, Any], 
    current_high: float, 
    current_low: float, 
    current_close: float, 
    current_ema50: float
) -> Dict[str, Any]:
    """
    Kiểm tra điều kiện thoát lệnh và cập nhật Trailing Stop theo Mục 6 của Chiến lược:
    - Ưu tiên 1: Giá chạm hoặc xuyên qua Stoploss -> BÁN HẾT (Cắt lỗ)
    - Ưu tiên 2: Phiên đóng cửa Close < EMA50 -> BÁN HẾT (Mất xu hướng)
    - Ưu tiên 3: Giá chạm Target0 và chưa chốt lời -> BÁN 50% (Chốt lời phần 1)
    - Cập nhật Trailing Stop: Dời stoploss lên điểm hòa vốn hoặc theo nến cao nhất, không bao giờ hạ stoploss.
    """
    stop_loss = position['stop_loss']
    target_price = position['target_price']
    entry_price = position['entry_price']
    is_partial_sold = bool(position.get('is_partial_sold', 0))
    current_qty = position['quantity']
    
    # 1. Cắt lỗ (Stoploss hit)
    if current_low <= stop_loss:
        return {
            "action": "SELL_ALL",
            "sell_qty": current_qty,
            "exec_price": min(current_close, stop_loss),
            "reason": f"Chạm ngưỡng cắt lỗ Stop Loss ({stop_loss})"
        }
        
    # 2. Thủng EMA50 ở phiên đóng cửa
    if current_close < current_ema50:
        return {
            "action": "SELL_ALL",
            "sell_qty": current_qty,
            "exec_price": current_close,
            "reason": f"Giá đóng cửa ({current_close}) thủng đường hỗ trợ EMA50 ({current_ema50:.2f})"
        }
        
    # 3. Chốt lời 50% khi chạm Target
    if not is_partial_sold and current_high >= target_price:
        partial_qty = (current_qty // 2 // 100) * 100
        if partial_qty < 100:
            partial_qty = current_qty  # Nếu chỉ có 100 cổ phiếu thì bán hết
            
        new_stop = max(stop_loss, entry_price) # Dời stop lên ít nhất là hòa vốn (Breakeven)
        
        return {
            "action": "SELL_PARTIAL",
            "sell_qty": partial_qty,
            "exec_price": target_price,
            "new_stop_loss": new_stop,
            "reason": f"Chạm mục tiêu chốt lời Target ({target_price}), bán 50% và dời Stoploss lên {new_stop}"
        }
        
    # 4. Giữ vị thế (HOLD)
    # Nếu đã chốt 50%, áp dụng trailing stop không được hạ
    new_stop = stop_loss
    if is_partial_sold:
        trail_candidate = current_close - (2.0 * position.get('atr0', 0))
        new_stop = max(stop_loss, trail_candidate, entry_price)
        
    return {
        "action": "HOLD",
        "sell_qty": 0,
        "new_stop_loss": new_stop,
        "reason": "Vị thế vẫn khỏe, chưa vi phạm điều kiện bán"
    }
