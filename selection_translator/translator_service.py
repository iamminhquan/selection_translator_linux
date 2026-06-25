"""Wrapper cho dịch vụ dịch văn bản."""

import os

from bs4 import BeautifulSoup
import certifi
import requests

from selection_translator.config import TARGET_LANGUAGE, TRANSLATION_TIMEOUT_SECONDS

GOOGLE_TRANSLATE_URL = "https://translate.google.com/m"
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

        try:
            response = requests.get(
                GOOGLE_TRANSLATE_URL,
                params={
                    "sl": "auto",
                    "tl": self.target_language,
                    "q": clean_text,
                },
                headers=REQUEST_HEADERS,
                timeout=TRANSLATION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.Timeout as error:
            raise RuntimeError(
                "Google Translate phản hồi quá chậm. "
                "Hãy kiểm tra mạng rồi thử lại."
            ) from error
        except requests.RequestException as error:
            raise RuntimeError(f"Không gọi được Google Translate: {error}") from error

        soup = BeautifulSoup(response.text, "html.parser")
        element = soup.find("div", {"class": "result-container"})
        if element is None:
            element = soup.find("div", {"class": "t0"})

        if element is None:
            raise RuntimeError("Không tìm thấy nội dung bản dịch trong phản hồi.")

        return element.get_text(strip=True)
