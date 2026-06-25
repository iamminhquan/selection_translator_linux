"""Tiện ích ghi log đơn giản cho app."""

from datetime import datetime
from pathlib import Path


LOG_FILE = Path("/tmp/selection-translator.log")


def log_debug(message: str) -> None:
    """Ghi log debug ra stdout và file tạm.

    Args:
        message (str): Nội dung log cần ghi.

    Returns:
        None: Hàm ghi log và không trả về giá trị.
    """
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{line}\n")
