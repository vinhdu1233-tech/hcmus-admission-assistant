/**
 * HCMUS admission method data for the academic project.
 * Check official notifications for requirements, deadlines and special eligibility.
 * This checklist is planning guidance, not a legally authoritative submission guide.
 */
const PORTAL='https://tuyensinh.hcmus.edu.vn/phuong-thuc-tuyen-sinh/';
const S26A='https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-1a/';
const S26B='https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-1b/';
const S26T='https://tuyensinh.hcmus.edu.vn/2026-thong-bao-ve-phuong-thuc-xet-tuyen-2/';
const S25A='https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-1a-nam-2025/';
const S25BC='https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-1b-va-1c-nam-2025/';
const S25D='https://tuyensinh.hcmus.edu.vn/2025-thong-bao-ve-phuong-thuc-xet-tuyen-1d/';
const S25T='https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-2-va-3-nam-2025/';
const task=(id,title,detail)=>({id,title,detail});
const commonTasks=year=>[
 task('common-check','Đối chiếu ngành dự định và điều kiện xét tuyển','Đọc điều kiện áp dụng cho ngành và đối tượng của bạn.'),
 task('common-profile','Rà soát thông tin cá nhân và hồ sơ học tập','Kiểm tra giấy tờ và thông tin liên quan đến năm '+year+'.'),
 task('common-register','Kiểm tra hướng dẫn đăng ký nguyện vọng','Theo dõi thời hạn và cổng đăng ký theo thông báo chính thức.'),
 task('common-result','Theo dõi kết quả và thủ tục xác nhận nhập học','Đánh dấu khi đã thực hiện theo hướng dẫn của trường.')
];
export const ADMISSION_METHODS={
 '2026':[
  {id:'1a',label:'Phương thức 1a — Xét tuyển thẳng / ưu tiên',short:'Xét tuyển thẳng và ưu tiên',source:S26A,summary:'Dành cho các diện xét tuyển thẳng/ưu tiên theo quy định Bộ GDĐT.',tasks:[
    task('1a-condition','Kiểm tra điều kiện xét tuyển thẳng/ưu tiên','Không phải tất cả thí sinh đều đủ điều kiện.'),
    task('1a-proof','Chuẩn bị minh chứng phù hợp với diện xét tuyển','Đối chiếu hồ sơ trong thông báo chính thức.'),
    task('1a-submit','Kiểm tra hình thức và thời gian nộp hồ sơ 1a','Đọc đúng hướng dẫn năm 2026.')]},
  {id:'1b',label:'Phương thức 1b — Thí sinh quốc tịch nước ngoài',short:'Thí sinh quốc tịch nước ngoài',source:S26B,summary:'Diện thí sinh quốc tịch nước ngoài với điều kiện học vấn theo công bố của trường.',tasks:[
    task('1b-condition','Kiểm tra điều kiện quốc tịch và bằng cấp','Đối chiếu quy định cụ thể của phương thức 1b.'),
    task('1b-transcript','Chuẩn bị minh chứng kết quả học tập THPT','Kiểm tra yêu cầu về chứng thực và giấy tờ.'),
    task('1b-submit','Kiểm tra quy trình và thời hạn đăng ký','Làm theo thông báo chính thức năm 2026.')]},
  {id:'2',label:'Phương thức 2 — Kết hợp điểm thi và học bạ',short:'Điểm thi kết hợp học bạ',source:S26T,summary:'Xét dựa trên điểm học bạ THPT kết hợp kết quả thi THPT hoặc ĐGNL ĐHQG-HCM năm 2026.',tasks:[],paths:[
    {id:'thpt',label:'Nhánh THPT — Điểm thi tốt nghiệp THPT',summary:'Kết quả thi THPT năm 2026 + học bạ ba năm.',tasks:[
      task('2-thpt-result','Kiểm tra kết quả thi tốt nghiệp THPT năm 2026','Đối chiếu điểm và tổ hợp môn của ngành dự tuyển.'),
      task('2-thpt-hocba','Đối chiếu học bạ lớp 10, 11, 12','Là thành phần trong phương thức kết hợp năm 2026.'),
      task('2-thpt-rule','Kiểm tra điều kiện và cách quy đổi điểm THPT','Các ngành đặc thù có thể yêu cầu thêm điều kiện.')]},
    {id:'dgnl',label:'Nhánh ĐGNL — Điểm thi ĐGNL ĐHQG-HCM',summary:'Kết quả thi ĐGNL năm 2026 + học bạ ba năm.',tasks:[
      task('2-dgnl-result','Kiểm tra kết quả thi ĐGNL ĐHQG-HCM năm 2026','Sử dụng đúng điểm ĐGNL và điều kiện ngành dự tuyển.'),
      task('2-dgnl-hocba','Đối chiếu học bạ lớp 10, 11, 12','Là thành phần trong phương thức kết hợp năm 2026.'),
      task('2-dgnl-rule','Kiểm tra quy đổi điểm và ngưỡng của nhánh ĐGNL','Không dùng ngưỡng THPT cho nhánh này.')]}
   ]}
 ],
 '2025':[
  {id:'1a',label:'Phương thức 1a — Xét tuyển thẳng / ưu tiên',short:'Xét tuyển thẳng và ưu tiên',source:S25A,summary:'Điều kiện xét tuyển thẳng/ưu tiên năm 2025.',tasks:[
    task('1a-condition','Kiểm tra điều kiện xét tuyển thẳng','Đối chiếu diện và trường hợp áp dụng năm 2025.'),
    task('1a-proof','Chuẩn bị minh chứng phù hợp','Xem hướng dẫn tài liệu và biểu mẫu năm 2025.')]},
  {id:'1b',label:'Phương thức 1b — Ưu tiên xét tuyển thẳng ĐHQG-HCM',short:'Ưu tiên xét tuyển thẳng',source:S25BC,summary:'Ưu tiên xét tuyển thẳng theo quy định ĐHQG-HCM năm 2025.',tasks:[
    task('1b-condition','Kiểm tra đối tượng ưu tiên xét tuyển thẳng','Xem điều kiện công bố năm 2025.'),
    task('1b-proof','Đối chiếu hồ sơ minh chứng','Chuẩn bị giấy tờ theo diện.')]},
  {id:'1c',label:'Phương thức 1c — Ưu tiên xét tuyển ĐHQG-HCM',short:'Ưu tiên xét tuyển',source:S25BC,summary:'Ưu tiên xét tuyển theo quy định ĐHQG-HCM năm 2025.',tasks:[
    task('1c-condition','Kiểm tra điều kiện ưu tiên xét tuyển','Điều kiện riêng cho phương thức 1c.'),
    task('1c-proof','Đối chiếu học bạ và minh chứng','Xem thông báo của trường.')]},
  {id:'1d',label:'Phương thức 1d — Chứng chỉ ngoại ngữ + học bạ',short:'Chứng chỉ ngoại ngữ + học bạ',source:S25D,summary:'Kết hợp chứng chỉ ngoại ngữ quốc tế và học bạ theo điều kiện chương trình năm 2025.',tasks:[
    task('1d-cert','Kiểm tra chứng chỉ ngoại ngữ quốc tế','Đối chiếu yêu cầu và thời hạn hiệu lực.'),
    task('1d-record','Đối chiếu kết quả học bạ THPT','Kiểm tra ngưỡng và điều kiện theo chương trình.'),
    task('1d-proof','Chuẩn bị hồ sơ minh chứng','Theo thông báo phương thức 1d năm 2025.')]},
  {id:'2',label:'Phương thức 2 — Điểm thi tốt nghiệp THPT 2025',short:'Điểm thi THPT',source:S25T,summary:'Xét theo kết quả thi tốt nghiệp THPT năm 2025.',tasks:[
    task('2-thpt-result','Kiểm tra kết quả thi tốt nghiệp THPT năm 2025','Đối chiếu ngưỡng và tổ hợp môn.'),
    task('2-thpt-rule','Kiểm tra điều kiện ngành xét bằng điểm THPT','Không nhầm với Phương thức 3 dùng ĐGNL.')]},
  {id:'3',label:'Phương thức 3 — Điểm ĐGNL ĐHQG-HCM 2025',short:'Điểm ĐGNL',source:S25T,summary:'Xét theo kết quả Đánh giá năng lực ĐHQG-HCM năm 2025.',tasks:[
    task('3-dgnl-result','Kiểm tra kết quả thi ĐGNL ĐHQG-HCM năm 2025','Đối chiếu điểm thi và điều kiện ngành.'),
    task('3-dgnl-rule','Kiểm tra ngưỡng điểm và hướng dẫn phương thức 3','Không dùng kết quả THPT thay cho điểm ĐGNL.')]}
 ]
};
export {PORTAL,commonTasks};
