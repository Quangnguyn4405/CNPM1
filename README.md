# CO3093/CO3094 Assignment 1 — Hybrid Chat Application

Student ID: 2312794

Ứng dụng chat kết hợp Client-Server (HTTP) và Peer-to-Peer (TCP trực tiếp). Server tự xây dựng, không dùng thư viện ngoài. Hỗ trợ 3 chế độ non-blocking: threading, callback (selectors), coroutine (asyncio).

---

## Khởi động server

```bash
python start_chatapp.py
```

Mặc định bind `0.0.0.0:8000`. Nếu port bị chiếm thì đổi:

```bash
python start_chatapp.py --server-port 8080
```

Chờ đến khi thấy dòng `**ASYNC** listening on 0.0.0.0:8000` là server đã sẵn sàng.

---

## Tắt server

Windows:

```powershell
Get-Process python | Stop-Process -Force
```

---

## Mở giao diện

Mở trình duyệt, vào:

```
http://127.0.0.1:8000/chat.html
```

Mỗi người dùng nên mở một tab ẩn danh (Incognito) riêng để tránh xung đột cookie/cache.

---

## Tài khoản có sẵn

| Username | Password  |
|----------|-----------|
| admin    | admin123  |
| user1    | password1 |
| user2    | password2 |
| guest    | guest     |

---

## Các bước sử dụng

**1. Login**

Nhập username và password, nhấn Login. Server trả về `Set-Cookie` chứa session ID.

**2. Register Peer**

Mỗi người chọn một port riêng (ví dụ user1 dùng 7001, user2 dùng 7002), nhấn Register Peer. Bước này tạo TCP listener để nhận kết nối P2P.

**3. Get Peer List**

Nhấn Get Peer List để xem danh sách người đã register và port của họ.

**4. Connect to Peer**

Nhập IP và port của người kia (không phải port của mình), nhấn Connect. Kết nối TCP được thiết lập trực tiếp giữa hai peer, không đi qua server.

**5. Gửi tin nhắn**

- Broadcast — gửi cho tất cả peer đang kết nối.
- Send to Peer — gửi riêng cho một người (nhập IP:port của người đó).

Tin nhắn hiển thị dạng bubble: tin của mình bên phải, tin của người khác bên trái. Tự động cập nhật mỗi 3 giây.

**6. Get Messages**

Xem lịch sử tin nhắn theo channel. Mặc định là channel `general`.

**7. Logout**

Nhấn Logout để hủy session.

---

## Demo nhanh với 2 người

```
Bước 1: python start_chatapp.py

Tab A — login user1, Register Peer port 7001
Tab B — login user2, Register Peer port 7002

Tab A — Connect to Peer: 127.0.0.1 : 7002
Tab B — Connect to Peer: 127.0.0.1 : 7001

Tab A — Broadcast "hello"  →  Tab B nhận được
Tab B — Broadcast "hi"     →  Tab A nhận được
```

Thêm người thứ 3: mở tab ẩn danh mới, login tài khoản khác, Register Peer port 7003, rồi Connect tới port của từng người muốn chat.

---

## Demo P2P không qua server (standalone)

Chạy 2 terminal riêng, không cần server:

```bash
# Terminal 1
python run_peer.py --user alice --port 7001

# Terminal 2
python run_peer.py --user bob --port 7002
```

Trong Terminal 1:

```
connect 127.0.0.1 7002
send Xin chào Bob!
```

Terminal 2 sẽ nhận được tin nhắn ngay lập tức. Không có server nào chạy — hoàn toàn P2P.

Các lệnh trong `run_peer.py`:

| Lệnh | Mô tả |
|------|-------|
| `connect <ip> <port>` | Kết nối tới peer |
| `send <message>` | Broadcast tới tất cả peer đang kết nối |
| `status` | Xem danh sách peer đang kết nối |
| `quit` | Thoát |

---

## API

| Method | Endpoint        | Auth |
|--------|-----------------|------|
| POST   | /login          | Không |
| POST   | /logout         | Có   |
| POST   | /register       | Không |
| POST   | /submit-info    | Có   |
| GET    | /get-list       | Không |
| POST   | /connect-peer   | Có   |
| POST   | /broadcast-peer | Có   |
| POST   | /send-peer      | Có   |
| GET    | /channels       | Có   |
| GET    | /messages       | Có   |
| GET    | /notifications  | Có   |
| GET    | /peer-status    | Có   |

---

## Non-blocking modes

Cấu hình trong `daemon/backend.py`, biến `mode_async`:

- `"coroutine"` — asyncio + StreamReader/Writer (mặc định)
- `"callback"` — selectors.DefaultSelector
- `"threading"` — 1 thread mỗi connection

---

## Lỗi thường gặp

`OSError: [Errno 10048]` — port đang bị dùng, đổi port khác hoặc tắt server cũ.

`Could not connect` — peer kia chưa Register Peer hoặc nhập sai IP/port.

`Authentication required` — session hết hạn, login lại.

Tab thấy tin nhắn cũ — dùng tab ẩn danh mới hoặc xóa cache.
