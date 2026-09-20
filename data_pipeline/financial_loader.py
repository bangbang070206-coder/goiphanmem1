import re
import logging
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

def _sort_quarter_columns(cols):
    """Sắp xếp các cột quý theo thứ tự thời gian TĂNG DẦN (cũ -> mới) dựa trên năm và
    số quý trích xuất từ tên cột (vd: '2023-Q4', 'Q4-2023'...). Đây là bước sửa lỗi quan
    trọng: code cũ giả định cột cuối cùng luôn là quý mới nhất theo đúng thứ tự vnstock
    trả về, nhưng không đảm bảo chắc chắn. Nếu không trích xuất được năm+quý từ TOÀN BỘ
    cột, giữ nguyên thứ tự gốc và log cảnh báo thay vì đoán bừa."""
    def _key(col):
        s = str(col)
        year_match = re.search(r'(20\d{2})', s)
        q_match = re.search(r'Q\s*([1-4])', s, re.IGNORECASE)
        if year_match and q_match:
            return (int(year_match.group(1)), int(q_match.group(1)))
        return None

    keyed = [(_key(c), c) for c in cols]
    if all(k is not None for k, _ in keyed):
        return [c for _, c in sorted(keyed, key=lambda x: x[0])]
    logger.warning(f"[financial_loader] Không xác định được thứ tự thời gian của các cột {list(cols)}, giữ nguyên thứ tự gốc.")
    return list(cols)

def parse_financial_ratio(df_ratio: pd.DataFrame) -> Dict[str, Any]:
    """Trích xuất các chỉ số P/E, P/B, ROE, Nợ/VCSH từ bảng tỷ số tài chính vnstock"""
    res = {
        "roe": None,
        "debt_to_equity": None,
        "pe": None,
        "pb": None,
        "report_date": None
    }
    if df_ratio is None or df_ratio.empty:
        return res

    quarter_cols = _sort_quarter_columns([c for c in df_ratio.columns if '-' in str(c) or 'Q' in str(c)])
    if not quarter_cols:
        return res

    latest_col = quarter_cols[-1]
    res["report_date"] = str(latest_col)

    for _, row in df_ratio.iterrows():
        item_name = str(row.get('item', '')).strip()
        val = row.get(latest_col)
        try:
            val_float = float(val) if pd.notna(val) else None
        except Exception:
            val_float = None

        if val_float is None:
            continue

        if 'ROE' in item_name:
            res["roe"] = val_float / 100.0 if val_float > 1.0 else val_float
        elif 'Nợ/Vốn chủ' in item_name or 'Nợ trên vốn chủ' in item_name:
            res["debt_to_equity"] = val_float
        elif item_name == 'P/E':
            res["pe"] = val_float
        elif item_name == 'P/B':
            res["pb"] = val_float

    return res

def _sum_last_n_quarters(df: pd.DataFrame, item_pattern: str, sorted_cols: list, n: int, offset: int = 0) -> Optional[float]:
    """Cộng dồn giá trị của n quý, bỏ qua `offset` quý gần nhất (offset=0 -> n quý mới nhất,
    offset=4 -> 4 quý liền TRƯỚC đó, dùng để tính TTM kỳ trước cho việc so sánh tăng trưởng)."""
    row = df[df['item'].astype(str).str.contains(item_pattern, na=False, regex=True)]
    if row.empty:
        return None
    end = len(sorted_cols) - offset
    start = end - n
    if start < 0:
        return None
    window = sorted_cols[start:end]
    try:
        return sum(float(row.iloc[0][c]) for c in window)
    except Exception:
        return None

def parse_growth_and_cfo(df_inc: pd.DataFrame, df_cf: pd.DataFrame) -> Dict[str, Any]:
    """
    Tính tăng trưởng Doanh thu/LNST và dòng tiền CFO theo đúng định nghĩa TTM
    (Trailing Twelve Months = tổng 4 quý gần nhất) như mô tả trong config.py và
    Chiến lược số 1 - THAY VÌ so 2 quý liền kề (QoQ) như bản cũ, vốn cho kết quả
    sai lệch nặng vì tính mùa vụ (đây chính là nguyên nhân FPT/VNM bị báo tăng
    trưởng âm sai trong khi thực tế TTM vẫn dương).

    Thứ tự ưu tiên:
    1. Đủ >= 8 quý dữ liệu -> so TTM hiện tại (4 quý gần nhất) với TTM liền trước (4 quý trước đó).
    2. Đủ >= 5 quý -> fallback so cùng kỳ năm trước (quý mới nhất vs quý cùng kỳ năm ngoái).
    3. Không đủ dữ liệu -> trả về None (KHÔNG bịa số liệu mặc định như bản cũ).
       Nơi gọi (fundamental_filter.py) sẽ tự quyết định cách xử lý khi thiếu dữ liệu,
       thay vì âm thầm coi một con số giả định là dữ liệu thật.
    """
    res = {
        "rev_growth": None,
        "np_growth": None,
        "cfo": None,
        "eps": None,
    }

    rev_pattern = 'Doanh thu thuần'
    np_pattern = 'Lợi nhuận sau thuế của cổ đông|Lợi nhuận sau thuế'
    cfo_pattern = r'Lưu chuyển tiền thuần từ hoạt động kinh doanh|Lợi nhuận/\(lỗ\) từ hoạt động kinh doanh'

    try:
        if df_inc is not None and not df_inc.empty:
            q_cols = _sort_quarter_columns([c for c in df_inc.columns if '-' in str(c) or 'Q' in str(c)])

            if len(q_cols) >= 8:
                rev_now = _sum_last_n_quarters(df_inc, rev_pattern, q_cols, 4, offset=0)
                rev_prev = _sum_last_n_quarters(df_inc, rev_pattern, q_cols, 4, offset=4)
                if rev_now is not None and rev_prev not in (None, 0):
                    res["rev_growth"] = (rev_now - rev_prev) / rev_prev

                np_now = _sum_last_n_quarters(df_inc, np_pattern, q_cols, 4, offset=0)
                np_prev = _sum_last_n_quarters(df_inc, np_pattern, q_cols, 4, offset=4)
                if np_now is not None and np_prev not in (None, 0):
                    res["np_growth"] = (np_now - np_prev) / np_prev

            elif len(q_cols) >= 5:
                latest_col, yoy_col = q_cols[-1], q_cols[-5]

                rev_row = df_inc[df_inc['item'].astype(str).str.contains(rev_pattern, na=False)]
                if not rev_row.empty:
                    try:
                        rev_now = float(rev_row.iloc[0][latest_col])
                        rev_yoy = float(rev_row.iloc[0][yoy_col])
                        if rev_yoy != 0:
                            res["rev_growth"] = (rev_now - rev_yoy) / rev_yoy
                    except Exception:
                        pass

                np_row = df_inc[df_inc['item'].astype(str).str.contains(np_pattern, na=False)]
                if not np_row.empty:
                    try:
                        np_now = float(np_row.iloc[0][latest_col])
                        np_yoy = float(np_row.iloc[0][yoy_col])
                        if np_yoy != 0:
                            res["np_growth"] = (np_now - np_yoy) / np_yoy
                    except Exception:
                        pass
            # < 5 quý: không đủ tin cậy để tính tăng trưởng -> giữ None

        if df_cf is not None and not df_cf.empty:
            q_cols_cf = _sort_quarter_columns([c for c in df_cf.columns if '-' in str(c) or 'Q' in str(c)])
            if len(q_cols_cf) >= 4:
                cfo_ttm = _sum_last_n_quarters(df_cf, cfo_pattern, q_cols_cf, 4, offset=0)
                if cfo_ttm is not None:
                    res["cfo"] = cfo_ttm
            elif q_cols_cf:
                cfo_row = df_cf[df_cf['item'].astype(str).str.contains(cfo_pattern, na=False)]
                if not cfo_row.empty:
                    try:
                        res["cfo"] = float(cfo_row.iloc[0][q_cols_cf[-1]])
                    except Exception:
                        pass

    except Exception as e:
        logger.warning(f"Lỗi khi trích xuất KQKD và Dòng tiền: {e}")

    return res
