// Account navigation and lightweight live inbox badge (never cache private data).
(async()=>{
 let user=null;
 try{const r=await fetch('/api/product/auth/me',{cache:'no-store'});if(r.ok)user=(await r.json()).user;}catch{}
 const links=[];
 for(const nav of document.querySelectorAll('.desktop-nav,#mobile-nav')){
  const account=document.createElement('a');account.href='/portal.html#account';account.textContent=user?user.username:'Đăng nhập';account.className='account-nav';nav.append(account);
  if(user){
   const n=document.createElement('a');n.href='/portal.html?notices=1#calendar';n.className='inbox-nav';n.textContent='Thông báo';n.setAttribute('aria-label','Thông báo của bạn');nav.append(n);links.push(n);
   if(user.role==='admin'){const admin=document.createElement('a');admin.href='/portal.html#dashboard';admin.textContent='Dashboard';nav.append(admin);}
  }
 }
 if(!user)return;
 // Keep the actual username visible while preserving the established account label for accessibility.
 for(const a of document.querySelectorAll('.account-nav')){a.textContent='Tài khoản · '+user.username;a.title='Tài khoản '+user.username;}
 let lastId=null,busy=false;
 async function updateInbox(){
  if(busy||document.hidden)return;busy=true;
  try{
   const me=await fetch('/api/product/auth/me',{cache:'no-store'});if(!me.ok)return;
   if((await me.json()).user?.id!==user.id){location.reload();return;}
   const r=await fetch('/api/product/calendar/notices',{cache:'no-store'});if(!r.ok)return;
   const d=await r.json();
   for(const link of links)link.textContent='Thông báo'+(d.unread?' ('+d.unread+')':'');
   const latest=d.items[0];if(lastId!==null&&latest&&latest.id>lastId){
    const old=document.getElementById('inbox-toast');if(old)old.remove();
    const toast=document.createElement('aside');toast.id='inbox-toast';toast.setAttribute('role','status');
    const title=document.createElement('strong');title.textContent='Thông báo mới';const body=document.createElement('p');body.textContent=latest.title;
    const open=document.createElement('a');open.href='/portal.html?notices=1#calendar';open.textContent='Mở hộp thư →';
    const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','Đóng thông báo');close.onclick=()=>toast.remove();
    toast.append(title,body,open,close);document.body.append(toast);
   }
   lastId=latest?.id||0;
  }catch{}finally{busy=false;}
 }
 updateInbox();setInterval(updateInbox,10000);window.addEventListener('focus',updateInbox);document.addEventListener('visibilitychange',updateInbox);
 const form=document.querySelector('#chat-form');if(form){const notice=document.createElement('p');notice.style.cssText='font-size:11px;color:#64748b;margin:4px 0';notice.textContent='Lịch sử chat lưu theo tài khoản. Nhật ký câu hỏi có thể được Admin xem tối đa 30 ngày. Không nhập mật khẩu, OTP hoặc thông tin nhạy cảm.';form.before(notice);}
})();
