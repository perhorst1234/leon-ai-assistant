// Server-only DOM notifications. No marketplace API, session values or page text
// cross the browser binding. The fixed worker reads only known conversations.
const { spawn } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
let socket, sequence = 0, sessionId, running = false, again = false, wakeTimer;
const pending = new Map();
function call(method, params = {}, session) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout')); }, 15000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(session ? { sessionId: session } : {}) }));
  });
}
function worker(dueOnly = false) {
  if (running) { again = true; return; }
  running = true;
  const child = spawn(path.join(root, '.venv/bin/python'), ['-m', 'leon_control_plane.shopper_service', '--follow-up-only', ...(dueOnly ? ['--due-replies-only'] : [])], { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] });
  let output = '';
  child.stdout.on('data', data => { if (output.length < 4096) output += data; });
  child.on('error', () => { running = false; });
  child.on('close', () => {
    running = false;
    clearTimeout(wakeTimer);
    try {
      const state = JSON.parse(output);
      if (Number.isFinite(state.next_reply_due)) wakeTimer = setTimeout(() => worker(true), Math.min(2147483647, Math.max(60000, state.next_reply_due * 1000 - Date.now())));
    } catch { /* No personal logs or automatic external-action retries. */ }
    if (again) { again = false; setTimeout(() => worker(), 15000); }
  });
}
const observer = `(function installLeonInboxObserver(){
  if(!document.documentElement){document.addEventListener('DOMContentLoaded',installLeonInboxObserver,{once:true});return;}
  if(window.__leonInboxObserver) window.__leonInboxObserver.disconnect();
  let timer, previous='';
  const changed=()=>{clearTimeout(timer);timer=setTimeout(()=>{
    const root=document.querySelector('[class*="Messages-module"], [class*="ConversationList"]');
    if(!root) return;
    const value=root.innerText.slice(0,16000);
    if(value===previous) return;
    previous=value;
    window.__leonInboxChanged('changed');
  },1500);};
  window.__leonInboxObserver=new MutationObserver(changed);
  window.__leonInboxObserver.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  changed();
})()`;
(async () => {
  const version = await (await fetch('http://127.0.0.1:9223/json/version')).json();
  socket = new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  socket.addEventListener('message', event => {
    const data = JSON.parse(event.data);
    if (pending.has(data.id)) {
      const promise = pending.get(data.id); pending.delete(data.id); clearTimeout(promise.timer);
      data.error ? promise.reject(new Error('CDP operation failed')) : promise.resolve(data.result);
    } else if (data.sessionId === sessionId && data.method === 'Runtime.bindingCalled' && data.params.name === '__leonInboxChanged') {
      console.log("Inbox DOM change received");
      worker();
    }
  });
  socket.addEventListener('close', () => process.exit(1));
  const targets = await call('Target.getTargets');
  let target = targets.targetInfos.find(t => t.type === 'page' && t.url === 'https://www.marktplaats.nl/messages/' && t.title);
  if (!target) { const created = await call('Target.createTarget', { url: 'https://www.marktplaats.nl/messages/', background: true }); target = created; }
  sessionId = (await call('Target.attachToTarget', { targetId: target.targetId, flatten: true })).sessionId;
  await call('Runtime.enable', {}, sessionId);
  await call('Page.enable', {}, sessionId);
  await call('Runtime.addBinding', { name: '__leonInboxChanged' }, sessionId);
  await call('Page.addScriptToEvaluateOnNewDocument', { source: observer }, sessionId);
  await call('Runtime.evaluate', { expression: observer }, sessionId);
  worker(); // Restore previously scheduled reply deadlines once at startup.
  console.log('Leon server inbox event listener connected');
})().catch(() => { console.error('Inbox listener unavailable'); process.exit(1); });
