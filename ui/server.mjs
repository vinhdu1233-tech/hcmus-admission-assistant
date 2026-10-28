/**
 * HCMUS Guide local Node.js server. Node >=18, no external dependencies.
 * Default: demo mode. API mode proxies POST /api/chat to FastAPI POST /chat.
 * This proxy avoids frontend/backend cross-origin issues during development.
 */
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number.parseInt(process.env.PORT || '5500', 10);
const MODE = process.env.CHAT_MODE === 'api' ? 'api' : 'demo';
const API_ORIGIN = process.env.API_ORIGIN || 'http://127.0.0.1:8000';
const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.json': 'application/json; charset=utf-8',
};

function json(res, status, value) {
  res.writeHead(status, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'});
  res.end(JSON.stringify(value));
}
function safeError(code, message) {
  return {answer: message, intent: 'unknown', status: 'error', sources: [], error: {code, message}};
}
async function readBody(req) {
  let value = '';
  for await (const chunk of req) {
    value += chunk.toString('utf8');
    if (Buffer.byteLength(value, 'utf8') > 12000) throw new Error('BODY_TOO_LARGE');
  }
  return JSON.parse(value);
}
function demoResponse(message) {
  const txt = message.toLocaleLowerCase('vi');
  const portal = [{title:'Cổng tuyển sinh HCMUS (để tự tham khảo)',url:'https://tuyensinh.hcmus.edu.vn/'}];
  if (/api\s*key|mật khẩu|password|secret|token/i.test(txt)) {
    return {answer:'Mình không thể chia sẻ API key, mật khẩu hoặc thông tin hệ thống riêng tư.',status:'answered',intent:'security',sources:[]};
  }
  if (/2027|2028|2029|2030|điểm chuẩn/i.test(txt)) {
    return {answer:'Đây là bản demo giao diện. Mình chưa thể xác minh điểm chuẩn theo năm, vì vậy sẽ không đưa ra một con số chưa kiểm chứng. Bạn có thể tra cứu thông báo mới nhất tại cổng tuyển sinh chính thức.',status:'insufficient_evidence',intent:'admission_lookup',sources:portal};
  }
  if (/a01|tổ hợp|học phí|phương thức|tuyển sinh|ngành|xét tuyển/i.test(txt)) {
    return {answer:'Mình đã nhận được câu hỏi về tuyển sinh hoặc ngành học. Hiện hệ thống đang ở DEMO MODE và chưa truy xuất cơ sở dữ liệu chính thức. Sau khi nối Backend, câu trả lời sẽ được kiểm chứng theo năm tuyển sinh và kèm nguồn phù hợp.',status:'insufficient_evidence',intent:'admission_lookup',sources:portal};
  }
  if (/năm nhất|ôn tập|học hiệu quả|chuẩn bị|kỹ năng/i.test(txt)) {
    return {answer:'Để chuẩn bị cho năm nhất, bạn có thể hệ thống lại kiến thức nền tảng, luyện thói quen tự học và tìm hiểu trước chương trình ngành dự định theo học. Đây là gợi ý chung, không phải hướng dẫn học vụ chính thức của HCMUS.',status:'answered',intent:'study_guidance',sources:[]};
  }
  return {answer:'Xin chào! Đây là giao diện demo của HCMUS Guide. Mình đã nhận câu hỏi của bạn; chức năng trả lời dựa trên dữ liệu và AI thật sẽ được kết nối qua FastAPI của nhóm.',status:'answered',intent:'unknown',sources:[]};
}

async function handleChat(req, res) {
  let body;
  try {body=await readBody(req);} catch(err) {
    return json(res,400,safeError('INVALID_JSON',err.message==='BODY_TOO_LARGE'?'Dữ liệu gửi lên quá lớn.':'JSON không hợp lệ.'));
  }
  const msg = typeof body?.message === 'string' ? body.message.trim() : '';
  if (!msg || msg.length > 1000) return json(res,400,safeError('INVALID_MESSAGE','Vui lòng nhập câu hỏi từ 1 đến 1000 ký tự.'));
  const year = body.admission_year;
  if (year !== undefined && year !== null && (!Number.isInteger(year) || year < 2000 || year > 2100)) {
    return json(res,400,safeError('INVALID_YEAR','Năm tuyển sinh không hợp lệ.'));
  }
  if (MODE === 'demo') return json(res,200,demoResponse(msg));
  try {
    const upstream = await fetch(new URL('/chat',API_ORIGIN), {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(30000),
    });
    const text = await upstream.text();
    let data;
    try { data = JSON.parse(text); } catch {throw new Error('NON_JSON_RESPONSE');}
    if (typeof data !== 'object' || data === null) throw new Error('INVALID_RESPONSE');
    return json(res, upstream.status >= 200 && upstream.status < 600 ? upstream.status : 502, data);
  } catch (e) {
    console.error('[HCMUS Guide] Backend request failed:',e.name || 'Error');
    return json(res,503,safeError('BACKEND_UNAVAILABLE','Chưa kết nối được Backend FastAPI. Hãy kiểm tra dịch vụ hoặc chuyển về demo mode.'));
  }
}

const server = http.createServer(async (req,res) => {
  const url = new URL(req.url || '/',`http://localhost:${PORT}`);
  if (url.pathname === '/api/config' && req.method === 'GET') return json(res,200,{mode:MODE,version:'1.0.0'});
  if (url.pathname === '/api/chat' && req.method === 'POST') return handleChat(req,res);
  if (url.pathname.startsWith('/api/')) return json(res,404,safeError('NOT_FOUND','Không tìm thấy API.'));
  if (req.method !== 'GET' && req.method !== 'HEAD') return json(res,405,safeError('METHOD_NOT_ALLOWED','Phương thức không hỗ trợ.'));
  if (url.pathname === '/ui' || url.pathname === '/ui/') {
    res.writeHead(302,{Location:'/'});return res.end();
  }
  let pathname;
  try { pathname=decodeURIComponent(url.pathname); } catch { res.writeHead(400);return res.end('Bad path'); }
  if (pathname === '/') pathname='/index.html';
  const absolute=path.resolve(ROOT,`.${pathname}`);
  if (!absolute.startsWith(ROOT + path.sep)) {res.writeHead(403);return res.end('Forbidden');}
  if (!CONTENT_TYPES[path.extname(absolute).toLowerCase()]) {res.writeHead(404);return res.end('Not found');}
  try {
    const content=await readFile(absolute);
    res.writeHead(200,{'Content-Type':CONTENT_TYPES[path.extname(absolute).toLowerCase()],'X-Content-Type-Options':'nosniff','Cache-Control':'no-cache'});
    return res.end(req.method==='HEAD'?undefined:content);
  } catch {res.writeHead(404);return res.end('Not found');}
});
server.listen(PORT,()=>console.log(`\nHCMUS Guide · Node.js ${process.version}\nMode: ${MODE.toUpperCase()}\nOpen: http://localhost:${PORT}/\nFastAPI target: ${API_ORIGIN} (only used in API mode)\n`));
