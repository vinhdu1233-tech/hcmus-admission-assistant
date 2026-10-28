/** Integration test: Node proxy assigns per-browser session IDs with no app.js changes. */
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { test } from 'node:test';

async function pickPort() {
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  return port;
}

test('Node chat proxy uses HttpOnly session cookie and forwards stable UUID to FastAPI', async () => {
  const received=[];
  const upstream = http.createServer(async (req,res) => {
    const chunks=[];
    for await (const piece of req) chunks.push(piece);
    received.push(JSON.parse(Buffer.concat(chunks).toString('utf8')));
    res.writeHead(200, {'Content-Type':'application/json'});
    res.end(JSON.stringify({
      answer:'OK', status:'answered', intent:'major_filter', sources:[]
    }));
  });
  await new Promise(resolve => upstream.listen(0,'127.0.0.1',resolve));
  const backendPort=upstream.address().port;
  const proxyPort=await pickPort();
  const child=spawn(process.execPath,['ui/server.mjs'],{
    cwd:process.cwd(),
    env:{...process.env,PORT:String(proxyPort), CHAT_MODE:'api',
         API_ORIGIN:`http://127.0.0.1:${backendPort}`},
    stdio:['ignore','pipe','pipe']
  });

  try{
    await new Promise((resolve,reject)=>{
      let output='';
      const deadline=setTimeout(()=>reject(Error('Node startup timeout: '+output)),5000);
      child.stdout.on('data',chunk=>{
        output+=chunk.toString();
        if(output.includes('FastAPI target:')){clearTimeout(deadline);resolve();}
      });
      child.on('exit',(code)=>{clearTimeout(deadline);reject(Error('Node exited '+code));});
    });
    const url=`http://127.0.0.1:${proxyPort}/api/chat`;
    const post = (message, cookie) => fetch(url,{
      method:'POST',
      headers:{'Content-Type':'application/json', ...(cookie?{Cookie:cookie}:{})},
      body:JSON.stringify({message,conversation_id:'00000000-0000-0000-0000-000000000000'}),
    });
    const first=await post('Ngành nào xét A01?');
    assert.equal(first.status,200);
    const setCookie=first.headers.get('set-cookie');
    assert.match(setCookie,/hcmus_sid=[0-9a-f-]{36}/);
    assert.match(setCookie,/HttpOnly/);
    assert.match(setCookie,/SameSite=Lax/);
    const cookie=setCookie.split(';')[0];
    const second=await post('2026',cookie);
    assert.equal(second.status,200);
    assert.equal(second.headers.get('set-cookie'),null);
    const other=await post('B00?');
    assert.equal(other.status,200);
    assert.equal(received.length,3);
    assert.match(received[0].conversation_id,/^[0-9a-f-]{36}$/);
    assert.equal(received[0].conversation_id,received[1].conversation_id);
    assert.notEqual(received[0].conversation_id,received[2].conversation_id);
    assert.notEqual(received[0].conversation_id,'00000000-0000-0000-0000-000000000000');
  } finally {
    child.kill('SIGTERM');
    await new Promise(resolve=>upstream.close(resolve));
  }
});
