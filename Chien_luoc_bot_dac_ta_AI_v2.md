# Đặc tả chiến lược và sửa bot chứng khoán

Phiên bản đề xuất 2.0 | Dành cho AI hỗ trợ lập trình và nhóm kiểm thử | Ngày soạn 22 tháng 9 năm 2026

Tài liệu này dùng cùng mã nguồn goiphanmem1-main.zip để sửa bot Telegram hiện có. Phạm vi gồm dữ liệu đầu vào, lọc cơ bản theo ngành, chấm điểm kỹ thuật, quản trị vị thế, tín hiệu và kiểm định. Đây là đặc tả triển khai, không phải bài thuyết trình, mã nguồn đã sửa hay kết quả backtest đã được chứng minh.

Quyết định thiết kế: giữ hướng chọn doanh nghiệp đủ điều kiện rồi tìm trạng thái xu hướng thuận lợi; mở bộ lọc cơ bản theo mô hình kinh doanh; giữ ba nhóm điểm có giải thích; chỉ dùng nến hoàn chỉnh để xác nhận mua. Giá trong phiên phục vụ tra cứu và cảnh báo vị thế. Bot phát đề xuất, không tự đặt lệnh ở công ty chứng khoán.

## 1 Mục tiêu và thứ tự ưu tiên

Đề bài yêu cầu bot Telegram Mua/Bán, dữ liệu giá lịch sử và thời gian thực, dữ liệu tài chính phục vụ lọc cơ bản, tối thiểu một chiến lược được code, mã nguồn Python có README và demo hoạt động. Barem là hoàn thiện 40%, sáng tạo và độ sâu tài chính 30%, kiến trúc code 20%, báo cáo 10%; backtest 3–6 tháng được ghi “nếu có”. Không cần hiện thực đồng thời mọi ví dụ chiến lược của đề.

Ưu tiên sửa lỗi dữ liệu và phép tính trước; tiếp theo hoàn thiện cảnh báo Mua/Bán; sau đó mới tối ưu ngưỡng. “Tối ưu” trong tài liệu là cân đối khả năng triển khai, giải thích và bám đề, không phải bảo đảm điểm số hay lợi nhuận cao nhất.

Yêu cầu bắt buộc được viết bằng “phải”. Ngưỡng chiến lược là giả thuyết ban đầu có thể kiểm định; không được tự nới để tạo thêm mã mua. Mỗi thay đổi ngưỡng hoặc công thức phải tăng strategy_version và lưu config_hash. Điểm cao là mức phù hợp với mô hình, không phải xác suất thắng.

Bản 2.0 là chuẩn cho lần triển khai này khi mâu thuẫn với tài liệu 1.0. Các công thức thay đổi được liệt kê ở mục 2; không trộn điểm của hai phiên bản trong cùng danh sách. Giữ chức năng sẵn có nhưng sửa mô tả nếu chưa triển khai đầy đủ.

Phạm vi mục tiêu là cổ phiếu thường trên HOSE, gồm doanh nghiệp phi tài chính, ngân hàng, chứng khoán và bảo hiểm. Loại chứng quyền, ETF, trái phiếu và công cụ ngoài phạm vi. HNX và UPCoM là mở rộng sau, không tự gộp qua fallback. Phân tích kỹ thuật có thể hiển thị tham khảo cho mã thiếu tài chính, nhưng không nâng thành ứng viên mua của chiến lược đầy đủ.

---
## 2 Những thay đổi so với bản đã triển khai

1. Thay danh sách loại toàn bộ tổ chức tài chính bằng bộ định tuyến ngành và các profile riêng. Một mã có thể thiếu dữ liệu cho profile, nhưng không bị kết luận yếu chỉ vì thuộc ngành tài chính.
2. Thay X_V bị cắt về 0 và phân vị của X_V bằng kết hợp phân vị khối lượng tương đối với vị trí đóng cửa. Xóa việc quy phiên giảm thành hàng loạt số 0 trong chuỗi dùng xếp hạng khối lượng.
3. Khối lượng trung bình phải lấy 20 phiên trước, không gồm phiên hiện tại. Phân vị lấy đúng 252 phiên trước, không bỏ dữ liệu thiếu rồi kéo lùi thêm.
4. Mua bắt buộc có Close_t > Close[t-1] và RSI14 > 50. Bổ sung giới hạn khoảng cách Close so với EMA20 là tối đa 3 ATR, nhằm thử kiểm soát mua khi giá đã kéo xa. Đây là thay đổi chiến lược cần ablation, không phải lỗi cú pháp.
5. Giữ Stop ban đầu 2 ATR và Target 3 ATR theo config của ZIP để hạn chế thay đổi triển khai. Hai hệ số này thay thế 1,5 và 2,5 ATR trong tài liệu 1.0; đều là tham số thử nghiệm, không có căn cứ để gọi là tối ưu.
6. Chuẩn hóa mọi phép tính tiền về VND. Điểm dùng số chưa làm tròn; số hiển thị chỉ là bản trình bày.
7. BUY_CANDIDATE, kế hoạch vốn, vị thế thực và đề xuất bán là các đối tượng riêng. Thiếu dữ liệu không đồng nghĩa HOLD hay trượt chất lượng.
8. Dùng chung hàm chỉ báo, điều kiện và quản trị vị thế giữa bot và backtest. Bổ sung đối soát sổ tiền, phí, lượng đã bán, giao dịch chờ và ngày có thể bán.

Các lỗi đã tái hiện trong ZIP gồm bỏ qua ngày không đọc được, dùng cache không kiểm tra tuổi, thiếu điều kiện phiên tăng, sai đơn vị định cỡ và chấm NaN thành 0. Bộ phận AI phải sửa độc lập với việc tối ưu chiến lược.

Các bản ghi kỳ 2018 trong SQLite là dữ liệu cũ đáng nghi; chưa chứng minh nguồn API hiện tại trả sai. Hàm sắp quý hiện tại có thể sắp đúng đầu vào hợp lệ. Phải lưu bảng API gốc mới và đối chiếu trước khi kết luận nguyên nhân. Không xóa dấu vết cũ để làm kết quả nhìn đẹp hơn.

Phải chạy trên bản sao dữ liệu khi kiểm thử; giữ bản ZIP gốc làm mốc. Không dùng ảnh của bản cũ làm bằng chứng cho kết quả phiên bản mới.

---
## 3 Luồng xử lý và hợp đồng dữ liệu

Luồng đầy đủ: lấy danh mục mã và ngành → tải và kiểm tra dữ liệu → chọn profile cơ bản → tính chỉ báo trên phiên hoàn chỉnh → kiểm tra điều kiện cứng → chấm điểm và xếp ứng viên → kiểm tra vốn theo người dùng → gửi Telegram → theo dõi vị thế và xác nhận giao dịch.

Mỗi dữ liệu phải có ticker, nguồn, source_version hoặc phiên bản adapter, fetched_at theo UTC, thời điểm sự kiện tại nguồn nếu có, chất lượng và đơn vị. Hiển thị giờ Asia/Ho_Chi_Minh. Đồng hồ hiện tại phải được truyền vào hàm kiểm tra để test được, không rải datetime.now khắp core logic.

Bảng giá ngày phải có session_date, OHLC, volume_shares, traded_value_vnd, is_final, adjustment_basis. Điều kiện: giá hữu hạn và dương; low ≤ min(open, close) ≤ max(open, close) ≤ high; volume hữu hạn và không âm; ngày duy nhất, tăng dần. Phân biệt phiên không giao dịch được nguồn xác nhận với nến bị thiếu; không tự forward-fill OHLCV để đủ cửa sổ.

Đơn vị nội bộ: giá, ATR, stop, target, tiền và NAV đều là VND; lượng là cổ phiếu; tỷ lệ dùng số thập phân, 15% = 0.15. Adapter có price_multiplier theo nguồn đã kiểm chứng; không đoán đơn vị bằng độ lớn của giá. Giữ trường đơn vị gốc để truy vết. Không chia ROE cho 100 chỉ vì ROE > 1 vì ROE thực có thể vượt 100%.

Giá raw dùng mô phỏng khớp; giá điều chỉnh nhất quán dùng chỉ báo. Phải lưu hệ số/sự kiện doanh nghiệp để quy ngưỡng về cơ sở giao dịch. Khi chưa xác định đúng điều chỉnh, chặn quyết định liên quan bằng CORPORATE_ACTION_REVIEW. Khối lượng phải cùng cơ sở cổ phiếu khi so qua chia tách; không cộng cổ tức hai lần.

FinancialFact tối thiểu có metric_code, value, unit, period_start, period_end, frequency, accumulation_type, statement_scope, published_at, fetched_at, source_url, revision_id và verification_status. statement_scope phân biệt hợp nhất và riêng lẻ. Không ghép lợi nhuận công ty mẹ với vốn toàn tập đoàn để tính ROE.

Nguồn và khả năng truy cập phải được thử thực tế. Vnstock là lớp kết nối, không bảo đảm mọi nguồn có cùng schema [S1]. Dùng một adapter chính cho mỗi loại dữ liệu; nguồn thay thế chỉ dùng sau đối chiếu đơn vị, kỳ, điều chỉnh. Đổi nguồn phải lưu dấu vết. Không coi request thành công là dữ liệu hợp lệ.

---
## 4 Cập nhật API và quản lý cache

Giá trong phiên: ưu tiên stream nếu có quyền; nếu polling, khởi đầu 60 giây cho danh sách theo dõi hữu hạn, có hạn mức tổng và backoff. Chỉ ghi “realtime” khi thực sự biết độ trễ phù hợp; còn lại ghi rõ lấy mẫu hoặc độ trễ nguồn. Không quét toàn bộ BCTC mỗi 60 giây.

Giá ngày: sau khi nguồn xác nhận phiên hoàn chỉnh, cập nhật nến mới và nến bị sửa. Cache đủ 200 hay 420 nến không được bỏ qua việc kiểm tra phiên mới nhất. Hàm nhận required_sessions; nếu thiếu thì tải lùi đến đủ hoặc trả INSUFFICIENT_HISTORY với số phiên thực có. Không dùng tham số “days” vừa mang nghĩa ngày lịch vừa mang nghĩa số nến.

Tài chính: kiểm tra công bố mới mỗi 60 phút trong giờ vận hành nếu hạn mức cho phép; đối soát hằng ngày. Khi nguồn thiếu endpoint công bố, dùng lịch kiểm tra có TTL và công khai thời điểm kiểm tra gần nhất. Báo cáo mới làm mất hiệu lực đánh giá cũ của mã. Có dữ liệu mới nhưng chưa parse xong thì chặn mua mã đó; không âm thầm dùng bản cũ.

Tách tuổi dữ liệu khỏi tuổi cache. period_end dùng kiểm tra tài chính quá cũ; fetched_at dùng kiểm tra đã đối soát nguồn hay chưa. Chuỗi 2018-Q4 phải chuyển thành period_end 2018-12-31, không coi đó là ngày công bố. Ngày thiếu, sai định dạng hoặc thuộc tương lai bất hợp lệ → DATA_INVALID. Dữ liệu quý quá 180 ngày từ cuối kỳ → DATA_STALE. Với tỷ lệ an toàn chỉ công bố năm, giới hạn là 450 ngày và phải hiển thị kỳ năm; không giả vờ là số quý mới nhất. Đây là chính sách thử nghiệm, không phải thời hạn pháp luật.

Cache lỗi phải có retry_after; khởi đầu 15 phút, backoff theo lỗi nguồn. Không cache FETCH_FAILED vô thời hạn. Dữ liệu tài chính hợp lệ cũ vẫn dùng khi API gián đoạn nếu chưa quá tuổi và chưa biết có công bố mới; hiển thị cảnh báo nguồn. Cache tín hiệu gắn strategy_version và mã snapshot, không chỉ gắn thời gian vừa tính lại.

Nến hiện tại chưa đóng chỉ hiển thị PREVIEW. Phiên t trong công thức là phiên hoàn chỉnh mới nhất đã có tại thời điểm đánh giá. Nếu phiên cần có đã kết thúc mà chưa có dữ liệu cuối phiên, giữ lịch sử để tra cứu và ngừng phát ứng viên mua mới.

Danh mục ngành, sàn, trạng thái và thành phần VN30 cập nhật trước phiên. API lỗi thì danh sách dự phòng phải ghi rõ tên và số mã; không gọi 20 mã dự phòng là “toàn thị trường” hoặc VN30.

---
## 5 Chuẩn hóa báo cáo tài chính

Chỉ cộng quý riêng lẻ. Nếu nguồn trả lũy kế: Q1 = YTD_Q1; Q2 = YTD_Q2 − YTD_Q1; Q3 = YTD_Q3 − YTD_Q2; Q4 = FY − YTD_Q3. Số liệu dùng phép trừ phải cùng phạm vi báo cáo và phiên bản có thể đối chiếu. Thiếu mốc thì trả thiếu dữ liệu, không suy đoán.

TTM_t = tổng 4 quý riêng liên tiếp đến quý t. Growth_TTM = TTM_t / TTM[t-4] − 1, chỉ tính khi mẫu số > 0. Cần 8 quý liên tiếp cho tăng trưởng; 5 quý không được tự chuyển thành tăng trưởng một quý cùng kỳ. Nếu mẫu số ≤ 0, trả BASE_NONPOSITIVE và FUNDAMENTAL_REVIEW; vẫn có thể hiển thị chênh lệch tuyệt đối nhưng không dùng phần trăm đó xét đạt.

LNST công ty mẹ TTM và VCSH công ty mẹ cuối kỳ phải dương. ROE_TTM = LNST công ty mẹ TTM / trung bình VCSH công ty mẹ tại 5 mốc cuối quý bao phủ 4 quý. Các mốc vốn phải hữu hạn và dương; nếu có mốc không dương thì REVIEW. Công ty độc lập chỉ dùng lợi nhuận/vốn toàn công ty khi xác minh không có phần thiểu số; không fallback tùy tiện.

Tổng nợ phải trả/VCSH = total_liabilities / total_equity cùng cuối kỳ và phạm vi hợp nhất. Không gọi đây là nợ vay/VCSH. CFO_TTM chỉ lấy tiền thuần từ hoạt động kinh doanh, không lấy lợi nhuận hoạt động hoặc tiền trước thay đổi vốn lưu động thay thế. Thiếu 4 quý CFO thì không dùng 1 quý dưới nhãn TTM.

EPS TTM lấy nguồn công bố có định nghĩa và cơ sở cổ phiếu rõ hoặc tính từ lợi nhuận dành cho cổ đông thường và lượng cổ phiếu bình quân gia quyền phù hợp. Không cộng EPS quý nếu cơ sở cổ phiếu khác nhau. P/E = giá VND/EPS VND; P/B = giá VND/BVPS VND cùng cơ sở cổ phiếu. EPS hoặc BVPS ≤ 0 thì tỷ số tương ứng không có ý nghĩa để định giá, hiển thị N/A. Trong v2, P/E và P/B là tham khảo, không áp ngưỡng loại chung mọi ngành.

Parser phải dựa vào mapping trường đã kiểm chứng bằng bảng gốc. Gặp schema mới, nhiều dòng khớp hoặc thứ tự quý không xác định thì DATA_INVALID; không giữ thứ tự nguồn rồi lấy cột cuối. Lưu raw response và hash; mỗi số dùng xét lọc phải truy được về dòng/cột/đơn vị gốc. BCTC và tỷ lệ an toàn khác phạm vi không được trộn vào cùng phép chia; có thể kiểm tra như các tiêu chí riêng với nhãn phạm vi riêng.

---
## 6 Phân ngành và profile lọc cơ bản

Bỏ EXCLUDED_SECTOR_TICKERS làm cơ chế phân loại chính. Dùng nguồn ngành có mã ngành, tên, phiên bản và thời điểm áp dụng; mapping về NON_FINANCIAL, BANK, SECURITIES, INSURANCE_LIFE, INSURANCE_NONLIFE hoặc REVIEW. Công ty mẹ hỗn hợp/holding chưa mapping chắc chắn → FUNDAMENTAL_REVIEW. Không suy ngành từ tên mã. Ngoại lệ thủ công phải có nguồn và thời hạn.

Các profile dưới đây là sàng lọc ban đầu cho đề tài, không phải mô hình đánh giá toàn diện sức khỏe hay định giá doanh nghiệp. Mọi ngưỡng ROE, tăng trưởng, đòn bẩy, nợ xấu và khoảng đệm vốn đều là tham số nghiên cứu, không được mô tả là mức tối ưu đã chứng minh.

Điều kiện chung: VCSH công ty mẹ cuối kỳ > 0; LNST công ty mẹ TTM > 0; dữ liệu bắt buộc hợp lệ; không có trạng thái giao dịch cấm mở mới. Mỗi profile yêu cầu đạt TẤT CẢ điều kiện riêng dưới đây.

| Profile | Điều kiện riêng ban đầu |
| --- | --- |
| NON_FINANCIAL | ROE_TTM ≥ 15%; tăng trưởng doanh thu thuần TTM > 0; tăng trưởng LNST mẹ TTM > 0; tổng nợ phải trả/tổng VCSH ≤ 1,5; CFO_TTM > 0 |
| BANK | ROE_TTM ≥ 10%; tăng trưởng LNST mẹ TTM > 0; tỷ lệ nợ xấu ≤ 3%; mức bao phủ yêu cầu vốn ≥ 1,10 |
| SECURITIES | ROE_TTM ≥ 10%; tăng trưởng LNST mẹ TTM > 0; mức bao phủ yêu cầu vốn khả dụng ≥ 1,10 |
| INSURANCE_LIFE | ROE_TTM ≥ 8%; tăng trưởng LNST mẹ TTM > 0; mức bao phủ yêu cầu khả năng thanh toán ≥ 1,10 |
| INSURANCE_NONLIFE | ROE_TTM ≥ 8%; tăng trưởng LNST mẹ TTM > 0; mức bao phủ yêu cầu khả năng thanh toán ≥ 1,10 |

Ngân hàng: nợ xấu = dư nợ xấu/tổng dư nợ cho vay khách hàng gộp cùng phạm vi, theo định nghĩa của báo cáo. CAR, chất lượng tín dụng và thanh khoản phản ánh các khía cạnh khác nhau; CAR không thay thế kiểm tra nợ xấu. Không dùng tiền gửi như nợ doanh nghiệp sản xuất. Theo dõi thêm bao phủ nợ xấu và thanh khoản khi có dữ liệu nhưng chưa cộng vào điểm v2.

Chứng khoán: không áp CFO và nợ/VCSH của doanh nghiệp phi tài chính. Tỷ lệ vốn khả dụng dùng đúng báo cáo an toàn tài chính; theo dõi thêm cho vay ký quỹ và tự doanh ở phần giải thích, không giả vờ profile đã đo hết rủi ro thị trường.

Bảo hiểm: tách dữ liệu và định nghĩa theo loại hình. Không áp combined ratio của phi nhân thọ cho nhân thọ. Bản v2 dùng bộ tối thiểu vốn và lợi nhuận; chưa đưa combined ratio vào gate vì cần dữ liệu cùng cơ sở. ROE tốt không chứng minh chất lượng dự phòng tốt. Nguyên tắc vốn phù hợp rủi ro của bảo hiểm tham khảo IAIS [S3].

---
## 7 Dữ liệu an toàn vốn và điều kiện bật profile

Mức bao phủ = tỷ lệ an toàn được công bố / tỷ lệ tối thiểu áp dụng, hoặc vốn đủ điều kiện/yêu cầu vốn khi báo cáo trình bày trực tiếp hai số này. Chỉ so các giá trị cùng định nghĩa, đơn vị, phạm vi và thời điểm áp dụng. Ví dụ giả định: tỷ lệ thực tế 12%, yêu cầu 10% → bao phủ 1,20. Đây là ví dụ số học, không phải quy định pháp lý của một ngành.

Không mã hóa một tỷ lệ pháp lý chung từ trí nhớ. regulatory_rules phải chứa metric_code, entity_scope, framework, minimum, effective_from, effective_to, source_url và verified_at. Người triển khai xác minh yêu cầu thực sự áp dụng cho tổ chức từ nguồn công bố chính thức hoặc báo cáo của tổ chức. Nếu chưa xác minh được, trả RULES_UNVERIFIED và chặn mua; không đặt minimum=0 hoặc bỏ tiêu chí. Hệ số 1,10 là khoảng đệm nghiên cứu của nhóm, không phải yêu cầu pháp luật. Vốn ngân hàng có thước đo chuyên biệt, xem cơ sở Basel [S2].

Nguồn ưu tiên: API đã đối chiếu cho giá, ngành và BCTC; báo cáo an toàn vốn/khả năng thanh toán tại trang quan hệ nhà đầu tư của doanh nghiệp hoặc cơ quan quản lý cho trường chuyên ngành. Không hứa API phổ thông luôn có đủ CAR, vốn khả dụng hoặc khả năng thanh toán.

Cho phép nhập CSV có kiểm chứng để bổ sung chỉ tiêu chuyên ngành: ticker, metric_code, value, unit, period_end, published_at, statement_scope, source_url, reviewer, verified_at. Nhập tay vẫn phải đi qua validator và giữ xuất xứ MANUAL_VERIFIED; đây là phương án bổ sung, không được tuyên bố toàn bộ dữ liệu đã tự động hóa.

Mỗi profile có capability_status: READY khi mapping, nguồn và test đã đạt; DATA_PENDING khi chưa đủ dữ liệu. Phải triển khai logic của cả bốn nhóm; chỉ phát BUY_CANDIDATE cho từng mã có đủ dữ liệu hợp lệ. Không loại toàn ngành vĩnh viễn và cũng không bật đại trà profile thiếu bằng chứng. Với mã thiếu trường, cho xem giá/điểm tham khảo và ghi đúng trường còn thiếu.

Báo cáo độ bao phủ theo ngành: số mã mục tiêu, số mã phân ngành được, đủ dữ liệu, đạt cơ bản, đạt kỹ thuật. Kiểm tra ít nhất hai mã mỗi profile nếu có trong phạm vi. Nếu phần lớn ngân hàng thiếu CAR hoặc bảo hiểm thiếu tỷ lệ thanh toán, phải trình bày hạn chế và kế hoạch nhập nguồn chính thức, không thay nhãn thiếu thành trượt.

Đối với phi tài chính, ngưỡng nợ 1,5 và CFO dương có thiên lệch theo ngành. Theo dõi tỷ lệ loại theo ngành; giữ nguyên profile nền trong lần test đầu, chỉ tách thêm nhóm ngành sau khi có bằng chứng. Chưa tuyên bố profile chung đó tối ưu cho sản xuất, bán lẻ, bất động sản và tiện ích cùng lúc.

---
## 8 Chỉ báo kỹ thuật và thang điểm mới

Cần tối thiểu 420 phiên hợp lệ và đúng 252 quan sát chỉ báo liền trước sau khởi tạo. Backtest cần thêm số phiên đánh giá ở ngoài phần khởi động. Không dùng NaN, infinity hoặc dữ liệu lỗi làm 0 điểm. EMA_N khởi tạo SMA N phiên đầu, alpha=2/(N+1). ATR14 và RSI14 làm trơn Wilder alpha=1/14; ATR khởi tạo 14 TR từ phiên có giá trước; RSI tính giá trị đầu tiên ngay tại mốc khởi tạo. RSI không giảm nhưng có tăng=100; không tăng không giảm=50; ATR≤0 → không đủ điều kiện chấm.

TR_t = max(H_t−L_t, abs(H_t−C[t-1]), abs(L_t−C[t-1])).
X_T = (EMA20−EMA50)/ATR14. X_M = RSI14.
VR_t = Volume_t / mean(Volume[t-20] ... Volume[t-1]).
CP_t = (C_t−L_t)/(H_t−L_t). Nếu H=L và OHLC hợp lệ thì CP=0,5; mẫu số trung bình volume bằng 0 thì VR không hợp lệ.

P252(x) = 100 × (số quan sát nhỏ hơn x + 0,5 × số quan sát bằng x)/252, trên đúng 252 phiên trước, không chứa t. Dùng dữ liệu gốc để xử lý bằng nhau, chỉ làm tròn khi hiển thị. Trong cửa sổ có thiếu dữ liệu thì score=null. Không nối 252 quan sát rời rạc thành “252 phiên liên tiếp”.

S_T = P252(X_T); S_M = P252(RSI14).
S_V = 0,5 × P252(VR) + 0,5 × (100 × CP).
TA_Score = (S_T + S_M + S_V)/3.

Thay đổi S_V giữ riêng hai câu hỏi: khối lượng có bất thường so với lịch sử và giá đóng ở đâu trong biên độ ngày. Không đưa điều kiện tăng/giảm vào chuỗi VR; điều kiện phiên tăng nằm ở gate mua. Ví dụ P252(VR)=80, CP=0,8 → S_V=80; nếu CP=0,55 → S_V=67,5. Không còn cơ chế một X_V dương rất nhỏ tự vượt hàng loạt số 0 được tạo nhân tạo trong lịch sử.

Ba điểm vẫn không độc lập: EMA và RSI cùng dựa trên giá; CP cũng dùng giá. Trọng số bằng nhau là baseline minh bạch, không phải bằng chứng khử tương quan. SCTR là ví dụ thực tế về tổng hợp chỉ báo nhưng xếp hạng trong nhóm cổ phiếu; không xác nhận mô hình tự thân 252 phiên này [S4]. MACD chưa cộng điểm để hạn chế trùng thông tin.

Điểm giữa các mã dùng để ưu tiên mức phù hợp theo quy tắc chung, không chứng minh mã 85 sẽ sinh lời hơn mã 75. Thang điểm mới phải kiểm định lại ngưỡng; không so trực tiếp với điểm cũ trong ảnh hoặc database.

---
## 9 Điều kiện mua và xếp hạng

Ứng viên mua được xác nhận sau khi có dữ liệu hoàn chỉnh phiên t. Phải đạt đồng thời: đúng phạm vi và ngành; profile cơ bản PASSED; dữ liệu và quy tắc chuyên ngành hợp lệ; cổ phiếu được phép mở vị thế; thanh khoản; các điều kiện kỹ thuật dưới đây.

Thanh khoản: trung bình giá trị giao dịch 20 phiên trước ≥ 10 tỷ VND. Ưu tiên số nguồn cung cấp; nếu ước lượng Close_raw_VND × Volume thì gắn ESTIMATED, áp nhất quán và đối chiếu mẫu. Không dùng Close theo nghìn đồng nhân volume rồi so với ngưỡng VND.

Gate kỹ thuật: C_t > EMA50_t; EMA20_t > EMA50_t; C_t > C[t-1]; RSI14_t > 50; CP_t > 0,5; VR_t > 1; abs(C_t−EMA20_t)/ATR14_t ≤ 3; TA_Score chưa làm tròn ≥ 75. Điểm không bù điều kiện cứng trượt. 74,96 hiển thị 75,0 vẫn chưa đạt, phải ghi “chưa đạt theo giá trị gốc”.

Không yêu cầu EMA vừa giao cắt trong ba phiên. Phiên bản này tìm trạng thái tiếp diễn xu hướng, không còn là chiến lược chỉ bắt giao cắt mới. Nghiên cứu momentum là cơ sở hình thành giả thuyết, chưa chứng minh bộ EMA20/50 cho cổ phiếu Việt Nam [S5]. Giới hạn 3 ATR có thể bỏ lỡ xu hướng mạnh, cần đo đánh đổi.

Xếp ứng viên: điểm gốc giảm dần; hòa thì thanh khoản giảm dần; còn hòa thì ticker tăng dần. Kiểm tra vốn lần lượt theo thứ tự, cập nhật ngân sách đã dành cho kế hoạch chưa hết hạn để không đề xuất vượt tiền khi nhiều mã cùng đạt.

Ứng viên t chỉ có hiệu lực phiên giao dịch kế tiếp. Trước khi lập kế hoạch mua phải kiểm tra lại dữ liệu cơ bản/trạng thái, số vị thế và vốn. Người đã giữ mã không nhận đề xuất mua gia tăng trong v2. Giá cao nhất chấp nhận = C_t + 0,5 ATR_t, quy về cùng cơ sở giá; vượt thì bỏ kế hoạch, không mở rộng giới hạn tự động.

Quét không có mã đạt là kết quả hợp lệ. Telegram phải phân biệt: “0 ứng viên trên X mã đã đánh giá hợp lệ” với “chưa kết luận vì thiếu dữ liệu Y mã”. Danh sách theo dõi không được gắn tiêu đề “đã qua BCTC và điểm ≥75”.

Với vị thế đang giữ, đánh giá thoát theo mục 11, không gọi HOLD chỉ vì không có tín hiệu mua. Điểm giảm không tự động tạo lệnh bán. Doanh nghiệp trượt lọc sau công bố mới → FUNDAMENTAL_REVIEW, dừng mua mới và tiếp tục quản trị vị thế; v2 không tự bán vì một lỗi API.

---
## 10 Vốn và ghi nhận giao dịch

Hệ thống có hai chế độ tách biệt: PAPER với sổ mô phỏng và MANUAL với giao dịch người dùng xác nhận. Không tự ghi nhận đã mua khi gửi ứng viên. NAV mặc định 100 triệu chỉ dành cho tài khoản PAPER được ghi nhãn rõ; MANUAL thiếu vốn → chỉ xem ứng viên, không đưa lượng mua cá nhân.

NAV = tiền mặt + giá trị thị trường vị thế theo giá hợp lệ. Tiền/giá thiếu hoặc quá cũ → không lập kế hoạch mới. Một vị thế mỗi người–mã; không đòn bẩy. Rủi ro dự kiến mỗi giao dịch = 0,5% NAV; giới hạn 20% NAV/mã, 30% NAV/ngành, tối đa 5 mã. Các giới hạn chặn mua mới; biến động giá làm tỷ trọng vượt ngưỡng không tự gây bán bắt buộc.

Tại giá kế hoạch E tính bằng VND: Stop0=E−2 ATR0; Target0=E+3 ATR0; ATR0 lấy phiên tín hiệu và giữ cố định sau khớp. Stop0≤0 hoặc R=E−Stop0≤0 → từ chối. Giá giới hạn mua và stop làm tròn xuống bước giá hợp lệ; target làm tròn lên. Dùng bảng bước giá đã xác minh; sau làm tròn phải tính lại R và lượng.

Lượng là bội số lô giao dịch hợp lệ lớn nhất thỏa đồng thời: rủi ro kế hoạch Q×R cộng chi phí/trượt giá dự kiến ≤ 0,005 NAV; giá trị Q×E ≤ 0,20 NAV; giá trị ngành hiện có và đã dành cộng Q×E ≤ 0,30 NAV; Q×E cộng phí mua ≤ tiền có thể dùng. Không còn chỗ vị thế → không mua. Có thể giải bằng min các giới hạn rồi giảm từng lô để kiểm tra phí. Quy tắc lô và phí lấy từ execution_rules có nguồn, không rải số cứng khắp code.

Ví dụ không phí để test đơn vị: E=66.400 VND, ATR0=1.530 VND, NAV=100 triệu, đủ tiền/ngành và lô giả định 100 → ngân sách rủi ro 500.000, R=3.060, lượng 100 cổ phiếu. Không được trả 163.300 cổ phiếu do đưa giá 66,4 vào cùng NAV VND.

Khi người dùng xác nhận mua thực tế, ghi đúng giá, lượng và phí thực; không âm thầm sửa lượng đã mua để vừa giới hạn. Nếu vi phạm kế hoạch, vẫn ghi sổ chính xác và cảnh báo. Stop/target tính từ giá khớp thực và ATR0; giao dịch từng phần tính giá vốn bình quân trong cùng lệnh ban đầu, không coi là mua gia tăng tùy ý.

Lưu order_id, position_id, filled_qty, sellable_qty, cash_reserved, entry_time, atr0, stop_active, target0, partial_filled và các xác nhận. Mọi thay đổi tiền/lượng là transaction nguyên tử và idempotent. Stop là kích hoạt; gap, thiếu thanh khoản, phí và thời gian chờ có thể làm lỗ thực vượt 0,5% NAV.

---
## 11 Quy tắc bán và trailing stop

Giá trong phiên chỉ kích hoạt cảnh báo với sự kiện mới, hợp lệ. Không dùng giá cũ để khẳng định vừa chạm stop. Xử lý sự kiện theo thời gian; ưu tiên chỉ giải quyết điều kiện xung đột cùng thời điểm, không được dùng tín hiệu cuối ngày phủ nhận giao dịch đã khớp buổi sáng.

Thứ tự tại một thời điểm: yêu cầu thoát toàn bộ đã chốt từ trước → stop → target → kiểm tra xu hướng khi nhận sự kiện EOD. Stop bị chạm khi giá ≤ stop_active → đề xuất bán toàn bộ lượng có thể bán. Cổ phiếu chưa được phép bán chuyển SELL_PENDING. Yêu cầu stop/thoát xu hướng được giữ đến lần thực hiện hợp lệ, dù giá hồi, trừ khi người dùng hủy có ghi log; backtest không tự hủy.

Close phiên hoàn chỉnh < EMA50 → tạo yêu cầu thoát toàn bộ cho lần thực hiện hợp lệ kế tiếp. Không giả lập khớp chính Close vừa dùng xác nhận. Bản live chỉ giảm vị thế sau xác nhận giao dịch hoặc mô phỏng khớp của PAPER.

Chạm Target0 lần đầu → đề xuất bán 50% lượng ban đầu, làm tròn xuống theo lô; nếu lượng ban đầu chỉ một lô thì bán hết và ghi SELL_ALL_TARGET. Chưa có lượng được phép bán thì ghi TARGET_DEFERRED, không chốt lời giả. Đến khi được phép bán phải kiểm tra lại giá ≥ target; nếu giá đã dưới target, hủy ý định target đó và giữ vị thế theo stop/xu hướng. Bán target chỉ là lệnh giới hạn còn hiệu lực trong phiên; không tự đuổi giá xuống để hoàn thành chốt lời.

Chỉ khi lượng chốt mục tiêu đã khớp đầy đủ mới đánh dấu partial_filled=true. Khớp từng phần được ghi đúng tiền/lượng, phần chưa khớp không phát thành lệnh mới. Một yêu cầu SELL_ALL thay thế mục tiêu chốt một phần còn treo.

Sau khi chốt một phần, tại EOD tính highest_close = giá đóng cửa cao nhất từ phiên mua đến hiện tại. stop_next = max(stop_active, Entry, highest_close−2 ATR0). Stop mới có hiệu lực từ phiên kế tiếp; không áp lên low của phiên vừa dùng cập nhật. Không hạ stop. Nếu phiên sau mở dưới stop thì thực hiện theo khả năng khớp và quy tắc gap, không giả định bán được đúng stop.

Trường hợp tài khoản chỉ đăng ký /alert mà không có vị thế: gửi thay đổi trạng thái ứng viên, không gửi “bán cổ phiếu đang giữ”. Tín hiệu thoát chỉ dựa trên vị thế tồn tại. Thiếu dữ liệu cần cho thoát → DATA_STALE kèm vị thế và cảnh báo mất giám sát, không kết luận HOLD an toàn.

---
## 12 Telegram và vận hành thực tế

Tách data_status, fundamental_status, technical_status, position_status và action. Trạng thái dữ liệu gồm VALID, MISSING, INVALID, STALE; cơ bản gồm PASSED, FAILED, REVIEW, NOT_EVALUATED; hành động gồm NONE, BUY_CANDIDATE, BUY_PLAN, SELL_PARTIAL, SELL_ALL, SELL_PENDING. Lý do ngành không hỗ trợ hoặc quy tắc chưa xác minh nằm trong reason_codes, không gộp thành BCTC yếu.

/check MA phải hiển thị ngành/profile, kỳ tài chính, từng chỉ tiêu và điều kiện đạt/trượt/thiếu; ngày nến hoàn chỉnh; giá với đơn vị; ba điểm, tổng, gate chưa đạt; nguồn và thời điểm kiểm tra. Giá trong phiên hiển thị riêng với timestamp, không gọi là Close xác nhận. Với mã thiếu ngành hoặc tài chính vẫn có thể xem kỹ thuật tham khảo, ghi rõ chưa có quyết định mua đầy đủ.

/signals là danh sách ứng viên trong phạm vi thực đã quét; /vn30 dùng danh mục VN30 có ngày áp dụng. Khi fallback, đổi nhãn danh sách. /filterstats báo riêng ngoài phạm vi, thiếu dữ liệu, dữ liệu lỗi/cũ, trượt cơ bản, trượt kỹ thuật; số loại theo tiêu chí có thể trùng và phải ghi rõ. Không cộng số trượt từng tiêu chí như số mã duy nhất.

/portfolio hiển thị sổ tiền/vị thế thật của chế độ đã chọn; /capital cấu hình vốn; /position ghi nhận mua/bán với xác nhận; /alert, /alerts và /unalert quản lý đăng ký; /backtest hiển thị phạm vi, thời gian và giả định thực. Các thao tác tiền/vị thế phải gắn user_id, không để người khác sửa.

Phải có scheduler thực sự chạy: nhận nến EOD, cập nhật dữ liệu, kiểm tra ứng viên, theo dõi giá vị thế và gửi thông báo. Lời chào chỉ giới thiệu chức năng đã được nối và test. Tác vụ API/backtest nặng chạy ở worker, không chặn event loop Telegram. Có khóa chống quét trùng, hạn mức dùng chung, timeout và hàng đợi gửi có retry.

Chống lặp bằng khóa người dùng–mã–loại sự kiện–phiên–strategy_version; bán thêm position_id và order_id. Khởi động lại không gửi lại mọi cảnh báo cũ. /check vẫn được xem lại không phát lệnh mới. Lưu sự kiện đã gửi và giao dịch đã xác nhận bền vững, không chỉ giữ RAM.

Heartbeat/polling không phản hồi quá 120 giây trong giờ theo dõi → cảnh báo nguồn, không đồng nhất mã ít giao dịch với mất kết nối. Chỉ một tiến trình polling Telegram cho một token. Token đọc từ biến môi trường, không có giá trị thật dự phòng trong code; không ghi vào log. Thay token từng đưa lên GitHub nếu còn hiệu lực.

---
## 13 Backtest có thể đối chiếu

Backtest dùng chung indicator_engine, gate_engine, score_engine và position_engine với live; chỉ thay data clock và execution adapter. Tín hiệu chỉ dùng dữ liệu available_at ≤ decision_time. available_at là thời điểm hệ thống thực sự có dữ liệu; lịch sử chỉ có published_at đáng tin có thể mô phỏng độ trễ thu nhận được công bố rõ.

Lịch sử tài chính thiếu ngày công bố hoặc phiên bản cũ → không chạy như backtest đầy đủ. Cho phép TECHNICAL_ONLY, ghi “không kiểm định lọc cơ bản” ở tiêu đề và báo cáo. Không dùng BCTC hiện tại chọn mã trong quá khứ rồi gọi là kiểm định toàn chiến lược. Thành phần rổ và trạng thái mã cũng phải theo thời điểm; thiếu lịch sử danh mục thì ghi rõ thiên lệch sống sót.

Mô hình mua ngày với OHLC: từ EOD t xác định giá giới hạn L=C_t+0,5 ATR_t, lượng tính trước theo L. Chỉ mô phỏng khớp mở cửa t+1 nếu open≤L, đủ điều kiện giao dịch và được phép tham gia phiên mở cửa; khớp open với phí và trượt giá không vượt L. Nếu không đủ bằng chứng khớp hoặc open>L thì bỏ giao dịch trong mô hình này, không xem low trong ngày rồi tự mua. Đây là giả định kiểm định hạn chế, không hứa bot khớp được mọi lệnh giới hạn.

Lượng đã định trước không được tăng sau khi thấy open thấp hơn. Stop/target tính từ giá khớp thực. Xử lý sự kiện vị thế ngay từ phiên mua nhưng chỉ khớp bán sau available_to_sell theo execution_rules có hiệu lực. Nếu chưa xác minh thời gian thanh toán, tick, lot, phí hoặc thuế thì full backtest bị chặn, không mặc định bằng 0. Ví dụ test giả định phải ghi SYNTHETIC_EXECUTION.

Với OHLC ngày và lượng được phép bán: nếu open xuyên stop, lấy open trừ trượt giá bất lợi; nếu intraday chạm stop, lấy stop trừ trượt giá; nếu cả stop và target cùng chạm mà chưa biết thứ tự, giả định stop trước. Target khớp tại target chỉ khi có khả năng thực hiện; phiên hạn chế thanh khoản chuyển chờ. Lệnh thoát do EMA50 được tạo EOD và thực hiện lần hợp lệ sau đó. Stop mới chỉ áp từ phiên sau.

Sổ mô phỏng phải ghi từng lần bán một phần, phí, thuế, lượng còn lại và tiền. Lợi nhuận vị thế = tổng tiền bán ròng + giá trị phần còn lại − tổng tiền mua và phí; phân biệt đã thực hiện và chưa thực hiện. Không tính vị thế mở thành lệnh thắng đã đóng. Lợi nhuận danh mục dựa đường NAV, không cộng phần trăm của các mã. Profit Factor = tổng lãi ròng vị thế đóng / trị tuyệt đối tổng lỗ ròng; không có lỗ thì ghi không xác định hoặc vô hạn cùng số mẫu, không chia 0,001 để tạo số đẹp.

---
## 14 Kiểm định đóng góp và cổng nghiệm thu

Tải đủ ít nhất 420 phiên khởi động cộng 120 phiên đánh giá nếu báo cáo 120 phiên. Báo ngày bắt đầu/kết thúc, số phiên thực được đánh giá và số phiên bị loại. Với 323 nến, không được ghi kiểm định 120 phiên theo chuẩn v2; với 303 nến không đủ khởi động phải báo thiếu, không báo “không có cơ hội”.

So sánh ngoài mẫu theo thứ tự: gate kỹ thuật không điểm với phiên bản thêm điểm; bỏ từng nhóm điểm; S_V mới với cũ; ngưỡng 70/75/80; trọng số đều với 40/30/30; có và không giới hạn 3 ATR. Giữ nguyên vốn, bán, chi phí, danh mục và dữ liệu trong từng so sánh. Baseline khi nhiều mã: xếp thanh khoản rồi ticker. Có thể thêm bản EMA20/50 đơn giản để đánh giá phần phức tạp có đáng giữ không.

Khóa tham số trước giai đoạn kiểm tra. Không chọn ngưỡng trên chính 3–6 tháng dùng báo cáo rồi gọi đó là ngoài mẫu. Báo số giao dịch, lợi nhuận NAV sau phí, drawdown, turnover, thời gian nắm giữ, tỷ lệ thắng, lãi/lỗ trung bình và benchmark cùng kỳ. Kết quả ít giao dịch hoặc chỉ một trạng thái thị trường → chưa đủ bằng chứng. Điểm cao hơn chỉ được mô tả là hữu ích nếu dữ liệu ngoài mẫu hỗ trợ; không bảo đảm tương lai.

Các ca kiểm tra bắt buộc trước nghiệm thu:

| Mã test | Đầu vào hoặc sự kiện | Kết quả cần có |
| --- | --- | --- |
| D01 | report_period=2018-Q4, xét năm 2026 | Parse thành cuối quý, DATA_STALE |
| D02 | Ngày thiếu hoặc sai; dữ liệu NaN | Không PASSED, không chuyển thành 0 điểm |
| D03 | Cache đủ nến nhưng thiếu phiên mới | Tải cập nhật hoặc chặn mua do cũ |
| F01 | 5 quý thay vì 8 quý tăng trưởng | MISSING, không tự dùng YoY một quý |
| F02 | LNST TTM từ −40 xuống −80 | BASE_NONPOSITIVE, không tăng trưởng +100% đạt |
| F03 | Không có dòng CFO nhưng có lợi nhuận hoạt động | CFO thiếu, không thay thế |
| F04 | VCB với tổng nợ/VCSH cao | Chạy BANK, không dùng gate 1,5 |
| F05 | Thiếu CAR hoặc quy tắc vốn áp dụng | NOT_EVALUATED với lý do, không kết luận yếu |
| T01 | Giá giảm, gate khác đạt | Không BUY_CANDIDATE |
| T02 | Volume=200, 20 phiên trước đều 100 | VR=2, không gồm phiên hiện tại |
| T03 | Điểm gốc 74,96 | Không đạt ngưỡng 75 |
| T04 | X_T hoặc một phiên tham chiếu bị thiếu | score=null, DATA_MISSING |

---
## 15 Kiểm thử vốn và chức năng

| Mã test | Đầu vào hoặc sự kiện | Kết quả cần có |
| --- | --- | --- |
| R01 | Ví dụ đơn vị tại mục 10 | 100 cổ phiếu khi không phí, đúng lô giả định |
| R02 | Đã đủ 5 mã hoặc vượt ngân sách ngành | Không lập BUY_PLAN mới |
| R03 | Chốt 50% đã khớp | Ghi tiền và giảm lượng đúng, phần còn lại còn mở |
| R04 | Đã cập nhật stop mới tại EOD | Không áp lên low của chính phiên đó |
| R05 | Stop chạm khi chưa được bán | SELL_PENDING; không ghi tiền bán trước hạn |
| R06 | Target chạm lúc chưa được bán rồi giá giảm | Không giả lập bán target khi đủ điều kiện sau đó |
| R07 | Khởi động lại hoặc xác nhận trùng order_id | Không nhân đôi tiền, lượng hoặc cảnh báo |
| B01 | Open xuyên stop | Không khớp giả tại stop tốt hơn open |
| B02 | EMA50 bị thủng tại EOD | Thoát sau thời điểm xác nhận |
| B03 | Thiếu lịch sử công bố BCTC | Chỉ TECHNICAL_ONLY có nhãn rõ |
| U01 | Mã thiếu tài chính | Không gắn chung nhãn BCTC trượt |
| U02 | API danh sách lỗi, dùng 20 mã dự phòng | Tiêu đề ghi rổ dự phòng 20 mã |
| U03 | Người A sửa vị thế của B | Từ chối, không thay dữ liệu |
| U04 | Đăng ký alert rồi sự kiện thực xuất hiện | Scheduler gửi đúng một cảnh báo và ghi log |

Kiểm thử số học dùng fixture nhỏ có kết quả tự tính độc lập. Kiểm thử API dùng raw response đã lưu và ít mã mẫu để không tiêu hao hạn mức không cần thiết. Không gọi mọi test xanh là đã xác minh nguồn live. Mỗi profile cần fixture đạt, trượt, thiếu, sai đơn vị và quá cũ.

Demo nghiệm thu: /start → /check cho mã phi tài chính và ngân hàng → /signals với số mã thực → /filterstats → đăng ký và nhận alert qua sự kiện PAPER có nhãn mô phỏng → ghi nhận vị thế → đề xuất bán và xác nhận → restart kiểm tra dữ liệu còn nguyên → lỗi API có thông báo. Không dùng tín hiệu mô phỏng mang nhãn giá thị trường thật.

Cổng dữ liệu: đối chiếu ít nhất hai mã mỗi profile với báo cáo gốc, có ảnh/trích dẫn dòng và kỳ, không chỉ đối chiếu hai API dùng chung một nguồn. Cổng triển khai: người khác cài theo README được; requirements khóa phiên bản sau khi thử thành công; có .env.example không bí mật. Cổng tài chính: mọi quyết định truy được gate, metric, nguồn và thời điểm; không cần có mã BUY trong mọi lần demo.

Nếu còn profile DATA_PENDING, nghiệm thu phải ghi là chưa đủ phạm vi mục tiêu; không mô tả sản phẩm đã bao phủ đầy đủ ngành đó. Những hạn chế này không được giải quyết bằng bỏ tiêu chí âm thầm.

---
## 16 Bản đồ sửa mã nguồn cho AI

Giữ cấu trúc module hiện có khi phù hợp. Tách thêm phần cần thiết; không viết lại toàn bộ bot chỉ vì đổi chiến lược. Hàm tính phải độc lập Telegram, mạng và đồng hồ hệ thống để kiểm thử được.

| Module trong ZIP | Công việc bắt buộc |
| --- | --- |
| config.py | Phiên bản cấu hình, đơn vị, profile, quy tắc giao dịch theo thời gian; xóa token thật dự phòng |
| data_pipeline/fetcher.py | required_sessions, cập nhật phiên mới, TTL tài chính, retry lỗi, adapter ngành và nguồn quote trong phiên |
| data_pipeline/financial_loader.py | Mapping có phiên bản, parse quý, quý riêng/TTM, ngày, phạm vi báo cáo, schema validation |
| database/db_manager.py | Migration có backup; raw facts và revision; snapshots; sổ tiền, vị thế, orders, trạng thái alert |
| core_logic/fundamental_filter.py | Profile ngành; điều kiện chung; phân biệt FAILED/MISSING/STALE/REVIEW |
| core_logic/indicators.py | Wilder nhất quán, VR shift 1 phiên, validator OHLCV và điều chỉnh |
| core_logic/scoring.py | S_V mới; đúng cửa sổ; không chấm NaN; giữ điểm gốc |
| core_logic/strategy.py | Gate đầy đủ, chỉ EOD, scope/profile, lý do máy đọc và người đọc |
| core_logic/scanner.py | Phạm vi thực, snapshots có phiên bản, scheduler, freshness và chống quét trùng |
| risk_management | VND, giới hạn thực, phí và lượng; state machine bán, trailing và pending |
| backtesting | Dùng chung core; sổ tiền/lượng; dữ liệu đúng thời điểm và báo đúng phạm vi |
| bot và main.py | Nối scheduler, vị thế và alert; không chặn event loop; nội dung đúng khả năng thực |

Đầu ra evaluate_ticker phải gồm ticker, strategy_version, as_of, price_session, profile, data_status, fundamental_status, technical_status, action, scores_raw, scores_display, gates và reason_codes. Mỗi gate có observed, operator, threshold, result và source_fact_ids. reason_codes ổn định cho test; tiếng Việt là lớp trình bày.

AI phải rà code trước, phân biệt phần đã có với phần cần thêm. Không tự thay nguồn API nếu chưa thử adapter cũ. Chụp schema dữ liệu gốc trên vài mã, xác minh trường và quyền truy cập. Quy tắc pháp lý/khớp chưa được xác minh phải để cấu hình chưa sẵn sàng có báo cáo rõ; không tự điền số để chạy qua test.

Vì SQLite cũ thiếu metadata và có kỳ đáng nghi, dữ liệu đó chỉ dùng chẩn đoán, không tự chuyển thành facts đã kiểm chứng. Migration giữ lịch sử và cách ly bản ghi, tải lại theo adapter mới; chỉ mở mua sau cổng dữ liệu. Không xóa tiền/vị thế người dùng khi làm mới cache thị trường.

---
## 17 Chỉ dẫn bàn giao và nguồn tham khảo

Yêu cầu dành cho AI triển khai: đọc đặc tả này và mã nguồn ZIP hiện tại; lập danh sách sai khác; thực hiện sửa lần lượt dữ liệu → lọc cơ bản theo ngành → kỹ thuật → vốn và thoát → Telegram → backtest. Viết test các ca ở mục 14–15 và bổ sung khi có rủi ro cụ thể. Giữ bản gốc và migration có thể phục hồi. Không tự triển khai lên bot dùng chung hoặc ghi nhận giao dịch thực.

Bàn giao phải có mã nguồn đã sửa, requirements khóa phiên bản đã thử, .env.example, README chạy Windows/VS Code và hướng dẫn máy chủ nếu dùng, hướng dẫn lấy nguồn chuyên ngành, migration, test results và danh sách phần chưa xác minh. Báo rõ đã chạy test số học, API live hay chỉ fixture; không nói “hoàn thiện” nếu scheduler/nguồn/profile chưa đạt cổng nghiệm thu.

Chứng cứ bám đề: hoàn thiện 40% được thể hiện qua demo, cập nhật đúng và xử lý lỗi; sáng tạo/tài chính 30% qua phân ngành, điểm có giải thích và so sánh đóng góp; code 20% qua tách core, data, bot và test; báo cáo 10% qua sơ đồ dữ liệu, công thức và nhật ký sửa lỗi. Đây là cách thiết kế theo barem, không cam kết mức điểm giảng viên cho.

Các nguồn dưới đây hỗ trợ nguyên tắc, không chứng minh các ngưỡng của v2. Khi thay quy tắc pháp lý hoặc điều kiện nguồn, người triển khai phải tra văn bản và tài liệu chính thức áp dụng tại thời điểm chạy.

[S1] Vnstock — tài liệu chính thức của dự án kết nối dữ liệu. Dùng xác định API, phiên bản và điều kiện truy cập; không suy rằng mọi chỉ tiêu ngành có sẵn hoặc luôn cập nhật.
https://github.com/thinh-vu/vnstock

[S2] Basel Committee — Leverage ratio. Hỗ trợ việc dùng khung vốn chuyên biệt cho ngân hàng; tỷ lệ Basel không đồng nhất tổng nợ phải trả/VCSH của doanh nghiệp. Không dùng nguồn này thay quy định cụ thể tại Việt Nam.
https://www.bis.org/basel_framework/standard/LEV.htm

[S3] IAIS — Insurance Core Principles and ComFrame. Tham khảo nguyên tắc giám sát và an toàn vốn bảo hiểm; không chứng minh ngưỡng ROE 8% hay khoảng đệm 1,10 của nhóm.
https://www.iais.org/activities-topics/standard-setting/icps-and-comframe/

[S4] StockCharts — StockCharts Technical Rank. Ví dụ tổng hợp chỉ báo có trọng số và xếp hạng trong nhóm; khác chuẩn hóa theo lịch sử từng mã trong tài liệu này.
https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stockcharts-technical-rank-sctr

[S5] Moskowitz, Ooi và Pedersen — Time Series Momentum, 2012. Bằng chứng về momentum trên các hợp đồng tương lai/kỳ hạn và thời hạn được nghiên cứu; chưa xác nhận hiệu quả bộ EMA20/50 hằng ngày tại Việt Nam.
https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum

Trạng thái tài liệu: đặc tả v2.0 để sửa và kiểm chứng phần mềm. Chưa có backtest của công thức mới, chưa xác nhận đầy đủ nguồn chuyên ngành, và chưa thay đổi mã nguồn bot trong lần bàn giao tài liệu này.
