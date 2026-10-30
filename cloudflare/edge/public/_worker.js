// Advanced-mode Pages front door. The translator is accessible only through
// its service binding; no public backend hostname or account suffix is used.
const ROUTES=new Map([
  ['/health','GET'],
  ['/v1/installations/register','POST'],
  ['/v1/installations/renew','POST'],
  ['/v1/usage','GET'],
  ['/v1/translate','POST'],
]);
const respond=(payload,status=200)=>Response.json(payload,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const unavailable=()=>respond({error:'Translation service unavailable'},503);
function usage(value){
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  const result={};
  for(const key of ['requests','inputBytes','requestsRemaining','inputBytesRemaining'])if(Number.isSafeInteger(value[key])&&value[key]>=0)result[key]=value[key];
  if(typeof value.day==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value.day))result.day=value.day;
  if(typeof value.resetAt==='string'&&/^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(value.resetAt))result.resetAt=value.resetAt;
  return result;
}
async function jsonBody(response){
  // Bound responses even if a service binding is accidentally misconfigured.
  const reader=response.body?.getReader();if(!reader)throw new Error('Missing response');
  const chunks=[];let total=0;
  for(;;){const {value,done}=await reader.read();if(done)break;total+=value.length;if(total>1048576){await reader.cancel();throw new Error('Response too large');}chunks.push(value);}
  const all=new Uint8Array(total);let offset=0;for(const chunk of chunks){all.set(chunk,offset);offset+=chunk.length;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(all));
}
export default {
  async fetch(request,env){
    const url=new URL(request.url),method=ROUTES.get(url.pathname);
    if(!method)return respond({error:'Not found'},404);
    if(request.method!==method)return respond({error:'Method not allowed'},405);
    if(url.search)return respond({error:'Query parameters are not accepted'},400);
    const ip=request.headers.get('CF-Connecting-IP');
    if(!ip||ip.length>64||! /^[a-fA-F0-9:.]+$/.test(ip)||typeof env.TRANSLATION?.fetch!=='function')return unavailable();
    const headers=new Headers({'CF-Connecting-IP':ip});
    for(const key of ['Authorization','Content-Type'])if(request.headers.has(key))headers.set(key,request.headers.get(key));
    try{
      const forwarded=new Request('https://translation.internal'+url.pathname,{
        method:request.method,headers,redirect:'manual',
        ...(method==='POST'?{body:request.body,duplex:'half'}:{}),
      });
      const response=await env.TRANSLATION.fetch(forwarded);
      if(response.status>=300&&response.status<400)return unavailable();
      if(response.status!==200){
        const messages={400:'Invalid request',401:'Access token is invalid or expired',403:'Installation authorization failed',404:'Not found',405:'Method not allowed',413:'Message too large',429:'Translation allowance or request limit reached'};
        return messages[response.status]?respond({error:messages[response.status]},response.status):unavailable();
      }
      const data=await jsonBody(response);
      if(!data||typeof data!=='object'||Array.isArray(data))return unavailable();
      if(url.pathname==='/health')return respond({service:'Improved Chat',translationEnabled:data.translationEnabled===true,publicRegistration:data.publicRegistration===true});
      if(url.pathname==='/v1/usage'){const safe=usage(data);return safe?respond(safe):unavailable();}
      if(url.pathname==='/v1/translate'){
        if(typeof data.text!=='string'||typeof data.source!=='string'||typeof data.target!=='string'||! /^[a-z]{2,3}$/.test(data.source)||! /^[a-z]{2,3}$/.test(data.target))return unavailable();
        return respond({text:data.text,source:data.source,target:data.target,usage:usage(data.usage)});
      }
      if(typeof data.token!=='string'||! /^[a-f0-9]{64}$/.test(data.token)||typeof data.subject!=='string'||! /^install:[0-9a-f-]{36}$/.test(data.subject)||typeof data.expiresAt!=='string'||! /^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(data.expiresAt))return unavailable();
      return respond({token:data.token,subject:data.subject,expiresAt:data.expiresAt});
    }catch{return unavailable();}
  }
};
