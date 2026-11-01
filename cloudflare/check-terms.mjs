// Deploy guard: the official Civ V names are generated from the local game and
// are not in Git. Without them translation still works, only less precisely.
import {existsSync} from 'node:fs';
if(!existsSync(new URL('./src/civ5-terms.generated.js',import.meta.url))){
  console.error('Official Civ V names are missing. Run tools/build_glossary.py (needs Civ V installed) before deploying.');
  process.exit(1);
}
