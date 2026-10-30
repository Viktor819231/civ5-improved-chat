import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{TranslationGate,normalizeNetwork} from '../src/worker.js';

class Storage {
  data=new Map();queue=Promise.resolve();
  alarmAt=null;
  async getAlarm(){return this.alarmAt;}
  async setAlarm(value){this.alarmAt=value;}
  async delete(key){return this.data.delete(key);}
  async list({prefix,limit=500,startAfter}){return new Map([...this.data].filter(([k])=>k.startsWith(prefix)&&(!startAfter||k>startAfter)).sort(([a],[b])=>a.localeCompare(b)).slice(0,limit));}
  async transaction(fn){
    const run=this.queue.then(async()=>{
      const copy=structuredClone(this.data);
      const result=await fn({get:async k=>structuredClone(copy.get(k)),put:async(k,v)=>copy.set(k,structuredClone(v)),delete:async k=>copy.delete(k)});
      this.data=copy;return result;
    });
    this.queue=run.catch(()=>{});return run;
  }
}
function setup(overrides={}){
  const storage=new Storage();let aiCalls=0;
  const env={TRANSLATION_ENABLED:'true',ADMIN_PROVISIONING_ENABLED:'true',ADMIN_SECRET:'test-admin-secret',ACCOUNT_CONCURRENCY:'50',GLOBAL_CONCURRENCY:'50',...overrides};
  const object=new TranslationGate({storage},env);
  env.GATE={idFromName:()=> 'global',get:()=>object};
  env.AI={run:async()=>{aiCalls++;return{translated_text:'Hello'};}};
  const request=(path,{token,admin=false,method='POST',data={},ip='203.0.113.1',forwarded}={})=>worker.fetch(new Request('https://example.test'+path,{method,headers:{'Content-Type':'application/json',...(ip?{'CF-Connecting-IP':ip}:{}),...(forwarded?{'X-Forwarded-For':forwarded}:{}),...(admin?{Authorization:'Bearer test-admin-secret'}:token?{Authorization:'Bearer '+token}:{})},...(method==='GET'?{}:{body:JSON.stringify(data)})}),env);
  const issue=async(steamId='76561198000000001')=>(await(await request('/admin/accounts/token',{admin:true,data:{steamId}})).json()).token;
  const translate=token=>request('/v1/translate',{token,data:{text:'Привет',source:'ru',target:'en'}});
  return{env,request,issue,translate,storage,calls:()=>aiCalls};
}

test('public registration fails closed and never accepts a claimed Steam ID',async()=>{
  const s=setup();
  assert.equal((await s.request('/v1/auth/start',{data:{steamId:'76561198000000001'}})).status,501);
  assert.equal((await s.translate('a'.repeat(64))).status,401);
  assert.equal(s.calls(),0);
});
test('admin provisioning is disabled by default',async()=>{
  const s=setup({ADMIN_PROVISIONING_ENABLED:'false'});
  assert.equal((await s.request('/admin/accounts/token',{admin:true,data:{steamId:'76561198000000001'}})).status,404);
});
test('two credentials for one account share a daily allowance',async()=>{
  const s=setup({ACCOUNT_DAILY_REQUESTS:'1'});const a=await s.issue(),b=await s.issue();
  assert.equal((await s.translate(a)).status,200);
  assert.equal((await s.translate(b)).status,429);
  assert.equal(s.calls(),1);
});
test('revoking and replacing credentials does not reset usage',async()=>{
  const s=setup({ACCOUNT_DAILY_REQUESTS:'1'});const a=await s.issue();
  await s.translate(a);
  await s.request('/admin/accounts/revoke',{admin:true,data:{steamId:'76561198000000001'}});
  assert.equal((await s.translate(a)).status,401);
  const b=await s.issue();assert.equal((await s.translate(b)).status,429);
});
test('global allowance reserved atomically across simultaneous accounts',async()=>{
  const s=setup({GLOBAL_DAILY_REQUESTS:'1'});
  const a=await s.issue(),b=await s.issue('76561198000000002');
  const results=await Promise.all([s.translate(a),s.translate(b)]);
  assert.deepEqual(results.map(r=>r.status).sort(),[200,429]);assert.equal(s.calls(),1);
});
test('failure consumes reservation conservatively but releases concurrency',async()=>{
  const s=setup({ACCOUNT_CONCURRENCY:'1'});const a=await s.issue();
  s.env.AI.run=async()=>{throw new Error('secret provider error');};
  const result=await s.translate(a);assert.equal(result.status,502);
  assert.ok(!(await result.text()).includes('secret provider error'));
  s.env.AI.run=async()=>({translated_text:'Hello'});
  assert.equal((await s.translate(a)).status,200);
  const usage=await(await s.request('/v1/usage',{token:a,method:'GET'})).json();
  assert.equal(usage.requests,2);assert.ok(Number.isFinite(Date.parse(usage.resetAt)));
});
test('limits measure UTF-8 bytes, not JS string length',async()=>{
  const s=setup({ACCOUNT_DAILY_INPUT_BYTES:'11'});const a=await s.issue();
  assert.equal((await s.translate(a)).status,429);assert.equal(s.calls(),0);
});
test('oversized input and unsupported language never call the model',async()=>{
  const s=setup({MAX_INPUT_BYTES:'4'});const a=await s.issue();
  assert.equal((await s.translate(a)).status,413);
  assert.equal((await s.request('/v1/translate',{token:a,data:{text:'hi',source:'auto',target:'en'}})).status,400);
  assert.equal(s.calls(),0);
});
test('service switch disables translation',async()=>{
  const s=setup({TRANSLATION_ENABLED:'false'});const a=await s.issue();
  assert.equal((await s.translate(a)).status,503);assert.equal(s.calls(),0);
});

test('modified clients cannot choose identity, quota, usage, clock or model',async()=>{
  const s=setup();const a=await s.issue();
  for(const extra of [{steamId:'76561198000000002'},{remaining:1000000},{inputBytes:0},{tokens:0},{day:'2099-01-01'},{limit:999999},{model:'unapproved-model'}]){
    const response=await s.request('/v1/translate',{token:a,data:{text:'Привет',source:'ru',target:'en',...extra}});
    assert.equal(response.status,400);
  }
  assert.equal(s.calls(),0);
  const usage=await(await s.request('/v1/usage',{token:a,method:'GET'})).json();
  assert.equal(usage.requests,0);
});

test('concurrent requests across keys cannot overshoot the account quota',async()=>{
  const s=setup({ACCOUNT_DAILY_REQUESTS:'1'});const a=await s.issue(),b=await s.issue();
  const responses=await Promise.all(Array.from({length:8},(_,i)=>s.translate(i%2?a:b)));
  assert.equal(responses.filter(r=>r.status===200).length,1);
  assert.equal(responses.filter(r=>r.status===429).length,7);
  assert.equal(s.calls(),1);
});

test('expired credentials fail and renewal retains account usage',async t=>{
  let now=Date.now();t.mock.method(Date,'now',()=>now);
  const s=setup({TOKEN_TTL_SECONDS:'1',ACCOUNT_DAILY_REQUESTS:'1'});const a=await s.issue();
  assert.equal((await s.translate(a)).status,200);
  now+=1001;
  assert.equal((await s.translate(a)).status,401);
  const b=await s.issue();
  assert.equal((await s.translate(b)).status,429);
  assert.equal(s.calls(),1);
});

test('non-object JSON never reaches inference or credential provisioning',async()=>{
  const s=setup();const a=await s.issue();
  for(const data of [null,[],42,'text']){
    assert.equal((await s.request('/v1/translate',{token:a,data})).status,400);
    assert.equal((await s.request('/admin/accounts/token',{admin:true,data})).status,400);
  }
  assert.equal(s.calls(),0);
});

test('installation provisioning requires admin authorization and a valid UUID',async()=>{
  const s=setup();
  const installationId='12345678-1234-4123-8123-123456789abc';
  assert.equal((await s.request('/admin/installations/token',{data:{installationId}})).status,401);
  assert.equal((await s.request('/admin/installations/token',{admin:true,data:{installationId:'random-text'}})).status,400);
  const result=await(await s.request('/admin/installations/token',{admin:true,data:{installationId}})).json();
  assert.equal(result.subject,'install:'+installationId);
  assert.equal(typeof result.token,'string');assert.equal(result.steamId,undefined);
});
test('reissuing an installation token shares quota and revocation preserves usage',async()=>{
  const s=setup({ACCOUNT_DAILY_REQUESTS:'1'}),installationId='12345678-1234-4123-8123-123456789abc';
  const issue=async()=>(await(await s.request('/admin/installations/token',{admin:true,data:{installationId}})).json()).token;
  const a=await issue();assert.equal((await s.translate(a)).status,200);
  const b=await issue();assert.equal((await s.translate(b)).status,429);
  await s.request('/admin/installations/revoke',{admin:true,data:{installationId}});
  assert.equal((await s.translate(a)).status,401);assert.equal((await s.translate(b)).status,401);
  const c=await issue();assert.equal((await s.translate(c)).status,429);
});
test('manual source dropdown languages are accepted but auto remains rejected',async()=>{
  const s=setup(),token=await s.issue();
  for(const source of ['fr','de','es','pl','pt','tr','it','nl','sv','zh','ja','ar']){
    assert.equal((await s.request('/v1/translate',{token,data:{text:'sample',source,target:'en'}})).status,200);
  }
  assert.equal((await s.request('/v1/translate',{token,data:{text:'sample',source:'auto',target:'en'}})).status,400);
});

const enrollment=n=>({version:1,installationId:'12345678-1234-4123-8123-'+n.toString(16).padStart(12,'0'),registrationSecret:'b'.repeat(64)});
const publicSetup=overrides=>setup({REGISTRATION_ENABLED:'true',IP_LIMITS_ENABLED:'true',IP_HASH_SECRET:'private-test-ip-hmac-secret-32-characters',TOKEN_TTL_SECONDS:'2592000',...overrides});
const register=(s,n,options={})=>s.request('/v1/installations/register',{data:enrollment(n),...options});

test('anonymous enrollment fails closed without server IP secret or trusted edge IP',async()=>{
  const a=publicSetup({IP_HASH_SECRET:''});assert.equal((await register(a,1)).status,503);
  const b=publicSetup();assert.equal((await register(b,1,{ip:null,forwarded:'203.0.113.2'})).status,503);
});
test('recovery preserves subject quota and a different registration secret cannot hijack it',async()=>{
  const s=publicSetup({ACCOUNT_DAILY_REQUESTS:'1'});
  const first=await(await register(s,1)).json();assert.equal(first.subject,'install:'+enrollment(1).installationId);
  assert.equal((await s.translate(first.token)).status,200);
  const recovered=await(await register(s,1)).json();assert.equal(recovered.subject,first.subject);
  assert.equal((await s.translate(recovered.token)).status,429);
  const changed={...enrollment(1),registrationSecret:'c'.repeat(64)};
  assert.equal((await register(s,1,{data:changed})).status,403);
  assert.ok(!JSON.stringify([...s.storage.data]).includes(enrollment(1).registrationSecret));
  assert.ok(!JSON.stringify([...s.storage.data]).includes('203.0.113.1'));
});
test('fresh installation IDs cannot bypass IP new-registration cap or use forged forwarded IPs',async()=>{
  const s=publicSetup({IP_REGISTRATIONS_PER_DAY:'1'});
  assert.equal((await register(s,1,{forwarded:'8.8.8.8'})).status,200);
  assert.equal((await register(s,2,{forwarded:'9.9.9.9'})).status,429);
  assert.equal((await register(s,1)).status,200); // Recovery does not consume a new registration.
});
test('subnet and global registration limits are strict under simultaneous new UUIDs',async()=>{
  const s=publicSetup({SUBNET_REGISTRATIONS_PER_DAY:'1'});
  const results=await Promise.all([register(s,1,{ip:'203.0.113.1'}),register(s,2,{ip:'203.0.113.2'})]);
  assert.deepEqual(results.map(r=>r.status).sort(),[200,429]);
  const g=publicSetup({GLOBAL_REGISTRATIONS_PER_DAY:'1'});
  assert.equal((await register(g,1)).status,200);
  assert.equal((await register(g,2,{ip:'198.51.100.2'})).status,429);
});
test('multiple installations share the IP translation quota',async()=>{
  const s=publicSetup({IP_DAILY_REQUESTS:'1'});
  const a=await(await register(s,1)).json(),b=await(await register(s,2)).json();
  assert.equal((await s.translate(a.token)).status,200);
  assert.equal((await s.translate(b.token)).status,429);
  assert.equal(s.calls(),1);
});
test('credential factory is throttled and at most three active credential hashes remain',async()=>{
  const s=publicSetup({INSTALLATION_TOKEN_ISSUES_PER_DAY:'4'}),tokens=[];
  for(let i=0;i<4;i++)tokens.push((await(await register(s,1)).json()).token);
  assert.equal((await register(s,1)).status,429);
  assert.equal([...s.storage.data.keys()].filter(k=>k.startsWith('token:')).length,3);
  assert.equal((await s.translate(tokens[0])).status,401);
  assert.equal((await s.translate(tokens[3])).status,200);
});
test('admin revocation blocks registration-secret recovery until operator intervention',async()=>{
  const s=publicSetup();await register(s,1);
  await s.request('/admin/installations/revoke',{admin:true,data:{installationId:enrollment(1).installationId}});
  assert.equal((await register(s,1)).status,403);
});
test('enrollment rejects client quota overrides and supports bearer renewal without a secret',async()=>{
  const s=publicSetup();
  assert.equal((await register(s,1,{data:{...enrollment(1),remaining:999999}})).status,400);
  const credential=await(await register(s,1)).json();
  const response=await s.request('/v1/installations/renew',{token:credential.token,data:{version:1,installationId:enrollment(1).installationId}});
  assert.equal(response.status,200);
});
test('UTC rollover refreshes allowance without changing installation identity',async t=>{
  let now=Date.parse('2026-10-30T23:59:00Z');t.mock.method(Date,'now',()=>now);
  const s=publicSetup({ACCOUNT_DAILY_REQUESTS:'1'}),credential=await(await register(s,1)).json();
  assert.equal((await s.translate(credential.token)).status,200);assert.equal((await s.translate(credential.token)).status,429);
  now+=120000;assert.equal((await s.translate(credential.token)).status,200);
});
test('IPv6 spellings normalize and temporary addresses share /64 grouping',()=>{
  assert.equal(normalizeNetwork('2001:0DB8:0001:0002::1').ip,normalizeNetwork('2001:db8:1:2:0:0:0:1').ip);
  assert.equal(normalizeNetwork('2001:db8:1:2::1').subnet,normalizeNetwork('2001:db8:1:2::abcd').subnet);
  assert.throws(()=>normalizeNetwork('not-an-ip'));
});
test('daily cleanup removes expired credentials and old hashed network data',async()=>{
  const s=publicSetup();await register(s,1);
  s.storage.data.set('token:expired',{expires:Date.now()-1});
  s.storage.data.set('net:old',{lastSeen:Date.now()-3*86400000});
  const object=new TranslationGate({storage:s.storage},s.env);await object.alarm();
  assert.ok(!s.storage.data.has('token:expired'));assert.ok(!s.storage.data.has('net:old'));
  assert.ok(s.storage.data.has('registration:install:'+enrollment(1).installationId));
});
