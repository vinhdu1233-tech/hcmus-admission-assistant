/** Smoke-test the actual served website, not just module syntax. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import net from 'node:net';
import { test } from 'node:test';

async function freePort(){
  const server=net.createServer();
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port;
  await new Promise(resolve=>server.close(resolve));
  return port;
}

test('HCMUS Guide serves all three features and starts a new browser conversation',async()=>{
  const port=await freePort();
  const child=spawn(process.execPath,['ui/server.mjs'],{
    cwd:process.cwd(),env:{...process.env,PORT:String(port),CHAT_MODE:'demo'},
    stdio:['ignore','pipe','pipe']
  });
  try{
    await new Promise((resolve,reject)=>{
      let output='';
      const timeout=setTimeout(()=>reject(new Error('Server start timed out: '+output)),5000);
      child.stdout.on('data',b=>{
        output+=b.toString();
        if(output.includes('FastAPI target:')){clearTimeout(timeout);resolve();}
      });
      child.once('exit',code=>{clearTimeout(timeout);reject(new Error('Node exited: '+code));});
    });

    const root=`http://127.0.0.1:${port}`;
    async function get(path){
      const response=await fetch(root+path);
      assert.equal(response.status,200,path);
      return response.text();
    }

    const html=await get('/');
    for(const phrase of ['id="assistant-modal"','id="new-chat"','id="planner"',
       'id="planner-year"','id="planner-method"','id="planner-task-list"']){
      assert.ok(html.includes(phrase),'Missing website feature: '+phrase);
    }

    const script=await get('/app.js');
    assert.ok(script.includes("from './admission-methods.js'"),'Checklist module not loaded');
    assert.ok(script.includes("125000"),'Local Ollama frontend timeout too short');
    assert.ok(script.includes('/api/conversation/reset'),'New conversation missing');
    assert.ok(script.includes("updateMethods('2')"),'Checklist init missing');

    const methods=await get('/admission-methods.js');
    assert.ok(methods.includes('ADMISSION_METHODS'));
    const css=await get('/style.css');
    assert.ok(css.includes('.planner-panel'));
    assert.ok(css.includes('.new-chat-button'));

    const config=await fetch(root+'/api/config').then(r=>r.json());
    assert.equal(config.mode,'demo');

    const reset=await fetch(root+'/api/conversation/reset',{method:'POST'});
    assert.equal(reset.status,200);
    assert.deepEqual(await reset.json(),{ok:true});
    assert.match(reset.headers.get('set-cookie')||'',/HttpOnly/);

    const blocked=await fetch(root+'/.env');
    assert.equal(blocked.status,404,'Never serve .env or unknown file extensions');
    assert.equal((await fetch(root+'/not-found.js')).status,404);
  }finally{
    child.kill('SIGTERM');
  }
});
