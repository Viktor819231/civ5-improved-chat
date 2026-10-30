// Companion translation preprocessing, performed only after authentication.
const TOKEN=/(\[ICON_[A-Z0-9_]+\]|\[COLOR_[A-Z0-9_]+\]|\[ENDCOLOR\]|\[TR[^\]\r\n]{0,32}\])/g;
const letter=/\p{L}/u;
const supported=new Set('en ru uk ko fr de es pl pt tr it nl sv zh ja ar'.split(' '));
const pairs=[['shch','щ'],['sch','щ'],['shh','щ'],['zh','ж'],['kh','х'],['ts','ц'],['ch','ч'],['sh','ш'],['yu','ю'],['ju','ю'],['ya','я'],['ja','я'],['yo','ё'],['jo','ё'],['ye','е'],['eh','э']];
const letters=Object.fromEntries([...'abcdefghijklmnopqrstuvwxyz'].map((x,i)=>[x,[...'абцдефгхийклмнопкрстуввхыз'][i]]));
export function russianFromLatin(text) {
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
export function detectSource(text) {
  const plain=text.replace(TOKEN,''),chars=[...plain].filter(c=>letter.test(c));
  const korean=chars.filter(c=>/\p{Script=Hangul}/u.test(c)).length;
  const cyrillic=chars.filter(c=>/\p{Script=Cyrillic}/u.test(c));
  if(korean&&korean>=cyrillic.length)return 'ko';
  if(cyrillic.length){
    if(cyrillic.some(c=>!'абвгґдеєжзиіїйклмнопрстуфхцчшщъыьэюяё'.includes(c.toLowerCase())))throw new Error('Choose the source language for this Cyrillic script.');
    return /[іїєґ]/i.test(plain)?'uk':'ru';
  }
  if(chars.every(c=>/\p{Script=Latin}/u.test(c)))return 'en';
  throw new Error('Choose a source language. Auto supports English, Russian, Ukrainian and Korean.');
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
export async function translateMessage(text,source,target,translate) {
  if(typeof text!=='string'||new TextEncoder().encode(text).length>6000||!text.trim())throw new Error('Shorten the message to 6,000 UTF-8 bytes.');
  const resolved=source==='ru-latn'?'ru':source==='auto'?detectSource(text):source;
  if(!supported.has(resolved)||!supported.has(target))throw new Error('Choose supported source and target languages.');
  const output=[];
  for(let part of text.split(TOKEN)){
    TOKEN.lastIndex=0;
    if(TOKEN.test(part)||!letter.test(part)){output.push(part);continue;}
    if(source==='ru-latn')part=russianFromLatin(part);
    if(resolved===target){output.push(part);continue;}
    for(const chunk of splitUtf8(part)){
      const core=chunk.trim();
      if(!letter.test(core)){output.push(chunk);continue;}
      output.push(chunk.slice(0,chunk.length-chunk.trimStart().length)+await translate(core,resolved,target)+chunk.slice(chunk.trimEnd().length));
    }
  }
  return {text:output.join(''),source:resolved};
}
