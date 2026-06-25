"""Điểm vào của Selection Translator trên Linux."""

import argparse
import sys

from selection_translator.app import TranslatorApp
from selection_translator.clipboard import read_selected_text
from selection_translator.ipc import send_translate_trigger


def main() -> None:
    """Chạy ứng dụng Selection Translator.

    Returns:
        None: Hàm không trả về giá trị.
    """
    parser = argparse.ArgumentParser(description="Selection Translator for Linux")
    parser.add_argument(
        "--test-ui",
        action="store_true",
        help="Hiển thị popup kiểm tra UI rồi chạy event loop.",
    )
    parser.add_argument(
        "--translate-once",
        action="store_true",
        help="Dịch selection hiện tại một lần rồi thoát khi đóng popup.",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="Gửi yêu cầu dịch tới ứng dụng đang chạy.",
    )
    parser.add_argument(
        "--debug-selection",
        action="store_true",
        help="In nội dung selection/clipboard đọc được rồi thoát.",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Không tự gửi Ctrl+C trước khi đọc clipboard.",
    )
    args = parser.parse_args()

    if args.debug_selection:
        print(read_selected_text(copy_before_read=not args.no_copy))
        return

    if len(sys.argv) == 1 and not sys.stdin.isatty() and send_translate_trigger():
        return

    if args.trigger and send_translate_trigger():
        return

    app = TranslatorApp()

    if args.test_ui:
        app.show_test_panel()
        return

    if args.trigger:
        app.run_shortcut_fallback(copy_before_read=not args.no_copy)
        return

    if args.translate_once:
        app.translate_once(copy_before_read=not args.no_copy)
        return

    app.run()


if __name__ == "__main__":
    main()
