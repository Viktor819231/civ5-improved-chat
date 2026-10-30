import {cipher,hex,unhex,utf8,installationKey,requestAD,responseAD} from './dlc-crypto.js';
import {translateMessage} from './dlc-text.js';

const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export async function dlcRequest(request,env,{call,networkIdentity,digest,translate}) {
  if(env.DLC_ENABLED!=='true')return json({error:'DLC downloads are unavailable'},503);
  const url=new URL(request.url);
  const enrollment=url.pathname==='/v2/dlc/enroll';
  let network;
  try{network=await networkIdentity(request,env);}catch{return json({error:'Service unavailable'},503);}
  const admitted=await call(env,'/admit',{...network,enrollment});
  if(!admitted.ok)return admitted;
  if(enrollment){
    if(request.method!=='POST')return json({error:'Method not allowed'},405);
    if(env.REGISTRATION_ENABLED!=='true')return json({error:'Downloads paused'},503);
    const id=crypto.randomUUID();let key;
    try{key=await installationKey(env.DLC_KEY_SECRET,id);}catch{return json({error:'Service unavailable'},503);}
    const registration=await call(env,'/register',{...network,subject:'install:'+id,secretHash:await digest(hex(crypto.getRandomValues(new Uint8Array(32)))),renewOnly:false});
    if(!registration.ok)return registration;
    const {token}=await registration.json();
    const bound=await call(env,'/dlc-bind',{tokenHash:await digest(token)});
    if(!bound.ok)return bound;
    return json({id,key:hex(key)});
  }
  const match=url.pathname.match(/^\/v2\/dlc\/([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\/([1-9][0-9]{0,14})\/([a-f0-9]{32,12200})$/);
  if(request.method!=='GET'||url.search||!match||match[3].length%2)return json({error:'Invalid request'},400);
  const [,id,seq,encoded]=match;const sealed=unhex(encoded);let aes,plain;
  try{
    aes=await cipher(await installationKey(env.DLC_KEY_SECRET,id));
    plain=new TextDecoder('utf-8',{fatal:true}).decode(await aes.open(sealed,requestAD(id,seq)));
  }catch{return json({error:'Invalid request'},403);}
  const reply=async text=>new Response(hex(await aes.seal(utf8(text),responseAD(id,seq,sealed.slice(0,16)))),{headers:{'Content-Type':'text/plain','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
  // Claim is durable and atomic. No automatic retry can repeat inference.
  const claim=await call(env,'/dlc-claim',{subject:'install:'+id,seq:Number(seq)});
  if(!claim.ok)return reply('error\nRequest expired, was already used, or this download was revoked. Download a fresh copy if needed.');
  const {token}=await claim.json();
  const m=plain.match(/^([a-z-]{2,8})\n([a-z]{2})\n([\s\S]*)$/);
  if(!m)return reply('error\nInvalid translation request.');
  try{
    if(env.TRANSLATION_ENABLED!=='true')return reply('error\nTranslation service is unavailable. Try later.');
    const deadline=Date.now()+30000;
    const result=await translateMessage(m[3],m[1],m[2],async(text,source,target)=>{
      if(Date.now()>deadline)throw new Error('Translation service timed out. Try a shorter message.');
      const response=await translate(new Request('https://internal/v1/translate',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token,'CF-Connecting-IP':request.headers.get('CF-Connecting-IP')},body:JSON.stringify({text,source,target})}),env);
      if(!response.ok)throw new Error(response.status===429?'Translation allowance or request limit reached. Try later.':'Translation service is unavailable. Try later.');
      return (await response.json()).text;
    });
    if(utf8(result.text).length>7800)return reply('error\nTranslation is too long. Try a shorter message.');
    return reply('ok\n'+result.source+'\n'+result.text);
  }catch(error){
    // Only local, fixed validation/provider messages are exposed.
    const message=error.message;
    const safe=/^(Choose |Shorten |Translation (allowance|service))/.test(message)?message:'Translation failed. Try a shorter message.';
    return reply('error\n'+safe);
  }
}
