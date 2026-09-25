import sqlite3
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo cấu trúc các bảng trong SQLite"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Bảng lưu nến giá lịch sử (OHLCV)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        value REAL,
        PRIMARY KEY (ticker, date)
    )
    """)
    
    # 2. Bảng lưu dữ liệu BCTC và các chỉ số tài chính TTM đã qua xử lý
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financial_metrics (
        ticker TEXT PRIMARY KEY,
        report_date TEXT,
        roe REAL,
        debt_to_equity REAL,
        rev_growth REAL,
        np_growth REAL,
        cfo REAL,
        eps REAL,
        pe REAL,
        pb REAL,
        is_passed INTEGER,
        status TEXT,
        updated_at TEXT
    )
    """)
    
    # 3. Bảng danh mục và vốn của từng User Telegram
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_portfolio (
        user_id INTEGER PRIMARY KEY,
        nav REAL DEFAULT 100000000,
        cash REAL DEFAULT 100000000,
        updated_at TEXT
    )
    """)
    
    # 4. Bảng vị thế nắm giữ của User
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        entry_price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        entry_date TEXT NOT NULL,
        atr0 REAL NOT NULL,
        stop_loss REAL NOT NULL,
        target_price REAL NOT NULL,
        is_partial_sold INTEGER DEFAULT 0,
        status TEXT DEFAULT 'OPEN',
        updated_at TEXT
    )
    """)
    
    # 5. Bảng đăng ký cảnh báo (Alerts)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_alerts (
        user_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        created_at TEXT,
        PRIMARY KEY (user_id, ticker)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS industry_classification (
        ticker TEXT PRIMARY KEY,
        industry_code TEXT NOT NULL,
        industry_name TEXT,
        icb_code TEXT,
        icb_level INTEGER,
        source TEXT,
        source_version TEXT,
        fetched_at TEXT,
        verified_status TEXT DEFAULT 'SOURCE_REPORTED'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS industry_metrics (
        ticker TEXT NOT NULL,
        metric_code TEXT NOT NULL,
        value REAL,
        unit TEXT,
        period_end TEXT,
        source TEXT,
        status TEXT,
        fetched_at TEXT,
        PRIMARY KEY (ticker, metric_code, period_end)
    )
    """)
    
    conn.commit()
    conn.close()

# Các hàm thao tác dữ liệu giá
def save_price_history(ticker: str, df: pd.DataFrame):
    if df is None or df.empty:
        return
    conn = get_connection()
    cursor = conn.cursor()
    for _, row in df.iterrows():
        date_str = str(row['date'])[:10]
        cursor.execute("""
        INSERT OR REPLACE INTO price_history (ticker, date, open, high, low, close, volume, value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker, date_str,
            float(row['open']), float(row['high']),
            float(row['low']), float(row['close']),
            float(row['volume']), float(row.get('value', row['close'] * row['volume']))
        ))
    conn.commit()
    conn.close()

def get_price_history(ticker: str, limit: int = 500) -> pd.DataFrame:
    conn = get_connection()
    query = """
    SELECT date, open, high, low, close, volume, value 
    FROM price_history 
    WHERE ticker = ? 
    ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(ticker,))
    conn.close()
    if not df.empty and limit and len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df

# Các hàm thao tác BCTC
def save_financial_metrics(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO financial_metrics (
        ticker, report_date, roe, debt_to_equity, rev_growth, np_growth, 
        cfo, eps, pe, pb, is_passed, status, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['ticker'], data.get('report_date'),
        data.get('roe'), data.get('debt_to_equity'),
        data.get('rev_growth'), data.get('np_growth'),
        data.get('cfo'), data.get('eps'),
        data.get('pe'), data.get('pb'),
        1 if data.get('is_passed') else 0,
        data.get('status', 'OK'),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def get_financial_metrics(ticker: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM financial_metrics WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_industry_classifications(rows: List[dict]):
    conn = get_connection()
    cursor = conn.cursor()
    for row in rows:
        cursor.execute("""
        INSERT OR REPLACE INTO industry_classification (
            ticker, industry_code, industry_name, icb_code, icb_level,
            source, source_version, fetched_at, verified_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["ticker"], row.get("industry_code", "generic"), row.get("industry_name"),
            row.get("icb_code"), row.get("icb_level"), row.get("source"),
            row.get("source_version"), row.get("fetched_at"), row.get("verified_status", "SOURCE_REPORTED")
        ))
    conn.commit()
    conn.close()


def get_industry_classifications(industry_code: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    query = "SELECT * FROM industry_classification"
    params = ()
    if industry_code:
        query += " WHERE industry_code = ?"
        params = (industry_code,)
    query += " ORDER BY ticker"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_industry_classification(ticker: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM industry_classification WHERE ticker = ?",
        (ticker.upper(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None

# Thao tác User Alerts
def add_user_alert(user_id: int, ticker: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO user_alerts (user_id, ticker, created_at)
    VALUES (?, ?, ?)
    """, (user_id, ticker.upper(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def remove_user_alert(user_id: int, ticker: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_alerts WHERE user_id = ? AND ticker = ?", (user_id, ticker.upper()))
    conn.commit()
    conn.close()

def get_user_alerts(user_id: int) -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM user_alerts WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r['ticker'] for r in rows]

# Khởi tạo DB ngay khi import
init_db()
