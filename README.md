# CO3093/CO3094 Assignment 1 — Hybrid Chat Application

Student ID: 2312794

Ứng dụng chat kết hợp Client-Server (HTTP) và Peer-to-Peer (TCP trực tiếp). Server tự xây dựng, không dùng thư viện ngoài, hỗ trợ 3 chế độ non-blocking: threading, callback (selectors), coroutine (asyncio).

---

## Chạy server

```bash
python start_chatapp.py
```

Mặc định bind `0.0.0.0:8000`. Nếu port bị chiếm:

```bash
python start_chatapp.py --server-port 8080
```

Khi thấy dòng `async_server **ASYNC** listening on 0.0.0.0:8000` là server đã sẵn sàng.

---

## Giao diện

Mở trình duyệt, vào `http://127.0.0.1:8000/chat.html`.

Nên dùng tab ẩn danh (Incognito) để tránh cache. Mỗi người dùng mở một tab ẩn danh riêng.

---

## Tài khoản có sẵn

| Username | Password  |
|----------|-----------|
| admin    | admin123  |
| user1    | password1 |
| user2    | password2 |
| guest    | guest     |

---

## Cách dùng

**1. Login** — nhập username/password, nhấn Login.

**2. Register Peer** — mỗi người chọn một port riêng (ví dụ user1 dùng 7001, user2 dùng 7002), nhấn Register Peer. Bước này tạo TCP listener cho P2P.

**3. Get Peer List** — xem danh sách người đã register.

**4. Connect to Peer** — nhập IP và port của *người kia* (không phải port của mình), nhấn Connect. Kết nối TCP được thiết lập trực tiếp, không qua server.

**5. Chat** — Broadcast gửi cho tất cả peer đang kết nối. Send to Peer gửi riêng cho một người.

**6. Get Messages** — xem lịch sử tin nhắn theo channel.

**7. Logout** — hủy session.

---

## Demo nhanh với 2 người

```
python start_chatapp.py --server-port 8080

Tab A — login user1, Register Peer port 7001
Tab B — login user2, Register Peer port 7002

Tab A — Connect to Peer: 127.0.0.1:7002
Tab B — Connect to Peer: 127.0.0.1:7001

Tab A — Broadcast "hello"  →  Tab B nhận được
Tab B — Broadcast "hi"     →  Tab A nhận được
```

Muốn thêm người thứ 3: mở tab ẩn danh mới, login tài khoản khác, Register Peer port 7003, rồi Connect tới port của từng người cần chat.

---

## API

| Method | Endpoint        | Yêu cầu auth |
|--------|-----------------|--------------|
| POST   | /login          | Không        |
| POST   | /logout         | Có           |
| POST   | /register       | Không        |
| POST   | /submit-info    | Có           |
| GET    | /get-list       | Không        |
| POST   | /connect-peer   | Có           |
| POST   | /broadcast-peer | Có           |
| POST   | /send-peer      | Có           |
| GET    | /channels       | Có           |
| GET    | /messages       | Có           |
| GET    | /notifications  | Có           |
| GET    | /peer-status    | Có           |

---

## Non-blocking modes

Cấu hình trong `daemon/backend.py`, biến `mode_async`:

- `"coroutine"` — asyncio + StreamReader/Writer (mặc định)
- `"callback"` — selectors.DefaultSelector
- `"threading"` — 1 thread mỗi connection

---

## Lỗi thường gặp

`OSError: [Errno 10048]` — port đang bị dùng, đổi port khác.

`Could not connect` — peer kia chưa Register Peer hoặc nhập sai port.

`Authentication required` — session hết hạn, login lại.

Tab thấy tin nhắn cũ — xóa cache hoặc dùng tab ẩn danh mới.
