from vnstock import Vnstock

ticker = "PNJ"
stock = Vnstock().stock(symbol=ticker, source='VCI')
df_inc = stock.finance.income_statement(period='quarter', lang='vi')

print("=" * 60)
print("CÁC CỘT (theo ĐÚNG thứ tự vnstock trả về):")
print(list(df_inc.columns))
print("=" * 60)
print()
print("5 dòng đầu của bảng (để xem tên cột 'item' và vài giá trị):")
print(df_inc.head(5).to_string())
print()
print("=" * 60)
print("Các dòng có chứa chữ 'Doanh thu thuần':")
rev_row = df_inc[df_inc['item'].astype(str).str.contains('Doanh thu thuần', na=False)]
print(rev_row.to_string())
