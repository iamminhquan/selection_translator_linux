"""Wrapper cho dịch vụ dịch văn bản."""

import os
from collections import OrderedDict
from time import perf_counter

import certifi
import requests
from bs4 import BeautifulSoup

from selection_translator.config import TARGET_LANGUAGE, TRANSLATION_TIMEOUT_SECONDS
from selection_translator.logging_utils import log_debug

GOOGLE_TRANSLATE_URL = "https://translate.google.com/m"
TRANSLATION_CACHE_SIZE = 128
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def configure_ssl_certificates() -> None:
    """Cấu hình CA bundle của certifi cho các thư viện dùng requests.

    Returns:
        None: Hàm chỉ cập nhật biến môi trường và không trả về giá trị.
    """
    cert_path = certifi.where()
    if os.path.exists(cert_path):
        os.environ["SSL_CERT_FILE"] = cert_path
        os.environ["REQUESTS_CA_BUNDLE"] = cert_path
        print(f"DEBUG: SSL_CERT_FILE set to: {cert_path}")
    else:
        print(f"WARNING: certifi bundle not found at: {cert_path}")


class TranslatorService:
    """Dịch văn bản sang ngôn ngữ đích đã cấu hình."""

    def __init__(self, target_language: str = TARGET_LANGUAGE) -> None:
        """Tạo cấu hình dịch Google Translate.

        Args:
            target_language (str): Mã ngôn ngữ đích, ví dụ `vi`.

        Returns:
            None: Hàm khởi tạo không trả về giá trị.
        """
        self.target_language = target_language
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self.cache: OrderedDict[str, str] = OrderedDict()

    def translate(self, text: str) -> str:
        """Dịch văn bản đầu vào.

        Args:
            text (str): Văn bản cần dịch.

        Returns:
            str: Nội dung đã dịch.
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        cached_text = self._get_cached_translation(clean_text)
        if cached_text is not None:
            return cached_text

        try:
            request_start = perf_counter()
            response = self.session.get(
                GOOGLE_TRANSLATE_URL,
                params={
                    "sl": "auto",
                    "tl": self.target_language,
                    "q": clean_text,
                },
                timeout=TRANSLATION_TIMEOUT_SECONDS,
            )
            elapsed_ms = (perf_counter() - request_start) * 1000
            log_debug(f"DEBUG: Google Translate phản hồi sau {elapsed_ms:.0f} ms.")
            response.raise_for_status()
        except requests.Timeout as error:
            raise RuntimeError(
                "Google Translate phản hồi quá chậm. " "Hãy kiểm tra mạng rồi thử lại."
            ) from error
        except requests.RequestException as error:
            raise RuntimeError(f"Không gọi được Google Translate: {error}") from error

        parse_start = perf_counter()
        soup = BeautifulSoup(response.text, "html.parser")
        element = soup.find("div", {"class": "result-container"})
        if element is None:
            element = soup.find("div", {"class": "t0"})
        elapsed_ms = (perf_counter() - parse_start) * 1000
        log_debug(f"DEBUG: Parse phản hồi dịch sau {elapsed_ms:.0f} ms.")

        if element is None:
            raise RuntimeError("Không tìm thấy nội dung bản dịch trong phản hồi.")

        translated_text = element.get_text(strip=True)
        self._store_cached_translation(clean_text, translated_text)
        return translated_text

    def _get_cached_translation(self, text: str) -> str | None:
        """Lấy bản dịch đã lưu trong bộ nhớ đệm.

        Args:
            text (str): Văn bản gốc đã chuẩn hóa.

        Returns:
            str | None: Bản dịch đã cache hoặc `None` nếu chưa có.
        """
        cached_text = self.cache.get(text)
        if cached_text is None:
            return None

        self.cache.move_to_end(text)
        log_debug("DEBUG: Dùng bản dịch từ cache.")
        return cached_text

    def _store_cached_translation(self, text: str, translated_text: str) -> None:
        """Lưu bản dịch vào bộ nhớ đệm giới hạn kích thước.

        Args:
            text (str): Văn bản gốc đã chuẩn hóa.
            translated_text (str): Nội dung bản dịch.

        Returns:
            None: Hàm chỉ cập nhật cache và không trả về giá trị.
        """
        self.cache[text] = translated_text
        self.cache.move_to_end(text)
        if len(self.cache) > TRANSLATION_CACHE_SIZE:
            self.cache.popitem(last=False)
