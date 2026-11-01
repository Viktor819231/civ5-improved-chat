// Companion translation preprocessing, performed only after authentication.
import {LANGUAGES,LATIN_RUSSIAN} from './languages.js';
import {TAG,guessLanguage} from './civ5-chat.js';
// Earlier translation markers are kept verbatim. Civ icon/colour tags stay
// inside the text so the model sees whole sentences ("5 [ICON_GOLD] per turn").
const MARKER=/(\[TR[^\]\r\n]{0,32}\])/;
const TAG_SPLIT=/(\[(?:ICON_[A-Z0-9_]+|COLOR_[A-Z0-9_]+|ENDCOLOR)\])/;
const letter=/\p{L}/u;
const hasLetters=s=>letter.test(s.replace(TAG,''));
const pairs=[['shch','щ'],['sch','щ'],['shh','щ'],['zh','ж'],['kh','х'],['ts','ц'],['ch','ч'],['sh','ш'],['yu','ю'],['ju','ю'],['ya','я'],['ja','я'],['yo','ё'],['jo','ё'],['ye','е'],['eh','э']];
const letters=Object.fromEntries([...'abcdefghijklmnopqrstuvwxyz'].map((x,i)=>[x,[...'абцдефгхийклмнопкрстуввхыз'][i]]));
function russianWords(text) {
  return text.replace(/https?:\/\/[^\s]+|www\.[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[A-Za-z]+(?:['`][A-Za-z]+)*['`]?/gi,value=>{
    if(value.includes('://')||value.toLowerCase().startsWith('www.')||value.includes('@'))return value;
    const lower=value.toLowerCase();let out='';
    for(let i=0;i<value.length;){
      const pair=pairs.find(([s])=>lower.startsWith(s,i));let count=pair?.[0].length??1;
      const char=lower[i];let replacement=pair?.[1]??("'`".includes(char)?'ь':letters[char]);
      if(!pair&&'iy'.includes(char)&&i>0&&(char==='y'||i===value.length-1)&&'aeiouy'.includes(lower[i-1]))replacement='й';
      if(value[i]!==value[i].toLowerCase())replacement=replacement.toUpperCase();
      out+=replacement;i+=count;
    }
    return out;
  });
}
/** Russian typed in Latin letters ("privet") to Cyrillic; markup tags untouched. */
export function russianFromLatin(text) {
  return text.split(TAG_SPLIT).map((part,i)=>i%2?part:russianWords(part)).join('');
}
// The way players write Russian when their game shows no Cyrillic.
const LATIN={а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'yo',ж:'zh',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'h',ц:'ts',ч:'ch',ш:'sh',щ:'sch',ъ:'',ы:'y',ь:'',э:'e',ю:'yu',я:'ya'};
/** Russian in Cyrillic to the Latin letters every Civ V font can show. */
export function latinFromRussian(text) {
  return [...text].map(c=>{
    const lower=c.toLowerCase(),value=LATIN[lower];
    if(value===undefined)return c;
    return c===lower||!value?value:value[0].toUpperCase()+value.slice(1);
  }).join('');
}
/** A language code for non-Latin letters; 'auto' lets the model recognise Latin-script languages. */
export function detectSource(text) {
  return guessLanguage(text)??'auto';
}
export function splitUtf8(text,limit=500) {
  const chunks=[];const encoder=new TextEncoder();
  while(text){let size=0,end=0,space=0;
    for(const c of text){const width=encoder.encode(c).length;if(size+width>limit)break;size+=width;end+=c.length;if(/\s/u.test(c))space=end;}
    if(end<text.length&&space>end/2)end=space;
    chunks.push(text.slice(0,end));text=text.slice(end);
  }
  return chunks;
}
/**
 * Translate a whole chat message in pieces of at most 500 bytes. `translate`
 * returns {text, source} (or just the text). The result's source is the
 * language the service found, so the player sees "(TR es>en)".
 */
export async function translateMessage(text,source,target,translate) {
  if(typeof text!=='string'||new TextEncoder().encode(text).length>6000||!text.trim())throw new Error('Shorten the message to 6,000 UTF-8 bytes.');
  const to=target===LATIN_RUSSIAN?'ru':target;
  const from=source===LATIN_RUSSIAN?'ru':source==='auto'?detectSource(text):source;
  if((from!=='auto'&&!LANGUAGES.has(from))||!LANGUAGES.has(to))throw new Error('Choose supported source and target languages.');
  const output=[];let detected=from==='auto'?null:from;
  for(let part of text.split(MARKER)){
    if(MARKER.test(part)||!hasLetters(part)){output.push(part);continue;}
    if(source===LATIN_RUSSIAN)part=russianFromLatin(part);
    if(from===to){output.push(part);continue;}
    for(const chunk of splitUtf8(part)){
      const core=chunk.trim();
      if(!hasLetters(core)){output.push(chunk);continue;}
      const result=await translate(core,from,to);
      const value=typeof result==='string'?{text:result,source:from}:result;
      if(!detected&&value.source&&value.source!=='auto')detected=value.source;
      output.push(chunk.slice(0,chunk.length-chunk.trimStart().length)+value.text+chunk.slice(chunk.trimEnd().length));
    }
  }
  const joined=output.join('');
  return {text:target===LATIN_RUSSIAN?latinFromRussian(joined):joined,source:detected??(from==='auto'?'en':from)};
}
