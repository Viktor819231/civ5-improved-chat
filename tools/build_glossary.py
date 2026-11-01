"""Build the official Civ V name glossary used by the translation service.

Reads the installed game's own localisation (10 languages) so translations use
the names players see in their game: "Great Library" -> "Великая библиотека"
-> "대도서관". The output is generated from the local installation and is not
committed (see .gitignore); the service works without it, only less precisely.
"""
from pathlib import Path
import argparse
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization V")
OUTPUT = ROOT / 'cloudflare/src/civ5-terms.generated.js'
LANGS = {'en_us': 'en', 'de_de': 'de', 'es_es': 'es', 'fr_fr': 'fr', 'it_it': 'it',
         'ja_jp': 'ja', 'ko_kr': 'ko', 'pl_pl': 'pl', 'ru_ru': 'ru', 'zh_hant_hk': 'zh'}
# Kinds of game objects whose names players use in chat.
KINDS = [('BUILDING', 'building'), ('UNIT', 'unit'), ('TECH', 'tech'), ('POLICY', 'policy'),
         ('CIV', 'civ'), ('LEADER', 'leader'), ('RESOURCE', 'resource'), ('IMPROVEMENT', 'improvement'),
         ('TERRAIN', 'terrain'), ('FEATURE', 'feature'), ('PROMOTION', 'promotion'), ('BELIEF', 'belief'),
         ('RELIGION', 'religion'), ('SPECIALIST', 'specialist'), ('ERA', 'era'), ('PROJECT', 'project'),
         ('VICTORY', 'victory'), ('CITYSTATE', 'city-state'), ('PROCESS', 'process'), ('ROUTE', 'route'),
         ('RESOLUTION', 'resolution'), ('LEAGUE_PROJECT', 'project')]
SKIP_KEY = re.compile(r'_(HELP|STRATEGY|PEDIA|TEXT|QUOTE|INFO|SUMMARY|DESC_LONG|TITLE|HEADING|LORE|FACT|GAMEPLAY)(_|$)')
SKIP_FILE = re.compile(r'scenario|civilwar|scrambleafrica|scramble_africa|tutorial|credits|leaderdialog', re.I)
NAME_FIELDS = {'Description', 'ShortDescription', 'Adjective'}


def kind_of(key):
    body = key[len('TXT_KEY_'):]
    for prefix, kind in KINDS:
        if body.startswith(prefix + '_'):
            return kind
    return None


def gameplay_roots(assets):
    """Base game, expansions and official DLC; mods such as KEK are not localised."""
    roots = [assets / 'Gameplay/XML']
    roots += sorted((assets / 'DLC').glob('*/Gameplay/XML')) + sorted((assets / 'DLC').glob('*/DLC/*/Gameplay/XML'))
    return [r for r in roots if r.is_dir() and 'kek' not in str(r).lower()]


def name_keys(assets):
    """Text keys the game database uses as object names (not help or pedia text)."""
    keys = {}
    for path in [p for root in gameplay_roots(assets) for p in sorted(root.rglob('*.xml'))]:
        parts = {p.lower() for p in path.parts}
        if 'text' in parts or 'newtext' in parts or SKIP_FILE.search(str(path)):
            continue
        try:
            tree = ET.parse(path)
        except (ET.ParseError, UnicodeDecodeError):
            continue
        for element in tree.iter():
            value = (element.text or '').strip()
            if element.tag in NAME_FIELDS and value.startswith('TXT_KEY_') and not SKIP_KEY.search(value):
                kind = kind_of(value)
                if kind:
                    keys[value] = kind
    return keys


def texts(assets):
    """{language: {key: text}}; expansions override the base game, BNW last."""
    result = {code: {} for code in LANGS.values()}
    folders = [p for root in gameplay_roots(assets) for p in root.rglob('*') if p.is_dir() and p.name.lower() in LANGS]
    def rank(p):
        s = str(p).lower()
        return 3 if 'expansion2' in s else 2 if 'expansion' in s else 1 if 'dlc' in s else 0
    for folder in sorted(folders, key=lambda p: (rank(p), str(p))):
        code = LANGS[folder.name.lower()]
        for path in sorted(folder.glob('*.xml')) + sorted(folder.glob('*.XML')):
            if SKIP_FILE.search(path.name):
                continue
            try:
                tree = ET.parse(path)
            except (ET.ParseError, UnicodeDecodeError):
                continue
            for row in tree.iter('Row'):
                tag, text = row.get('Tag'), row.findtext('Text')
                if tag and text:
                    result[code][tag] = text.strip()
    return result


def clean(text):
    """Game names only: drop markup, keep declension forms separated by '|'."""
    if not text or any(c in text for c in '{}[]<>%\n'):
        return None
    forms = []
    for form in text.split('|'):
        form = re.sub(r'\s+', ' ', form).strip()
        if form and len(form) <= 48 and form not in forms:
            forms.append(form)
    return '|'.join(forms) or None


def build(game=GAME, output=OUTPUT):
    assets = Path(game) / 'Assets'
    if not assets.is_dir():
        raise SystemExit(f'Civ V not found at {game}; pass --game')
    keys, localised = name_keys(assets), texts(assets)
    langs = list(LANGS.values())
    seen, terms = set(), []
    for key in sorted(keys):
        names = [clean(localised[code].get(key)) for code in langs]
        english = names[0]
        if not english or sum(1 for n in names if n) < 2:
            continue
        # Same name for different objects (e.g. a unit and its promotion) once.
        signature = tuple(names)
        if signature in seen:
            continue
        seen.add(signature)
        terms.append([keys[key]] + [n or '' for n in names])
    data = {'source': 'Civilization V: Brave New World localisation', 'langs': langs, 'terms': terms}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('// Generated by tools/build_glossary.py from the local game. Do not commit.\n'
                      'export default ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n',
                      encoding='utf-8')
    print(f'Wrote {len(terms)} official names in {len(langs)} languages to {output}')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=GAME)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.game, args.output)
