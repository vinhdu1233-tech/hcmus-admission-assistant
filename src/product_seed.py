"""Historical, source-linked 2026 events; no guessed 2027 dates.
Seeded once per event; reviewed administrator edits are preserved.
"""
from datetime import datetime
BASE="https://tuyensinh.hcmus.edu.vn/"
S1=BASE+"2026-thong-bao-mo-cong-dang-ky-phuong-thuc-1a/"
S2=BASE+"2026-thong-bao-ve-phuong-thuc-xet-tuyen-1b/"
S3=BASE+"2026-thong-bao-ve-phuong-thuc-xet-tuyen-2/"
S4=BASE+"2026-thong-bao-ve-gia-han-nop-ho-so-minh-chung/"
SOURCES={
 S1:"2026 • Mở cổng phương thức 1a", S2:"2026 • Phương thức 1b",
 S3:"2026 • Phương thức 2", S4:"2026 • Gia hạn minh chứng phương thức 2",
 BASE+"2026-thong-tin-tuyen-sinh/":"2026 • Bảng thông tin tuyển sinh",
 BASE+"danh-muc/thong-tin-tuyen-sinh/":"Danh mục thông báo tuyển sinh"
}
S5=BASE+"2026-thong-bao-mo-cong-nop-ho-so-minh-chung/"
S6=BASE+"2026-thong-bao-thoi-gian-cong-bo-ket-qua-va-thong-tin-lien-quan-den-nhap-hoc/"
SOURCES.update({S5:"2026 • Minh chứng phương thức 2",S6:"2026 • Kết quả và nhập học",BASE+"danh-muc/thong-tin-tuyen-sinh/thong-tin-tuyen-sinh-nam-2026/":"Danh mục 2026"})
def timestamp(value):
    return datetime.fromisoformat(value).timestamp()
def seed(c):
    c.executemany("INSERT OR IGNORE INTO monitor_sources(url,label) VALUES (?,?)",SOURCES.items())
    rows=[
      ("official-2026-1a-application","1a","Nộp hồ sơ trực tuyến — phương thức 1a","2026-06-01T11:00:00+07:00","2026-06-20T17:00:00+07:00",S1,"Theo thông báo mở cổng của trường."),
      ("official-2026-1b-application","1b","Nộp hồ sơ trực tuyến — phương thức 1b","2026-06-16T10:00:00+07:00","2026-07-10T17:00:00+07:00",S2,"Dành cho đối tượng phương thức 1b."),
      ("official-2026-2-extension","2","Đợt gia hạn nộp minh chứng — phương thức 2","2026-06-23T14:00:00+07:00","2026-06-25T19:00:00+07:00",S4,"Chứng chỉ ngoại ngữ, giải thưởng và học bạ cho nhóm đối tượng được quy định; đây là đợt gia hạn, không phải hạn chung của mọi thí sinh."),
      ("official-2026-2-preferences","2","Đăng ký, điều chỉnh nguyện vọng","2026-07-02T00:00:00+07:00","2026-07-14T17:00:00+07:00",S3,"Nguồn chỉ công bố ngày bắt đầu, không công bố giờ; 00:00 là mốc hiển thị ngày."),
    ]
    rows.extend([
      ("official-2026-2-evidence","2","Nộp minh chứng ban đầu — phương thức 2","2026-05-25T00:00:00+07:00","2026-06-20T23:59:00+07:00",S5,"Chỉ các nhóm phải nộp hoặc muốn quy đổi/cộng điểm. Nguồn không nêu giờ chung; giờ hiển thị không phải hạn chính thức. Xem đợt gia hạn riêng."),
      ("official-2026-2-fee","2","Nộp lệ phí xét tuyển trực tuyến","2026-07-15T00:00:00+07:00","2026-07-21T17:00:00+07:00",S3,"Nguồn không nêu giờ mở; 00:00 là mốc hiển thị."),
    ])
    for method in ("1a","1b","2"):
        rows.extend([
          (f"official-2026-{method}-result",method,"Dự kiến tra cứu kết quả trúng tuyển","2026-08-13T15:00:00+07:00","2026-08-13T15:00:00+07:00",S6,"Thời điểm dự kiến trong thông báo; áp dụng mọi phương thức."),
          (f"official-2026-{method}-appeal",method,"Gửi khiếu nại kết quả / thông tin cá nhân","2026-08-13T00:00:00+07:00","2026-08-15T23:59:00+07:00",S6,"Chỉ công bố ngày, không công bố giờ; giờ hiển thị mang tính quy ước."),
          (f"official-2026-{method}-confirm",method,"Hạn xác nhận nhập học trực tuyến","2026-08-21T17:00:00+07:00","2026-08-21T17:00:00+07:00",S6,"Hạn cuối; không biểu thị giờ mở cổng."),
          (f"official-2026-{method}-enroll",method,"Làm thủ tục nhập học trực tiếp","2026-08-17T08:00:00+07:00","2026-08-21T17:00:00+07:00",S6,"Theo lịch riêng trên giấy báo; 08–11h và 13:30–16h, riêng 21/8 đến 17h."),
        ])
    for ident,method,title,start,end,source,note in rows:
        c.execute("""INSERT OR IGNORE INTO events(id,year,method,title,starts,ends,source_url,note)
          VALUES (?,2026,?,?,?,?,?,?)""",(ident,method,title,timestamp(start),timestamp(end),source,note))
