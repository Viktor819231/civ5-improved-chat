"""Best-effort informal Russian transliteration, enabled only by explicit choice.

Chat spelling is not standardized (e.g. y/i, missing soft signs). Preserve the
original in the game; this conversion is input to translation, not a claim of
lossless spelling recovery. No dictionaries, network calls or extra API cost.
"""
from __future__ import annotations

import re

_DIGRAPHS = (
    ('shch', 'щ'), ('sch', 'щ'), ('shh', 'щ'),
    ('zh', 'ж'), ('kh', 'х'), ('ts', 'ц'), ('ch', 'ч'), ('sh', 'ш'),
    ('yu', 'ю'), ('ju', 'ю'), ('ya', 'я'), ('ja', 'я'),
    ('yo', 'ё'), ('jo', 'ё'), ('ye', 'е'), ('eh', 'э'),
)
_LETTERS = dict(zip('abcdefghijklmnopqrstuvwxyz', 'абцдефгхийклмнопкрстуввхыз'))
_LETTERS.update(j='й', q='к', w='в', x='х')
_WORDS = re.compile(r"https?://[^\s]+|www\.[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[A-Za-z]+(?:['`][A-Za-z]+)*['`]?",re.IGNORECASE)


def _word(value: str) -> str:
    if '://' in value or value.lower().startswith('www.') or '@' in value:
        return value
    output=[]
    index=0
    lower=value.lower()
    while index<len(value):
        count=1
        replacement=None
        for spelling,letter in _DIGRAPHS:
            if lower.startswith(spelling,index):
                count=len(spelling)
                replacement=letter
                break
        if replacement is None:
            char=lower[index]
            replacement='ь' if char in "'`" else _LETTERS[char]
            # Common word-final spellings: moi, tvoi, igrai, russkii / moy.
            if char in 'iy' and index>0 and (char=='y' or index==len(value)-1) and lower[index-1] in 'aeiouy':
                replacement='й'
        original=value[index:index+count]
        if original.isupper():
            replacement=replacement.upper()
        elif original[0].isupper():
            replacement=replacement.capitalize()
        output.append(replacement)
        index+=count
    return ''.join(output)


def russian_from_latin(text: str) -> str:
    return _WORDS.sub(lambda match:_word(match.group()),text)
