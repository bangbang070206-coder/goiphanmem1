from typing import List, Dict, Any
from backtesting.backtest_engine import run_backtest_single_stock
from data_pipeline.fetcher import fetch_stock_quote_history, fetch_stock_financials
from core_logic.fundamental_filter import check_fundamental_criteria
from config import DEFAULT_WATCHLIST

def run_portfolio_backtest(tickers: List[str] = None, lookback_days: int = 150) -> Dict[str, Any]:
    """
    Chạy backtest trên rổ cổ phiếu và tổng hợp chỉ số hiệu suất.
    Theo Mục 8 của Chiến lược số 1: Kiểm định kỹ thuật trên dữ liệu giá lịch sử
    để đo lường đóng góp của các chỉ báo và hệ thống điểm TA_Score.
    """
    if tickers is None:
        tickers = ["HPG", "FPT", "VNM", "MWG", "REE"]
        
    all_trades = []
    stock_summaries = {}
    
    for t in tickers:
        df = fetch_stock_quote_history(t, days=lookback_days + 300)
        res = run_backtest_single_stock(
            ticker=t, 
            df=df, 
            lookback_days=lookback_days,
            is_fundamental_passed=True
        )
        
        stock_summaries[t] = res["summary"]
        all_trades.extend(res["trades"])
        
    total_trades = len(all_trades)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_return": 0,
            "profit_factor": 0,
            "stocks": stock_summaries
        }
        
    returns = [t['return_pct'] for t in all_trades]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.001
    profit_factor = gross_profit / gross_loss
    win_rate = (len(wins) / total_trades) * 100
    avg_return = sum(returns) / total_trades
    
    return {
        "lookback_days": lookback_days,
        "total_stocks": len(tickers),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "avg_return_per_trade": round(avg_return, 2),
        "profit_factor": round(profit_factor, 2),
        "gross_profit": round(gross_profit, 1),
        "gross_loss": round(gross_loss, 1),
        "stocks": stock_summaries
    }

def format_backtest_message(report: Dict[str, Any]) -> str:
    """Format kết quả backtest thành tin nhắn Telegram đẹp mắt"""
    msg = (
        "📊 <b>KẾT QUẢ KIỂM ĐỊNH CHIẾN LƯỢC (BACKTESTING)</b>\n"
        f"⏱ <i>Thời gian kiểm thử: {report.get('lookback_days', 120)} phiên gần nhất (~6 tháng)</i>\n\n"
        f"🔹 <b>Tổng số giao dịch:</b> <code>{report.get('total_trades', 0)}</code> lệnh\n"
        f"🎯 <b>Tỷ lệ thắng (Win Rate):</b> <b>{report.get('win_rate', 0)}%</b>\n"
        f"📈 <b>Tỷ suất sinh lời TB/lệnh:</b> <b>{report.get('avg_return_per_trade', 0):+.2f}%</b>\n"
        f"⚖️ <b>Hệ số Lợi nhuận/Rủi ro (Profit Factor):</b> <code>{report.get('profit_factor', 0)}</code>\n\n"
        "<b>Chi tiết theo từng mã tiêu biểu:</b>\n"
    )
    for ticker, s in report.get('stocks', {}).items():
        if s.get('total_trades', 0) > 0:
            msg += f"• <b>{ticker}:</b> {s['total_trades']} lệnh | Thắng {s['win_rate']}% | LN: {s['total_return']:+.1f}%\n"
        else:
            msg += f"• <b>{ticker}:</b> Chưa xuất hiện điểm mua thỏa mãn\n"
            
    msg += (
        "\n<i>💡 Lưu ý: Kết quả mô phỏng theo quy tắc mua tại giá mở cửa phiên t+1, "
        "cắt lỗ tại Stoploss ATR và chốt lời tại Target 3xATR.</i>"
    )
    return msg
