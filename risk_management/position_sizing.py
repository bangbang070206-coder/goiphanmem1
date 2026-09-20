from typing import Dict, Any
from config import (
    RISK_PER_TRADE_PCT, MAX_STOCK_WEIGHT_PCT, 
    STOP_ATR_MULTIPLE, TARGET_ATR_MULTIPLE, 
    CHASE_BUY_MAX_ATR, LOT_SIZE
)

def calculate_position_size(
    entry_price: float, 
    atr0: float, 
    nav: float, 
    cash_available: float
) -> Dict[str, Any]:
    """
    Tính toán định cỡ vị thế theo Mục 6 của Chiến lược số 1:
    - Rủi ro tối đa 0.5% NAV cho mỗi giao dịch
    - Ngưỡng cắt lỗ: Stop0 = Entry - 2 * ATR0
    - Khoảng cách rủi ro: R = 2 * ATR0
    - Giới hạn phân bổ tối đa 20% NAV cho 1 cổ phiếu
    - Làm tròn xuống lô chẵn 100 cổ phiếu (HOSE)
    """
    if entry_price <= 0 or atr0 <= 0 or nav <= 0:
        return {
            "can_buy": False,
            "quantity": 0,
            "reason": "Dữ liệu giá hoặc NAV không hợp lệ",
            "stop_loss": 0,
            "target_price": 0
        }
        
    stop_loss = round(entry_price - (STOP_ATR_MULTIPLE * atr0), 2)
    target_price = round(entry_price + (TARGET_ATR_MULTIPLE * atr0), 2)
    risk_per_share = entry_price - stop_loss
    
    if risk_per_share <= 0:
        return {
            "can_buy": False,
            "quantity": 0,
            "reason": "Khoảng cắt lỗ không hợp lệ",
            "stop_loss": stop_loss,
            "target_price": target_price
        }
        
    # 1. Giới hạn số lượng theo ngân sách rủi ro (0.5% NAV)
    risk_budget = nav * RISK_PER_TRADE_PCT
    qty_by_risk = int(risk_budget / risk_per_share)
    
    # 2. Giới hạn số lượng theo tỷ trọng tối đa cho 1 mã (20% NAV)
    max_capital_per_stock = nav * MAX_STOCK_WEIGHT_PCT
    qty_by_max_weight = int(max_capital_per_stock / entry_price)
    
    # 3. Giới hạn theo tiền mặt thực tế đang có
    qty_by_cash = int(cash_available / entry_price)
    
    # Lấy số lượng nhỏ nhất giữa các ràng buộc
    raw_qty = min(qty_by_risk, qty_by_max_weight, qty_by_cash)
    
    # Làm tròn xuống theo lô 100 cổ phiếu
    final_qty = (raw_qty // LOT_SIZE) * LOT_SIZE
    
    if final_qty < LOT_SIZE:
        return {
            "can_buy": False,
            "quantity": 0,
            "reason": f"Số lượng tính toán ({raw_qty}) không đủ 1 lô tối thiểu ({LOT_SIZE} CP)",
            "stop_loss": stop_loss,
            "target_price": target_price,
            "risk_per_share": risk_per_share,
            "total_value": 0
        }
        
    total_cost = final_qty * entry_price
    
    return {
        "can_buy": True,
        "quantity": final_qty,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "risk_per_share": risk_per_share,
        "total_cost": total_cost,
        "pct_nav": (total_cost / nav) * 100,
        "risk_amount": final_qty * risk_per_share,
        "chase_buy_limit": round(entry_price + (CHASE_BUY_MAX_ATR * atr0), 2)
    }
