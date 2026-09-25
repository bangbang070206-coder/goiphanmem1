import re
import logging

from typing import Dict, Any, Optional

import pandas as pd


logger = logging.getLogger(__name__)


def _sort_quarter_columns(cols):
    """
    Sắp xếp các cột quý theo thứ tự thời gian tăng dần (cũ -> mới).

    Ví dụ:
        2024-Q4
        2025-Q1
        2025-Q2
        2026-Q1
        2026-Q2

    Không giả định cột cuối cùng vnstock trả về luôn là quý mới nhất.
    """

    def _key(col):
        s = str(col)

        year_match = re.search(r"(20\d{2})", s)
        q_match = re.search(r"Q\s*([1-4])", s, re.IGNORECASE)

        if year_match and q_match:
            return (
                int(year_match.group(1)),
                int(q_match.group(1)),
            )

        return None

    keyed = [(_key(c), c) for c in cols]

    if all(k is not None for k, _ in keyed):
        return [
            c
            for _, c in sorted(
                keyed,
                key=lambda x: x[0],
            )
        ]

    logger.warning(
        "[financial_loader] Không xác định được thứ tự thời gian "
        "của các cột %s, giữ nguyên thứ tự gốc.",
        list(cols),
    )

    return list(cols)


def parse_financial_ratio(df_ratio: pd.DataFrame) -> Dict[str, Any]:
    """
    Parser tương thích với bảng ratio cũ của vnstock.

    LƯU Ý:
    Không nên dùng hàm này để lấy ROE/Debt-to-Equity cho chiến lược
    hiện tại vì vnstock 2.6.0 có thể trả bảng ratio rất cũ
    (ví dụ HPG chỉ có 2018).

    Giữ lại hàm để tương thích với code cũ và các trường P/E, P/B
    nếu nguồn dữ liệu phù hợp trong tương lai.
    """

    res = {
        "roe": None,
        "debt_to_equity": None,
        "pe": None,
        "pb": None,
        "report_date": None,
    }

    if df_ratio is None or df_ratio.empty:
        return res

    quarter_cols = _sort_quarter_columns(
        [
            c
            for c in df_ratio.columns
            if "-" in str(c) or "Q" in str(c)
        ]
    )

    if not quarter_cols:
        return res

    latest_col = quarter_cols[-1]
    res["report_date"] = str(latest_col)

    for _, row in df_ratio.iterrows():
        item_name = str(row.get("item", "")).strip()
        val = row.get(latest_col)

        try:
            val_float = (
                float(val)
                if pd.notna(val)
                else None
            )
        except Exception:
            val_float = None

        if val_float is None:
            continue

        if "ROE" in item_name:
            res["roe"] = (
                val_float / 100.0
                if val_float > 1.0
                else val_float
            )

        elif (
            "Nợ/Vốn chủ" in item_name
            or "Nợ trên vốn chủ" in item_name
        ):
            res["debt_to_equity"] = val_float

        elif item_name == "P/E":
            res["pe"] = val_float

        elif item_name == "P/B":
            res["pb"] = val_float

    return res


def _find_matching_row(
    df: pd.DataFrame,
    patterns: list,
):
    """
    Thử từng pattern theo thứ tự ưu tiên.

    Pattern đầu tiên khớp sẽ được sử dụng.
    """

    if df is None or df.empty or "item" not in df.columns:
        return None

    for pat in patterns:
        row = df[
            df["item"]
            .astype(str)
            .str.contains(
                pat,
                na=False,
                regex=True,
            )
        ]

        if not row.empty:
            return row.iloc[0]

    return None


def _sum_last_n_quarters(
    df: pd.DataFrame,
    patterns: list,
    sorted_cols: list,
    n: int,
    offset: int = 0,
) -> Optional[float]:
    """
    Cộng dồn n quý.

    offset=0:
        n quý mới nhất.

    offset=4:
        4 quý liền trước đó.
    """

    row = _find_matching_row(
        df,
        patterns,
    )

    if row is None:
        return None

    end = len(sorted_cols) - offset
    start = end - n

    if start < 0:
        return None

    window = sorted_cols[start:end]

    values = []

    try:
        for col in window:
            value = row.get(col)

            if pd.isna(value):
                return None

            values.append(float(value))

        return sum(values)

    except Exception:
        return None


def parse_growth_and_cfo(
    df_inc: pd.DataFrame,
    df_cf: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Tính:

    - Tăng trưởng doanh thu TTM
    - Tăng trưởng LNST TTM
    - CFO TTM

    Ưu tiên:
    1. >= 8 quý:
       TTM hiện tại so với TTM 4 quý trước.
    2. >= 5 quý:
       quý mới nhất so với cùng kỳ năm trước.
    3. < 5 quý:
       không đủ dữ liệu -> None.

    LNST ưu tiên:
        Lợi nhuận của Cổ đông của Công ty mẹ

    Fallback:
        Lãi/(lỗ) thuần sau thuế
    """

    res = {
        "rev_growth": None,
        "np_growth": None,
        "cfo": None,
        "eps": None,
    }

    rev_patterns = [
        r"Doanh thu thuần",
    ]

    np_patterns = [
        r"Lợi nhuận của Cổ đông của Công ty mẹ",
        r"Lãi/\(lỗ\) thuần sau thuế",
    ]

    cfo_patterns = [
        r"Lưu chuyển tiền thuần từ hoạt động kinh doanh",
        r"Lợi nhuận/\(lỗ\) từ hoạt động kinh doanh",
    ]

    try:

        # ==================================================
        # INCOME STATEMENT
        # ==================================================

        if df_inc is not None and not df_inc.empty:

            q_cols = _sort_quarter_columns(
                [
                    c
                    for c in df_inc.columns
                    if "-" in str(c) or "Q" in str(c)
                ]
            )

            if len(q_cols) >= 8:

                # ------------------------------
                # Doanh thu TTM
                # ------------------------------

                rev_now = _sum_last_n_quarters(
                    df_inc,
                    rev_patterns,
                    q_cols,
                    4,
                    offset=0,
                )

                rev_prev = _sum_last_n_quarters(
                    df_inc,
                    rev_patterns,
                    q_cols,
                    4,
                    offset=4,
                )

                if (
                    rev_now is not None
                    and rev_prev is not None
                    and rev_prev != 0
                ):
                    res["rev_growth"] = (
                        (rev_now - rev_prev)
                        / abs(rev_prev)
                    )

                # ------------------------------
                # LNST TTM
                # ------------------------------

                np_now = _sum_last_n_quarters(
                    df_inc,
                    np_patterns,
                    q_cols,
                    4,
                    offset=0,
                )

                np_prev = _sum_last_n_quarters(
                    df_inc,
                    np_patterns,
                    q_cols,
                    4,
                    offset=4,
                )

                if (
                    np_now is not None
                    and np_prev is not None
                    and np_prev != 0
                ):
                    res["np_growth"] = (
                        (np_now - np_prev)
                        / abs(np_prev)
                    )

            elif len(q_cols) >= 5:

                latest_col = q_cols[-1]
                yoy_col = q_cols[-5]

                # ------------------------------
                # Doanh thu YoY
                # ------------------------------

                rev_row = _find_matching_row(
                    df_inc,
                    rev_patterns,
                )

                if rev_row is not None:
                    try:
                        rev_now = float(
                            rev_row[latest_col]
                        )

                        rev_yoy = float(
                            rev_row[yoy_col]
                        )

                        if rev_yoy != 0:
                            res["rev_growth"] = (
                                (rev_now - rev_yoy)
                                / abs(rev_yoy)
                            )

                    except Exception:
                        pass

                # ------------------------------
                # LNST YoY
                # ------------------------------

                np_row = _find_matching_row(
                    df_inc,
                    np_patterns,
                )

                if np_row is not None:
                    try:
                        np_now = float(
                            np_row[latest_col]
                        )

                        np_yoy = float(
                            np_row[yoy_col]
                        )

                        if np_yoy != 0:
                            res["np_growth"] = (
                                (np_now - np_yoy)
                                / abs(np_yoy)
                            )

                    except Exception:
                        pass

        # ==================================================
        # CASH FLOW
        # ==================================================

        if df_cf is not None and not df_cf.empty:

            q_cols_cf = _sort_quarter_columns(
                [
                    c
                    for c in df_cf.columns
                    if "-" in str(c) or "Q" in str(c)
                ]
            )

            if len(q_cols_cf) >= 4:

                cfo_ttm = _sum_last_n_quarters(
                    df_cf,
                    cfo_patterns,
                    q_cols_cf,
                    4,
                    offset=0,
                )

                if cfo_ttm is not None:
                    res["cfo"] = cfo_ttm

            elif q_cols_cf:

                cfo_row = _find_matching_row(
                    df_cf,
                    cfo_patterns,
                )

                if cfo_row is not None:
                    try:
                        res["cfo"] = float(
                            cfo_row[q_cols_cf[-1]]
                        )
                    except Exception:
                        pass

    except Exception as e:
        logger.warning(
            "Lỗi khi trích xuất KQKD và Dòng tiền: %s",
            e,
        )

    return res


def parse_current_balance_sheet(
    df_bs: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Lấy dữ liệu Balance Sheet hiện tại.

    Dùng để thay thế ROE/Debt-to-Equity từ ratio().

    vnstock 2.6.0:
        ratio() của HPG có thể chỉ trả dữ liệu tới 2018,
        trong khi balance_sheet() có dữ liệu tới 2026-Q2.

    Kết quả:
        - debt_to_equity
        - report_date
        - equity_latest
        - equity_previous
    """

    result = {
        "debt_to_equity": None,
        "report_date": None,
        "equity_latest": None,
        "equity_previous": None,
    }

    if df_bs is None or df_bs.empty:
        return result

    if "item" not in df_bs.columns:
        return result

    quarter_cols = _sort_quarter_columns(
        [
            c
            for c in df_bs.columns
            if "-" in str(c) or "Q" in str(c)
        ]
    )

    if len(quarter_cols) < 2:
        return result

    latest_col = quarter_cols[-1]
    previous_col = quarter_cols[-2]

    result["report_date"] = str(latest_col)

    def get_value(
        item_name: str,
        column: str,
    ):
        rows = df_bs[
            df_bs["item"]
            .astype(str)
            .str.strip()
            == item_name
        ]

        if rows.empty:
            return None

        value = rows.iloc[0].get(column)

        try:
            return (
                float(value)
                if pd.notna(value)
                else None
            )
        except (TypeError, ValueError):
            return None

    liabilities = get_value(
        "NỢ PHẢI TRẢ",
        latest_col,
    )

    equity_latest = get_value(
        "Vốn chủ sở hữu",
        latest_col,
    )

    equity_previous = get_value(
        "Vốn chủ sở hữu",
        previous_col,
    )

    result["equity_latest"] = equity_latest
    result["equity_previous"] = equity_previous

    if (
        liabilities is not None
        and equity_latest is not None
        and equity_latest != 0
    ):
        result["debt_to_equity"] = (
            liabilities / equity_latest
        )

    return result


def calculate_roe_from_statements(
    df_inc: pd.DataFrame,
    df_bs: pd.DataFrame,
) -> Optional[float]:
    """
    Tính ROE TTM từ BCTC hiện tại.

    Công thức:

        ROE TTM =
            LNST thuộc cổ đông công ty mẹ 4 quý gần nhất
            /
            Vốn chủ sở hữu bình quân đầu và cuối kỳ

    Không sử dụng ratio().
    """

    if (
        df_inc is None
        or df_inc.empty
        or df_bs is None
        or df_bs.empty
    ):
        return None

    if (
        "item" not in df_inc.columns
        or "item" not in df_bs.columns
    ):
        return None

    # ==================================================
    # Xác định 4 quý gần nhất của Income Statement
    # ==================================================

    inc_cols = _sort_quarter_columns(
        [
            c
            for c in df_inc.columns
            if "-" in str(c) or "Q" in str(c)
        ]
    )

    if len(inc_cols) < 4:
        return None

    latest_4 = inc_cols[-4:]

    # ==================================================
    # LNST thuộc cổ đông công ty mẹ
    # ==================================================

    np_patterns = [
        r"Lợi nhuận của Cổ đông của Công ty mẹ",
        r"Lãi/\(lỗ\) thuần sau thuế",
    ]

    np_row = _find_matching_row(
        df_inc,
        np_patterns,
    )

    if np_row is None:
        return None

    np_values = []

    try:
        for col in latest_4:
            value = np_row.get(col)

            if pd.isna(value):
                return None

            np_values.append(float(value))

        np_ttm = sum(np_values)

    except (TypeError, ValueError):
        return None

    # ==================================================
    # Vốn chủ sở hữu đầu/cuối kỳ
    # ==================================================

    bs_cols = _sort_quarter_columns(
        [
            c
            for c in df_bs.columns
            if "-" in str(c) or "Q" in str(c)
        ]
    )

    if len(bs_cols) < 2:
        return None

    latest_col = bs_cols[-1]
    previous_col = bs_cols[-2]

    equity_rows = df_bs[
        df_bs["item"]
        .astype(str)
        .str.strip()
        == "Vốn chủ sở hữu"
    ]

    if equity_rows.empty:
        return None

    equity_row = equity_rows.iloc[0]

    try:
        equity_latest = float(
            equity_row[latest_col]
        )

        equity_previous = float(
            equity_row[previous_col]
        )

    except (TypeError, ValueError):
        return None

    if (
        equity_latest <= 0
        or equity_previous <= 0
    ):
        return None

    average_equity = (
        equity_previous + equity_latest
    ) / 2.0

    if average_equity <= 0:
        return None

    roe = np_ttm / average_equity

    return float(roe)
def _find_matching_row(df, patterns):
    """
    Tìm dòng trong DataFrame dựa trên danh sách regex pattern.
    Trả về Series hoặc None.
    """
    if df is None or df.empty or "item" not in df.columns:
        return None

    import re

    items = df["item"].astype(str).str.strip()

    for pattern in patterns:
        mask = items.str.contains(pattern, case=False, regex=True, na=False)
        if mask.any():
            return df.loc[mask].iloc[0]

    return None


def _sort_quarter_columns(columns):
    """
    Sắp xếp các cột dạng YYYY-QN theo thứ tự thời gian.
    Ví dụ:
    2025-Q4, 2026-Q1, 2026-Q2
    """
    import re

    quarter_cols = []

    for col in columns:
        col_str = str(col).strip()
        match = re.fullmatch(r"(\d{4})-Q([1-4])", col_str)

        if match:
            year = int(match.group(1))
            quarter = int(match.group(2))
            quarter_cols.append((year, quarter, col))

    quarter_cols.sort(key=lambda x: (x[0], x[1]))

    return [item[2] for item in quarter_cols]


def parse_current_balance_sheet(df_bs):
    """
    Lấy các chỉ tiêu hiện tại từ bảng cân đối kế toán.

    Dùng:
    - Nợ phải trả
    - Vốn chủ sở hữu
    - D/E = Nợ phải trả / Vốn chủ sở hữu
    """
    result = {
        "debt_to_equity": None,
        "report_date": None,
        "equity_latest": None,
        "equity_previous": None,
    }

    if df_bs is None or df_bs.empty:
        return result

    quarter_cols = _sort_quarter_columns(df_bs.columns)

    if len(quarter_cols) < 1:
        return result

    latest_col = quarter_cols[-1]
    previous_col = quarter_cols[-2] if len(quarter_cols) >= 2 else None

    result["report_date"] = str(latest_col)

    def get_value(patterns, column):
        row = _find_matching_row(df_bs, patterns)

        if row is None or column not in row.index:
            return None

        try:
            value = float(row[column])

            if value != value:  # NaN
                return None

            return value
        except (TypeError, ValueError):
            return None

    liabilities = get_value(
        [
            r"^NỢ PHẢI TRẢ$",
            r"^Nợ phải trả$",
        ],
        latest_col,
    )

    equity_latest = get_value(
        [
            r"^Vốn chủ sở hữu$",
            r"^VỐN CHỦ SỞ HỮU$",
        ],
        latest_col,
    )

    equity_previous = None

    if previous_col:
        equity_previous = get_value(
            [
                r"^Vốn chủ sở hữu$",
                r"^VỐN CHỦ SỞ HỮU$",
            ],
            previous_col,
        )

    result["equity_latest"] = equity_latest
    result["equity_previous"] = equity_previous

    if (
        liabilities is not None
        and equity_latest is not None
        and equity_latest != 0
    ):
        result["debt_to_equity"] = liabilities / equity_latest

    return result


def calculate_roe_from_statements(df_inc, df_bs):
    """
    Tính ROE hiện tại từ báo cáo tài chính.

    Công thức:
        ROE = LNST của cổ đông công ty mẹ 4 quý gần nhất
              / Bình quân vốn chủ sở hữu đầu kỳ và cuối kỳ
    """

    if df_inc is None or df_inc.empty:
        return None

    if df_bs is None or df_bs.empty:
        return None

    # -------------------------
    # 1. Lấy 4 quý gần nhất
    # -------------------------
    inc_cols = _sort_quarter_columns(df_inc.columns)

    if len(inc_cols) < 4:
        return None

    latest_4 = inc_cols[-4:]

    # -------------------------
    # 2. Tìm dòng LNST
    # -------------------------
    np_patterns = [
        r"Lợi nhuận của Cổ đông của Công ty mẹ",
        r"Lợi nhuận của cổ đông của công ty mẹ",
        r"Lãi/\(lỗ\) thuần sau thuế",
        r"Lãi/lỗ thuần sau thuế",
    ]

    np_row = _find_matching_row(df_inc, np_patterns)

    if np_row is None:
        return None

    # -------------------------
    # 3. Tính LNST TTM
    # -------------------------
    np_ttm = 0.0
    valid_quarters = 0

    for col in latest_4:
        try:
            value = float(np_row[col])

            if value == value:  # không phải NaN
                np_ttm += value
                valid_quarters += 1

        except (TypeError, ValueError):
            continue

    if valid_quarters < 4:
        return None

    # -------------------------
    # 4. Lấy vốn chủ sở hữu
    # -------------------------
    bs_cols = _sort_quarter_columns(df_bs.columns)

    if len(bs_cols) < 2:
        return None

    latest_col = bs_cols[-1]
    previous_col = bs_cols[-2]

    equity_row = _find_matching_row(
        df_bs,
        [
            r"^Vốn chủ sở hữu$",
            r"^VỐN CHỦ SỞ HỮU$",
        ],
    )

    if equity_row is None:
        return None

    try:
        equity_latest = float(equity_row[latest_col])
        equity_previous = float(equity_row[previous_col])
    except (TypeError, ValueError, KeyError):
        return None

    if equity_latest != equity_latest or equity_previous != equity_previous:
        return None

    average_equity = (equity_latest + equity_previous) / 2.0

    if average_equity == 0:
        return None

    roe = np_ttm / average_equity

    return float(roe)