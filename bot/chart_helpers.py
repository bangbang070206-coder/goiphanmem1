import io
import logging
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Không cần GUI, chỉ render ảnh PNG
import matplotlib.pyplot as plt

from config import EMA_FAST, EMA_SLOW, RSI_PERIOD

logger = logging.getLogger(__name__)


def _find_col(df: pd.DataFrame, name: str):
    """Tìm cột không phân biệt hoa/thường (dữ liệu có thể là 'close' hoặc 'Close')."""
    for c in df.columns:
        if str(c).lower() == name:
            return c
    return None


def _calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def build_price_chart(df: pd.DataFrame, ticker: str, lookback_days: int = 180) -> io.BytesIO:
    """
    Vẽ biểu đồ giá + EMA20/EMA50 (trên) và RSI14 (dưới) từ dữ liệu OHLCV đã có sẵn
    (không gọi thêm API - dùng lại dữ liệu đã fetch cho /check).
    Trả về ảnh PNG dạng BytesIO để gửi qua Telegram bằng message.reply_photo().
    """
    if df is None or df.empty:
        raise ValueError("Không có dữ liệu giá để vẽ biểu đồ.")

    data = df.copy()
    date_col = _find_col(data, "date") or data.columns[0]
    close_col = _find_col(data, "close")
    if close_col is None:
        raise ValueError("Không tìm thấy cột giá đóng cửa (close) trong dữ liệu.")

    data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=[date_col]).sort_values(date_col)

    ema_fast_full = _calc_ema(data[close_col], EMA_FAST)
    ema_slow_full = _calc_ema(data[close_col], EMA_SLOW)
    rsi_full = _calc_rsi(data[close_col], RSI_PERIOD)

    plot_data = data.tail(lookback_days)
    ema_fast = ema_fast_full.tail(lookback_days)
    ema_slow = ema_slow_full.tail(lookback_days)
    rsi = rsi_full.tail(lookback_days)

    fig, (ax_price, ax_rsi) = plt.subplots(
        2, 1, figsize=(9, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    ax_price.plot(plot_data[date_col], plot_data[close_col], label="Giá đóng cửa", color="#1f77b4", linewidth=1.3)
    ax_price.plot(plot_data[date_col], ema_fast, label=f"EMA{EMA_FAST}", color="#ff7f0e", linewidth=1)
    ax_price.plot(plot_data[date_col], ema_slow, label=f"EMA{EMA_SLOW}", color="#2ca02c", linewidth=1)
    ax_price.set_title(f"{ticker} - Giá & Đường trung bình động ({len(plot_data)} phiên gần nhất)")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(alpha=0.3)

    ax_rsi.plot(plot_data[date_col], rsi, color="#9467bd", linewidth=1)
    ax_rsi.axhline(70, color="red", linestyle="--", linewidth=0.8)
    ax_rsi.axhline(30, color="green", linestyle="--", linewidth=0.8)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_title(f"RSI{RSI_PERIOD}")
    ax_rsi.grid(alpha=0.3)

    fig.autofmt_xdate()
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)
    buf.name = f"{ticker}_chart.png"
    return buf
