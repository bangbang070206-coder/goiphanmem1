import os
from pathlib import Path
from dotenv import load_dotenv

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ==========================================
# 1. CẤU HÌNH TELEGRAM BOT
# ==========================================
# Token phải được cung cấp qua biến môi trường; không để giá trị thật trong mã nguồn.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

STRATEGY_VERSION = "3.0.0-student-mvp"
MARKET_EXCHANGES = ["HOSE"]

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
MIN_AVG_VALUE_20D = 150_000_000  # Thanh khoản bình quân 20 phiên >= 150 triệu VNĐ
ROE_MIN = 0.08                      # ROE TTM >= 15%
MAX_DEBT_TO_EQUITY = 3.0            # Tổng nợ phải trả / Tổng VCSH <= 1.5
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
TA_SCORE_BUY_THRESHOLD = 55         # TA_Score >= 55 mới đủ điều kiện BUY_CANDIDATE

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

# Tỷ lệ Stoploss & Target theo ATR (đúng theo Mục 6 tài liệu Chiến lược số 1)
STOP_ATR_MULTIPLE = 2.0             # Stop0 = Entry - 2.0 * ATR
TARGET_ATR_MULTIPLE = 3.0           # Target0 = Entry + 3.0 * ATR
CHASE_BUY_MAX_ATR = 0.5             # Nếu giá mở cửa > Close + 0.5*ATR thì bỏ lệnh

# ==========================================
# 7. LOẠI TRỪ NHÓM NGÀNH TÀI CHÍNH (theo Mục 2 của Chiến lược số 1)
# ==========================================
# Ngân hàng/Chứng khoán/Bảo hiểm có cấu trúc vốn đặc thù (vd: "nợ" của ngân hàng
# gồm cả tiền gửi khách hàng) khiến chỉ số Nợ/VCSH <= 1.5 không phản ánh đúng sức
# khỏe thật - luôn "trượt" một cách máy móc dù công ty có thể rất tốt. Danh sách
# này liệt kê thủ công các mã thuộc 3 nhóm ngành trên (không đầy đủ 100% nhưng phủ
# các mã lớn/thường gặp trên HOSE) để loại khỏi bộ lọc BCTC, thay vì chấm sai.
# ==========================================
# 7. ĐỊNH TUYẾN NGÀNH & PROFILE LỌC CƠ BẢN (Mục 6, Chiến lược v2)
# ==========================================
# v2 thay "danh sách loại toàn bộ tổ chức tài chính" (v1) bằng ĐỊNH TUYẾN NGÀNH:
# mỗi mã được gán 1 profile (NON_FINANCIAL / BANK / SECURITIES / INSURANCE_LIFE /
# INSURANCE_NONLIFE); mỗi profile có bộ tiêu chí riêng thay vì bị loại thẳng.
#
# MINH BẠCH VỀ NGUỒN: bản đồ dưới đây là DANH SÁCH THỦ CÔNG do nhóm tự biên soạn
# (không phải lấy tự động từ API mã ngành đã xác minh như v2 Mục 6 yêu cầu lý
# tưởng: "Dùng nguồn ngành có mã ngành, tên, phiên bản và thời điểm áp dụng").
# Đây là phương án tạm thời, có thời hạn, cần thay bằng nguồn ngành chính thức
# (vd: vnstock Listing kèm industry code) khi có điều kiện xác minh.
SECTOR_MAP_VERSION = "manual-v1-2026-09-22"

SECTOR_MAP: dict = {
    # Ngân hàng
    "VCB": "BANK", "BID": "BANK", "CTG": "BANK", "TCB": "BANK", "MBB": "BANK",
    "ACB": "BANK", "VPB": "BANK", "STB": "BANK", "HDB": "BANK", "VIB": "BANK",
    "TPB": "BANK", "SHB": "BANK", "EIB": "BANK", "LPB": "BANK", "OCB": "BANK",
    "MSB": "BANK", "SSB": "BANK", "ABB": "BANK", "BVB": "BANK", "NAB": "BANK",
    "SGB": "BANK", "KLB": "BANK", "VBB": "BANK", "PGB": "BANK",
    # Chứng khoán
    "SSI": "SECURITIES", "VND": "SECURITIES", "VCI": "SECURITIES", "HCM": "SECURITIES",
    "MBS": "SECURITIES", "VIX": "SECURITIES", "FTS": "SECURITIES", "BSI": "SECURITIES",
    "CTS": "SECURITIES", "AGR": "SECURITIES", "ORS": "SECURITIES", "VDS": "SECURITIES",
    # Bảo hiểm nhân thọ (hiện chưa có mã bảo hiểm nhân thọ thuần niêm yết độc lập
    # trên HOSE mà nhóm xác minh được - để trống, bổ sung khi có nguồn xác nhận)
    # Bảo hiểm phi nhân thọ
    "BVH": "INSURANCE_NONLIFE", "BMI": "INSURANCE_NONLIFE", "PVI": "INSURANCE_NONLIFE",
    "PGI": "INSURANCE_NONLIFE", "MIG": "INSURANCE_NONLIFE", "BIC": "INSURANCE_NONLIFE",
}
# Mã không có trong bản đồ mặc định là NON_FINANCIAL.

# Ngưỡng riêng cho từng profile (Mục 6, bảng "Điều kiện riêng ban đầu" của v2).
# LƯU Ý: BANK/SECURITIES/INSURANCE_* cần dữ liệu chuyên ngành (nợ xấu, CAR, vốn
# khả dụng, khả năng thanh toán) mà vnstock công cộng CHƯA xác nhận có cung cấp.
# Cho tới khi xác minh được nguồn, các profile này trả NOT_EVALUATED thay vì
# chấm điểm bằng số liệu chưa kiểm chứng hoặc mặc định bằng 0 (v2 Mục 7).
SECTOR_PROFILE_THRESHOLDS = {
    "NON_FINANCIAL": {
        "roe_min": 0.15,
        "np_growth_min": 0.0,
        "rev_growth_min": 0.0,
        "max_debt_to_equity": 1.5,
        "cfo_min": 0.0,
    },
    "BANK": {
        "roe_min": 0.10,
        "np_growth_min": 0.0,
        # NPL <= 3%, capital coverage >= 1.10: CẦN NGUỒN CHUYÊN NGÀNH CHƯA XÁC MINH
    },
    "SECURITIES": {
        "roe_min": 0.10,
        "np_growth_min": 0.0,
        # capital adequacy coverage >= 1.10: CẦN NGUỒN CHUYÊN NGÀNH CHƯA XÁC MINH
    },
    "INSURANCE_LIFE": {
        "roe_min": 0.08,
        "np_growth_min": 0.0,
        # solvency coverage >= 1.10: CẦN NGUỒN CHUYÊN NGÀNH CHƯA XÁC MINH
    },
    "INSURANCE_NONLIFE": {
        "roe_min": 0.08,
        "np_growth_min": 0.0,
        # solvency coverage >= 1.10: CẦN NGUỒN CHUYÊN NGÀNH CHƯA XÁC MINH
    },
}

# ==========================================
# 8. QUÉT ĐỊNH KỲ TOÀN THỊ TRƯỜNG (Background Scanner)
# ==========================================
SIGNALS_SCAN_INTERVAL_MINUTES = 30  # Khoảng cách giữa 2 lần quét định kỳ toàn thị trường
SIGNALS_SCAN_DELAY_SECONDS = 0      # (không dùng nữa - xem VNSTOCK_MIN_INTERVAL_SECONDS bên dưới)

# ==========================================
# 9. GIỚI HẠN TỐC ĐỘ GỌI API VNSTOCK (Rate Limiting)
# ==========================================
# Gói Khách (Guest, chưa đăng ký) của vnstock giới hạn 20 request/phút -> tối
# thiểu ~3.0s giữa 2 request để không bị "Rate limit exceeded".
# Sau khi chạy register_user() để lấy API key miễn phí (gói Community, 60
# request/phút), có thể giảm xuống còn ~1.05s.
VNSTOCK_MIN_INTERVAL_SECONDS = 3.2
API_CALL_TIMEOUT_SECONDS = 15       # Timeout cứng cho mỗi lệnh gọi vnstock - tránh treo vô thời hạn

TECHNICAL_BUY_THRESHOLD = 20
GENERAL_FUNDAMENTAL_MIN_SCORE = 20
