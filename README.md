# Hybrid Chat Application — CO3093/CO3094 Assignment 1

**Student ID:** 2312794  
**Mô tả:** Ứng dụng chat kết hợp Client-Server (HTTP) và Peer-to-Peer (TCP trực tiếp), xây dựng trên framework AsynapRous tự viết với 3 chế độ non-blocking: threading, callback (selectors), coroutine (asyncio).

---

## Yêu cầu

- Python 3.9+
- Không cần cài thêm thư viện nào (chỉ dùng stdlib)

---

## Khởi động server

```bash
python start_chatapp.py
```

Mặc định server chạy tại `http://0.0.0.0:8000`.  
Để đổi port (ví dụ nếu 8000 đã bị dùng):

```bash
python start_chatapp.py --server-port 8080
```

Để chỉ định IP cụ thể:

```bash
python start_chatapp.py --server-ip 127.0.0.1 --server-port 8000
```

Khi server khởi động thành công, terminal sẽ hiển thị:

```
============================================================
  Hybrid Chat Application - CO3093/CO3094 Assignment 1
  Student ID: 2312794
============================================================
  Server: http://0.0.0.0:8000
  ...
[Backend] async_server **ASYNC** listening on 0.0.0.0:8000
```

---

## Mở giao diện chat

Sau khi server chạy, mở trình duyệt và truy cập:

```
http://127.0.0.1:8000/chat.html
```

> **Khuyến nghị:** Dùng tab ẩn danh (Incognito) để tránh cache trình duyệt gây lỗi.  
> Mỗi người dùng nên mở một tab ẩn danh riêng.

---

## Tài khoản có sẵn

| Username | Password  |
|----------|-----------|
| admin    | admin123  |
| user1    | password1 |
| user2    | password2 |
| guest    | guest     |

---

## Hướng dẫn sử dụng từng bước

### Bước 1 — Đăng nhập

1. Mở `http://127.0.0.1:8000/chat.html`
2. Nhập **Username** và **Password**
3. Nhấn **Login**
4. Kết quả: xuất hiện thông báo `Logged in as <username>`, session được lưu

> Server trả về `Set-Cookie: session_id=...` (RFC 6265) và giao diện tự lưu session.

---

### Bước 2 — Đăng ký Peer (Register Peer)

Mỗi người dùng cần đăng ký địa chỉ P2P của mình trước khi chat.

1. Điền **Peer Port** (ví dụ: `7001` cho user1, `7002` cho user2)
2. Peer IP để mặc định `127.0.0.1`
3. Nhấn **Register Peer**
4. Kết quả: server tạo một TCP listener tại port đó, sẵn sàng nhận kết nối P2P

> Mỗi người dùng phải dùng **port khác nhau**.  
> Ví dụ: user1 → port 7001, user2 → port 7002.

---

### Bước 3 — Xem danh sách Peer (Get Peer List)

1. Nhấn **Get Peer List**
2. Bảng danh sách hiện ra với username, IP, port của tất cả peer đã đăng ký

---

### Bước 4 — Kết nối P2P (Connect to Peer)

Để chat trực tiếp với một peer khác (không qua server):

1. Nhập **Target IP** (ví dụ: `127.0.0.1`)
2. Nhập **Target Port** — port của peer **kia** (ví dụ: user1 nhập `7002` để kết nối user2)
3. Nhấn **Connect to Peer**
4. Kết quả: `Connected to 127.0.0.1:7002`

> **Lưu ý quan trọng:**  
> - Phải nhập port của **người kia**, không phải port của mình.  
> - Ví dụ: user1 (port 7001) muốn kết nối user2 (port 7002) → nhập `7002`.  
> - user2 muốn kết nối user1 → nhập `7001`.

---

### Bước 5 — Kiểm tra trạng thái kết nối (Peer Status)

1. Nhấn **Peer Status**
2. Hiển thị danh sách các peer đang kết nối, username, địa chỉ

---

### Bước 6 — Chat

#### Broadcast (gửi cho tất cả peer đã kết nối)

1. Nhập tin nhắn vào ô **Message**
2. Chọn channel (mặc định: `general`)
3. Nhấn **Broadcast**
4. Tất cả peer đã kết nối đều nhận được tin nhắn

#### Send to Specific Peer (gửi riêng cho 1 peer)

1. Nhập **Target IP** và **Target Port** của peer muốn gửi
2. Nhập **Message**
3. Nhấn **Send to Peer**

---

### Bước 7 — Xem tin nhắn (Messages)

1. Nhập tên channel (mặc định: `general`)
2. Nhấn **Get Messages**
3. Danh sách tin nhắn hiện ra theo thứ tự thời gian

---

### Bước 8 — Notifications

- Nhấn **Get Notifications** để lấy tin nhắn mới nhất chưa đọc
- Thông báo tự xóa sau khi đọc

---

### Bước 9 — Đăng xuất

1. Nhấn **Logout**
2. Session bị hủy, không thể gửi tin nhắn nữa cho đến khi đăng nhập lại

---

## Kịch bản demo 2 người dùng

```
Terminal:  python start_chatapp.py --server-port 8080

Tab A (user1):
  → Mở http://127.0.0.1:8080/chat.html (tab ẩn danh)
  → Login: user1 / password1
  → Register Peer: port 7001
  → Get Peer List (thấy user1)

Tab B (user2):
  → Mở http://127.0.0.1:8080/chat.html (tab ẩn danh mới)
  → Login: user2 / password2
  → Register Peer: port 7002
  → Get Peer List (thấy user1 và user2)

Tab A:
  → Connect to Peer: IP=127.0.0.1, Port=7002  ← port của user2
  → Peer Status: thấy user2 đã kết nối

Tab B:
  → Connect to Peer: IP=127.0.0.1, Port=7001  ← port của user1
  → Peer Status: thấy user1 đã kết nối

Tab A:
  → Broadcast: "Xin chào user2!"
  → Tab B nhận được tin nhắn

Tab B:
  → Broadcast: "Xin chào user1!"
  → Tab A nhận được tin nhắn
```

---

## API Endpoints

| Method | Endpoint         | Mô tả                                 | Auth cần? |
|--------|------------------|---------------------------------------|-----------|
| POST   | /login           | Đăng nhập, trả về session cookie      | Không     |
| POST   | /logout          | Hủy session                           | Có        |
| GET    | /users           | Danh sách user (debug)                | Không     |
| POST   | /register        | Tạo tài khoản mới                     | Không     |
| POST   | /submit-info     | Đăng ký địa chỉ P2P với tracker       | Có        |
| GET    | /get-list        | Lấy danh sách peer từ tracker         | Không     |
| POST   | /add-list        | Thêm peer vào tracker                 | Không     |
| POST   | /connect-peer    | Kết nối TCP trực tiếp tới peer        | Có        |
| POST   | /broadcast-peer  | Gửi tin nhắn tới tất cả peer          | Có        |
| POST   | /send-peer       | Gửi tin nhắn tới 1 peer cụ thể        | Có        |
| GET    | /channels        | Danh sách channel đã tham gia         | Có        |
| GET    | /messages        | Lấy tin nhắn theo channel             | Có        |
| GET    | /notifications   | Lấy thông báo tin nhắn mới            | Có        |
| GET    | /peer-status     | Trạng thái kết nối P2P hiện tại       | Có        |

---

## Kiến trúc Non-blocking

Server hỗ trợ 3 chế độ non-blocking (cấu hình trong `daemon/backend.py`):

| Chế độ     | Cơ chế                          | Biến `mode_async` |
|------------|---------------------------------|-------------------|
| threading  | 1 thread / connection           | `"threading"`     |
| callback   | `selectors.DefaultSelector`     | `"callback"`      |
| coroutine  | `asyncio` + StreamReader/Writer | `"coroutine"`     |

Mặc định dùng `"coroutine"`. Route handlers đồng bộ được chạy qua `loop.run_in_executor()` để không block event loop.

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `OSError: [Errno 10048]` | Port đang bị dùng bởi process khác | Đổi port: `--server-port 8080` |
| `Could not connect to 127.0.0.1:XXXX` | Peer kia chưa Register hoặc dùng sai port | Kiểm tra port trong Get Peer List |
| `Peer not initialized` | Chưa Register Peer trước khi Connect/Chat | Thực hiện Register Peer (Bước 2) |
| `Authentication required` | Session hết hạn hoặc chưa đăng nhập | Đăng nhập lại |
| Tab mới thấy tin nhắn cũ | Browser cache | Dùng tab ẩn danh mới |
