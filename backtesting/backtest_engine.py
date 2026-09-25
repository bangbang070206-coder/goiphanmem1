import pandas as pd
import numpy as np
from typing import List, Dict, Any

from core_logic.indicators import calculate_indicators
from config import (
    STOP_ATR_MULTIPLE,
    TARGET_ATR_MULTIPLE,
    MIN_AVG_VALUE_20D,
    TECHNICAL_BUY_THRESHOLD,
    TA_SCORE_BUY_THRESHOLD,
)

def _safe_float(value, default=0.0):
    """
    Chuyển giá trị về float an toàn.
    """
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _calculate_technical_score(row, previous_close=None):
    """
    Tính technical score theo Strategy 3.0.

    Tổng tối đa 65 điểm:

    - Close > EMA20 > EMA50: 20 điểm
    - RSI14 > 50: 15 điểm
    - Volume >= Volume trung bình 20 phiên: 15 điểm
    - Khoảng cách Close - EMA20 <= 3 ATR: 10 điểm
    - Up day: 5 điểm
    """

    close = _safe_float(row.get("close"))
    ema20 = _safe_float(row.get("ema20"))
    ema50 = _safe_float(row.get("ema50"))
    rsi14 = _safe_float(row.get("rsi14"))
    atr14 = _safe_float(row.get("atr14"))
    volume = _safe_float(row.get("volume"))

    # -----------------------------------------
    # Volume trung bình 20 phiên
    # -----------------------------------------

    avg_volume_20 = _safe_float(
        row.get("avg_volume_20")
    )

    score = 0

    # 1. Trend
    trend_pass = (
        close > ema20
        and ema20 > ema50
    )

    if trend_pass:
        score += 20

    # 2. RSI
    rsi_pass = rsi14 > 50

    if rsi_pass:
        score += 15

    # 3. Volume
    volume_pass = (
        avg_volume_20 > 0
        and volume >= avg_volume_20
    )

    if volume_pass:
        score += 15

    # 4. Distance to EMA20
    distance_atr = None

    if atr14 > 0:
        distance_atr = (
            abs(close - ema20) / atr14
        )

    distance_pass = (
        distance_atr is not None
        and distance_atr <= 3.0
    )

    if distance_pass:
        score += 10

    # 5. Up day
    up_day = (
        previous_close is not None
        and close > previous_close
    )

    if up_day:
        score += 5

    # -----------------------------------------
    # Technical confirmation
    # Strategy 3.0:
    # Trend OR RSI OR Distance
    # -----------------------------------------

    technical_confirmation = (
        trend_pass
        or rsi_pass
        or distance_pass
    )

    return {
        "technical_score": score,
        "trend_pass": trend_pass,
        "rsi_pass": rsi_pass,
        "volume_pass": volume_pass,
        "distance_pass": distance_pass,
        "up_day": up_day,
        "technical_confirmation": technical_confirmation,
        "distance_atr": distance_atr,
        "atr14": atr14,
    }


def run_backtest_single_stock(
    ticker: str,
    df: pd.DataFrame,
    lookback_days: int = 120,
    is_fundamental_passed: bool = True,
) -> Dict[str, Any]:
    """
    Backtest Strategy 3.0 cho 1 mã.

    Logic:

    1. Tại phiên t:
       - Kiểm tra tín hiệu mua.
       - Không mua ngay.

    2. Nếu tín hiệu đạt:
       - Mua tại giá Open của phiên t+1.

    3. Sau khi mua:
       - Stop Loss = Entry - 2*ATR
       - Target = Entry + 3*ATR
       - Nếu thủng EMA50 -> thoát.
       - Nếu chạm Target -> dời Stop Loss về hòa vốn.

    Strategy 3.0 không yêu cầu tất cả chỉ báo kỹ thuật phải PASS.
    """

    # -----------------------------------------
    # Kiểm tra dữ liệu
    # -----------------------------------------

    if df is None or df.empty:
        return {
            "ticker": ticker,
            "trades": [],
            "summary": {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
            },
        }

    # Cần đủ dữ liệu để tính EMA/ATR và vùng lịch sử.
    if len(df) < 100:
        return {
            "ticker": ticker,
            "trades": [],
            "summary": {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
            },
        }

    # -----------------------------------------
    # Tính indicators
    # -----------------------------------------

    df_ind = calculate_indicators(df).copy()

    if df_ind.empty:
        return {
            "ticker": ticker,
            "trades": [],
            "summary": {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
            },
        }

    # -----------------------------------------
    # Chuẩn hóa volume trung bình 20 phiên
    # -----------------------------------------

    if "avg_volume_20" not in df_ind.columns:
        df_ind["avg_volume_20"] = (
            df_ind["volume"]
            .rolling(20)
            .mean()
        )

    # -----------------------------------------
    # Xác định vùng backtest
    # -----------------------------------------

    start_idx = max(
        60,
        len(df_ind) - lookback_days
    )

    trades = []

    in_position = False

    entry_price = 0.0
    entry_idx = 0

    stop_loss = 0.0
    target_price = 0.0

    is_partial = False

    # -----------------------------------------
    # BACKTEST LOOP
    # -----------------------------------------

    for i in range(
        start_idx,
        len(df_ind) - 1
    ):

        curr_row = df_ind.iloc[i]
        next_row = df_ind.iloc[i + 1]

        # =================================================
        # 1. ĐANG CÓ VỊ THẾ
        # =================================================

        if in_position:

            high_next = _safe_float(
                next_row.get("high")
            )

            low_next = _safe_float(
                next_row.get("low")
            )

            close_next = _safe_float(
                next_row.get("close")
            )

            ema50_next = _safe_float(
                next_row.get("ema50")
            )

            date_next = str(
                next_row.get("date", "")
            )[:10]

            # -----------------------------------------
            # STOP LOSS
            # -----------------------------------------

            if low_next <= stop_loss:

                exit_price = min(
                    stop_loss,
                    _safe_float(
                        next_row.get("open"),
                        stop_loss
                    )
                )

                ret = (
                    (exit_price - entry_price)
                    / entry_price
                )

                trades.append({
                    "type": "STOP_LOSS",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": ret * 100,
                    "holding_days": (
                        i + 1 - entry_idx
                    ),
                    "date": date_next,
                })

                in_position = False
                continue

            # -----------------------------------------
            # EMA50 EXIT
            # -----------------------------------------

            if (
                pd.notna(ema50_next)
                and close_next < ema50_next
            ):

                exit_price = close_next

                ret = (
                    (exit_price - entry_price)
                    / entry_price
                )

                trades.append({
                    "type": "EXIT_EMA50",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": ret * 100,
                    "holding_days": (
                        i + 1 - entry_idx
                    ),
                    "date": date_next,
                })

                in_position = False
                continue

            # -----------------------------------------
            # TARGET
            # -----------------------------------------

            if (
                high_next >= target_price
                and not is_partial
            ):

                is_partial = True

                # Dời stop về hòa vốn
                stop_loss = max(
                    stop_loss,
                    entry_price
                )

            continue

        # =================================================
        # 2. CHƯA CÓ VỊ THẾ -> TÌM TÍN HIỆU MUA
        # =================================================

        if not is_fundamental_passed:
            continue

        # -----------------------------------------
        # Lấy dữ liệu phiên hiện tại
        # -----------------------------------------

        close = _safe_float(
            curr_row.get("close")
        )

        ema20 = _safe_float(
            curr_row.get("ema20")
        )

        ema50 = _safe_float(
            curr_row.get("ema50")
        )

        rsi14 = _safe_float(
            curr_row.get("rsi14")
        )

        atr14 = _safe_float(
            curr_row.get("atr14")
        )

        volume = _safe_float(
            curr_row.get("volume")
        )

        avg_volume_20 = _safe_float(
            curr_row.get("avg_volume_20")
        )

        # Nếu thiếu dữ liệu quan trọng thì bỏ qua
        if (
            close <= 0
            or ema20 <= 0
            or ema50 <= 0
            or atr14 <= 0
        ):
            continue

        # -----------------------------------------
        # Technical score Strategy 3.0
        # -----------------------------------------

        previous_close = None

        if i > 0:
            previous_close = _safe_float(
                df_ind.iloc[i - 1].get("close")
            )

        technical = _calculate_technical_score(
            curr_row,
            previous_close
        )

        technical_score = technical[
            "technical_score"
        ]

        technical_confirmation = technical[
            "technical_confirmation"
        ]

        # -----------------------------------------
        # Liquidity
        # -----------------------------------------

        traded_value = None

        if "traded_value_vnd" in df_ind.columns:
            traded_value = (
                df_ind["traded_value_vnd"]
            )

        else:
            traded_value = (
                df_ind["close"]
                * df_ind["volume"]
            )

        if i < 20:
            continue

        avg_value_20 = _safe_float(
            traded_value.iloc[
                i - 20:i
            ].mean()
        )

        liquidity_pass = (
            avg_value_20
            >= MIN_AVG_VALUE_20D
        )

        # -----------------------------------------
        # Overall score
        #
        # Backtest không có BCTC lịch sử.
        # Vì performance_report truyền
        # is_fundamental_passed=True,
        # ta dùng fundamental score giả định
        # = 35/35.
        #
        # Overall:
        # BCTC 40% + Technical 60%
        # -----------------------------------------

        fundamental_score = 35.0
        fundamental_max = 35.0

        overall_score = (
            (
                fundamental_score
                / fundamental_max
            ) * 40
            +
            (
                technical_score
                / 65.0
            ) * 60
        )

        score_pass = (
            overall_score
            >= TA_SCORE_BUY_THRESHOLD
        )

        # -----------------------------------------
        # Strategy 3.0 BUY
        #
        # Không cần tất cả điều kiện.
        #
        # Bắt buộc:
        # 1. BCTC pass
        # 2. Thanh khoản pass
        # 3. Overall score >= threshold
        # 4. Có technical confirmation
        # -----------------------------------------

        buy_signal = (
            is_fundamental_passed
            and liquidity_pass
            and score_pass
            and technical_confirmation
        )

        if not buy_signal:
            continue

        # =================================================
        # 3. MUA TẠI OPEN PHIÊN T+1
        # =================================================

        entry_price = _safe_float(
            next_row.get("open")
        )

        if entry_price <= 0:
            continue

        # -----------------------------------------
        # Chống mua đuổi
        # -----------------------------------------

        if (
            entry_price
            > close + 0.5 * atr14
        ):
            continue

        stop_loss = (
            entry_price
            - STOP_ATR_MULTIPLE * atr14
        )

        target_price = (
            entry_price
            + TARGET_ATR_MULTIPLE * atr14
        )

        entry_idx = i + 1

        in_position = True
        is_partial = False

    # =================================================
    # 4. ĐÓNG LỆNH CUỐI KỲ
    # =================================================

    if in_position:

        last_close = _safe_float(
            df_ind.iloc[-1].get("close")
        )

        if last_close > 0:

            ret = (
                (last_close - entry_price)
                / entry_price
            )

            trades.append({
                "type": "OPEN_POSITION",
                "entry_price": entry_price,
                "exit_price": last_close,
                "return_pct": ret * 100,
                "holding_days": (
                    len(df_ind) - entry_idx
                ),
                "date": str(
                    df_ind.iloc[-1].get("date", "")
                )[:10],
            })

    # =================================================
    # 5. THỐNG KÊ
    # =================================================

    total_trades = len(trades)

    if total_trades == 0:

        return {
            "ticker": ticker,
            "trades": [],
            "summary": {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "avg_gain": 0,
                "avg_loss": 0,
                "win_count": 0,
                "loss_count": 0,
            },
        }

    returns = [
        _safe_float(
            trade.get("return_pct")
        )
        for trade in trades
    ]

    wins = [
        value
        for value in returns
        if value > 0
    ]

    losses = [
        value
        for value in returns
        if value <= 0
    ]

    win_rate = (
        len(wins)
        / total_trades
        * 100
    )

    total_return = sum(
        returns
    )

    avg_gain = (
        np.mean(wins)
        if wins
        else 0
    )

    avg_loss = (
        np.mean(losses)
        if losses
        else 0
    )

    return {
        "ticker": ticker,
        "trades": trades,
        "summary": {
            "total_trades": total_trades,
            "win_rate": round(
                win_rate,
                1
            ),
            "total_return": round(
                total_return,
                1
            ),
            "avg_gain": round(
                avg_gain,
                1
            ),
            "avg_loss": round(
                avg_loss,
                1
            ),
            "win_count": len(wins),
            "loss_count": len(losses),
        },
    }