"""Wrapper cho dịch vụ dịch văn bản."""

import os
import re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import certifi
import requests
from bs4 import BeautifulSoup

from selection_translator.config import TARGET_LANGUAGE, TRANSLATION_TIMEOUT_SECONDS
from selection_translator.logging_utils import log_debug

GOOGLE_TRANSLATE_URL = "https://translate.google.com/m"
TRANSLATION_CACHE_SIZE = 128
CHUNK_MIN_TEXT_LENGTH = 900
MAX_TRANSLATION_CHUNK_CHARS = 900
MAX_PARALLEL_CHUNKS = 4
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")
CLAUSE_BOUNDARY_PATTERN = re.compile(r"(?<=[,;:，；：])\s+")


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

        chunks = self._split_text_into_chunks(clean_text)
        if len(chunks) > 1:
            log_debug(
                f"DEBUG: Chia văn bản thành {len(chunks)} chunk để dịch song song."
            )
            translated_text = self._translate_chunks(chunks)
            self._store_cached_translation(clean_text, translated_text)
            return translated_text

        translated_text = self._request_translation(clean_text)
        self._store_cached_translation(clean_text, translated_text)
        return translated_text

    def _request_translation(self, text: str) -> str:
        """Gửi một request dịch tới Google Translate.

        Args:
            text (str): Nội dung của một chunk cần dịch.

        Returns:
            str: Nội dung chunk đã dịch.
        """
        try:
            request_start = perf_counter()
            session = requests.Session()
            session.headers.update(REQUEST_HEADERS)
            response = session.get(
                GOOGLE_TRANSLATE_URL,
                params={
                    "sl": "auto",
                    "tl": self.target_language,
                    "q": text,
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
        return translated_text

    def _translate_chunks(self, chunks: list[str]) -> str:
        """Dịch nhiều chunk song song và ghép kết quả theo thứ tự ban đầu.

        Args:
            chunks (list[str]): Danh sách chunk đã tách từ văn bản gốc.

        Returns:
            str: Văn bản đã dịch và ghép lại.
        """
        translated_chunks: list[str | None] = []
        uncached_chunks: list[str] = []
        uncached_indexes: list[int] = []

        for chunk in chunks:
            cached_text = self._get_cached_translation(chunk)
            translated_chunks.append(cached_text)
            if cached_text is None:
                uncached_indexes.append(len(translated_chunks) - 1)
                uncached_chunks.append(chunk)

        if uncached_chunks:
            worker_count = min(MAX_PARALLEL_CHUNKS, len(uncached_chunks))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                translated_uncached_chunks = list(
                    executor.map(self._request_translation, uncached_chunks)
                )

            for index, chunk, translated_text in zip(
                uncached_indexes, uncached_chunks, translated_uncached_chunks
            ):
                translated_chunks[index] = translated_text
                self._store_cached_translation(chunk, translated_text)

        return " ".join(chunk for chunk in translated_chunks if chunk is not None)

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """Tách văn bản dài thành các chunk vừa phải để dịch nhanh hơn.

        Args:
            text (str): Văn bản gốc đã chuẩn hóa.

        Returns:
            list[str]: Danh sách chunk theo đúng thứ tự xuất hiện.
        """
        if len(text) < CHUNK_MIN_TEXT_LENGTH:
            return [text]

        segments = self._split_text_by_boundaries(text)
        chunks: list[str] = []
        current_chunk = ""

        for segment in segments:
            if not segment:
                continue

            if not current_chunk:
                current_chunk = segment
                continue

            candidate = f"{current_chunk} {segment}"
            if len(candidate) <= MAX_TRANSLATION_CHUNK_CHARS:
                current_chunk = candidate
                continue

            chunks.append(current_chunk)
            current_chunk = segment

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _split_text_by_boundaries(self, text: str) -> list[str]:
        """Tách văn bản theo đoạn, câu, mệnh đề và từ khi cần thiết.

        Args:
            text (str): Văn bản gốc đã chuẩn hóa.

        Returns:
            list[str]: Các segment đủ nhỏ để gom thành chunk dịch.
        """
        segments: list[str] = []
        for paragraph in re.split(r"\n{2,}", text):
            clean_paragraph = paragraph.strip()
            if not clean_paragraph:
                continue

            sentence_parts = [
                sentence.strip()
                for sentence in SENTENCE_BOUNDARY_PATTERN.split(clean_paragraph)
                if sentence.strip()
            ]
            for sentence in sentence_parts:
                segments.extend(self._split_long_sentence(sentence))

        return segments

    def _split_long_sentence(self, sentence: str) -> list[str]:
        """Tách câu quá dài thành mệnh đề hoặc nhóm từ ngắn hơn.

        Args:
            sentence (str): Câu cần kiểm tra độ dài.

        Returns:
            list[str]: Một hoặc nhiều segment ngắn hơn.
        """
        if len(sentence) <= MAX_TRANSLATION_CHUNK_CHARS:
            return [sentence]

        clause_parts = [
            clause.strip()
            for clause in CLAUSE_BOUNDARY_PATTERN.split(sentence)
            if clause.strip()
        ]
        if len(clause_parts) > 1:
            return self._group_oversized_parts(clause_parts)

        return self._split_by_words(sentence)

    def _group_oversized_parts(self, parts: list[str]) -> list[str]:
        """Gom các phần nhỏ và tiếp tục tách phần còn quá dài.

        Args:
            parts (list[str]): Các phần đã tách theo dấu câu.

        Returns:
            list[str]: Các segment không vượt quá giới hạn mục tiêu.
        """
        segments: list[str] = []
        current_segment = ""

        for part in parts:
            if len(part) > MAX_TRANSLATION_CHUNK_CHARS:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = ""
                segments.extend(self._split_by_words(part))
                continue

            if not current_segment:
                current_segment = part
                continue

            candidate = f"{current_segment} {part}"
            if len(candidate) <= MAX_TRANSLATION_CHUNK_CHARS:
                current_segment = candidate
                continue

            segments.append(current_segment)
            current_segment = part

        if current_segment:
            segments.append(current_segment)

        return segments

    def _split_by_words(self, text: str) -> list[str]:
        """Tách chuỗi rất dài theo từ khi không có ranh giới câu phù hợp.

        Args:
            text (str): Chuỗi cần tách.

        Returns:
            list[str]: Các nhóm từ theo giới hạn ký tự.
        """
        segments: list[str] = []
        current_segment = ""

        for word in text.split():
            if len(word) > MAX_TRANSLATION_CHUNK_CHARS:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = ""
                segments.extend(self._split_by_characters(word))
                continue

            if not current_segment:
                current_segment = word
                continue

            candidate = f"{current_segment} {word}"
            if len(candidate) <= MAX_TRANSLATION_CHUNK_CHARS:
                current_segment = candidate
                continue

            segments.append(current_segment)
            current_segment = word

        if current_segment:
            segments.append(current_segment)

        return segments

    def _split_by_characters(self, text: str) -> list[str]:
        """Tách chuỗi không có khoảng trắng theo giới hạn ký tự.

        Args:
            text (str): Chuỗi cần tách.

        Returns:
            list[str]: Các đoạn con không vượt quá giới hạn ký tự.
        """
        return [
            text[index : index + MAX_TRANSLATION_CHUNK_CHARS]
            for index in range(0, len(text), MAX_TRANSLATION_CHUNK_CHARS)
        ]

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
