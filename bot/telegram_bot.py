import re
import logging
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from config import TELEGRAM_BOT_TOKEN, DEFAULT_NAV

from data_pipeline.fetcher import (
    fetch_stock_quote_history,
    fetch_stock_financials,
    fetch_vn30_tickers,
    fetch_all_listed_tickers,
    fetch_tickers_by_industry,
)

from core_logic.scanner import (
    get_latest_scan,
    save_scan_result,
    is_scan_fresh,
)

from core_logic.strategy import evaluate_ticker

from core_logic.industry import (
    get_industry_filter,
    list_industries,
)

from risk_management.position_sizing import (
    calculate_position_size,
)

from backtesting.performance_report import (
    run_portfolio_backtest,
    format_backtest_message,
    DEFAULT_BACKTEST_TICKERS,
)

from database.db_manager import (
    add_user_alert,
    remove_user_alert,
    get_user_alerts,
)

from bot.ui_helpers import (
    get_main_menu_keyboard,
    get_industry_keyboard,
    format_welcome_message,
    format_check_result,
)

from bot.chart_helpers import build_price_chart


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ==========================================
# HÀM TIỆN ÍCH
# ==========================================

async def safe_edit_message(
    msg: Message,
    text: str,
    reply_markup=None,
):
    """
    Gửi tin nhắn HTML an toàn.
    Nếu Telegram từ chối HTML thì fallback về text thường.
    """

    try:
        await msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    except Exception as e:
        logger.warning(
            f"Lỗi gửi HTML ({e}), đang fallback về văn bản thuần..."
        )

        plain_text = re.sub(
            r"<[^>]+>",
            "",
            text,
        )

        await msg.edit_text(
            plain_text,
            reply_markup=reply_markup,
        )


# ==========================================
# START
# ==========================================

async def do_start(
    message: Message,
):
    text = format_welcome_message()

    await message.reply_html(
        text,
        reply_markup=get_main_menu_keyboard(),
    )


# ==========================================
# INDUSTRIES
# ==========================================

async def do_industries(
    message: Message,
):
    text = (
        "🏭 <b>CHỌN NGÀNH PHÂN TÍCH</b>\n\n"
        "Chọn một ngành để hệ thống lấy đúng danh sách mã, "
        "áp dụng bộ tiêu chí riêng và trả kết quả "
        "PASS/FAIL/INSUFFICIENT_DATA.\n\n"
        "Mã ngành cũng có thể dùng trực tiếp:\n"
        "<code>/industry banking</code>"
    )

    await message.reply_html(
        text,
        reply_markup=get_industry_keyboard(),
    )


# ==========================================
# CONSTANTS
# ==========================================

SIGNALS_PAGE_SIZE = 10
VN30_PAGE_SIZE = 10
SIGNALS_FRESHNESS_MINUTES = 20

BACKTEST_LOOKBACK_DAYS = 120


# ==========================================
# RENDER RESULTS
# ==========================================

def _render_results_page(
    results: list,
    page: int,
    page_size: int,
    title_found: str,
    title_empty: str,
    meta_note: str,
    page_prefix: str,
    suggest_vn30: bool = False,
):
    """
    Dựng nội dung + bàn phím phân trang
    cho danh sách kết quả.
    """

    buy_candidates = [
        r
        for r in results
        if r.get("status") == "BUY_CANDIDATE"
    ]

    buy_candidates.sort(
        key=lambda x: (
            x.get("scoring", {}).get("ta_score", 0)
            or 0
        ),
        reverse=True,
    )

    if buy_candidates:
        source_list = buy_candidates

        header = (
            f"{title_found}\n"
            f"<i>{meta_note}</i>\n\n"
        )

    else:
        source_list = []

        header = (
            f"{title_empty}\n"
            f"<i>{meta_note}</i>\n\n"
        )

    total_items = len(source_list)

    total_pages = max(
        1,
        (total_items + page_size - 1) // page_size,
    )

    page = max(
        0,
        min(page, total_pages - 1),
    )

    start = page * page_size

    page_items = source_list[
        start:start + page_size
    ]

    reply_text = (
        header
        + f"<i>Trang {page + 1}/{total_pages}</i>\n\n"
    )

    for i, c in enumerate(
        page_items,
        start + 1,
    ):
        score = c.get(
            "scoring",
            {},
        ).get(
            "ta_score",
            "N/A",
        )

        close = c.get(
            "technical",
            {},
        ).get(
            "close",
            "N/A",
        )

        fin_status = (
            "✅ BCTC Đạt"
            if c.get(
                "fundamental",
                {},
            ).get(
                "is_passed"
            )
            else "❌ BCTC Chưa đạt"
        )

        reply_text += (
            f"{i}. <b>{c['ticker']}</b> - "
            f"Giá: {close} | "
            f"Điểm TA: <b>{score}/100</b> "
            f"({fin_status})\n"
        )

    reply_text += (
        "\n<i>Chỉ mã có đủ dữ liệu, BCTC đạt "
        "và đạt điều kiện chiến lược mới được "
        "đưa vào danh sách này.</i>"
    )

    keyboard = []

    nav_row = []

    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                "◀️ Trước",
                callback_data=(
                    f"{page_prefix}{page - 1}"
                ),
            )
        )

    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                "Sau ▶️",
                callback_data=(
                    f"{page_prefix}{page + 1}"
                ),
            )
        )

    if nav_row:
        keyboard.append(nav_row)

    for c in page_items:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔎 Kiểm tra {c['ticker']}",
                    callback_data=(
                        f"cmd_check_{c['ticker']}"
                    ),
                )
            ]
        )

    if suggest_vn30:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📈 Thử quét nhanh VN30",
                    callback_data="cmd_vn30",
                )
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Quay lại Menu Chính",
                callback_data="cmd_start",
            )
        ]
    )

    return (
        reply_text,
        InlineKeyboardMarkup(keyboard),
    )


# ==========================================
# QUÉT TOÀN THỊ TRƯỜNG
# ==========================================

async def _scan_market_async(
    progress_cb=None,
):
    """
    Quét toàn thị trường HOSE.
    """

    tickers = fetch_all_listed_tickers(
        exchange="HOSE",
    )

    sem = asyncio.Semaphore(5)

    async def _process(ticker):
        async with sem:

            try:
                df = await asyncio.to_thread(
                    fetch_stock_quote_history,
                    ticker,
                    450,
                )

                if (
                    df is not None
                    and not df.empty
                ):
                    return await asyncio.to_thread(
                        evaluate_ticker,
                        ticker,
                        df,
                    )

            except Exception as e:
                logger.warning(
                    "[Signals] Lỗi khi xử lý mã %s: %s",
                    ticker,
                    e,
                )

            return None

    tasks = [
        asyncio.create_task(
            _process(ticker)
        )
        for ticker in tickers
    ]

    results = []

    done_count = 0

    for task in asyncio.as_completed(tasks):

        result = await task

        done_count += 1

        if result is not None:
            results.append(result)

        if progress_cb:
            await progress_cb(
                done_count,
                len(tickers),
            )

    return (
        results,
        len(tickers),
    )


# ==========================================
# QUÉT DANH SÁCH MÃ
# ==========================================

async def _scan_tickers_async(
    tickers,
    progress_cb=None,
):
    sem = asyncio.Semaphore(5)

    async def _process(
        ticker,
    ):
        async with sem:

            try:
                df = await asyncio.to_thread(
                    fetch_stock_quote_history,
                    ticker,
                    450,
                )

                if (
                    df is not None
                    and not df.empty
                ):
                    return await asyncio.to_thread(
                        evaluate_ticker,
                        ticker,
                        df,
                    )

            except Exception as exc:
                logger.warning(
                    "Lỗi khi xử lý mã %s: %s",
                    ticker,
                    exc,
                )

            return None

    tasks = [
        asyncio.create_task(
            _process(ticker)
        )
        for ticker in tickers
    ]

    results = []

    for index, task in enumerate(
        asyncio.as_completed(tasks),
        1,
    ):
        result = await task

        if result is not None:
            results.append(result)

        if progress_cb:
            await progress_cb(
                index,
                len(tickers),
            )

    return results


# ==========================================
# QUÉT NGÀNH
# ==========================================

async def _scan_industry_async(
    tickers,
    progress_cb=None,
):
    """
    Lọc fundamentals trước,
    sau đó mới tải kỹ thuật.
    """

    sem = asyncio.Semaphore(5)

    async def _financial_only(
        ticker,
    ):
        async with sem:

            try:
                return await asyncio.to_thread(
                    evaluate_ticker,
                    ticker,
                    None,
                    include_technical=False,
                )

            except Exception as exc:
                logger.warning(
                    "Lỗi lọc tài chính mã %s: %s",
                    ticker,
                    exc,
                )

                return None

    financial_tasks = [
        asyncio.create_task(
            _financial_only(ticker)
        )
        for ticker in tickers
    ]

    financial_results = []

    for index, task in enumerate(
        asyncio.as_completed(
            financial_tasks
        ),
        1,
    ):
        result = await task

        if result is not None:
            financial_results.append(
                result
            )

        if progress_cb:
            await progress_cb(
                index,
                len(tickers),
                "financial",
            )

    passed = [
        result["ticker"]
        for result in financial_results
        if result.get(
            "fundamental",
            {},
        ).get(
            "is_passed"
        )
    ]

    if not passed:
        return financial_results

    async def _technical(
        ticker,
    ):
        async with sem:

            try:
                df = await asyncio.to_thread(
                    fetch_stock_quote_history,
                    ticker,
                    700,
                )

                return await asyncio.to_thread(
                    evaluate_ticker,
                    ticker,
                    df,
                )

            except Exception as exc:
                logger.warning(
                    "Lỗi kỹ thuật mã %s: %s",
                    ticker,
                    exc,
                )

                return None

    technical_tasks = [
        asyncio.create_task(
            _technical(ticker)
        )
        for ticker in passed
    ]

    technical_results = []

    for index, task in enumerate(
        asyncio.as_completed(
            technical_tasks
        ),
        1,
    ):
        result = await task

        if result is not None:
            technical_results.append(
                result
            )

        if progress_cb:
            await progress_cb(
                index,
                len(passed),
                "technical",
            )

    return technical_results


async def do_industry(
    message: Message,
    industry_code: str,
):
    industry = get_industry_filter(
        industry_code
    )

    if industry is None:

        supported = ", ".join(
            item["code"]
            for item in list_industries()
        )

        await message.reply_html(
            f"⚠️ Mã ngành "
            f"<code>{industry_code}</code> "
            f"chưa được hỗ trợ.\n"
            f"Mã hợp lệ: "
            f"<code>{supported}</code>"
        )

        return

    if industry_code == "generic":

        await message.reply_html(
            "⚠️ <b>Ngành khác</b> chỉ là nhóm dự phòng "
            "cho mã chưa map ICB, không mở quét toàn bộ "
            "nhóm này. Hãy chọn một ngành cụ thể."
        )

        return

    tickers = fetch_tickers_by_industry(
        industry_code
    )

    if not tickers:

        await message.reply_html(
            f"⚠️ Chưa lấy được mã nào cho ngành "
            f"<b>{industry.display_name}</b>. "
            "Kiểm tra lại dữ liệu ICB hoặc thử lại sau."
        )

        return

    loading = await message.reply_html(
        f"⏳ Đang lọc tài chính ngành "
        f"<b>{industry.display_name}</b>: "
        f"0/{len(tickers)} mã..."
    )

    async def progress(
        done,
        total,
        phase,
    ):
        if (
            done % 5 == 0
            or done == total
        ):
            label = (
                "lọc tài chính"
                if phase == "financial"
                else "tải kỹ thuật"
            )

            await safe_edit_message(
                loading,
                f"⏳ Đang {label} ngành "
                f"<b>{industry.display_name}</b>: "
                f"{done}/{total} mã..."
            )

    results = await _scan_industry_async(
        tickers,
        progress,
    )

    candidates = [
        result
        for result in results
        if result.get(
            "fundamental",
            {},
        ).get(
            "is_passed"
        )
    ]

    candidates.sort(
        key=lambda result: (
            result.get(
                "fundamental",
                {},
            ).get("score")
            or 0
        ),
        reverse=True,
    )

    lines = [
        f"🏭 <b>KẾT QUẢ NGÀNH "
        f"{industry.display_name.upper()}</b>",
        f"Đã xử lý: "
        f"{len(results)}/{len(tickers)} mã",
        "",
    ]

    if not candidates:
        lines.append(
            "🟡 Chưa có mã đạt bộ lọc ngành."
        )

    for result in candidates:

        fin = result.get(
            "fundamental",
            {},
        )

        lines.append(
            f"✅ <b>{result['ticker']}</b> | "
            f"{fin.get('status')} | "
            f"Điểm ngành: "
            f"{fin.get('score', 'N/A')} | "
            f"Kỹ thuật: "
            f"{result.get('status')} | "
            f"<code>/check "
            f"{result['ticker']}</code>"
        )

    lines.append(
        "\n<i>Thiếu chỉ số được ghi "
        "INSUFFICIENT_DATA, không bị xem là FAIL.</i>"
    )

    await safe_edit_message(
        loading,
        "\n".join(lines),
        get_industry_keyboard(),
    )


# ==========================================
# SIGNALS
# ==========================================

async def do_signals(
    message: Message,
    application,
    page: int = 0,
    edit_target: Message = None,
):
    fresh = is_scan_fresh(
        application,
        max_age_minutes=SIGNALS_FRESHNESS_MINUTES,
    )

    if not fresh:

        loading_text = (
            "⏳ <i>Chưa có dữ liệu mới - đang quét "
            "toàn thị trường ngay bây giờ "
            "(đã xử lý 0 mã)...</i>"
        )

        if edit_target:

            await safe_edit_message(
                edit_target,
                loading_text,
            )

            target = edit_target

        else:

            target = await message.reply_html(
                loading_text
            )

        async def _progress(
            done,
            total,
        ):
            if (
                done % 5 == 0
                or done == total
            ):
                try:
                    await safe_edit_message(
                        target,
                        f"⏳ <i>Đang quét toàn thị trường - "
                        f"đã xử lý {done}/{total} mã...</i>",
                    )

                except Exception:
                    pass

        results, total_listed = (
            await _scan_market_async(
                progress_cb=_progress
            )
        )

        scan = save_scan_result(
            application,
            results,
            total_listed,
        )

        edit_target = target

    else:

        scan = get_latest_scan(
            application
        )

        results = scan.get(
            "results"
        )

    scanned_at = scan.get(
        "timestamp",
        "",
    )

    total_listed = scan.get(
        "total_listed",
        len(results),
    )

    meta_note = (
        f"{len(results)}/{total_listed} mã có dữ liệu | "
        f"Cập nhật: {scanned_at} UTC"
    )

    reply_text, markup = _render_results_page(
        results,
        page,
        SIGNALS_PAGE_SIZE,
        title_found=(
            "🎯 <b>DANH SÁCH CỔ PHIẾU "
            "ĐẠT TÍN HIỆU MUA</b>"
        ),
        title_empty=(
            "🟡 <b>Hiện thị trường chưa có mã nào "
            "vượt ngưỡng MUA.</b>"
        ),
        meta_note=meta_note,
        page_prefix="cmd_signals_p",
        suggest_vn30=True,
    )

    if edit_target:

        await safe_edit_message(
            edit_target,
            reply_text,
            markup,
        )

    else:

        msg = await message.reply_html(
            "🔎 <i>Đang tổng hợp kết quả...</i>"
        )

        await safe_edit_message(
            msg,
            reply_text,
            markup,
        )


# ==========================================
# VN30
# ==========================================

async def _scan_vn30_async(
    progress_cb=None,
):
    """
    Quét rổ VN30 song song.
    """

    tickers = fetch_vn30_tickers()

    sem = asyncio.Semaphore(5)

    async def _process(ticker):

        async with sem:

            try:

                df = await asyncio.to_thread(
                    fetch_stock_quote_history,
                    ticker,
                    450,
                )

                if (
                    df is not None
                    and not df.empty
                ):

                    return await asyncio.to_thread(
                        evaluate_ticker,
                        ticker,
                        df,
                    )

            except Exception as e:

                logger.warning(
                    "[VN30] Lỗi khi xử lý mã %s: %s",
                    ticker,
                    e,
                )

            return None

    tasks = [
        asyncio.create_task(
            _process(ticker)
        )
        for ticker in tickers
    ]

    results = []

    done_count = 0

    for task in asyncio.as_completed(tasks):

        result = await task

        done_count += 1

        if result is not None:
            results.append(result)

        if progress_cb:
            await progress_cb(
                done_count,
                len(tickers),
            )

    return (
        results,
        len(tickers),
    )


async def do_vn30(
    message: Message,
    page: int = 0,
    edit_target: Message = None,
):
    """
    Quét trực tiếp rổ VN30.
    """

    loading_text = (
        "⏳ <i>Đang quét nhanh rổ VN30 - "
        "đã xử lý 0 mã...</i>"
    )

    if edit_target:

        await safe_edit_message(
            edit_target,
            loading_text,
        )

        target = edit_target

    else:

        target = await message.reply_html(
            loading_text
        )

    async def _progress(
        done,
        total,
    ):
        if (
            done % 5 == 0
            or done == total
        ):

            try:

                await safe_edit_message(
                    target,
                    f"⏳ <i>Đang quét nhanh rổ VN30 - "
                    f"đã xử lý {done}/{total} mã...</i>",
                )

            except Exception:
                pass

    results, total = await _scan_vn30_async(
        progress_cb=_progress
    )

    if not results:

        await safe_edit_message(
            target,
            "⚠️ <i>Không lấy được dữ liệu "
            "cho rổ VN30. "
            "Vui lòng thử lại sau ít phút.</i>",
        )

        return

    meta_note = (
        f"Quét trực tiếp {len(results)}/{total} mã VN30 | "
        f"Vừa cập nhật"
    )

    reply_text, markup = _render_results_page(
        results,
        page,
        VN30_PAGE_SIZE,
        title_found=(
            "🎯 <b>TÍN HIỆU MUA "
            "TRONG RỔ VN30</b>"
        ),
        title_empty=(
            "🟡 <b>Rổ VN30 hiện chưa có mã nào "
            "đạt tín hiệu MUA.</b>"
        ),
        meta_note=meta_note,
        page_prefix="cmd_vn30_p",
    )

    await safe_edit_message(
        target,
        reply_text,
        markup,
    )


# ==========================================
# FILTER STATS
# ==========================================

async def do_filterstats(
    message: Message,
    application,
):
    scan = get_latest_scan(
        application
    )

    results = (
        scan.get("results")
        if scan
        else None
    )

    if not results:

        await message.reply_html(
            "⏳ <i>Chưa có dữ liệu quét toàn thị trường "
            "để thống kê.</i>"
        )

        return

    total = len(results)

    status_counts = {}

    reason_counts = {
        "ROE": 0,
        "Nợ/VCSH": 0,
        "Tăng trưởng DT": 0,
        "Tăng trưởng LNST": 0,
        "CFO": 0,
    }

    for result in results:

        fin = result.get(
            "fundamental",
            {},
        ) or {}

        status = fin.get(
            "status",
            "UNKNOWN",
        )

        status_counts[status] = (
            status_counts.get(
                status,
                0,
            ) + 1
        )

        reason = fin.get(
            "reason"
        ) or ""

        for key in reason_counts:

            if key in reason:
                reason_counts[key] += 1

    text = (
        "📊 <b>THỐNG KÊ BỘ LỌC BCTC</b>\n"
        f"<i>Tổng số mã có dữ liệu: {total}</i>\n\n"
        "<b>Theo trạng thái:</b>\n"
    )

    for status, count in sorted(
        status_counts.items(),
        key=lambda x: -x[1],
    ):

        pct = (
            count / total * 100
            if total
            else 0
        )

        text += (
            f"• <code>{status}</code>: "
            f"{count} mã ({pct:.1f}%)\n"
        )

    text += (
        "\n<b>Bị loại vì từng tiêu chí cụ thể</b> "
        "<i>(1 mã có thể trượt nhiều tiêu chí cùng lúc):</i>\n"
    )

    for name, count in reason_counts.items():

        text += (
            f"• {name}: {count} mã\n"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ]
    ]

    await message.reply_html(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ==========================================
# CHECK MÃ
# ==========================================

async def do_check(
    message: Message,
    ticker: str,
):
    ticker = ticker.upper().strip()

    msg = await message.reply_html(
        f"⏳ <i>Đang phân tích dữ liệu "
        f"cho mã {ticker}...</i>"
    )

    df = fetch_stock_quote_history(
        ticker,
        days=450,
    )

    res = evaluate_ticker(
        ticker,
        df,
    )

    pos_info = None

    if (
        res.get("technical")
        and res["technical"].get("close")
        and res["technical"].get("atr14")
    ):

        pos_info = calculate_position_size(
            entry_price=res["technical"]["close"],
            atr0=res["technical"]["atr14"],
            nav=DEFAULT_NAV,
            cash_available=DEFAULT_NAV,
        )

    reply_text = format_check_result(
        res,
        pos_info,
    )

    action_row = [
        InlineKeyboardButton(
            f"🔔 Nhận Alert {ticker}",
            callback_data=f"cmd_alert_{ticker}",
        ),
        InlineKeyboardButton(
            "📊 Backtest",
            callback_data="cmd_backtest",
        ),
    ]

    keyboard = [
        action_row
    ]

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ]
    )

    await safe_edit_message(
        msg,
        reply_text,
        InlineKeyboardMarkup(keyboard),
    )

    try:

        chart_buf = build_price_chart(
            df,
            ticker,
        )

        await message.reply_photo(
            photo=chart_buf,
            caption=(
                f"📈 Biểu đồ giá & chỉ báo "
                f"kỹ thuật - {ticker}"
            ),
        )

    except Exception as e:

        logger.warning(
            f"Không thể tạo biểu đồ cho "
            f"{ticker}: {e}"
        )


# ==========================================
# ALERT
# ==========================================

async def do_alert(
    message: Message,
    user_id: int,
    ticker: str = None,
):
    if not ticker:

        alerts = get_user_alerts(
            user_id
        )

        if alerts:

            alert_str = ", ".join(
                alerts
            )

            await message.reply_html(
                f"🔔 <b>Các mã bạn đang đăng ký "
                f"nhận cảnh báo:</b> "
                f"<code>{alert_str}</code>\n\n"
                f"Để thêm mã mới, gõ: "
                f"<code>/alert &lt;MÃ&gt;</code> "
                f"(Ví dụ: <code>/alert HPG</code>)"
            )

        else:

            await message.reply_html(
                "ℹ️ Bạn chưa đăng ký cảnh báo mã nào.\n"
                "Gõ: <code>/alert &lt;MÃ&gt;</code> "
                "để đăng ký "
                "(Ví dụ: <code>/alert HPG</code>)"
            )

        return

    ticker = ticker.upper().strip()

    add_user_alert(
        user_id,
        ticker,
    )

    await message.reply_html(
        f"✅ <b>Đã đăng ký nhận cảnh báo "
        f"cho mã {ticker}!</b>\n"
        f"Hệ thống sẽ tự động quét và gửi tin nhắn "
        f"cho bạn khi có tín hiệu."
    )


# ==========================================
# PORTFOLIO
# ==========================================

async def do_portfolio(
    message: Message,
):
    msg = (
        "💼 <b>QUẢN TRỊ DANH MỤC & VỐN ĐẦU TƯ</b>\n\n"
        f"💰 <b>Vốn NAV giả định:</b> "
        f"<code>{DEFAULT_NAV:,.0f} VNĐ</code>\n"
        f"🛡 <b>Quy tắc rủi ro:</b> "
        f"Tối đa 0.5% NAV/lệnh "
        f"(~{DEFAULT_NAV * 0.005:,.0f} VNĐ)\n"
        f"📊 <b>Phân bổ tối đa:</b> "
        f"20% NAV/mã | Tối đa 5 mã\n"
        f"📉 <b>Thoát lệnh:</b> "
        f"Cắt lỗ Stop0 = Entry - 2*ATR, "
        f"Chốt lời Target0 = Entry + 3*ATR\n\n"
        "💡 Dùng <code>/backtest</code> "
        "để kiểm định chiến lược."
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Backtest chiến lược",
                callback_data="cmd_backtest",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ],
    ]

    await message.reply_html(
        msg,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ==========================================
# BACKTEST - MENU
# ==========================================

async def do_backtest_menu(
    message: Message,
):
    """
    Menu chọn phạm vi backtest.

    1. 5 mã tiêu biểu
    2. VN30
    3. Mã riêng
    """

    text = (
        "📊 <b>BACKTEST CHIẾN LƯỢC</b>\n\n"
        "Chọn phạm vi muốn kiểm định:\n\n"

        "🧪 <b>5 mã tiêu biểu</b>\n"
        "HPG • FPT • VNM • MWG • REE\n\n"

        "📈 <b>VN30</b>\n"
        "Kiểm định toàn bộ rổ VN30 hiện tại.\n\n"

        "🔎 <b>Mã riêng</b>\n"
        "Ví dụ:\n"
        "<code>/backtest SSI</code>\n"
        "<code>/backtest HPG FPT MWG</code>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🧪 5 mã tiêu biểu",
                callback_data="cmd_backtest_sample",
            )
        ],
        [
            InlineKeyboardButton(
                "📈 Backtest VN30",
                callback_data="cmd_backtest_vn30",
            )
        ],
        [
            InlineKeyboardButton(
                "🔎 Backtest mã riêng",
                callback_data="cmd_backtest_custom",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ],
    ]

    await message.reply_html(
        text,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ==========================================
# BACKTEST - CHẠY
# ==========================================

async def do_backtest(
    message: Message,
    tickers=None,
    universe_name="5 mã tiêu biểu",
    lookback_days=BACKTEST_LOOKBACK_DAYS,
):
    """
    Chạy backtest theo danh sách ticker.

    tickers=None:
        dùng 5 mã mặc định.

    Ví dụ:
        ["HPG", "FPT"]
        ["SSI"]
        danh sách VN30
    """

    if tickers is None:

        tickers = (
            DEFAULT_BACKTEST_TICKERS.copy()
        )

    # Chuẩn hóa ticker
    tickers = [
        str(ticker).upper().strip()
        for ticker in tickers
        if str(ticker).strip()
    ]

    # Loại mã trùng
    tickers = list(
        dict.fromkeys(tickers)
    )

    if not tickers:

        await message.reply_html(
            "⚠️ Không có mã cổ phiếu nào "
            "để chạy backtest."
        )

        return

    ticker_count = len(tickers)

    msg = await message.reply_html(
        "⏳ <i>Đang chạy Backtest...</i>\n\n"
        f"📌 Phạm vi: <b>{universe_name}</b>\n"
        f"📊 Số mã: <b>{ticker_count}</b>\n"
        f"⏱ Thời gian: "
        f"<b>{lookback_days} phiên</b>\n\n"
        "Có thể mất một lúc nếu chạy nhiều mã."
    )

    try:

        report = await asyncio.to_thread(
            run_portfolio_backtest,
            tickers=tickers,
            lookback_days=lookback_days,
            universe_name=universe_name,
        )

        reply_text = format_backtest_message(
            report
        )

    except Exception as exc:

        logger.exception(
            "Lỗi backtest"
        )

        reply_text = (
            "⚠️ <b>Không thể chạy Backtest.</b>\n\n"
            f"<code>{str(exc)}</code>"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "🧪 5 mã",
                callback_data="cmd_backtest_sample",
            ),
            InlineKeyboardButton(
                "📈 VN30",
                callback_data="cmd_backtest_vn30",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔎 Mã riêng",
                callback_data="cmd_backtest_custom",
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ],
    ]

    await safe_edit_message(
        msg,
        reply_text,
        InlineKeyboardMarkup(keyboard),
    )


# ==========================================
# COMMAND HANDLERS
# ==========================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_start(
        update.message
    )


async def signals_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_signals(
        update.message,
        context.application,
    )


async def industries_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_industries(
        update.message
    )


async def industry_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:

        await do_industries(
            update.message
        )

        return

    await do_industry(
        update.message,
        context.args[0].lower().strip(),
    )


async def vn30_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_vn30(
        update.message
    )


async def filterstats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_filterstats(
        update.message,
        context.application,
    )


async def check_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:

        await update.message.reply_html(
            "⚠️ <b>Vui lòng nhập mã cổ phiếu "
            "cần tra cứu.</b>\n"
            "Ví dụ: <code>/check HPG</code> "
            "hoặc <code>/check FPT</code>"
        )

        return

    await do_check(
        update.message,
        context.args[0],
    )


async def alert_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    ticker = (
        context.args[0]
        if context.args
        else None
    )

    await do_alert(
        update.message,
        user_id,
        ticker,
    )


async def portfolio_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await do_portfolio(
        update.message
    )


# ==========================================
# BACKTEST COMMAND
# ==========================================

async def backtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Cú pháp:

    /backtest
        -> mở menu

    /backtest sample
        -> 5 mã tiêu biểu

    /backtest vn30
        -> toàn bộ VN30

    /backtest SSI
        -> chỉ SSI

    /backtest HPG FPT MWG
        -> nhiều mã riêng
    """

    args = [
        arg.upper().strip()
        for arg in context.args
        if arg.strip()
    ]

    # --------------------------------------
    # /backtest
    # --------------------------------------

    if not args:

        await do_backtest_menu(
            update.message
        )

        return

    # --------------------------------------
    # /backtest sample
    # --------------------------------------

    if (
        len(args) == 1
        and args[0] in {
            "SAMPLE",
            "5MA",
        }
    ):

        await do_backtest(
            update.message,
            tickers=(
                DEFAULT_BACKTEST_TICKERS.copy()
            ),
            universe_name="5 mã tiêu biểu",
        )

        return

    # --------------------------------------
    # /backtest vn30
    # --------------------------------------

    if (
        len(args) == 1
        and args[0] == "VN30"
    ):

        loading = await update.message.reply_html(
            "⏳ <i>Đang lấy danh sách VN30...</i>"
        )

        try:

            tickers = await asyncio.to_thread(
                fetch_vn30_tickers
            )

            if not tickers:

                await safe_edit_message(
                    loading,
                    "⚠️ Không lấy được danh sách VN30.",
                )

                return

            await safe_edit_message(
                loading,
                f"⏳ <i>Đã lấy {len(tickers)} mã VN30. "
                f"Đang bắt đầu backtest...</i>",
            )

            await do_backtest(
                update.message,
                tickers=tickers,
                universe_name="VN30",
            )

        except Exception as exc:

            logger.exception(
                "Lỗi lấy danh sách VN30 cho backtest"
            )

            await safe_edit_message(
                loading,
                "⚠️ <b>Lỗi backtest VN30:</b>\n"
                f"<code>{str(exc)}</code>",
            )

        return

    # --------------------------------------
    # /backtest HPG
    # /backtest HPG FPT MWG
    # --------------------------------------

    invalid = [
        ticker
        for ticker in args
        if not re.fullmatch(
            r"[A-Z]{2,5}",
            ticker,
        )
    ]

    if invalid:

        await update.message.reply_html(
            "⚠️ <b>Cú pháp không hợp lệ.</b>\n\n"
            "Ví dụ:\n"
            "<code>/backtest SSI</code>\n"
            "<code>/backtest HPG FPT MWG</code>\n"
            "<code>/backtest VN30</code>\n"
            "<code>/backtest sample</code>"
        )

        return

    # Đây là phần QUAN TRỌNG:
    # truyền đúng args vào do_backtest

    await do_backtest(
        update.message,
        tickers=args,
        universe_name=(
            "Mã riêng: "
            + ", ".join(args)
        ),
    )


# ==========================================
# CALLBACK QUERY
# ==========================================

async def button_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Xử lý các nút Inline Keyboard.
    """

    query = update.callback_query

    try:
        await query.answer()

    except Exception:
        pass

    data = query.data
    message = query.message
    user_id = query.from_user.id

    # --------------------------------------
    # MENU CHÍNH
    # --------------------------------------

    if data == "cmd_start":

        await do_start(
            message
        )

    # --------------------------------------
    # NGÀNH
    # --------------------------------------

    elif data == "cmd_industries":

        await do_industries(
            message
        )

    elif data.startswith(
        "cmd_industry_"
    ):

        await do_industry(
            message,
            data.replace(
                "cmd_industry_",
                "",
                1,
            ),
        )

    # --------------------------------------
    # SIGNALS
    # --------------------------------------

    elif data == "cmd_signals":

        await do_signals(
            message,
            context.application,
        )

    elif data.startswith(
        "cmd_signals_p"
    ):

        page = int(
            data.replace(
                "cmd_signals_p",
                "",
            )
        )

        await do_signals(
            message,
            context.application,
            page=page,
            edit_target=message,
        )

    # --------------------------------------
    # VN30
    # --------------------------------------

    elif data == "cmd_vn30":

        await do_vn30(
            message
        )

    elif data.startswith(
        "cmd_vn30_p"
    ):

        page = int(
            data.replace(
                "cmd_vn30_p",
                "",
            )
        )

        await do_vn30(
            message,
            page=page,
            edit_target=message,
        )

    # --------------------------------------
    # FILTER STATS
    # --------------------------------------

    elif data == "cmd_filterstats":

        await do_filterstats(
            message,
            context.application,
        )

    # --------------------------------------
    # CHECK
    # --------------------------------------

    elif data.startswith(
        "cmd_check_"
    ):

        ticker = data.replace(
            "cmd_check_",
            "",
        )

        await do_check(
            message,
            ticker,
        )

    # --------------------------------------
    # ALERT
    # --------------------------------------

    elif data.startswith(
        "cmd_alert_"
    ):

        ticker = data.replace(
            "cmd_alert_",
            "",
        )

        await do_alert(
            message,
            user_id,
            ticker,
        )

    # --------------------------------------
    # PORTFOLIO
    # --------------------------------------

    elif data == "cmd_portfolio":

        await do_portfolio(
            message
        )

    # ======================================
    # BACKTEST
    # ======================================

    elif data == "cmd_backtest":

        await do_backtest_menu(
            message
        )

    # --------------------------------------
    # BACKTEST SAMPLE
    # --------------------------------------

    elif data == "cmd_backtest_sample":

        await do_backtest(
            message,
            tickers=(
                DEFAULT_BACKTEST_TICKERS.copy()
            ),
            universe_name="5 mã tiêu biểu",
        )

    # --------------------------------------
    # BACKTEST VN30
    # --------------------------------------

    elif data == "cmd_backtest_vn30":

        loading = await message.reply_html(
            "⏳ <i>Đang lấy danh sách VN30...</i>"
        )

        try:

            tickers = await asyncio.to_thread(
                fetch_vn30_tickers
            )

            if not tickers:

                await safe_edit_message(
                    loading,
                    "⚠️ Không lấy được danh sách VN30.",
                )

                return

            await safe_edit_message(
                loading,
                f"⏳ <i>Đã lấy {len(tickers)} mã VN30. "
                f"Đang chạy backtest...</i>",
            )

            await do_backtest(
                message,
                tickers=tickers,
                universe_name="VN30",
            )

        except Exception as exc:

            logger.exception(
                "Lỗi backtest VN30"
            )

            await safe_edit_message(
                loading,
                "⚠️ <b>Lỗi backtest VN30:</b>\n"
                f"<code>{str(exc)}</code>",
            )

    # --------------------------------------
    # BACKTEST CUSTOM
    # --------------------------------------

    elif data == "cmd_backtest_custom":

        await safe_edit_message(
            message,
            "🔎 <b>BACKTEST MÃ RIÊNG</b>\n\n"
            "Hãy nhập lệnh:\n\n"
            "<code>/backtest SSI</code>\n\n"
            "Hoặc nhiều mã:\n"
            "<code>/backtest HPG FPT MWG</code>",
        )

    # --------------------------------------
    # ALERT LIST
    # --------------------------------------

    elif data == "cmd_my_alerts":

        await do_alert(
            message,
            user_id,
            None,
        )


# ==========================================
# ERROR HANDLER
# ==========================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Bắt mọi ngoại lệ.
    """

    logger.error(
        "Exception while handling an update:",
        exc_info=context.error,
    )

    if (
        isinstance(update, Update)
        and update.effective_message
    ):

        try:

            await update.effective_message.reply_text(
                f"⚠️ Có sự cố định dạng "
                f"hoặc dữ liệu: {context.error}"
            )

        except Exception:
            pass


# ==========================================
# BUILD APPLICATION
# ==========================================

def build_application():
    """
    Khởi tạo Telegram Application.
    """

    if (
        not TELEGRAM_BOT_TOKEN
        or TELEGRAM_BOT_TOKEN
        == "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    ):

        logger.warning(
            "Chưa cấu hình TELEGRAM_BOT_TOKEN "
            "trong config.py!"
        )

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = (
        ApplicationBuilder()
        .token(
            TELEGRAM_BOT_TOKEN
        )
        .request(
            request
        )
        .concurrent_updates(
            True
        )
        .build()
    )

    # ======================================
    # COMMANDS
    # ======================================

    app.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "signals",
            signals_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "industries",
            industries_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "industry",
            industry_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "vn30",
            vn30_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "filterstats",
            filterstats_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "check",
            check_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "alert",
            alert_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "portfolio",
            portfolio_command,
        )
    )

    # BACKTEST
    app.add_handler(
        CommandHandler(
            "backtest",
            backtest_command,
        )
    )

    # ======================================
    # CALLBACK
    # ======================================

    app.add_handler(
        CallbackQueryHandler(
            button_callback_handler
        )
    )

    # ======================================
    # ERROR HANDLER
    # ======================================

    app.add_error_handler(
        error_handler
    )

    return app