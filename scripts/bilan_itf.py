#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bilan_itf.py — COUVERTURE DU POINT PAR POINT ITF POUR NOS JOUEURS DE CHALLENGER (22/11/2026, paquet 360, Lucas :
« Données Challenger / ITF »).

Question préalable à toute étude : pour les joueurs des Challengers récents, combien de matchs ITF avec déroulé point
par point (historique/itf_points/, scripts/itf_points.py) a-t-on AVANT chacun de leurs matchs, et combien de points de
service cela ajoute-t-il ? Si la couverture reste faible, l'étude « profils de service enrichis par l'ITF » ne vaut
pas d'être lancée ; si elle est bonne, sa règle sera écrite avant de regarder les résultats.

Population : les matchs Challenger en simple des JOURS derniers jours dans feuilles/ (identifiants TennisApi des deux
joueurs). Pour chaque joueur de chaque match : matchs ITF avec déroulé joués AVANT le jour du match (24 mois au plus)
et points de service qu'ils apportent (jeux décisifs exclus, comme dans itf_points.py).
Sortie : des comptes seulement (le journal d'Actions est public) ; aucun nom, aucune cote. Ne modifie rien.
Usage : python scripts/bilan_itf.py [jours=30]
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

FEUILLES = os.environ.get('FEUILLES_DOSSIER_SOURCE', 'feuilles')
ITF = os.environ.get('ITF_POINTS_DOSSIER', os.path.join('historique', 'itf_points'))
TRANCHES = ((0, 0, 'aucun'), (1, 4, '1 à 4'), (5, 14, '5 à 14'), (15, 10 ** 9, '15 et plus'))


def _lignes(motif):
    for p in sorted(glob.glob(motif)):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    if l.strip():
                        try:
                            yield json.loads(l)
                        except ValueError:
                            continue
        except (OSError, EOFError):
            continue


def matchs_challenger(depuis, dossier=FEUILLES):
    """[(jour, id_home, id_away)] — Challengers en simple depuis la date donnée."""
    out = []
    for r in _lignes(os.path.join(dossier, '2*.jsonl.gz')):
        if 'challenger' not in str(r.get('categorie') or '').lower() or not r.get('jour') or r['jour'] < depuis:
            continue
        h, a = (r.get('home') or {}).get('id'), (r.get('away') or {}).get('id')
        if h and a:
            out.append((r['jour'], h, a))
    return out


def itf_par_joueur(dossier=ITF):
    """{id: [(jour, points de service joués)]} — matchs ITF avec déroulé, triés par jour."""
    out = {}
    for r in _lignes(os.path.join(dossier, '2*.jsonl.gz')):
        sv = r.get('service') or {}
        if not r.get('jeux') or not r.get('jour'):
            continue
        for c in ('home', 'away'):
            i = (r.get(c) or {}).get('id')
            v = sv.get(c)
            if i and isinstance(v, list) and len(v) == 2:
                out.setdefault(i, []).append((r['jour'], int(v[1] or 0)))
    for v in out.values():
        v.sort()
    return out


def couverture(matchs, itf):
    """Par (match, joueur) : (matchs ITF avant le jour, points de service ITF avant le jour), 24 mois au plus."""
    import bisect
    res = []
    for jour, h, a in matchs:
        d0 = (dt.date.fromisoformat(jour) - dt.timedelta(days=730)).isoformat()
        for i in (h, a):
            L = itf.get(i) or []
            jours = [x[0] for x in L]
            lo, hi = bisect.bisect_left(jours, d0), bisect.bisect_left(jours, jour)
            res.append((hi - lo, sum(p for _, p in L[lo:hi])))
    return res


def resumer(res):
    n = len(res)
    out = {'joueurs_matchs': n, 'tranches': []}
    for a, b, lib in TRANCHES:
        k = sum(1 for m, _ in res if a <= m <= b)
        out['tranches'].append({'tranche': lib, 'n': k, 'pct': round(100 * k / n, 1) if n else None})
    pts = sorted(p for _, p in res)
    out['points_service_median'] = pts[len(pts) // 2] if pts else None
    out['avec_500_points_ou_plus_pct'] = round(100 * sum(1 for p in pts if p >= 500) / n, 1) if n else None
    return out


def main(argv):
    jours = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 30
    depuis = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=jours)).isoformat()
    M = matchs_challenger(depuis)
    itf = itf_par_joueur()
    doc = resumer(couverture(M, itf))
    print(f"Couverture ITF point par point — Challengers des {jours} derniers jours : {len(M)} matchs, "
          f"{doc['joueurs_matchs']} joueurs-matchs ; {len(itf)} joueurs ont au moins un match ITF avec déroulé")
    for t in doc['tranches']:
        print(f"  matchs ITF avec déroulé avant le match : {t['tranche']:>10} → {t['n']} ({t['pct']} %)")
    print(f"  points de service ITF avant le match : médiane {doc['points_service_median']} · "
          f"500 ou plus pour {doc['avec_500_points_ou_plus_pct']} % des joueurs-matchs")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
