import html
from typing import Dict, Any, Optional

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
                "💼 Quản trị vốn",
                callback_data="cmd_portfolio",
            ),
            InlineKeyboardButton(
                "🔔 Cảnh báo",
                callback_data="cmd_my_alerts",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Backtest",
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
        "🤖 <b>STOCK ADVISOR BOT</b>\n\n"
        "Trợ lý phân tích cổ phiếu Việt Nam với "
        "bộ lọc BCTC, phân tích kỹ thuật và quản trị vốn.\n\n"

        "📌 <b>Bot hiện tập trung vào:</b>\n"
        "• 📊 Quét rổ <b>VN30</b>\n"
        "• 📈 Quét rổ <b>VN100</b>\n"
        "• 🔎 Kiểm tra chi tiết từng mã\n"
        "• 🏭 Phân tích theo ngành\n"
        "• 💼 Quản trị vốn &amp; vị thế\n"
        "• 🔔 Theo dõi cảnh báo\n"
        "• 📊 Backtest chiến lược\n\n"

        "🧩 <b>Chiến lược:</b> "
        "<code>3.0.0-student-mvp</code>\n\n"

        "💡 <b>Cách dùng nhanh:</b>\n"
        "1️⃣ Chọn <b>VN30</b> hoặc <b>VN100</b> để tìm ứng viên\n"
        "2️⃣ Bấm <b>Kiểm tra</b> để xem chi tiết từng mã\n"
        "3️⃣ Hoặc nhập trực tiếp <code>/check HPG</code>\n\n"

        "⚠️ <i>Kết quả chỉ mang tính chất tham khảo, "
        "không phải khuyến nghị đầu tư.</i>\n\n"

        "<b>👇 Chọn chức năng bên dưới:</b>"
    )


# ============================================================
# HELPER
# ============================================================

def _fmt_number(value, digits=2, suffix=""):
    """
    Format số an toàn cho UI.
    """
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return html.escape(str(value))


def _fmt_percent(value):
    """
    0.165 -> 16.51%
    """
    if value is None:
        return "N/A"

    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return html.escape(str(value))


def _fmt_growth(value):
    """
    Format growth:
    0.342 -> +34.28%
    -0.037 -> -3.77%
    """
    if value is None:
        return "N/A"

    try:
        number = float(value) * 100
        return f"{number:+.2f}%"
    except (TypeError, ValueError):
        return html.escape(str(value))


def _status_icon(status):
    if status == "BUY_CANDIDATE":
        return "🟢"

    if status == "WATCHLIST":
        return "🟡"

    if status in (
        "NOT_EVALUATED",
        "DATA_INSUFFICIENT",
        "DATA_UNAVAILABLE",
    ):
        return "⚪"

    return "🔴"


def _status_text(status):
    mapping = {
        "BUY_CANDIDATE": "ỨNG VIÊN MUA",
        "WATCHLIST": "THEO DÕI",
        "NOT_EVALUATED": "CHƯA ĐÁNH GIÁ",
        "DATA_INSUFFICIENT": "CHƯA ĐỦ DỮ LIỆU",
        "DATA_UNAVAILABLE": "CHƯA CÓ DỮ LIỆU",
    }

    return mapping.get(status, f"LOẠI BỎ ({status})")


def _gate_icon(passed):
    return "✅" if passed else "❌"


# ============================================================
# RESULT CHECK - STRATEGY 3.0
# ============================================================

def format_check_result(
    res: Dict[str, Any],
    position_info: Optional[Dict[str, Any]] = None,
) -> str:

    ticker = res.get("ticker", "N/A")
    status = res.get("status", "NOT_EVALUATED")

    tech = res.get("technical") or {}
    fin = res.get("fundamental") or {}
    scoring = res.get("scoring") or {}
    gates = res.get("gates") or {}
    industry = res.get("industry") or {}

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status_icon = _status_icon(status)
    status_text = _status_text(status)

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    industry_name = industry.get(
        "industry_name",
        "Chưa xác định",
    )

    strategy_version = res.get(
        "strategy_version",
        "N/A",
    )

    data_date = tech.get(
        "date",
        "Mới nhất",
    )

    msg = (
        f"{status_icon} <b>ĐÁNH GIÁ {html.escape(str(ticker))}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏭 <b>Ngành:</b> "
        f"{html.escape(str(industry_name))}\n"
        f"🧩 <b>Chiến lược:</b> "
        f"<code>{html.escape(str(strategy_version))}</code>\n"
        f"📅 <b>Dữ liệu giá:</b> "
        f"{html.escape(str(data_date))}\n\n"

        f"🏷 <b>TRẠNG THÁI</b>\n"
        f"{status_icon} <b>{status_text}</b>\n"
        f"📌 Tín hiệu: "
        f"<b>{html.escape(str(res.get('signal', 'N/A')))}</b>\n\n"
    )

    # ========================================================
    # 1. BCTC
    # ========================================================

    fin_passed = bool(fin.get("is_passed", False))
    fin_icon = "✅" if fin_passed else "❌"

    fin_score = fin.get("score")
    fin_max = fin.get("max_score", 35)

    roe = fin.get("roe")
    rev_growth = fin.get("rev_growth")
    np_growth = fin.get("np_growth")

    msg += (
        f"📋 <b>1. BCTC</b> {fin_icon}\n"
        f"• Trạng thái: "
        f"<b>{'ĐẠT' if fin_passed else 'CHƯA ĐẠT'}</b>\n"
        f"• Điểm BCTC: "
        f"<b>{fin_score if fin_score is not None else 'N/A'}/"
        f"{fin_max}</b>\n"
        f"• ROE: "
        f"<code>{_fmt_percent(roe)}</code>\n"
        f"• Tăng trưởng doanh thu: "
        f"<code>{_fmt_growth(rev_growth)}</code>\n"
        f"• Tăng trưởng LNST: "
        f"<code>{_fmt_growth(np_growth)}</code>\n"
    )

    fin_reason = fin.get("reason")

    if fin_reason:
        msg += (
            f"• Nhận xét: "
            f"<i>{html.escape(str(fin_reason))}</i>\n"
        )

    msg += "\n"

    # ========================================================
    # 2. KỸ THUẬT
    # ========================================================

    technical_score = scoring.get(
        "technical_score"
    )

    msg += (
        "📊 <b>2. KỸ THUẬT</b>\n"
        f"⭐ Điểm kỹ thuật: "
        f"<b>{_fmt_number(technical_score, 1)}</b>/65\n"
        f"• Giá đóng cửa: "
        f"<code>{_fmt_number(tech.get('close'))}</code>\n"
        f"• EMA20: "
        f"<code>{_fmt_number(tech.get('ema20'))}</code>\n"
        f"• EMA50: "
        f"<code>{_fmt_number(tech.get('ema50'))}</code>\n"
        f"• RSI14: "
        f"<code>{_fmt_number(tech.get('rsi14'), 1)}</code>\n"
        f"• Volume Ratio: "
        f"<code>{_fmt_number(tech.get('volume_ratio'), 2)}x</code>\n"
        f"• Khoảng cách EMA20: "
        f"<code>{_fmt_number(tech.get('distance_atr'), 2)} ATR</code>\n"
        f"• ATR14: "
        f"<code>{_fmt_number(tech.get('atr14'))}</code>\n\n"
    )

    # ========================================================
# 4. TỔNG ĐIỂM
# ========================================================
    # ========================================================
    # 4. TỔNG ĐIỂM
    # ========================================================

    overall_score = scoring.get(
        "ta_score"
    )

    if overall_score is None:
        overall_score = scoring.get(
            "overall_score"
        )

    fundamental_score = scoring.get(
        "fundamental_score"
    )

    msg += (
        "⭐ <b>4. TỔNG ĐIỂM</b>\n"
        f"• BCTC: "
        f"<b>{_fmt_number(fundamental_score, 1)}</b>/35\n"
        f"• Kỹ thuật: "
        f"<b>{_fmt_number(technical_score, 1)}</b>/65\n"
        f"• Tổng hợp: "
        f"<b>{_fmt_number(overall_score, 1)}</b>/100\n\n"
    )

    # ========================================================
    # 5. NHẬN XÉT
    # ========================================================

    msg += "💡 <b>5. NHẬN XÉT</b>\n"

    reasons = res.get("reasons") or []

    if reasons:
        for reason in reasons:
            msg += (
                f"• {html.escape(str(reason))}\n"
            )
    else:
        msg += "• Chưa có nhận xét bổ sung.\n"

    # ========================================================
    # 6. QUẢN TRỊ VỊ THẾ
    # ========================================================

    if (
        status == "BUY_CANDIDATE"
        and position_info
        and position_info.get("can_buy")
    ):
        msg += (
            "\n🎯 <b>6. QUẢN TRỊ VỊ THẾ</b>\n"
            f"• Entry: "
            f"<b>{position_info.get('entry_price', 'N/A')}</b>\n"
            f"• Stop Loss: "
            f"<b>{position_info.get('stop_loss', 'N/A')}</b>\n"
            f"• Target: "
            f"<b>{position_info.get('target_price', 'N/A')}</b>\n"
            f"• Khối lượng: "
            f"<b>{position_info.get('quantity', 'N/A')} CP</b>\n"
            f"• Giá trị: "
            f"<b>{position_info.get('total_cost', 0):,.0f} VNĐ</b>\n"
            f"• Tỷ trọng NAV: "
            f"<b>{position_info.get('pct_nav', 0):.1f}%</b>\n"
            f"• Rủi ro tối đa: "
            f"<b>{position_info.get('risk_amount', 0):,.0f} VNĐ</b>\n"
        )

    return msg