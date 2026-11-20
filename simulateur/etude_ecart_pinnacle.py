#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_ecart_pinnacle.py — LOUPE : où la clôture Pinnacle prévoit-elle le vainqueur bien mieux que notre Elo ?
(04/11/2026, demande de Lucas). Étude DESCRIPTIVE : la cote n'entre jamais dans l'algo ; elle sert seulement à
repérer les situations où il nous manque une information (à chercher ensuite dans les données publiques).

Population : matchs ATP et WTA de l'archive appariés aux clôtures Pinnacle (tennis-data, sans marge), depuis 2022.
(Le Challenger n'a pas de clôtures dans tennis-data : absent.)
Notre probabilité : l'Elo du pronostic (elo.py, notes d'avant le jour du match), ~78 % du mélange affiché et à
0,0002 près de sa log loss sur 2025 →.
Pour chaque situation (calculée avant le match) et chaque circuit : log loss du vainqueur, Elo contre Pinnacle ;
écart = Elo − Pinnacle. Une situation « à creuser » a un écart d'au moins 1,5 fois l'écart moyen du circuit sur au
moins 300 matchs, et le sens du biais dit qui l'Elo surestime.
Usage : python simulateur/etude_ecart_pinnacle.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_changement_surface as ECS  # noqa: E402

DEPUIS = dt.date(2022, 1, 1)
MIN_N, FACTEUR = 300, 1.5
SORTIE = os.path.join(ICI, 'rapport_ecart_pinnacle.json')


def ll(p):
    return -math.log(min(max(p, 1e-9), 1 - 1e-9))


def situations(sa, sb, pa):
    """sa, sb : états des deux joueurs (A = vainqueur) ; pa : P_elo(A). → {situation: joueur concerné (+1 A, −1 B, 0 les deux)}."""
    out = {}
    fav = 1 if pa >= 0.5 else -1
    pf = max(pa, 1 - pa)
    out['favori 50–60 %' if pf < .6 else 'favori 60–75 %' if pf < .75 else 'favori 75 % et plus'] = fav
    for cle, f in (('moins de 30 matchs', lambda s: s['n'] < 30), ('30 à 100 matchs', lambda s: 30 <= s['n'] < 100),
                   ('vient surtout de l’ITF ou du Challenger', lambda s: s['bas'] >= 0.5),
                   ('retour après 45 jours ou plus', lambda s: s['absence'] is not None and s['absence'] >= 45),
                   ('abandon dans les 30 derniers jours', lambda s: s['abandon'] is not None and s['abandon'] <= 30),
                   ('1er ou 2e match après un changement de surface', lambda s: s['nouveau']),
                   ('3 matchs ou plus dans le tournoi (dont qualifications)', lambda s: s['tournoi'] >= 3),
                   ('note en forte hausse (+100 sur 3 mois)', lambda s: s['hausse'] >= 100),
                   ('note en forte baisse (−100 sur 3 mois)', lambda s: s['hausse'] <= -100)):
        a, b = bool(f(sa)), bool(f(sb))
        if a or b:
            out[cle] = 0 if a and b else (1 if a else -1)
    return out


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import feuilles as FE
    M = DN.charger(archive, 2012)
    fin = max(m['date'] for m in M)
    M = M + [m for m in FE.charger(racine) if m['date'] > fin]
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    td = DN.charger_td(os.path.join(racine, 'historique', 'tennis_data.csv.gz'), DEPUIS.isoformat())
    import backtest_pronostic as BP
    pin = {id(m): BP.juste(t['psw'], t['psl']) for t, m in DN.joindre(td, M)}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, su = E.Elo(), ECS.Suivi()
    dern, niv, ab, hist, tour_n = {}, collections.defaultdict(lambda: collections.deque(maxlen=20)), {}, {}, {}
    jour, attente, rows = None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
                for j in (g, p):
                    hist.setdefault(j, collections.deque(maxlen=200)).append((d, el.note(j)))
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        tid = m.get('tournoi_id') or m.get('tournoi')
        if id(m) in pin and d >= DEPUIS and c in ('ATP', 'WTA') and not m.get('abandon'):
            def etat(j):
                h = hist.get(j) or ()
                ref = next((n for dd, n in h if (d - dd).days <= 100), None)
                return {'n': el.matchs(j), 'bas': (sum(niv[j]) / len(niv[j])) if niv[j] else 0.0,
                        'absence': (d - dern[j]).days if j in dern else None,
                        'abandon': (d - ab[j]).days if j in ab else None, 'nouveau': su.nouveau(j, d, s),
                        'tournoi': tour_n.get((j, tid), 0), 'hausse': (el.note(j) - ref) if ref is not None else 0.0}
            pa = el.proba(g, p, s)
            rows.append({'c': c, 'pe': pa, 'pp': pin[id(m)], 's': situations(etat(g), etat(p), pa)})
        for j in (g, p):
            dern[j] = d
            niv[j].append(1.0 if c in ('CH', 'ITF') else 0.0)
            tour_n[(j, tid)] = tour_n.get((j, tid), 0) + 1
            su.jouer(j, d, s)
        if m.get('abandon'):
            ab[p] = d
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def bilan(R):
    n = len(R)
    le, lp = sum(ll(r['pe']) for r in R) / n, sum(ll(r['pp']) for r in R) / n
    return n, round(le, 5), round(lp, 5), round(le - lp, 5)


def analyser(rows):
    out = {}
    for c in ('ATP', 'WTA'):
        R = [r for r in rows if r['c'] == c]
        if not R:
            continue
        n, le, lp, ec = bilan(R)
        bloc = {'matchs': n, 'log_loss_elo': le, 'log_loss_pinnacle': lp, 'ecart': ec, 'situations': {}}
        noms = sorted({s for r in R for s in r['s']})
        for s_ in noms:
            sub = [r for r in R if s_ in r['s']]
            n2, le2, lp2, ec2 = bilan(sub)
            # biais : de combien (points de %) l'Elo donne PLUS que Pinnacle au joueur concerné (seul concerné)
            seuls = [r for r in sub if r['s'][s_] != 0]
            biais = (100 * sum((r['pe'] - r['pp']) * r['s'][s_] for r in seuls) / len(seuls)) if seuls else None
            reel = (100 * sum(1 if r['s'][s_] > 0 else 0 for r in seuls) / len(seuls)) if seuls else None
            ann_e = (100 * sum(r['pe'] if r['s'][s_] > 0 else 1 - r['pe'] for r in seuls) / len(seuls)) if seuls else None
            ann_p = (100 * sum(r['pp'] if r['s'][s_] > 0 else 1 - r['pp'] for r in seuls) / len(seuls)) if seuls else None
            bloc['situations'][s_] = {
                'matchs': n2, 'log_loss_elo': le2, 'log_loss_pinnacle': lp2, 'ecart': ec2,
                'ecart_relatif': round(ec2 / ec, 2) if ec else None,
                'a_creuser': n2 >= MIN_N and ec and ec2 >= FACTEUR * ec,
                'joueur_concerne': ({'matchs': len(seuls), 'elo_pct': round(ann_e, 1), 'pinnacle_pct': round(ann_p, 1),
                                     'reel_pct': round(reel, 1), 'elo_moins_pinnacle_pts': round(biais, 2)} if seuls else None)}
        out[c] = bloc
    return out


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'nature': 'descriptive : la cote ne sert qu’à mesurer après coup, jamais d’entrée de l’algo',
           'population': f'ATP et WTA depuis {DEPUIS.isoformat()}, matchs appariés aux clôtures Pinnacle (sans marge)',
           'circuits': analyser(rows)}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for c, b in doc['circuits'].items():
        print(f"\n{c} : {b['matchs']} matchs, Elo {b['log_loss_elo']} / Pinnacle {b['log_loss_pinnacle']} (écart {b['ecart']})")
        for s_, v in sorted(b['situations'].items(), key=lambda kv: -(kv[1]['ecart'] or 0)):
            jc = v['joueur_concerne'] or {}
            print(f"  {'★' if v['a_creuser'] else ' '} {s_:<55} n {v['matchs']:>5} écart {v['ecart']:+.4f} "
                  f"(×{v['ecart_relatif']}) | concerné : Elo {jc.get('elo_pct')} Pin {jc.get('pinnacle_pct')} réel {jc.get('reel_pct')} (n {jc.get('matchs')})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
