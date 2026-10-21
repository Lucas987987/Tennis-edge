#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marches_sets.py — le moteur contre les marchés « vainqueur du set 1 » (21/10/2026).

Pour chaque match :
  1. probabilité juste de victoire chez Pinnacle (clôture, marge retirée,
     méthode puissance du Lab) ;
  2. le moteur la TRADUIT en probabilité de gagner le set 1 (forme du jour,
     σ réglé sur juin–août 2026, vérifié sur septembre–octobre) ;
  3. comparaison avec la cote set 1 de PINNACLE (le juge) et des books mous
     à la clôture ; résultat réel du set 1 (set_results.json).

Mesures :
  * précision : log loss sur le set 1 réel — moteur, Pinnacle set 1, books ;
  * accord moteur / Pinnacle set 1 (écart moyen, en points de probabilité) ;
  * « valeur » : cote d'un book mou × probabilité > 1 + seuil, avec comme
    probabilité (a) le moteur, (b) Pinnacle set 1 sans marge — ROI sur le set
    réel (IC95 rééchantillonné par jour) et CLV contre la clôture set 1 Pinnacle.
Aucun pari n'est conseillé ici : c'est un test.

Données : parts/hist_set1_* et parts/hist_book_* (Pinnacle match), et R2 si
R2_HIST_MATERIALIZE=1 (oddspapi_v5.iter_hist_lines), set_results.json.
Usage : python simulateur/marches_sets.py [racine]  -> simulateur/rapport_marches_sets.json
"""
import collections
import datetime as dt
import glob
import importlib.util
import json
import math
import os
import random
import re
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import modele as M  # noqa: E402

_sp = importlib.util.spec_from_file_location('tennis_edge_ms_books', os.path.join(RACINE, 'Tennis_Edge_Lab', 'books.py'))
books = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(books)

SIGMA = 0.15                 # forme du jour (réglage juin–août 2026, validé sept.–oct.)
SERVICE_MOYEN = {'ATP': 0.646, 'CH': 0.625, 'WTA': 0.559, 'ITF': 0.546}   # sigmoïde(mu dur), notes Sackmann
SEUILS = (0.0, 0.03, 0.05, 0.10)


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def circuit(t):
    t = str(t or '').lower()
    if 'wta' in t or 'women' in t:
        return 'WTA'
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'CH'
    return 'ATP'


def cinq_sets(t):
    t = str(t or '')
    return bool(re.search(r'(wimbledon|us open|french open|roland|australian open)', t, re.I)) and \
        bool(re.search(r'\bmen', t, re.I)) and not re.search(r'women', t, re.I)


def juste(c1, c2):
    """Probabilité juste du côté 1 (puissance), repli proportionnel."""
    if not c1 or not c2 or c1 <= 1 or c2 <= 1:
        return None
    k = books.power_exponent(c1, c2)
    return (1 / c1) ** k if k else (1 / c1) / (1 / c1 + 1 / c2)


def lire_jsonl(chemins):
    for f in chemins:
        op = __import__('gzip').open if f.endswith('.gz') else open
        try:
            with op(f, 'rt', encoding='utf-8') as fh:
                for l in fh:
                    try:
                        yield json.loads(l)
                    except ValueError:
                        continue
        except OSError:
            continue


def lignes(marche):
    """Lignes hist_<marche> (une par match et par book, avec ouverture/clôture)."""
    try:
        sys.path.insert(0, os.path.join(RACINE, 'scripts'))
        import oddspapi_v5 as ov
        cwd = os.getcwd()
        os.chdir(RACINE)
        try:
            for l in ov.iter_hist_lines(marche):
                try:
                    yield json.loads(l) if isinstance(l, str) else l
                except ValueError:
                    continue
        finally:
            os.chdir(cwd)
    except Exception as e:  # repli : fichiers locaux
        print(f"  lecture directe des partitions ({type(e).__name__}: {e})")
        yield from lire_jsonl(sorted(glob.glob(os.path.join(RACINE, 'parts', f'hist_{marche}_*'))))


def pinnacle_match():
    """Cote Pinnacle du MATCH 30 min avant le début (hist_book, mêmes identifiants
    que les marchés de sets) : {uid: ((cote home, cote away), home)}."""
    out = {}
    for r in lignes('book'):
        if books.normalize(r.get('book')) != 'pinnacle':
            continue
        debut = _t(r.get('commence_time'))
        if debut is None or not r.get('uid'):
            continue
        q = paire_a(r, debut - dt.timedelta(minutes=DECISION_MIN))
        if q:
            out[r['uid']] = (q, r.get('home'))
    return out


def resultat_set1(sr, uid, home, away, jour):
    """'home' / 'away' du point de vue (home, away) de la ligne, ou None."""
    if uid in sr and sr[uid].get('set1') in ('home', 'away'):
        return sr[uid]['set1']
    d0 = dt.date.fromisoformat(jour)
    for d in (d0, d0 - dt.timedelta(days=1), d0 + dt.timedelta(days=1)):
        k1, k2 = f"{d}_{norm(home)}_{norm(away)}", f"{d}_{norm(away)}_{norm(home)}"
        if sr.get(k1, {}).get('set1') in ('home', 'away'):
            return sr[k1]['set1']
        if sr.get(k2, {}).get('set1') in ('home', 'away'):
            return 'away' if sr[k2]['set1'] == 'home' else 'home'
    return None


DECISION_MIN = 30            # décision 30 min avant le début annoncé
AGE_MAX_MIN = 180            # cote vieille d'au plus 3 h à la décision


def _t(x):
    try:
        return dt.datetime.fromisoformat(str(x).replace('Z', '').split('+')[0])
    except ValueError:
        return None


def cote_a(r, cote, t, age_max=AGE_MAX_MIN):
    """Dernière cote du côté `cote` ('home_curve'/'away_curve') à l'instant t, si assez fraîche."""
    best = None
    for p in r.get(cote) or []:
        tp = _t(p[0])
        if tp is None or tp > t:
            continue
        if best is None or tp >= best[0]:
            best = (tp, p[1])
    if best is None or (t - best[0]).total_seconds() / 60 > age_max:
        return None
    try:
        v = float(best[1])
    except (TypeError, ValueError):
        return None
    return v if v > 1 else None


def paire_a(r, t, age_max=AGE_MAX_MIN):
    h, a = cote_a(r, 'home_curve', t, age_max), cote_a(r, 'away_curve', t, age_max)
    return (h, a) if h and a else None


def bootstrap(items, B=2000):
    """IC95 (en %) de la moyenne, rééchantillonnage par jour."""
    g = collections.defaultdict(list)
    for j, v in items:
        g[j].append(v)
    ks = list(g)
    if len(ks) < 5:
        return None
    rnd = random.Random(11)
    res = []
    for _ in range(B):
        xs = [x for k in rnd.choices(ks, k=len(ks)) for x in g[k]]
        res.append(sum(xs) / len(xs))
    res.sort()
    return [round(100 * res[int(0.025 * B)], 2), round(100 * res[int(0.975 * B)], 2)]


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def main():
    pin = pinnacle_match()
    sr = json.load(open(os.path.join(RACINE, 'set_results.json'), encoding='utf-8'))
    # Chaque ligne est réduite DÈS LA LECTURE à ses cotes utiles (décision et
    # dernière cote d'avant-match) : l'historique complet ne tient pas en mémoire.
    par_match = collections.defaultdict(dict)
    for r in lignes('set1'):
        try:
            b = books.normalize(r['book'])
            debut = _t(r.get('commence_time'))
            if debut is None:
                continue
            T = debut - dt.timedelta(minutes=DECISION_MIN)
            nv = {'home': r.get('home'), 'away': r.get('away'), 'tournament': r.get('tournament'),
                  'commence_time': r.get('commence_time'), 'T': paire_a(r, T),
                  'clot': paire_a(r, debut, age_max=24 * 60) if b == 'pinnacle' else None}
            anc = par_match[r['uid']].get(b)
            if anc:                                   # même match dans deux partitions : on garde le non-vide
                for k in ('T', 'clot'):
                    nv[k] = nv[k] or anc[k]
            par_match[r['uid']][b] = nv
        except (KeyError, TypeError):
            continue
    cache, L = {}, []
    for uid, bk in par_match.items():
        p_ = bk.get('pinnacle')
        if uid not in pin or not p_:
            continue
        pr = pin[uid]
        r0 = p_
        if cinq_sets(r0.get('tournament')) or norm(pr[1]) != norm(r0.get('home')):
            continue                                   # 5 sets, ou orientation différente : écarté
        debut = _t(r0.get('commence_time'))
        if debut is None:
            continue
        T = debut - dt.timedelta(minutes=DECISION_MIN)
        jour = str(r0.get('commence_time'))[:10]
        res = resultat_set1(sr, uid, r0.get('home'), r0.get('away'), jour)
        m_ = pr[0]
        s1 = p_['T']
        s1_clot = p_['clot']                               # dernière cote set 1 Pinnacle d'avant-match
        if not m_ or not s1 or not s1_clot:
            continue
        ph, p_pin_s1, p_pin_s1_clot = juste(*m_), juste(*s1), juste(*s1_clot)
        if ph is None or p_pin_s1 is None or p_pin_s1_clot is None:
            continue
        c = circuit(r0.get('tournament'))
        k = (round(round(ph / 0.002) * 0.002, 3), c)   # pas de 0,2 point : calcul partagé
        if k not in cache:
            cache[k] = M.prix_depuis_pinnacle(k[0], SERVICE_MOYEN[c], 2, SIGMA)['set1']
        p_mod = cache[k]
        softs = {}
        for b, r in bk.items():
            f = books.flags(b)
            if b == 'pinnacle' or not f['jouable']:
                continue
            if r['T']:
                softs[b] = r['T']
        L.append({'uid': uid, 'jour': jour, 'circuit': c, 'res': res, 'p_match': ph, 'p_mod': p_mod,
                  'p_pin_s1': p_pin_s1, 'p_pin_s1_clot': p_pin_s1_clot, 'softs': softs})
    print(f"matchs avec Pinnacle match + set 1 frais {DECISION_MIN} min avant : {len(L)} (résultat connu : {sum(1 for x in L if x['res'])})")
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'sigma': SIGMA,
           'decision': f"{DECISION_MIN} min avant le début, cotes de moins de {AGE_MAX_MIN} min ; CLV contre la dernière cote set 1 Pinnacle d'avant-match",
           'matchs': len(L), 'periode': [min((x['jour'] for x in L), default=None), max((x['jour'] for x in L), default=None)]}
    # accord moteur / Pinnacle set 1
    d = [x['p_mod'] - x['p_pin_s1'] for x in L]
    rap['accord_moteur_pinnacle_set1'] = {'ecart_moyen_pts': round(100 * sum(d) / len(d), 2) if d else None,
                                          'ecart_absolu_moyen_pts': round(100 * sum(abs(v) for v in d) / len(d), 2) if d else None}
    R = [x for x in L if x['res']]
    if R:
        y = lambda x: int(x['res'] == 'home')
        rap['precision_set1'] = {
            'matchs': len(R),
            'moteur': round(sum(ll(x['p_mod'], y(x)) for x in R) / len(R), 5),
            'pinnacle_set1': round(sum(ll(x['p_pin_s1'], y(x)) for x in R) / len(R), 5),
            'victoire_match_comme_set1': round(sum(ll(x['p_match'], y(x)) for x in R) / len(R), 5)}
    # valeur chez les books mous, deux juges
    for juge, cle in (('moteur', 'p_mod'), ('pinnacle_set1', 'p_pin_s1')):
        bloc = []
        for s in SEUILS:
            items, clv = [], []
            for x in L:
                for b, (oh, oa) in x['softs'].items():
                    for side, cote, p in (('home', oh, x[cle]), ('away', oa, 1 - x[cle])):
                        net = books.effective_odds(b, cote)
                        if net * p - 1 > s:
                            pj = x['p_pin_s1_clot'] if side == 'home' else 1 - x['p_pin_s1_clot']
                            clv.append(net * pj - 1)
                            if x['res']:
                                items.append((x['jour'], (net - 1) if x['res'] == side else -1.0))
            if clv:
                bloc.append({'seuil': f"> {int(100 * s)} %", 'paris': len(clv),
                             'clv_pinnacle_set1_pct': round(100 * sum(clv) / len(clv), 2),
                             'regles': len(items),
                             'roi_pct': round(100 * sum(v for _, v in items) / len(items), 2) if items else None,
                             'ic95_roi_pct': bootstrap(items) if items else None})
        rap[f'valeur_books_juge_{juge}'] = bloc
    # où le moteur et Pinnacle set 1 divergent le plus
    rap['ecart_par_niveau'] = []
    for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)):
        g = [x for x in L if lo <= max(x['p_match'], 1 - x['p_match']) < hi]
        if g:
            fav = lambda x, v: v if x['p_match'] >= 0.5 else 1 - v
            rap['ecart_par_niveau'].append({
                'favori_match': f"{int(lo * 100)}–{int(hi * 100)} %", 'n': len(g),
                'set1_moteur': round(100 * sum(fav(x, x['p_mod']) for x in g) / len(g), 1),
                'set1_pinnacle': round(100 * sum(fav(x, x['p_pin_s1']) for x in g) / len(g), 1),
                'set1_reel': (round(100 * sum(fav(x, int(x['res'] == 'home')) for x in g if x['res']) /
                              max(1, sum(1 for x in g if x['res'])), 1) if any(x['res'] for x in g) else None),
                'n_reel': sum(1 for x in g if x['res'])})
    with open(os.path.join(ICI, 'rapport_marches_sets.json'), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rap.items() if k != 'genere_le'}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
