import os
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent

# ==========================================
# 1. CẤU HÌNH TELEGRAM BOT
# ==========================================
# Điền Token của bạn từ @BotFather vào đây hoặc đặt qua biến môi trường
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8625630959:AAFtPdDgvP-_JO33VP6VSEpiudHUTKOvfsI")

# ==========================================
# 2. CẤU HÌNH DATABASE
# ==========================================
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "fintech_bot.sqlite"

# ==========================================
# 3. DANH MỤC CỔ PHIẾU THEO DÕI BAN ĐẦU
# Phạm vi: Cổ phiếu phi tài chính trên sàn HOSE có thanh khoản tốt
# (Loại trừ ngân hàng, chứng khoán, bảo hiểm theo mục 2 của chiến lược)
# ==========================================
DEFAULT_WATCHLIST = [
    "HPG", "VNM", "FPT", "MWG", "DGC", 
    "REE", "MSN", "PNJ", "GMD", "KDH", 
    "VHC", "KBC", "HSG", "NKG", "VRE",
    "POW", "SBT", "DCM", "DPM", "PC1"
]

# ==========================================
# 4. TIÊU CHÍ BỘ LỌC CƠ BẢN (BCTC TTM)
# Theo Mục 2 của Chiến lược số 1
# ==========================================
MIN_AVG_VALUE_20D = 10_000_000_000  # Thanh khoản bình quân 20 phiên >= 10 tỷ VNĐ
ROE_MIN = 0.15                      # ROE TTM >= 15%
MAX_DEBT_TO_EQUITY = 1.5            # Tổng nợ phải trả / Tổng VCSH <= 1.5
REVENUE_GROWTH_MIN = 0.0            # Doanh thu TTM tăng trưởng > 0%
NET_PROFIT_GROWTH_MIN = 0.0         # LNST công ty mẹ TTM tăng trưởng > 0%
CFO_MIN = 0.0                       # Dòng tiền thuần từ HĐKD TTM > 0
MAX_STALE_DAYS = 180                # Nếu BCTC cũ hơn 180 ngày => DATA_STALE

# ==========================================
# 5. TIÊU CHÍ CHẤM ĐIỂM KỸ THUẬT (TA SCORING)
# Theo Mục 3, 4, 5 của Chiến lược số 1
# ==========================================
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
PERCENTILE_WINDOW = 252             # So sánh với 252 phiên lịch sử liền trước
TA_SCORE_BUY_THRESHOLD = 75         # TA_Score >= 75 mới đủ điều kiện BUY_CANDIDATE

# Trọng số 3 nhóm điểm (Mục 4: 3 nhóm có trọng số bằng nhau 1/3)
WEIGHT_TREND = 1.0 / 3.0
WEIGHT_MOMENTUM = 1.0 / 3.0
WEIGHT_VOLUME = 1.0 / 3.0

# ==========================================
# 6. QUẢN TRỊ RỦI RO & ĐỊNH CỠ VỊ THẾ
# Theo Mục 6 của Chiến lược số 1
# ==========================================
DEFAULT_NAV = 100_000_000           # Vốn giả định mặc định: 100 triệu VNĐ
RISK_PER_TRADE_PCT = 0.005          # Rủi ro 0.5% NAV cho mỗi giao dịch
MAX_PORTFOLIO_STOCKS = 5            # Tối đa 5 mã trong danh mục
MAX_STOCK_WEIGHT_PCT = 0.20         # Tối đa 20% NAV cho 1 mã
MAX_SECTOR_WEIGHT_PCT = 0.30        # Tối đa 30% NAV cho 1 ngành
LOT_SIZE = 100                      # Lô giao dịch tối thiểu HOSE là 100 cổ phiếu

# Tỷ lệ Stoploss & Target theo ATR
STOP_ATR_MULTIPLE = 2.0             # Stop0 = Entry - 2 * ATR
TARGET_ATR_MULTIPLE = 3.0           # Target0 = Entry + 3 * ATR
CHASE_BUY_MAX_ATR = 0.5             # Nếu giá mở cửa > Close + 0.5*ATR thì bỏ lệnh

# ==========================================
# 7. QUÉT ĐỊNH KỲ TOÀN THỊ TRƯỜNG (Background Scanner)
# ==========================================
SIGNALS_SCAN_INTERVAL_MINUTES = 30  # Khoảng cách giữa 2 lần quét định kỳ toàn thị trường
SIGNALS_SCAN_DELAY_SECONDS = 0.3    # Nghỉ giữa mỗi mã trong lúc quét, tránh dồn dập gọi API
