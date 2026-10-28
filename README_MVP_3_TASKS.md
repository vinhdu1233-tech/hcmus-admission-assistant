# HCMUS Guide — 3 việc cần làm trước khi demo

## 1) Câu trả lời AI tự nhiên + nguồn

- `src/assistant/ai.py`: Ollama nhận 5 ứng viên từ retrieval, có mô tả HCMUS đã kiểm chứng (nếu có). Prompt yêu cầu mỗi ngành chỉ 1–2 câu, không nhắc trực tiếp đến tags và tránh lặp cùng lý do.
- `src/assistant/router.py`: hiển thị tối đa 3 ngành, lý do ngắn, câu hỏi tiếp theo về sở thích; gắn nguồn riêng của chương trình được xác minh, và đường dẫn bảng tuyển sinh HCMUS.
- Nếu `AI_PROVIDER=ollama` chạy được thì dùng Qwen3 local; không có AI thì trả fallback từ dữ liệu. Không có key/chi phí cloud.
- Quan trọng: các ngành chưa có `official_profile` chỉ là gợi ý theo **tên ngành + tags của nhóm**, không được nói có căn cứ về học phần hay việc làm.

Mở `.env` local:

```dotenv
AI_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
```

Cảnh báo **Frontend do bạn sửa cục bộ**: file `ui/app.js` trong GitHub vẫn có `setTimeout(()=>controller.abort(),16000)`, chỉ 16 giây. Để Ollama có thời gian trả lời, trong **file app.js trên máy bạn**, đổi đúng dòng đó thành:

```javascript
const timeout=setTimeout(()=>controller.abort(),125000);
```

Chỉ đổi số timeout, **không ghi đè** các thay đổi giao diện đang staged trên máy. Node proxy đã có timeout dài hơn.

## 2) Mở rộng 39 mô tả chính thức

Khác biệt quan trọng:
- 39/39 là **ngành/nhóm ngành trong bảng tuyển sinh** (`data/curated/majors_2026.json`).
- Đã thêm **34 mô tả ngành/nhóm ngành còn thiếu** (tổng **39/39 mô tả**), mỗi mô tả có URL trên website tuyển sinh HCMUS hoặc trang khoa chính thức. Đây là bản tóm tắt để tham khảo, không phải toàn văn chương trình đào tạo.
- **Trí tuệ nhân tạo:** mã xét tuyển `7480107` trùng bảng năm 2026 và quyết định mở ngành, nhưng trang chi tiết khác ghi `7480207`. Chỉ dùng phần giới thiệu ngành mới của trường để tóm tắt; lưu sai khác trong `review_flags`, không tự ý đổi mã tuyển sinh.

Nguồn:
- Bảng xét tuyển 2026: https://tuyensinh.hcmus.edu.vn/2026-thong-tin-tuyen-sinh/
- Nguồn các khoa: https://math.hcmus.edu.vn/ và https://phys.hcmus.edu.vn/
- Danh mục các khoa/ngành: https://tuyensinh.hcmus.edu.vn/khoa-dao-tao/

Cài BeautifulSoup để đọc HTML:

```bash
source .venv/bin/activate
python -m pip install beautifulsoup4
```

Tự rà soát 39 ngành với catalog:

```bash
python scripts/discover_program_profiles.py
# Nếu muốn lấy thêm đoạn văn tham khảo từ từng trang:
python scripts/discover_program_profiles.py --fetch-excerpts
```

Tool ghi dữ liệu vào `data/processed/program_profile_candidates_2026.json`. **Chỉ là đề xuất chưa xác minh**:
1. Mở từng `matches[].url`, xem trang có đúng ngành/chương trình và mã tuyển sinh hay không.
2. Đối chiếu tên và các hậu tố `_TT`, `_DKD`, `_NN`; với nhóm ngành không nhầm trang của một chuyên ngành đơn lẻ.
3. Tóm tắt ngắn bằng ngôn ngữ của bạn, bám sát thông tin trên trang; không chép nguyên nhiều đoạn.
4. Khi đã đối chiếu, thêm vào mảng `profiles` trong `data/curated/program_profiles_2026.json` theo mẫu:

```json
{
  "code": "CODE_CUA_BANG_TUYEN_SINH_2026",
  "summary": "Nội dung tóm tắt đã đối chiếu theo URL chương trình...",
  "source_url": "https://tuyensinh.hcmus.edu.vn/duong-dan-da-kiem-tra/",
  "reviewed_on": "2026-10-28"
}
```

**KHÔNG copy file review candidates vào curated**. Python importer chỉ nhập các profile có `reviewed_on` và URL cổng tuyển sinh hợp lệ. Chạy `python -m src.database.db` sau khi cập nhật JSON.

Kiểm tra DBeaver:

```sql
SELECT COUNT(*) AS majors FROM majors WHERE year=2026;
SELECT COUNT(*) AS verified_profiles FROM program_profiles WHERE year=2026;
SELECT m.code, m.name, p.summary, p.source_url
FROM majors m
LEFT JOIN program_profiles p
  ON p.year=m.year AND p.major_code=m.code
WHERE m.year=2026
ORDER BY m.name;
```

## 3) Kiểm thử ba Feature

Tại thư mục gốc repository:

```bash
source .venv/bin/activate
python -m pip install -r requirements-backend-dev.txt
python -m src.database.db
python scripts/check_mvp.py
```

Chương trình này chạy các tests backend và mock AI **không gọi OpenAI, Gemini hoặc Ollama thật**. Nếu có cả `ui/admission-methods.js` và `tests/test_planner_methods.mjs` trên Mac, nó cũng chạy Node tests Feature 3; nếu không, nó ghi rõ chưa thể xác nhận Feature 3 (không báo pass giả).

Lưu ý: Hai file Feature 3 hiện **chưa xuất hiện trong branch GitHub PR #13**, mặc dù bạn có thể đã tạo chúng trên Mac ở trạng thái untracked. Bạn cần review, test, commit chúng trước khi coi 3 Feature là hoàn tất để nộp.

Sau đó thực hiện E2E browser thủ công:
1. Bật Ollama, FastAPI ở port 8000, Node ở port 5501 với `CHAT_MODE=api`.
2. Feature 1: Hỏi "Ngành nào xét A01 năm 2026?" → ngành + link HCMUS; thử 2027 → từ chối khi thiếu dữ liệu.
3. Feature 2: Hỏi sở thích lập trình/toán → 3 gợi ý + nguồn giới thiệu ngành khi có; thử bóng đá/nấu ăn → câu hỏi làm rõ.
4. Feature 3: chọn năm/phương thức xét tuyển → checklist khác nhau; tick một mục, tải lại trang, kiểm tra `localStorage` vẫn lưu; đổi phương thức và kiểm tra tiến độ độc lập.
5. Thử giao diện mobile; xem Console và Network trong Safari/Chrome DevTools.

## Đồng bộ code an toàn

Vì `ui/app.js`, `ui/index.html`, `ui/style.css` và docs có thể vẫn đang modified/staged trên Mac:
- `git status` trước.
- Nếu pull báo xung đột, commit phần đang làm hoặc stash **có kiểm soát**; không dùng `git reset --hard`.
- Đặc biệt giữ `.env` ngoài git; khóa API từng bị chia sẻ cần revoke dù bạn đã chuyển Ollama.
