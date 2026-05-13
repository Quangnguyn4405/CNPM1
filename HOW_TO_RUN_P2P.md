# Hướng dẫn chạy mô hình Decentralized Web Node (True P2P)

Mô hình này tách biệt hoàn toàn Server Trung Tâm (Tracker) và Web Client cá nhân (Local Node). Qua đó đảm bảo: **Tắt Server Trung Tâm thì 2 người dùng vẫn có thể chat P2P với nhau trên trình duyệt web**.

Dưới đây là các bước để chạy thử và kiểm chứng:

## 1. Khởi chạy Tracker Server (Sổ Danh Bạ)
Mở một cửa sổ Terminal (hoặc Command Prompt) mới, chạy lệnh sau:
```bash
python start_tracker.py --server-port 8000
```
*Bạn sẽ thấy màn hình báo Tracker Server đang lắng nghe ở cổng 8000.*

## 2. Khởi chạy Client A (Local Web Node của User 1)
Mở cửa sổ Terminal thứ 2, chạy:
```bash
python start_localnode.py --node-port 8001
```
*Client A lúc này sẽ cung cấp một giao diện web nội bộ ở cổng 8001.*
- Mở trình duyệt, truy cập `http://127.0.0.1:8001/chat.html`
- Đăng nhập tài khoản `user1`
- Nhập thông tin Register Peer (ví dụ IP `127.0.0.1`, Port `7001`). Bấm Register.
*(Local Node lúc này sẽ báo lên Tracker Server ở cổng 8000 rằng User1 đã online ở cổng 7001).*

## 3. Khởi chạy Client B (Local Web Node của User 2)
Mở cửa sổ Terminal thứ 3, chạy:
```bash
python start_localnode.py --node-port 8002
```
*Client B cung cấp giao diện web ở cổng 8002.*
- Mở một tab trình duyệt khác, truy cập `http://127.0.0.1:8002/chat.html`
- Đăng nhập tài khoản `user2`
- Nhập thông tin Register Peer (ví dụ IP `127.0.0.1`, Port `7002`). Bấm Register.

## 4. Kết nối và Chat (Qua Tracker)
- Trên Web của Client A (`8001`), bấm **Get Peer List** (Lúc này Client A gọi Tracker Server lấy danh sách, bạn sẽ thấy User2 ở cổng 7002).
- Nhập `127.0.0.1` và `7002` vào ô IP/Port kết nối của Client A. Bấm **Connect to Peer**.
- Chat thử qua lại, bạn sẽ thấy tin nhắn nhận được bình thường.

## 5. KIỂM CHỨNG: Tắt Tracker Server
Bây giờ, hãy quay lại **Terminal 1** (cửa sổ đang chạy `start_tracker.py`), bấm `Ctrl + C` để **tắt hoàn toàn Tracker Server**.

Tiếp tục mở giao diện web của Client A và Client B, gửi tin nhắn cho nhau (`Broadcast` hoặc `Send`).
=> **Kết quả:** Tin nhắn vẫn nhảy liên tục! Vì trình duyệt web của bạn vẫn đang tương tác với Server cá nhân (`localnode.py`), và Server cá nhân này đang giữ Socket TCP kết nối trực tiếp với Server cá nhân của người kia. Tracker Server đã hoàn thành nhiệm vụ của nó (làm mai mối) và việc nó chết không còn ảnh hưởng đến mạng P2P nữa.

curl.exe -v -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d '{\"username\":\"user1\",\"password\":\"password1\"}'

curl.exe -v -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d '{\"username\":\"admin\",\"password\":\"wrong\"}'