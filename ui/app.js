/*
 * HCMUS Guide · Frontend client (Node.js server at ./server.mjs)
 * No frontend build or third-party JS dependencies needed.
 * Backend contract: POST /chat { message, admission_year? }
 * API mode transparently proxied by Node at /api/chat.
 */
const els = {
  header: document.getElementById('site-header'),
  menu: document.getElementById('menu-toggle'),
  mobileNav: document.getElementById('mobile-nav'),
  modal: document.getElementById('assistant-modal'),
  close: document.getElementById('close-modal'),
  newChat: document.getElementById('new-chat'),
  floating: document.getElementById('floating-chat'),
  messages: document.getElementById('messages'),
  form: document.getElementById('chat-form'),
  input: document.getElementById('question'),
  submit: document.getElementById('send-button'),
  count: document.getElementById('character-count'),
  chatMode: document.getElementById('chat-mode'),
  status: document.getElementById('chat-status-text'),
  invitationStatus: document.getElementById('invitation-status'),
};
let mode = 'demo';
let sending = false;
let previousFocus = null;

function updateHeader() {els.header.classList.toggle('is-scrolled', window.scrollY > 40);}
window.addEventListener('scroll', updateHeader, {passive:true});
updateHeader();

function closeMenu() {
  els.mobileNav.hidden=true;
  els.menu.setAttribute('aria-expanded','false');
  els.menu.setAttribute('aria-label','Mở menu');
}
els.menu.addEventListener('click',()=>{
  const open=els.mobileNav.hidden;
  els.mobileNav.hidden=!open;
  els.menu.setAttribute('aria-expanded',String(open));
  els.menu.setAttribute('aria-label',open?'Đóng menu':'Mở menu');
});
els.mobileNav.querySelectorAll('a').forEach(a=>a.addEventListener('click',closeMenu));

// Reveal is optional; users without IntersectionObserver still see everything.
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const io=new IntersectionObserver(entries=>entries.forEach(entry=>{
    if(entry.isIntersecting){entry.target.classList.add('is-visible');io.unobserve(entry.target);}
  }),{threshold:.06,rootMargin:'0px 0px 30px 0px'});
  document.querySelectorAll('.reveal').forEach(node=>io.observe(node));
} else document.querySelectorAll('.reveal').forEach(node=>node.classList.add('is-visible'));

async function openAssistant() {
  const u=await accountNow().catch(()=>null);if(!u){location.href='/portal.html#account';return false;}
  if(chatOwner!==u.id||!activeThread){try{await restoreChat(u);}catch(e){alert(e.message);return false;}}

  if(!els.modal.hidden){els.input.focus();return true;}
  previousFocus=document.activeElement;
  closeMenu();
  els.modal.hidden=false;
  document.body.classList.add('chat-open');
  for(const selector of ['.site-header','.mobile-nav','main','.site-footer','.floating-chat']) {
    const node=document.querySelector(selector); if(node)node.inert=true;
  }
  requestAnimationFrame(()=>els.input.focus());return true;
}
function closeAssistant() {
  if(els.modal.hidden)return;
  els.modal.hidden=true;
  document.body.classList.remove('chat-open');
  for(const selector of ['.site-header','.mobile-nav','main','.site-footer','.floating-chat']) {
    const node=document.querySelector(selector); if(node)node.inert=false;
  }
  if(previousFocus && previousFocus.isConnected && typeof previousFocus.focus==='function')previousFocus.focus();
}
function trapTab(event){
  const focusable=Array.from(els.modal.querySelectorAll('button:not([disabled]),textarea:not([disabled]),a[href]')).filter(node=>node.getClientRects().length>0);
  if(!focusable.length)return;
  const first=focusable[0],last=focusable[focusable.length-1];
  if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
}
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'){if(!els.modal.hidden)closeAssistant();else closeMenu();}
  if(event.key==='Tab' && !els.modal.hidden)trapTab(event);
});
document.querySelectorAll('.js-open-chat').forEach(button=>button.addEventListener('click',openAssistant));
els.close.addEventListener('click',closeAssistant);

function element(tag,className,text) {
  const node=document.createElement(tag);
  if(className)node.className=className;
  if(text!==undefined)node.textContent=String(text); // no unsafe innerHTML
  return node;
}
function scrollMessages() {els.messages.scrollTop=els.messages.scrollHeight;}
function isOfficialSource(source) {
  if(!source || typeof source.url!=='string')return false;
  try{const url=new URL(source.url);return url.protocol==='https:' && (url.hostname==='hcmus.edu.vn' || url.hostname.endsWith('.hcmus.edu.vn'));}
  catch{return false;}
}
function appendMessage(text,author,options={}) {
  const outer=element('div',`msg ${author}`);
  outer.append(element('span','msg-label',author==='user'?'BẠN':'HCMUS GUIDE'));
  outer.append(element('div','msg-bubble',text));
  if(author==='bot' && options.status && options.status!=='answered') {
    const labels={clarification_needed:'CẦN BỔ SUNG THÔNG TIN',insufficient_evidence:'CHƯA CÓ ĐỦ NGUỒN XÁC MINH',error:'LỖI XỬ LÝ'};
    outer.append(element('span','msg-details',labels[options.status]||''));
  }
  if(author==='bot' && Array.isArray(options.sources)) {
    const trusted=options.sources.filter(isOfficialSource);
    if(trusted.length){
      const group=element('div','msg-sources');
      group.append(element('span','msg-details',mode==='demo'?'TRANG CHÍNH THỨC ĐỂ TỰ THAM KHẢO':'NGUỒN THAM KHẢO')); 
      for(const source of trusted){
        const anchor=element('a','',`${source.title || 'Nguồn HCMUS'} ↗`);
        anchor.href=source.url;anchor.rel='noopener noreferrer';anchor.target='_blank';group.append(anchor);
      }
      outer.append(group);
    }
  }
  const welcome=els.messages.querySelector('.chat-welcome');
  if(welcome)welcome.remove();
  els.messages.append(outer);scrollMessages();return outer;
}
function appendTyping() {
  const outer=element('div','msg bot');
  outer.setAttribute('aria-label','Trợ lý đang xử lý câu hỏi');
  outer.append(element('span','msg-label','HCMUS GUIDE'));
  const bubble=element('div','msg-bubble typing');
  for(let i=0;i<3;i++)bubble.append(element('span'));
  outer.append(bubble);els.messages.append(outer);scrollMessages();return outer;
}
function updateStatus(message,error=false){els.status.textContent=message;els.status.classList.toggle('is-error',error);}
function setBusy(value){
  sending=value;els.submit.disabled=value;els.input.disabled=value;
  document.querySelectorAll('[data-question]').forEach(b=>b.disabled=value);
  if (els.newChat) els.newChat.disabled=value;
  if(document.getElementById('chat-history'))document.getElementById('chat-history').disabled=value;
  els.submit.setAttribute('aria-label',value?'Đang gửi câu hỏi':'Gửi câu hỏi');
}
function extractYear(question) {
  const years=[...new Set([...question.matchAll(/\b20\d{2}\b/g)].map(match=>Number(match[0])))];
  return years.length===1 ? years[0] : null;
}
async function askServer(question) {
  const payload={message:question,thread_id:activeThread,account_id:chatOwner};
  const year=extractYear(question);if(year!==null)payload.admission_year=year;
  const controller=new AbortController();
  // Local Ollama may need time to warm up; Node upstream timeout is 130 seconds.
  const timeout=setTimeout(()=>controller.abort(),125000);
  try{
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
    const data=await response.json().catch(()=>null);
    if(response.status===401){location.href='/portal.html#account';throw Error('Phiên đăng nhập đã hết hạn.');}
    if(!data || typeof data.answer!=='string')throw new Error('Server chưa trả JSON theo API Contract.');
    if(!response.ok)throw new Error(data?.error?.message || data.answer || 'Không thể xử lý câu hỏi.');
    if(!Array.isArray(data.sources) || typeof data.status!=='string')throw new Error('Response thiếu status hoặc sources.');
    return data;
  }catch(err){
    if(err.name==='AbortError')throw new Error('Hệ thống phản hồi quá lâu. Vui lòng thử lại.');
    if(err instanceof TypeError)throw new Error('Không kết nối được đến Node.js server. Hãy kiểm tra Terminal.');
    throw err;
  }finally{clearTimeout(timeout);}
}
async function sendQuestion(raw) {
  if(sending)return;
  const question=String(raw||'').trim();
  if(!question){els.input.focus();return;}
  if(question.length>1000){updateStatus('Câu hỏi tối đa 1000 ký tự.',true);return;}
  if(!await openAssistant())return;
  if(sending)return;
  appendMessage(question,'user');els.input.value='';updateCount();setBusy(true);
  const pending=appendTyping();updateStatus('Đang truy xuất thông tin và xử lý câu hỏi…');
  try{
    const data=await askServer(question);
    pending.remove();appendMessage(data.answer,'bot',{status:data.status,sources:data.sources});
    const option=historySelect.selectedOptions[0];if(option?.textContent==='Cuộc trò chuyện mới')option.textContent=question.slice(0,80);
    updateStatus(mode==='demo'?'DEMO MODE · Đây là phản hồi mô phỏng, không phải kết quả truy xuất tuyển sinh.':'API MODE · Hãy đối chiếu nguồn và năm áp dụng.');
  }catch(err){
    pending.remove();
    const errorRow=appendMessage(err.message || 'Đã có lỗi xảy ra.','bot',{status:'error',sources:[]});
    const retry=element('button','chat-retry','↻ Thử gửi lại');
    retry.type='button';
    retry.addEventListener('click',()=>{errorRow.remove();sendQuestion(question);},{once:true});
    errorRow.append(retry);
    updateStatus(err.message||'Không thể gửi câu hỏi.',true);
  }finally{setBusy(false);els.input.focus();}
}
function updateCount(){els.count.textContent=`${els.input.value.length} / 1000`;els.input.style.height='auto';els.input.style.height=`${Math.min(els.input.scrollHeight,130)}px`;}
els.form.addEventListener('submit',event=>{event.preventDefault();sendQuestion(els.input.value);});
els.input.addEventListener('input',updateCount);
els.input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();sendQuestion(els.input.value);}});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>sendQuestion(button.dataset.question)));

// Private history: all reads and writes are account-authorized by FastAPI.
let chatOwner=null,activeThread=null,chatLoading=null;
const historySelect=document.getElementById('chat-history');
async function chatApi(path,method='GET'){
 const r=await fetch('/api/product/chat/threads'+path,{method,cache:'no-store',headers:method==='POST'?{'Content-Type':'application/json'}:{},body:method==='POST'?'{}':undefined});
 if(!r.ok)throw Error('Không tải được cuộc trò chuyện. Hãy đăng nhập lại.');
 return r.json();
}
function welcomeChat(){
 els.messages.replaceChildren();
 appendMessage('Chào bạn! Mình là HCMUS Guide. Bạn muốn hỏi gì về tuyển sinh và ngành học?','bot');
}
async function readThread(id){
 const d=await chatApi('/'+encodeURIComponent(id));activeThread=id;
 welcomeChat();
 for(const t of d.turns){appendMessage(t.question,'user');appendMessage(t.response.answer,'bot',t.response);}
 historySelect.value=id;
}
async function listThreads(preferred){
 const d=await chatApi('');historySelect.replaceChildren(...d.items.map(t=>new Option(t.title,t.id)));
 if(!d.items.length){const t=await chatApi('','POST');return listThreads(t.id);}
 await readThread(d.items.some(t=>t.id===preferred)?preferred:d.items[0].id);
}
async function restoreChat(u){
 if(chatLoading)return chatLoading;
 chatOwner=u.id;activeThread=null;welcomeChat();
 chatLoading=listThreads().catch(e=>{chatOwner=null;throw e;}).finally(()=>{chatLoading=null;});
 return chatLoading;
}
historySelect.onchange=async()=>{if(sending)return;setBusy(true);try{await readThread(historySelect.value);}catch(e){updateStatus(e.message,true);}finally{setBusy(false);}};
els.newChat.onclick=async()=>{if(sending)return;setBusy(true);try{const t=await chatApi('','POST');await listThreads(t.id);updateStatus('Cuộc trò chuyện mới. Lịch sử cũ vẫn được lưu.');}catch(e){updateStatus(e.message,true);}finally{setBusy(false);}};
window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
// The server chooses demo vs API mode; never store API keys or secrets in browser JS.
async function loadMode(){
  try{
    const res=await fetch('/api/config',{cache:'no-store'});
    if(!res.ok)throw new Error('CONFIG_UNAVAILABLE');
    const config=await res.json();mode=config.mode==='api'?'api':'demo';
  }catch{mode='demo';updateStatus('Không đọc được cấu hình Node.js. Hãy chạy npm start.',true);}
  const isApi=mode==='api';
  els.chatMode.textContent=isApi?'API MODE':'DEMO MODE';
  els.chatMode.classList.toggle('api',isApi);
  els.invitationStatus.textContent=isApi?'ĐÃ CHUYỂN SANG API MODE':'BẢN DEMO GIAO DIỆN';
  if(isApi)updateStatus('API MODE · Câu trả lời đến từ FastAPI; hãy đối chiếu nguồn và năm áp dụng.');
}
loadMode();

/* Feature 3 — Year/method-specific admission checklist, separate from chatbot. */
import { ADMISSION_METHODS, PORTAL, commonTasks } from './admission-methods.js';
const planner={
 year:document.querySelector('#planner-year'),method:document.querySelector('#planner-method'),
 path:document.querySelector('#planner-path'),pathWrap:document.querySelector('#planner-path-wrap'),
 methodHelp:document.querySelector('#planner-method-help'),profile:document.querySelector('#planner-profile'),
 sources:document.querySelector('#planner-source-box'),list:document.querySelector('#planner-task-list'),
 percentage:document.querySelector('#planner-percentage'),progress:document.querySelector('#planner-progress-track'),
 fill:document.querySelector('#planner-progress-fill'),counter:document.querySelector('#planner-counter'),
 summary:document.querySelector('#planner-summary'),saved:document.querySelector('#planner-saved'),
 addForm:document.querySelector('#planner-add-form'),addInput:document.querySelector('#planner-new-task'),
 reset:document.querySelector('#planner-reset')
};
let plannerState={done:[],extra:[]};
function selectedMethod(){return (ADMISSION_METHODS[planner.year.value]||[]).find(m=>m.id===planner.method.value)||null;}
function selectedPath(){return selectedMethod()?.paths?.find(p=>p.id===planner.path.value)||null;}
function plannerKey(){return planner.year.value+':'+planner.method.value+':'+planner.path.value;}
let planOwner=null,planReady=false,planVersion=0,syncChain=Promise.resolve(),planFailed=false,pendingSaves=0;
async function accountNow(){const r=await fetch('/api/product/auth/me',{cache:'no-store'});if(!r.ok)throw Error('Không kết nối được tài khoản');return (await r.json()).user;}
function savePlanner(){
 if(!planReady||!planOwner||!selectedMethod())return;
 const uid=planOwner,key=plannerKey(),payload=planPayload();
 planner.saved.textContent='ĐANG LƯU…';planFailed=false;pendingSaves++;
 syncChain=syncChain.catch(()=>{}).then(()=>sendPlan(payload,uid)).then(()=>{if(key===plannerKey())planner.saved.textContent='ĐÃ LƯU VÀO TÀI KHOẢN';}).catch(e=>{planFailed=true;planner.saved.textContent='CHƯA LƯU: '+e.message;}).finally(()=>pendingSaves--);
}
function setOptions(select,items,preferred){
 select.replaceChildren();
 for(const item of items){const option=document.createElement('option');option.value=item.value;option.textContent=item.label;select.append(option);}
 if(items.some(x=>x.value===preferred))select.value=preferred;
}
async function loadPlanner(){
 const v=++planVersion,key=plannerKey();planReady=false;plannerState={done:[],extra:[]};renderPlanner();planner.saved.textContent='ĐANG TẢI…';
 try{
  await syncChain;const u=await accountNow();if(v!==planVersion)return;
  planOwner=u?.id||null;
  if(!u){planner.saved.textContent='ĐĂNG NHẬP ĐỂ LƯU CHECKLIST';return;}
  if(!selectedMethod()){planner.saved.textContent='CHƯA CÓ PHƯƠNG THỨC';return;}
  const r=await fetch('/api/product/calendar/checklist?'+new URLSearchParams({year:planner.year.value,method:planner.method.value}),{cache:'no-store'});
  if(!r.ok)throw Error('Không tải được checklist');
  const p=(await r.json()).items.find(x=>x.path===(selectedPath()?.id||''));
  if(v!==planVersion||key!==plannerKey())return;
  if(p)plannerState={done:p.tasks.filter(t=>t.done).map(t=>t.id),extra:p.tasks.filter(t=>t.id.startsWith('custom-')).map(t=>({id:t.id,title:t.title}))};
  planReady=true;planner.saved.textContent=p?'ĐÃ KHÔI PHỤC TỪ TÀI KHOẢN':'SẴN SÀNG LƯU TỰ ĐỘNG';renderPlanner();
 }catch(e){if(v===planVersion)planner.saved.textContent=e.message;}
}
function updateMethods(preferred,pathPreferred){
 const methods=ADMISSION_METHODS[planner.year.value]||[];
 if(methods.length){planner.method.disabled=false;setOptions(planner.method,methods.map(m=>({value:m.id,label:m.label})),preferred);}
 else{planner.method.disabled=true;setOptions(planner.method,[{value:'',label:'Chưa có phương thức được xác minh'}],'');}
 updatePath(pathPreferred);
}
function updatePath(preferred){
 const method=selectedMethod();
 if(method?.paths?.length){
  planner.pathWrap.hidden=false;
  setOptions(planner.path,method.paths.map(p=>({value:p.id,label:p.label})),preferred);
 }else{
  planner.pathWrap.hidden=true;setOptions(planner.path,[{value:'',label:'Không cần nhánh xét tuyển'}],'');
 }
 loadPlanner();
}
function renderPlanner(){
 const method=selectedMethod(),path=selectedPath();
 planner.list.replaceChildren();planner.profile.replaceChildren();planner.sources.replaceChildren();
 const tasks=method?[...commonTasks(planner.year.value),...method.tasks,...(path?.tasks||[]),...plannerState.extra]:[];
 if(!method){
  const note=document.createElement('p');note.className='planner-empty';
  note.textContent='Chưa có dữ liệu phương thức tuyển sinh năm '+planner.year.value+' được xác minh. Vui lòng chọn năm 2025 hoặc 2026.';
  planner.profile.append(note);
  planner.methodHelp.textContent='Chưa có phương thức được xác minh cho năm này.';
 }else{
  planner.methodHelp.textContent=planner.year.value==='2026'
    ?'Năm 2026 có 1a, 1b, 2; ĐGNL và THPT là hai nhánh của phương thức 2.'
    :'Năm 2025 có phương thức 1a, 1b, 1c, 1d, 2 và 3.';
  const kicker=document.createElement('small');
  kicker.textContent='NĂM '+planner.year.value+' · PHƯƠNG THỨC '+method.id.toUpperCase()+(path?' · '+path.id.toUpperCase():'');
  const title=document.createElement('strong');title.textContent=method.short;
  const desc=document.createElement('p');desc.textContent=method.summary+(path?' '+path.summary:'');
  planner.profile.append(kicker,title,desc);
  const head=document.createElement('span');head.className='planner-sources-title';head.textContent='THAM KHẢO NGUỒN HCMUS';
  const link=document.createElement('a');link.href=method.source;link.target='_blank';link.rel='noopener noreferrer';
  link.textContent='Xem thông báo Phương thức '+method.id+' năm '+planner.year.value+' ↗';
  const all=document.createElement('a');all.href=PORTAL;all.target='_blank';all.rel='noopener noreferrer';all.textContent='Xem danh sách phương thức ↗';
  planner.sources.append(head,link,all);
 }
 for(const task of tasks){
  const line=document.createElement('div');line.className='planner-task';
  const label=document.createElement('label');label.className='planner-task-label';
  const check=document.createElement('input');check.type='checkbox';check.checked=plannerState.done.includes(task.id);check.disabled=!planReady;
  check.setAttribute('aria-label','Đã hoàn thành: '+task.title);
  const content=document.createElement('span');content.className='planner-task-content';
  const title=document.createElement('strong');title.textContent=task.title;content.append(title);
  if(task.detail){const detail=document.createElement('small');detail.textContent=task.detail;content.append(detail);}
  label.append(check,content);line.append(label);
  check.addEventListener('change',()=>{
   plannerState.done=check.checked?[...new Set([...plannerState.done,task.id])]:plannerState.done.filter(id=>id!==task.id);
   savePlanner();renderPlanner();
  });
  if(task.id.startsWith('custom-')){
   const remove=document.createElement('button');remove.type='button';remove.disabled=!planReady;remove.className='planner-remove';
   remove.textContent='×';remove.setAttribute('aria-label','Xóa việc: '+task.title);
   remove.addEventListener('click',()=>{
    plannerState.extra=plannerState.extra.filter(v=>v.id!==task.id);
    plannerState.done=plannerState.done.filter(id=>id!==task.id);
    savePlanner();renderPlanner();
   });
   line.append(remove);
  }
  planner.list.append(line);
 }
 const completed=tasks.filter(t=>plannerState.done.includes(t.id)).length;
 const percent=tasks.length?Math.round(completed/tasks.length*100):0;
 planner.percentage.textContent=percent+'%';planner.fill.style.width=percent+'%';
 planner.progress.setAttribute('aria-valuenow',String(percent));
 planner.counter.textContent=completed+' / '+tasks.length+' việc đã đánh dấu';
 planner.summary.textContent=!method?'Hãy chọn năm có dữ liệu chính thức để bắt đầu.'
  :completed===tasks.length?'Đã đánh dấu hết checklist. Tiếp tục đối chiếu thông báo của trường.'
  :'Còn '+(tasks.length-completed)+' việc trong kế hoạch '+planner.year.value+' · '+method.id+'.';
 planner.addForm.hidden=!method;planner.reset.disabled=!method||!planReady;planner.addInput.disabled=!planReady;
}
planner.year.addEventListener('change',()=>updateMethods());
planner.method.addEventListener('change',()=>updatePath());
planner.path.addEventListener('change',loadPlanner);
planner.addForm.addEventListener('submit',event=>{
 event.preventDefault();if(!selectedMethod())return;
 const title=planner.addInput.value.trim();
 if(!planReady||!title||plannerState.extra.length>=25)return;
 const id='custom-'+Date.now()+'-'+Math.random().toString(36).slice(2,8);
 plannerState.extra.push({id,title});planner.addInput.value='';savePlanner();renderPlanner();
});
planner.reset.addEventListener('click',()=>{
 if(!planReady||!selectedMethod())return;
 if(!confirm('Bỏ đánh dấu tất cả việc đã hoàn thành trong checklist hiện tại?'))return;
 plannerState.done=[];savePlanner();renderPlanner();
});
document.querySelectorAll('.js-open-planner').forEach(button=>{
 button.addEventListener('click',()=>{
  closeAssistant();
  requestAnimationFrame(()=>document.getElementById('planner').scrollIntoView({behavior:'smooth'}));
 });
});
const linkPlan=element('button','planner-reset','Liên kết với lịch tài khoản →');linkPlan.type='button';planner.reset.after(linkPlan);
function planPayload(){
 const m=selectedMethod(),p=selectedPath();
 return {year:Number(planner.year.value),method:m.id,path:p?.id||'',tasks:[...commonTasks(planner.year.value),...m.tasks,...(p?.tasks||[]),...plannerState.extra].map(t=>({id:t.id,title:t.title,done:plannerState.done.includes(t.id)}))};
}
async function sendPlan(payload,expected){
 const r=await fetch('/api/product/calendar/checklist',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,account_id:expected}),keepalive:true});
 if(!r.ok)throw Error('Không lưu được checklist lên tài khoản');
}
linkPlan.onclick=async()=>{
 try{const u=await accountNow();if(!u){location.href='/portal.html#account';return;}
 if(!planReady||planOwner!==u.id||!selectedMethod())return;
 linkPlan.disabled=true;await syncChain;await sendPlan(planPayload(),u.id);
 location.href='/portal.html?year='+encodeURIComponent(planner.year.value)+'&method='+encodeURIComponent(planner.method.value)+'#calendar';
 }catch(e){planner.saved.textContent=e.message;}finally{linkPlan.disabled=false;}
};
window.addEventListener('beforeunload',e=>{if(planFailed||pendingSaves){e.preventDefault();e.returnValue='';}});
updateMethods('2');
(async()=>{
 const v=planVersion;
 try{
  const u=await accountNow();if(!u)return;
  const r=await fetch('/api/product/calendar/checklist?year=0',{cache:'no-store'});if(!r.ok)return;
  const p=(await r.json()).items[0];
  if(v!==planVersion||!p||!ADMISSION_METHODS[p.year])return;
  if([...planner.year.options].some(o=>Number(o.value)===p.year)){planner.year.value=String(p.year);updateMethods(p.method,p.path);}
 }catch{}
})();
document.addEventListener('visibilitychange',async()=>{
 if(document.hidden)return;
 try{const u=await accountNow();if((chatOwner&&chatOwner!==u?.id)||(planOwner&&planOwner!==u?.id))location.reload();}
 catch{}
});
