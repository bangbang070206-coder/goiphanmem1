import time
import random
import logging
from typing import Optional, Dict, Any
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Danh sách User-Agent hiện đại luân phiên (tránh fingerprinting của Cloudflare/CafeF)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15"
]

def get_random_headers(referer: str = "https://cafef.vn/") -> Dict[str, str]:
    """Tạo HTTP Headers ngẫu nhiên mô phỏng hành vi trình duyệt thực tế"""
    ua = random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Connection": "keep-alive",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

def safe_request(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    min_delay: float = 0.8,
    max_delay: float = 1.8,
    timeout: int = 15
) -> Optional[requests.Response]:
    """
    Thực hiện HTTP Request an toàn với 3 lớp phòng vệ chống chặn IP:
    1. Random Throttling: Delay ngẫu nhiên giữa các request tránh kích hoạt Rate Limiter.
    2. Header Randomization: Xoay vòng User-Agent và browser fingerprint.
    3. Exponential Backoff: Tự động tăng thời gian chờ khi gặp mã lỗi 429 hoặc 403.
    """
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    
    session = requests.Session()
    
    for attempt in range(1, max_retries + 1):
        try:
            headers = get_random_headers()
            if method.upper() == "GET":
                response = session.get(url, headers=headers, params=params, timeout=timeout)
            else:
                response = session.post(url, headers=headers, data=data, timeout=timeout)
                
            # Nếu thành công
            if response.status_code == 200:
                return response
                
            # Nếu bị Rate Limit (429) hoặc Tạm khóa (403)
            elif response.status_code in [403, 429]:
                wait_time = (2 ** attempt) + random.uniform(1.0, 2.5)
                logger.warning(f"[Anti-Block] Bị giới hạn IP (Code {response.status_code}) khi gọi {url}. Chờ {wait_time:.1f}s trước khi thử lại lần {attempt}/{max_retries}...")
                time.sleep(wait_time)
            else:
                logger.warning(f"[Anti-Block] Request thất bại với mã lỗi HTTP {response.status_code}: {url}")
                
        except requests.exceptions.RequestException as e:
            wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
            logger.warning(f"[Anti-Block] Lỗi mạng: {e}. Đang thử lại lần {attempt}/{max_retries} sau {wait_time:.1f}s...")
            time.sleep(wait_time)
            
    logger.error(f"[Anti-Block] Không thể cào dữ liệu từ {url} sau {max_retries} lần thử.")
    return None
