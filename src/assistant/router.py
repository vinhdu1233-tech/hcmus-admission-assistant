"""Intent router: verified SQLite lookup + optional retrieved-evidence AI for major exploration."""
from __future__ import annotations
import json
import re
import unicodedata
from src.database.db import search_majors, all_majors, get_methods, count_majors
from src.assistant.retrieval import retrieve_majors
from src.assistant.ai import explain_with_ai

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

def route(message:str,year:int|None,*,focus_query:str|None=None,
          candidates_override:list[dict]|None=None)->dict:
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
        candidates=(candidates_override if candidates_override is not None else
                    retrieve_majors(focus_query or message,y,limit=5))
        if not candidates:
            return response(
                'Bạn đang quan tâm môn học hoặc hoạt động nào (ví dụ: lập trình, dữ liệu, vật lý, sinh học)? '
                'Mình cần thêm một sở thích để tìm ngành trong dữ liệu HCMUS.',
                intent,'clarification_needed')
        explanations=explain_with_ai(message,candidates)
        if explanations:
            chosen=[r for r in candidates if r['code'] in explanations][:3]
            lines='\n'.join(
                f"• {r['name']} ({r['code']}): {explanations[r['code']]}"
                for r in chosen)
            intro=('Dựa trên hướng bạn vừa chọn, đây là những ngành đáng tìm hiểu:'
                   if focus_query else 'Dựa trên sở thích bạn chia sẻ, đây là các hướng ngành đáng tìm hiểu:')
        else:
            chosen=candidates[:3]
            lines='\n'.join(
                f"• {r['name']} ({r['code']}): "
                +(r['official_profile'] if r.get('official_profile') else
                  'Tên ngành và các từ khóa liên quan gợi ý đây có thể là lựa chọn để bạn tìm hiểu thêm.')
                for r in chosen)
            intro=('Gợi ý theo hướng bạn vừa chọn từ dữ liệu HCMUS '
                   '(AI chưa cấu hình hoặc tạm không khả dụng):'
                   if focus_query else 'Gợi ý từ dữ liệu truy xuất (AI chưa cấu hình hoặc tạm không khả dụng):')
        sources=[]
        for row in chosen:
            urls=[(row['source_url'],row['source_title'])]
            if row.get('official_profile') and row.get('profile_source_url'):
                urls.insert(0,(row['profile_source_url'],'Giới thiệu chương trình '+row['name']+' – HCMUS'))
            for url,title in urls:
                if not any(s['url']==url for s in sources):
                    sources.append({'title':title,'url':url,'admission_year':y})
        if focus_query:
            followup='Bạn có thể chọn hướng khác để so sánh, hoặc đặt câu hỏi tuyển sinh tiếp theo.'
        elif any(word in clean for word in ('lap trinh','python','code','toan','du lieu')):
            followup='Bạn thích hơn việc xây dựng ứng dụng, giải bài toán thuật toán hay phân tích dữ liệu?'
        else:
            followup='Bạn thích hoạt động nào nhất trong lĩnh vực này để mình gợi ý sát hơn?'
        notice=('Đây là gợi ý tham khảo, không phải đánh giá năng lực hay kết luận trúng tuyển. '
                'Chỉ những ngành có liên kết giới thiệu riêng mới có mô tả chương trình đã đối chiếu; '
                'các ngành khác dùng tên ngành và từ khóa do nhóm biên soạn.')
        result=response(
            intro+'\n'+lines+'\n'+followup+'\n'+notice+'\n'+coverage_note(y),
            intent,sources=sources)
        # Internal-only dialogue metadata; the public ChatResponse schema drops it.
        # Avoid reconstructing recommendations when the LLM changes selection.
        result["_recommended_codes"]=tuple(r["code"] for r in chosen)
        result["_recommended_names"]=tuple(r["name"] for r in chosen)
        result["_followup_prompt"]=followup
        return result
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
