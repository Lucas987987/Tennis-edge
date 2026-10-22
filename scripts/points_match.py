#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
points_match.py — le déroulé POINT PAR POINT des matchs collectés (TennisApi) — 22/10/2026.

Pour chaque match des feuilles (feuilles/AAAA-MM-JJ.jsonl.gz) qui a ses statistiques, une requête :
    /api/tennis/event/{id}/point-by-point
et on garde, en compact, chaque jeu : set, n° du jeu, serveur (1 = home, 2 = away), et la suite des
points (« H » point gagné par home, « A » par away). Sert à mesurer comment chaque joueur gère la
pression (30-30, égalité, servir pour le set, rebond après un break…) — facteurs.py, groupe « pression ».
Sortie : feuilles_points/AAAA-MM-JJ.jsonl.gz (une ligne par match : {id, jeux: [[set, jeu, serveur, "HAHH…"]]}).

Mêmes garde-fous que feuilles_match.py (budget, réserve de quota). Le format de la réponse n'est pas
documenté : --sonde affiche la réponse brute d'un match récent, à vérifier une fois.
Usage : python scripts/points_match.py [budget] [--sonde] [--depuis AAAA-MM-JJ]
"""
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

DOSSIER = os.path.join(FM.DOSSIER, '..', 'feuilles_points')
VALEURS = {'0': 0, '15': 1, '30': 2, '40': 3, 'A': 4, 'AD': 4}


def _v(x):
    """Valeur d'un score de point (« 15 », « A », ou un nombre en tie-break)."""
    s = str(x if x is not None else '').strip().upper()
    if s in VALEURS:
        return VALEURS[s]
    try:
        return int(s)
    except ValueError:
        return None


def suite_des_points(points, gagnant_du_jeu=None):
    """« HAHH… » depuis la liste des scores successifs {homePoint, awayPoint} (après chaque point)."""
    out = []
    ph = pa = 0
    for pt in points or []:
        h, a = _v(pt.get('homePoint')), _v(pt.get('awayPoint'))
        if h is None or a is None:
            return None
        if h > ph or (a < pa and h >= ph):           # home marque (ou efface l'avantage adverse)
            out.append('H')
        elif a > pa or (h < ph and a >= pa):
            out.append('A')
        else:
            return None
        ph, pa = h, a
    if gagnant_du_jeu in (1, 2) and out:
        out.append('H' if gagnant_du_jeu == 1 else 'A')   # le point qui conclut le jeu n'a souvent pas de score
    return ''.join(out)


def compacter(doc):
    """[[set, jeu, serveur, points]] depuis la réponse point-by-point ; None si le format n'est pas reconnu."""
    sets = (doc or {}).get('pointByPoint')
    if not isinstance(sets, list):
        return None
    jeux = []
    for s in sets:
        for g in s.get('games') or []:
            sc = g.get('score') or {}
            pts = g.get('points') or []
            seq = suite_des_points(pts, sc.get('scoring'))
            if seq is None or sc.get('serving') not in (1, 2):
                continue
            jeux.append([s.get('set'), g.get('game'), sc['serving'], seq])
    jeux.sort(key=lambda j: (j[0] or 0, j[1] or 0))
    return jeux or None


def lire(chemin):
    out = {}
    try:
        with gzip.open(chemin, 'rt', encoding='utf-8') as f:
            for l in f:
                r = json.loads(l)
                out[r['id']] = r
    except (OSError, ValueError, EOFError):
        pass
    return out


def ecrire(chemin, recs):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with gzip.open(chemin + '.tmp', 'wt', encoding='utf-8') as f:
        for r in recs.values():
            f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    os.replace(chemin + '.tmp', chemin)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    budget = int(args[0]) if args else 3000
    sonde = '--sonde' in argv
    depuis = next((argv[i + 1] for i, a in enumerate(argv) if a == '--depuis' and i + 1 < len(argv)), '0000')
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    if not cle:
        print('RAPIDAPI_KEY absent : rien à faire.')
        return 0
    c = FM.Client(cle, budget=budget)
    jours = sorted(p for p in glob.glob(os.path.join(FM.DOSSIER, '*.jsonl.gz')) if os.path.basename(p)[:10] >= depuis)
    if sonde:
        for p in reversed(jours):
            for r in FM.lire_jour(os.path.basename(p)[:10]).values():
                if r.get('stats'):
                    code, doc = c.get(f"/api/tennis/event/{r['id']}/point-by-point")
                    print(f"HTTP {code} · {r['home']['nom']} – {r['away']['nom']} ({r['jour']})")
                    print(json.dumps(doc, ensure_ascii=False)[:3000])
                    print('Compacté :', json.dumps(compacter(doc), ensure_ascii=False)[:600])
                    return 0
        return 0
    n_ok = n_rien = 0
    try:
        for p in reversed(jours):                       # les plus récents d'abord
            jour = os.path.basename(p)[:10]
            sortie = os.path.join(DOSSIER, jour + '.jsonl.gz')
            deja = lire(sortie)
            a_faire = [r for r in FM.lire_jour(jour).values() if r.get('stats') and r['id'] not in deja]
            try:
                for r in a_faire:
                    code, doc = c.get(f"/api/tennis/event/{r['id']}/point-by-point")
                    jeux = compacter(doc) if code == 200 else None
                    deja[r['id']] = {'id': r['id'], 'jeux': jeux}
                    n_ok += bool(jeux)
                    n_rien += not jeux
            finally:
                if a_faire:
                    ecrire(sortie, deja)
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e}")
    print(f"Point par point : {n_ok} matchs gardés, {n_rien} sans déroulé exploitable · {c.n} requêtes · quota restant {c.restant}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
