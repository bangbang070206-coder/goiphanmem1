from typing import List, Dict, Any

from backtesting.backtest_engine import run_backtest_single_stock
from data_pipeline.fetcher import fetch_stock_quote_history
from config import PERCENTILE_WINDOW


DEFAULT_BACKTEST_TICKERS = [
    "HPG",
    "FPT",
    "VNM",
    "MWG",
    "REE",
]


def run_portfolio_backtest(
    tickers: List[str] = None,
    lookback_days: int = 150,
    universe_name: str = None,
) -> Dict[str, Any]:

    if tickers is None:
        tickers = DEFAULT_BACKTEST_TICKERS.copy()

    # Chuẩn hóa và bỏ mã trùng
    tickers = list(
        dict.fromkeys(
            str(t).upper().strip()
            for t in tickers
            if str(t).strip()
        )
    )

    all_trades = []
    stock_summaries = {}

    required_sessions = PERCENTILE_WINDOW + 50 + lookback_days
    fetch_days = int(required_sessions * 1.6)

    for ticker in tickers:
        try:
            df = fetch_stock_quote_history(
                ticker,
                days=fetch_days,
            )

            if df is None or df.empty:
                stock_summaries[ticker] = {
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_return": 0,
                    "error": "Không có dữ liệu giá",
                }
                continue

            result = run_backtest_single_stock(
                ticker=ticker,
                df=df,
                lookback_days=lookback_days,
                is_fundamental_passed=True,
            )

            summary = result.get(
                "summary",
                {
                    "total_trades": 0,
                    "win_rate": 0,
                    "total_return": 0,
                },
            )

            stock_summaries[ticker] = summary
            all_trades.extend(result.get("trades", []))

        except Exception as exc:
            stock_summaries[ticker] = {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "error": str(exc),
            }

    total_trades = len(all_trades)

    if total_trades == 0:
        return {
            "lookback_days": lookback_days,
            "total_stocks": len(tickers),
            "total_trades": 0,
            "win_rate": 0,
            "avg_return_per_trade": 0,
            "profit_factor": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "stocks": stock_summaries,
            "tickers": tickers,
            "universe_name": (
                universe_name
                or f"{len(tickers)} mã"
            ),
        }

    returns = [
        float(trade["return_pct"])
        for trade in all_trades
    ]

    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0
    )

    win_rate = (
        len(wins) / total_trades
    ) * 100

    avg_return = (
        sum(returns) / total_trades
    )

    return {
        "lookback_days": lookback_days,
        "total_stocks": len(tickers),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "avg_return_per_trade": round(avg_return, 2),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "stocks": stock_summaries,
        "tickers": tickers,
        "universe_name": (
            universe_name
            or f"{len(tickers)} mã"
        ),
    }


def format_backtest_message(
    report: Dict[str, Any],
) -> str:

    universe_name = report.get(
        "universe_name",
        "5 mã tiêu biểu",
    )

    total_stocks = report.get(
        "total_stocks",
        len(report.get("stocks", {})),
    )

    msg = (
        "📊 <b>KẾT QUẢ KIỂM ĐỊNH CHIẾN LƯỢC</b>\n\n"
        f"📌 <b>Phạm vi:</b> {universe_name}\n"
        f"🧾 <b>Số mã:</b> {total_stocks}\n"
        f"⏱ <b>Thời gian:</b> "
        f"{report.get('lookback_days', 120)} phiên gần nhất\n\n"
        f"🔹 <b>Tổng số giao dịch:</b> "
        f"{report.get('total_trades', 0)} lệnh\n"
        f"🎯 <b>Win Rate:</b> "
        f"{report.get('win_rate', 0)}%\n"
        f"📈 <b>Lợi nhuận TB/lệnh:</b> "
        f"{report.get('avg_return_per_trade', 0):+.2f}%\n"
        f"⚖️ <b>Profit Factor:</b> "
        f"{report.get('profit_factor', 0)}\n\n"
        "<b>Chi tiết:</b>\n"
    )

    for ticker, summary in report.get(
        "stocks",
        {},
    ).items():

        error = summary.get("error")

        if error:
            msg += (
                f"• <b>{ticker}:</b> ⚠️ "
                f"{error}\n"
            )
            continue

        total_trades = summary.get(
            "total_trades",
            0,
        )

        if total_trades > 0:
            msg += (
                f"• <b>{ticker}:</b> "
                f"{total_trades} lệnh | "
                f"Thắng {summary.get('win_rate', 0)}% | "
                f"LN: "
                f"{summary.get('total_return', 0):+.1f}%\n"
            )
        else:
            msg += (
                f"• <b>{ticker}:</b> "
                "Chưa xuất hiện điểm mua thỏa mãn\n"
            )

    msg += (
        "\n<i>💡 Kết quả mô phỏng theo quy tắc "
        "mua tại giá mở cửa phiên t+1, "
        "cắt lỗ tại Stoploss ATR và "
        "chốt lời tại Target 3xATR.</i>"
    )

    return msg