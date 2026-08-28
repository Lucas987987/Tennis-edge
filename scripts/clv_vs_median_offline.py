#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clv_vs_median_offline.py — Répond au §E : la sélection du meilleur book
explique-t-elle le CLV mesuré, ou le marché bouge-t-il vraiment ? (v1 audit
v4 §Y, réécrit v2 audit v5 §AB, réécrit v3 audit v6 §AF/§AG/§AE.)

CE QUE LA VERSION D'HIER (§AF) COMPARAIT MAL : clv_book (entrée vs clôture
du book CHOISI, le max) contre clv_median (entrée vs clôture MÉDIANE).
L'entrée est un maximum sur ~20 books ; la médiane à la clôture est donc
mécaniquement inférieure à la clôture du meilleur book, indépendamment de
tout mouvement de marché -- l'écart mesuré mélangeait deux effets sans les
séparer.

LA DÉCOMPOSITION QUI RÉPOND VRAIMENT AU §E (audit v6 §AG) :
  PRIME DE SÉLECTION = entry / médiane À L'ENTRÉE (même instant, isole le
                        choix du meilleur book)
  DÉRIVE DU MARCHÉ    = médiane À L'ENTRÉE / médiane À LA CLÔTURE (isole
                        le mouvement du marché, book identique des 2 côtés)
  TOTAL = PRIME x DÉRIVE (approximativement, en %) = ce que clv_book mesure

L'instant d'entrée est reconstruit via `commence_time - lead_min` (les deux
sont dans moves_detail_hist.csv / la partition source).

Écrit clv_vs_median_report.json (audit v6 §AE : un rapport en stdout non
committé, c'est la situation exacte de Q3 avant son correctif -- resté non
lu deux mois et demi).

Usage : python scripts/clv_vs_median_offline.py
"""
import csv
import datetime
import glob
import gzip
import json
import math
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_key as mk
import curves_common as cc

SEUIL_PERTINENCE_PTS = 1.0   # audit v6 §AF.2 : un écart <1pt n'est pas actionnable
                             # même si l'IC l'exclut de zéro -- il faut les DEUX.


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8', errors='replace') \
        if p.endswith('.gz') else open(p, encoding='utf-8', errors='replace')


def _dt(s):
    """Copie locale volontaire, voir curves_common.py."""
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', '')).timestamp()
    except (ValueError, TypeError):
        return None


def _cote_par_noms(steame, home, away):
    """Identifie le côté PAR LES NOMS -- CORRIGÉ LE 28/08/2026 (audit v6
    §AH) : la version d'hier renvoyait 'h' dès que th matchait, SANS
    vérifier que ta ne matchait pas AUSSI -- exactement l'ambiguïté
    (Zverev/Zverev, Wu/Wu) que l'étape 4 de match_key.py avait pour raison
    d'être retirée en passe 3. Risque plus faible ici (comparaison intra-
    match, pas inter-matchs) mais le principe est le même partout dans ce
    dépôt : tester LES DEUX côtés, ne renvoyer que si un seul correspond."""
    ts = mk._toks(steame)
    th, ta = mk._toks(home), mk._toks(away)
    ih = bool(ts and th and (ts <= th or th <= ts))
    ia = bool(ts and ta and (ts <= ta or ta <= ts))
    if ih and not ia:
        return 'h'
    if ia and not ih:
        return 'a'
    return None   # ambigu (ou aucun match) -> on refuse, comme partout ailleurs


def _point_a_ou_avant(points, ts_limite):
    """Dernier point de `points` (liste de (epoch, prix)) daté <= ts_limite."""
    meilleur = None
    for t, prix in points:
        if t <= ts_limite and (meilleur is None or t > meilleur[0]):
            meilleur = (t, prix)
    return meilleur[1] if meilleur else None


def charge_moves():
    moves = []
    for r in csv.DictReader(open('moves_detail_hist.csv', encoding='utf-8')):
        try:
            entry = float(r['entry'])
            lead_min = float(r['lead_min'])
            clv_book_pct = float(r['clv_book_pct'])
        except (ValueError, KeyError, TypeError):
            continue
        nat = mk.natural_key(r.get('steame', ''), r.get('opp', ''), r.get('date'))
        if not nat[0]:
            continue
        moves.append({'nat': nat, 'entry': entry, 'lead_min': lead_min,
                      'clv_book_pct': clv_book_pct,
                      'steame': r.get('steame', ''), 'opp': r.get('opp', '')})
    return moves


def charge_courbes(besoins, closing_lines, cl_idx):
    """Ne charge QUE les matchs présents dans `besoins` (les clés naturelles
    des moves) -- pas toute la base, pour rester léger en mémoire tout en
    gardant les courbes complètes (pas juste le dernier point, il faut
    pouvoir chercher le prix À L'INSTANT DE L'ENTRÉE, pas seulement à la
    clôture)."""
    out = {}
    fichiers = sorted(glob.glob('parts/hist_book_*.jsonl') +
                      glob.glob('parts/hist_book_*.jsonl.gz'))
    print(f'  {len(fichiers)} partitions à charger (filtrées aux {len(besoins)} '
         f'matchs nécessaires)...')
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
                nat = mk.natural_key(r.get('home', ''), r.get('away', ''),
                                     r.get('commence_time'))
                # AUDIT v7 §AM.2 : seul join du dépôt SANS
                # cc.cherche_avec_tolerance() -- c'est volontaire, pas un
                # oubli. moves_detail_hist.csv et les partitions hist_book_*
                # tirent leur date de la MÊME source (le pipeline qui écrit
                # les deux), elles ne peuvent pas diverger comme
                # closing_lines.json (convention d'uid indépendante)
                # divergeait des courbes. Vérifié : 949/949 moves joints,
                # 0 perdu. Ne pas "corriger" en ajoutant la tolérance ici
                # sans revérifier -- ce serait un affaiblissement inutile
                # d'une clé qui n'a jamais eu besoin d'être assouplie.
                if nat not in besoins:
                    continue
                ct = _dt(r.get('commence_time'))
                if ct is None:
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
                h_pts = [(_dt(p[0]), float(p[1])) for p in h_pre
                        if _dt(p[0]) is not None]
                a_pts = [(_dt(p[0]), float(p[1])) for p in a_pre
                        if _dt(p[0]) is not None]
                if not h_pts or not a_pts:
                    continue
                m = out.setdefault(nat, {'_home': r.get('home', ''),
                                         '_away': r.get('away', ''), '_ct': ct})
                m[r.get('book')] = {'h': h_pts, 'a': a_pts}
    if n_croises_tentes:
        print(f'  commence_time croisé sur {n_croises_resolus}/{n_croises_tentes} '
             f'lignes ({100*n_croises_resolus/n_croises_tentes:.0f}%)')
    return out


def _ic_bootstrap(valeurs, n_boot=3000, graine=2026828):
    n = len(valeurs)
    if n < 8:
        return st.median(valeurs) if valeurs else 0.0, None, None
    rng = random.Random(graine)
    tirages = []
    for _ in range(n_boot):
        sel = [valeurs[rng.randrange(n)] for _ in range(n)]
        tirages.append(st.median(sel))
    tirages.sort()
    return st.median(valeurs), tirages[int(0.025 * n_boot)], tirages[int(0.975 * n_boot) - 1]


def _verdict(label, med, lo, hi):
    """CORRIGÉ (audit v6 §AF.2) : IC qui exclut 0 ET taille d'effet >= seuil
    de pertinence -- l'un sans l'autre ne suffit pas. À n=661 sur une
    quantité quasi déterministe, un écart de 0,05 pt sortait déjà de l'IC
    hier ; ça ne le rendait pas actionnable."""
    if lo is None:
        return f'{label} : médiane {med:+.2f}% (n trop petit pour un IC)'
    pertinent = abs(med) >= SEUIL_PERTINENCE_PTS
    exclut_zero = lo > 0 or hi < 0
    if pertinent and exclut_zero:
        tag = '✅ effet réel et pertinent'
    elif exclut_zero:
        tag = f'⚠️ IC exclut 0 mais |médiane|<{SEUIL_PERTINENCE_PTS}pt -- pas actionnable'
    else:
        tag = '— IC traverse 0, non démontré'
    return f'{label} : médiane {med:+.2f}% [IC95 {lo:+.2f}, {hi:+.2f}] -> {tag}'


def main():
    print('PONT CLV -> P&L : décomposition prime de sélection / dérive du marché (§E, §AG)')
    closing_lines, cl_idx = cc.build_closing_index()
    moves = charge_moves()
    besoins = {mv['nat'] for mv in moves}
    print(f'  {len(moves)} moves | {len(besoins)} matchs distincts à charger')
    courbes = charge_courbes(besoins, closing_lines, cl_idx)
    print(f'  {len(courbes)} matchs trouvés dans les partitions')

    lignes = []
    n_cote_inconnu, n_incomplet = 0, 0
    for mv in moves:
        m = courbes.get(mv['nat'])
        if not m:
            n_incomplet += 1
            continue
        side = _cote_par_noms(mv['steame'], m.get('_home', ''), m.get('_away', ''))
        if side is None:
            n_cote_inconnu += 1
            continue
        ct = m['_ct']
        instant_entree = ct - mv['lead_min'] * 60

        prix_entree, prix_cloture = [], []
        for bkname, bkval in m.items():
            if bkname.startswith('_') or bkname == 'pinnacle':
                continue
            pts = bkval.get(side)
            if not pts:
                continue
            pe = _point_a_ou_avant(pts, instant_entree)
            # CORRIGÉ LE 28/08/2026 (audit v7 §AM.1) : pts[-1][1] suppose la
            # courbe triée, _point_a_ou_avant() scanne sans le supposer --
            # même fonction que pour l'entrée, une seule convention.
            # Vérifié à part : 0 courbe désordonnée sur 8474 aujourd'hui,
            # mais si l'ordre casse un jour, seule une moitié du calcul
            # aurait suivi sans cette uniformisation.
            pc = _point_a_ou_avant(pts, ct)
            if pe and pe > 1:
                prix_entree.append(pe)
            if pc and pc > 1:
                prix_cloture.append(pc)
        if len(prix_entree) < 3 or len(prix_cloture) < 3:
            n_incomplet += 1
            continue

        med_entree = st.median(prix_entree)
        med_cloture = st.median(prix_cloture)
        if med_entree <= 1 or med_cloture <= 1:
            continue

        prime = (mv['entry'] / med_entree - 1) * 100
        derive = (med_entree / med_cloture - 1) * 100
        # AJOUTÉ (audit v7 §AK.1) : le TOTAL calculé directement par move
        # (entry/med_cloture), pas reconstruit via (1+prime)*(1+derive)-1
        # appliqué aux MÉDIANES agrégées -- médiane(a)*médiane(b) !=
        # médiane(a*b). Écart mesuré par l'audit : 0,35 pt, au-dessus du
        # seuil de pertinence déclaré (1 pt). Ici chaque LIGNE a son propre
        # total, cohérent par construction avec sa propre prime et dérive ;
        # la médiane du total se prend sur ces lignes, pas sur les médianes.
        total = (mv['entry'] / med_cloture - 1) * 100
        lignes.append({'prime': prime, 'derive': derive, 'total': total,
                       'clv_book_pct': mv['clv_book_pct'], 'lead_min': mv['lead_min'],
                       'n_entree': len(prix_entree), 'n_cloture': len(prix_cloture)})

    n = len(lignes)
    print(f'\n  {n_cote_inconnu} côté(s) ambigu(s)/inconnu(s) (audit v6 §AH) | '
         f'{n_incomplet} match(s) incomplet(s) (<3 books à l\'entrée ET/ou à la clôture)')
    print(f'  {n} moves exploitables (>= 3 books à l\'entrée ET à la clôture)')

    rapport = {
        'genere_le': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'n_moves_total': len(moves), 'n_cote_ambigu': n_cote_inconnu,
        'n_incomplet': n_incomplet, 'n_exploitables': n,
    }

    if n < 30:
        print('\n  trop tôt pour conclure (<30 exploitables).')
        rapport['verdict'] = 'trop_tot'
        json.dump(rapport, open('clv_vs_median_report.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return

    primes = [x['prime'] for x in lignes]
    derives = [x['derive'] for x in lignes]
    totaux = [x['total'] for x in lignes]
    clv_books = [x['clv_book_pct'] for x in lignes]

    mp, lop, hip = _ic_bootstrap(primes)
    md, lod, hid = _ic_bootstrap(derives)
    # CORRIGÉ LE 28/08/2026 (audit v7 §AK.1) : médiane des totaux PAR MOVE,
    # pas composition des deux médianes agrégées séparément -- voir le
    # commentaire à la construction de `total` plus haut.
    mt, lot, hit = _ic_bootstrap(totaux)

    ligne_prime = _verdict('PRIME DE SELECTION (entry / mediane a entree)', mp, lop, hip)
    ligne_derive = _verdict('DERIVE DU MARCHE (mediane entree / mediane cloture)', md, lod, hid)
    print(f'\n  {ligne_prime}')
    print(f'  {ligne_derive}')
    # CORRIGÉ (audit v7 §AK.2) : cette quantité EST clv_vs_median (entry vs
    # book médian), pas clv_book (entry vs book D'ENTRÉE, le meilleur des
    # ~20) -- les deux ont un nom différent parce que ce ne sont pas la
    # même chose. L'étiquette d'hier ("ce que clv_book mesure") était fausse.
    print(f'\n  TOTAL = clv_vs_median (entry / mediane cloture, mediane des '
         f'totaux par move) : {mt:+.2f}% [IC95 {lot:+.2f}, {hit:+.2f}]')
    med_clv_book = st.median(clv_books)
    print(f'  clv_book_pct (entry / cloture du book D\'ENTRÉE, pour comparaison) : '
         f'{med_clv_book:+.2f}%')
    # CORRIGÉ LE 28/08/2026 (audit v8 §AN) : cette ligne répétait EXACTEMENT
    # l'erreur que le §AK.1 venait de corriger trois lignes plus haut --
    # médiane(a) - médiane(b) au lieu de médiane(a - b). La question posée
    # ("que coûte de rester au book d'entrée ?") est une quantité PAR PARI,
    # donc appariée par construction -- une différence de deux médianes
    # agrégées séparément ne répond pas à cette question. Mesuré : l'écart
    # affiché était 7x trop grand (différence de médianes -0,36pt contre
    # médiane des différences -0,05pt, IC [-0,32, -0,01]).
    ecarts_pairs = [cb - x['total'] for cb, x in zip(clv_books, lignes)]
    ecart_book_median, lo_e, hi_e = _ic_bootstrap(ecarts_pairs)
    ligne_ecart = _verdict('écart clv_book - clv_vs_median (par pari, apparié)',
                           ecart_book_median, lo_e, hi_e)
    print(f'  {ligne_ecart}')
    print(f'  (ce que coûte, ou rapporte, de rester au book d\'entrée plutôt '
         f'que d\'être au médian jusqu\'à la clôture)')
    # CORRIGÉ (audit v7 §AK.3) : dénominateur = le total RÉEL affiché
    # (mt), pas mp+md qui n'est ni le total multiplicatif d'hier ni celui-ci.
    part_prime = 100 * mp / mt if abs(mt) > 1e-9 else None
    if part_prime is not None:
        print(f'  part de la prime de sélection dans le total : ~{part_prime:.0f}%')

    print(f'  %positif prime : {100*sum(1 for x in primes if x>0)/n:.0f}% | '
         f'%positif dérive : {100*sum(1 for x in derives if x>0)/n:.0f}%')

    # AJOUTÉ (audit v7 §AL) : ventilation par délai détection -> départ.
    # L'audit a testé et RÉFUTÉ l'hypothèse que les moves exclus (< 3 books)
    # auraient une prime plus forte -- la prime est stable ±0,2pt sur toutes
    # les tranches. En revanche la DÉRIVE varie d'un facteur 3 : un signal
    # détecté à moins de 6h du départ n'apporte presque que la prime, pas
    # la dérive -- actionnable sur MIN_LEAD (actuellement 15 min).
    tranches = [(0, 360, '<6h'), (360, 720, '6-12h'),
               (720, 1440, '12-24h'), (1440, float('inf'), '>24h')]
    print('\n  Ventilation par délai détection -> départ (audit v7 §AL) :')
    for lo, hi, label in tranches:
        sel = [x for x in lignes if lo <= x['lead_min'] < hi]
        if len(sel) < 10:
            print(f'    {label:8} n={len(sel):3} -- trop peu pour une médiane fiable')
            continue
        p_sel = st.median(x['prime'] for x in sel)
        d_sel = st.median(x['derive'] for x in sel)
        print(f'    {label:8} n={len(sel):3} | PRIME {p_sel:+.2f}% | DÉRIVE {d_sel:+.2f}%')

    print('\n  Rappel : ceci mesure la VALIDITÉ du CLV, pas le profit -- le '
         'journal forward reste la seule mesure directe du ROI.')

    rapport.update({
        'verdict': 'calcule',
        'prime_selection_pct': round(mp, 3), 'prime_ic95': [round(lop, 3), round(hip, 3)],
        'derive_marche_pct': round(md, 3), 'derive_ic95': [round(lod, 3), round(hid, 3)],
        'total_clv_vs_median_pct': round(mt, 3), 'total_ic95': [round(lot, 3), round(hit, 3)],
        'clv_book_pct_median': round(med_clv_book, 3),
        'ecart_book_vs_median_pct': round(ecart_book_median, 3),
        'ecart_book_vs_median_ic95': [round(lo_e, 3), round(hi_e, 3)],
        'part_prime_pct': round(part_prime, 1) if part_prime is not None else None,
        'pct_positif_prime': round(100*sum(1 for x in primes if x>0)/n, 1),
        'pct_positif_derive': round(100*sum(1 for x in derives if x>0)/n, 1),
    })
    json.dump(rapport, open('clv_vs_median_report.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n  -> clv_vs_median_report.json écrit (audit v6 §AE : plus de '
         'rapport perdu en stdout).')


if __name__ == '__main__':
    main()
