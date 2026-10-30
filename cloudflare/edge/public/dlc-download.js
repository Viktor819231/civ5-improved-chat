import {unzipSync,zipSync,strToU8,strFromU8} from 'fflate';
const headers={'Cache-Control':'private, no-store, max-age=0','CDN-Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'};
export const downloadPage=()=>new Response(`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Improved Chat for Civ V</title><style>body{max-width:640px;margin:60px auto;padding:24px;font:18px/1.6 system-ui;background:#0b1619;color:#eff4e8}button{font:inherit;padding:12px 24px;cursor:pointer}a{color:#f4d581}</style><h1>Improved Chat</h1><p>Translate Civilization V chat without a companion app.</p><p>Translation is enabled by default and sends messages selected for translation to Cloudflare. You can turn it off in the mod.</p><form method="post" action="/download"><button>Download Improved Chat</button></form><p>Extract the ZIP and copy <b>InGameTranslateMod</b> into your game's <b>Assets\\DLC</b> folder. Start Civ V and translate chats immediately. Translation is enabled by default.</p><p>Your download contains a private installation key. Keep your ZIP private; send friends this page so they get their own copy. No account or API key entry is required.</p><p>Online translation sends selected messages to Cloudflare. Notes and history stay on your PC. The companion-free beta does not provide Windows clipboard buttons. Translation availability and daily limits apply.</p><p><a href="https://github.com/Viktor819231/civ5-improved-chat">Source and documentation</a></p></html>`,{headers:{...headers,'Referrer-Policy':'strict-origin-when-cross-origin','Content-Type':'text/html; charset=utf-8','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"}});

export async function download(request,env,ip) {
  const url=new URL(request.url);
  // Key delivery MUST be HTTPS; unlike the encrypted native transport.
  if(url.protocol!=='https:'||request.method!=='POST'||(request.headers.get('Origin')&&request.headers.get('Origin')!==url.origin))return new Response('Open the HTTPS download page and try again.',{status:403,headers});
  const template=await env.ASSETS.fetch(new Request(url.origin+'/dlc-template.zip'));
  if(!template.ok)return new Response('Download build is not available yet.',{status:503,headers});
  const archive=new Uint8Array(await template.arrayBuffer());
  if(archive.length>2000000)throw new Error('Invalid template');
  const files=unzipSync(archive);
  const names=['InGameTranslateMod/UI/InGameTranslate.lua','InGameTranslateMod/UI/InGameTranslateLobby.lua'];
  const marker='IGT_Config = false; -- PERSONALIZED_DOWNLOAD_CONFIG';
  for(const name of names)if(!files[name]||strFromU8(files[name]).split(marker).length!==2)throw new Error('Invalid template');
  const registration=await env.TRANSLATION.fetch(new Request('https://translation.internal/v2/dlc/enroll',{method:'POST',headers:{'CF-Connecting-IP':ip}}));
  if(!registration.ok)return new Response(registration.status===429?'Download limit reached. Please try again later.':'Downloads are temporarily unavailable.',{status:registration.status===429?429:503,headers});
  const data=await registration.json();
  if(!/^[a-f0-9-]{36}$/.test(data.id)||!/^[a-f0-9]{64}$/.test(data.key))throw new Error('Invalid enrollment');
  const config=`IGT_Config = {id="${data.id}",key="${data.key}",url="http://civ5-improved-chat-api.pages.dev"};`;
  for(const name of names)files[name]=strToU8(strFromU8(files[name]).replace(marker,config));
  return new Response(zipSync(files,{level:6}),{headers:{...headers,'Content-Type':'application/zip','Content-Disposition':'attachment; filename="Improved-Chat-no-companion.zip"'}});
}
