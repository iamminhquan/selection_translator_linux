"""IPC nội bộ để gửi lệnh dịch tới ứng dụng đang chạy."""

from __future__ import annotations

import os
import socket
import threading
from collections.abc import Callable

from selection_translator.logging_utils import log_debug

SOCKET_PATH = f"/tmp/selection-translator-{os.getuid()}.sock"
TRIGGER_COMMAND = "translate"


def send_translate_trigger() -> bool:
    """Gửi lệnh dịch tới tiến trình ứng dụng đang chạy.

    Returns:
        bool: `True` nếu gửi được lệnh, ngược lại là `False`.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.5)
            client.connect(SOCKET_PATH)
            client.sendall(TRIGGER_COMMAND.encode("utf-8"))
        log_debug("DEBUG: Đã gửi trigger dịch tới app đang chạy.")
        return True
    except OSError as error:
        log_debug(f"DEBUG: Không gửi được trigger tới app đang chạy: {error}")
        return False


class TriggerServer:
    """Lắng nghe lệnh dịch từ shortcut bên ngoài."""

    def __init__(self, on_trigger: Callable[[], None]) -> None:
        """Tạo server IPC.

        Args:
            on_trigger (Callable[[], None]): Callback chạy khi nhận lệnh dịch.

        Returns:
            None: Hàm khởi tạo không trả về giá trị.
        """
        self.on_trigger = on_trigger
        self.socket: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.running = False

    def start(self) -> None:
        """Bắt đầu lắng nghe lệnh dịch trong thread nền.

        Returns:
            None: Hàm khởi động server và không trả về giá trị.
        """
        self.stop()

        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        server.listen(5)
        server.settimeout(0.5)

        self.socket = server
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        log_debug(f"DEBUG: Trigger server đang lắng nghe tại {SOCKET_PATH}")

    def stop(self) -> None:
        """Dừng server IPC và dọn socket file.

        Returns:
            None: Hàm dừng server và không trả về giá trị.
        """
        self.running = False

        if self.socket is not None:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

    def _serve(self) -> None:
        """Nhận kết nối IPC và gọi callback khi có lệnh hợp lệ.

        Returns:
            None: Hàm chạy vòng lặp server cho tới khi dừng.
        """
        while self.running and self.socket is not None:
            try:
                connection, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with connection:
                try:
                    command = connection.recv(64).decode("utf-8").strip()
                except OSError as error:
                    log_debug(f"DEBUG: Không đọc được lệnh IPC: {error}")
                    continue

            if command == TRIGGER_COMMAND:
                log_debug("DEBUG: Trigger server đã nhận yêu cầu dịch.")
                self.on_trigger()
