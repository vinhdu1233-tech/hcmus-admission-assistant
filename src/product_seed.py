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
    for ident,method,title,start,end,source,note in rows:
        c.execute("""INSERT OR IGNORE INTO events(id,year,method,title,starts,ends,source_url,note)
          VALUES (?,2026,?,?,?,?,?,?)""",(ident,method,title,timestamp(start),timestamp(end),source,note))
