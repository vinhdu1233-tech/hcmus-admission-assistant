# HCMUS Guide — Chatbot hiểu hội thoại nhiều lượt (Multi-turn Context)

## Vấn đề trước đây

FastAPI nhận mỗi câu `message` độc lập. Khi hỏi “Ngành nào A01?” hệ thống hỏi tiếp năm, nhưng câu trả lời ngắn “2026” bị xử lý như một câu mới không có ngữ cảnh.

## Cơ chế mới

Browser (không sửa giao diện) -> Node proxy `ui/server.mjs` tự tạo cookie phiên `hcmus_sid` là UUID ngẫu nhiên, `HttpOnly`, `SameSite=Lax`. Node gửi `conversation_id` đi cùng câu hỏi qua `POST /chat` của FastAPI. `src/assistant/conversation.py` giữ những thông tin tối thiểu trong RAM:
- câu hỏi gần nhất đang chờ hoặc vừa xử lý
- năm đã xác nhận
- có đang chờ người dùng cung cấp năm hay không

**Ví dụ 1 — hỏi thiếu năm:**

```text
Bạn: Ngành nào xét tuyển A01?
Bot: Bạn muốn tra cứu năm tuyển sinh nào?
Bạn: 2026
Bot: Các ngành/nhóm ngành xét A01 năm 2026 ... [dữ liệu SQLite + nguồn HCMUS]
```

**Ví dụ 2 — đổi tổ hợp nhưng giữ năm:**

```text
Bạn: Ngành nào xét A01 năm 2026?
Bot: ...A01 năm 2026...
Bạn: Còn B00 thì sao?
Bot: ...B00 năm 2026...
```

**Ví dụ 3 — đổi năm:**

```text
Bạn: Ngành nào xét A01 năm 2026?
Bot: ...
Bạn: Còn năm 2027?
Bot: Chưa có dữ liệu được xác minh cho 2027.
Bạn: 2026 nhé
Bot: ...A01 năm 2026...
```

**Reset:** nhắn `bắt đầu lại` hoặc `reset` để quên câu hỏi gần nhất của phiên. Phiên tự hết hạn sau **1 giờ** không hoạt động hoặc khi FastAPI khởi động lại. Tối đa 500 phiên được giữ trong RAM; không lưu lịch sử chat hay dữ liệu cá nhân vào SQLite.

## Chạy trên Mac (sau khi đã lưu thay đổi cục bộ)

```bash
cd ~/Downloads/hcmus-admission-assistant
git status
git pull --ff-only origin feat/mvp-sqlite-router
source .venv/bin/activate
python -m pytest -q tests/test_conversation.py
node --test tests/test_conversation_proxy.mjs
```

Nếu `git pull` bị chặn bởi thay đổi chưa commit, lưu/commit các file đó trước; **không dùng `git reset --hard`** và không xóa UI đã sửa.

Khởi động lại (bắt buộc vì Backend và Node proxy đều đã thay đổi):

- Terminal 1: `python -m uvicorn src.api.main:app --reload --port 8000`
- Terminal 2: `cd ui && CHAT_MODE=api PORT=5501 npm start`

Sau đó mở `http://localhost:5501`, thử cuộc trò chuyện A01 → 2026 → B00. Trình duyệt tự gửi cookie trong cùng origin. Không cần đưa `conversation_id` vào `ui/app.js`.

### Test bằng curl (kiểm tra chính xác session cookie)

Chạy Node & FastAPI như trên. Trong Terminal thứ ba:

```bash
COOKIE_JAR=$(mktemp)
curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Ngành nào xét A01?"}' \
  http://127.0.0.1:5501/api/chat | python3 -m json.tool

curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d '{"message":"2026","admission_year":2026}' \
  http://127.0.0.1:5501/api/chat | python3 -m json.tool

rm -f "$COOKIE_JAR"
```

**Backward compatibility:** Gọi trực tiếp FastAPI mà không gửi `conversation_id` vẫn hoạt động, nhưng sẽ không nhớ câu trước. API nhận `conversation_id` UUID tuỳ chọn. Node quản lý mã phiên từ cookie; người dùng không cần nhập UUID.

**Giới hạn MVP:** ngữ cảnh chỉ nhớ các mốc ngắn và một câu hỏi gần nhất, không phải hội thoại tự do với trí nhớ dài hạn; các phiên chia sẻ giữa nhiều tab cùng trình duyệt; restart Backend hoặc chạy nhiều workers không chia sẻ RAM. Để triển khai công khai nhiều server, chuyển state sang Redis/DB với TTL, xác thực người dùng nếu có dữ liệu cá nhân, thêm nút “Trò chuyện mới” và chính sách bảo vệ dữ liệu. Câu trả lời về tuyển sinh vẫn phải dùng dữ liệu HCMUS đã kiểm chứng, không dùng AI tự suy đoán năm khác.
