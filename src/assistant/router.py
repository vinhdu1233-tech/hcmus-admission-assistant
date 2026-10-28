"""Deterministic intent router for the HCMUS admissions MVP.
Full LLM retrieval is a separate feature, not claimed here.
"""
from __future__ import annotations
import json
import re
import unicodedata
from src.database.db import search_majors, all_majors, get_methods, count_majors

PORTAL = 'https://tuyensinh.hcmus.edu.vn/'
PUBLISHED_2026_PROGRAM_COUNT = 39
COMBINATIONS = ('A00','A01','A02','A03','A04','A07','B00','B03','B08','C01','C02','C04',
                'D01','D07','D10','X06','X10','X11','X12','X14','X15','X16','X26')
INTEREST_GROUPS = {
  'lap trinh': ('lập trình','phần mềm','máy tính','dữ liệu','trí tuệ nhân tạo'),
  'code': ('lập trình','phần mềm','máy tính'),
  'cong nghe thong tin': ('công nghệ thông tin','máy tính','phần mềm'),
  'toan': ('toán','phân tích','thống kê','dữ liệu'),
  'du lieu': ('dữ liệu','thống kê','phân tích'),
  'ai': ('trí tuệ nhân tạo','ai','dữ liệu'),
  'tri tue nhan tao': ('trí tuệ nhân tạo','ai','dữ liệu'),
  'sinh': ('sinh học','công nghệ sinh học'),
  'hoa': ('hóa học',),
  'vat ly': ('vật lý','điện tử','bán dẫn'),
  'dien tu': ('điện tử','vi mạch','bán dẫn'),
  'moi truong': ('môi trường',),
}

def normalized(s:str)->str:
    x=''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
    return x.replace('đ','d')

def detect_intent(message:str)->str:
    s=normalized(message)
    if any(t in s for t in ('hoc phi','hocphi')):return 'tuition_lookup'
    if any(t in s for t in ('phuong thuc','xet tuyen bang','hinh thuc xet tuyen')):return 'admission_methods'
    if any(t in s for t in ('so thich','em thich','nen chon','goi y nganh','phu hop','muon hoc ve')):return 'major_exploration'
    if re.search(r'(?<![A-Z0-9])(?:'+'|'.join(COMBINATIONS)+r')(?![A-Z0-9])',message.upper()) or 'to hop' in s:return 'major_filter'
    if any(t in s for t in ('nganh','tuyen sinh','ma nganh','chi tieu')):return 'admission_lookup'
    if 'nam nhat' in s or 'chuan bi' in s:return 'study_guidance'
    return 'unknown'

def response(answer:str,intent:str,status:str='answered',sources:list|None=None)->dict:
    return {'answer':answer,'intent':intent,'status':status,'sources':sources or []}

def coverage_note(year:int)->str:
    """Describe actual SQLite coverage, never a hard-coded 13/39."""
    loaded=count_majors(year)
    target=PUBLISHED_2026_PROGRAM_COUNT
    if loaded < target:
        return f'Database hiện có {loaded}/{target} ngành/nhóm ngành năm {year}. Danh sách chưa đầy đủ.'
    if loaded == target:
        return f'Database hiện có {loaded}/{target} ngành/nhóm ngành năm {year} theo bộ dữ liệu đã nhập.'
    return f'Database có {loaded} bản ghi, vượt {target} ngành/nhóm ngành công bố; cần kiểm tra dữ liệu trùng hoặc sai phạm vi.'

def extract_year(message:str,request_year:int|None)->tuple[int|None,str|None]:
    matches={int(x) for x in re.findall(r'(?<!\d)20\d{2}(?!\d)',message)}
    if len(matches)>1:return None,'Bạn đang nhắc đến nhiều năm. Vui lòng chọn một năm tuyển sinh.'
    embedded=next(iter(matches),None)
    if request_year is not None and embedded is not None and request_year!=embedded:
        return None,'Năm trong câu hỏi khác với năm được chọn. Bạn muốn tra cứu năm nào?'
    return request_year if request_year is not None else embedded, None

def route(message:str,year:int|None)->dict:
    intent=detect_intent(message)
    y,error=extract_year(message,year)
    if error:return response(error,intent,'clarification_needed')
    clean=normalized(message)
    if re.search(r'api\s*key|password|secret|token|mat khau',clean):
        return response('Mình không thể cung cấp API key, mật khẩu hay dữ liệu riêng tư.', 'unknown')
    if intent=='study_guidance':
        return response('Bạn có thể ôn kiến thức nền tảng, luyện tự học và đọc chương trình đào tạo. Đây là lời khuyên chung, không phải chính sách HCMUS.',intent)
    if intent=='tuition_lookup':
        if y is None:
            return response('Bạn muốn hỏi học phí của năm tuyển sinh hoặc năm học nào?',intent,'clarification_needed')
        return response('Chưa có dữ liệu học phí đã chuẩn hóa cho câu hỏi này. Vui lòng kiểm tra thông báo chính thức của HCMUS.',intent,'insufficient_evidence')
    if intent in ('major_filter','admission_lookup','admission_methods','major_exploration') and y is None:
        return response('Bạn muốn tra cứu hoặc khám phá ngành học của năm tuyển sinh nào?',intent,'clarification_needed')
    if y is not None and y!=2026:
        return response(f'Database MVP hiện chỉ có dữ liệu tuyển sinh năm 2026, chưa có bảng ngành được xác minh cho {y}.',intent,'insufficient_evidence')
    if intent=='admission_methods':
        methods=get_methods(y)
        if not methods:return response('Chưa có phương thức được xác minh trong database.',intent,'insufficient_evidence')
        text='Các phương thức xét tuyển HCMUS 2026 (tóm tắt):\n'+'\n'.join(f"• {r['code']}: {r['summary']}" for r in methods)
        return response(text+'\nĐọc thông báo chi tiết để kiểm tra điều kiện từng phương thức.',intent,sources=[{'title':'Thông báo phương thức '+r['code']+' – HCMUS','url':r['source_url'],'admission_year':y} for r in methods])
    if intent=='major_exploration':
        matched=set()
        for interest,tags in INTEREST_GROUPS.items():
            if interest in clean:matched.update(tags)
        if not matched:
            return response('Bạn thích lĩnh vực nào: lập trình, toán, dữ liệu, vật lý, hóa học, sinh học hay môi trường?',intent,'clarification_needed')
        ranked=[]
        for r in all_majors(y):
            tags={normalized(v) for v in json.loads(r['tags_json'])}
            score=len({normalized(t) for t in matched} & tags)
            if score:ranked.append((score,r))
        ranked.sort(key=lambda pair:(-pair[0],pair[1]['name']))
        choices=[r for _,r in ranked[:5]]
        if not choices:return response('Chưa đủ dữ liệu về ngành phù hợp trong bộ mẫu đã được xác minh.',intent,'insufficient_evidence')
        names='\n'.join(f"• {r['name']} ({r['code']})" for r in choices)
        return response('Gợi ý để bạn tìm hiểu thêm, dựa trên khớp từ khóa sở thích với nhóm ngành trong database (không phải kết quả AI hoặc đánh giá năng lực cá nhân):\n'+names+'\n'+coverage_note(y),intent,sources=[{'title':choices[0]['source_title'],'url':choices[0]['source_url'],'admission_year':2026}])
    if intent in ('major_filter','admission_lookup'):
        found=[c for c in COMBINATIONS if re.search(r'(?<![A-Z0-9])'+c+r'(?![A-Z0-9])',message.upper())]
        if len(found)>1:return response('Bạn muốn tìm theo tổ hợp nào? Vui lòng nhập một mã tổ hợp (ví dụ A01).',intent,'clarification_needed')
        combination=found[0] if found else None
        rows=search_majors(y,combination,limit=50)
        if not rows:
            return response('Không tìm thấy kết quả trong bộ dữ liệu MVP hiện tại. Điều này KHÔNG có nghĩa là HCMUS không tuyển ngành đó.',intent,'insufficient_evidence')
        lines='\n'.join(f"• {r['name']} ({r['code']})" for r in rows)
        prefix=f'Các ngành/nhóm ngành được ghi nhận có tổ hợp {combination} năm 2026' if combination else 'Các ngành/nhóm ngành trong bộ dữ liệu MVP năm 2026'
        return response(f'{prefix}:\n{lines}\n{coverage_note(y)}',intent,sources=[{'title':rows[0]['source_title'],'url':rows[0]['source_url'],'admission_year':2026}])
    return response('Bạn có thể hỏi về tổ hợp A01 năm 2026, phương thức tuyển sinh 2026 hoặc sở thích ngành học.',intent,'clarification_needed')
