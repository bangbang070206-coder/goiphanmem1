from typing import Dict, Any, Optional

import pandas as pd

from core_logic.indicators import calculate_indicators
from core_logic.scoring import score_stock
from core_logic.fundamental_filter import check_industry_criteria
from database.db_manager import get_financial_metrics, get_industry_classification
from config import (
    MIN_AVG_VALUE_20D,
    STRATEGY_VERSION,
    TA_SCORE_BUY_THRESHOLD,
    TECHNICAL_BUY_THRESHOLD,
    GENERAL_FUNDAMENTAL_MIN_SCORE,
)


def _load_financials(ticker: str):
    fin = get_financial_metrics(ticker)

    if not fin:
        from data_pipeline.fetcher import fetch_stock_financials
        fin = fetch_stock_financials(ticker)

    return fin or {}


def _general_fundamental(fin: dict) -> dict:
    """
    Bộ lọc BCTC chung cho /signals và /check.
    Không dùng tiêu chí riêng theo ngành.
    """

    roe = fin.get("roe")
    rev = fin.get("rev_growth")
    npg = fin.get("np_growth")

    score = 0
    reasons = []

    # ROE
    if roe is not None:
        try:
            if float(roe) >= 0.08:
                score += 15
            else:
                reasons.append("ROE < 8%")
        except Exception:
            pass

    # Tăng trưởng doanh thu
    if rev is not None:
        try:
            if float(rev) > 0:
                score += 10
            else:
                reasons.append("Doanh thu không tăng")
        except Exception:
            pass

    # Tăng trưởng lợi nhuận
    if npg is not None:
        try:
            if float(npg) > 0:
                score += 10
            else:
                reasons.append("LNST không tăng")
        except Exception:
            pass

    has_roe = roe is not None
    has_growth = rev is not None or npg is not None

    passed = (
        has_roe
        and has_growth
        and score >= GENERAL_FUNDAMENTAL_MIN_SCORE
    )

    if not has_roe or not has_growth:
        status = "INSUFFICIENT_DATA"
    elif passed:
        status = "PASSED"
    else:
        status = "FAILED"

    return {
        "is_passed": passed,
        "status": status,
        "score": score,
        "max_score": 35,
        "reason": (
            "; ".join(reasons)
            if reasons
            else (
                "BCTC chung đạt"
                if passed
                else "Chưa đạt ngưỡng BCTC chung"
            )
        ),
        "roe": roe,
        "rev_growth": rev,
        "np_growth": npg,
    }


def _technical_result(df_price):
    """
    Tính chỉ báo và technical score.
    Giữ lại để tương thích với các phần khác của project.
    """

    if df_price is None or df_price.empty:
        return None, "INSUFFICIENT_DATA", "Không có dữ liệu giá"

    try:
        df_ind = calculate_indicators(df_price)
        score_res = score_stock(df_ind)

        if score_res.get("status") != "SUCCESS":
            return (
                df_ind,
                score_res.get("status"),
                score_res.get("reason"),
            )

        return df_ind, score_res, None

    except Exception as exc:
        return None, "INSUFFICIENT_DATA", str(exc)


def evaluate_ticker(
    ticker: str,
    df_price: pd.DataFrame,
    industry_code: Optional[str] = None,
    include_technical: bool = True,
    use_industry_filter: bool = False,
) -> Dict[str, Any]:

    ticker = ticker.upper()

    result = {
        "ticker": ticker,
        "strategy_version": STRATEGY_VERSION,
        "status": "WATCHLIST",
        "signal": "HOLD",
        "fundamental": {},
        "technical": {},
        "scoring": {},
        "gates": {},
        "reasons": [],
        "fundamental_status": "NOT_EVALUATED",
        "technical_status": "NOT_EVALUATED",
        "ta_status": "NOT_EVALUATED",
    }

    # =========================================================
    # 1. BCTC
    # =========================================================

    fin_data = _load_financials(ticker)

    classification = get_industry_classification(ticker)

    resolved_industry = (
        industry_code
        or (classification or {}).get("industry_code")
    )

    if use_industry_filter:
        fin_eval = check_industry_criteria(
            fin_data,
            resolved_industry,
        )
    else:
        fin_eval = _general_fundamental(fin_data)

    result["fundamental"] = fin_eval

    result["fundamental_status"] = fin_eval.get(
        "status",
        "INSUFFICIENT_DATA",
    )

    result["industry"] = (
        classification
        or {
            "industry_code": resolved_industry,
            "industry_name": "Chưa xác định",
        }
    )

    result["industry_status"] = result["fundamental_status"]

    # =========================================================
    # 2. Nếu chỉ kiểm tra BCTC thì dừng ở đây
    # =========================================================

    if not include_technical:
        result["final_status"] = result["fundamental_status"]
        result["status"] = result["final_status"]
        return result

    # =========================================================
    # 3. Kiểm tra dữ liệu giá
    # =========================================================

    if df_price is None or len(df_price) < 60:

        result["technical_status"] = (
            result["ta_status"]
        ) = "INSUFFICIENT_DATA"

        result["status"] = "INSUFFICIENT_DATA"

        result["final_status"] = result["status"]

        result["reasons"].append(
            "Dữ liệu giá chưa đủ 60 phiên"
        )

        return result

    # =========================================================
    # 4. Tính chỉ báo kỹ thuật
    # =========================================================

    df_ind = calculate_indicators(df_price)

    score_res = score_stock(df_ind)

    if score_res.get("status") != "SUCCESS":

        result["technical_status"] = (
            result["ta_status"]
        ) = "INSUFFICIENT_DATA"

        result["status"] = (
            "INSUFFICIENT_DATA"
            if fin_eval.get("is_passed")
            else result["fundamental_status"]
        )

        result["final_status"] = result["status"]

        result["reasons"].append(
            score_res.get(
                "reason",
                "Thiếu dữ liệu kỹ thuật",
            )
        )

        return result

    # =========================================================
    # 5. Lấy dữ liệu kỹ thuật
    # =========================================================

    raw = score_res["raw"]

    close = raw["close"]
    ema20 = raw["ema20"]
    ema50 = raw["ema50"]

    atr14 = raw["atr14"]
    rsi14 = raw["rsi14"]

    volume_ratio = raw["volume_ratio"]
    distance_atr = raw["distance_atr"]

    # Thanh khoản bình quân 20 phiên
    avg_traded_value_20d = (
        df_ind["close"] * df_ind["volume"]
    ).iloc[-21:-1].mean()

    technical_score = score_res["technical_score"]

    # =========================================================
    # 6. Tính tổng điểm
    #
    # Fundamental = 40%
    # Technical   = 60%
    # =========================================================

    overall_score = (
        (
            fin_eval.get("score", 0)
            / max(fin_eval.get("max_score", 35), 1)
        )
        * 40
        +
        (
            technical_score
            / 65
        )
        * 60
    )

    # =========================================================
    # 7. Các tín hiệu kỹ thuật
    # =========================================================

    liquidity_pass = (
        avg_traded_value_20d >= MIN_AVG_VALUE_20D
    )

    # Xu hướng tăng
    trend = close > ema20 > ema50

    # RSI tích cực
    rsi_pass = rsi14 > 50

    # Volume cao hơn trung bình
    vol_pass = (
        volume_ratio is not None
        and volume_ratio >= 1.0
    )

    # Giá không quá xa EMA20
    distance_pass = (
        distance_atr is not None
        and distance_atr <= 3.0
    )

    # Giá tăng so với phiên trước
    up_day = raw["up_day"]

    # =========================================================
    # 8. Lưu technical data
    # =========================================================

    result["technical"] = {
        "close": close,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "atr14": round(atr14, 2),
        "rsi14": round(rsi14, 1),
        "volume_ratio": (
            round(volume_ratio, 2)
            if volume_ratio is not None
            else None
        ),
        "distance_atr": (
            round(distance_atr, 2)
            if distance_atr is not None
            else None
        ),
        "date": raw["date"],
    }

    # =========================================================
    # 9. Lưu scoring
    # =========================================================

    result["scoring"] = {
        "ta_score": round(overall_score, 1),
        "technical_score": technical_score,
        "fundamental_score": fin_eval.get("score", 0),
        "max_fundamental_score": fin_eval.get(
            "max_score",
            35,
        ),
    }

    # =========================================================
    # 10. Lưu các gate để Telegram hiển thị
    # =========================================================

    result["gates"] = {
        "trend": {
            "passed": trend,
        },
        "rsi": {
            "passed": rsi_pass,
        },
        "volume": {
            "passed": vol_pass,
        },
        "distance": {
            "passed": distance_pass,
        },
        "up_day": {
            "passed": up_day,
        },
        "liquidity": {
            "passed": liquidity_pass,
            "observed": avg_traded_value_20d,
        },
        "score": {
            "passed": (
                overall_score
                >= TA_SCORE_BUY_THRESHOLD
            ),
            "observed": overall_score,
        },
    }

    # =========================================================
    # 11. Xác nhận kỹ thuật
    #
    # KHÔNG cần tất cả chỉ báo PASS.
    #
    # Chỉ cần 1 trong 3:
    # - Trend tốt
    # - RSI > 50
    # - Giá gần EMA20
    # =========================================================

    technical_confirmation = (
        trend
        or rsi_pass
        or distance_pass
    )

    # Technical status giờ dựa trên tín hiệu xác nhận,
    # không bắt buộc technical_score phải đạt riêng một gate.
    technical_pass = (
        technical_score
        >= TECHNICAL_BUY_THRESHOLD
    )

    result["technical_status"] = (
        result["ta_status"]
    ) = (
        "PASS"
        if technical_confirmation
        else "FAIL"
    )

    # =========================================================
    # 12. QUYẾT ĐỊNH BUY
    #
    # Không yêu cầu tất cả chỉ báo kỹ thuật PASS.
    #
    # Cần:
    # - BCTC đạt
    # - Thanh khoản đạt
    # - Tổng điểm >= 55
    # - Có ít nhất 1 tín hiệu kỹ thuật xác nhận
    # =========================================================

    if (
        fin_eval.get("is_passed")
        and liquidity_pass
        and overall_score >= TA_SCORE_BUY_THRESHOLD
        and technical_confirmation
    ):

        result["status"] = "BUY_CANDIDATE"
        result["signal"] = "BUY"

        result["reasons"].append(
            f"BCTC đạt + thanh khoản đạt + "
            f"tổng điểm {overall_score:.1f} "
            f">= {TA_SCORE_BUY_THRESHOLD} + "
            f"có tín hiệu kỹ thuật xác nhận"
        )

    # =========================================================
    # 13. Nếu BCTC đạt nhưng chưa đủ điều kiện BUY
    # =========================================================

    elif fin_eval.get("is_passed"):

        result["status"] = "WATCHLIST"

        result["reasons"].append(
            "BCTC đạt nhưng chưa đủ điều kiện "
            "tổng hợp để MUA"
        )

    # =========================================================
    # 14. Nếu BCTC không đạt
    # =========================================================

    else:

        result["status"] = result["fundamental_status"]

        result["reasons"].append(
            f"BCTC: "
            f"{fin_eval.get('reason', 'Chưa đạt')}"
        )

    # =========================================================
    # 15. Final status
    # =========================================================

    result["final_status"] = result["status"]

    return result