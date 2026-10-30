// RFC 5297 AES-SIV. The HTTPS download is the key-delivery trust boundary.
// Never use this key in a URL, header, log, or unencrypted native request.
import {SIV, WebCryptoProvider} from 'miscreant';
export const utf8 = value => new TextEncoder().encode(value);
export const hex = value => [...value].map(x=>x.toString(16).padStart(2,'0')).join('');
export function unhex(value) {
  if(typeof value!=='string'||value.length%2||!/^[a-f0-9]*$/.test(value))throw new Error('Invalid encoding');
  return Uint8Array.from(value.match(/../g)??[],s=>parseInt(s,16));
}
export const cipher = key => SIV.importKey(key,'AES-SIV',new WebCryptoProvider(crypto));
export async function installationKey(master,id) {
  if(typeof master!=='string'||!/^[a-f0-9]{64}$/.test(master))throw new Error('DLC service unavailable');
  const key=await crypto.subtle.importKey('raw',unhex(master),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC',key,utf8('ImprovedChat/DLC/key/v1:'+id)));
}
export const requestAD=(id,seq)=>['IGT-request/v1',id,seq].map(utf8);
export const responseAD=(id,seq,tag)=>[...['IGT-response/v1',id,seq].map(utf8),tag];
