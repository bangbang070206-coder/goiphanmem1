from vnstock import Vnstock

ticker = "PNJ"
stock = Vnstock().stock(symbol=ticker, source='VCI')
df_inc = stock.finance.income_statement(period='quarter', lang='vi')

print("=" * 70)
print(f"TOÀN BỘ TÊN DÒNG (cột 'item') trong bảng KQKD của {ticker}:")
print("=" * 70)
for idx, name in enumerate(df_inc['item'].astype(str).tolist()):
    print(f"[{idx}] {name}")

print()
print("=" * 70)
print("Các dòng có chứa chữ 'Lợi nhuận sau thuế' (không phân biệt gì thêm):")
print("=" * 70)
profit_rows = df_inc[df_inc['item'].astype(str).str.contains('Lợi nhuận sau thuế', na=False)]
print(profit_rows.to_string())

print()
print("=" * 70)
print("Số cột dạng quý (để kiểm tra đủ >= 8 quý hay không):")
print("=" * 70)
q_cols = [c for c in df_inc.columns if '-' in str(c) or 'Q' in str(c)]
print(f"Số cột quý tìm được: {len(q_cols)}")
print(f"Danh sách: {q_cols}")
