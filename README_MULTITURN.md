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

**Ví dụ 4 — trả lời câu hỏi khám phá ngành mà AI vừa hỏi:**

```text
Bạn: Em thích Python và toán, nên học ngành nào năm 2026?
Bot: [Gợi ý ngành]. Bạn thích xây dựng ứng dụng, giải bài toán thuật toán hay phân tích dữ liệu?
Bạn: Phân tích dữ liệu
Bot: [Gợi ý mới theo nhóm Khoa học dữ liệu/Thống kê từ SQLite 2026,
      cùng nguồn HCMUS; không cần nhắc lại năm hay sở thích cũ]
Bạn: Còn xây dựng ứng dụng?
Bot: [Gợi ý theo hướng phần mềm/CNTT, vẫn thuộc năm 2026]
```

Hệ thống chỉ diễn giải lựa chọn ngắn nếu **cùng phiên đang thảo luận khám phá ngành**. Ba hướng trả lời nhanh được hỗ trợ: phát triển ứng dụng, thuật toán, phân tích dữ liệu. Ngoài ra, học sinh có thể nhắn sở thích ngắn khác như “sinh học” hay “thiết kế vi mạch”; chỉ khi Retrieval tìm được ngành tương ứng trong SQLite thì chatbot mới tiếp tục gợi ý. Nếu không tìm thấy bằng chứng, chatbot yêu cầu làm rõ thay vì bịa ngành. Không lấy ý tưởng do Ollama bịa thành thông tin tuyển sinh chính thức.

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


## Mở rộng: hội thoại mở không giới hạn ở ba từ khóa gợi ý

Bắt đầu từ câu trả lời AI như:
"Bạn thích hoạt động nào nhất trong lĩnh vực này để mình gợi ý sát hơn?"

Trên cùng phiên, học sinh có thể đáp:
- "lĩnh vực nghiên cứu", "mình thích làm thí nghiệm", "em muốn làm nghiên cứu trong phòng lab" — hệ thống giữ lĩnh vực từ câu trước, ưu tiên mô tả có bằng chứng nghiên cứu/thực hành và gợi ý chương trình HCMUS 2026.
- "xây dựng ứng dụng", "phân tích dữ liệu", "thuật toán", "sinh học", "thiết kế vi mạch" — thay đổi hướng khám phá theo ý mới, không cần nhập lại năm.
- "ngành thứ hai học gì?" — sử dụng đúng thứ tự ngành vừa hiển thị và mô tả nguồn HCMUS.
- "so sánh hai ngành đầu" — so sánh 2 mô tả chính thức, không tự bịa học phần.
- "ngành đó học gì?" khi hệ thống vừa hiển thị 3 ngành — phải hỏi rõ ngành nào.
- "còn học phí?" — nhớ năm, nhưng báo dữ liệu học phí chưa xác minh nếu không có nguồn.

Cơ chế: src/assistant/dialogue.py thử các quy tắc đơn giản trước, sau đó tùy chọn
dùng Ollama local để phân loại câu tiếp nối mơ hồ qua JSON schema; nó **không**
được phép tạo ngành, điểm hay chính sách tuyển sinh. Dù Ollama phân loại được ý
định, Retrieval/SQLite vẫn phải có nguồn cho câu trả lời chuyên ngành.
Tắt Ollama vẫn dùng được các trường hợp phổ biến theo quy tắc.

**Giới hạn:** Không thể bảo đảm trả lời chính xác *mọi* câu hỏi. Mảng dữ liệu chính
hiện là tuyển sinh 2026 và mô tả chương trình; học phí, điểm chuẩn ngoài phạm vi,
thông tin nghề nghiệp có số liệu chưa xác minh và câu hỏi mơ hồ sẽ được giải thích
giới hạn hoặc yêu cầu làm rõ, không tự bịa. Mỗi phiên lưu câu gần nhất, năm,
tối đa ba mã ngành đã gợi ý cùng câu hỏi tiếp theo, tự hết hạn sau một giờ.

Kiểm thử:

```bash
python -m pytest -q tests/test_conversation.py tests/test_interest_followup.py tests/test_flexible_dialogue.py
node --test tests/test_conversation_proxy.mjs
```
