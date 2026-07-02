"""Cửa sổ nổi hiển thị bản dịch bằng Tkinter."""

import signal
import tkinter as tk
from collections.abc import Callable
from queue import Empty, Queue

from selection_translator.config import APP_NAME, PANEL_HEIGHT, PANEL_WIDTH


class TranslationPanel:
    """Hiển thị kết quả dịch trong cửa sổ luôn nổi."""

    def __init__(self) -> None:
        """Tạo cửa sổ nổi và ẩn cho đến khi có nội dung.

        Returns:
            None: Hàm khởi tạo không trả về giá trị.
        """
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry(f"{PANEL_WIDTH}x{PANEL_HEIGHT}")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.withdraw()
        self.tasks: Queue[Callable[[], None]] = Queue()
        self.stop_callbacks: list[Callable[[], None]] = []

        self.text = tk.Text(
            self.root,
            wrap="word",
            bg="#1f2933",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            padx=12,
            pady=12,
            font=("Sans", 12),
            exportselection=False,
        )
        self.text.pack(fill="both", expand=True)

    def show(self, translated_text: str, original_text: str = "") -> None:
        """Hiển thị bản dịch và nội dung gốc gần vị trí con trỏ.

        Args:
            translated_text (str): Văn bản đã dịch để hiển thị.
            original_text (str): Văn bản gốc, có thể để trống.

        Returns:
            None: Hàm cập nhật UI và không trả về giá trị.
        """
        content = f"BẢN DỊCH:\n{translated_text}"
        if original_text:
            content += f"\n\nNỘI DUNG GỐC:\n{original_text}"

        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)
        self.text.configure(state="disabled")

        pointer_x = self.root.winfo_pointerx()
        pointer_y = self.root.winfo_pointery()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = min(pointer_x + 20, screen_width - PANEL_WIDTH - 20)
        y = min(pointer_y + 20, screen_height - PANEL_HEIGHT - 60)
        x = max(x, 20)
        y = max(y, 20)

        self.root.geometry(f"{PANEL_WIDTH}x{PANEL_HEIGHT}+{x}+{y}")
        self.root.deiconify()
        self.root.lift()

    def show_message(self, message: str) -> None:
        """Hiển thị thông báo trạng thái không kèm nhãn bản dịch.

        Args:
            message (str): Nội dung thông báo cần hiển thị.

        Returns:
            None: Hàm cập nhật UI và không trả về giá trị.
        """
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, message)
        self.text.configure(state="disabled")

        self.root.deiconify()
        self.root.lift()

    def hide(self) -> None:
        """Ẩn cửa sổ bản dịch.

        Returns:
            None: Hàm không trả về giá trị.
        """
        self.root.withdraw()

    def run(self) -> None:
        """Chạy vòng lặp sự kiện Tkinter.

        Returns:
            None: Hàm chạy event loop và không trả về giá trị.
        """
        signal.signal(signal.SIGINT, self._handle_sigint)
        self._poll_signals()
        self._poll_tasks()
        self.root.mainloop()

    def stop(self) -> None:
        """Dừng vòng lặp UI và đóng ứng dụng.

        Returns:
            None: Hàm đóng Tkinter root và không trả về giá trị.
        """
        for callback in self.stop_callbacks:
            callback()
        self.root.quit()
        self.root.destroy()

    def on_stop(self, callback: Callable[[], None]) -> None:
        """Đăng ký callback chạy trước khi đóng cửa sổ.

        Args:
            callback (Callable[[], None]): Hàm cần gọi khi đóng cửa sổ.

        Returns:
            None: Hàm chỉ lưu callback và không trả về giá trị.
        """
        self.stop_callbacks.append(callback)

    def schedule(self, callback: Callable[[], None]) -> None:
        """Đưa callback vào hàng đợi chạy trên UI thread.

        Args:
            callback (Callable[[], None]): Hàm cần chạy trên UI thread.

        Returns:
            None: Hàm chỉ lên lịch callback và không trả về giá trị.
        """
        self.tasks.put(callback)

    def _poll_signals(self) -> None:
        """Cho phép Python xử lý tín hiệu trong khi Tkinter đang chạy.

        Returns:
            None: Hàm tự lên lịch lại và không trả về giá trị.
        """
        self.root.after(100, self._poll_signals)

    def _poll_tasks(self) -> None:
        """Chạy các callback đã được đưa vào hàng đợi UI thread.

        Returns:
            None: Hàm tự lên lịch lại và không trả về giá trị.
        """
        while True:
            try:
                callback = self.tasks.get_nowait()
            except Empty:
                break

            callback()

        self.root.after(50, self._poll_tasks)

    def _handle_sigint(self, signum: int, frame: object | None) -> None:
        """Xử lý tín hiệu `Ctrl+C` từ terminal.

        Args:
            signum (int): Mã tín hiệu hệ điều hành.
            frame (object | None): Frame hiện tại do signal handler truyền vào.

        Returns:
            None: Hàm dừng ứng dụng và không trả về giá trị.
        """
        self.stop()
