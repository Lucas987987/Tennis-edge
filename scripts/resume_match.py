#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resume_match.py — LE VRAI DÉROULÉ D'UN MATCH TERMINÉ, POUR LE RÉSUMÉ 3D (20/11/2026, paquet 308, demande de Lucas :
résumés de match en 3D pour X, match choisi à la main, 30–45 s, 4 à 6 points clés).

Lit, sans aucune requête :
  feuilles/AAAA-MM-JJ.jsonl.gz         la feuille TennisApi du match (joueurs, score par set, statut « Ended ») ;
  feuilles_points/AAAA-MM-JJ.jsonl.gz  son point par point (chaque jeu : set, n°, serveur, « HAHH… »).
et écrit algo/resume_match.json : la suite RÉELLE des points (0 = le joueur cité en premier sur le site, 1 = l'autre),
le premier serveur, le score réel par set et le vainqueur. La page (?video=1&resume=1) rejoue ces points dans le
stade 3D avec le vrai score à l'écran ; seuls les échanges (trajectoires, coups) sont reconstitués.

Refus (pas de vidéo) : ITF, match non terminé (abandon, forfait), feuille ou point par point introuvable, ou point par
point incomplet (le score qu'il donne diffère du score de la feuille).
Usage : python scripts/resume_match.py UID [racine]
"""
import datetime as dt
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import resultats_feuilles as RF  # noqa: E402


def _lire_gz(chemin):
    out = []
    try:
        with gzip.open(chemin, 'rt', encoding='utf-8') as f:
            for ligne in f:
                try:
                    out.append(json.loads(ligne))
                except ValueError:
                    continue
    except (OSError, EOFError):
        pass
    return out


def feuille_du_match(racine, m):
    """(feuille, sens) : sens +1 si la feuille a les joueurs dans l'ordre du site, −1 sinon."""
    t = RF.instant(m.get('debut_utc') or m.get('debut'))
    if t is None:
        return None, 0
    j = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
    for k in (0, -1, 1):
        for fe in _lire_gz(os.path.join(racine, 'feuilles', f'{(j + dt.timedelta(days=k)).isoformat()}.jsonl.gz')):
            if abs(float(fe.get('debut') or 0) - t) > RF.ECART_H * 3600:
                continue
            fh, fa = (fe.get('home') or {}).get('nom'), (fe.get('away') or {}).get('nom')
            if fh and fa:
                s = RF._sens_champs(fh, fa, m.get('home') or '', m.get('away') or '')
                if s:
                    return fe, s
    return None, 0


def points_du_match(racine, fe):
    jour = fe.get('jour') or ''
    for k in (0, 1, -1):
        try:
            d = (dt.date.fromisoformat(jour) + dt.timedelta(days=k)).isoformat()
        except ValueError:
            return None
        for p in _lire_gz(os.path.join(racine, 'feuilles_points', f'{d}.jsonl.gz')):
            if str(p.get('id')) == str(fe.get('id')):
                return p
    return None


def _jeu_complet(pts, decisif):
    """Vrai si le jeu se termine exactement sur son dernier point (jeu décisif : en 7 ou en 10 points)."""
    for cible in ((7, 10) if decisif else (4,)):
        h = a = 0
        for i, c in enumerate(pts):
            h, a = h + (c == 'H'), a + (c == 'A')
            if max(h, a) >= cible and abs(h - a) >= 2:
                if i == len(pts) - 1:
                    return True
                break
    return False


def stats_reelles(fe, s):
    """Les vraies statistiques du match (feuille TennisApi, match entier), dans l'ordre des joueurs du site :
    aces, doubles fautes, % de 1res balles, balles de break converties [réussies, occasions], points gagnés.
    None si la feuille n'en a pas. (Paquet 312 : affichées à la fin du résumé ; descriptif, le % ne change pas.)"""
    st = (fe.get('stats') or {}).get('ALL') or {}
    if not st:
        return None
    v = lambda k, i: (st.get(k) or [None] * 4)[i]
    out = {}
    for cle, k in (('aces', 'aces'), ('df', 'doubleFaults'), ('pts', 'pointsTotal')):
        x = [v(k, 0), v(k, 2)]
        if None not in x:
            out[cle] = [int(x[0]), int(x[1])]
    p = [v('firstServeAccuracy', 0), v('firstServeAccuracy', 1), v('firstServeAccuracy', 2), v('firstServeAccuracy', 3)]
    if None not in p and p[1] and p[3]:
        out['prem'] = [round(100 * p[0] / p[1]), round(100 * p[2] / p[3])]
    # balles de break : réussies par le joueur, occasions = balles de break de l'adversaire (sauvées + perdues)
    r0, r1, o1, o0 = v('breakPointsScored', 0), v('breakPointsScored', 2), v('breakPointsSaved', 3), v('breakPointsSaved', 1)
    if None not in (r0, r1, o0, o1):
        out['bb'] = [[int(r0), int(o1)], [int(r1), int(o0)]]
    if not out:
        return None
    if s < 0:
        out = {k: [x[1], x[0]] for k, x in out.items()}
    return out


def construire(racine, uid):
    """{trace, premier, sets, vainqueur, …} dans l'ordre des joueurs du site ; lève ValueError en cas de refus."""
    with open(os.path.join(racine, 'algo', 'donnees.json'), encoding='utf-8') as f:
        D = json.load(f)
    m = next((x for x in D.get('matchs', []) if x.get('uid') == uid), None)
    if not m:
        raise ValueError('match absent du site (algo/donnees.json)')
    if 'ITF' in str(m.get('circuit') or '').upper():
        raise ValueError('ITF : jamais de vidéo')
    fe, s = feuille_du_match(racine, m)
    if not fe:
        raise ValueError('feuille du match introuvable')
    if RF.gagnants(fe) is None:
        raise ValueError(f"match non terminé normalement ({(fe.get('statut') or {}).get('texte')})")
    pp = points_du_match(racine, fe)
    if not pp or not pp.get('jeux'):
        raise ValueError('point par point introuvable')
    jeux = sorted(pp['jeux'], key=lambda g: (int(g[0]), int(g[1])))
    vers = {'H': '0', 'A': '1'} if s > 0 else {'H': '1', 'A': '0'}
    serveur = int(jeux[0][2])                                   # 1 = joueur à domicile sur la feuille
    premier = (0 if serveur == 1 else 1) if s > 0 else (1 if serveur == 1 else 0)
    # contrôle : chaque jeu doit être complet et s'arrêter sur son dernier point (4 points et 2 d'écart ; jeu décisif à
    # 6-6 : 7 ou 10 points et 2 d'écart), et les jeux gagnés par set redonner le score de la feuille
    par_set = {}
    for g in jeux:
        pts = [c for c in str(g[3]) if c in 'HA']
        if not pts:
            raise ValueError('point par point incomplet (jeu vide)')
        e = par_set.setdefault(int(g[0]), [0, 0])
        if e == [6, 6] and not _jeu_complet(pts, True) and len(pts) > 1 and pts[-1] == pts[-2] and _jeu_complet(pts[:-1], True):
            # format TennisApi : 9 jeux décisifs sur 10 se terminent par un point en double (vu sur 3 718 jeux décisifs
            # de juin à novembre 2026) ; on l'enlève, et la suite des points (trace) aussi
            pts = pts[:-1]
            g[3] = ''.join(pts)
        if not _jeu_complet(pts, e == [6, 6]):
            raise ValueError(f'point par point incomplet (set {g[0]}, jeu {g[1]} : {"".join(pts)})')
        e[0 if pts[-1] == 'H' else 1] += 1
    trace = ''.join(vers[c] for g in jeux for c in str(g[3]) if c in vers)
    sh, sa = (fe.get('score_home') or {}).get('sets') or [], (fe.get('score_away') or {}).get('sets') or []
    feuille_sets = [[int(a), int(b)] for a, b in zip(sh, sa) if a is not None and b is not None]
    pbp_sets = [par_set[k] for k in sorted(par_set)]
    if pbp_sets != feuille_sets:
        raise ValueError(f'point par point incomplet ({pbp_sets} contre {feuille_sets} sur la feuille)')
    sets = [[x[0], x[1]] if s > 0 else [x[1], x[0]] for x in feuille_sets]
    v = int(fe.get('vainqueur'))
    vainqueur = (0 if v == 1 else 1) if s > 0 else (1 if v == 1 else 0)
    return {'uid': uid, 'trace': trace, 'premier': premier, 'sets': sets, 'vainqueur': vainqueur,
            'score': ' '.join(f'{a}-{b}' if vainqueur == 0 else f'{b}-{a}' for a, b in sets),
            'points': len(trace), 'stats': stats_reelles(fe, s), 'source': 'feuille et point par point TennisApi'}


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    uid, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    try:
        r = construire(racine, uid)
    except ValueError as e:
        print(f'Résumé impossible : {e}')
        return 1
    with open(os.path.join(racine, 'algo', 'resume_match.json'), 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False)
    print(f"Résumé : {r['uid']} · {r['score']} · {r['points']} points réels")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
