import html
from typing import Dict, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core_logic.industry import list_industries


# ============================================================
# MENU CHÍNH
# ============================================================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu chính của bot.

    UX:
    - Kiểm tra 1 mã
    - Quét VN30
    - Quét VN100
    - Phân tích ngành
    - Quản trị vốn
    - Cảnh báo
    - Backtest
    """

    keyboard = [
        [
            InlineKeyboardButton(
                "🔎 Kiểm tra mã",
                callback_data="cmd_check_menu",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Quét VN30",
                callback_data="cmd_vn30",
            ),
            InlineKeyboardButton(
                "📈 Quét VN100",
                callback_data="cmd_vn100",
            ),
        ],
        [
            InlineKeyboardButton(
                "🏭 Phân tích ngành",
                callback_data="cmd_industries",
            ),
        ],
        [
            InlineKeyboardButton(
                "💼 Danh mục & vốn",
                callback_data="cmd_portfolio",
            ),
            InlineKeyboardButton(
                "🔔 Cảnh báo",
                callback_data="cmd_my_alerts",
            ),
        ],
        [
            InlineKeyboardButton(
                "📈 Backtest",
                callback_data="cmd_backtest",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# MENU NHẬP MÃ
# ============================================================

def get_check_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu hướng dẫn người dùng nhập mã cổ phiếu.
    """

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Quét VN30",
                callback_data="cmd_vn30",
            ),
            InlineKeyboardButton(
                "📈 Quét VN100",
                callback_data="cmd_vn100",
            ),
        ],
        [
            InlineKeyboardButton(
                "🏭 Phân tích ngành",
                callback_data="cmd_industries",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# MENU NGÀNH
# ============================================================

def get_industry_keyboard() -> InlineKeyboardMarkup:
    keyboard = []

    industries = list_industries()

    for index in range(0, len(industries), 2):
        row = []

        for item in industries[index:index + 2]:
            row.append(
                InlineKeyboardButton(
                    item["name"],
                    callback_data=f"cmd_industry_{item['code']}",
                )
            )

        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# WELCOME
# ============================================================

def format_welcome_message() -> str:
    return (
        "🤖 <b>FINTECH STOCK ADVISOR BOT</b>\n\n"
        "Trợ lý phân tích cổ phiếu Việt Nam với "
        "bộ lọc BCTC, phân tích kỹ thuật và quản trị rủi ro.\n\n"

        "📌 <b>Bot hiện tập trung vào:</b>\n"
        "• 📊 Quét rổ <b>VN30</b>\n"
        "• 📈 Quét rổ <b>VN100</b>\n"
        "• 🔎 Kiểm tra chi tiết từng mã\n"
        "• 🏭 Phân tích theo ngành\n"
        "• 💼 Quản trị vốn &amp; vị thế\n"
        "• 🔔 Theo dõi cảnh báo\n"
        "• 📈 Kiểm định chiến lược\n\n"

        "💡 <b>Cách dùng nhanh:</b>\n"
        "1️⃣ Chọn <b>VN30</b> hoặc <b>VN100</b> để tìm ứng viên\n"
        "2️⃣ Bấm <b>Kiểm tra</b> để xem chi tiết từng mã\n"
        "3️⃣ Hoặc nhập trực tiếp <code>/check HPG</code>\n\n"

        "⚠️ <i>Kết quả chỉ mang tính chất tham khảo, "
        "không phải khuyến nghị đầu tư.</i>\n\n"

        "<b>👇 Chọn chức năng bên dưới:</b>"
    )


# ============================================================
# RESULT CHECK
# ============================================================

def format_check_result(
    res: Dict[str, Any],
    position_info: Dict[str, Any] = None,
) -> str:

    ticker = res["ticker"]
    status = res["status"]

    tech = res.get("technical", {})
    fin = res.get("fundamental", {})
    scoring = res.get("scoring", {})

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status_icon = (
        "🟢"
        if status == "BUY_CANDIDATE"
        else "🟡"
        if status == "WATCHLIST"
        else "⚪"
        if status in (
            "NOT_EVALUATED",
            "DATA_INSUFFICIENT",
            "DATA_UNAVAILABLE",
        )
        else "🔴"
    )

    status_text = (
        "ỨNG VIÊN MUA"
        if status == "BUY_CANDIDATE"
        else "THEO DÕI"
        if status == "WATCHLIST"
        else "CHƯA ĐÁNH GIÁ"
        if status == "NOT_EVALUATED"
        else "CHƯA ĐỦ DỮ LIỆU"
        if status == "DATA_INSUFFICIENT"
        else "CHƯA CÓ DỮ LIỆU"
        if status == "DATA_UNAVAILABLE"
        else f"LOẠI BỎ ({status})"
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    msg = (
        f"{status_icon} <b>ĐÁNH GIÁ {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧭 <b>Ngành:</b> "
        f"{res.get('industry', {}).get('industry_name', 'Chưa xác định')}\n"
        f"🧩 <b>Chiến lược:</b> "
        f"{res.get('strategy_version', 'N/A')}\n"
        f"📅 <b>Dữ liệu:</b> "
        f"{tech.get('date', 'Mới nhất')}\n"
        f"🏷 <b>Trạng thái:</b> "
        f"{status_icon} <b>{status_text}</b>\n\n"
    )

    # --------------------------------------------------------
    # 1. BCTC / FUNDAMENTAL
    # --------------------------------------------------------

    fin_passed = fin.get("is_passed", False)
    fin_icon = "✅" if fin_passed else "❌"

    details = fin.get("details", {})

    msg += (
        f"📋 <b>1. BỘ LỌC CƠ BẢN:</b> "
        f"{fin_icon}\n"
    )

    groups = fin.get("groups") or details

    if groups:
        for group_name, checks in groups.items():

            msg += (
                f"<b>{html.escape(str(group_name))}</b>:\n"
            )

            for check in checks:

                icon = (
                    "✅"
                    if check.get("status") == "PASS"
                    else "❌"
                    if check.get("status") == "FAIL"
                    else "⚪"
                )

                value = html.escape(
                    str(check.get("value", "N/A"))
                )

                threshold = check.get("threshold")

                suffix = (
                    f" | Y/C "
                    f"{html.escape(str(threshold))}"
                    if threshold is not None
                    else ""
                )

                msg += (
                    f"{icon} "
                    f"{html.escape(str(check.get('label', check.get('code', 'metric'))))}: "
                    f"<code>{value}</code>"
                    f"{suffix}\n"
                )

    else:
        msg += "• Chưa có dữ liệu metric ngành.\n"

    msg += (
        f"⭐ <b>Điểm cơ bản:</b> "
        f"{fin.get('score', 'N/A')}/"
        f"{fin.get('max_score', 35)}\n\n"
    )

    # --------------------------------------------------------
    # 2. CHẤM ĐIỂM KỸ THUẬT
    # --------------------------------------------------------

    ta_score = scoring.get("ta_score")

    msg += (
        "📊 <b>2. ĐIỂM KỸ THUẬT</b>\n"
        f"• Xu hướng: "
        f"<b>{scoring.get('trend_score', 'N/A')}</b>/100\n"
        f"• Động lượng RSI: "
        f"<b>{scoring.get('momentum_score', 'N/A')}</b>/100\n"
        f"• Giá &amp; Volume: "
        f"<b>{scoring.get('volume_score', 'N/A')}</b>/100\n"
        f"⭐ <b>TA Score:</b> "
        f"<b>{ta_score if ta_score is not None else 'N/A'}</b>/100\n\n"
    )

    # --------------------------------------------------------
    # 3. THÔNG SỐ KỸ THUẬT
    # --------------------------------------------------------

    msg += (
        "📈 <b>3. THÔNG SỐ KỸ THUẬT</b>\n"
        f"• Giá đóng cửa: "
        f"<b>{tech.get('close', 'N/A')}</b>\n"
        f"• EMA20: "
        f"<code>{tech.get('ema20', 'N/A')}</code> | "
        f"EMA50: "
        f"<code>{tech.get('ema50', 'N/A')}</code>\n"
        f"• RSI14: "
        f"<code>{tech.get('rsi14', 'N/A')}</code> | "
        f"ATR14: "
        f"<code>{tech.get('atr14', 'N/A')}</code>\n"
        f"• Volume Ratio: "
        f"<code>{tech.get('vr', 'N/A')}x</code>\n\n"
    )

    # --------------------------------------------------------
    # 4. GATE / TÍN HIỆU
    # --------------------------------------------------------

    gates = res.get("gates", {})

    if gates:

        msg += "🧪 <b>4. KIỂM TRA TÍN HIỆU</b>\n"

        for gate_name, gate in gates.items():

            icon = (
                "✅"
                if gate.get("passed")
                else "❌"
            )

            msg += (
                f"{icon} <b>{html.escape(str(gate_name))}</b>: "
                f"{html.escape(str(gate.get('observed', 'N/A')))}"
            )

            threshold = gate.get("threshold")

            if threshold not in (None, ""):
                msg += (
                    f" | "
                    f"{html.escape(str(threshold))}"
                )

            msg += "\n"

        msg += "\n"

    # --------------------------------------------------------
    # 5. POSITION / REASON
    # --------------------------------------------------------

    if (
        status == "BUY_CANDIDATE"
        and position_info
        and position_info.get("can_buy")
    ):

        msg += (
            "🎯 <b>5. QUẢN TRỊ VỊ THẾ</b>\n"
            f"• Entry: "
            f"<b>{position_info['entry_price']}</b>\n"
            f"• Stop Loss: "
            f"<b>{position_info['stop_loss']}</b>\n"
            f"• Target: "
            f"<b>{position_info['target_price']}</b>\n"
            f"• Khối lượng: "
            f"<b>{position_info['quantity']} CP</b>\n"
            f"• Giá trị: "
            f"<b>{position_info['total_cost']:,.0f} VNĐ</b>\n"
            f"• Tỷ trọng NAV: "
            f"<b>{position_info['pct_nav']:.1f}%</b>\n"
            f"• Rủi ro tối đa: "
            f"<b>{position_info['risk_amount']:,.0f} VNĐ</b>\n"
        )

    else:

        msg += "💡 <b>Nhận xét:</b>\n"

        reasons = res.get("reasons", [])

        if reasons:

            for reason in reasons:
                msg += (
                    f"• <i>{html.escape(str(reason))}</i>\n"
                )

        else:
            msg += "• Chưa có nhận xét bổ sung.\n"

    return msg