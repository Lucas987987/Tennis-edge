#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_feuilles.py — les statistiques TennisApi des feuilles sont-elles justes ? (05/11/2026, demande de Lucas, après
la découverte que « firstToServe » donne le serveur du DERNIER jeu.) Chaque champ que l'on peut recompter est
comparé au déroulé POINT PAR POINT du même match (feuilles_points : serveur et gagnant de chaque point) :
  points joués au service, points gagnés dans le match, jeux de service joués, breaks concédés, balles de break
  concédées, jeux par set (contre le score). Aces et doubles fautes ne sont pas dans le point par point : non audités.
Un champ est déclaré FAUX si plus de 5 % des matchs comparables diffèrent (tolérance : 0 pour les comptes de jeux,
±2 pour les comptes de points, qui peuvent perdre un point dans les flux). Rapport : simulateur/rapport_audit_feuilles.json.
Résultat du 05/11/2026 (8 842 matchs, 17 362 joueurs-matchs) :
  — points joués au service et points gagnés : justes (3,6–3,7 % d'écarts, des déroulés incomplets) ;
  — jeux par set : justes (1,8 %) ;
  — « serviceGamesTotal » : FAUX par joueur dans 47 % des cas, toujours de ±1 et en miroir (21/20 au lieu de 20/21) :
    le total des deux est juste, la répartition suit le faux « premier serveur » de TennisApi. Effet : % de jeux de
    service gagnés d'un joueur bruité de quelques points (sans biais) ;
  — balles de break et breaks : SOUS-COMPTÉS dans 8,5 % des matchs (−3,6 % de breaks au total), même quand tous les
    points concordent : nos breaks « réels » sont un peu trop bas.
Usage : python simulateur/audit_feuilles.py . <dossier(s) feuilles_points>
"""
import collections
import datetime as dt
import glob
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
SORTIE = os.path.join(ICI, 'rapport_audit_feuilles.json')
SEUIL_FAUX = 5.0


def depuis_points(jeux):
    """Recomptes depuis [[set, jeu, serveur (1/2), 'HAH…']] : par joueur (0 = home, 1 = away)."""
    svpt, gagnes, sg, perdus, bpf = [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]
    par_set = collections.defaultdict(lambda: [0, 0])
    for s, j, srv, pts in sorted(jeux, key=lambda g: (g[0], g[1])):
        if not pts:
            continue
        i = 0 if srv == 1 else 1
        tb = len(pts) >= 7 and par_set[s][0] == 6 and par_set[s][1] == 6
        a = b = 0                                    # points du serveur, du relanceur dans ce jeu
        for k, x in enumerate(pts):
            gagnant = 0 if x == 'H' else 1
            gagnes[gagnant] += 1
            if tb:
                # au jeu décisif, le service change au 1er point puis tous les deux points
                serv = i if (k == 0 or ((k - 1) // 2) % 2 == 1) else 1 - i
                svpt[serv] += 1
                continue
            svpt[i] += 1
            if b >= 3 and b > a:                       # balle de break (relanceur à 40 ou avantage)
                bpf[i] += 1
            if gagnant == i:
                a += 1
            else:
                b += 1
        g = 0 if pts[-1] == 'H' else 1
        par_set[s][g] += 1
        if not tb:
            sg[i] += 1
            if g != i:
                perdus[i] += 1
    return {'svpt': svpt, 'points_gagnes': gagnes, 'sg': sg, 'breaks_concedes': perdus, 'bpf': bpf,
            'sets': [tuple(par_set[k]) for k in sorted(par_set)]}


def depuis_feuille(e):
    import feuilles as FE
    st = (e.get('stats') or {}).get('ALL') or {}
    d = [FE.detail(st, 0), FE.detail(st, 2)]
    if not d[0] or not d[1]:
        return None
    sv = [x[0] for x in d]
    pg = [d[0][2] + d[0][3] + (sv[1] - d[1][2] - d[1][3]), d[1][2] + d[1][3] + (sv[0] - d[0][2] - d[0][3])]
    sets = list(zip(e['score_home'].get('sets') or [], e['score_away'].get('sets') or []))
    return {'svpt': sv, 'points_gagnes': pg, 'sg': [x[8] for x in d], 'breaks_concedes': [x[6] - x[7] for x in d],
            'bpf': [x[6] for x in d], 'sets': [tuple(x) for x in sets if None not in x]}


def auditer(racine, dossiers):
    pb = {}
    for dsr in dossiers:
        for f in glob.glob(os.path.join(dsr, '*.jsonl.gz')):
            for l in gzip.open(f, 'rt', encoding='utf-8'):
                x = json.loads(l)
                if x.get('jeux'):
                    pb[x['id']] = x['jeux']
    tol = {'svpt': 2, 'points_gagnes': 2, 'sg': 0, 'breaks_concedes': 0, 'bpf': 0}
    cpt = collections.defaultdict(lambda: [0, 0, []])       # champ → [comparés, différents, exemples]
    n = 0
    for f in sorted(glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz'))):
        for l in gzip.open(f, 'rt', encoding='utf-8'):
            e = json.loads(l)
            if e.get('id') not in pb or str((e.get('statut') or {}).get('texte') or '').lower() != 'ended':
                continue
            a, b = depuis_feuille(e), None
            if not a:
                continue
            b = depuis_points(pb[e['id']])
            if b['sets'] != a['sets']:                          # déroulé incomplet ou décalé : comparé à part
                cpt['sets'][0] += 1
                cpt['sets'][1] += 1
                if len(cpt['sets'][2]) < 3:
                    cpt['sets'][2].append({'id': e['id'], 'feuille': a['sets'], 'points': b['sets']})
                continue
            cpt['sets'][0] += 1
            n += 1
            for k, t in tol.items():
                for i in (0, 1):
                    c = cpt[k]
                    c[0] += 1
                    if abs(a[k][i] - b[k][i]) > t:
                        c[1] += 1
                        if len(c[2]) < 3:
                            c[2].append({'id': e['id'], 'joueur': i, 'feuille': a[k][i], 'points': b[k][i]})
    out = {k: {'compares': v[0], 'differents': v[1], 'differents_pct': round(100 * v[1] / v[0], 2) if v[0] else None,
               'faux': bool(v[0] and 100 * v[1] / v[0] > SEUIL_FAUX), 'exemples': v[2]} for k, v in cpt.items()}
    return n, out


def main(argv):
    racine, dossiers = argv[1], argv[2:]
    n, champs = auditer(racine, dossiers)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'matchs_complets': n,
           'regle': "faux si plus de 5 % des matchs diffèrent (jeux : tolérance 0 ; points : ±2)", 'champs': champs}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: {x: v[x] for x in ('compares', 'differents_pct', 'faux')} for k, v in champs.items()},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
