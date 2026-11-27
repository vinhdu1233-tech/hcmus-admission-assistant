import {groupCalendarEvents} from './calendar-grouping.mjs';
const $=id=>document.getElementById(id);
const apiBase='/api/product';
let pushConfig=null,pushRegistration=null;
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
function announceAccountChange(){try{localStorage.setItem('hcmus:auth-change',String(Date.now())+Math.random());}catch{}}
window.addEventListener('storage',e=>{if(e.key==='hcmus:auth-change'){document.querySelector('main').hidden=true;location.reload();}});
window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
async function refreshUser(){
  user=(await api('/auth/me')).user;
  $('nav-dashboard').hidden=user?.role!=='admin';$('nav-notices').hidden=!user;if(user){const n=await api('/calendar/notices');$('unread-count').textContent=n.unread?'('+n.unread+')':'';}$('nav-account').textContent=user?'Tài khoản':'Đăng nhập';
  $('signed-in').hidden=!user;$('auth-forms').hidden=!!user;
  if(user){$('account-name').textContent=user.username;$('account-role').textContent=user.role==='admin'?'Quản trị viên (Admin)':'Học sinh (Student)';}
}
async function showPage(){
  let target=location.hash.slice(1)||'calendar';
  if(!['account','calendar','dashboard'].includes(target))target='calendar';
  if(target==='dashboard'&&user?.role!=='admin'){target='account';location.hash='account';flash('Dashboard chỉ dành cho Admin.',true);}
  for(const id of ['account','calendar','dashboard'])$(id).hidden=id!==target;
  if(target==='calendar'){await loadCalendar(initialFilters.has('year'));await refreshMonitor();await refreshNotices();await refreshPush();}
  if(target==='dashboard')await loadAdmin();
}
window.addEventListener('hashchange',()=>safe(showPage));
$('login-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  const d=fields(event.target);await api('/auth/login',{method:'POST',body:d});event.target.reset();
  announceAccountChange();location.replace('/');
});});
$('register-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  await api('/auth/register',{method:'POST',body:fields(event.target)});event.target.reset();showAuthTab('login');flash('Đăng ký thành công. Hãy đăng nhập.');
});});
$('reset-form').addEventListener('submit',event=>{event.preventDefault();safe(async()=>{
  await api('/auth/reset',{method:'POST',body:fields(event.target)});event.target.reset();announceAccountChange();location.replace('/portal.html#account');
});});
document.querySelectorAll('[data-send-code]').forEach(b=>b.addEventListener('click',()=>safe(async()=>{
  const f=b.closest('form'),email=f.elements.email;if(!email.reportValidity())return;
  b.disabled=true;try{const d=await api('/auth/'+b.dataset.sendCode+'/code',{method:'POST',body:{email:email.value}});flash(d.message||'Đã gửi mã.');setTimeout(()=>b.disabled=false,60000);}
  catch(e){b.disabled=false;throw e;}
})));
$('logout').onclick=()=>safe(async()=>{let sub=null;try{const reg=await navigator.serviceWorker?.getRegistration('/');sub=await reg?.pushManager?.getSubscription();}catch{}await api('/auth/logout',{method:'POST',body:sub?{endpoint:sub.endpoint}:{}});if(sub){try{await sub.unsubscribe();}catch{}}announceAccountChange();location.replace('/portal.html#account');});
$('change-password').onclick=()=>{ $('auth-forms').hidden=false;showAuthTab('reset');fill($('reset-form'),'email',user.email);};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
for(const id of ['day-dialog','candidate-dialog'])$(id).addEventListener('click',e=>{if(e.target===$(id))$(id).close();});
const currentYear=Number(selected.slice(0,4));
for(let y=2025;y<=Math.max(currentYear+2,2028);y++){$('year').append(new Option(String(y),String(y)));}
$('year').value=String(currentYear);
const initialFilters=new URLSearchParams(location.search);if([...$('year').options].some(o=>o.value===initialFilters.get('year')))$('year').value=initialFilters.get('year');if(['1a','1b','2','all'].includes(initialFilters.get('method')))$('method').value=initialFilters.get('method');
function keyDate(d){return d.toISOString().slice(0,10);}
function eventClass(e){return e.variants?'shared':e.user_id!==null?'personal':'m'+e.method;}
function visibleEvents(){const q=$('calendar-search').value.trim().toLocaleLowerCase('vi');return groupCalendarEvents(calendarData.events.filter(e=>($('personal-visible').checked||e.user_id===null)&&(!q||(e.title+' '+e.note).toLocaleLowerCase('vi').includes(q))));}
function onDay(e,k){return dateKey(e.starts)<=k&&dateKey(e.ends)>=k;}
function eventRow(e){const row=button(e.title,()=>showEvent(e),'event-row '+(e.id===searchId?'search-hit':''));row.append(el('small',timeText(e.starts)+(e.ends!==e.starts?' → '+timeText(e.ends):'')+(e.variants?' · Phương thức '+e.variants.map(v=>v.method).join(', '):'')));return row;}
let searchIndex=-1,searchId=null;
function jumpToDate(k){selected=k;month=new Date(k+'T00:00:00Z');month.setUTCDate(1);}
function searchResults(){return visibleEvents().slice().sort((a,b)=>a.starts-b.starts||a.id.localeCompare(b.id));}
function moveSearch(delta=0,reset=false){
 const q=$('calendar-search').value.trim(),items=searchResults();
 if(!q||!items.length){searchIndex=-1;searchId=null;renderCalendar();return;}
 searchIndex=reset?0:(searchIndex+delta+items.length)%items.length;
 const e=items[searchIndex];searchId=e.id;jumpToDate(dateKey(e.starts));
 if($('calendar-view').value==='agenda')$('calendar-view').value='month';
 renderCalendar();
}
function updateSearchControls(events){
 const q=$('calendar-search').value.trim(),index=events.slice().sort((a,b)=>a.starts-b.starts||a.id.localeCompare(b.id)).findIndex(e=>e.id===searchId);
 searchIndex=index;
 $('search-count').textContent=!q?'Tìm trong năm và phương thức đang chọn':!events.length?'Không tìm thấy sự kiện':(index>=0?index+1:0)+' / '+events.length+' kết quả · Enter để chuyển tiếp';
 $('search-prev').disabled=$('search-next').disabled=!q||!events.length;
}
function showDay(k,events){
 jumpToDate(k);renderCalendar();
 $('day-dialog-title').textContent=new Intl.DateTimeFormat('vi-VN',{dateStyle:'full',timeZone:'UTC'}).format(new Date(k+'T00:00:00Z'));
 const list=$('day-dialog-list');list.replaceChildren();
 const matches=events.filter(e=>onDay(e,k));list.append(el('p',matches.length+' sự kiện','hint'));
 for(const e of matches){const b=button(e.title,()=>{$('day-dialog').close();showEvent(e);},'event-row '+eventClass(e));b.append(el('small',timeText(e.starts)+' → '+timeText(e.ends)));list.append(b);}
 $('day-dialog').showModal();
}
function makeDay(d,events,week=false){
 const k=keyDate(d),cell=el('div',undefined,'day'+(!week&&d.getUTCMonth()!==month.getUTCMonth()?' outside':'')+(k===selected?' selected':'')+(k===dateKey(Date.now()/1000)?' current-day':''));
 const label=week?['CN','T2','T3','T4','T5','T6','T7'][d.getUTCDay()]+' · '+d.getUTCDate()+'/'+(d.getUTCMonth()+1):String(d.getUTCDate());
 const num=button(label,()=>{jumpToDate(k);renderCalendar();},'day-number'+(k===dateKey(Date.now()/1000)?' today':''));
 num.setAttribute('aria-label','Ngày '+k);cell.append(num);
 const matches=events.filter(e=>onDay(e,k)),limit=week?5:3;
 const sorted=matches.slice().sort((a,b)=>Number(b.id===searchId)-Number(a.id===searchId));
 for(const e of sorted.slice(0,limit)){const b=button(e.title,()=>showEvent(e),'event-chip '+eventClass(e)+(e.id===searchId?' search-hit':''));b.title=e.title;cell.append(b);}
 if(matches.length>limit){const more=button('+'+(matches.length-limit)+' mốc',()=>showDay(k,events),'event-chip more-events');more.setAttribute('aria-label','Xem tất cả '+matches.length+' sự kiện ngày '+k);cell.append(more);}
 if(week&&!matches.length)cell.append(el('span','—','hint'));return cell;
}
function renderCalendar(){
 const view=$('calendar-view').value,events=visibleEvents();
 $('month-grid').hidden=view!=='month';document.querySelector('.weekdays').hidden=view!=='month';$('alternate-view').hidden=view==='month';
 const fmt=new Intl.DateTimeFormat('vi-VN',{dateStyle:'full',timeZone:'UTC'}),selectedDate=new Date(selected+'T00:00:00Z');
 const monday=new Date(selectedDate);monday.setUTCDate(monday.getUTCDate()-(monday.getUTCDay()+6)%7);
 const sunday=new Date(monday);sunday.setUTCDate(sunday.getUTCDate()+6);
 $('month-label').textContent=view==='week'?('Tuần '+keyDate(monday).split('-').reverse().join('/')+' – '+keyDate(sunday).split('-').reverse().join('/')):view==='day'?fmt.format(selectedDate):view==='agenda'?'Sự kiện sắp tới':'Tháng '+(month.getUTCMonth()+1)+', '+month.getUTCFullYear();
 $('prev').setAttribute('aria-label',view==='week'?'Tuần trước':view==='day'?'Ngày trước':'Tháng trước');$('next').setAttribute('aria-label',view==='week'?'Tuần sau':view==='day'?'Ngày sau':'Tháng sau');$('prev').hidden=$('next').hidden=view==='agenda';
 const grid=$('month-grid');grid.replaceChildren();const start=new Date(month);start.setUTCDate(1-(start.getUTCDay()+6)%7);
 if(view==='month')for(let i=0;i<42;i++){const d=new Date(start);d.setUTCDate(start.getUTCDate()+i);grid.append(makeDay(d,events));}
 $('selected-day-title').textContent='Ngày '+selected.split('-').reverse().join('/');
 const day=$('day-events');day.replaceChildren();const matches=events.filter(e=>onDay(e,selected));
 if(!matches.length)day.append(el('p','Không có sự kiện.','hint'));else for(const e of matches)day.append(eventRow(e));
 const year=$('year-events');year.replaceChildren();const official=events.filter(e=>e.user_id===null);
 if(!official.length)year.append(el('p','Chưa có mốc được xác minh cho lựa chọn này.','hint'));else for(const e of official)year.append(eventRow(e));
 renderAlternative(view,events);renderCountdown(events);updateSearchControls(events);
}
function renderAlternative(view,events){
 const b=$('alternate-view');b.replaceChildren();b.className='view-'+view;if(view==='month')return;
 const now=Date.now()/1000,today=dateKey(now),fmt=new Intl.DateTimeFormat('vi-VN',{dateStyle:'full',timeZone:'UTC'});
 if(view==='week'){
  const d=new Date(selected+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);const grid=el('div',undefined,'week-grid');
  for(let i=0;i<7;i++){grid.append(makeDay(new Date(d),events,true));d.setUTCDate(d.getUTCDate()+1);}b.append(grid);return;
 }
 if(view==='agenda'){
  const upcoming=events.filter(e=>e.ends>=now).sort((a,b)=>Math.max(now,a.starts)-Math.max(now,b.starts)||a.ends-b.ends);
  const intro=el('div',undefined,'agenda-intro');intro.append(el('p','HÔM NAY','eyebrow'),el('h2',fmt.format(new Date(today+'T00:00:00Z'))),el('p',upcoming.length+' sự kiện đang diễn ra hoặc sắp tới · Múi giờ Việt Nam','hint'));b.append(intro);
  if(!upcoming.length)b.append(el('p','Không có sự kiện sắp tới. Chọn năm khác hoặc thêm sự kiện cá nhân.','empty-state'));
  let group='',section;
  for(const e of upcoming){const k=e.starts<=now?today:dateKey(e.starts);
   if(k!==group){group=k;section=el('section',undefined,'agenda-group');section.append(el('h3',k===today?'Hôm nay / Đang diễn ra':fmt.format(new Date(k+'T00:00:00Z'))));b.append(section);}
   const row=eventRow(e);row.classList.add('agenda-event',eventClass(e));row.append(el('span',e.starts<=now?'Đang diễn ra':'Còn '+Math.max(1,Math.ceil((e.starts-now)/86400))+' ngày','event-status'));section.append(row);
  }return;
 }
 const intro=el('div',undefined,'agenda-intro');intro.append(el('p',selected===today?'HÔM NAY':'LỊCH TRONG NGÀY','eyebrow'),el('h2',fmt.format(new Date(selected+'T00:00:00Z'))));b.append(intro);
 const matches=events.filter(e=>onDay(e,selected)).sort((a,b)=>a.starts-b.starts);intro.append(el('p',matches.length+' sự kiện · Giờ Việt Nam','hint'));
 if(!matches.length)b.append(el('p','Không có sự kiện trong ngày này.','empty-state'));
 for(const e of matches){const row=eventRow(e);row.classList.add('agenda-event',eventClass(e));row.append(el('span',e.user_id!==null?'Cá nhân':e.variants?'Nhiều phương thức':'Phương thức '+e.method,'event-status'));b.append(row);}
}
function renderCountdown(events){
  const b=$('countdown');b.replaceChildren();const now=Date.now()/1000;
  const upcoming=events.filter(e=>e.user_id===null&&e.ends>=now).sort((a,b)=>a.ends-b.ends)[0];
  if(!upcoming){b.append(el('span','Chưa có deadline tương lai đã xác minh trong bộ lọc.','hint'));return;}
  const days=Math.ceil((upcoming.ends-now)/86400);b.append(el('strong',days<=1?'Deadline trong vòng 24 giờ':'Còn khoảng '+days+' ngày đến hạn'),eventRow(upcoming));
}
function moveCalendar(direction){
  const view=$('calendar-view').value;
  if(view==='month'||view==='agenda'){month.setUTCMonth(month.getUTCMonth()+direction);selected=keyDate(month);}
  else{const d=new Date(selected+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+direction*(view==='week'?7:1));selected=keyDate(d);month=new Date(selected+'T00:00:00Z');month.setUTCDate(1);}
  renderCalendar();
}
$('calendar-view').onchange=renderCalendar;$('calendar-search').oninput=()=>moveSearch(0,true);$('search-prev').onclick=()=>moveSearch(-1);$('search-next').onclick=()=>moveSearch(1);$('calendar-search').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();moveSearch(e.shiftKey?-1:1);}};
async function loadCalendar(jump=false){
  calendarData=await api('/calendar?'+new URLSearchParams({year:$('year').value,method:$('method').value}));
  const method=$('method').value;$('follow-method').disabled=!user||method==='all';$('follow-method').checked=calendarData.follows.includes(method);
  if(jump){const first=calendarData.events.find(e=>e.user_id===null);const y=Number($('year').value);month=first?new Date(dateKey(first.starts)+'T00:00:00Z'):new Date(Date.UTC(y,0,1));selected=keyDate(month);month.setUTCDate(1);}
  if($('calendar-search').value.trim())moveSearch(0,true);else renderCalendar();await refreshChecklist();renderPersonalPlans();await refreshProposals();
}
$('prev').onclick=()=>moveCalendar(-1);
$('next').onclick=()=>moveCalendar(1);
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
  if(e.variants){
    const box=$('event-detail');box.replaceChildren();
    box.append(el('h2',e.title),el('p',timeText(e.starts)+' → '+timeText(e.ends)),el('p',e.note||'','hint'),sourceLink(e.source_url),el('p','Mốc chung cho các phương thức '+e.variants.map(v=>v.method).join(', ')+'. Chọn phương thức để xem hoặc đặt lời nhắc riêng.'));
    for(const v of e.variants)box.append(button('Phương thức '+v.method,()=>showEvent(v)));
    if(!$('detail-dialog').open)$('detail-dialog').showModal();return;
  }
  const pinned=e.personal_plan||calendarData.plans?.find(p=>p.event_id===e.id);
  const schedule=pinned||e;
  const box=$('event-detail');box.replaceChildren();box.append(el('h2',e.title),el('p',timeText(e.starts)+' → '+timeText(e.ends)),el('p',e.note||'', 'hint'));
  if(e.source_url){const a=el('a','Mở thông báo chính thức ↗');a.href=e.source_url;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
  if(pinned){
    box.append(el('h3','Kế hoạch cá nhân đã lưu'),el('p',timeText(pinned.starts)+' → '+timeText(pinned.ends)));
    if(pinned.revision!==e.revision)box.append(el('p','Cảnh báo: kế hoạch cá nhân khác lịch chính thức. Lời nhắc vẫn theo kế hoạch cũ.','plan-warning'));
  }
  if(schedule.ends<Date.now()/1000)box.append(el('p','Mốc đã qua; không thể tạo nhắc mới cho ngày đã qua.','hint'));
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
        if(!input.checked&&((edge==='start'?schedule.starts:schedule.ends)-days*86400<=Date.now()/1000))input.disabled=true;
        l.append(input,document.createTextNode(days?'Trước '+days+' ngày':'Đúng thời điểm'));group.append(l);
      }form.append(group);
    }
    const save=el('button','Lưu nhắc lịch');save.type='submit';form.append(save);
    form.onsubmit=ev=>{ev.preventDefault();safe(async()=>{
      const fd=new FormData(form);await api('/calendar/reminders',{method:'POST',body:{event_id:e.id,before_start:fd.getAll('start').map(Number),before_end:fd.getAll('end').map(Number)}});
      $('detail-dialog').close();flash('Đã lưu nhắc lịch. Bật thông báo trên thiết bị để nhận Web Push.');await loadCalendar();
    });};box.append(form);
  }else box.append(button('Đăng nhập để đặt nhắc lịch',()=>{$('detail-dialog').close();requireLogin();}));
  if(!$('detail-dialog').open)$('detail-dialog').showModal();
}
function decodeVapid(s){const b64=s.replace(/-/g,'+').replace(/_/g,'/');const padded=b64+'='.repeat((4-b64.length%4)%4);return Uint8Array.from(atob(padded),c=>c.charCodeAt(0));}
async function refreshPush(){
  const supported='serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window&&window.isSecureContext;
  $('enable-push').disabled=!user||!supported;$('disable-push').disabled=!user||!supported;
  if(!supported){$('push-status').textContent='Thiết bị/trình duyệt chưa hỗ trợ Web Push hoặc trang chưa dùng HTTPS.';return;}
  const config=pushConfig=await api('/push/config');
  if(!config.enabled){$('enable-push').disabled=true;$('push-status').textContent='Server chưa được cấu hình VAPID.';return;}
  const reg=pushRegistration=await navigator.serviceWorker.register('/product-sw.js',{scope:'/'});
  const sub=await reg?.pushManager.getSubscription();
  $('push-status').textContent=Notification.permission==='denied'?'Bạn đã chặn thông báo. Thay đổi trong cài đặt thiết bị.':sub?'Thiết bị có subscription. Nhấn Bật để liên kết với tài khoản hiện tại.':'Chưa bật trên thiết bị này.';
}
$('enable-push').onclick=()=>safe(async()=>{
  if(!requireLogin())return;
  const config=pushConfig;if(!config?.enabled||!pushRegistration)throw Error('Server chưa cấu hình VAPID hoặc đang chuẩn bị Service Worker.');
  const permission=await Notification.requestPermission();if(permission!=='granted')throw Error('Bạn chưa cấp quyền nhận thông báo.');
  const reg=await navigator.serviceWorker.ready;
  let sub=await reg.pushManager.getSubscription();
  if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decodeVapid(config.public_key)});
  await api('/push/subscribe',{method:'POST',body:sub.toJSON()});flash('Đã liên kết thiết bị nhận Web Push.');await refreshPush();
});
$('disable-push').onclick=()=>safe(async()=>{if(!requireLogin())return;const reg=await navigator.serviceWorker.getRegistration('/'),sub=await reg?.pushManager.getSubscription();
  if(sub){await api('/push/unsubscribe',{method:'POST',body:{endpoint:sub.endpoint}});await sub.unsubscribe();}
  flash('Đã tắt thông báo trên thiết bị này.');await refreshPush();
});
async function refreshChecklist(){
  const b=$('linked-checklist');b.replaceChildren();
  if(!user){b.append(el('p','Đăng nhập để liên kết checklist.','hint'));return;}
  const owner=user.id;const data=await api('/calendar/checklist?'+new URLSearchParams({year:$('year').value,method:$('method').value,account_id:owner}));
  if(user?.id!==owner||data.account_id!==owner)return;
  if(!data.items.length)b.append(el('p','Chưa có kế hoạch F3 đã lưu. Mở Checklist và chọn Liên kết với lịch.','hint'));
  for(const p of data.items){
    const row=el('div',undefined,'entry'),done=p.tasks.filter(t=>t.done).length;
    row.append(el('strong',p.year+' · '+p.method+(p.path?' / '+p.path:'')+' · '+done+'/'+p.tasks.length+' hoàn thành'));
    const progress=el('progress');progress.max=p.tasks.length||1;progress.value=done;row.append(progress);
    for(const t of p.tasks.filter(t=>!t.done))row.append(el('p','○ '+t.title,'hint'));
    b.append(row);
  }
}
async function openNoticeEvent(id){
  const e=await api('/calendar/event/'+encodeURIComponent(id));
  if(e.year){$('year').value=String(e.year);$('method').value=e.method;}
  selected=dateKey(e.starts);month=new Date(selected+'T00:00:00Z');month.setUTCDate(1);
  await loadCalendar();showEvent(e);
}
function renderPersonalPlans(){
  const panel=$('personal-plans-panel'),b=$('personal-plans');panel.hidden=!user;b.replaceChildren();
  if(!user)return;
  const plans=calendarData.plans||[];
  if(!plans.length)b.append(el('p','Chưa lưu kế hoạch chính thức nào vào tài khoản.','hint'));
  for(const p of plans){
    const row=el('div',undefined,'entry');row.append(el('strong',p.title),el('p',timeText(p.starts)+' → '+timeText(p.ends)));
    if(p.revision!==p.official_revision)row.append(el('p','Kế hoạch cũ; hạn chính thức hiện tại: '+timeText(p.official_ends),'plan-warning'));
    row.append(button('Xem sự kiện',()=>openNoticeEvent(p.event_id)));b.append(row);
  }
}
async function refreshProposals(){
  const b=$('update-proposals');b.replaceChildren();if(!user)return;
  const data=await api('/calendar/proposals');
  if(!data.items.length)b.append(el('p','Chưa có đề xuất thay đổi lịch.','hint'));
  const labels={pending:'Chờ xác nhận',deferred:'Để sau',accepted:'Đã đồng ý',rejected:'Đã từ chối',superseded:'Đã có phiên bản mới hơn'};
  for(const p of data.items){
    const row=el('div',undefined,'entry proposal');row.append(el('strong',p.title+' · '+labels[p.state]),el('p','Bản lịch '+p.revision+' · '+p.year+' / '+p.method,'hint'));
    const dates=el('div',undefined,'proposal-dates');
    const old=el('div');old.append(el('strong','Lịch trước'),el('p',p.old_starts===null?'Mốc mới, chưa có lịch cũ':timeText(p.old_starts)+' → '+timeText(p.old_ends)));
    const next=el('div');next.append(el('strong','Lịch chính thức mới'),el('p',timeText(p.new_starts)+' → '+timeText(p.new_ends)));
    dates.append(old,next);row.append(dates,sourceLink(p.source_url));
    if(p.state==='pending'||p.state==='deferred'){
      row.append(el('p','Chỉ khi đồng ý, kế hoạch cá nhân và lời nhắc mới chuyển sang mốc mới.','hint'));
      for(const o of p.offsets){
        const prior=o.edge==='start'?p.old_starts:p.old_ends,after=o.edge==='start'?p.new_starts:p.new_ends;
        row.append(el('p',(o.edge==='start'?'Mở':'Đóng')+' · '+o.days_before+' ngày: '+(prior===null?'—':timeText(prior-o.days_before*86400))+' → '+timeText(after-o.days_before*86400),'hint'));
      }
      for(const [title,decision] of [['Đồng ý cập nhật','accepted'],['Không cập nhật','rejected'],['Để sau','deferred']]){
        const btn=button(title,async()=>{
          await api('/calendar/proposals/'+p.id+'/decision',{method:'POST',body:{decision}});
          flash(decision==='accepted'?'Đã cập nhật kế hoạch. Các mốc nhắc đã qua không được gửi bù.':decision==='rejected'?'Đã giữ kế hoạch cũ; hãy đối chiếu hạn chính thức.':'Đã lưu đề xuất để xử lý sau.');
          await loadCalendar();await refreshNotices();
        },decision==='accepted'?'':'secondary');btn.dataset.decision=decision;row.append(btn);
      }
    }else if(p.state==='rejected')row.append(el('p','Giữ kế hoạch đã lưu; luôn kiểm tra hạn chính thức mới nhất.','plan-warning'));
    if(p.history.length){const d=el('details');d.append(el('summary','Lịch sử quyết định'));for(const x of p.history)d.append(el('p',labels[x.decision]+' · '+timeText(x.created_at),'hint'));row.append(d);}
    b.append(row);
  }
}
async function refreshNotices(){const b=$('notices');b.replaceChildren();$('nav-notices').hidden=!user;$('read-all').hidden=!user;if(!user){b.append(el('p','Đăng nhập để xem thông báo của bạn.','hint'));return;}
  const owner=user.id;const d=await api('/calendar/notices');if(user?.id!==owner)return;if(!d.items.length)b.append(el('p','Chưa có thông báo.','hint'));
  $('unread-count').textContent=d.unread?'('+d.unread+')':'';
  for(const n of d.items){const item=el('div',undefined,'entry'+(!n.read_at?' unread':''));item.append(el('span',n.kind==='announcement'?'Thông báo tuyển sinh':n.kind==='change'?'Cập nhật lịch':'Nhắc lịch','notice-type'),el('strong',(!n.read_at?'● ':'')+n.title),el('p',timeText(n.created_at),'hint'),button('Xem sự kiện',async()=>{await api('/calendar/notices/'+n.id+'/read',{method:'POST',body:{}});await refreshNotices();if(n.kind==='change'){await refreshProposals();$('personal-plans-panel').scrollIntoView({behavior:'smooth'});}else await openNoticeEvent(n.event_id);}),button('Đã đọc',async()=>{await api('/calendar/notices/'+n.id+'/read',{method:'POST',body:{}});await refreshNotices();}));b.append(item);}
}
$('read-all').onclick=()=>safe(async()=>{await api('/calendar/notices/read-all',{method:'POST',body:{}});await refreshNotices();});
$('nav-notices').onclick=()=>setTimeout(()=>$('notices').scrollIntoView({behavior:'smooth'}),350);
function sourceLink(url,label){const a=el('a',label||'Nguồn chính thức');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
async function refreshMonitor(){monitorData=await api('/monitor');const status=$('monitor-status'),changes=$('change-list');status.replaceChildren();changes.replaceChildren();
  for(const s of monitorData.sources){const row=el('div',undefined,'entry');row.append(sourceLink(s.url,s.label),el('p',s.last_error?'Kiểm tra thất bại: '+s.last_error:s.successful_at?'Kiểm tra: '+timeText(s.successful_at):'Chưa kiểm tra lần đầu.','hint'));status.append(row);}
  for(const c of monitorData.changes){const row=el('div',undefined,'entry');row.append(el('strong',c.reviewed_at?'Đã kiểm duyệt':'Phát hiện thay đổi — đang chờ xác minh'),el('p',timeText(c.detected_at),'hint'),sourceLink(c.url));const details=el('details');details.append(el('summary','Xem phần nội dung thay đổi'),el('pre',c.summary));row.append(details);if(c.reviewed_at&&c.review_note)row.append(el('p',c.review_note,'hint'));changes.append(row);}
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
async function reviewCandidate(c){
 const b=$('candidate-review');b.replaceChildren();
 b.append(el('p','Kiểm tra nội dung gốc và xác nhận đầy đủ trước khi công bố.','hint'),sourceLink(c.url),el('pre',c.evidence,'review-evidence'),el('p',c.precision_note,'plan-warning'));
 const f=el('form',undefined,'review-form'),errorBox=el('p','','review-error');errorBox.hidden=true;
 function field(title,name,type,value){const l=el('label',title),n=document.createElement(type==='textarea'?'textarea':'input');n.name=name;if(type!=='textarea')n.type=type;n.value=value??'';n.required=name!=='note';if(name==='title')n.maxLength=160;if(name==='note')n.maxLength=500;l.append(n);f.append(l);return n;}
 const choose=el('label','Công bố vào sự kiện');const sel=document.createElement('select');sel.name='id';sel.append(new Option('Thêm mốc mới',''));
 const data=await api('/calendar?year='+c.year+'&method=all');
 for(const e of data.events.filter(e=>e.user_id===null&&e.method===c.method))sel.append(new Option(e.title+' · '+timeText(e.ends),e.id));
 choose.append(sel);f.append(choose);
 field('Năm tuyển sinh','year','number',c.year).readOnly=true;field('Phương thức','method','text',c.method).readOnly=true;field('Tiêu đề','title','text',c.title);
 field('Bắt đầu (giờ Việt Nam)','start','datetime-local',c.starts===null?'':localInput(c.starts));field('Kết thúc (giờ Việt Nam)','end','datetime-local',localInput(c.ends));field('Ghi chú / điều kiện','note','textarea',c.precision_note);
 const check=el('label',undefined,'check review-confirm'),input=document.createElement('input');input.type='checkbox';input.required=true;check.append(input,document.createTextNode('Tôi đã đọc nguồn, xác nhận đối tượng, ngày giờ và chọn đúng sự kiện mới / cũ.'));f.append(check);
 const actions=el('div',undefined,'controls'),submit=el('button','Xác minh & công bố');submit.type='submit';actions.append(submit,button('Hủy — chưa quyết định',()=>$('candidate-dialog').close()));f.append(errorBox,actions);
 f.onsubmit=e=>{e.preventDefault();safe(async()=>{submit.disabled=true;errorBox.hidden=true;try{const d=fields(f);d.id=d.id||null;d.year=Number(d.year);d.start=dateISO(d.start);d.end=dateISO(d.end);d.source_url=c.url;
  await api('/admin/monitor/candidates/'+c.id+'/publish',{method:'POST',body:d});
  $('candidate-dialog').close();flash('✓ Đã xác minh và công bố lịch.');await Promise.all([loadCandidates(),loadOfficialEvents()]);
 }catch(err){errorBox.textContent=err.message;errorBox.hidden=false;}finally{submit.disabled=false;}});};
 b.append(f);$('candidate-dialog').showModal();
}
async function loadCandidates(){
 const d=await api('/admin/monitor/candidates?history=true'),b=$('deadline-candidates');b.replaceChildren();
 const pending=d.items.filter(c=>c.state==='pending'),history=d.items.filter(c=>c.state!=='pending');
 b.append(el('h3','Chờ xử lý · '+pending.length,'candidate-section-title'));
 if(!pending.length)b.append(el('p','Không có đề xuất chờ xử lý.','empty-state'));
 function card(c){
  const row=el('article',undefined,'candidate-card '+c.state),header=el('div',undefined,'candidate-head');
  header.append(el('strong',c.year+' · Phương thức '+c.method+' · '+c.title),el('span',({pending:'Chờ xác minh',reviewed:'✓ Đã xử lý',rejected:'✕ Đã từ chối',superseded:'Đã có phiên bản mới'})[c.state]||c.state,'review-status '+c.state));
  row.append(header,el('p',(c.starts===null?'Chưa xác định bắt đầu':timeText(c.starts))+' → '+timeText(c.ends),'candidate-dates'),el('pre',c.evidence,'review-evidence'),el('p',c.precision_note,'hint'),sourceLink(c.url));
  if(c.state==='pending'){const actions=el('div',undefined,'controls');actions.append(button('Điền vào form để kiểm chứng',()=>reviewCandidate(c),'primary-action'),button('Từ chối đề xuất',async()=>{if(!confirm('Từ chối đề xuất này? Lịch hiện tại không thay đổi.'))return;await api('/admin/monitor/candidates/'+c.id+'/decision',{method:'POST',body:{decision:'rejected'}});await loadCandidates();},'secondary reject-action'));row.append(actions);}
  else if(c.reviewed_at)row.append(el('p','Xử lý lúc '+timeText(c.reviewed_at),'hint'));
  return row;
 }
 for(const c of pending)b.append(card(c));b.append(el('h3','Lịch sử xử lý · '+history.length,'candidate-section-title'));for(const c of history)b.append(card(c));
}
async function loadAdminChanges(){
  const data=await api('/monitor');$('official-source').replaceChildren(...data.sources.map(s=>new Option(s.label,s.url)));
  await loadCandidates();const b=$('admin-changes');b.replaceChildren();b.append(el('h3','Lịch sử thay đổi nguồn'));
  for(const c of data.changes){const n=el('div',undefined,'entry');n.append(el('strong',c.reviewed_at?'Đã kiểm duyệt':'Chờ kiểm duyệt'),el('p',c.summary,'hint'),sourceLink(c.url));
    if(!c.reviewed_at)n.append(button('Ghi nhận đã kiểm duyệt',async()=>{const note=prompt('Kết quả đối chiếu (nếu đổi ngày, cập nhật lịch ở trên trước):');if(!note?.trim())return;await api('/admin/monitor/'+c.id+'/review',{method:'POST',body:{note}});await loadAdminChanges();}));b.append(n);
  }
}
async function loadAdmin(){if(user?.role!=='admin')return;await Promise.all([loadQuestions(),loadUsers(),loadOfficialEvents(),loadAdminChanges()]);}
$('source-form').onsubmit=e=>{e.preventDefault();safe(async()=>{await api('/admin/monitor/sources',{method:'POST',body:fields(e.target)});e.target.reset();await loadAdminChanges();flash('Đã thêm nguồn. Worker sẽ kiểm tra ở lượt tiếp theo.');});};
$('refresh-admin').onclick=()=>safe(loadAdmin);
safe(async()=>{await refreshUser();await showPage();const id=new URLSearchParams(location.search).get('event');if(id&&location.hash==='#calendar')await openNoticeEvent(id);});
let backgroundBusy=false;
async function refreshAccountAndNotices(){
 if(backgroundBusy||document.hidden)return;backgroundBusy=true;
 try{
  const current=(await api('/auth/me')).user;
  if((current?.id||null)!==(user?.id||null)){document.querySelector('main').hidden=true;location.reload();return;}
  if(user){await refreshNotices();if(location.hash==='#calendar')await refreshProposals();}
 }catch{}finally{backgroundBusy=false;}
}
setInterval(refreshAccountAndNotices,10000);
document.addEventListener('visibilitychange',refreshAccountAndNotices);
window.addEventListener('focus',refreshAccountAndNotices);
