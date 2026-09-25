# HỆ THỐNG TELEGRAM BOT TÍN HIỆU ĐẦU TƯ CHỨNG KHOÁN (FINTECH BOT)

Dự án xây dựng hệ thống **Fintech Telegram Bot** tự động cung cấp tín hiệu Mua/Bán (Buy/Sell) trên thị trường chứng khoán Việt Nam, kết hợp **Phân tích Cơ bản (Fundamental Analysis)** và **Chấm điểm Kỹ thuật Đa lớp (Technical Quant Scoring)** dựa trên phân phối xác suất 252 phiên.

---

## 1. Sơ đồ Kiến trúc Hệ thống (System Architecture)

```
[ Nguồn Dữ Liệu ]
(vnstock / CafeF Scraper / SSI FastConnect)
       │
       ▼
[ Tầng Chống Chặn IP & Bộ đệm ]
• Rotating User-Agents & Exponential Backoff (anti_blocking.py)
• SQLite Local Cache (db_manager.py) - Giảm 90% số request
       │
       ▼
[ Core Logic Engine ]
├── 1. Bộ lọc BCTC TTM (fundamental_filter.py): ROE >= 15%, Nợ/VCSH <= 1.5, CFO > 0, Tăng trưởng TTM
├── 2. Chỉ báo Kỹ thuật (indicators.py): EMA20, EMA50, ATR14, RSI14, VR, CP
└── 3. Chấm điểm Quant 252 phiên (scoring.py): Xếp hạng phân vị lịch sử tự thân (Percentile Rank)
       │
       ▼
[ Quản trị Rủi ro & Định cỡ Vị thế (risk_management) ]
• Rủi ro tối đa 0.5% NAV/giao dịch: Qty = min(0.5% NAV / 2*ATR, 20% NAV / Price)
• Trailing Stop (2*ATR) & Target chốt lời (3*ATR)
       │
       ▼
[ Giao diện Telegram Bot (bot) ]
• Lệnh tương tác: /signals, /check <MÃ>, /alert, /portfolio, /backtest
• Bàn phím nút bấm thông minh (Inline Keyboards)
```

---

## 2. Điểm Mới & Sáng Tạo của Hệ Thống

1. **Chuẩn hóa Phân vị Tự thân 252 phiên (Percentile Ranking)**:
   - Không áp đặt ngưỡng cứng nhắc (RSI > 70 hay Volume > 1.5x) chung cho mọi mã. Bot so sánh xung lực của cổ phiếu với phân phối xác suất của chính mã đó trong 1 năm giao dịch gần nhất ($N = 252$ phiên).
   - Công thức: $Score = \frac{n_{nhỏ\_hơn} + 0.5 \times n_{bằng}}{N} \times 100$.
2. **Kiểm tra Chất lượng Dòng tiền Kinh doanh ($CFO_{TTM} > 0$)**:
   - Khác với mô hình thông thường chỉ nhìn vào $P/E$ hay $ROE$ dễ bị xào nấu kế toán, bot bổ sung bộ lọc dòng tiền thuần từ HĐKD ($CFO > 0$), giúp loại bỏ các công ty có doanh thu/lợi nhuận ảo nhưng bị đọng công nợ.
3. **Quản trị Rủi ro & Định cỡ Vị thế Tự động**:
   - Bot tính toán cụ thể số lượng cổ phiếu an toàn người dùng nên mua theo vốn NAV và khoảng dừng lỗ biến động ($2 \times ATR_{14}$), tuân thủ nghiêm ngặt kỷ luật quản trị vốn của các quỹ đầu cơ chuyên nghiệp.
4. **Kiến trúc Dữ liệu Đa tầng chống Chặn IP**:
   - SQLite Cache tự động lưu trữ dữ liệu nến và BCTC.
   - Throttling nghỉ ngẫu nhiên $0.8s - 1.8s$, xoay vòng User-Agent trình duyệt thật, chống lỗi HTTP 429/403 từ CafeF.

---

## 3. Hướng Dẫn Cài Đặt & Sử Dụng Từng Bước

### Bước 1: Chuẩn bị Môi trường Python
Cài đặt các gói thư viện cần thiết:
```bash
py -m pip install python-telegram-bot vnstock3 pandas numpy requests
```

### Bước 2: Đăng ký Telegram Bot Token
1. Mở ứng dụng Telegram, tìm kiếm `@BotFather`.
2. Gõ `/newbot`, đặt tên hiển thị và username (kết thúc bằng chữ `bot`).
3. Copy đoạn mã **HTTP API Token**.
4. Sao chép `.env.example` thành `.env`, rồi điền token:
   ```text
   TELEGRAM_BOT_TOKEN=token_cua_ban
   ```
   Hoặc đặt tạm trong PowerShell trước khi chạy:
   ```powershell
   $env:TELEGRAM_BOT_TOKEN = "token_cua_ban"
   ```
   Không dán token vào `config.py` và không commit file `.env`.

### Bước 3: Chạy Bot
- **Chế độ kiểm thử nhanh tại Terminal (Không cần Bot Token):**
  ```bash
  py main.py --test
  ```
- **Khởi chạy Bot Telegram trực tiếp (Live Demo):**
  ```bash
  py main.py
  ```

---

## 4. Hướng Dẫn Thao Tác Trên Telegram Bot

| Lệnh | Mô tả chi tiết |
| :--- | :--- |
| `/start` | Hiển thị lời chào, hướng dẫn sử dụng và Menu nút bấm tương tác nhanh |
| `/signals` | Quét toàn bộ rổ cổ phiếu theo dõi, lọc ra các mã đạt tín hiệu MUA hôm nay ($TA\_Score \ge 75$ và qua lọc BCTC) |
| `/check <MÃ>` | Tra cứu sức khỏe toàn diện một mã cổ phiếu (Ví dụ: `/check HPG`, `/check FPT`). Trả về bảng điểm BCTC, điểm Kỹ thuật 3 nhóm, khuyến nghị Entry, Stoploss, Target và khối lượng mua an toàn |
| `/alert <MÃ>` | Đăng ký nhận thông báo tự động khi cổ phiếu vi phạm ngưỡng kỹ thuật |
| `/portfolio` | Xem danh mục giả định, quản trị vốn NAV và hạn mức rủi ro |
| `/backtest` | Chạy kiểm thử chiến lược trên 3-6 tháng gần nhất, xuất tỷ lệ thắng (Win Rate), lợi nhuận bình quân và hệ số Profit Factor |
| `/industries` | Mở danh sách ngành để chọn bộ lọc riêng |
| `/industry banking` | Quét trực tiếp các mã thuộc ngành ngân hàng |

Industry Filter lấy phân loại ICB từ `vnstock.Listing`, lưu vào SQLite rồi mới tải dữ liệu và chạy filter riêng. Các metric ngành không có trong nguồn sẽ hiện `N/A`/`INSUFFICIENT_DATA`, không được thay bằng số giả định. Bộ lọc hiện có các nhóm: ngân hàng, chứng khoán, bất động sản, thép, dầu khí, điện, bán lẻ, hóa chất và vận tải/cảng biển; mã chưa map giữ tên ICB nguồn và dùng trạng thái ngành khác.

---

## 5. Cấu Trúc Mã Nguồn (Modular Architecture)

- `config.py`: File cấu hình tập trung (Token, danh mục theo dõi, các ngưỡng tham số chiến lược và quản trị rủi ro).
- `main.py`: Điểm khởi chạy hệ thống, hỗ trợ cả chế độ bot Telegram và chế độ CLI `--test`.
- `database/`: Quản lý lưu trữ SQLite cục bộ (`price_history`, `financial_metrics`, `user_alerts`).
- `data_pipeline/`: Thu thập dữ liệu từ vnstock, CafeF và cơ chế xoay vòng chống chặn IP (`anti_blocking.py`).
- `core_logic/`: Các thuật toán tính toán chỉ báo (`indicators.py`), chấm điểm phân vị (`scoring.py`), lọc BCTC (`fundamental_filter.py`) và chiến lược ra quyết định (`strategy.py`).
- `risk_management/`: Module định cỡ vị thế theo NAV (`position_sizing.py`) và quản lý Trailing Stop/Target (`exit_manager.py`).
- `backtesting/`: Công cụ mô phỏng giao dịch lịch sử 3-6 tháng và xuất báo cáo đánh giá hiệu suất (`backtest_engine.py`, `performance_report.py`).
- `bot/`: Tầng giao diện Telegram Bot, các lệnh tương tác và bàn phím Inline Keyboard (`telegram_bot.py`, `ui_helpers.py`).
- `core_logic/industry/`: Registry và filter riêng theo từng ngành.
- `data_pipeline/industry_loader.py`: Adapter phân loại ICB từ vnstock.

## 6. Những nơi cần sửa chiến lược v2

- `core_logic/indicators.py`: EMA, ATR, RSI, CP và VR.
- `core_logic/scoring.py`: phân vị 252 phiên và ba nhóm điểm.
- `core_logic/strategy.py`: điều kiện tạo `BUY_CANDIDATE`.
- `core_logic/fundamental_filter.py`: profile ngành và điều kiện BCTC.
- `risk_management/position_sizing.py`: vốn, stop, target và khối lượng.
- `backtesting/backtest_engine.py`: kiểm định dùng cùng gate với bot.

Chiến lược hiện yêu cầu tối thiểu 420 phiên, dùng Stop `2 ATR`, Target `3 ATR`, và không phát ứng viên nếu thiếu dữ liệu hoặc một điều kiện cứng bị trượt. Điểm kỹ thuật được giữ ở giá trị gốc; chỉ làm tròn khi hiển thị.
