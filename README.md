# HCMUS Guide — Admission & Study Assistant

> **Dự án sinh viên CSC10014, không phải website chính thức của HCMUS.** Thông tin tuyển sinh phải được kiểm tra lại theo năm và nguồn trường công bố.

HCMUS Guide giúp học sinh tìm hiểu chương trình tuyển sinh, khám phá ngành học với AI có kiểm chứng và tự quản lý checklist chuẩn bị hồ sơ.

## Ba tính năng đang hoạt động

| Feature | Chức năng | Nguồn / lưu trữ |
| --- | --- | --- |
| **1. Verified Admissions Lookup** | Tra ngành, mã xét tuyển, tổ hợp, phương thức tuyển sinh theo năm | SQLite từ dữ liệu tuyển sinh HCMUS 2026 |
| **2. Major Exploration + Multi-turn Chat** | Hỏi theo sở thích, theo dõi ngữ cảnh nhiều lượt; truy xuất các ngành có nguồn rồi sử dụng Ollama giải thích | 39/39 bản tóm tắt chương trình, URL từ trang HCMUS / khoa; Ollama local tùy chọn |
| **3. Admissions Checklist** | Chọn năm 2025/2026, phương thức, nhánh THPT/ĐGNL; lưu tiến độ và việc cá nhân | `localStorage` trong trình duyệt, độc lập với chatbot |

Checklist là công cụ kế hoạch cá nhân, **không phải hướng dẫn pháp lý hay xác nhận đã nộp hồ sơ**. Với năm ngoài phạm vi dữ liệu, chatbot không tự bịa thông tin.

## Công nghệ và kiến trúc

```text
Browser (HTML/CSS/vanilla JavaScript)
     │
     ├── Checklist → browser localStorage (không cần tài khoản)
     │
     └── POST /api/chat → Node.js proxy (ui/server.mjs :5501)
                              │  HttpOnly per-browser session ID
                              ▼
                       FastAPI :8000
                         │       └─ Context (memory, TTL ~1 hour)
                         ▼
                 Intent router + Retrieval
                         │
                         ├─ SQLite (39 major records + verified program summaries)
                         └─ Ollama qwen3:4b :11434 (tùy chọn)
```

Câu trả lời có dẫn URL của HCMUS khi truy xuất được bằng chứng. Khi Ollama không chạy, chức năng tìm kiếm dữ liệu vẫn có cơ chế dự phòng.

## Chạy dự án trên macOS/Linux

**Yêu cầu:** Python 3.10+; Node.js 18+; Ollama nếu muốn AI local (không bắt buộc để thử tra cứu).

1. Clone GitHub và đi vào thư mục dự án:

   ```bash
   git clone https://github.com/vinhdu1233-tech/hcmus-admission-assistant.git
   cd hcmus-admission-assistant
   ```

   Nếu tính năng chưa merge vào `main`, chuyển sang branch `feat/mvp-sqlite-router`.

2. Cài Python và tạo dữ liệu:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements-backend-dev.txt
   cp .env.example .env
   python -m src.database.db
   python scripts/check_profiles_2026.py
   ```

   File `.env` là file **chỉ giữ trên máy** (đã có trong `.gitignore`). Không đưa API key, token lên GitHub.

3. **Tùy chọn AI local:** Cài Ollama từ https://ollama.com/download, mở app và chạy:

   ```bash
   ollama pull qwen3:4b
   ollama list
   ```

   Trong `.env`: `AI_PROVIDER=ollama`, `OLLAMA_MODEL=qwen3:4b`. Nếu không có Ollama, đặt `AI_PROVIDER=none` để dùng Retrieval mà không tạo nội dung AI. Không cần key hay tài khoản trả phí cho Ollama local.

4. Chạy FastAPI — Terminal 1:

   ```bash
   source .venv/bin/activate
   python -m uvicorn src.api.main:app --reload --port 8000
   ```

5. Chạy Frontend — Terminal 2:

   ```bash
   cd ui
   CHAT_MODE=api PORT=5501 npm start
   ```

6. Mở **http://localhost:5501**. Để quay về màn hình chat mới, nhấn **Trò chuyện mới** ở đầu cửa sổ hội thoại.

## Kiểm thử sản phẩm

Từ thư mục gốc repository, sau khi activate môi trường Python:

```bash
python scripts/check_mvp.py
```

Lệnh này chạy kiểm thử Backend/SQLite/Retrieval/multi-turn, Node proxy, các file UI và cấu hình Checklist. **AI trả lời thật bằng Ollama và việc lưu localStorage qua reload cần được thử thủ công trên trình duyệt.**

Các kịch bản xác nhận:
- Hỏi `Ngành nào xét A01?` rồi chỉ trả lời `2026` → tiếp tục câu hỏi và có nguồn.
- Hỏi `Em thích sinh học và hóa học, nên học ngành nào năm 2026?` → `lĩnh vực nghiên cứu` → tư vấn theo dữ liệu.
- Hỏi `Ngành thứ hai học gì?`, `So sánh hai ngành đầu`, `Còn học phí?` → không bịa dữ liệu.
- Ở **Checklist**, chọn 2026, phương thức 2, nhánh THPT; đánh dấu; refresh; chuyển qua nhánh ĐGNL và kiểm tra tiến độ riêng. Thử cả 2025; năm 2027 cần hiện rõ chưa xác minh.
- Dùng nút **Trò chuyện mới** để xóa ngữ cảnh cũ; hỏi lại câu rời `2026` không được sử dụng nội dung cuộc trò chuyện trước.
- Tắt Ollama để kiểm tra chế độ Retrieval dự phòng; kiểm tra giao diện Safari/Chrome và mobile.

## Phạm vi và giới hạn

- Dữ liệu tuyển sinh cấu trúc hiện có **39 ngành/nhóm ngành năm 2026**, cùng 39 bản tóm tắt giới thiệu chương trình có nguồn. Tóm tắt do nhóm biên soạn dựa trên trang HCMUS, **không phải nguyên văn toàn bộ chương trình đào tạo**.
- Một trang giới thiệu ngành Trí tuệ nhân tạo có mã khác với bảng xét tuyển 2026; file `data/curated/program_profiles_2026.json` ghi lại chênh lệch trong `review_flags`. Mã xét tuyển trong Database vẫn được bảo toàn.
- Điểm chuẩn, học phí và chính sách chưa có trong nguồn đã kiểm chứng không được tự suy đoán.
- Ngữ cảnh chatbot được lưu tạm theo session trong RAM FastAPI (không chia sẻ giữa nhiều tiến trình); Checklist chỉ lưu trong browser localStorage.
- Đây là hệ thống chạy local. Đưa giao diện lên web công khai **không tự động làm cho Ollama local có thể phục vụ người dùng khác**.

## Tài liệu kỹ thuật nội bộ

- [SQLite và Router](README_DATABASE_ROUTER.md)
- [Retrieval và Ollama](README_RAG.md)
- [Multi-turn conversation](README_MULTITURN.md)
- [Kiểm tra 3 Features](README_MVP_3_TASKS.md)

**Nguồn chính:** https://tuyensinh.hcmus.edu.vn/ và các website khoa trực thuộc HCMUS.
