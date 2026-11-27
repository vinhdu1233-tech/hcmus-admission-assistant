"""Conservative extraction of explicit Vietnamese admissions date ranges.
Candidates are evidence, not official calendar entries. Never infer a missing year.
"""
import re
from datetime import datetime,timezone,timedelta
VN=timezone(timedelta(hours=7))
DATE=r"(?:(?P<{p}h>\d{{1,2}})\s*(?:giờ|:)\s*(?P<{p}min>\d{{1,2}})?\s*(?:phút\s*)?)?(?:ngày\s*)?(?P<{p}d>\d{{1,2}})/(?P<{p}m>\d{{1,2}})/(?P<{p}y>20\d{{2}})"
A=DATE.format(p="a"); B=DATE.format(p="b")
RANGE=re.compile(r"\btừ\s+"+A+r"\s+(?:đến|tới)\s+"+B,re.I)
END=re.compile(r"(?:gia hạn(?:\s+[^.;\n]{0,70}?)?\s+đến|chậm nhất(?:\s+là)?|trước)\s+"+B,re.I)
METHOD=re.compile(r"phương thức(?:\s+xét tuyển)?\s+(1a|1b|2)\b",re.I)
def stamp(m,p):
    g=m.groupdict()
    return datetime(int(g[p+"y"]),int(g[p+"m"]),int(g[p+"d"]),int(g[p+"h"] or 0),int(g[p+"min"] or 0),tzinfo=VN).timestamp()
def extract(text,label=""):
    # Scope method to a local sentence or unambiguous source label; not entire article.
    label_methods=set(x.lower() for x in METHOD.findall(label))
    out=[]
    for line in re.split(r"[\n;]+|(?<=[.!?])\s+(?=[A-ZÀ-Ỹ])",text):
        if len(line)>1800:continue
        methods=set(x.lower() for x in METHOD.findall(line)) or label_methods
        if len(methods)!=1:continue
        method=next(iter(methods))
        if not re.search(r"hồ sơ|đăng ký|nguyện vọng|lệ phí|minh chứng|nhập học|tra cứu|khiếu nại",line,re.I):continue
        for regex,kind in ((RANGE,"range"),(END,"end")):
            for m in regex.finditer(line):
                # Ignore end matcher nested in a full range.
                if kind=="end" and any(r.start()<=m.start()<r.end() for r in RANGE.finditer(line)):continue
                try:
                    end=stamp(m,"b");start=stamp(m,"a") if kind=="range" else None
                    y=int(m.group("by"))
                    if start is not None and (start>end or int(m.group("ay"))!=y):continue
                except (ValueError,OverflowError):continue
                # Evidence contains surrounding qualification/target group.
                evidence=line[max(0,m.start()-220):min(len(line),m.end()+340)].strip()
                title=("Khoảng thời gian tuyển sinh" if kind=="range" else "Mốc kết thúc cần xác minh")
                note="Không suy ra giờ bị thiếu; Admin phải xác minh đối tượng, loại mốc và thời gian."
                out.append(dict(year=y,method=method,title=title,starts=start,ends=end,evidence=evidence,precision_note=note))
    return out[:50]
def save_candidates(c,snapshot_id,url,text):
    label=c.execute("SELECT label FROM monitor_sources WHERE url=?",(url,)).fetchone()[0]
    c.execute("UPDATE deadline_candidates SET state='superseded' WHERE state='pending' AND snapshot_id IN (SELECT id FROM snapshots WHERE url=? AND id!=?)",(url,snapshot_id))
    for d in extract(text,label):
        c.execute("""INSERT OR IGNORE INTO deadline_candidates(snapshot_id,year,method,title,starts,ends,evidence,precision_note)
        VALUES (?,?,?,?,?,?,?,?)""",(snapshot_id,d["year"],d["method"],d["title"],d["starts"],d["ends"],d["evidence"],d["precision_note"]))
