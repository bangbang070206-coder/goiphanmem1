import re
import logging
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    BotCommand,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from telegram.request import HTTPXRequest

from config import (
    TELEGRAM_BOT_TOKEN,
    DEFAULT_NAV,
)

from data_pipeline.fetcher import (
    fetch_stock_quote_history,
    fetch_vn30_tickers,
    fetch_tickers_by_industry,
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
)

from database.db_manager import (
    add_user_alert,
    get_user_alerts,
)

from bot.ui_helpers import (
    get_main_menu_keyboard,
    get_check_menu_keyboard,
    get_industry_keyboard,
    format_welcome_message,
    format_check_result,
)

from bot.chart_helpers import build_price_chart

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Mở menu chính"),
        BotCommand("check", "Phân tích cổ phiếu"),
        BotCommand("vn30", "Quét VN30"),
        BotCommand("vn100", "Quét VN100"),
        BotCommand("industry", "Lọc theo ngành"),
        BotCommand("industries", "Danh sách ngành"),
        BotCommand("portfolio", "Quản trị vốn"),
        BotCommand("alert", "Cảnh báo giá"),
        BotCommand("backtest", "Backtest chiến lược"),
    ]

    await application.bot.set_my_commands(commands)
# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# CẤU HÌNH
# ============================================================

VN30_PAGE_SIZE = 10
VN100_PAGE_SIZE = 10

VNSTOCK_GROUP_CACHE_TTL_HOURS = 12


# ============================================================
# CACHE VN100
# ============================================================

_VN100_CACHE = {
    "data": None,
    "fetched_at": None,
}


# ============================================================
# HÀM TIỆN ÍCH
# ============================================================

async def safe_edit_message(
    msg: Message,
    text: str,
    reply_markup=None,
):
    """
    Gửi tin nhắn HTML an toàn.

    Nếu Telegram không chấp nhận HTML:
    fallback về text thường.
    """

    try:

        await msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    except Exception as e:

        logger.warning(
            "Lỗi gửi HTML (%s), fallback về văn bản thường...",
            e,
        )

        plain_text = re.sub(
            r"<[^>]+>",
            "",
            text,
        )

        try:

            await msg.edit_text(
                plain_text,
                reply_markup=reply_markup,
            )

        except Exception:
            pass


# ============================================================
# VN100
# ============================================================

def fetch_vn100_tickers() -> list:
    """
    Lấy danh sách VN100 trực tiếp từ vnstock Listing.

    VN100:
        Listing(source='VCI').symbols_by_group(group='VN100')

    Cache 12 giờ.
    """

    from datetime import datetime
    from data_pipeline.rate_limiter import throttle

    now = datetime.now()

    cached = _VN100_CACHE.get("data")
    fetched_at = _VN100_CACHE.get("fetched_at")

    if cached is not None and fetched_at is not None:

        age_hours = (
            now - fetched_at
        ).total_seconds() / 3600

        if age_hours < VNSTOCK_GROUP_CACHE_TTL_HOURS:
            return cached

    try:

        from vnstock import Listing

        listing = Listing(
            source="VCI"
        )

        throttle()

        result = listing.symbols_by_group(
            group="VN100"
        )

        if hasattr(result, "tolist"):

            tickers = [
                str(t).upper().strip()
                for t in result.tolist()
            ]

        else:

            tickers = [
                str(t).upper().strip()
                for t in result
            ]

        tickers = list(
            dict.fromkeys(
                t
                for t in tickers
                if t
            )
        )

        if not tickers:

            raise ValueError(
                "Danh sách VN100 trả về rỗng."
            )

        _VN100_CACHE["data"] = tickers
        _VN100_CACHE["fetched_at"] = now

        logger.info(
            "Đã tải %s mã VN100 từ vnstock Listing API.",
            len(tickers),
        )

        return tickers

    except (
        Exception,
        SystemExit,
        BaseException,
    ) as e:

        logger.warning(
            "Lỗi khi lấy VN100 từ vnstock: %s",
            e,
        )

        return []


# ============================================================
# START / MENU
# ============================================================

async def do_start(
    message: Message,
):

    text = format_welcome_message()

    await message.reply_html(
        text,
        reply_markup=get_main_menu_keyboard(),
    )


# ============================================================
# CHECK MENU
# ============================================================

async def do_check_menu(
    message: Message,
):

    text = (
        "🔎 <b>KIỂM TRA MỘT MÃ CỔ PHIẾU</b>\n\n"
        "Nhập mã cổ phiếu bạn muốn phân tích.\n\n"
        "Ví dụ:\n"
        "• <code>/check HPG</code>\n"
        "• <code>/check FPT</code>\n"
        "• <code>/check VNM</code>\n\n"
        "Bot sẽ kiểm tra:\n"
        "📋 BCTC &amp; nền tảng cơ bản\n"
        "📈 Xu hướng &amp; động lượng\n"
        "📊 Thanh khoản\n"
        "🛡 Quản trị rủi ro\n\n"
        "<i>Hoặc chọn một rổ cổ phiếu bên dưới.</i>"
    )

    await message.reply_html(
        text,
        reply_markup=get_check_menu_keyboard(),
    )


# ============================================================
# INDUSTRY
# ============================================================

async def do_industries(
    message: Message,
):

    text = (
        "🏭 <b>PHÂN TÍCH THEO NGÀNH</b>\n\n"
        "Chọn một ngành để hệ thống:\n"
        "• Lấy danh sách mã thuộc ngành\n"
        "• Áp dụng bộ tiêu chí riêng\n"
        "• Lọc BCTC trước\n"
        "• Sau đó kiểm tra kỹ thuật\n\n"
        "Bạn cũng có thể dùng:\n"
        "<code>/industry banking</code>"
    )

    await message.reply_html(
        text,
        reply_markup=get_industry_keyboard(),
    )


async def _scan_industry_async(
    tickers,
    progress_cb=None,
):
    """
    Giai đoạn 1:
        lọc BCTC trước.

    Giai đoạn 2:
        chỉ mã đạt BCTC mới tải dữ liệu kỹ thuật.
    """

    sem = asyncio.Semaphore(10)

    # ========================================================
    # PHASE 1 - FUNDAMENTAL
    # ========================================================

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
                    use_industry_filter=True,
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
            financial_results.append(result)

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
        ).get("is_passed")
    ]

    if not passed:
        return financial_results

    # ========================================================
    # PHASE 2 - TECHNICAL
    # ========================================================

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

                if df is None or df.empty:
                    return None

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
            technical_results.append(result)

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
            f"chưa được hỗ trợ.\n\n"
            f"Mã hợp lệ:\n"
            f"<code>{supported}</code>"
        )

        return

    if industry_code == "generic":

        await message.reply_html(
            "⚠️ <b>Ngành khác</b> chỉ là nhóm dự phòng "
            "cho mã chưa map ICB.\n\n"
            "Hãy chọn một ngành cụ thể."
        )

        return

    tickers = fetch_tickers_by_industry(
        industry_code
    )

    if not tickers:

        await message.reply_html(
            f"⚠️ Chưa lấy được mã nào cho ngành "
            f"<b>{industry.display_name}</b>.\n\n"
            "Kiểm tra lại dữ liệu ICB hoặc thử lại sau."
        )

        return

    loading = await message.reply_html(
        f"⏳ Đang lọc ngành "
        f"<b>{industry.display_name}</b>\n\n"
        f"📋 BCTC: 0/{len(tickers)} mã"
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

            if phase == "financial":
                label = "📋 BCTC"
            else:
                label = "📈 Kỹ thuật"

            await safe_edit_message(
                loading,
                f"⏳ Đang phân tích "
                f"<b>{industry.display_name}</b>\n\n"
                f"{label}: {done}/{total} mã",
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
        ).get("is_passed")
    ]

    candidates.sort(
        key=lambda result:
            result.get(
                "fundamental",
                {},
            ).get("score") or 0,
        reverse=True,
    )

    lines = [
        f"🏭 <b>NGÀNH "
        f"{industry.display_name.upper()}</b>",
        "",
        f"📋 Đã xử lý: "
        f"{len(results)}/{len(tickers)} mã",
        f"✅ Đạt BCTC: "
        f"{len(candidates)} mã",
        "",
    ]

    if not candidates:

        lines.append(
            "🟡 Chưa có mã đạt bộ lọc ngành."
        )

    else:

        for result in candidates:

            fin = result.get(
                "fundamental",
                {},
            )

            lines.append(
                f"✅ <b>{result['ticker']}</b>\n"
                f"   • Điểm ngành: "
                f"<b>{fin.get('score', 'N/A')}</b>\n"
                f"   • Kỹ thuật: "
                f"<b>{result.get('status', 'N/A')}</b>\n"
                f"   • <code>/check "
                f"{result['ticker']}</code>"
            )

    lines.append(
        "\n<i>INSUFFICIENT_DATA không được "
        "xem là FAIL.</i>"
    )

    await safe_edit_message(
        loading,
        "\n".join(lines),
        get_industry_keyboard(),
    )


# ============================================================
# RENDER VN30 / VN100
# ============================================================

def _render_results_page(
    results: list,
    page: int,
    page_size: int,
    title_found: str,
    title_empty: str,
    meta_note: str,
    page_prefix: str,
    market_buttons: bool = True,
):
    """
    Dùng chung cho VN30 và VN100.
    """

    buy_candidates = [
        r
        for r in results
        if r.get("status")
        == "BUY_CANDIDATE"
    ]

    buy_candidates.sort(
        key=lambda x:
            x.get(
                "scoring",
                {},
            ).get("ta_score", 0)
            or 0,
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
        (
            total_items
            + page_size
            - 1
        )
        // page_size,
    )

    page = max(
        0,
        min(
            page,
            total_pages - 1,
        ),
    )

    start = page * page_size

    page_items = source_list[
        start:start + page_size
    ]

    reply_text = (
        header
        + f"<i>Trang "
        f"{page + 1}/{total_pages}</i>\n\n"
    )

    for i, candidate in enumerate(
        page_items,
        start + 1,
    ):

        score = candidate.get(
            "scoring",
            {},
        ).get(
            "ta_score",
            "N/A",
        )

        close = candidate.get(
            "technical",
            {},
        ).get(
            "close",
            "N/A",
        )

        fin_passed = candidate.get(
            "fundamental",
            {},
        ).get(
            "is_passed"
        )

        fin_status = (
            "✅ BCTC đạt"
            if fin_passed
            else "❌ BCTC chưa đạt"
        )

        reply_text += (
            f"{i}. <b>{candidate['ticker']}</b>\n"
            f"   💰 Giá: {close} | "
            f"⭐ TA: <b>{score}/100</b>\n"
            f"   {fin_status}\n\n"
        )

    reply_text += (
        "<i>BUY = BCTC đạt + thanh khoản đạt "
        "+ tổng điểm đạt ngưỡng "
        "+ có tín hiệu kỹ thuật xác nhận.</i>"
    )

    keyboard = []

    # ========================================================
    # PAGINATION
    # ========================================================

    nav_row = []

    if page > 0:

        nav_row.append(
            InlineKeyboardButton(
                "◀️ Trước",
                callback_data=(
                    f"{page_prefix}"
                    f"{page - 1}"
                ),
            )
        )

    if page < total_pages - 1:

        nav_row.append(
            InlineKeyboardButton(
                "Sau ▶️",
                callback_data=(
                    f"{page_prefix}"
                    f"{page + 1}"
                ),
            )
        )

    if nav_row:
        keyboard.append(nav_row)

    # ========================================================
    # CHECK TỪNG MÃ
    # ========================================================

    for candidate in page_items:

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔎 Kiểm tra {candidate['ticker']}",
                    callback_data=(
                        f"cmd_check_"
                        f"{candidate['ticker']}"
                    ),
                )
            ]
        )

    # ========================================================
    # CHUYỂN VN30 / VN100
    # ========================================================

    if market_buttons:

        keyboard.append(
            [
                InlineKeyboardButton(
                    "📊 VN30",
                    callback_data="cmd_vn30",
                ),
                InlineKeyboardButton(
                    "📈 VN100",
                    callback_data="cmd_vn100",
                ),
            ]
        )

    keyboard.append(
        [
            InlineKeyboardButton(
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ]
    )

    return (
        reply_text,
        InlineKeyboardMarkup(keyboard),
    )


# ============================================================
# SCAN GENERIC INDEX
# ============================================================

async def _scan_index_async(
    tickers,
    index_name,
    progress_cb=None,
):
    """
    Scan VN30 / VN100.

    Không dùng industry filter.
    """

    if not tickers:
        return [], 0

    sem = asyncio.Semaphore(10)

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

                if df is None or df.empty:
                    return None

                return await asyncio.to_thread(
                    evaluate_ticker,
                    ticker,
                    df,
                    use_industry_filter=False,
                )

            except Exception as exc:

                logger.warning(
                    "[%s] Lỗi khi xử lý %s: %s",
                    index_name,
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

    done_count = 0

    for task in asyncio.as_completed(
        tasks
    ):

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


# ============================================================
# VN30
# ============================================================

async def do_vn30(
    message: Message,
    page: int = 0,
    edit_target: Message = None,
):

    loading_text = (
        "⏳ <i>Đang quét "
        "<b>VN30</b>...\n\n"
        "📊 Đã xử lý: 0 mã</i>"
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

        if done % 5 == 0 or done == total:

            try:

                await safe_edit_message(
                    target,
                    f"⏳ <i>Đang quét "
                    f"<b>VN30</b>...\n\n"
                    f"📊 Đã xử lý: "
                    f"{done}/{total} mã</i>",
                )

            except Exception:
                pass

    tickers = fetch_vn30_tickers()

    if not tickers:

        await safe_edit_message(
            target,
            "⚠️ <b>Không lấy được danh sách VN30.</b>\n\n"
            "Vui lòng thử lại sau ít phút.",
            get_main_menu_keyboard(),
        )

        return

    results, total = await _scan_index_async(
        tickers,
        "VN30",
        progress_cb=_progress,
    )

    if not results:

        await safe_edit_message(
            target,
            "⚠️ <i>Không lấy được dữ liệu "
            "cho rổ VN30.</i>",
            get_main_menu_keyboard(),
        )

        return

    buy_count = sum(
        1
        for result in results
        if result.get("status")
        == "BUY_CANDIDATE"
    )

    meta_note = (
        f"Quét trực tiếp "
        f"{len(results)}/{total} mã VN30 | "
        f"BUY: {buy_count} | "
        f"Vừa cập nhật"
    )

    reply_text, markup = _render_results_page(
        results,
        page,
        VN30_PAGE_SIZE,
        title_found=(
            "🎯 <b>TÍN HIỆU MUA TRONG RỔ VN30</b>"
        ),
        title_empty=(
            "🟡 <b>VN30 hiện chưa có "
            "mã đạt tín hiệu MUA.</b>"
        ),
        meta_note=meta_note,
        page_prefix="cmd_vn30_p",
    )

    await safe_edit_message(
        target,
        reply_text,
        markup,
    )


# ============================================================
# VN100
# ============================================================

async def do_vn100(
    message: Message,
    page: int = 0,
    edit_target: Message = None,
):

    loading_text = (
        "⏳ <i>Đang quét "
        "<b>VN100</b>...\n\n"
        "📊 Đã xử lý: 0 mã</i>"
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

        if done % 10 == 0 or done == total:

            try:

                await safe_edit_message(
                    target,
                    f"⏳ <i>Đang quét "
                    f"<b>VN100</b>...\n\n"
                    f"📊 Đã xử lý: "
                    f"{done}/{total} mã</i>",
                )

            except Exception:
                pass

    tickers = fetch_vn100_tickers()

    if not tickers:

        await safe_edit_message(
            target,
            "⚠️ <b>Không lấy được danh sách VN100.</b>\n\n"
            "Kiểm tra phiên bản vnstock hoặc thử lại sau.",
            get_main_menu_keyboard(),
        )

        return

    results, total = await _scan_index_async(
        tickers,
        "VN100",
        progress_cb=_progress,
    )

    if not results:

        await safe_edit_message(
            target,
            "⚠️ <i>Không lấy được dữ liệu "
            "cho rổ VN100.</i>\n\n"
            "Vui lòng thử lại sau ít phút.",
            get_main_menu_keyboard(),
        )

        return

    buy_count = sum(
        1
        for result in results
        if result.get("status")
        == "BUY_CANDIDATE"
    )

    meta_note = (
        f"Quét trực tiếp "
        f"{len(results)}/{total} mã VN100 | "
        f"BUY: {buy_count} | "
        f"Vừa cập nhật"
    )

    reply_text, markup = _render_results_page(
        results,
        page,
        VN100_PAGE_SIZE,
        title_found=(
            "🎯 <b>TÍN HIỆU MUA TRONG RỔ VN100</b>"
        ),
        title_empty=(
            "🟡 <b>VN100 hiện chưa có "
            "mã đạt tín hiệu MUA.</b>"
        ),
        meta_note=meta_note,
        page_prefix="cmd_vn100_p",
    )

    await safe_edit_message(
        target,
        reply_text,
        markup,
    )


# ============================================================
# CHECK 1 MÃ
# ============================================================

async def do_check(
    message: Message,
    ticker: str,
):

    ticker = ticker.upper().strip()

    msg = await message.reply_html(
        f"⏳ <i>Đang phân tích "
        f"<b>{ticker}</b>...</i>\n\n"
        "📋 BCTC + 📈 kỹ thuật + 🛡 rủi ro"
    )

    try:

        df = await asyncio.to_thread(
            fetch_stock_quote_history,
            ticker,
            450,
        )

        if df is None or df.empty:

            await safe_edit_message(
                msg,
                f"⚠️ Không lấy được dữ liệu "
                f"cho mã <b>{ticker}</b>.",
                get_main_menu_keyboard(),
            )

            return

        res = await asyncio.to_thread(
            evaluate_ticker,
            ticker,
            df,
        )

    except Exception as exc:

        logger.exception(
            "Lỗi khi check %s",
            ticker,
        )

        await safe_edit_message(
            msg,
            f"⚠️ Không thể phân tích "
            f"<b>{ticker}</b> lúc này.\n\n"
            f"<code>{exc}</code>",
            get_main_menu_keyboard(),
        )

        return

    # ========================================================
    # POSITION SIZING
    # ========================================================

    pos_info = None

    technical = (
        res.get("technical")
        or {}
    )

    if (
        technical.get("close")
        and technical.get("atr14")
    ):

        try:

            pos_info = calculate_position_size(
                entry_price=technical["close"],
                atr0=technical["atr14"],
                nav=DEFAULT_NAV,
                cash_available=DEFAULT_NAV,
            )

        except Exception as exc:

            logger.warning(
                "Không tính được position size %s: %s",
                ticker,
                exc,
            )

    # ========================================================
    # RESULT
    # ========================================================

    reply_text = format_check_result(
        res,
        pos_info,
    )

    # ========================================================
    # BUTTONS
    # ========================================================

    keyboard = [
        [
            InlineKeyboardButton(
                f"🔔 Nhận Alert {ticker}",
                callback_data=f"cmd_alert_{ticker}",
            )
        ],
        [
            InlineKeyboardButton(
                "📊 VN30",
                callback_data="cmd_vn30",
            ),
            InlineKeyboardButton(
                "📈 VN100",
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
            )
        ],
    ]

    await safe_edit_message(
        msg,
        reply_text,
        InlineKeyboardMarkup(keyboard),
    )

    # ========================================================
    # CHART
    # ========================================================

    try:

        chart_buf = build_price_chart(
            df,
            ticker,
        )

        await message.reply_photo(
            photo=chart_buf,
            caption=(
                f"📈 Biểu đồ giá & "
                f"chỉ báo kỹ thuật - {ticker}"
            ),
        )

    except Exception as e:

        logger.warning(
            "Không thể tạo biểu đồ cho %s: %s",
            ticker,
            e,
        )


# ============================================================
# ALERT
# ============================================================

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
                "🔔 <b>DANH SÁCH CẢNH BÁO</b>\n\n"
                f"📌 Mã đang theo dõi:\n"
                f"<code>{alert_str}</code>\n\n"
                "Để thêm mã:\n"
                "<code>/alert &lt;MÃ&gt;</code>\n\n"
                "Ví dụ:\n"
                "<code>/alert HPG</code>",
                reply_markup=get_main_menu_keyboard(),
            )

        else:

            await message.reply_html(
                "🔔 <b>CẢNH BÁO</b>\n\n"
                "Bạn chưa đăng ký mã nào.\n\n"
                "Để thêm mã:\n"
                "<code>/alert &lt;MÃ&gt;</code>\n\n"
                "Ví dụ:\n"
                "<code>/alert HPG</code>",
                reply_markup=get_main_menu_keyboard(),
            )

        return

    ticker = ticker.upper().strip()

    add_user_alert(
        user_id,
        ticker,
    )

    await message.reply_html(
        f"✅ <b>Đã đăng ký cảnh báo {ticker}</b>\n\n"
        "Bot sẽ theo dõi tín hiệu theo "
        "ngưỡng đã cấu hình.",
        reply_markup=get_main_menu_keyboard(),
    )


# ============================================================
# PORTFOLIO
# ============================================================

async def do_portfolio(
    message: Message,
):

    msg = (
        "💼 <b>QUẢN TRỊ DANH MỤC & VỐN</b>\n\n"

        f"💰 <b>NAV giả định:</b> "
        f"<code>{DEFAULT_NAV:,.0f} VNĐ</code>\n"

        "🛡 <b>Rủi ro/lệnh:</b> "
        "Tối đa 0.5% NAV\n"

        "📊 <b>Phân bổ:</b> "
        "Tối đa 20% NAV/mã\n"

        "📦 <b>Số mã tối đa:</b> "
        "5 mã\n"

        "📉 <b>Stop Loss:</b> "
        "Entry - 2×ATR\n"

        "🎯 <b>Target:</b> "
        "Entry + 3×ATR\n\n"

        "<i>Chọn rổ cổ phiếu để tìm tín hiệu:</i>"
    )

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


# ============================================================
# BACKTEST
# ============================================================

async def do_backtest(
    message: Message,
):

    msg = await message.reply_html(
        "⏳ <i>Đang chạy Backtest...</i>\n\n"
        "📊 Kiểm thử chiến lược trên dữ liệu lịch sử.\n"
        "Có thể mất khoảng 20-30 giây."
    )

    try:

        report = await asyncio.to_thread(
            run_portfolio_backtest,
            lookback_days=120,
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
            f"<code>{exc}</code>"
        )

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
                "🔙 Menu Chính",
                callback_data="cmd_start",
            )
        ],
    ]

    await safe_edit_message(
        msg,
        reply_text,
        InlineKeyboardMarkup(
            keyboard
        ),
    )


# ============================================================
# COMMAND HANDLERS
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await do_start(
        update.message
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


async def vn100_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await do_vn100(
        update.message
    )


async def check_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not context.args:

        await update.message.reply_html(
            "🔎 <b>KIỂM TRA CỔ PHIẾU</b>\n\n"
            "Vui lòng nhập mã cổ phiếu.\n\n"
            "Ví dụ:\n"
            "<code>/check HPG</code>\n"
            "<code>/check FPT</code>\n"
            "<code>/check VNM</code>",
            reply_markup=get_check_menu_keyboard(),
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


async def backtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await do_backtest(
        update.message
    )


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def button_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data

    message = query.message

    user_id = query.from_user.id

    # ========================================================
    # START
    # ========================================================

    if data == "cmd_start":

        await do_start(
            message
        )

    # ========================================================
    # CHECK MENU
    # ========================================================

    elif data == "cmd_check_menu":

        await do_check_menu(
            message
        )

    # ========================================================
    # INDUSTRIES
    # ========================================================

    elif data == "cmd_industries":

        await do_industries(
            message
        )

    elif data.startswith(
        "cmd_industry_"
    ):

        industry_code = data.replace(
            "cmd_industry_",
            "",
            1,
        )

        await do_industry(
            message,
            industry_code,
        )

    # ========================================================
    # VN30
    # ========================================================

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
                1,
            )
        )

        await do_vn30(
            message,
            page=page,
            edit_target=message,
        )

    # ========================================================
    # VN100
    # ========================================================

    elif data == "cmd_vn100":

        await do_vn100(
            message
        )

    elif data.startswith(
        "cmd_vn100_p"
    ):

        page = int(
            data.replace(
                "cmd_vn100_p",
                "",
                1,
            )
        )

        await do_vn100(
            message,
            page=page,
            edit_target=message,
        )

    # ========================================================
    # CHECK
    # ========================================================

    elif data.startswith(
        "cmd_check_"
    ):

        ticker = data.replace(
            "cmd_check_",
            "",
            1,
        )

        await do_check(
            message,
            ticker,
        )

    # ========================================================
    # ALERT
    # ========================================================

    elif data == "cmd_my_alerts":

        await do_alert(
            message,
            user_id,
        )

    elif data.startswith(
        "cmd_alert_"
    ):

        ticker = data.replace(
            "cmd_alert_",
            "",
            1,
        )

        await do_alert(
            message,
            user_id,
            ticker,
        )

    # ========================================================
    # PORTFOLIO
    # ========================================================

    elif data == "cmd_portfolio":

        await do_portfolio(
            message
        )

    # ========================================================
    # BACKTEST
    # ========================================================

    elif data == "cmd_backtest":

        await do_backtest(
            message
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

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
                "⚠️ Có sự cố khi xử lý yêu cầu:\n"
                f"{context.error}"
            )

        except Exception:
            pass


# ============================================================
# BUILD APPLICATION
# ============================================================

def build_application():

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
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .concurrent_updates(True)
        .post_init(set_bot_commands)
        .build()
    )

    # ========================================================
    # COMMANDS
    # ========================================================

    app.add_handler(
        CommandHandler(
            "start",
            start_command,
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
            "vn100",
            vn100_command,
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

    app.add_handler(
        CommandHandler(
            "backtest",
            backtest_command,
        )
    )

    # ========================================================
    # CALLBACK
    # ========================================================

    app.add_handler(
        CallbackQueryHandler(
            button_callback_handler
        )
    )

    # ========================================================
    # ERROR
    # ========================================================

    app.add_error_handler(
        error_handler
    )

    # ========================================================
    # MVP SCOPE
    #
    # GIỮ:
    # /vn30
    # /vn100
    # /check
    # /industry
    # /portfolio
    # /alert
    # /backtest
    #
    # KHÔNG ĐƯA /signals VÀ /filterstats VÀO MENU.
    # ========================================================

    return app