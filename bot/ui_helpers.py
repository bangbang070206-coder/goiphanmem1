import html
from typing import Dict, Any, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Bàn phím tương tác nhanh ở màn hình chính"""
    keyboard = [
        [
            InlineKeyboardButton("🎯 Tín hiệu toàn thị trường", callback_data="cmd_signals"),
            InlineKeyboardButton("📈 Quét nhanh VN30", callback_data="cmd_vn30")
        ],
        [
            InlineKeyboardButton("💼 Quản trị vốn (/portfolio)", callback_data="cmd_portfolio"),
            InlineKeyboardButton("📊 Kiểm định (/backtest)", callback_data="cmd_backtest")
        ],
        [
            InlineKeyboardButton("🔔 Xem danh sách Cảnh báo", callback_data="cmd_my_alerts"),
            InlineKeyboardButton("📉 Thống kê bộ lọc BCTC", callback_data="cmd_filterstats")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_welcome_message() -> str:
    return (
        "🤖 <b>CHÀO MỪNG BẠN ĐẾN VỚI FINTECH STOCK ALERT BOT!</b>\n\n"
        "Hệ thống định lượng phân tích cổ phiếu Việt Nam tự động kết hợp:\n"
        "• <b>Lọc BCTC:</b> ROE &gt;= 15%, Dòng tiền CFO &gt; 0, Nợ/VCSH &lt;= 1.5, Tăng trưởng TTM.\n"
        "• <b>Chấm điểm Quant:</b> Phân vị 252 phiên Xu hướng - Động lượng - Giá &amp; Khối lượng.\n"
        "• <b>Quản trị vốn:</b> Định cỡ lệnh theo Rủi ro 0.5% NAV &amp; Trailing Stop ATR.\n\n"
        "<b>Các lệnh bạn có thể dùng:</b>\n"
        "👉 <code>/signals</code> : Quét toàn thị trường (chạy nền định kỳ), lấy các mã đạt điểm MUA\n"
        "👉 <code>/vn30</code> : Quét nhanh (live) 30 mã trong rổ VN30\n"
        "👉 <code>/check &lt;MÃ&gt;</code> : Tra cứu chi tiết sức khỏe + biểu đồ kỹ thuật (Ví dụ: <code>/check HPG</code>)\n"
        "👉 <code>/alert &lt;MÃ&gt;</code> : Đăng ký nhận thông báo tự động (Ví dụ: <code>/alert FPT</code>)\n"
        "👉 <code>/portfolio</code> : Xem danh mục và quản lý vốn cá nhân\n"
        "👉 <code>/backtest</code> : Xem kết quả kiểm thử chiến lược 6 tháng gần nhất\n"
        "👉 <code>/filterstats</code> : Thống kê lý do các mã bị loại bởi bộ lọc BCTC\n\n"
        "<i>Hãy bấm vào các nút bên dưới để trải nghiệm nhanh:</i>"
    )

def format_check_result(res: Dict[str, Any], position_info: Dict[str, Any] = None) -> str:
    ticker = res['ticker']
    status = res['status']
    tech = res.get('technical', {})
    fin = res.get('fundamental', {})
    scoring = res.get('scoring', {})
    
    # Biểu tượng trạng thái
    status_icon = "🟢" if status == "BUY_CANDIDATE" else ("🟡" if status == "WATCHLIST" else "🔴")
    status_text = "ỨNG VIÊN MUA (BUY_CANDIDATE)" if status == "BUY_CANDIDATE" else (
        "THEO DÕI (WATCHLIST)" if status == "WATCHLIST" else f"LOẠI BỎ ({status})"
    )
    
    msg = (
        f"{status_icon} <b>KẾT QUẢ ĐÁNH GIÁ MÃ {ticker}</b>\n"
        f"📅 <i>Ngày dữ liệu: {tech.get('date', 'Mới nhất')}</i>\n"
        f"🏷 <b>Trạng thái:</b> <b>{status_text}</b>\n\n"
    )
    
    # 1. Báo cáo tài chính
    fin_passed = fin.get('is_passed', False)
    fin_icon = "✅" if fin_passed else "❌"
    details = fin.get('details', {})
    msg += (
        f"📋 <b>1. BỘ LỌC CƠ BẢN (BCTC):</b> {fin_icon}\n"
        f"• ROE TTM: <code>{details.get('ROE', 'N/A')}</code> (Y/c &gt;= 15%)\n"
        f"• Nợ/VCSH: <code>{details.get('Debt_to_Equity', 'N/A')}</code> (Y/c &lt;= 1.5)\n"
        f"• Tăng trưởng DT: <code>{details.get('Rev_Growth', 'N/A')}</code> | LNST: <code>{details.get('NP_Growth', 'N/A')}</code>\n"
        f"• Dòng tiền CFO: <code>{details.get('CFO', 'N/A')}</code>\n\n"
    )
    
    # 2. Chấm điểm kỹ thuật 3 nhóm
    ta_score = scoring.get('ta_score')
    msg += (
        "📊 <b>2. CHẤM ĐIỂM ĐỊNH LƯỢNG (PERCENTILE 252 PHIÊN):</b>\n"
        f"• Điểm Xu hướng (Trend): <b>{scoring.get('trend_score', 'N/A')}/100</b>\n"
        f"• Điểm Động lượng (RSI): <b>{scoring.get('momentum_score', 'N/A')}/100</b>\n"
        f"• Điểm Giá &amp; Volume: <b>{scoring.get('volume_score', 'N/A')}/100</b>\n"
        f"⭐️ <b>TỔNG ĐIỂM TA_SCORE:</b> <b>{ta_score if ta_score is not None else 'N/A'}/100</b> "
        f"<i>(Ngưỡng mua: &gt;= 75)</i>\n\n"
    )
    
    # 3. Kỹ thuật chi tiết
    msg += (
        "📈 <b>3. THÔNG SỐ KỸ THUẬT:</b>\n"
        f"• Giá đóng cửa: <b>{tech.get('close', 'N/A')}</b>\n"
        f"• EMA20: <code>{tech.get('ema20', 'N/A')}</code> | EMA50: <code>{tech.get('ema50', 'N/A')}</code>\n"
        f"• RSI14: <code>{tech.get('rsi14', 'N/A')}</code> | ATR14: <code>{tech.get('atr14', 'N/A')}</code>\n"
        f"• Khối lượng tương đối (VR): <code>{tech.get('vr', 'N/A')}x</code> (Y/c &gt; 1.0)\n\n"
    )
    
    # 4. Quản trị rủi ro & Khuyến nghị
    if status == "BUY_CANDIDATE" and position_info and position_info.get("can_buy"):
        msg += (
            "🎯 <b>4. KẾ HOẠCH VÀO LỆNH & QUẢN TRỊ VỐN:</b>\n"
            f"• Giá mua tham chiếu (Entry): <b>{position_info['entry_price']}</b>\n"
            f"• Cắt lỗ (Stop Loss - 2xATR): <b>{position_info['stop_loss']}</b>\n"
            f"• Chốt lời (Target - 3xATR): <b>{position_info['target_price']}</b>\n"
            f"• Khối lượng mua an toàn: <b>{position_info['quantity']} cổ phiếu</b>\n"
            f"• Tổng giá trị: <b>{position_info['total_cost']:,.0f} VNĐ</b> ({position_info['pct_nav']:.1f}% NAV)\n"
            f"• Rủi ro tối đa: <b>{position_info['risk_amount']:,.0f} VNĐ</b> (0.5% NAV)\n"
        )
    else:
        msg += "💡 <b>Khuyến nghị:</b>\n"
        for r in res.get('reasons', []):
            clean_r = html.escape(str(r))
            msg += f"• <i>{clean_r}</i>\n"
            
    return msg
