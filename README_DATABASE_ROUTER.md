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

**Seed của branch hiện có 39/39 ngành/nhóm ngành năm 2026, tổng 4.926 chỉ tiêu**, trích xuất từ bảng HCMUS cập nhật 10/7/2026: https://tuyensinh.hcmus.edu.vn/2026-thong-tin-tuyen-sinh/. Sau khi chạy `python -m src.database.db`, Router đọc số lượng bản ghi thực tế và không giới hạn danh sách ở 20 dòng. Việc có 39 bản ghi không tự động xác minh từng dòng; vẫn cần đối chiếu mã, chỉ tiêu, tổ hợp và nguồn.

**Feature 2 đã tích hợp retrieval BM25-style + AI tùy chọn**, giải thích dựa trên các ngành truy xuất và tags do nhóm tự biên soạn. Không có API key thì chỉ trả gợi ý retrieval. Chưa có mô tả chương trình đào tạo đầy đủ; không khẳng định môn học/cơ hội nghề nghiệp. Xem `README_RAG.md` để cấu hình API key và kiểm thử.

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


## Kiểm tra bản mở rộng 39 ngành (router dynamic)

1. Bộ JSON 39 ngành đã nằm trên branch `feat/mvp-sqlite-router` (không commit file SQLite).
2. Cập nhật code mới nhất từ PR #13 và chạy `python -m src.database.db`.
3. Trong DBeaver: `SELECT COUNT(*), SUM(quota) FROM majors WHERE year=2026;` (mục tiêu 39 và 4926 sau khi đã xác minh).
4. Chạy `python -m pytest -q tests/test_api_smoke.py tests/test_db_router.py tests/test_retrieval_ai.py`.
5. Gửi câu hỏi `HCMUS có những ngành nào năm 2026?` để kiểm tra trả đủ 39 dòng và thông báo `39/39`.
6. Nếu Database hiện chỉ có 13 ngành, Router trả đủ 13 và thông báo `13/39 ... chưa đầy đủ` — không khẳng định là đã có 39.
