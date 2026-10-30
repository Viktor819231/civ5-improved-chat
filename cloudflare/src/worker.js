const MODEL = '@cf/meta/m2m100-1.2b';
const LANGUAGES = new Set(['en','ru','uk','ko','fr','de','es','pl','pt','tr','it','nl','sv','zh','ja','ar']);
const bytes = s => new TextEncoder().encode(s).length;
const json = (data, status = 200) => Response.json(data, {status, headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
export const digest = async s => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)))].map(x=>x.toString(16).padStart(2,'0')).join('');
const randomToken = () => [...crypto.getRandomValues(new Uint8Array(32))].map(x=>x.toString(16).padStart(2,'0')).join('');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SECRET = /^[a-f0-9]{64}$/;
export function normalizeNetwork(ip) {
  if(typeof ip!=='string'||ip.length>64)throw new Error('Invalid network');
  const v4=s=>{const a=s.split('.');if(a.length!==4||a.some(x=>!/^\d{1,3}$/.test(x)||Number(x)>255))throw new Error('Invalid network');return a.map(Number);};
  if(!ip.includes(':')){const a=v4(ip);return{ip:a.join('.'),subnet:a.slice(0,3).join('.')+'.0/24'};}
  let s=ip.toLowerCase();
  if(s.includes('.')){const i=s.lastIndexOf(':');const a=v4(s.slice(i+1));s=s.slice(0,i+1)+((a[0]<<8)|a[1]).toString(16)+':'+((a[2]<<8)|a[3]).toString(16);}
  if(!/^[a-f0-9:]+$/.test(s)||(s.match(/::/g)||[]).length>1)throw new Error('Invalid network');
  let parts;
  if(s.includes('::')){const [l,r]=s.split('::');const left=l?l.split(':'):[],right=r?r.split(':'):[];const missing=8-left.length-right.length;if(missing<1)throw new Error('Invalid network');parts=[...left,...Array(missing).fill('0'),...right];}
  else parts=s.split(':');
  if(parts.length!==8||parts.some(x=>! /^[a-f0-9]{1,4}$/.test(x)))throw new Error('Invalid network');
  parts=parts.map(x=>parseInt(x,16).toString(16));
  return{ip:parts.join(':'),subnet:parts.slice(0,4).join(':')+'::/64'};
}
async function networkIdentity(request,env) {
  if(typeof env.IP_HASH_SECRET!=='string'||env.IP_HASH_SECRET.length<32)throw new Error('Network protection is not configured');
  // Cloudflare overwrites this header at its public edge. No X-Forwarded-For
  // or JSON-supplied IP is used. Directly invoking this Worker outside that
  // boundary must not be exposed as another ingress route.
  const network=normalizeNetwork(request.headers.get('CF-Connecting-IP'));
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(env.IP_HASH_SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const hash=async value=>[...new Uint8Array(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(value)))].map(x=>x.toString(16).padStart(2,'0')).join('');
  return{ipKey:await hash('ip:'+network.ip),subnetKey:await hash('subnet:'+network.subnet)};
}
function limit(env, key, fallback) {
  const n = Number(env[key] ?? fallback);
  if (!Number.isSafeInteger(n) || n < 0) throw new Error('Invalid server limit');
  return n;
}
async function body(request, max = 4096) {
  if (!request.headers.get('content-type')?.startsWith('application/json')) throw new Error('JSON required');
  const reader = request.body?.getReader();
  if (!reader) throw new Error('Body required');
  const chunks=[]; let total=0;
  for (;;) {
    const {value,done}=await reader.read(); if(done) break;
    total+=value.length;
    if(total>max){await reader.cancel();throw new Error('Body too large');}
    chunks.push(value);
  }
  const buffer=new Uint8Array(total);let offset=0;
  for(const chunk of chunks){buffer.set(chunk,offset);offset+=chunk.length;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(buffer));
}
const gate = env => env.GATE.get(env.GATE.idFromName('global-v1'));
const call = async (env,path,data) => gate(env).fetch(new Request('https://internal'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}));

export default {
  async fetch(request,env) {
    const url=new URL(request.url);
    if(url.pathname==='/health') return json({service:'Improved Chat',translationEnabled:env.TRANSLATION_ENABLED==='true',publicRegistration:env.REGISTRATION_ENABLED==='true'&&typeof env.IP_HASH_SECRET==='string'&&env.IP_HASH_SECRET.length>=32});
    const enrollment=['/v1/installations/register','/v1/installations/renew'].includes(url.pathname);
    let network;
    if(enrollment||((url.pathname==='/v1/translate'||url.pathname==='/v1/usage')&&env.IP_LIMITS_ENABLED==='true')){
      if(enrollment&&env.REGISTRATION_ENABLED!=='true')return json({error:'Installation registration is disabled'},503);
      try{network=await networkIdentity(request,env);}catch{return json({error:'Network protection is unavailable'},503);}
      const admitted=await call(env,'/admit',{...network,enrollment});
      if(!admitted.ok)return admitted;
    }
    if(enrollment){
      if(request.method!=='POST')return json({error:'Method not allowed'},405);
      let data;try{data=await body(request,1024);}catch{return json({error:'Invalid enrollment request'},400);}
      if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).some(k=>!['version','installationId','registrationSecret'].includes(k))||data.version!==1||typeof data.installationId!=='string'||!UUID.test(data.installationId))return json({error:'Invalid enrollment request'},400);
      const token=request.headers.get('authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
      if(data.registrationSecret!==undefined&&(typeof data.registrationSecret!=='string'||!SECRET.test(data.registrationSecret)))return json({error:'Invalid enrollment request'},400);
      if(!data.registrationSecret&&!token)return json({error:'Installation authorization required'},403);
      return call(env,'/register',{...network,subject:'install:'+data.installationId.toLowerCase(),secretHash:data.registrationSecret?await digest('registration:'+data.registrationSecret):null,tokenHash:token?await digest(token):null,renewOnly:url.pathname.endsWith('/renew')});
    }
    // Deliberately no placeholder that trusts a caller-provided Steam ID.
    if(url.pathname.startsWith('/v1/auth/')) return json({error:'This authentication route is unavailable. Use installation enrollment.'},501);
    if(url.pathname.startsWith('/admin/')) {
      if(env.ADMIN_PROVISIONING_ENABLED!=='true'||!env.ADMIN_SECRET) return json({error:'Not found'},404);
      const presented=request.headers.get('authorization')??'';
      if(await digest(presented)!==await digest('Bearer '+env.ADMIN_SECRET)) return json({error:'Unauthorized'},401);
      if(request.method!=='POST') return json({error:'Method not allowed'},405);
      let data; try {data=await body(request);} catch {return json({error:'Invalid JSON body'},400);}
      if(!data||typeof data!=='object'||Array.isArray(data)) return json({error:'JSON object required'},400);
      if(['/admin/installations/token','/admin/installations/revoke'].includes(url.pathname)) {
        if(typeof data.installationId!=='string'||! /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(data.installationId))return json({error:'Installation UUID required'},400);
        const subject='install:'+data.installationId.toLowerCase();
        return call(env,url.pathname.endsWith('/token')?'/issue':'/revoke',{subject});
      }
      if(['/admin/accounts/token','/admin/accounts/revoke'].includes(url.pathname)) {
        if(typeof data.steamId!=='string'||!/^7656\d{13}$/.test(data.steamId))return json({error:'SteamID64 string required'},400);
        return call(env,url.pathname.endsWith('/token')?'/issue':'/revoke',{subject:'steam:'+data.steamId});
      }
      return json({error:'Not found'},404);
    }
    if(!['/v1/translate','/v1/usage'].includes(url.pathname)) return json({error:'Not found'},404);
    const token=request.headers.get('authorization')?.match(/^Bearer ([a-f0-9]{64})$/)?.[1];
    if(!token) return json({error:'Access token required'},401);
    const tokenHash=await digest(token);
    if(url.pathname==='/v1/usage') {
      if(request.method!=='GET')return json({error:'Method not allowed'},405);
      return call(env,'/usage',{tokenHash});
    }
    if(request.method!=='POST')return json({error:'Method not allowed'},405);
    if(env.TRANSLATION_ENABLED!=='true')return json({error:'Translation is disabled'},503);
    let input;
    try {input=await body(request,8192);}catch{return json({error:'Invalid JSON body'},400);}
    // The public client may be edited freely. It supplies text/languages only;
    // identity, quotas, reservations, time and model choice belong to the server.
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['text','source','target'].includes(k)))return json({error:'Only text, source and target are accepted'},400);
    const {text,source,target}=input;
    if(typeof text!=='string'||!text.trim()||!LANGUAGES.has(source)||!LANGUAGES.has(target))return json({error:'Provide text and a supported explicit source/target language'},400);
    if(bytes(text)>limit(env,'MAX_INPUT_BYTES',1000))return json({error:'Message too long'},413);
    const reservation=await call(env,'/reserve',{tokenHash,inputBytes:bytes(text),...network});
    if(!reservation.ok)return reservation;
    const {reservationId,usage}=await reservation.json();
    try {
      const result=source===target?{translated_text:text}:await env.AI.run(MODEL,{text,source_lang:source,target_lang:target});
      if(typeof result?.translated_text!=='string'||!result.translated_text.trim())throw new Error('Invalid model response');
      return json({text:result.translated_text,source,target,usage});
    } catch {
      // Never include message text, provider responses or credentials in errors.
      return json({error:'Translation failed; reservation remains charged'},502);
    } finally {
      await call(env,'/release',{reservationId});
    }
  }
};

export class TranslationGate {
  constructor(ctx,env){this.ctx=ctx;this.env=env;}
  async fetch(request) {
    if(this.ctx.storage.getAlarm&&this.ctx.storage.setAlarm&&await this.ctx.storage.getAlarm()===null)await this.ctx.storage.setAlarm(Date.now()+86400000);
    const path=new URL(request.url).pathname;
    const data=await request.json();
    return this.ctx.storage.transaction(async tx=>{
      const now=Date.now(),day=new Date(now).toISOString().slice(0,10),minute=Math.floor(now/60000),hour=Math.floor(now/3600000);
      const daily=async key=>{const value=await tx.get(key);return value?.day===day?value:{day,count:0,minute,minuteCount:0,registrations:0,inputBytes:0,requests:0,lastSeen:now};};
      const issue=async subject=>{
        const version=await tx.get('version:'+subject)??0;
        const token=randomToken(),expires=now+limit(this.env,'TOKEN_TTL_SECONDS',2592000)*1000;
        const hash=await digest(token);
        const previous=await tx.get('tokens:'+subject)??[];
        const retained=previous.filter(p=>p.expires>now).slice(-2);
        for(const p of previous)if(!retained.some(r=>r.hash===p.hash))await tx.delete('token:'+p.hash);
        await tx.put('token:'+hash,{subject,version,created:now,expires});
        await tx.put('tokens:'+subject,[...retained,{hash,expires}]);
        return json({token,subject,expiresAt:new Date(expires).toISOString()});
      };
      if(path==='/admit'){
        const ip=await daily('net:'+data.ipKey),subnet=await daily('subnet:'+data.subnetKey),all=await daily('admissions');
        if(ip.minute!==minute){ip.minute=minute;ip.minuteCount=0;ip.enrollmentMinuteCount=0;}
        if(subnet.minute!==minute){subnet.minute=minute;subnet.minuteCount=0;}
        if(ip.minuteCount>=limit(this.env,'IP_REQUESTS_PER_MINUTE',120)||subnet.minuteCount>=limit(this.env,'SUBNET_REQUESTS_PER_MINUTE',240)||ip.count>=limit(this.env,'IP_REQUESTS_PER_DAY',20000)||all.count>=limit(this.env,'GLOBAL_ADMISSIONS_PER_DAY',40000)||(data.enrollment&&(ip.enrollmentMinuteCount??0)>=limit(this.env,'IP_ENROLLMENT_PER_MINUTE',10)))return json({error:'Network request limit reached'},429);
        ip.minuteCount++;ip.count++;if(data.enrollment)ip.enrollmentMinuteCount=(ip.enrollmentMinuteCount??0)+1;
        subnet.minuteCount++;ip.lastSeen=subnet.lastSeen=now;all.count++;all.lastSeen=now;
        await tx.put('net:'+data.ipKey,ip);await tx.put('subnet:'+data.subnetKey,subnet);await tx.put('admissions',all);
        return json({allowed:true});
      }
      if(path==='/register'){
        const subject=data.subject,version=await tx.get('version:'+subject)??0;
        const registration=await tx.get('registration:'+subject);
        const credential=data.tokenHash?await tx.get('token:'+data.tokenHash):null;
        const bearerValid=credential&&credential.subject===subject&&credential.version===version&&credential.expires>now;
        const secretValid=registration&&data.secretHash===registration.secretHash&&registration.version===version;
        if(registration&&(!secretValid&&!bearerValid))return json({error:'Installation authorization failed'},403);
        const ip=await daily('net:'+data.ipKey),subnet=await daily('subnet:'+data.subnetKey),global=await daily('registrations');
        if(!registration){
          // A known private/operator installation cannot be claimed by UUID alone.
          const existing=await tx.get('account:'+subject),issued=await tx.get('tokens:'+subject);
          if(((existing||issued?.length)&&!bearerValid)||data.renewOnly||!data.secretHash)return json({error:'Installation authorization failed'},403);
          if(ip.registrations>=limit(this.env,'IP_REGISTRATIONS_PER_DAY',3)||subnet.registrations>=limit(this.env,'SUBNET_REGISTRATIONS_PER_DAY',12)||global.count>=limit(this.env,'GLOBAL_REGISTRATIONS_PER_DAY',200))return json({error:'New installation registration limit reached'},429);
          ip.registrations++;subnet.registrations++;global.count++;ip.lastSeen=subnet.lastSeen=global.lastSeen=now;
          await tx.put('net:'+data.ipKey,ip);await tx.put('subnet:'+data.subnetKey,subnet);await tx.put('registrations',global);
        }
        const issuance=await daily('issuance:'+subject);
        const ipIssue=await daily('ipissuance:'+data.ipKey),allIssue=await daily('allissuance');
        if(ipIssue.hour!==hour){ipIssue.hour=hour;ipIssue.hourCount=0;}
        if(issuance.count>=limit(this.env,'INSTALLATION_TOKEN_ISSUES_PER_DAY',12)||ipIssue.count>=limit(this.env,'IP_TOKEN_ISSUES_PER_DAY',100)||ipIssue.hourCount>=limit(this.env,'IP_TOKEN_ISSUES_PER_HOUR',30)||allIssue.count>=limit(this.env,'GLOBAL_TOKEN_ISSUES_PER_DAY',1000))return json({error:'Installation credential renewal limit reached'},429);
        issuance.count++;issuance.lastSeen=now;await tx.put('issuance:'+subject,issuance);
        ipIssue.count++;ipIssue.hourCount++;allIssue.count++;ipIssue.lastSeen=allIssue.lastSeen=now;
        await tx.put('ipissuance:'+data.ipKey,ipIssue);await tx.put('allissuance',allIssue);
        await tx.put('registration:'+subject,{secretHash:registration?.secretHash??data.secretHash,version,lastSeen:now});
        return issue(subject);
      }
      if(path==='/issue') {
        return issue(data.subject);
      }
      if(path==='/revoke') {
        await tx.put('version:'+data.subject,(await tx.get('version:'+data.subject)??0)+1);
        return json({revoked:true});
      }
      let global=await tx.get('global')??{day,requests:0,inputBytes:0,leases:{}};
      if(path==='/release') {
        const lease=global.leases[data.reservationId];
        if(lease){
          const account=await tx.get('account:'+lease.subject);
          if(account){delete account.leases[data.reservationId];await tx.put('account:'+lease.subject,account);}
          delete global.leases[data.reservationId];await tx.put('global',global);
        }
        return json({released:true});
      }
      const credential=await tx.get('token:'+data.tokenHash);
      if(!credential||!Number.isSafeInteger(credential.expires)||credential.expires<=now||credential.version!==(await tx.get('version:'+credential.subject)??0))return json({error:'Invalid, expired or revoked token'},401);
      const key='account:'+credential.subject;
      let account=await tx.get(key)??{day,requests:0,inputBytes:0,minute,minuteRequests:0,leases:{}};
      // Leases survive midnight, preventing a reset from increasing concurrency.
      if(account.day!==day)account={...account,day,requests:0,inputBytes:0};
      if(global.day!==day)global={...global,day,requests:0,inputBytes:0};
      if(account.minute!==minute){account.minute=minute;account.minuteRequests=0;}
      for(const [id,l]of Object.entries(global.leases))if(l.expires<=now)delete global.leases[id];
      for(const [id,l]of Object.entries(account.leases))if(l.expires<=now)delete account.leases[id];
      const dailyRequests=limit(this.env,'ACCOUNT_DAILY_REQUESTS',1000),dailyBytes=limit(this.env,'ACCOUNT_DAILY_INPUT_BYTES',100000);
      const usage=()=>({day,requests:account.requests,inputBytes:account.inputBytes,requestsRemaining:Math.max(0,dailyRequests-account.requests),inputBytesRemaining:Math.max(0,dailyBytes-account.inputBytes),resetAt:new Date(Date.parse(day+'T00:00:00Z')+86400000).toISOString()});
      if(path==='/usage')return json(usage());
      if(path!=='/reserve')return json({error:'Not found'},404);
      if(!Number.isSafeInteger(data.inputBytes)||data.inputBytes<=0)return json({error:'Invalid reservation'},400);
      if(account.requests+1>dailyRequests||account.inputBytes+data.inputBytes>dailyBytes)return json({error:'Daily account quota reached',usage:usage()},429);
      let ipUsage,subnetUsage;
      if(this.env.IP_LIMITS_ENABLED==='true'){
        if(typeof data.ipKey!=='string')return json({error:'Network protection is unavailable'},503);
        ipUsage=await daily('net:'+data.ipKey);
        subnetUsage=await daily('subnet:'+data.subnetKey);
        if(ipUsage.requests+1>limit(this.env,'IP_DAILY_REQUESTS',6000)||ipUsage.inputBytes+data.inputBytes>limit(this.env,'IP_DAILY_INPUT_BYTES',250000)||subnetUsage.requests+1>limit(this.env,'SUBNET_DAILY_REQUESTS',12000)||subnetUsage.inputBytes+data.inputBytes>limit(this.env,'SUBNET_DAILY_INPUT_BYTES',500000))return json({error:'Network daily translation limit reached'},429);
      }
      if(global.requests+1>limit(this.env,'GLOBAL_DAILY_REQUESTS',5000)||global.inputBytes+data.inputBytes>limit(this.env,'GLOBAL_DAILY_INPUT_BYTES',500000))return json({error:'Global daily quota reached'},429);
      if(account.minuteRequests>=limit(this.env,'ACCOUNT_REQUESTS_PER_MINUTE',30)||Object.keys(account.leases).length>=limit(this.env,'ACCOUNT_CONCURRENCY',2)||Object.keys(global.leases).length>=limit(this.env,'GLOBAL_CONCURRENCY',20))return json({error:'Too many requests'},429);
      const reservationId=randomToken();
      const lease={subject:credential.subject,expires:now+120000};
      account.requests++;account.inputBytes+=data.inputBytes;account.minuteRequests++;account.leases[reservationId]=lease;
      global.requests++;global.inputBytes+=data.inputBytes;global.leases[reservationId]=lease;
      if(ipUsage){ipUsage.requests++;ipUsage.inputBytes+=data.inputBytes;ipUsage.lastSeen=now;await tx.put('net:'+data.ipKey,ipUsage);}
      if(subnetUsage){subnetUsage.requests++;subnetUsage.inputBytes+=data.inputBytes;subnetUsage.lastSeen=now;await tx.put('subnet:'+data.subnetKey,subnetUsage);}
      await tx.put(key,account);await tx.put('global',global);
      return json({reservationId,usage:usage()});
    });
  }
  async alarm(){
    const now=Date.now();
    for(const prefix of ['token:','net:','subnet:','issuance:','ipissuance:']){
      let startAfter;
      for(;;){
        const entries=await this.ctx.storage.list({prefix,limit:500,...(startAfter?{startAfter}:{})});
        for(const [key,value]of entries){
          startAfter=key;
          if((prefix==='token:'&&value.expires<=now)||(prefix!=='token:'&&(value.lastSeen??0)<now-2*86400000))await this.ctx.storage.delete(key);
        }
        if(entries.size<500)break;
      }
    }
    await this.ctx.storage.setAlarm(now+86400000);
  }
}
