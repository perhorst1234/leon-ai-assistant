import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {GET,POST} from '../app/api/auth/route.ts';

test('native password form registers/logs in with private cookies; wrong password and foreign origin cannot authenticate',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'leon-native-auth-'));
 const keys=['LEON_WEB_AUTH_FILE','LEON_WEB_SESSION_SECRET','LEON_WEB_SETUP_CODE'];
 const saved=Object.fromEntries(keys.map(k=>[k,process.env[k]]));
 process.env.LEON_WEB_AUTH_FILE=join(dir,'account.json');process.env.LEON_WEB_SESSION_SECRET='s'.repeat(48);process.env.LEON_WEB_SETUP_CODE='test-setup-code-at-least-24-chars';
 const send=(fields,origin='https://leon.test')=>POST(new Request('https://leon.test/api/auth',{method:'POST',headers:{Origin:origin,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(fields)}));
 try{
  const registered=await send({action:'register',code:process.env.LEON_WEB_SETUP_CODE,password:'private-test-password',confirm:'private-test-password'});
  assert.equal(registered.status,303);assert.equal(registered.headers.get('location'),'/?space=today');
  assert.match(registered.headers.get('set-cookie'),/HttpOnly; Secure; SameSite=Lax/);
  const logged=await send({action:'login',password:'private-test-password'});
  const cookie=logged.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await GET(new Request('https://leon.test/api/auth',{headers:{cookie}}))).json()).authenticated,true);
  for(const response of [await send({action:'login',password:'wrong'}),await send({action:'login',password:'private-test-password'},'https://attacker.test')]){
   assert.equal(response.headers.get('location'),'/?auth=invalid');assert.equal(response.headers.get('set-cookie'),null);
  }
 }finally{for(const k of keys){if(saved[k]===undefined)delete process.env[k];else process.env[k]=saved[k];}await rm(dir,{recursive:true,force:true});}
});
