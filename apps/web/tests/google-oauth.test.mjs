import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, stat, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { startGoogleOAuth, validateOAuthState, exchangeGoogleCode, GOOGLE_SCOPES, selectOAuthOrigin } from '../lib/google-oauth.ts';
const config = {clientId:'test-client',clientSecret:'test-secret',publicOrigin:'https://leon.example/',sessionSecret:'a'.repeat(48),credentialsFile:'/tmp/test-google.json',repositoryRoot:'/tmp/repository'};
test('Google consent uses PKCE and session-bound signed expiring state', () => {
  const started=startGoogleOAuth(config,'leon_session=owner',1000);
  const url=new URL(started.url);
  assert.equal(url.origin,'https://accounts.google.com');
  assert.equal(url.searchParams.get('redirect_uri'),'https://leon.example/api/google/oauth/callback');
  assert.equal(url.searchParams.get('code_challenge_method'),'S256');
  const cookie=started.cookie.split(';')[0].slice('leon_google_oauth='.length);
  assert.match(started.cookie,/HttpOnly; Secure; SameSite=Lax/);
  const state=url.searchParams.get('state');
  assert.equal(validateOAuthState(config,cookie,state,'leon_session=owner',2000).verifier.length,64);
  for(const [c,s,session,now] of [[cookie,state,'another owner',2000],[cookie,'wrong', 'leon_session=owner',2000],[cookie,state,'leon_session=owner',601001],[cookie+'x',state,'leon_session=owner',2000]])assert.throws(()=>validateOAuthState(config,c,s,session,now));
});
test('Token exchange writes only granted readonly scopes to a private atomic credential file',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'leon-google-test-'));
 try{
  const cfg={...config,credentialsFile:join(dir,'credentials.json')};
  await exchangeGoogleCode(cfg,'fake-code','fake-verifier',async(url,options)=>{
    assert.equal(url,'https://oauth2.googleapis.com/token');assert.equal(options.redirect,'error');
    assert.equal(new URLSearchParams(options.body).get('code_verifier'),'fake-verifier');
    return Response.json({refresh_token:'fake-refresh',scope:GOOGLE_SCOPES.join(' ')+' https://example.org/extra'});
  });
  const saved=JSON.parse(await readFile(cfg.credentialsFile,'utf8'));
  assert.deepEqual(saved.granted_scopes,GOOGLE_SCOPES);assert.equal(saved.refresh_token,'fake-refresh');
  assert.equal((await stat(cfg.credentialsFile)).mode&0o777,0o600);
  await assert.rejects(exchangeGoogleCode(cfg,'fake','fake',async()=>Response.json({access_token:'no-refresh',scope:GOOGLE_SCOPES.join(' ')})));
  assert.deepEqual(JSON.parse(await readFile(cfg.credentialsFile,'utf8')),saved);
  assert.throws(()=>startGoogleOAuth({...cfg,credentialsFile:'/tmp/repository/leak.json'},'session'));
 }finally{await rm(dir,{recursive:true,force:true});}
});

test('LAN connections use the configured HTTPS tunnel while the public domain retains its own callback',()=>{
 const primary='https://leon.example',temporary='https://test.trycloudflare.com';
 assert.equal(selectOAuthOrigin(new Request('http://192.168.1.2:3000/'),primary,temporary),temporary);
 assert.equal(selectOAuthOrigin(new Request(temporary+'/api/google/oauth/start'),primary,temporary),temporary);
 assert.equal(selectOAuthOrigin(new Request(primary+'/api/google/oauth/start'),primary,temporary),primary);
 assert.equal(selectOAuthOrigin(new Request('https://attacker.example/'),primary,temporary),temporary);
 const started=startGoogleOAuth({...config,publicOrigin:temporary},'owner');
 const url=new URL(started.url);assert.equal(url.searchParams.get('redirect_uri'),temporary+'/api/google/oauth/callback');
 const cookie=started.cookie.split(';')[0].slice('leon_google_oauth='.length);
 assert.throws(()=>validateOAuthState(config,cookie,url.searchParams.get('state'),'owner'));
});
