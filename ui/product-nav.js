// Links are presentation only; all admin routes are separately authorized by FastAPI.
(async()=>{
  let user=null;
  try{const r=await fetch('/api/product/auth/me',{cache:'no-store'});if(r.ok)user=(await r.json()).user;}
  catch{}
  for(const nav of document.querySelectorAll('.desktop-nav,#mobile-nav')){
    const account=document.createElement('a');
    account.href='/portal.html#account';account.textContent=user?'Tài khoản':'Đăng nhập';nav.append(account);
    if(user){const n=document.createElement('a');n.href='/portal.html#calendar';n.textContent='Thông báo';nav.append(n);fetch('/api/product/calendar/notices',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{if(d?.unread)n.textContent='Thông báo ('+d.unread+')';}).catch(()=>{});}
    if(user?.role==='admin'){
      const admin=document.createElement('a');admin.href='/portal.html#dashboard';admin.textContent='Dashboard';nav.append(admin);
    }
  }
  if(user){
    const form=document.querySelector('#chat-form');
    if(form){
      const notice=document.createElement('p');
      notice.style.cssText='font-size:11px;color:#64748b;margin:4px 0';
      notice.textContent='Lịch sử chat được lưu theo tài khoản. Nhật ký câu hỏi có thể được Admin xem tối đa 30 ngày. Không nhập mật khẩu, OTP hoặc thông tin nhạy cảm.';
      form.before(notice);
    }
  }
})();
