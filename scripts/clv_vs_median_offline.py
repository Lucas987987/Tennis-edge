#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clv_vs_median_offline.py — Répond au §E MAINTENANT, sur les moves
historiques au lieu d'attendre des semaines le journal forward (audit v4
§Y, RÉÉCRIT LE 28/08/2026 après l'audit v5 §AB qui a trouvé deux défauts
graves dans la version d'hier).

Le §E posait la question : pick_signal() choisit le book au prix le PLUS
HAUT parmi ~20 -- le CLV mesuré est-il gonflé par cette sélection, ou
reflète-t-il un vrai edge de marché ? clv_vs_median (ajouté dans
paper_journal.py) répond à ça, mais n'existe que sur les paris du journal
forward -- il faudra n>=30 nouveaux paris pour dire quoi que ce soit.
moves_detail_hist.csv a la même info sur ~900 lignes.

CE QUI ÉTAIT CASSÉ HIER (audit v5 §AB), et pourquoi la réécriture :
1. Le côté (home/away) était DEVINÉ en comparant le dernier point BRUT du
   book d'entrée au clv_book_pct déjà calculé (lui-même sur courbe
   TRONQUÉE au pré-match) -- un move n'était gardé QUE si le marché n'avait
   pas bougé après le coup d'envoi. Conséquence : 44/923 appariés (4,8%),
   un échantillon sélectionné par un critère CORRÉLÉ au phénomène étudié
   (la liquidité/couverture in-play), pas un échantillon aléatoire.
   Corrigé : côté identifié par les NOMS (mk._toks, comme partout ailleurs
   dans le dépôt), indépendant de ce qui s'est passé après le coup d'envoi.
2. La médiane des AUTRES books utilisait leur dernier point BRUT (in-play
   compris), pendant que le numérateur (entry) est pré-match -- comparaison
   non homogène. Corrigé : troncature pré-match sur TOUTES les courbes,
   via curves_common (même pont commence_time croisé que les 4 autres
   fichiers du dépôt).

Usage : python scripts/clv_vs_median_offline.py
"""
import csv
import glob
import gzip
import json
import math
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_key as mk
import curves_common as cc


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') \
        if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def _dt(s):
    """Conversion ISO -> epoch float. Copie locale volontaire (comme
    steam_alert/move_audit/canal_clv en ont chacune une) -- curves_common
    ne réimplémente pas le parsing de date, voir sa docstring."""
    if not s:
        return None
    try:
        from datetime import datetime
        s2 = str(s).replace('Z', '').replace('+00:00', '')
        return datetime.fromisoformat(s2).timestamp()
    except (ValueError, TypeError):
        return None


def charge_courbes_par_cle(closing_lines, cl_idx):
    """{clé_naturelle: {'_home':, '_away':, book: dernier_prix_PRÉ-MATCH}}

    Un seul point par book (pas la courbe entière -- mémoire), mais ce
    point est maintenant le dernier AVANT commence_time (croisé via
    curves_common, comme steam_alert/move_audit/canal_clv), pas le dernier
    point brut. C'est le correctif §AB.2 : numérateur et dénominateur
    doivent obéir à la même règle de troncature."""
    out = {}
    fichiers = sorted(glob.glob('parts/hist_book_*.jsonl') +
                      glob.glob('parts/hist_book_*.jsonl.gz'))
    print(f'  {len(fichiers)} partitions à charger...')
    n_croises_tentes, n_croises_resolus = 0, 0
    for f in fichiers:
        with _ouvrir(f) as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except json.JSONDecodeError:
                    continue
                hc, ac = r.get('home_curve'), r.get('away_curve')
                if not hc or not ac:
                    continue
                ct = _dt(r.get('commence_time'))
                if ct is None:
                    continue
                nat = mk.natural_key(r.get('home', ''), r.get('away', ''),
                                     r.get('commence_time'))
                if not nat[0]:
                    continue
                n_croises_tentes += 1
                cl_uid = cc.cherche_avec_tolerance(cl_idx, nat)
                ct_croise = _dt((closing_lines.get(cl_uid) or {}).get('commence_time')) \
                    if cl_uid else None
                if ct_croise:
                    n_croises_resolus += 1
                    if ct_croise < ct:
                        ct = ct_croise
                h_pre = cc.tronque_prematch(hc, ct, _dt)
                a_pre = cc.tronque_prematch(ac, ct, _dt)
                if not h_pre or not a_pre:
                    continue
                try:
                    ph, pa = float(h_pre[-1][1]), float(a_pre[-1][1])
                except (TypeError, ValueError, IndexError):
                    continue
                m = out.setdefault(nat, {'_home': r.get('home', ''),
                                         '_away': r.get('away', '')})
                m[r.get('book')] = {'h': ph, 'a': pa}
    if n_croises_tentes:
        print(f'  commence_time croisé sur {n_croises_resolus}/{n_croises_tentes} '
             f'lignes ({100*n_croises_resolus/n_croises_tentes:.0f}%)')
    return out


def _cote_par_noms(steame, home, away):
    """Identifie le côté (home/away) PAR LES NOMS -- audit v5 §AB.1. La
    version d'hier devinait le côté via un test numérique corrélé au
    phénomène étudié (voir docstring du module). Même comparaison tolérante
    que match_key.py (inclusion d'ensembles) pour couvrir les prénoms
    abrégés d'un côté du CSV et pas de l'autre."""
    ts = mk._toks(steame)
    th, ta = mk._toks(home), mk._toks(away)
    if ts and th and (ts <= th or th <= ts):
        return 'h'
    if ts and ta and (ts <= ta or ta <= ts):
        return 'a'
    return None


def main():
    print('PONT CLV -> P&L : clv_vs_median calculé hors ligne (§Y, réécrit §AB)')
    closing_lines, cl_idx = cc.build_closing_index()
    print('  chargement des courbes multi-books par clé naturelle...')
    courbes = charge_courbes_par_cle(closing_lines, cl_idx)
    print(f'  {len(courbes)} matchs indexés')

    lignes = []
    n_lignes, n_apparies, n_cote_inconnu, n_moins_de_3_books = 0, 0, 0, 0
    for r in csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8')):
        n_lignes += 1
        try:
            entry = float(r['entry'])
            clv_book_pct = float(r['clv_book_pct'])
        except (ValueError, KeyError):
            continue
        nat = mk.natural_key(r.get('steame', ''), r.get('opp', ''), r.get('date'))
        m = courbes.get(nat)
        if not m:
            continue
        side = _cote_par_noms(r.get('steame', ''), m.get('_home', ''), m.get('_away', ''))
        if side is None:
            n_cote_inconnu += 1
            continue
        clotures = []
        for bkname, bkval in m.items():
            if bkname.startswith('_') or bkname == 'pinnacle':
                continue
            prix = bkval.get(side)
            if prix and prix > 1:
                clotures.append(prix)
        if len(clotures) < 3:
            n_moins_de_3_books += 1
            continue
        med = st.median(clotures)
        if med <= 1:
            continue
        n_apparies += 1
        clv_median = (entry / med - 1) * 100
        lignes.append({'clv_book': clv_book_pct, 'clv_median': clv_median,
                       'n_books': len(clotures)})

    print(f'\n  {n_lignes} moves | côté résolu par les noms : '
         f'{n_lignes - n_cote_inconnu}/{n_lignes}')
    print(f'  côté non résolu (noms) : {n_cote_inconnu} | <3 books : {n_moins_de_3_books} '
         f'| appariés au final : {n_apparies}')
    if n_apparies < 30:
        print('\n  trop tôt pour conclure (<30 appariés).')
        return

    cb = [x['clv_book'] for x in lignes]
    cm = [x['clv_median'] for x in lignes]
    n = len(lignes)
    ecarts = [b - m_ for b, m_ in zip(cb, cm)]
    ecart_median = st.median(ecarts)
    # IC bootstrap sur l'écart (même discipline que validation_report.py --
    # une approximation normale sur un échantillon possiblement asymétrique
    # a déjà produit un faux résultat une fois aujourd'hui, ailleurs dans
    # ce dépôt -- pas la peine de répéter l'erreur ici).
    import random
    rng = random.Random(2026828)
    tirages = []
    for _ in range(3000):
        sel = [ecarts[rng.randrange(n)] for _ in range(n)]
        tirages.append(st.median(sel))
    tirages.sort()
    ic_lo, ic_hi = tirages[int(0.025 * 3000)], tirages[int(0.975 * 3000) - 1]

    print(f'\n  clv_book  (vs clôture du book d\'entrée) : médiane {st.median(cb):+.2f}% '
         f'| %positif {100*sum(1 for x in cb if x>0)/n:.0f}%')
    print(f'  clv_median(vs book MÉDIAN pré-match, n>=3): médiane {st.median(cm):+.2f}% '
         f'| %positif {100*sum(1 for x in cm if x>0)/n:.0f}%')
    print(f'\n  écart médian (clv_book - clv_median) : {ecart_median:+.2f} pts '
         f'[IC95 bootstrap {ic_lo:+.2f}, {ic_hi:+.2f}] (n={n})')
    # CORRIGÉ (audit v5 §AB.4) : plus d'affirmation catégorique "pas de
    # signature" -- l'IC dit ce qu'il dit, on le rapporte sans conclure à
    # sa place.
    if ic_lo > 0:
        print('  IC95 exclut 0, entièrement positif -- clv_book semble '
             'systématiquement gonflé par la sélection du book max.')
    elif ic_hi < 0:
        print('  IC95 exclut 0, entièrement négatif (inattendu, à creuser).')
    else:
        print('  IC95 traverse 0 -- pas encore démontré à ce n, ni dans un '
             'sens ni dans l\'autre.')

    par_n = {}
    for x in lignes:
        par_n.setdefault(min(x['n_books'], 10), []).append(x['clv_median'])
    print('\n  Répartition par nombre de books dans la médiane :')
    for nb in sorted(par_n):
        v = par_n[nb]
        print(f'    n_books={nb}{"+" if nb==10 else ""} : {len(v)} moves | '
             f'clv_median médian {st.median(v):+.1f}%')


if __name__ == '__main__':
    main()
