import test from 'node:test';
import assert from 'node:assert/strict';
import {LLM_MODEL,FALLBACK_MODEL,RULES,buildRequest,checkAnswer,findSlang,findTerms,guessLanguage,prepareGlossary,scriptOf,translateChat} from '../src/civ5-chat.js';

// A slice of the generated table: [kind, en, ko, ru] with Russian case forms.
const glossary=prepareGlossary({langs:['en','ko','ru','zh'],terms:[
  ['unit','Composite Bowman','합성궁병','Меткие лучники|метких лучников|метким лучникам','複合弓手'],
  ['building','Great Library','알렉산드리아 도서관','Александрийская библиотека|Александрийской библиотеки|Александрийскую библиотеку','大圖書館'],
  ['belief','God of the Sea','바다의 신','Бог морей',''],
  ['civ','Korea','한국','Корея','朝鮮'],
]});
const reply=(translation,source_language='en',finish_reason='stop')=>({choices:[{message:{content:JSON.stringify({source_language,translation})},finish_reason}]});
function ai(answer){
  const calls=[];
  return {calls,run:async(model,input)=>{calls.push({model,input});if(model===FALLBACK_MODEL)return {translated_text:'FALLBACK('+input.text+')'};return typeof answer==='function'?answer(input):answer;}};
}

test('official names in any case form become prompt hints with the target-language name',()=>{
  assert.deepEqual(findTerms('Кто строит Александрийскую библиотеку? И сколько метких лучников?','ru','en',glossary).map(t=>[t.from,t.to]),
    [['Александрийская библиотека','Great Library'],['Меткие лучники','Composite Bowman']]);
  assert.deepEqual(findTerms('3 composite bowmen at my border','en','ko',glossary).map(t=>t.to),['합성궁병']);
  assert.deepEqual(findTerms('합성궁병을 보내','ko','en',glossary).map(t=>t.to),['Composite Bowman']);
  // Unknown source: the alphabet picks the glossary language.
  assert.deepEqual(findTerms('Корея строит Бог морей','auto','en',glossary).map(t=>t.to).sort(),['God of the Sea','Korea']);
  assert.deepEqual(findTerms('libraryX koreans','en','ru',glossary),[]);
  // No official name in the target language: the hint still says it is a game term.
  const request=buildRequest('Great Library is mine','en','uk',glossary).messages[1].content;
  assert.match(request,/- "Great Library" \(Civ V building\)/);
  assert.match(buildRequest('Korea','en','zh',glossary).messages[1].content,/Simplified/);
});

test('shorthand hints only for words in the message, by language, capitals where it matters',()=>{
  assert.deepEqual(findSlang('gg wp, I DoW you next turn','en'),['gg: good game (said at the end or when giving up); in unit talk can mean Great General','wp: well played','dow: declaration of war; declare war']);
  assert.deepEqual(findSlang('he said NC first','en'),['NC: National College']);
  assert.ok(findSlang('HE first, then NC','en').some(h=>h.startsWith('HE:')));
  assert.deepEqual(findSlang('ob du kommst?','de'),[]);
  assert.ok(findSlang('спс, щас объява будет','auto').some(h=>h.startsWith('объява')));
  assert.ok(findSlang('ㅋㅋㅋㅋ 도국 먹었다','auto').some(h=>h.startsWith('도국')));
  assert.equal(findSlang('잠수함 만들자','ko').length,0);
  assert.ok(findSlang('gl hf everyone','en').some(h=>h.startsWith('gl hf')));
});

test('scripts and local language guesses',()=>{
  assert.equal(scriptOf('[ICON_GOLD] 100'),null);
  assert.equal(scriptOf('ㅋㅋ'),'hangul');
  assert.equal(scriptOf('東京へ行く'),'kana');
  assert.equal(guessLanguage('Сәлем қалайсың'),'kk');
  assert.equal(guessLanguage('Hello'),null);
});

test('the language model gets a fixed rule prompt, a JSON schema and a hard output cap',async()=>{
  const AI=ai(reply('Привет, хочешь мир?','en'));
  const result=await translateChat({TRANSLATION_ENGINE:'llm',AI},'Hi, want peace?','en','ru',{glossary});
  assert.deepEqual(result,{text:'Привет, хочешь мир?',source:'en'});
  const {model,input}=AI.calls[0];
  assert.equal(model,LLM_MODEL);assert.equal(AI.calls.length,1);
  assert.equal(input.messages[0].content,RULES);
  assert.match(input.messages[1].content,/Target language: Russian\nMessage language: English/);
  assert.equal(input.max_completion_tokens,96+15);
  assert.equal(input.chat_template_kwargs.enable_thinking,false);
  assert.equal(input.response_format.type,'json_schema');
});

test('auto source comes back from the model, or from the alphabet when the model is unsure',async()=>{
  assert.equal((await translateChat({TRANSLATION_ENGINE:'llm',AI:ai(reply('Hi','es'))},'Hola','auto','en',{glossary:null})).source,'es');
  assert.equal((await translateChat({TRANSLATION_ENGINE:'llm',AI:ai(reply('Hi','??'))},'Привет','auto','en',{glossary:null})).source,'ru');
  assert.equal((await translateChat({TRANSLATION_ENGINE:'llm',AI:ai(reply('Hi','xx'))},'Hola','auto','en',{glossary:null})).source,'en');
});

test('a bad model answer falls back to M2M100 between the markup tags',async()=>{
  const text='Give me 5 [ICON_GOLD] per turn';
  for(const bad of [reply('Дай 5 золота за ход'),reply('x'.repeat(200)),reply('',),reply('Дай 5 [ICON_GOLD]','en','length'),{choices:[{message:{content:'not json'}}]},()=>{throw new Error('provider down');}]){
    const AI=ai(bad);
    const result=await translateChat({TRANSLATION_ENGINE:'llm',AI},text,'en','ru',{glossary:null});
    assert.equal(result.text,'FALLBACK(Give me 5) [ICON_GOLD] FALLBACK(per turn)');
    assert.deepEqual(AI.calls.slice(1).map(c=>c.model),[FALLBACK_MODEL,FALLBACK_MODEL]);
  }
  assert.throws(()=>checkAnswer(reply('Дай 5 [ICON_GOLD] [ICON_GOLD]'),text),/markup/);
  assert.equal(checkAnswer({choices:[{message:{content:'```json\n{"source_language":"en","translation":"ok [ICON_GOLD]"}\n```'}}]},text).text,'ok [ICON_GOLD]');
});

test('M2M100 engine switch and same-language messages never call the language model',async()=>{
  const AI=ai(()=>assert.fail('language model must not run'));
  assert.equal((await translateChat({TRANSLATION_ENGINE:'m2m100',AI},'Привет','auto','en')).text,'FALLBACK(Привет)');
  assert.equal(AI.calls[0].input.source_lang,'ru');
  assert.deepEqual(await translateChat({TRANSLATION_ENGINE:'llm',AI},'hello','en','en'),{text:'hello',source:'en'});
  // Unknown Latin language without the model: English is the old, explicit assumption.
  assert.equal((await translateChat({AI},'Hola','auto','en')).source,'en');
});
