const $=id=>document.getElementById(id);
const apiBase='/api/product';
let user=null,calendarData={events:[],reminders:[],follows:[]},monitorData={sources:[],changes:[]},adminEvents=[],questionOffset=0;
const tz='Asia/Ho_Chi_Minh', todayKey=()=>new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).replace(/\//g,'-');
const dateKey=seconds=>{
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(seconds*1000));
  const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return p.year+'-'+p.month+'-'+p.day;
};
const timeText=s=>new Intl.DateTimeFormat('vi-VN',{timeZone:tz,dateStyle:'short',timeStyle:'short',hour12:false}).format(new Date(s*1000));
const localInput=s=>{
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(s*1000));
  const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute;
};
const dateISO=d=>d?d+':00+07:00':'';
let selected=dateKey(Date.now()/1000),month=new Date(selected+'T00:00:00Z');
month.setUTCDate(1);
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function button(text,handler,cls='secondary'){const b=el('button',text,cls);b.type='button';b.addEventListener('click',()=>safe(handler));return b;}
function flash(text,error=false){$('message').textContent=text;$('message').hidden=false;$('message').classList.toggle('error',error);}
async function api(path,{method='GET',body}={}){
  const response=await fetch(apiBase+path,{method,cache:'no-store',headers:body!==undefined?{'Content-Type':'application/json'}:{},body:body!==undefined?JSON.stringify(body):undefined});
  const data=await response.json().catch(()=>null);
  if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:data?.error?.message||data?.answer||'Yêu cầu không thành công ('+response.status+').');
  return data;
}
async function safe(fn){try{await fn();}catch(e){flash(e.message||String(e),true);}}
function requireLogin(){if(user)return true;location.hash='account';flash('Đăng nhập để lưu lịch và nhắc lịch cá nhân.');return false;}
function fill(form,key,value){if(form.elements[key])form.elements[key].value=value??'';}
function fields(form){return Object.fromEntries(new FormData(form));}
function showAuthTab(tab){for(const f of ['login','register','reset']){$(f+'-form').hidden=f!==tab;document.querySelector('[data-auth-tab="'+f+'"]').classList.toggle('active',f===tab);}}
document.querySelectorAll('[data-auth-tab]').forEach(b=>b.onclick=()=>showAuthTab(b.dataset.authTab));
showAuthTab('login');
async function refreshUser(){
  user=(await api('/auth/me')).user;
  $('nav-dashboard').hidden=user?.role!=='admin';$('nav-account').textContent=user?'Tài khoản':'Đăng nhập';
  $('signed-in').hidden=!user;$('auth-forms').hidden=!!user;
  if(user){$('account-name').textContent=user.username;$('account-role').textContent=user.role==='admin'?'Quản trị viên (Admin)':'Học sinh (Student)';}
}
async function showPage(){
  let target=location.hash.slice(1)||'calendar';
  if(!['account','calendar','dashboard'].includes(target))target='calendar';
  if(target==='dashboard'&&user?.role!=='admin'){target='account';location.hash='account';flash('Dashboard chỉ dành cho Admin.',true);}
  for(const id of ['account','calendar','dashboard'])$(id).hidden=id!==target;
  if(target==='calendar'){await loadCalendar();await refreshMonitor();await refreshNotices();await refreshPush();}
  if(target==='dashboard')await loadAdmin();
}
window.addEventListener('hashchange',()=>safe(showPage));
$('login-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  const d=fields(event.target);await api('/auth/login',{method:'POST',body:d});event.target.reset();await refreshUser();
  location.hash=user.role==='admin'?'dashboard':'calendar';flash('Đăng nhập thành công.');await showPage();
});});
$('register-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  await api('/auth/register',{method:'POST',body:fields(event.target)});event.target.reset();showAuthTab('login');flash('Đăng ký thành công. Hãy đăng nhập.');
});});
$('reset-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  await api('/auth/reset',{method:'POST',body:fields(event.target)});event.target.reset();await refreshUser();showAuthTab('login');flash('Đã đổi mật khẩu. Hãy đăng nhập lại.');
});});
document.querySelectorAll('[data-send-code]').forEach(b=>b.addEventListener('click',()=>safe(async()=>{
  const f=b.closest('form'),email=f.elements.email;if(!email.reportValidity())return;
  b.disabled=true;try{const d=await api('/auth/'+b.dataset.sendCode+'/code',{method:'POST',body:{email:email.value}});flash(d.message||'Đã gửi mã.');setTimeout(()=>b.disabled=false,60000);}
  catch(e){b.disabled=false;throw e;}
})));
$('logout').onclick=()=>safe(async()=>{await api('/auth/logout',{method:'POST',body:{}});await refreshUser();showAuthTab('login');flash('Đã đăng xuất. Lịch riêng không còn hiển thị.');});
$('change-password').onclick=()=>{ $('auth-forms').hidden=false;showAuthTab('reset');fill($('reset-form'),'email',user.email);};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
const currentYear=Number(selected.slice(0,4));
for(let y=2025;y<=Math.max(currentYear+2,2028);y++){$('year').append(new Option(String(y),String(y)));}
$('year').value=String(currentYear);
function keyDate(d){return d.toISOString().slice(0,10);}
function eventClass(e){return e.user_id!==null?'personal':'m'+e.method;}
function visibleEvents(){return calendarData.events.filter(e=>$('personal-visible').checked||e.user_id===null);}
function onDay(e,k){return dateKey(e.starts)<=k&&dateKey(e.ends)>=k;}
function eventRow(e){const row=button(e.title,()=>showEvent(e),'event-row');row.append(el('small',timeText(e.starts)+(e.ends!==e.starts?' → '+timeText(e.ends):'')));return row;}
function renderCalendar(){
  $('month-label').textContent='Tháng '+(month.getUTCMonth()+1)+', '+month.getUTCFullYear();
  const grid=$('month-grid');grid.replaceChildren();const start=new Date(month);
  start.setUTCDate(1-(start.getUTCDay()+6)%7);const events=visibleEvents();
  for(let i=0;i<42;i++){
    const d=new Date(start);d.setUTCDate(start.getUTCDate()+i);const k=keyDate(d);
    const cell=el('div',undefined,'day'+(d.getUTCMonth()!==month.getUTCMonth()?' outside':'')+(k===selected?' selected':''));
    cell.append(button(String(d.getUTCDate()),()=>{selected=k;month=new Date(k+'T00:00:00Z');month.setUTCDate(1);renderCalendar();},'day-number'+(k===dateKey(Date.now()/1000)?' today':'')));
    const matches=events.filter(e=>onDay(e,k));
    for(const e of matches.slice(0,3)){const b=button(e.title,()=>showEvent(e),'event-chip '+eventClass(e));b.title=e.title;cell.append(b);}
    if(matches.length>3)cell.append(button('+'+(matches.length-3)+' mốc',()=>{selected=k;renderCalendar();},'event-chip'));
    grid.append(cell);
  }
  $('selected-day-title').textContent='Ngày '+selected.split('-').reverse().join('/');
  const day=$('day-events');day.replaceChildren();const matches=events.filter(e=>onDay(e,selected));
  if(!matches.length)day.append(el('p','Không có sự kiện.','hint'));else for(const e of matches)day.append(eventRow(e));
  const year=$('year-events');year.replaceChildren();
  const official=events.filter(e=>e.user_id===null);
  if(!official.length)year.append(el('p','Chưa có mốc được xác minh cho lựa chọn này.','hint'));
  else for(const e of official)year.append(eventRow(e));
}
async function loadCalendar(jump=false){
  calendarData=await api('/calendar?'+new URLSearchParams({year:$('year').value,method:$('method').value}));
  const method=$('method').value;$('follow-method').disabled=!user||method==='all';$('follow-method').checked=calendarData.follows.includes(method);
  if(jump){const first=calendarData.events.find(e=>e.user_id===null);const y=Number($('year').value);month=first?new Date(dateKey(first.starts)+'T00:00:00Z'):new Date(Date.UTC(y,0,1));selected=keyDate(month);month.setUTCDate(1);}
  renderCalendar();
}
$('prev').onclick=()=>{month.setUTCMonth(month.getUTCMonth()-1);renderCalendar();};
$('next').onclick=()=>{month.setUTCMonth(month.getUTCMonth()+1);renderCalendar();};
$('today').onclick=()=>safe(async()=>{selected=dateKey(Date.now()/1000);month=new Date(selected+'T00:00:00Z');month.setUTCDate(1);$('year').value=selected.slice(0,4);await loadCalendar();});
$('year').onchange=()=>safe(()=>loadCalendar(true));$('method').onchange=()=>safe(()=>loadCalendar(true));$('personal-visible').onchange=renderCalendar;
$('follow-method').onchange=()=>safe(async()=>{await api('/calendar/follow',{method:'POST',body:{method:$('method').value,enabled:$('follow-method').checked}});flash('Đã lưu lựa chọn theo dõi.');await loadCalendar();});
function openPersonal(e){
  if(!requireLogin())return;
  const f=$('personal-form');f.reset();
  $('personal-heading').textContent=e?'Sửa sự kiện riêng':'Thêm sự kiện riêng';
  fill(f,'id',e?.id||'');fill(f,'title',e?.title||'');fill(f,'start',e?localInput(e.starts):selected+'T09:00');fill(f,'end',e?localInput(e.ends):selected+'T10:00');fill(f,'note',e?.note||'');
  $('event-dialog').showModal();
}
$('new-event').onclick=()=>openPersonal(null);
$('personal-form').onsubmit=event=>{event.preventDefault();safe(async()=>{
  const d=fields(event.target),id=d.id;delete d.id;d.start=dateISO(d.start);d.end=dateISO(d.end);
  await api('/calendar/personal'+(id?'/'+encodeURIComponent(id):''),{method:id?'PUT':'POST',body:d});
  $('event-dialog').close();flash('Đã lưu sự kiện.');await loadCalendar();
});};
function showEvent(e){
  const box=$('event-detail');box.replaceChildren();box.append(el('h2',e.title),el('p',timeText(e.starts)+' → '+timeText(e.ends)),el('p',e.note||'', 'hint'));
  if(e.source_url){const a=el('a','Mở thông báo chính thức ↗');a.href=e.source_url;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
  if(e.ends<Date.now()/1000)box.append(el('p','Mốc đã qua; không thể tạo nhắc mới cho ngày đã qua.','hint'));
  if(user){
    if(e.user_id!==null){
      box.append(button('Sửa sự kiện',()=>{$('detail-dialog').close();openPersonal(e);}));
      box.append(button('Xóa sự kiện',async()=>{if(!confirm('Xóa sự kiện cá nhân và các lời nhắc?'))return;await api('/calendar/personal/'+encodeURIComponent(e.id),{method:'DELETE'});$('detail-dialog').close();await loadCalendar();flash('Đã xóa.');}));
    }
    const form=el('form');form.append(el('h3','Nhắc lịch riêng của bạn'));
    for(const edge of ['start','end']){
      const group=el('fieldset');group.append(el('legend',edge==='start'?'Trước mốc bắt đầu':'Trước mốc kết thúc'));
      for(const days of [7,4,1,0]){
        const l=el('label',undefined,'check'),input=document.createElement('input');input.type='checkbox';input.name=edge;input.value=String(days);
        input.checked=calendarData.reminders.some(r=>r.event_id===e.id&&r.edge===edge&&r.days_before===days);
        if(!input.checked&&((edge==='start'?e.starts:e.ends)-days*86400<=Date.now()/1000))input.disabled=true;
        l.append(input,document.createTextNode(days?'Trước '+days+' ngày':'Đúng thời điểm'));group.append(l);
      }form.append(group);
    }
    const save=el('button','Lưu nhắc lịch');save.type='submit';form.append(save);
    form.onsubmit=ev=>{ev.preventDefault();safe(async()=>{
      const fd=new FormData(form);await api('/calendar/reminders',{method:'POST',body:{event_id:e.id,before_start:fd.getAll('start').map(Number),before_end:fd.getAll('end').map(Number)}});
      $('detail-dialog').close();flash('Đã lưu nhắc lịch. Bật thông báo trên thiết bị để nhận Web Push.');await loadCalendar();
    });};box.append(form);
  }else box.append(button('Đăng nhập để đặt nhắc lịch',()=>{$('detail-dialog').close();requireLogin();}));
  $('detail-dialog').showModal();
}
function decodeVapid(s){const b64=s.replace(/-/g,'+').replace(/_/g,'/');const padded=b64+'='.repeat((4-b64.length%4)%4);return Uint8Array.from(atob(padded),c=>c.charCodeAt(0));}
async function refreshPush(){
  const supported='serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window&&window.isSecureContext;
  $('enable-push').disabled=!user||!supported;$('disable-push').disabled=!user||!supported;
  if(!supported){$('push-status').textContent='Thiết bị/trình duyệt chưa hỗ trợ Web Push hoặc trang chưa dùng HTTPS.';return;}
  const config=await api('/push/config');
  if(!config.enabled){$('enable-push').disabled=true;$('push-status').textContent='Server chưa được cấu hình VAPID.';return;}
  const reg=await navigator.serviceWorker.getRegistration('/');
  const sub=await reg?.pushManager.getSubscription();
  $('push-status').textContent=Notification.permission==='denied'?'Bạn đã chặn thông báo. Thay đổi trong cài đặt thiết bị.':sub?'Thiết bị có subscription. Nhấn Bật để liên kết với tài khoản hiện tại.':'Chưa bật trên thiết bị này.';
}
$('enable-push').onclick=()=>safe(async()=>{
  if(!requireLogin())return;
  const config=await api('/push/config');if(!config.enabled)throw Error('Server chưa cấu hình VAPID.');
  const permission=await Notification.requestPermission();if(permission!=='granted')throw Error('Bạn chưa cấp quyền nhận thông báo.');
  const reg=await navigator.serviceWorker.register('/product-sw.js',{scope:'/'});
  await navigator.serviceWorker.ready;
  let sub=await reg.pushManager.getSubscription();
  if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decodeVapid(config.public_key)});
  await api('/push/subscribe',{method:'POST',body:sub.toJSON()});flash('Đã liên kết thiết bị nhận Web Push.');await refreshPush();
});
$('disable-push').onclick=()=>safe(async()=>{if(!requireLogin())return;const reg=await navigator.serviceWorker.getRegistration('/'),sub=await reg?.pushManager.getSubscription();
  if(sub){await api('/push/unsubscribe',{method:'POST',body:{endpoint:sub.endpoint}});await sub.unsubscribe();}
  flash('Đã tắt thông báo trên thiết bị này.');await refreshPush();
});
async function refreshNotices(){const b=$('notices');b.replaceChildren();if(!user){b.append(el('p','Đăng nhập để xem thông báo của bạn.','hint'));return;}
  const d=await api('/calendar/notices');if(!d.items.length)b.append(el('p','Chưa có thông báo.','hint'));
  for(const n of d.items){const item=el('div',undefined,'entry');item.append(el('strong',n.title),el('p',timeText(n.created_at),'hint'));b.append(item);}
}
function sourceLink(url,label){const a=el('a',label||'Nguồn chính thức');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
async function refreshMonitor(){monitorData=await api('/monitor');const status=$('monitor-status'),changes=$('change-list');status.replaceChildren();changes.replaceChildren();
  for(const s of monitorData.sources){const row=el('div',undefined,'entry');row.append(sourceLink(s.url,s.label),el('p',s.last_error?'Kiểm tra thất bại: '+s.last_error:s.successful_at?'Kiểm tra: '+timeText(s.successful_at):'Chưa kiểm tra lần đầu.','hint'));status.append(row);}
  for(const c of monitorData.changes){const row=el('div',undefined,'entry');row.append(el('strong',c.reviewed_at?'Đã kiểm duyệt':'Phát hiện thay đổi — đang chờ xác minh'),el('p',timeText(c.detected_at),'hint'),sourceLink(c.url));changes.append(row);}
}
function dateStart(value){return value?value+'T00:00:00+07:00':null;}
function dateEnd(value){if(!value)return null;const d=new Date(value+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+1);return keyDate(d)+'T00:00:00+07:00';}
async function loadQuestions(){
  const f=fields($('filters')),p=new URLSearchParams({sort:f.sort,limit:'50',offset:String(questionOffset)});
  if(f.start)p.set('start',dateStart(f.start));if(f.end)p.set('end',dateEnd(f.end));
  const data=await api('/admin/questions?'+p),body=$('questions');body.replaceChildren();
  const kpis=$('kpis');kpis.replaceChildren();for(const [label,total] of [['Tổng câu hỏi',data.total],...data.by_intent.map(x=>[x.intent,x.total])]){const n=el('div',undefined,'kpi');n.append(el('strong',String(total)),el('span',label));kpis.append(n);}
  for(const item of data.items){
    const tr=el('tr');for(const val of [timeText(item.created_at),item.username,item.question.slice(0,170)+(item.question.length>170?'…':''),item.intent+' / '+item.status,item.latency_ms.toFixed(2)+' ms'])tr.append(el('td',val,val===item.question?'question':''));
    const td=el('td');td.append(button('Xem',()=>{$('question-detail').textContent='Username: '+item.username+'\nThời gian: '+timeText(item.created_at)+'\nIntent: '+item.intent+'\nStatus: '+item.status+'\n\n'+item.question;$('question-dialog').showModal();}));tr.append(td);body.append(tr);
  }
  $('question-page').textContent=data.total?(questionOffset+1)+'–'+Math.min(questionOffset+50,data.total)+' / '+data.total:'0';$('questions-prev').disabled=questionOffset===0;$('questions-next').disabled=questionOffset+50>=data.total;
}
$('filters').onsubmit=e=>{e.preventDefault();questionOffset=0;safe(loadQuestions);};
$('questions-prev').onclick=()=>safe(async()=>{questionOffset=Math.max(0,questionOffset-50);await loadQuestions();});
$('questions-next').onclick=()=>safe(async()=>{questionOffset+=50;await loadQuestions();});
async function loadUsers(){const d=await api('/admin/users'),b=$('users');b.replaceChildren();for(const u of d.items){
  const state=u.hard_locked?'Khóa vĩnh viễn':u.locked_until>Date.now()/1000?'Khóa đến '+timeText(u.locked_until):'Hoạt động';
  const tr=el('tr');for(const v of [u.username,u.role,String(u.failed),state])tr.append(el('td',v));
  const td=el('td');const unlock=button('Mở khóa',async()=>{if(!confirm('Mở khóa '+u.username+'?'))return;await api('/admin/users/'+u.id+'/unlock',{method:'POST',body:{}});await loadUsers();flash('Đã mở khóa.');});unlock.disabled=!u.lock_round&&!u.hard_locked;td.append(unlock);tr.append(td);b.append(tr);
}}
async function loadOfficialEvents(){
  const f=$('official-form'),year=f.elements.year.value;const data=await api('/calendar?year='+encodeURIComponent(year)+'&method=all');
  adminEvents=data.events.filter(e=>e.user_id===null);
  const list=$('official-event');list.replaceChildren(new Option('Thêm mới',''));for(const e of adminEvents)list.append(new Option(e.title,e.id));
}
$('official-form').elements.year.onchange=()=>safe(loadOfficialEvents);
$('official-event').onchange=()=>{const f=$('official-form'),e=adminEvents.find(e=>e.id===f.elements.id.value);if(!e)return;for(const [k,v]of Object.entries({method:e.method,title:e.title,start:localInput(e.starts),end:localInput(e.ends),source_url:e.source_url,note:e.note}))fill(f,k,v);};
$('official-form').onsubmit=e=>{e.preventDefault();safe(async()=>{const d=fields(e.target);d.year=Number(d.year);d.id=d.id||null;d.start=dateISO(d.start);d.end=dateISO(d.end);
  if(!confirm('Bạn đã đối chiếu đúng ngày, năm, phương thức và nguồn HCMUS?'))return;
  await api('/admin/calendar',{method:'POST',body:d});flash('Đã lưu mốc chính thức.');await loadOfficialEvents();
});};
async function loadAdminChanges(){
  const data=await api('/monitor');$('official-source').replaceChildren(...data.sources.map(s=>new Option(s.label,s.url)));
  const b=$('admin-changes');b.replaceChildren();b.append(el('h3','Lịch sử thay đổi nguồn'));
  for(const c of data.changes){const n=el('div',undefined,'entry');n.append(el('strong',c.reviewed_at?'Đã kiểm duyệt':'Chờ kiểm duyệt'),el('p',c.summary,'hint'),sourceLink(c.url));
    if(!c.reviewed_at)n.append(button('Ghi nhận đã kiểm duyệt',async()=>{const note=prompt('Kết quả đối chiếu (nếu đổi ngày, cập nhật lịch ở trên trước):');if(!note?.trim())return;await api('/admin/monitor/'+c.id+'/review',{method:'POST',body:{note}});await loadAdminChanges();}));b.append(n);
  }
}
async function loadAdmin(){if(user?.role!=='admin')return;await Promise.all([loadQuestions(),loadUsers(),loadOfficialEvents(),loadAdminChanges()]);}
$('refresh-admin').onclick=()=>safe(loadAdmin);
safe(async()=>{await refreshUser();await showPage();});
