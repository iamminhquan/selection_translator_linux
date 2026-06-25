# Selection Translator for Linux

Ứng dụng dịch nhanh văn bản đang bôi đen trên Linux/Ubuntu. Dự án này được fork từ bản macOS và được điều chỉnh để chạy tốt hơn với Ubuntu Wayland.

## Tính năng chính

- Dịch selection hoặc clipboard hiện tại sang tiếng Việt.
- Hỗ trợ Wayland bằng `wl-paste` từ gói `wl-clipboard`.
- Hỗ trợ X11 bằng `xclip`.
- Hiển thị kết quả trong cửa sổ nổi bằng `tkinter`.
- Phù hợp để gắn vào Ubuntu Custom Keyboard Shortcut.
- Khi chạy `python3 translator.py`, cửa sổ mở ngay và chờ phím tắt dịch.

## Yêu cầu hệ thống

- Ubuntu hoặc distro Linux desktop tương thích.
- Python 3.9+.
- `python3-tk` để hiển thị popup.
- `wl-clipboard` cho Wayland.
- `xclip` cho X11.
- `ydotool` để gửi `Ctrl+C` tự động trên Wayland khi dùng keyboard shortcut.

Trên Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk wl-clipboard xclip ydotool
```

Trên Wayland, bật daemon của `ydotool`:

```bash
sudo systemctl enable --now ydotool
```

Nếu systemd báo không có service `ydotool`, thử:

```bash
sudo systemctl enable --now ydotoold
```

## Cài đặt

```bash
git clone https://github.com/ch-hnhu/selection-translator-linux.git
cd selection-translator-linux

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Chạy thử

Kiểm tra popup:

```bash
python3 translator.py --test-ui
```

Mở ứng dụng thường trực:

```bash
python3 translator.py
```

Cửa sổ sẽ hiện ngay với hướng dẫn bôi đen văn bản và nhấn `Ctrl + Alt + Y`.

Dịch một lần rồi thoát khi đóng popup:

```bash
python3 translator.py --translate-once
```

Trước khi chạy lệnh dịch một lần, hãy bôi đen text ở ứng dụng khác hoặc copy text vào clipboard. Trên Wayland, nếu `ydotool` đang chạy, app sẽ gửi `Ctrl+C` trước rồi đọc clipboard bằng `wl-paste`.

Khi dùng Ubuntu shortcut, nên gọi script wrapper để copy selection rồi gửi lệnh dịch tới cửa sổ đang chạy:

```bash
/home/minh-quan/projects/selection-translator-linux/selection-translator-shortcut
```

Kiểm tra riêng phần đọc selection:

```bash
python3 translator.py --debug-selection
```

Khi chạy bằng keyboard shortcut, log debug được ghi ở:

```bash
tail -n 50 /tmp/selection-translator.log
```

## Tạo Ubuntu Keyboard Shortcut

Mở:

```text
Settings -> Keyboard -> View and Customize Shortcuts -> Custom Shortcuts
```

Tạo shortcut mới:

```text
Name: Selection Translator
Command: /home/minh-quan/projects/selection-translator-linux/selection-translator-shortcut
Shortcut: Ctrl+Alt+Y
```

Sau đó bôi đen text ở ứng dụng bất kỳ và nhấn `Ctrl + Alt + Y`. Popup bản dịch sẽ hiện gần con trỏ chuột.

Nếu ứng dụng chưa chạy, script wrapper vẫn mở popup dịch một lần theo selection/clipboard hiện tại.

Có thể cấu hình shortcut bằng lệnh:

```bash
gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selection-translator/']"
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selection-translator/ name 'Selection Translator'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selection-translator/ command '/home/minh-quan/projects/selection-translator-linux/selection-translator-shortcut'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selection-translator/ binding '<Control><Alt>y'
```

Kiểm tra GNOME đã nhận shortcut:

```bash
gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings
gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/selection-translator/ binding
```

## Cấu trúc mã nguồn

```text
translator.py                 # Entry point cho shortcut
selection_translator/
  app.py                      # Điều phối đọc selection, dịch và UI
  clipboard.py                # Đọc Wayland/X11 selection hoặc clipboard
  config.py                   # Cấu hình chung
  translator_service.py       # Wrapper deep-translator
  ui.py                       # Floating panel bằng tkinter
```

## Phát triển

Kiểm tra cú pháp:

```bash
python3 -m py_compile translator.py selection_translator/*.py
```

Coding convention của dự án:

- Dùng 4 spaces cho indentation.
- Mỗi hàm/method phải có type hint cho tham số và return type.
- Mỗi hàm/method phải có docstring tiếng Việt theo Google style, gồm `Args` nếu có tham số và `Returns` cho kiểu trả về.
- Tách logic theo module, không dồn thêm tính năng mới vào `translator.py`.
