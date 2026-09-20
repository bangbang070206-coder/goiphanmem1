import re
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes
)
from telegram.request import HTTPXRequest

from config import TELEGRAM_BOT_TOKEN, DEFAULT_NAV, SIGNALS_SCAN_INTERVAL_MINUTES
from data_pipeline.fetcher import fetch_stock_quote_history, fetch_stock_financials, fetch_vn30_tickers
from core_logic.scanner import run_full_market_scan, get_latest_scan
from core_logic.strategy import evaluate_ticker
from risk_management.position_sizing import calculate_position_size
from backtesting.performance_report import run_portfolio_backtest, format_backtest_message
from database.db_manager import (
    add_user_alert, remove_user_alert,
    get_user_alerts
)
from bot.ui_helpers import (
    get_main_menu_keyboard, format_welcome_message,
    format_check_result
)
from bot.chart_helpers import build_price_chart

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==========================================
# HÀM TIỆN ÍCH
# ==========================================

async def safe_edit_message(msg: Message, text: str, reply_markup=None):
    """Gửi tin nhắn HTML an toàn, tự động fallback về văn bản thường nếu Telegram từ chối tag"""
    try:
        await msg.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Lỗi gửi HTML ({e}), đang fallback về văn bản thuần...")
        plain_text = re.sub(r'<[^>]+>', '', text)
        await msg.edit_text(plain_text, reply_markup=reply_markup)

# ==========================================
# LOGIC LÕI (dùng chung cho cả Command lẫn Button)
# Nhận thẳng các giá trị đã trích xuất (message, user_id, ticker...)
# thay vì phụ thuộc vào kiểu của "update" -> tránh lỗi khi update thực
# ra là CallbackQuery (không có .effective_user, không set được .args)
# ==========================================

async def do_start(message: Message):
    text = format_welcome_message()
    await message.reply_html(text, reply_markup=get_main_menu_keyboard())

SIGNALS_PAGE_SIZE = 10
VN30_PAGE_SIZE = 10

def _render_results_page(results: list, page: int, page_size: int, title_found: str, title_empty: str, meta_note: str, page_prefix: str):
    """Dựng nội dung + bàn phím phân trang cho một danh sách kết quả đã chấm điểm.
    Dùng chung cho /signals (quét toàn thị trường từ cache nền) và /vn30 (quét live)."""
    buy_candidates = [r for r in results if r['status'] == 'BUY_CANDIDATE']
    buy_candidates.sort(key=lambda x: x.get('scoring', {}).get('ta_score', 0) or 0, reverse=True)

    if buy_candidates:
        source_list = buy_candidates
        header = f"{title_found}\n<i>{meta_note}</i>\n\n"
    else:
        source_list = sorted(results, key=lambda x: x.get('scoring', {}).get('ta_score', 0) or 0, reverse=True)
        header = f"{title_empty}\n<i>{meta_note}</i>\n\n"

    total_items = len(source_list)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    page_items = source_list[start:start + page_size]

    reply_text = header + f"<i>Trang {page + 1}/{total_pages}</i>\n\n"
    keyboard = []
    for i, c in enumerate(page_items, start + 1):
        score = c.get('scoring', {}).get('ta_score', 'N/A')
        close = c.get('technical', {}).get('close', 'N/A')
        fin_status = "✅ BCTC Đạt" if c.get('fundamental', {}).get('is_passed') else "❌ BCTC Chưa đạt"
        reply_text += f"{i}. <b>{c['ticker']}</b> - Giá: {close} | Điểm TA: <b>{score}/100</b> ({fin_status})\n"
        keyboard.append([InlineKeyboardButton(f"🔍 Xem chi tiết {c['ticker']}", callback_data=f"cmd_check_{c['ticker']}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Trước", callback_data=f"{page_prefix}{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Sau ▶️", callback_data=f"{page_prefix}{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔙 Quay lại Menu Chính", callback_data="cmd_start")])

    return reply_text, InlineKeyboardMarkup(keyboard)

async def do_signals(message: Message, application, page: int = 0, edit_target: Message = None):
    scan = get_latest_scan(application)
    results = scan.get("results") if scan else None

    if not results:
        text = (
            "⏳ <i>Hệ thống đang quét toàn bộ thị trường lần đầu (chạy nền), việc này có thể mất vài phút "
            "tùy số lượng mã. Vui lòng thử lại /signals sau ít phút, hoặc bấm 'Quét nhanh VN30' để xem ngay "
            "kết quả của 30 mã vốn hóa lớn nhất trong lúc chờ.</i>"
        )
        if edit_target:
            await safe_edit_message(edit_target, text)
        else:
            await message.reply_html(text)
        return

    scanned_at = scan.get("timestamp", "")
    total_listed = scan.get("total_listed", len(results))
    meta_note = f"Đã qua lọc BCTC và đạt TA_Score >= 75 | {len(results)}/{total_listed} mã có dữ liệu | Cập nhật: {scanned_at} UTC"

    reply_text, markup = _render_results_page(
        results, page, SIGNALS_PAGE_SIZE,
        title_found="🎯 <b>DANH SÁCH CỔ PHIẾU ĐẠT TÍN HIỆU MUA (QUÉT TOÀN THỊ TRƯỜNG)</b>",
        title_empty="🟡 <b>Hiện thị trường chưa có mã nào vượt ngưỡng MUA (TA_Score >= 75).</b>",
        meta_note=meta_note,
        page_prefix="cmd_signals_p"
    )

    if edit_target:
        await safe_edit_message(edit_target, reply_text, markup)
    else:
        msg = await message.reply_html("🔎 <i>Đang tổng hợp kết quả từ lần quét gần nhất...</i>")
        await safe_edit_message(msg, reply_text, markup)

def _scan_vn30_sync():
    """Phần việc nặng của quét VN30 - chạy trong thread riêng để không treo bot."""
    tickers = fetch_vn30_tickers()
    results = []
    for t in tickers:
        try:
            df = fetch_stock_quote_history(t, days=450)
            if df is not None and not df.empty:
                results.append(evaluate_ticker(t, df))
        except Exception as e:
            logger.warning(f"[VN30] Lỗi khi xử lý mã {t}: {e}")
    return results, len(tickers)

async def do_vn30(message: Message, page: int = 0, edit_target: Message = None):
    """Quét TRỰC TIẾP (live) rổ VN30 - lấy danh sách 30 mã qua API vnstock.Listing
    ngay lúc bấm, không cần chờ job quét nền như /signals (toàn thị trường)."""
    loading_text = "⏳ <i>Đang quét nhanh rổ VN30 (gọi API trực tiếp, chỉ 30 mã nên sẽ nhanh hơn)...</i>"
    if edit_target:
        await safe_edit_message(edit_target, loading_text)
        target = edit_target
    else:
        target = await message.reply_html(loading_text)

    results, total = await asyncio.to_thread(_scan_vn30_sync)

    if not results:
        await safe_edit_message(target, "⚠️ <i>Không lấy được dữ liệu cho rổ VN30. Vui lòng thử lại sau ít phút.</i>")
        return

    meta_note = f"Quét trực tiếp {len(results)}/{total} mã VN30 | Vừa cập nhật"
    reply_text, markup = _render_results_page(
        results, page, VN30_PAGE_SIZE,
        title_found="🎯 <b>TÍN HIỆU MUA TRONG RỔ VN30</b>",
        title_empty="🟡 <b>Rổ VN30 hiện chưa có mã nào đạt tín hiệu MUA (TA_Score >= 75).</b>",
        meta_note=meta_note,
        page_prefix="cmd_vn30_p"
    )
    await safe_edit_message(target, reply_text, markup)

async def do_filterstats(message: Message, application):
    """Thống kê lý do các mã bị loại bởi bộ lọc BCTC trên lần quét toàn thị trường
    gần nhất - để trả lời câu hỏi 'bộ lọc có đang loại đúng lý do không, hay do thiếu dữ liệu'."""
    scan = get_latest_scan(application)
    results = scan.get("results") if scan else None
    if not results:
        await message.reply_html(
            "⏳ <i>Chưa có dữ liệu quét toàn thị trường để thống kê. Vui lòng đợi job quét nền hoàn tất "
            "(hoặc dùng /signals để kiểm tra tiến độ).</i>"
        )
        return

    total = len(results)
    status_counts = {}
    reason_counts = {"ROE": 0, "Nợ/VCSH": 0, "Tăng trưởng DT": 0, "Tăng trưởng LNST": 0, "CFO": 0}

    for r in results:
        fin = r.get('fundamental', {}) or {}
        status = fin.get('status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
        reason = fin.get('reason') or ''
        for key in reason_counts:
            if key in reason:
                reason_counts[key] += 1

    text = (
        "📊 <b>THỐNG KÊ BỘ LỌC BCTC (LẦN QUÉT TOÀN THỊ TRƯỜNG GẦN NHẤT)</b>\n"
        f"<i>Tổng số mã có dữ liệu: {total}</i>\n\n"
        "<b>Theo trạng thái:</b>\n"
    )
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        text += f"• <code>{status}</code>: {count} mã ({pct:.1f}%)\n"

    text += (
        "\n<b>Bị loại vì từng tiêu chí cụ thể</b> <i>(1 mã có thể trượt nhiều tiêu chí cùng lúc):</i>\n"
    )
    for name, count in reason_counts.items():
        text += f"• {name}: {count} mã\n"

    text += (
        "\n<i>💡 Nếu phần lớn rơi vào DATA_INSUFFICIENT/DATA_UNAVAILABLE thay vì OUT_OF_UNIVERSE, "
        "đó là dấu hiệu vẫn còn vấn đề lấy/parse dữ liệu, không phải do doanh nghiệp thực sự yếu kém.</i>"
    )

    keyboard = [[InlineKeyboardButton("🔙 Menu Chính", callback_data="cmd_start")]]
    await message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def do_check(message: Message, ticker: str):
    ticker = ticker.upper().strip()
    msg = await message.reply_html(f"⏳ <i>Đang phân tích dữ liệu cho mã {ticker}...</i>")

    df = fetch_stock_quote_history(ticker, days=450)
    res = evaluate_ticker(ticker, df)

    pos_info = None
    if res.get('technical') and res['technical'].get('close') and res['technical'].get('atr14'):
        pos_info = calculate_position_size(
            entry_price=res['technical']['close'],
            atr0=res['technical']['atr14'],
            nav=DEFAULT_NAV,
            cash_available=DEFAULT_NAV
        )

    reply_text = format_check_result(res, pos_info)

    keyboard = [
        [
            InlineKeyboardButton(f"🔔 Nhận Alert {ticker}", callback_data=f"cmd_alert_{ticker}"),
            InlineKeyboardButton("🎯 Xem Tín hiệu khác", callback_data="cmd_signals")
        ],
        [InlineKeyboardButton("🔙 Menu Chính", callback_data="cmd_start")]
    ]
    await safe_edit_message(msg, reply_text, InlineKeyboardMarkup(keyboard))

    # Gửi thêm biểu đồ giá + EMA + RSI (dùng lại df đã fetch, không tốn thêm lượt gọi API)
    try:
        chart_buf = build_price_chart(df, ticker)
        await message.reply_photo(photo=chart_buf, caption=f"📈 Biểu đồ giá & chỉ báo kỹ thuật - {ticker}")
    except Exception as e:
        logger.warning(f"Không thể tạo biểu đồ cho {ticker}: {e}")

async def do_alert(message: Message, user_id: int, ticker: str = None):
    if not ticker:
        alerts = get_user_alerts(user_id)
        if alerts:
            alert_str = ", ".join(alerts)
            await message.reply_html(
                f"🔔 <b>Các mã bạn đang đăng ký nhận cảnh báo:</b> <code>{alert_str}</code>\n\n"
                f"Để thêm mã mới, gõ: <code>/alert &lt;MÃ&gt;</code> (Ví dụ: <code>/alert HPG</code>)"
            )
        else:
            await message.reply_html(
                "ℹ️ Bạn chưa đăng ký cảnh báo mã nào.\n"
                "Gõ: <code>/alert &lt;MÃ&gt;</code> để đăng ký (Ví dụ: <code>/alert HPG</code>)"
            )
        return

    ticker = ticker.upper().strip()
    add_user_alert(user_id, ticker)
    await message.reply_html(
        f"✅ <b>Đã đăng ký nhận cảnh báo cho mã {ticker}!</b>\n"
        f"Hệ thống sẽ tự động quét và gửi tin nhắn cho bạn khi có tín hiệu Mua/Bán vi phạm ngưỡng."
    )

async def do_portfolio(message: Message):
    msg = (
        "💼 <b>QUẢN TRỊ DANH MỤC & VỐN ĐẦU TƯ</b>\n\n"
        f"💰 <b>Vốn NAV giả định:</b> <code>{DEFAULT_NAV:,.0f} VNĐ</code>\n"
        f"🛡 <b>Quy tắc rủi ro:</b> Tối đa 0.5% NAV/lệnh (~{DEFAULT_NAV * 0.005:,.0f} VNĐ)\n"
        f"📊 <b>Phân bổ tối đa:</b> 20% NAV/mã | Tối đa 5 mã\n"
        f"📉 <b>Thoát lệnh:</b> Cắt lỗ Stop0 = Entry - 2*ATR, Chốt lời Target0 = Entry + 3*ATR\n\n"
        "<i>💡 Gõ <code>/signals</code> để tìm kiếm cổ phiếu mở vị thế mới!</i>"
    )
    keyboard = [
        [InlineKeyboardButton("🎯 Quét Tín hiệu Ngay", callback_data="cmd_signals")],
        [InlineKeyboardButton("🔙 Menu Chính", callback_data="cmd_start")]
    ]
    await message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def do_backtest(message: Message):
    msg = await message.reply_html("⏳ <i>Đang chạy kiểm thử Backtesting trên 8 mã cổ phiếu tiêu biểu... Vui lòng đợi trong giây lát...</i>")

    report = run_portfolio_backtest(lookback_days=120)
    reply_text = format_backtest_message(report)

    keyboard = [[InlineKeyboardButton("🔙 Quay lại Menu Chính", callback_data="cmd_start")]]
    await safe_edit_message(msg, reply_text, InlineKeyboardMarkup(keyboard))

# ==========================================
# CÁC HÀM XỬ LÝ LỆNH (COMMAND HANDLERS)
# Chỉ có nhiệm vụ: trích xuất input từ update/context rồi gọi logic lõi
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_start(update.message)

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_signals(update.message, context.application)

async def vn30_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_vn30(update.message)

async def filterstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_filterstats(update.message, context.application)

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html(
            "⚠️ <b>Vui lòng nhập mã cổ phiếu cần tra cứu.</b>\nVí dụ: <code>/check HPG</code> hoặc <code>/check FPT</code>"
        )
        return
    await do_check(update.message, context.args[0])

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ticker = context.args[0] if context.args else None
    await do_alert(update.message, user_id, ticker)

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_portfolio(update.message)

async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_backtest(update.message)

# ==========================================
# XỬ LÝ SỰ KIỆN NÚT BẤM (CALLBACK QUERY)
# Trích xuất input từ CallbackQuery (query.message, query.from_user)
# rồi gọi CÙNG một logic lõi ở trên -> không còn giả lập update/context
# ==========================================

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý các cú click trên bàn phím Inline Keyboard"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    message = query.message
    user_id = query.from_user.id  # CallbackQuery dùng from_user, KHÔNG có effective_user

    if data == "cmd_start":
        await do_start(message)
    elif data == "cmd_signals":
        await do_signals(message, context.application)
    elif data.startswith("cmd_signals_p"):
        page = int(data.replace("cmd_signals_p", ""))
        await do_signals(message, context.application, page=page, edit_target=message)
    elif data == "cmd_vn30":
        await do_vn30(message)
    elif data.startswith("cmd_vn30_p"):
        page = int(data.replace("cmd_vn30_p", ""))
        await do_vn30(message, page=page, edit_target=message)
    elif data == "cmd_filterstats":
        await do_filterstats(message, context.application)
    elif data.startswith("cmd_check_"):
        ticker = data.replace("cmd_check_", "")
        await do_check(message, ticker)
    elif data.startswith("cmd_alert_"):
        ticker = data.replace("cmd_alert_", "")
        await do_alert(message, user_id, ticker)
    elif data == "cmd_portfolio":
        await do_portfolio(message)
    elif data == "cmd_backtest":
        await do_backtest(message)
    elif data == "cmd_my_alerts":
        await do_alert(message, user_id, None)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bắt mọi ngoại lệ và gửi tin nhắn cảnh báo thay vì im lặng"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"⚠️ Có sự cố định dạng hoặc dữ liệu: {context.error}"
            )
        except Exception:
            pass

def build_application():
    """Khởi tạo ứng dụng Telegram Application với timeout mở rộng chống rớt mạng"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.warning("Chưa cấu hình TELEGRAM_BOT_TOKEN trong config.py!")

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("signals", signals_command))
    app.add_handler(CommandHandler("vn30", vn30_command))
    app.add_handler(CommandHandler("filterstats", filterstats_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_error_handler(error_handler)

    # Đăng ký job quét toàn thị trường định kỳ (chạy nền, không chặn bot trả lời tin nhắn)
    if app.job_queue is not None:
        app.job_queue.run_repeating(
            run_full_market_scan,
            interval=SIGNALS_SCAN_INTERVAL_MINUTES * 60,
            first=5,  # Chờ 5s sau khi bot khởi động rồi bắt đầu quét lần đầu
            name="full_market_scan"
        )
        logger.info(f"Đã đăng ký quét toàn thị trường định kỳ mỗi {SIGNALS_SCAN_INTERVAL_MINUTES} phút.")
    else:
        logger.warning(
            "JobQueue chưa khả dụng! Cài đặt bằng lệnh: "
            "pip install \"python-telegram-bot[job-queue]\" để bật tính năng quét định kỳ. "
            "/signals sẽ không có dữ liệu cho tới khi bạn cài đặt và khởi động lại bot."
        )

    return app
