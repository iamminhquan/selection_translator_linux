"""Kiểm thử TranslatorService."""

from selection_translator.translator_service import (
    MAX_TRANSLATION_CHUNK_CHARS,
    TranslatorService,
)


class FakeTranslatorService(TranslatorService):
    """TranslatorService giả lập để kiểm thử không cần mạng."""

    def __init__(self) -> None:
        """Tạo service giả và danh sách request đã nhận.

        Returns:
            None: Hàm khởi tạo không trả về giá trị.
        """
        super().__init__()
        self.requests: list[str] = []

    def _request_translation(self, text: str) -> str:
        """Ghi nhận request và trả về nội dung giả lập.

        Args:
            text (str): Chunk cần dịch.

        Returns:
            str: Nội dung giả lập đã dịch.
        """
        self.requests.append(text)
        return f"vi:{text}"


def test_split_text_into_chunks_keeps_order_and_size() -> None:
    """Kiểm tra tách chunk giữ thứ tự và không vượt giới hạn.

    Returns:
        None: Test chỉ dùng assert.
    """
    service = TranslatorService()
    text = " ".join(
        f"This is sentence number {index} with enough words to build a long sample."
        for index in range(80)
    )

    chunks = service._split_text_into_chunks(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_TRANSLATION_CHUNK_CHARS for chunk in chunks)
    assert " ".join(chunks) == text


def test_translate_chunks_runs_each_chunk_and_joins_results_in_order() -> None:
    """Kiểm tra dịch nhiều chunk rồi ghép đúng thứ tự ban đầu.

    Returns:
        None: Test chỉ dùng assert.
    """
    service = FakeTranslatorService()
    chunks = ["first sentence.", "second sentence.", "third sentence."]

    translated_text = service._translate_chunks(chunks)

    assert service.requests == chunks
    assert (
        translated_text == "vi:first sentence. vi:second sentence. vi:third sentence."
    )


def test_translate_uses_chunking_for_long_text() -> None:
    """Kiểm tra văn bản dài đi qua luồng dịch theo chunk.

    Returns:
        None: Test chỉ dùng assert.
    """
    service = FakeTranslatorService()
    text = " ".join(
        f"Sentence {index} contains enough words to make chunking useful."
        for index in range(120)
    )

    translated_text = service.translate(text)

    assert len(service.requests) > 1
    assert translated_text.startswith("vi:Sentence 0")


def test_split_text_into_chunks_handles_long_unbroken_text() -> None:
    """Kiểm tra chuỗi không có khoảng trắng vẫn được tách theo giới hạn.

    Returns:
        None: Test chỉ dùng assert.
    """
    service = TranslatorService()
    text = "a" * (MAX_TRANSLATION_CHUNK_CHARS * 2 + 10)

    chunks = service._split_text_into_chunks(text)

    assert len(chunks) == 3
    assert all(len(chunk) <= MAX_TRANSLATION_CHUNK_CHARS for chunk in chunks)
