import os
import sys
import logging
import argparse

# Thiết lập encoding UTF-8 chuẩn trên Windows
sys.stdout.reconfigure(encoding='utf-8')
os.environ['VNSTOCK_TELEMETRY'] = 'off'

from config import TELEGRAM_BOT_TOKEN, DEFAULT_WATCHLIST
from database.db_manager import init_db
from bot.telegram_bot import build_application
from core_logic.strategy import evaluate_ticker
from data_pipeline.fetcher import fetch_stock_quote_history
from backtesting.performance_report import run_portfolio_backtest, format_backtest_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger("FintechBot")

def run_cli_test():
    """Chế độ Test nhanh qua giao diện dòng lệnh (không cần Telegram Bot Token)"""
    print("\n" + "="*60)
    print("🚀 CHẠY THỬ NGHIỆM ĐỊNH LƯỢNG FINTECH BOT (CLI TEST)")
    print("="*60)
    
    test_tickers = ["HPG", "FPT", "VNM"]
    for ticker in test_tickers:
        print(f"\n[1] Đang nạp dữ liệu và đánh giá mã: {ticker}...")
        df = fetch_stock_quote_history(ticker, days=450)
        res = evaluate_ticker(ticker, df)
        
        print(f"-> Trạng thái: {res['status']} | Tín hiệu: {res['signal']}")
        fin = res['fundamental']
        print(f"-> Lọc BCTC ({'ĐẠT' if fin.get('is_passed') else 'TRƯỢT'}): {fin.get('reason')}")
        sc = res['scoring']
        if sc.get('status') == 'SUCCESS':
            print(f"-> Chấm điểm Quant 252 phiên: TA_Score = {sc['ta_score']}/100 "
                  f"(Xu hướng: {sc['trend_score']} | Động lượng: {sc['momentum_score']} | Giá&Vol: {sc['volume_score']})")
        else:
            print(f"-> Chấm điểm: {sc.get('reason')}")
            
    print("\n[2] Đang chạy kiểm thử Backtesting 6 tháng gần nhất...")
    report = run_portfolio_backtest(tickers=["HPG", "FPT", "MWG"], lookback_days=120)
    print(format_backtest_message(report))
    print("\n" + "="*60)
    print("✅ HOÀN TẤT KIỂM THỬ CLI THÀNH CÔNG!")
    print("="*60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Fintech Telegram Bot Runner")
    parser.add_argument("--test", action="store_true", help="Chạy kiểm thử logic tại Terminal mà không cần bật Telegram")
    args = parser.parse_args()

    # Khởi tạo DB SQLite
    init_db()

    if args.test:
        run_cli_test()
        return

    # Kiểm tra Token Telegram
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "!"*65)
        print("⚠️  CHƯA CÓ TELEGRAM BOT TOKEN!")
        print("!"*65)
        print("1. Hãy mở Telegram, tìm @BotFather và gõ /newbot để lấy Token.")
        print("2. Mở file 'config.py' và thay thế chuỗi 'YOUR_TELEGRAM_BOT_TOKEN_HERE'")
        print("   bằng mã Token của bạn.")
        print("3. Sau đó chạy lại: py main.py\n")
        print("💡 Hoặc nếu bạn muốn kiểm tra thử thuật toán ngay tại màn hình này, gõ:")
        print("   py main.py --test\n" + "!"*65 + "\n")
        return

    print("🤖 Đang khởi động Fintech Telegram Bot...")
    app = build_application()
    print("✅ Bot đã sẵn sàng nhận tin nhắn! Nhấn Ctrl+C để dừng.")
    app.run_polling(bootstrap_retries=10, timeout=30)

if __name__ == "__main__":
    main()
