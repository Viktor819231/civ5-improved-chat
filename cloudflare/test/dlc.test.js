import test from 'node:test';
import assert from 'node:assert/strict';
import {cipher,hex,unhex,utf8,requestAD,responseAD} from '../src/dlc-crypto.js';
import {detectSource,latinFromRussian,russianFromLatin,splitUtf8,translateMessage} from '../src/dlc-text.js';
import {download,downloadPage} from '../edge/public/dlc-download.js';
import edge from '../edge/public/_worker.js';
import {zipSync,unzipSync,strToU8,strFromU8} from 'fflate';

test('WebCrypto RFC5297 Appendix A.1 and authentication failure',async()=>{
  const key=unhex('fffefdfcfbfaf9f8f7f6f5f4f3f2f1f0f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff');
  const c=await cipher(key),ad=[unhex('101112131415161718191a1b1c1d1e1f2021222324252627')];
  const plain=unhex('112233445566778899aabbccddee');
  const sealed=await c.seal(plain,ad);
  assert.equal(hex(sealed),'85632d07c6e8f37f950acd320a2ecc9340c02b9690c4dc04daef7f6afe5c');
  assert.deepEqual(await c.open(sealed,ad),plain);
  sealed[0]^=1;await assert.rejects(c.open(sealed,ad));
});
test('direction, sequence, installation and request tag bind responses',async()=>{
  const c=await cipher(crypto.getRandomValues(new Uint8Array(32)));
  const request=await c.seal(utf8('hello'),requestAD('one','1'));
  const ad=responseAD('one','1',request.slice(0,16));
  const response=await c.seal(utf8('reply'),ad);
  for(const wrong of [requestAD('one','1'),responseAD('two','1',request.slice(0,16)),responseAD('one','2',request.slice(0,16)),responseAD('one','1',new Uint8Array(16))])await assert.rejects(c.open(response,wrong));
});
test('source detection, transliteration, markup and UTF8 preserve companion behavior',async()=>{
  for(const [s,l] of [['Hello','auto'],['Hola amigo','auto'],['Привет','ru'],['Привіт','uk'],['안녕','ko'],['ㅋㅋㅋ','ko'],['日本語','zh'],['ありがとう','ja'],['[ICON_GOLD]','auto']])assert.equal(detectSource(s),l);
  assert.equal(russianFromLatin('Privet, moy drug! https://example.test'),'Привет, мой друг! https://example.test');
  assert.equal(russianFromLatin('dam 5 [ICON_GOLD] za ham'),'дам 5 [ICON_GOLD] за хам');
  assert.equal(latinFromRussian('Объявляю войну, щас Москву возьму!'),'Obyavlyayu voynu, schas Moskvu vozmu!');
  const input='안녕 '.repeat(200),chunks=splitUtf8(input);assert.equal(chunks.join(''),input);assert.ok(chunks.every(c=>utf8(c).length<=500));
  // Markup stays inside the sentence: one request sees "Hello [ICON_GOLD] friend!".
  const calls=[];
  const result=await translateMessage('[COLOR_RED] Privet [ICON_GOLD] drug! [ENDCOLOR]','ru-latn','en',async(t,s,g)=>{calls.push([t,s,g]);return t.replace('Привет','Hello').replace('друг','friend');});
  assert.equal(result.text,'[COLOR_RED] Hello [ICON_GOLD] friend! [ENDCOLOR]');assert.deepEqual(calls,[['[COLOR_RED] Привет [ICON_GOLD] друг! [ENDCOLOR]','ru','en']]);
});
test('auto lets the service name the language; Latin-letter Russian is an output too',async()=>{
  const auto=await translateMessage('Hola, ¿paz?','auto','en',async(t,s)=>{assert.equal(s,'auto');return {text:'Hi, peace?',source:'es'};});
  assert.deepEqual(auto,{text:'Hi, peace?',source:'es'});
  const latin=await translateMessage('Want peace?','en','ru-latn',async(t,s,g)=>{assert.equal(g,'ru');return {text:'Хочешь мир?',source:'en'};});
  assert.deepEqual(latin,{text:'Hochesh mir?',source:'en'});
  // Same language: no request, only the letters change.
  assert.deepEqual(await translateMessage('Привет','ru','ru-latn',()=>assert.fail('no request')),{text:'Privet',source:'ru'});
  await assert.rejects(translateMessage('Hi','en','xx',()=>{}),/supported/);
});
test('personalized ZIP is private, keyless template unchanged, HTTPS mandatory',async()=>{
  const marker='IGT_Config = false; -- PERSONALIZED_DOWNLOAD_CONFIG';
  const names=['InGameTranslateMod/UI/InGameTranslate.lua','InGameTranslateMod/UI/InGameTranslateLobby.lua'];
  const template=zipSync(Object.fromEntries(names.map(n=>[n,strToU8(marker)])));
  let registrations=0;
  const env={ASSETS:{fetch:async()=>new Response(template)},TRANSLATION:{fetch:async()=>{registrations++;return Response.json({id:crypto.randomUUID(),key:hex(crypto.getRandomValues(new Uint8Array(32)))});}}};
  for(const url of ['http://example.test/download','https://example.test/download']){
    const r=await download(new Request(url,{method:'POST'}),env,'203.0.113.1');
    if(url.startsWith('http:')){assert.equal(r.status,403);continue;}
    assert.match(r.headers.get('Cache-Control'),/no-store/);
    const files=unzipSync(new Uint8Array(await r.arrayBuffer()));
    assert.match(strFromU8(files[names[0]]),/IGT_Config = \{id=/);
    assert.equal(strFromU8(files[names[0]]),strFromU8(files[names[1]]));
  }
  assert.equal(registrations,1);assert.equal(strFromU8(unzipSync(template)[names[0]]),marker);
  assert.equal((await download(new Request('https://example.test/download',{method:'POST',headers:{Origin:'https://evil.test'}}),env,'203.0.113.1')).status,403);
});


test('browser download page preserves same-origin POST information and GET never enrolls',async()=>{
  const page=downloadPage();
  assert.equal(page.headers.get('Referrer-Policy'),'strict-origin-when-cross-origin');
  assert.match(await page.text(),/<form method="post" action="\/download">/);
  const env={TRANSLATION:{fetch:()=>{throw new Error('GET must not issue a key');}}};
  const direct=await edge.fetch(new Request('https://example.test/download'),env);
  assert.equal(direct.status,200);assert.match(await direct.text(),/Download Civ5TranslatorMod/);
  const insecure=await edge.fetch(new Request('http://example.test/download'),env);
  assert.equal(insecure.status,303);assert.equal(insecure.headers.get('Location'),'https://example.test/download');
  const rejected=await download(new Request('https://example.test/download',{method:'POST',headers:{Origin:'null'}}),env,'203.0.113.1');
  assert.equal(rejected.status,403);
});

