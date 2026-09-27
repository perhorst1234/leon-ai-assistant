import assert from 'node:assert/strict';
import test from 'node:test';
import { forwardLeon } from '../lib/leon-proxy.ts';

test('school credentials use only authenticated local routes and refuse foreign origins', async () => {
 const config={url:'http://127.0.0.1:8765',token:'test-only-dashboard-token',webAuth:{}};
 for(const [resource,method,path] of [['magister-status','GET','/api/magister/status'],['magister-login','POST','/api/magister/login'],['magister-start','POST','/api/magister/start']]){
  const body=resource==='magister-login'?JSON.stringify({request_id:'owner-request',password:'dummy-school-pass'}):'{}';
  const request=new Request(`http://localhost:5173/api/leon?resource=${resource}`,{method,headers:{authorization:`Bearer ${config.token}`,origin:'http://localhost:5173','content-type':'application/json'},...(method==='POST'?{body}:{})});
  const r=await forwardLeon(request,config,async (url,options)=>{assert.equal(String(url),`http://127.0.0.1:8765${path}`);if(method==='POST')assert.equal(options.body,body);return Response.json({state:'password_needed',calendar_connected:false});});
  assert.equal(r.status,200);assert.equal(r.headers.get('cache-control'),'no-store');assert.doesNotMatch(await r.text(),/dummy-school-pass/);
 }
 const foreign=new Request('http://localhost:5173/api/leon?resource=magister-login',{method:'POST',headers:{authorization:`Bearer ${config.token}`,origin:'https://other.example','content-type':'application/json'},body:'{"password":"dummy"}'});
 assert.equal((await forwardLeon(foreign,config,()=>{throw Error('must not forward');})).status,403);
});
