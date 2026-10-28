# HCMUS MVP — SQLite Database + Router

## Lý do chọn SQLite

Với MVP, `sqlite3` đã tích hợp trong Python: không cần MySQL, Docker hoặc dịch vụ cloud. Có thể mở file `.sqlite3` bằng DBeaver (chọn SQLite driver). MySQL phù hợp để học quản trị/triển khai nhiều người dùng, nhưng không cần cho demo cục bộ.

## Cài đặt trong repo

1. Sao lưu `src/api/main.py` (bản cập nhật sẽ thay thế file này).
2. Copy toàn bộ `src/`, `data/curated/`, `tests/test_db_router.py` từ gói vào thư mục gốc repo.
3. Môi trường Python 3.10+: `source .venv/bin/activate` và `python -m pip install -r requirements-backend-dev.txt`.
4. Database tự khởi tạo khi Backend nhận request lần đầu, hoặc chủ động chạy:
   `python -m src.database.db`
5. Chạy test: `python -m pytest -q tests/test_api_smoke.py tests/test_db_router.py`.
6. Chạy API ở repo root: `python -m uvicorn src.api.main:app --reload --port 8000`.
7. Chạy Node.js trong terminal khác: `cd ui && CHAT_MODE=api PORT=5501 npm start`.
8. Mở http://localhost:5501/ và thử: `Ngành nào xét A01 năm 2026?`, `Các phương thức tuyển sinh năm 2026?`, `Em thích lập trình và toán, nên chọn ngành nào năm 2026?`.

## Schema

- `sources`: nguồn URL HCMUS, năm, ngày kiểm chứng.
- `majors`: mã ngành/nhóm ngành, tên, chỉ tiêu công bố, năm, tags gợi ý (tags là phân loại của nhóm, không phải phát biểu chính thức của trường).
- `major_combinations`: mã ngành và tổ hợp xét tuyển (lọc SQL theo năm + mã tổ hợp).
- `admission_methods`: 1a/1b/2 cho 2026, URL thông báo.

Các truy vấn dùng SQL có tham số (`?`) để tránh SQL injection. DB tạo ở `data/processed/hcmus.sqlite3` và không commit vì `.gitignore` đã bỏ qua `*.sqlite3`. Chỉ commit `data/curated/majors_2026.json` và code để máy khác tự tạo DB.

## Phạm vi dữ liệu hiện tại

**13 / 39 ngành/nhóm ngành 2026**, chọn từ bảng HCMUS cập nhật 10/7/2026: https://tuyensinh.hcmus.edu.vn/2026-thong-tin-tuyen-sinh/. Dữ liệu mẫu đủ để trình diễn tìm ngành theo A01, nhưng KHÔNG phải toàn bộ danh sách hoặc căn cứ xét đủ điều kiện. Mỗi record gắn nguồn trong DB. Các phương thức tuyển sinh 2026 có link thông báo HCMUS chính thức.

**Feature 2 hiện dùng keyword matching deterministic**, không phải LLM. Khi triển khai Retrieval/AI ở bước tiếp theo, cần dùng mô tả chương trình đào tạo đã kiểm chứng trước khi đưa ra khuyến nghị sâu.

**Feature 3 checklist** nằm ở Frontend Node.js riêng (localStorage) và không cần Database để demo.

## DBeaver thao tác nhanh

1. Mở DBeaver → Database → New Database Connection → SQLite (tải driver nếu được yêu cầu).
2. Database File → chọn `data/processed/hcmus.sqlite3` trong repo sau khi đã khởi tạo.
3. Chọn `SQL Editor` và chạy:

```sql
SELECT code, name, quota FROM majors WHERE year=2026 LIMIT 10;
SELECT m.name, c.combination
FROM majors m
JOIN major_combinations c ON m.year=c.year AND m.code=c.major_code
WHERE m.year=2026 AND c.combination='A01';
SELECT code, name, summary FROM admission_methods WHERE year=2026;
```

**Chú ý:** Sau khi tải ZIP vào repo phải khởi tạo DB mới (nếu không có). DBeaver dùng để xem và truy vấn; không cần Docker hoặc MySQL. Đừng tự ý tạo các bản ghi không có nguồn chỉ để được kết quả.

## Thay đổi so với test cũ

`tests/test_api_smoke.py` cập nhật 1 kỳ vọng: truy vấn `HCMUS có ngành nào năm 2026?` giờ sẽ được trả `answered` kèm nguồn do đã có database; trước đó cần trả `insufficient_evidence` vì Backend chưa có data. Các test khác giữ ý nghĩa cũ.
