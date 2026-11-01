// Languages the service translates between. Codes are what clients send; the
// English name goes into the model prompt. Every code is also an M2M100 code,
// so the fallback model can always take over.
export const LANGUAGE_NAMES={
  en:'English',ru:'Russian',uk:'Ukrainian',be:'Belarusian',kk:'Kazakh',
  pl:'Polish',cs:'Czech',sk:'Slovak',de:'German',fr:'French',es:'Spanish',pt:'Portuguese',
  it:'Italian',nl:'Dutch',sv:'Swedish',da:'Danish',no:'Norwegian',fi:'Finnish',
  hu:'Hungarian',ro:'Romanian',bg:'Bulgarian',sr:'Serbian',hr:'Croatian',el:'Greek',
  tr:'Turkish',ar:'Arabic',vi:'Vietnamese',id:'Indonesian',ja:'Japanese',ko:'Korean',
  zh:'Chinese (Simplified)',
};
export const LANGUAGES=new Set(Object.keys(LANGUAGE_NAMES));
// Pseudo-languages handled around a real one: Russian typed or shown in Latin letters,
// for players whose Civ V font has no Cyrillic.
export const LATIN_RUSSIAN='ru-latn';
