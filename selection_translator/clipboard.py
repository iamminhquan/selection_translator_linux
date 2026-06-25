"""Các hàm hỗ trợ lấy nội dung selection trên Linux."""

import os
import shutil
import subprocess
import time

from selection_translator.logging_utils import log_debug

COPY_BEFORE_SEND_SECONDS = 0.45
COPY_WAIT_SECONDS = 0.35


APP_CONTENT_MARKERS = (
    "BẢN DỊCH:",
    "NỘI DUNG GỐC:",
    "ORIGINAL CONTENT:",
)


def is_app_generated_content(text: str) -> bool:
    """Kiểm tra text có phải nội dung popup cũ của app không.

    Args:
        text (str): Văn bản cần kiểm tra.

    Returns:
        bool: `True` nếu text chứa marker do app tạo ra.
    """
    return any(marker in text for marker in APP_CONTENT_MARKERS)


def run_text_command(command: list[str]) -> str:
    """Chạy lệnh hệ thống và trả về stdout dạng text.

    Args:
        command (list[str]): Lệnh và tham số cần chạy.

    Returns:
        str: Nội dung stdout đã strip hoặc chuỗi rỗng nếu lệnh lỗi.
    """
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log_debug(f"DEBUG: Không chạy được lệnh {' '.join(command)}: {error}")
        return ""

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log_debug(f"DEBUG: Lệnh {' '.join(command)} trả về lỗi: {stderr}")
        return ""

    text = result.stdout.strip()
    if is_app_generated_content(text):
        log_debug("DEBUG: Bỏ qua selection vì giống nội dung popup cũ của app.")
        return ""

    return text


def send_copy_shortcut() -> None:
    """Gửi phím `Ctrl+C` bằng `ydotool` nếu công cụ này có sẵn.

    Returns:
        None: Hàm chỉ thử gửi phím copy và không trả về giá trị.
    """
    if shutil.which("ydotool") is None:
        log_debug("DEBUG: Không tìm thấy ydotool, bỏ qua bước tự gửi Ctrl+C.")
        return

    time.sleep(COPY_BEFORE_SEND_SECONDS)

    try:
        result = subprocess.run(
            ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log_debug(f"DEBUG: Không chạy được ydotool: {error}")
        return
    if result.returncode != 0:
        log_debug(f"DEBUG: ydotool không gửi được Ctrl+C: {result.stderr.strip()}")
        return

    log_debug("DEBUG: Đã gửi Ctrl+C bằng ydotool.")
    time.sleep(COPY_WAIT_SECONDS)


def read_wayland_selection() -> str:
    """Đọc selection trên Wayland bằng `wl-paste`.

    Returns:
        str: Văn bản trong primary selection hoặc clipboard trên Wayland.
    """
    if shutil.which("wl-paste") is None:
        log_debug("DEBUG: Không tìm thấy wl-paste. Hãy cài gói wl-clipboard.")
        return ""

    primary_text = run_text_command(["wl-paste", "--primary", "--no-newline"])
    if primary_text:
        log_debug("DEBUG: Đã lấy văn bản từ Wayland primary selection.")
        return primary_text

    clipboard_text = run_text_command(["wl-paste", "--no-newline"])
    if clipboard_text:
        log_debug("DEBUG: Đã lấy văn bản từ Wayland clipboard.")
        return clipboard_text

    return ""


def read_x11_selection() -> str:
    """Đọc selection trên X11 bằng `xclip`.

    Returns:
        str: Văn bản trong primary selection hoặc clipboard trên X11.
    """
    if shutil.which("xclip") is None:
        log_debug("DEBUG: Không tìm thấy xclip.")
        return ""

    primary_text = run_text_command(["xclip", "-o", "-selection", "primary"])
    if primary_text:
        log_debug("DEBUG: Đã lấy văn bản từ X11 primary selection.")
        return primary_text

    clipboard_text = run_text_command(["xclip", "-o", "-selection", "clipboard"])
    if clipboard_text:
        log_debug("DEBUG: Đã lấy văn bản từ X11 clipboard.")
        return clipboard_text

    return ""


def read_selected_text(copy_before_read: bool = True) -> str:
    """Đọc văn bản đang bôi đen hoặc clipboard theo session hiện tại.

    Args:
        copy_before_read (bool): Có gửi `Ctrl+C` trước khi đọc clipboard không.

    Returns:
        str: Văn bản đọc được từ Wayland/X11 selection hoặc chuỗi rỗng.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    log_debug(f"DEBUG: Session hiện tại: {session_type or 'unknown'}")
    if copy_before_read:
        send_copy_shortcut()

    if session_type == "wayland":
        return read_wayland_selection()

    if session_type == "x11":
        return read_x11_selection()

    wayland_text = read_wayland_selection()
    if wayland_text:
        return wayland_text

    return read_x11_selection()
