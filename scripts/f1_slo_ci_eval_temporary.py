#!/usr/bin/env python3
"""Temporary F1 SLO benchmark against the actual running FastAPI application.
Reference program sets come from the checked-in Team 05 2026 seed:
this is implementation consistency testing, not independent official-site verification.
"""
from __future__ import annotations
import concurrent.futures
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data/curated/majors_2026.json").read_text(encoding="utf-8"))
PROGRAMS = SEED["majors"]
KNOWN_CODES = {p["code"] for p in PROGRAMS}
URL = "http://127.0.0.1:8000/chat"
MAIN_SOURCE = SEED["source"]["url"]

PROGRAM_QUESTIONS = [
"HCMUS có những ngành nào năm 2026?",
"Cho tôi danh sách ngành tuyển sinh HCMUS năm 2026.",
"Tra cứu tất cả các ngành HCMUS năm 2026.",
"Liệt kê mã ngành tại HCMUS năm 2026.",
"Năm 2026 HCMUS tuyển sinh những ngành gì?",
"Có bao nhiêu ngành tuyển sinh HCMUS năm 2026?",
"Cho mình xem các ngành được công bố trong năm 2026.",
"Thông tin các ngành HCMUS năm 2026?",
"Liệt kê ngành và nhóm ngành tuyển sinh HCMUS 2026.",
"Tra cứu danh mục ngành của HCMUS trong năm 2026.",
]
COMBINATION_QUERIES = [
("A01","Ngành nào xét tổ hợp A01 năm 2026?"),
("B00","HCMUS năm 2026 tuyển sinh tổ hợp B00 ở các ngành nào?"),
("D07","Cho biết các ngành có tổ hợp D07 năm 2026."),
("A00","Ngành nào xét tổ hợp A00 năm 2026?"),
("B08","HCMUS năm 2026 tuyển sinh tổ hợp B08 ở các ngành nào?"),
("X26","Cho biết các ngành có tổ hợp X26 năm 2026."),
("A02","Ngành nào xét tổ hợp A02 năm 2026?"),
("C01","HCMUS năm 2026 tuyển sinh tổ hợp C01 ở các ngành nào?"),
("D01","Cho biết các ngành có tổ hợp D01 năm 2026."),
("X06","Ngành nào xét tổ hợp X06 năm 2026?"),
("A03","HCMUS năm 2026 tuyển sinh tổ hợp A03 ở các ngành nào?"),
("C02","Cho biết các ngành có tổ hợp C02 năm 2026."),
("B03","Ngành nào xét tổ hợp B03 năm 2026?"),
("X10","HCMUS năm 2026 tuyển sinh tổ hợp X10 ở các ngành nào?"),
("X15","Cho biết các ngành có tổ hợp X15 năm 2026."),
("X14","Tra cứu các ngành xét tuyển tổ hợp X14 tại HCMUS năm 2026."),
("X11","Tra cứu các ngành xét tuyển tổ hợp X11 tại HCMUS năm 2026."),
("C04","Tra cứu các ngành xét tuyển tổ hợp C04 tại HCMUS năm 2026."),
("X12","Tra cứu các ngành xét tuyển tổ hợp X12 tại HCMUS năm 2026."),
("D10","Tra cứu các ngành xét tuyển tổ hợp D10 tại HCMUS năm 2026."),
]
METHOD_QUESTIONS = [
"Phương thức tuyển sinh HCMUS năm 2026 là gì?",
"Cho mình xem các phương thức xét tuyển 2026 tại HCMUS.",
"HCMUS công bố những phương thức tuyển sinh nào trong năm 2026?",
"Năm 2026 có các hình thức xét tuyển nào tại HCMUS?",
"Thông tin về phương thức tuyển sinh năm 2026?",
"Liệt kê các phương thức xét tuyển HCMUS 2026.",
"Cho hỏi phương thức xét tuyển năm 2026.",
"HCMUS 2026 xét tuyển bằng những phương thức nào?",
"Cho biết các phương thức tuyển sinh HCMUS 2026.",
"Năm 2026 trường dùng phương thức nào để xét tuyển?",
]
EDGE_CASES = [
("Ngành nào xét A01?",None,"major_filter","clarification_needed"),
("Các phương thức tuyển sinh của HCMUS là gì?",None,"admission_methods","clarification_needed"),
("HCMUS có những ngành nào?",None,"admission_lookup","clarification_needed"),
("Ngành nào xét A01 năm 2027?",None,"major_filter","insufficient_evidence"),
("HCMUS tuyển sinh những ngành nào năm 2025?",None,"admission_lookup","insufficient_evidence"),
("Ngành nào xét B00 năm 2028?",None,"major_filter","insufficient_evidence"),
("Ngành nào xét A01 năm 2025 và 2026?",None,"major_filter","clarification_needed"),
("Ngành nào xét A01 năm 2026?",2027,"major_filter","clarification_needed"),
("HCMUS tuyển sinh ngành nào năm 2026 và 2027?",None,"admission_lookup","clarification_needed"),
("Ngành nào xét A01?",2027,"major_filter","insufficient_evidence"),
]
CASES=[]
for q in PROGRAM_QUESTIONS:
    CASES.append(dict(family="program_list",question=q,year=None,intent="admission_lookup",
                      status="answered",expected_codes=KNOWN_CODES))
for combination,q in COMBINATION_QUERIES[:15]:
    CASES.append(dict(family="combination",question=q,year=None,intent="major_filter",
                      status="answered",expected_codes={p["code"] for p in PROGRAMS
                                                      if combination in p["combinations"]}))
for q in METHOD_QUESTIONS:
    CASES.append(dict(family="methods",question=q,year=None,intent="admission_methods",
                      status="answered",expected_codes=set()))
for combination,q in COMBINATION_QUERIES[15:]:
    CASES.append(dict(family="combination",question=q,year=None,intent="major_filter",
                      status="answered",expected_codes={p["code"] for p in PROGRAMS
                                                      if combination in p["combinations"]}))
for q,year,intent,status in EDGE_CASES:
    CASES.append(dict(family="edge",question=q,year=year,intent=intent,
                      status=status,expected_codes=set()))
assert len(CASES)==50

def call_api(case):
    payload={"message":case["question"]}
    if case["year"] is not None:
        payload["admission_year"]=case["year"]
    request=urllib.request.Request(URL,method="POST",
        headers={"Content-Type":"application/json"},
        data=json.dumps(payload,ensure_ascii=False).encode())
    began=time.perf_counter()
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            status=response.status
            content=json.loads(response.read().decode())
            error=""
    except urllib.error.HTTPError as exc:
        status=exc.code
        error=f"HTTP {status}"
        try:content=json.loads(exc.read().decode())
        except Exception:content={}
    except Exception as exc:
        status=0;content={};error=str(exc)[:200]
    return status,content,round((time.perf_counter()-began)*1000,3),error

def check_case(case,status,body):
    reasons=[]
    if status != 200:reasons.append(f"HTTP={status}")
    if not isinstance(body,dict):
        return ["response_not_json_object"]
    for key,expected in [("status",case["status"]),("intent",case["intent"])]:
        if body.get(key)!=expected:reasons.append(f"{key}={body.get(key)!r} expected={expected!r}")
    answer=str(body.get("answer",""))
    if case["family"] in ("program_list","combination"):
        actual={c for c in KNOWN_CODES if re.search(r"(?<![A-Za-z0-9_])"+re.escape(c)+r"(?![A-Za-z0-9_])",answer)}
        if actual != case["expected_codes"]:
            missing=case["expected_codes"]-actual
            extra=actual-case["expected_codes"]
            reasons.append(f"program_sets_differ missing={sorted(missing)} extra={sorted(extra)}")
    if case["family"]=="methods":
        for m in ("1a","1b","2"):
            if not re.search(r"(?<![A-Za-z0-9])"+re.escape(m)+r"\s*:",answer):
                reasons.append(f"missing_method_{m}")
    if case["status"]=="answered":
        sources=body.get("sources")
        if not isinstance(sources,list) or not sources:
            reasons.append("missing_sources")
        else:
            for src in sources:
                if not isinstance(src,dict) or src.get("admission_year")!=2026 or not str(src.get("url","")).startswith("https://tuyensinh.hcmus.edu.vn/"):
                    reasons.append("wrong_source_url_or_year");break
    else:
        if any(c in answer for c in ("7420101","7480107","7480201_NN")):
            reasons.append("unsupported_year_contains_program_code")
    return reasons

def p95(values):
    s=sorted(values)
    return s[math.ceil(len(s)*0.95)-1] if s else None

case_results=[]
for idx,case in enumerate(CASES,1):
    status,body,latency,error=call_api(case)
    issues=check_case(case,status,body)
    if error:issues.append(error)
    case_results.append(dict(id=f"F1-{idx:03d}",family=case["family"],
        question=case["question"],http=status,
        returned_status=body.get("status") if isinstance(body,dict) else None,
        returned_intent=body.get("intent") if isinstance(body,dict) else None,
        latency_ms=latency,pass_machine=not issues,issues=issues))
    print(f"CASE F1-{idx:03d} {'PASS' if not issues else 'FAIL'} {latency:.2f}ms " + " | ".join(issues),flush=True)

benchmark_pass=sum(r["pass_machine"] for r in case_results)
latency_data=[]
for i in range(10):call_api(CASES[i])
for i in range(50):
    status,body,latency,error=call_api(CASES[i%40]);latency_data.append(latency)
latency_p95=p95(latency_data)
runtime=[]
for i in range(100):
    status,body,latency,error=call_api(CASES[i%40])
    runtime.append(dict(ok=(status==200 and not error and isinstance(body,dict)),
        latency_ms=latency,error=error))
runtime_success=sum(r["ok"] for r in runtime)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    concurrent=list(pool.map(call_api, (CASES[i%40] for i in range(100))))
ccu_success=sum(status==200 and not error and isinstance(body,dict)
                for status,body,latency,error in concurrent)
ccu_p95=p95([r[2] for r in concurrent])
summary=dict(git_sha=os.environ.get("GITHUB_SHA","unknown"),
    tests=50,correctness_machine_pass=benchmark_pass,
    accuracy_machine_pct=round(benchmark_pass*100/50,2),
    latency_p95_ms=latency_p95,latency_target_met=latency_p95<=2000,
    runtime_requests=100,runtime_success=runtime_success,
    runtime_target_met=runtime_success>=99,
    ccu=3,ccu_requests=100,ccu_success=ccu_success,
    ccu_p95_ms=ccu_p95,ccu_target_met=(ccu_success>=99 and ccu_p95<=3000),
    source_content_manual_review="NOT PERFORMED",
    environment="GitHub Actions Ubuntu / localhost FastAPI API (not public deployment)")
out=ROOT/"f1_slo_actual_results.json"
out.write_text(json.dumps({"summary":summary,"cases":case_results},ensure_ascii=False,indent=2),encoding="utf-8")
print("SLO_SUMMARY "+json.dumps(summary,ensure_ascii=False),flush=True)
print("SLO_RESULT_FILE "+str(out),flush=True)
# Do not fail job for SLO misses; report observed results truthfully.
