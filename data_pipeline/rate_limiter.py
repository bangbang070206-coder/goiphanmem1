import time
import threading
import logging

from config import VNSTOCK_MIN_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_call_time = [0.0]

def throttle():
    """
    Đảm bảo khoảng cách tối thiểu giữa MỌI lệnh gọi API vnstock trong toàn bộ dự án
    (không riêng gì giữa các mã, mà giữa TỪNG request - vì 1 mã có thể cần tới 4
    request: giá lịch sử + tỷ số tài chính + KQKD + lưu chuyển tiền tệ).

    Dùng threading.Lock vì các lệnh gọi có thể đến từ nhiều thread khác nhau cùng
    lúc (do bot dùng asyncio.to_thread / asyncio.gather để chạy song song) - nếu
    không khóa, nhiều thread có thể "nghĩ" mình đang trong khoảng nghỉ hợp lệ và
    cùng gọi API một lúc, vẫn bị Rate limit exceeded như cũ.
    """
    with _lock:
        now = time.time()
        elapsed = now - _last_call_time[0]
        wait = VNSTOCK_MIN_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_call_time[0] = time.time()
