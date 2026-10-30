import test from 'node:test';
import assert from 'node:assert/strict';
import edge from '../edge/public/_worker.js';

const base='https://civ5-improved-chat-api.pages.dev';
const request=(path='/health',options={})=>new Request(base+path,{headers:{'CF-Connecting-IP':'203.0.113.6',...options.headers},...options});
test('Pages forwards UTF8/auth and edge IP over binding only',async()=>{
  let received;
  const env={TRANSLATION:{fetch:async r=>{received=r;return Response.json({text:'Привіт',source:'en',target:'uk',usage:{requestsRemaining:99,internalHost:'private-value'}},{headers:{'Location':'https://private-value','X-Internal':'private-value'}});}}};
  const original=new Request(base+'/v1/translate',{method:'POST',headers:{'CF-Connecting-IP':'203.0.113.6','X-Forwarded-For':'1.2.3.4','Authorization':'Bearer test-token','Content-Type':'application/json'},body:JSON.stringify({text:'Hello 한국',source:'en',target:'uk'})});
  const response=await edge.fetch(original,env);
  assert.equal(response.status,200);assert.equal(received.url,'https://translation.internal/v1/translate');
  assert.equal(received.headers.get('authorization'),'Bearer test-token');assert.equal(received.headers.get('CF-Connecting-IP'),'203.0.113.6');assert.equal(received.headers.get('X-Forwarded-For'),null);
  assert.equal(received.redirect,'manual');assert.equal((await received.json()).text,'Hello 한국');
  assert.equal(response.headers.get('Location'),null);assert.equal(response.headers.get('X-Internal'),null);
  const data=await response.json();assert.equal(data.text,'Привіт');assert.equal(data.usage.internalHost,undefined);
});
test('admin, legacy auth and unexpected methods never reach the binding',async()=>{
  let calls=0;const env={TRANSLATION:{fetch:async()=>{calls++;throw new Error();}}};
  for(const path of ['/admin/installations/token','/v1/auth/start','/anything'])assert.equal((await edge.fetch(request(path),env)).status,404);
  assert.equal((await edge.fetch(request('/health',{method:'POST'}),env)).status,405);assert.equal(calls,0);
});
test('missing Cloudflare IP/binding fails closed and forwarded IP is not a substitute',async()=>{
  const env={TRANSLATION:{fetch:async()=>{throw new Error('should not call');}}};
  const missing=new Request(base+'/health',{headers:{'X-Forwarded-For':'203.0.113.6'}});
  assert.equal((await edge.fetch(missing,env)).status,503);assert.equal((await edge.fetch(request(),{})).status,503);
});
test('binding exceptions and redirects expose no internal locations or error details',async()=>{
  for(const fetch of [async()=>{throw new Error('private-account-host');},async()=>new Response('private-account-host',{status:302,headers:{Location:'https://private-account-host'}}),async()=>new Response('private-account-host',{status:500})]){
    const response=await edge.fetch(request(),{TRANSLATION:{fetch}});
    assert.equal(response.status,503);assert.equal(response.headers.get('location'),null);assert.ok(!(await response.text()).includes('private-account-host'));
  }
});
test('no HTTP fallback is attempted',async t=>{
  t.mock.method(globalThis,'fetch',()=>{throw new Error('Public HTTP fallback must not happen');});
  assert.equal((await edge.fetch(request(),{})).status,503);
  assert.equal((await edge.fetch(request(),{TRANSLATION:{fetch:async()=>{throw new Error();}}})).status,503);
});
test('contracted enrollment credential response remains usable',async()=>{
  const data={token:'a'.repeat(64),subject:'install:12345678-1234-4123-8123-123456789abc',expiresAt:'2026-11-30T00:00:00.000Z',backend:'private-value'};
  const r=await edge.fetch(request('/v1/installations/register',{method:'POST',body:'{}'}),{TRANSLATION:{fetch:async()=>Response.json(data)}});
  assert.equal(r.status,200);const result=await r.json();assert.equal(result.token,data.token);assert.equal(result.backend,undefined);
});
test('backend error bodies and unexpected success fields are not forwarded',async()=>{
  const rejected=await edge.fetch(request('/v1/usage'),{TRANSLATION:{fetch:async()=>new Response('private-value',{status:429})}});
  assert.equal(rejected.status,429);assert.ok(!(await rejected.text()).includes('private-value'));
  const health=await edge.fetch(request(),{TRANSLATION:{fetch:async()=>Response.json({service:'private-value',translationEnabled:true,publicRegistration:true,backend:'private-value'})}});
  assert.ok(!(await health.text()).includes('private-value'));
});
