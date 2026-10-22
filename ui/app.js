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

function openAssistant() {
  if(!els.modal.hidden){els.input.focus();return;}
  previousFocus=document.activeElement;
  closeMenu();
  els.modal.hidden=false;
  document.body.classList.add('chat-open');
  for(const selector of ['.site-header','.mobile-nav','main','.site-footer','.floating-chat']) {
    const node=document.querySelector(selector); if(node)node.inert=true;
  }
  requestAnimationFrame(()=>els.input.focus());
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
  els.submit.setAttribute('aria-label',value?'Đang gửi câu hỏi':'Gửi câu hỏi');
}
function extractYear(question) {
  const years=[...new Set([...question.matchAll(/\b20\d{2}\b/g)].map(match=>Number(match[0])))];
  return years.length===1 ? years[0] : null;
}
async function askServer(question) {
  const payload={message:question};
  const year=extractYear(question);if(year!==null)payload.admission_year=year;
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),16000);
  try{
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
    const data=await response.json().catch(()=>null);
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
  if(els.modal.hidden)openAssistant();
  appendMessage(question,'user');els.input.value='';updateCount();setBusy(true);
  const pending=appendTyping();updateStatus('Đang xử lý câu hỏi…');
  try{
    const data=await askServer(question);
    pending.remove();appendMessage(data.answer,'bot',{status:data.status,sources:data.sources});
    updateStatus(mode==='demo'?'DEMO MODE · Đây là phản hồi mô phỏng, không phải kết quả truy xuất tuyển sinh.':'API MODE · Hãy đối chiếu nguồn và năm áp dụng.');
  }catch(err){
    pending.remove();appendMessage(err.message || 'Đã có lỗi xảy ra.','bot',{status:'error',sources:[]});
    updateStatus(err.message||'Không thể gửi câu hỏi.',true);
  }finally{setBusy(false);els.input.focus();}
}
function updateCount(){els.count.textContent=`${els.input.value.length} / 1000`;els.input.style.height='auto';els.input.style.height=`${Math.min(els.input.scrollHeight,130)}px`;}
els.form.addEventListener('submit',event=>{event.preventDefault();sendQuestion(els.input.value);});
els.input.addEventListener('input',updateCount);
els.input.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();sendQuestion(els.input.value);}});
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>{openAssistant();sendQuestion(button.dataset.question);}));

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
