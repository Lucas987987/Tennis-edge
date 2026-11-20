"""Contrôle du réalisme des échanges du direct en 3D (paquet 275). Lance le moteur G3D de algo/index.html dans node,
joue 150 coups d'échange par surface et écrit un rapport public (aucun nom, aucune cote) :
simulateur/rapport_3d_echanges.json. Les échanges sont illustratifs : rien de tout cela ne change le %.

Règle de retrait, écrite avant de regarder : si sur une surface moins de 97 % des coups passent le filet, moins de 95 %
tombent dans le court, ou si la prise de balle médiane sort de 0,8–1,6 m de haut, on remet algo/index.html du paquet 274.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / 'simulateur' / 'rapport_3d_echanges.json'
JS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf-8');
const a = src.indexOf('const G3D = (() => {'), b = src.indexOf('// Vue du direct choisie par le visiteur');
global.court = n => n; global.esc = x => String(x);
let graine = 275; Math.random = () => { graine = (graine * 16807) % 2147483647; return graine / 2147483647; };
eval(src.slice(a, b).replace('const G3D =', 'global.G3D ='));
const P = G3D._phys, HL = 23.77 / 2, W = 10.97, rnd = (x, y) => x + (y - x) * Math.random(), out = {};
for (const surf of ['Hard', 'Clay', 'Grass']) {
  P.surface(surf);
  let n = 0, passe = 0, dedans = 0; const hy = [], hz = [], marge = [];
  for (let k = 0; k < 150; k++) {
    const sens = k % 2 ? 1 : -1, a0 = { x: rnd(-3.5, 3.5), y: rnd(0.9, 1.3), z: -sens * (HL + rnd(0.6, 1.8)) };
    const st = P.styleCoup(0, 'echange'), c = P.coupPhysique(a0, { x: rnd(-3.8, 3.8), y: 0, z: sens * rnd(HL - 5.5, HL - 2.2) }, st.V, st.s, 'rebond', { hc: rnd(0.85, 1.15) });
    n++;
    let hf = null; for (const q of c.vols[0].pts) if (q[3] * sens >= 0) { hf = q[2]; break; }
    if (hf !== null && hf >= P.hauteurFilet(0) + 0.03) { passe++; marge.push(hf - P.hauteurFilet(0)); }
    const i = c.vols[0].b; if (Math.abs(i.x) <= W / 2 && sens * i.z > 0 && sens * i.z <= HL) dedans++;
    if (c.vols[1]) { hy.push(c.ex.y); hz.push(Math.abs(c.ex.z) - HL); }
  }
  const med = x => { const s = x.slice().sort((p, q) => p - q); return s.length ? +s[s.length >> 1].toFixed(2) : null; };
  out[surf] = { coups: n, passent_le_filet_pct: +(100 * passe / n).toFixed(1), dans_le_court_pct: +(100 * dedans / n).toFixed(1),
    marge_filet_mediane_m: med(marge), prise_hauteur_mediane_m: med(hy), prise_derriere_la_ligne_mediane_m: med(hz) };
}
console.log(JSON.stringify(out));
"""


def mesurer():
    if not shutil.which('node'):
        raise SystemExit('node absent')
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / 'c.js'; f.write_text(JS, encoding='utf-8')
        r = subprocess.run(['node', str(f), str(RACINE / 'algo' / 'index.html')], capture_output=True, text=True, timeout=120, check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])


def retrait(m):
    """Vrai si la règle de retrait se déclenche sur au moins une surface."""
    return any(v['passent_le_filet_pct'] < 97 or v['dans_le_court_pct'] < 95
               or not (0.8 <= (v['prise_hauteur_mediane_m'] or 0) <= 1.6) for v in m.values())


def main():
    m = mesurer()
    rapport = {'paquet': 275, 'quoi': "Réalisme des échanges du direct en 3D : trajectoires (pesanteur, air, effet), rebond selon la surface, prise de balle.",
               'note': "Échanges illustratifs : ils ne changent pas le %.", 'par_surface': m, 'retrait_declenche': retrait(m),
               'regle_retrait': "Moins de 97 % des coups au-dessus du filet, moins de 95 % dans le court, ou prise de balle médiane hors 0,8–1,6 m : retour au paquet 274."}
    SORTIE.write_text(json.dumps(rapport, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rapport, ensure_ascii=False, indent=1))
    return 1 if rapport['retrait_declenche'] else 0


if __name__ == '__main__':
    sys.exit(main())
