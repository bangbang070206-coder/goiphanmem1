# BỘ LỌC NGÀNH CỔ PHIẾU – SPEC CHO GITHUB COPILOT

## 1. Mục tiêu

Xây dựng hệ thống đánh giá cổ phiếu theo 2 tầng:

1. Industry Filter: bộ lọc riêng theo từng ngành.
2. Technical Analysis (TA): đánh giá xu hướng/động lượng/giá-volume sau khi ngành đạt yêu cầu.

Không dùng một bộ threshold chung cho tất cả ngành.

Pipeline:

Stock
→ Industry Detection
→ Industry-specific Filter
→ Industry-specific Scoring
→ Technical Analysis
→ Final Result

Quan trọng:
- HARD FILTER = điều kiện bắt buộc, có thể làm cổ phiếu FAIL.
- SCORING = tiêu chí dùng để cộng/trừ điểm, không tự động FAIL.
- N/A hoặc thiếu dữ liệu = INSUFFICIENT_DATA, không tự động biến thành FAIL.
- Không hard-code theo ticker. Phải áp dụng theo ngành.
- Không tạo dữ liệu giả.
- Tận dụng data/API/database hiện có.
- Không rewrite module không liên quan nếu không cần.

---

# 2. Trạng thái chuẩn

Mỗi ngành nên trả về:

- PASS
- FAIL
- INSUFFICIENT_DATA

Các metric riêng lẻ nên có:

- PASS
- WARNING
- FAIL
- N/A

N/A không đồng nghĩa FAIL.

Ví dụ:

Revenue Growth = -3.77% đối với Software:
→ WARNING / trừ điểm nếu rule quy định
→ không hard-fail chỉ vì doanh thu âm nhẹ.

---

# 3. Nguyên tắc HARD FILTER và SCORING

Không biến mọi metric thành hard filter.

Ví dụ:

ROE:
- >= 15%: PASS
- 10–15%: WARNING
- < 10%: FAIL

Revenue Growth:
- Không mặc định là hard filter.
- Có thể đưa vào scoring.
- Nếu dữ liệu thiếu: N/A.

Có thể dùng cấu trúc:

INDUSTRY_RULES = {
    "software": {
        "hard_filters": [...],
        "scoring": [...],
        "weights": {...}
    },
    ...
}

---

# 4. NGÂN HÀNG (BANKING)

## Hard Filter
- ROE >= 12%
- NPL <= 3%
- CAR >= 9% hoặc ngưỡng pháp lý tương ứng
- Profit Growth >= 0%

## Scoring
- ROE: 20%
- NIM: 15%
- Profit Growth: 15%
- Credit Growth: 10%
- CASA: 10%
- NPL: 10%
- Loan Loss Coverage: 10%
- CIR: 10%

## Lưu ý
Không dùng Debt/Equity như doanh nghiệp thông thường.
Ưu tiên:
ROE, NIM, NPL, LLR, CASA, Credit Growth.

---

# 5. CHỨNG KHOÁN (SECURITIES)

## Hard Filter
- ROE >= 8%
- Profit Growth >= 0%
- Operating Cash Flow >= 0 nếu dữ liệu có
- Capital adequacy phải đạt ngưỡng pháp lý nếu có dữ liệu

## Scoring
- ROE: 20%
- Profit Growth: 20%
- Brokerage Market Share: 15%
- Margin Loan Growth: 15%
- Brokerage Revenue: 10%
- Trading Value: 10%
- Revenue Growth: 10%

## Lưu ý
Đánh giá theo:
Brokerage + Margin + Investment + Financial Strength.
Không chỉ nhìn EPS.

---

# 6. BẤT ĐỘNG SẢN (REAL ESTATE)

## Hard Filter
- CFO TTM >= 0
- Debt/Equity <= 2.5
- Interest Coverage > 1.5
- Cash/Short-term Debt >= 1 nếu có dữ liệu

## Scoring
- CFO: 20%
- Debt/Equity: 15%
- Profit Growth: 15%
- Gross Margin: 10%
- Revenue Growth: 10%
- Customer Advances: 10%
- Project/Backlog: 10%
- ROE: 10%

## Lưu ý
Không dùng Revenue Growth >= 0 làm hard filter mặc định.
Doanh thu BĐS có thể biến động theo thời điểm ghi nhận dự án.
Ưu tiên:
Inventory, Customer Advances, CFO, Debt, Project/Backlog.

---

# 7. PHẦN MỀM / CÔNG NGHỆ (SOFTWARE / TECHNOLOGY)

## Hard Filter
- ROE >= 15%
- CFO TTM > 0
- Debt/Equity <= 1.5
- Profit Growth >= 0

## KHÔNG hard filter
Revenue Growth >= 0 KHÔNG được là hard filter mặc định.

## Scoring
- ROE: 20%
- Profit Growth: 20%
- Revenue Growth: 15%
- EPS Growth: 10%
- Gross Margin: 10%
- CFO Quality: 10%
- Debt/Equity: 5%
- ROA: 5%
- R&D / Business Quality: 5%

## Ví dụ FPT
Nếu:
- ROE = 18.71% → PASS
- Profit Growth = 16.06% → PASS
- CFO > 0 → PASS
- Debt/Equity = 1.01 → PASS
- Revenue Growth = -3.77% → WARNING / trừ điểm

Thì FPT không được FAIL ngành chỉ vì Revenue Growth âm nhẹ.

---

# 8. THÉP (STEEL)

## Hard Filter
- CFO TTM >= 0
- Debt/Equity <= 2
- Interest Coverage >= 1.5

## Scoring
- Profit Growth: 20%
- Gross Margin: 15%
- Revenue Growth: 10%
- ROE: 10%
- CFO: 10%
- Debt/Equity: 10%
- Sales Volume: 10%
- Capacity Utilization: 5%
- Steel Price: 5%
- Input Cost: 5%

## Lưu ý
Phải xem xét tính chu kỳ giá thép và nguyên liệu.

---

# 9. DẦU KHÍ (OIL & GAS)

## Hard Filter
- CFO > 0
- Debt/Equity <= 2
- Profit >= 0

## Scoring
- Profit Growth: 20%
- ROE: 15%
- CFO: 15%
- Revenue Growth: 10%
- Gross Margin: 10%
- Oil Price Exposure: 10%
- Backlog: 10%
- Debt/Equity: 5%
- Dividend: 5%

## Lưu ý
Nếu có thể phân loại:
- Upstream
- Midstream
- Downstream
- Oil & Gas Services

thì có thể dùng rule phụ riêng cho từng nhóm.
Dịch vụ dầu khí ưu tiên Backlog, Contract Coverage, Utilization.

---

# 10. ĐIỆN / UTILITIES

## Hard Filter
- CFO >= 0
- Debt/Equity <= 3
- Interest Coverage >= 1.5

## Scoring
- CFO: 20%
- ROE: 15%
- Profit Growth: 15%
- Revenue Growth: 10%
- Debt/Equity: 10%
- Capacity Utilization: 10%
- Power Output: 5%
- Gross Margin: 5%
- Dividend: 5%

## Phân nhóm nếu có dữ liệu
- Hydropower
- Thermal Power
- Gas Power
- Renewable Energy

---

# 11. BÁN LẺ (RETAIL)

## Hard Filter
- CFO > 0
- Profit Growth >= 0
- Debt/Equity <= 2

## Scoring
- Revenue Growth: 20%
- Profit Growth: 20%
- ROE: 15%
- Gross Margin: 10%
- CFO: 10%
- Same-store Sales: 10%
- Store Growth: 5%
- Inventory Turnover: 5%
- Debt/Equity: 5%

Nếu Same-store Sales không có dữ liệu thì N/A, không FAIL.

---

# 12. HÓA CHẤT (CHEMICALS)

## Hard Filter
- CFO > 0
- Debt/Equity <= 2

## Scoring
- ROE: 15%
- Profit Growth: 15%
- Revenue Growth: 10%
- Gross Margin: 15%
- CFO: 15%
- Debt/Equity: 10%
- Selling Price: 5%
- Input Cost: 5%
- Capacity Utilization: 10%

---

# 13. VẬN TẢI / CẢNG BIỂN (TRANSPORTATION / PORTS)

## Hard Filter
- CFO > 0
- Debt/Equity <= 2
- Profit >= 0

## Scoring
- Revenue Growth: 15%
- Profit Growth: 20%
- ROE: 15%
- CFO: 15%
- Volume: 10%
- Capacity Utilization: 10%
- Freight Rate: 5%
- Debt/Equity: 5%
- Dividend: 5%

---

# 14. THỦY SẢN (SEAFOOD)

## Hard Filter
- CFO > 0
- Debt/Equity <= 2
- Profit >= 0

## Scoring
- Revenue Growth: 15%
- Profit Growth: 20%
- ROE: 15%
- Gross Margin: 15%
- CFO: 10%
- Export Growth: 10%
- Selling Price: 5%
- Debt/Equity: 5%
- Inventory: 5%

---

# 15. DỆT MAY (TEXTILE)

## Hard Filter
- CFO > 0
- Debt/Equity <= 2

## Scoring
- Revenue Growth: 15%
- Profit Growth: 20%
- ROE: 15%
- Gross Margin: 15%
- CFO: 10%
- Order/Backlog: 10%
- Capacity Utilization: 5%
- Debt/Equity: 5%

---

# 16. THỰC PHẨM / F&B (FOOD & BEVERAGE)

## Hard Filter
- CFO > 0
- Profit >= 0
- Debt/Equity <= 2

## Scoring
- Revenue Growth: 20%
- Profit Growth: 20%
- ROE: 15%
- Gross Margin: 15%
- CFO: 10%
- Market Share: 5%
- Volume Growth: 5%
- Debt/Equity: 5%
- Inventory: 5%

---

# 17. DƯỢC (PHARMACEUTICALS)

## Hard Filter
- ROE >= 10%
- CFO > 0
- Debt/Equity <= 1.5

## Scoring
- Revenue Growth: 15%
- Profit Growth: 20%
- ROE: 15%
- Gross Margin: 15%
- CFO: 10%
- EPS Growth: 10%
- R&D: 5%
- Debt/Equity: 5%

---

# 18. XÂY DỰNG (CONSTRUCTION)

## Hard Filter
- CFO >= 0
- Debt/Equity <= 2.5
- Interest Coverage >= 1.5

## Scoring
- Backlog: 20%
- Revenue Growth: 15%
- Profit Growth: 15%
- ROE: 10%
- CFO: 15%
- Gross Margin: 10%
- Debt/Equity: 5%
- Book-to-Bill: 5%

Backlog là chỉ tiêu quan trọng nếu dữ liệu có.

---

# 19. KHU CÔNG NGHIỆP (INDUSTRIAL PARKS)

## Hard Filter
- CFO >= 0
- Debt/Equity <= 2.5

## Scoring
- Occupancy Rate: 20%
- Leased Area Growth: 15%
- Revenue Growth: 15%
- Profit Growth: 15%
- ROE: 10%
- CFO: 10%
- Rental Price Growth: 5%
- Debt/Equity: 5%
- Backlog: 5%

---

# 20. BẢO HIỂM (INSURANCE)

## Hard Filter
- Profit >= 0
- ROE >= 8%
- Solvency Ratio >= regulatory requirement nếu có dữ liệu

## Scoring
- Premium Growth: 15%
- Profit Growth: 20%
- ROE: 15%
- Combined Ratio: 15%
- Investment Yield: 10%
- CFO: 10%
- Solvency: 10%
- Dividend: 5%

Không dùng bộ rule của ngân hàng cho bảo hiểm.

---

# 21. CẤU TRÚC CODE ĐỀ XUẤT

Ưu tiên architecture dạng configuration + class.

Ví dụ:

```python
INDUSTRY_FILTERS = {
    "banking": BankingFilter(),
    "securities": SecuritiesFilter(),
    "real_estate": RealEstateFilter(),
    "software": SoftwareFilter(),
    "steel": SteelFilter(),
    "oil_gas": OilGasFilter(),
    "electricity": ElectricityFilter(),
    "retail": RetailFilter(),
    "chemicals": ChemicalFilter(),
    "transportation": TransportationFilter(),
    "seafood": SeafoodFilter(),
    "textile": TextileFilter(),
    "food_beverage": FoodBeverageFilter(),
    "pharmaceuticals": PharmaceuticalFilter(),
    "construction": ConstructionFilter(),
    "industrial_parks": IndustrialParkFilter(),
    "insurance": InsuranceFilter(),
}
```

Hoặc nếu project đang có generic filter architecture, tận dụng architecture hiện tại.

Mỗi filter nên có interface:

```python
class IndustryFilter:
    def evaluate(self, stock):
        ...

    def score(self, stock):
        ...

    def explain(self, stock):
        ...
```

---

# 22. DATA AVAILABILITY

Nếu metric không tồn tại trong API/database:

```text
metric = N/A
status = INSUFFICIENT_DATA
```

Không:
- tự đoán
- tự tạo số
- dùng 0 thay cho missing
- biến missing thành FAIL

Đặc biệt:
- Missing technical data không được làm Industry Filter FAIL.
- Missing Industry data không được làm TA FAIL.
- Hai pipeline phải độc lập.

---

# 23. FINAL DECISION

Pipeline:

Industry Filter
    ↓
PASS → tiếp tục TA
FAIL → loại theo Industry
INSUFFICIENT_DATA → trạng thái thiếu dữ liệu ngành

Sau đó:

TA
    ↓
PASS / FAIL / INSUFFICIENT_DATA

Final result phải cho biết nguyên nhân cụ thể.

Ví dụ:

FPT:

Industry:
PASS

TA:
INSUFFICIENT_DATA

Final:
INSUFFICIENT_DATA

Không ghi:
"Chưa đạt lọc BCTC"
nếu Industry Filter thực tế đã PASS.

---

# 24. OUTPUT MONG MUỐN

Ví dụ:

KẾT QUẢ ĐÁNH GIÁ MÃ FPT

Ngành: Phần mềm

1. BỘ LỌC NGÀNH – SOFTWARE

Profitability
✅ ROE: 18.71%

Growth
⚠️ Revenue Growth: -3.77%
   → Không phải hard fail đối với Software

✅ Profit Growth: 16.06%

Risk
✅ Debt/Equity: 1.01
✅ CFO TTM: 12.67T

Điểm ngành: XX/100

Trạng thái ngành: PASS

2. CHẤM ĐIỂM TA

Trend: N/A
Momentum: N/A
Price & Volume: N/A
TA Score: N/A

Trạng thái TA: INSUFFICIENT_DATA

3. FINAL STATUS

INSUFFICIENT_DATA

Lý do:
- Bộ lọc ngành đạt.
- Dữ liệu giá chưa đủ số phiên hợp lệ để tính TA.

Không được nói:
"Chưa đạt lọc BCTC: Revenue Growth < 0"
nếu SoftwareFilter không đặt Revenue Growth là hard filter.

---

# 25. YÊU CẦU COPILOT TRƯỚC KHI CODE

Trước khi chỉnh sửa:

1. Đọc toàn bộ architecture hiện tại.
2. Tìm module xác định industry.
3. Tìm module industry filter hiện tại.
4. Tìm nơi khai báo threshold.
5. Tìm nơi tính industry score.
6. Tìm nơi tạo PASS/FAIL/DATA_UNAVAILABLE.
7. Tìm nơi tính TA.
8. Trace một ticker cụ thể như FPT qua toàn bộ pipeline.
9. Xác định chính xác tại sao Revenue Growth < 0 đang làm FPT FAIL.
10. Đề xuất file cần sửa/tạo.
11. Chỉ sau khi hiểu architecture mới implement.

Không hard-code theo ticker.
Không tạo data giả.
Không rewrite toàn bộ project nếu không cần.
Giữ backward compatibility với các module hiện tại.
Thêm unit tests cho ít nhất:
- Banking
- Software/FPT
- Real Estate
- Securities
- Missing data
- TA data unavailable

Mục tiêu cuối cùng:
Mỗi ngành phải thực sự dùng bộ tiêu chí riêng, thay vì chỉ phân loại ngành nhưng vẫn chạy generic rules.
