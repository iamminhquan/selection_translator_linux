"""Cửa sổ nổi hiển thị bản dịch bằng Tkinter."""

import signal
import tkinter as tk
from collections.abc import Callable
from queue import Empty, Queue

from selection_translator.config import (
    APP_NAME,
    PANEL_HEIGHT,
    PANEL_MIN_HEIGHT,
    PANEL_MIN_WIDTH,
    PANEL_WIDTH,
)


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
        self.root.minsize(PANEL_MIN_WIDTH, PANEL_MIN_HEIGHT)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.bind_all("<Escape>", self._handle_escape)
        self.root.withdraw()
        self.tasks: Queue[Callable[[], None]] = Queue()
        self.stop_callbacks: list[Callable[[], None]] = []
        self.escape_callback: Callable[[], None] = self.stop
        self.last_translated_text = ""

        self.actions = tk.Frame(self.root, bg="#111827")
        self.actions.pack(side="bottom", fill="x")

        self.copy_button = tk.Button(
            self.actions,
            text="Copy bản dịch",
            command=self.copy_translation,
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=6,
        )
        self.copy_button.pack(side="left", padx=10, pady=8)

        self.status_label = tk.Label(
            self.actions,
            text="",
            bg="#111827",
            fg="#cbd5e1",
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

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
        self.text.pack(side="top", fill="both", expand=True)

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

        self.last_translated_text = translated_text
        self.status_label.configure(text="")
        self.copy_button.configure(state="normal")

        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)
        self.text.configure(state="disabled")

        pointer_x = self.root.winfo_pointerx()
        pointer_y = self.root.winfo_pointery()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        panel_width = min(PANEL_WIDTH, max(PANEL_MIN_WIDTH, screen_width - 40))
        panel_height = min(PANEL_HEIGHT, max(PANEL_MIN_HEIGHT, screen_height - 80))

        x = min(pointer_x + 20, screen_width - panel_width - 20)
        y = min(pointer_y + 20, screen_height - panel_height - 60)
        x = max(x, 20)
        y = max(y, 20)

        self.root.geometry(f"{panel_width}x{panel_height}+{x}+{y}")
        self.root.deiconify()
        self.root.lift()

    def show_message(self, message: str) -> None:
        """Hiển thị thông báo trạng thái không kèm nhãn bản dịch.

        Args:
            message (str): Nội dung thông báo cần hiển thị.

        Returns:
            None: Hàm cập nhật UI và không trả về giá trị.
        """
        self.last_translated_text = ""
        self.status_label.configure(text="")
        self.copy_button.configure(state="disabled")

        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, message)
        self.text.configure(state="disabled")

        self.root.deiconify()
        self.root.lift()

    def copy_translation(self) -> None:
        """Copy bản dịch gần nhất vào clipboard hệ thống.

        Returns:
            None: Hàm cập nhật clipboard và trạng thái UI.
        """
        if not self.last_translated_text:
            self.status_label.configure(text="Chưa có bản dịch để copy.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_translated_text)
        self.root.update()
        self.status_label.configure(text="Đã copy bản dịch.")

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

    def on_escape(self, callback: Callable[[], None]) -> None:
        """Đăng ký hành động khi người dùng nhấn phím Escape.

        Args:
            callback (Callable[[], None]): Hàm cần gọi khi nhấn Escape.

        Returns:
            None: Hàm chỉ lưu callback và không trả về giá trị.
        """
        self.escape_callback = callback

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

    def _handle_escape(self, event: tk.Event) -> None:
        """Chạy hành động đã đăng ký khi người dùng nhấn phím Escape.

        Args:
            event (tk.Event): Sự kiện bàn phím từ Tkinter.

        Returns:
            None: Hàm gọi callback và không trả về giá trị.
        """
        self.escape_callback()

    def _handle_sigint(self, signum: int, frame: object | None) -> None:
        """Xử lý tín hiệu `Ctrl+C` từ terminal.

        Args:
            signum (int): Mã tín hiệu hệ điều hành.
            frame (object | None): Frame hiện tại do signal handler truyền vào.

        Returns:
            None: Hàm dừng ứng dụng và không trả về giá trị.
        """
        self.stop()
