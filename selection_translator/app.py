"""Điều phối luồng chạy chính của Selection Translator."""

import threading

from selection_translator.clipboard import read_selected_text
from selection_translator.config import SHORTCUT_LABEL
from selection_translator.ipc import TriggerServer
from selection_translator.logging_utils import log_debug
from selection_translator.translator_service import (
    TranslatorService,
    configure_ssl_certificates,
)
from selection_translator.ui import TranslationPanel

INSTRUCTION_TEXT = f"Bôi đen đoạn văn bản và sử dụng phím tắt {SHORTCUT_LABEL} để dịch."
READING_TEXT = "Đang đọc văn bản đã bôi đen..."
TRANSLATING_TEXT = "Đang dịch..."


class TranslatorApp:
    """Điều phối selection, dịch thuật và cập nhật UI."""

    def __init__(self) -> None:
        """Tạo các service chính và cửa sổ nổi.

        Returns:
            None: Hàm khởi tạo không trả về giá trị.
        """
        configure_ssl_certificates()
        self.panel: TranslationPanel | None = None
        self.translator: TranslatorService | None = None
        self.trigger_server: TriggerServer | None = None
        self.translation_lock = threading.Lock()

    def get_panel(self) -> TranslationPanel:
        """Lấy hoặc tạo cửa sổ popup dịch.

        Returns:
            TranslationPanel: Cửa sổ popup dùng để hiển thị kết quả.
        """
        if self.panel is None:
            self.panel = TranslationPanel()

        return self.panel

    def get_translator(self) -> TranslatorService:
        """Lấy hoặc tạo service dịch khi thật sự cần dịch.

        Returns:
            TranslatorService: Service dùng để dịch văn bản.
        """
        if self.translator is None:
            self.translator = TranslatorService()

        return self.translator

    def show_test_panel(self) -> None:
        """Hiển thị popup kiểm tra UI.

        Returns:
            None: Hàm cập nhật UI và không trả về giá trị.
        """
        panel = self.get_panel()
        panel.show_message(
            "Popup kiểm tra hoạt động.\n\n"
            "Nếu bạn thấy cửa sổ này, phần UI không có lỗi.",
        )
        panel.run()

    def run(self) -> None:
        """Mở cửa sổ chính và lắng nghe yêu cầu dịch từ shortcut.

        Returns:
            None: Hàm chạy event loop và không trả về giá trị.
        """
        panel = self.get_panel()
        panel.show_message(INSTRUCTION_TEXT)
        self.trigger_server = TriggerServer(self.translate_from_shortcut)
        self.trigger_server.start()
        panel.on_stop(self.stop)
        panel.run()

    def run_shortcut_fallback(self, copy_before_read: bool = False) -> None:
        """Mở cửa sổ ngay và dịch một lần khi chưa có app thường trực.

        Args:
            copy_before_read (bool): Có gửi `Ctrl+C` trước khi đọc clipboard không.

        Returns:
            None: Hàm chạy event loop và không trả về giá trị.
        """
        panel = self.get_panel()
        panel.show_message(READING_TEXT)

        thread = threading.Thread(
            target=self._translate_in_background,
            kwargs={"copy_before_read": copy_before_read},
            daemon=True,
        )
        log_debug("DEBUG: Chạy fallback dịch một lần từ shortcut.")
        thread.start()
        panel.run()

    def stop(self) -> None:
        """Dừng các tài nguyên nền của ứng dụng.

        Returns:
            None: Hàm dọn tài nguyên và không trả về giá trị.
        """
        if self.trigger_server is not None:
            self.trigger_server.stop()
            self.trigger_server = None

    def translate_from_shortcut(self) -> None:
        """Khởi chạy tác vụ dịch khi nhận hotkey từ shortcut hệ thống.

        Returns:
            None: Hàm tạo thread nền và không trả về giá trị.
        """
        thread = threading.Thread(
            target=self._translate_in_background,
            kwargs={"copy_before_read": False},
            daemon=True,
        )
        log_debug("DEBUG: App bắt đầu thread dịch từ shortcut.")
        thread.start()

    def translate_once(self, copy_before_read: bool = True) -> None:
        """Dịch selection hoặc clipboard hiện tại một lần.

        Args:
            copy_before_read (bool): Có gửi `Ctrl+C` trước khi đọc clipboard không.

        Returns:
            None: Hàm hiển thị kết quả dịch và không trả về giá trị.
        """
        print("--- Đang đọc selection/clipboard ---")
        panel = self.get_panel()
        text = read_selected_text(copy_before_read=copy_before_read)
        if not text:
            panel.show(
                "Không đọc được văn bản.\n\n"
                "Hãy bôi đen text hoặc copy text vào clipboard trước khi gọi shortcut.",
            )
            panel.run()
            return

        try:
            translated = self.get_translator().translate(text)
            if translated.strip() == text.strip():
                translated = (
                    f"{translated}\n\n"
                    "Ghi chú: Bản dịch giống nội dung gốc. "
                    "Điều này thường xảy ra với tên riêng, lệnh hoặc tên package."
                )
            panel.show(translated, text)
        except Exception as error:
            panel.show(f"Lỗi: {error}")

        panel.run()

    def _translate_in_background(self, copy_before_read: bool) -> None:
        """Đọc selection, dịch và đưa kết quả về UI thread.

        Args:
            copy_before_read (bool): Có gửi `Ctrl+C` trước khi đọc clipboard không.

        Returns:
            None: Hàm chạy trong thread nền và không trả về giá trị.
        """
        if not self.translation_lock.acquire(blocking=False):
            self._show_message_on_ui("Ứng dụng đang dịch yêu cầu trước đó...")
            return

        try:
            self._show_message_on_ui(READING_TEXT)
            text = read_selected_text(copy_before_read=copy_before_read)
            if not text:
                log_debug("DEBUG: Không đọc được text sau khi nhận shortcut.")
                self._show_message_on_ui(
                    "Không đọc được văn bản.\n\n"
                    f"Hãy bôi đen đoạn văn bản rồi nhấn {SHORTCUT_LABEL}."
                )
                return

            log_debug(f"DEBUG: Đã đọc text dài {len(text)} ký tự, bắt đầu dịch.")
            self._show_on_ui(TRANSLATING_TEXT, text)
            try:
                translated = self.get_translator().translate(text)
                if translated.strip() == text.strip():
                    translated = (
                        f"{translated}\n\n"
                        "Ghi chú: Bản dịch giống nội dung gốc. "
                        "Điều này thường xảy ra với tên riêng, lệnh hoặc tên package."
                    )
                log_debug("DEBUG: Dịch xong, chuẩn bị cập nhật UI.")
                self._show_on_ui(translated, text)
            except Exception as error:
                log_debug(f"DEBUG: Lỗi khi dịch: {error}")
                self._show_on_ui(f"Lỗi: {error}", text)
        finally:
            self.translation_lock.release()

    def _show_on_ui(self, translated_text: str, original_text: str = "") -> None:
        """Lên lịch cập nhật nội dung cửa sổ trên UI thread.

        Args:
            translated_text (str): Nội dung cần hiển thị.
            original_text (str): Văn bản gốc, có thể để trống.

        Returns:
            None: Hàm chỉ đưa callback vào hàng đợi UI.
        """
        panel = self.get_panel()
        panel.schedule(lambda: panel.show(translated_text, original_text))

    def _show_message_on_ui(self, message: str) -> None:
        """Lên lịch hiển thị thông báo trạng thái trên UI thread.

        Args:
            message (str): Nội dung thông báo cần hiển thị.

        Returns:
            None: Hàm chỉ đưa callback vào hàng đợi UI.
        """
        panel = self.get_panel()
        panel.schedule(lambda: panel.show_message(message))
