"""Contrôle de la vidéo du jour en 3D (paquet 276). Joue 300 matchs au hasard avec le moteur du site et la sélection
des moments forts de la vidéo (algo/index.html), et écrit un rapport public sans nom ni cote :
simulateur/rapport_video_3d.json.

Règle de retrait, écrite avant de regarder : si un match finit sans sa balle de match en dernier moment, ou si une vidéo
compte moins de 2 ou plus de 6 moments, on remet la vidéo 2D (fichiers du paquet 275)."""
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / 'simulateur' / 'rapport_video_3d.json'
JS = r"""
const fs = require('fs');
const h = fs.readFileSync(process.argv[2], 'utf-8');
const bout = (a, b) => h.slice(h.indexOf(a), h.indexOf(b, h.indexOf(a)));
eval(bout('function Moteur(sim){', 'const logit'));
eval(bout("const PTS = ['0','15','30','40'];", '/* Les probabilités'));
eval(bout('function momentsForts(', 'async function filmDuJour'));
let a = 276; const R = () => { a = (a * 16807) % 2147483647; return a / 2147483647; };
const out = [];
for (let k = 0; k < 300; k++) {
  const n = k % 3 === 2 ? 3 : 2, pa = 0.58 + 0.12 * R(), pb = 0.58 + 0.12 * R();
  const M = Moteur({ a: pa, b: pb, sets_gagnants: n, tb_final: 7 }), S = M.etat(k % 2); let tr = '';
  while (!S.fini) tr += String(M.point(S, R()));
  const F = momentsForts(M, tr, k % 2, 5);
  out.push({ quoi: F.choix.map(x => x.quoi), fin_ok: F.choix[F.choix.length - 1].quoi === 'match' && F.choix[F.choix.length - 1].h === F.final.vainqueur });
}
console.log(JSON.stringify(out));
"""


def mesurer():
    if not shutil.which('node'):
        raise SystemExit('node absent')
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / 'v.js'; f.write_text(JS, encoding='utf-8')
        r = subprocess.run(['node', str(f), str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, timeout=180, check=True)
    return json.loads(r.stdout)


def retrait(res):
    return any(not x['fin_ok'] or not (2 <= len(x['quoi']) <= 6) for x in res)


def main():
    res = mesurer()
    types = Counter(q for x in res for q in x['quoi'])
    longueurs = Counter(len(x['quoi']) for x in res)
    rapport = {'paquet': 277, 'quoi': "Vidéo du jour en 3D : moments forts retenus sur 300 matchs tirés au hasard par le moteur du site.",
               'note': "Échanges illustratifs : seul le vainqueur de chaque point vient de la simulation ; le % ne change pas.",
               'matchs': len(res), 'moments_par_video': {str(k): v for k, v in sorted(longueurs.items())},
               'types_de_moments': dict(types.most_common()), 'balle_de_match_toujours_en_dernier': all(x['fin_ok'] for x in res),
               'retrait_declenche': retrait(res),
               'regle_retrait': "Balle de match absente à la fin, ou moins de 2 / plus de 6 moments : retour à la vidéo 2D (paquet 275)."}
    SORTIE.write_text(json.dumps(rapport, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rapport, ensure_ascii=False, indent=1))
    return 1 if rapport['retrait_declenche'] else 0


if __name__ == '__main__':
    sys.exit(main())
