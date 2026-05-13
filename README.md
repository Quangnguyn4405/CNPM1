# CO3093/CO3094 Assignment 1 — Hybrid Chat Application

**Student ID:** 2312794

Ứng dụng chat kết hợp **Client-Server** (HTTP) và **Peer-to-Peer** (TCP trực tiếp). Toàn bộ server tự xây dựng bằng Python thuần, không dùng thư viện ngoài. Hỗ trợ 3 chế độ non-blocking: threading, callback (selectors), coroutine (asyncio).

---

## Tài khoản có sẵn

| Username | Password  |
|----------|-----------|
| admin    | admin123  |
| user1    | password1 |
| user2    | password2 |
| guest    | guest     |

---

## Phương pháp 1 — Hybrid Server (1 server dùng chung)

Tất cả người dùng kết nối vào cùng một server HTTP trung tâm. Server xử lý auth, peer discovery và serve giao diện web. Các peer chat P2P trực tiếp qua TCP, nhưng web UI phụ thuộc server trung tâm.

### Khởi chạy

```bash
python start_chatapp.py
```

Mặc định bind `0.0.0.0:8000`. Đổi port nếu bị chiếm:

```bash
python start_chatapp.py --server-port 8080
```

Khi thấy dòng `async_server **ASYNC** listening on 0.0.0.0:8000` là server sẵn sàng.

### Truy cập

`http://127.0.0.1:8000/login.html`.

Mở trình duyệt, vào `http://127.0.0.1:8000/chat.html`.

> Nên dùng **tab ẩn danh (Incognito)** để tránh xung đột session/cache. Mỗi người dùng mở một tab ẩn danh riêng.

### Demo nhanh với 2 người

```
Terminal:  python start_chatapp.py

Tab A (Incognito) → http://127.0.0.1:8000/chat.html
  1. Login: user1 / password1
  2. Register Peer: IP 127.0.0.1, Port 7001 → bấm Register
  3. Connect to Peer: IP 127.0.0.1, Port 7002 → bấm Connect

Tab B (Incognito) → http://127.0.0.1:8000/chat.html
  1. Login: user2 / password2
  2. Register Peer: IP 127.0.0.1, Port 7002 → bấm Register
  3. Connect to Peer: IP 127.0.0.1, Port 7001 → bấm Connect

→ Broadcast hoặc Send Direct để chat qua lại.
```

Thêm người thứ 3: mở tab ẩn danh mới, login tài khoản khác, Register Peer port 7003, Connect tới port của từng người.

---

## Phương pháp 2 — True P2P / Decentralized (Khuyến nghị để chứng minh P2P)

Mỗi người dùng chạy **web server riêng (Local Node)**. Tracker Server chỉ đóng vai trò "sổ danh bạ" để tìm nhau lần đầu. Sau khi đã kết nối TCP P2P, **tắt Tracker Server đi vẫn chat được bình thường**.

### Kiến trúc

```
[Tracker :8000]  ←── chỉ dùng khi tìm peer, có thể tắt sau khi connect
     ↑ ↑
     │ │  (đăng ký & lấy danh sách)
     │ │
[LocalNode A :8001]  ←──── TCP P2P trực tiếp ────→  [LocalNode B :8002]
  (web của user1)                                      (web của user2)
```

### Bước 1 — Khởi chạy Tracker Server

Mở **Terminal 1**:

```bash
python start_tracker.py --server-port 8000
```

### Bước 2 — Khởi chạy Local Node cho từng người dùng

Mở **Terminal 2** (User 1):

```bash
python start_localnode.py --node-port 8001
```

Mở **Terminal 3** (User 2):

```bash
python start_localnode.py --node-port 8002
```

Thêm User 3 (nếu cần), mở **Terminal 4**:

```bash
python start_localnode.py --node-port 8003
```

### Bước 3 — Đăng nhập và thiết lập Peer

**User 1** — Mở trình duyệt, vào `http://127.0.0.1:8001/chat.html`:
1. Login: `user1` / `password1`
2. Register Peer: IP `127.0.0.1`, Port `7001` → bấm **Register**
3. Bấm **Get Peer List** để xem danh sách peer đã đăng ký

**User 2** — Mở tab/trình duyệt khác, vào `http://127.0.0.1:8002/chat.html`:
1. Login: `user2` / `password2`
2. Register Peer: IP `127.0.0.1`, Port `7002` → bấm **Register**

### Bước 4 — Kết nối P2P và Chat

Trên giao diện của User 1:
- Target IP: `127.0.0.1`, Target Port: `7002` → bấm **Connect**

Trên giao diện của User 2:
- Target IP: `127.0.0.1`, Target Port: `7001` → bấm **Connect**

Sau đó dùng **Broadcast** (gửi tất cả) hoặc **Send Direct** (gửi riêng) để chat.

### Bước 5 — Kiểm chứng True P2P

Quay lại **Terminal 1**, bấm `Ctrl+C` để **tắt hoàn toàn Tracker Server**.

Tiếp tục gửi tin nhắn giữa User 1 và User 2 → **tin nhắn vẫn nhận được bình thường**, vì TCP socket P2P đã được giữ trực tiếp giữa hai Local Node. Tracker đã hoàn thành vai trò "mai mối" và không còn cần thiết nữa.

---

## So sánh hai phương pháp

| | Hybrid Server | True P2P |
|---|---|---|
| Số terminal cần mở | 1 | 1 + N người dùng |
| Cách truy cập | Tất cả vào cùng 1 URL | Mỗi người 1 URL riêng |
| Phụ thuộc server trung tâm | Có (web UI) | Chỉ khi tìm peer lần đầu |
| Tắt server → mất chat? | Có | Không (nếu đã connect) |
| Phù hợp để demo nhanh | ✅ | ❌ |
| Chứng minh True P2P | ❌ | ✅ |

---

## Tính năng Chat

- **Channel**: tạo channel mới, list và chuyển channel bằng click
- **Broadcast**: gửi tin nhắn đến tất cả peer đang kết nối
- **Send Direct**: gửi riêng đến một peer theo IP:Port
- **Auto-refresh**: tin nhắn tự cập nhật mỗi 3 giây
- **Bubble UI**: tin của mình hiện bên phải (xanh), của người khác bên trái

---

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | /login | Serve trang đăng nhập |
| POST | /login | Xác thực, trả `session_id` + `Set-Cookie` |
| POST | /logout | Hủy session |
| POST | /register | Tạo tài khoản mới |
| POST | /change-password | Đổi mật khẩu |
| GET | /users | Danh sách tài khoản |
| POST | /submit-info | Đăng ký peer (IP, port) với tracker |
| GET | /get-list | Lấy danh sách peer đang online |
| POST | /connect-peer | Kết nối TCP P2P tới peer khác |
| POST | /broadcast-peer | Gửi tin nhắn tới tất cả peer |
| POST | /send-peer | Gửi tin nhắn tới một peer cụ thể |
| GET | /peer-status | Trạng thái kết nối P2P hiện tại |
| GET | /channels | Danh sách channel |
| POST | /create-channel | Tạo channel mới |
| GET | /messages | Lịch sử tin nhắn theo channel |

---

## Non-blocking Modes

Cấu hình trong `daemon/backend.py`, biến `mode_async`:

| Mode | Cơ chế | Mặc định |
|------|--------|----------|
| `"coroutine"` | asyncio + StreamReader/Writer | ✅ |
| `"callback"` | selectors.DefaultSelector | |
| `"threading"` | 1 thread mỗi connection | |

---

## Cấu trúc dự án

```
├── start_chatapp.py       # Khởi động Phương pháp 1 (Hybrid)
├── start_tracker.py       # Khởi động Tracker (Phương pháp 2)
├── start_localnode.py     # Khởi động Local Node (Phương pháp 2)
├── apps/
│   ├── chatapp.py         # Logic Hybrid Server
│   ├── localnodeapp.py    # Logic Local Node
│   └── trackerapp.py      # Logic Tracker
├── daemon/
│   ├── asynaprous.py      # Framework routing (tự xây)
│   ├── backend.py         # TCP server, 3 non-blocking modes
│   ├── httpadapter.py     # HTTP parser + static file serving
│   ├── peer.py            # PeerNode — TCP P2P
│   ├── auth.py            # Session, Basic Auth
│   └── utils.py           # Utilities
└── www/
    ├── chat.html          # Giao diện chat chính
    └── login.html         # Trang đăng nhập
```

---

## Lỗi thường gặp

**`OSError: [Errno 10048]`** — Port đang bị chiếm, đổi port khác.

**`Could not connect`** — Peer kia chưa Register hoặc nhập sai IP/Port. Đảm bảo điền đúng port của *người kia*, không phải port của mình.

**`Authentication required`** — Session hết hạn, login lại.

**`Peer not initialized`** — Chưa bấm Register Peer trước khi chat.

**Tin nhắn cũ vẫn hiện** — Xóa cache hoặc dùng tab ẩn danh mới.
