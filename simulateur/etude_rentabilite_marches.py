#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_rentabilite_marches.py — notre algorithme peut-il être rentable sur Kalshi et Polymarket ? (23/10/2026)

QUESTION : en jouant, sur les marchés de prédiction, le côté que NOTRE algorithme (mélange simulation + Elo,
sans aucune cote) juge sous-coté, gagne-t-on de la valeur ?

PRONOSTICS UTILISÉS — tous faits AVANT le match, sur des matchs jamais vus :
  — historique : les pronostics hors échantillon de l'entraînement semaine après semaine (facteurs.py →
    simulateur/pronostics_hors_echantillon.jsonl.gz), mélange appris sur les semaines précédentes seulement ;
  — direct : la 1re prédiction « Simulation + Elo » du journal (simulateur/pronostics_log.jsonl).

RÈGLE FIXÉE AVANT DE VOIR LE RÉSULTAT (23/10/2026, 13 h) :
  — prix d'entrée : le dernier prix ACHETEUR (ask) affiché entre 12 h et 60 min avant le début ;
  — frais preneur : Kalshi 0,07 × p × (1 − p) par contrat ; Polymarket (sport) 0,05 × p × (1 − p) ;
  — on joue un côté si P_algo(côté) − ask − frais ≥ SEUIL (0,05 = la règle principale ; 0,03 et 0,08 en
    lecture), au plus un côté par match (le plus grand écart), une mise de 1 contrat ;
  — MESURE QUI JUGE : la CLV contre la clôture Pinnacle (marge retirée) = P_Pinnacle(côté) à la clôture − ask.
    Le ROI est donné, mais il ne juge pas. Rien n'est conclu sous 30 paris.
  — TÉMOIN : la même règle avec la cote Pinnacle du même instant à la place de l'algorithme. Si le témoin fait
    aussi bien, l'éventuel gain vient de l'écart Pinnacle / marché, pas de notre algorithme.

Sortie : Tennis_Edge_Lab/live/rentabilite_marches.json et le rapport à l'écran.
Usage : python simulateur/etude_rentabilite_marches.py [racine] [--jours 90]
"""
import collections
import datetime as dt
import glob
import gzip
import importlib.util
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import feuilles as FE  # noqa: E402
import nos_resultats as NR  # noqa: E402

FRAIS = {'kalshi': 0.07, 'polymarket': 0.05}
SEUILS = (0.03, 0.05, 0.08)
SEUIL_PRINCIPAL = 0.05
DECISION_MIN, FENETRE_H = 60, 12
MIN_N = 30
SORTIE = os.path.join('Tennis_Edge_Lab', 'live', 'rentabilite_marches.json')


def _ts(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def frais(venue, p):
    return FRAIS[venue] * p * (1 - p)


def _books(racine):
    sp = importlib.util.spec_from_file_location('tennis_edge_rm_books', os.path.join(racine, 'Tennis_Edge_Lab', 'books.py'))
    b = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(b)
    return b


def proba_home(books, ch, ca):
    k = books.power_exponent(ch, ca)
    return (1 / ch) ** k if k else (1 / ch) / (1 / ch + 1 / ca)


# ------------------------------------------------------------------ matchs : noms, début, Pinnacle
def matchs_pinnacle(racine, books):
    """{uid: {'home', 'away', 'debut', 'pin': [(t, p_home)]}} depuis closing_lines (chaud + archives)."""
    sys.path.insert(0, os.path.join(racine, 'scripts'))
    import closing_store as CS
    out = {}
    cwd = os.getcwd()
    try:
        os.chdir(racine)
        d = CS.load_all(max_age_days=None)
    finally:
        os.chdir(cwd)
    for e in d.values():
        debut = _ts(e.get('commence_time'))
        if not debut or not e.get('home') or not e.get('away'):
            continue
        serie = []
        for h in e.get('history') or []:
            t = _ts(h.get('t'))
            try:
                ch, ca = float(h['home']), float(h['away'])
            except (KeyError, TypeError, ValueError):
                continue
            if t and ch > 1 and ca > 1 and t < debut:
                serie.append((t, proba_home(books, ch, ca)))
        serie.sort()
        uid = f"{debut.date()}_{NR.slug(e['home'])}_{NR.slug(e['away'])}"
        out[uid] = {'home': e['home'], 'away': e['away'], 'debut': debut, 'pin': serie, 'tournoi': e.get('tournament')}
    return out


def valeur_a(serie, t):
    v = None
    for x in serie:
        if x[0] > t:
            break
        v = x
    return v


# ------------------------------------------------------------------ pronostics de l'algorithme
def pronostics_historiques(racine, M):
    """{uid: (p_algo_home, gagnant)} : pronostics hors échantillon reliés à nos matchs (noms, ± 1 jour)."""
    try:
        with gzip.open(os.path.join(racine, 'simulateur', 'pronostics_hors_echantillon.jsonl.gz'), 'rt', encoding='utf-8') as f:
            H = {r['id']: r for r in (json.loads(l) for l in f) if r.get('p_algo') is not None}
    except (OSError, ValueError):
        return {}
    idx = FE.Index(FE.lire(racine))
    out = {}
    for uid, m in M.items():
        fi, inv = idx.trouver(str(m['debut'].date()), m['home'], m['away'])
        r = H.get((fi or {}).get('id')) if fi else None
        if not r:
            continue
        p, g = r['p_algo'], r['gagnant']
        if inv:
            p, g = 1 - p, {'home': 'away', 'away': 'home'}[g]
        out[uid] = (p, g)
    return out


def pronostics_direct(racine):
    """{uid: (p_algo_home, gagnant, pronostiqué_le)} : 1re prédiction « Simulation + Elo » du journal, match joué."""
    try:
        R = json.load(open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    out = {}
    for m in R.get('matchs') or []:
        c = (m.get('premier') or {}).get('combinaison') or {}
        g = (m.get('reel') or {}).get('gagnant')
        if c.get('p_home') is None or g not in ('home', 'away') or (m.get('reel') or {}).get('interrompu'):
            continue
        out[m['uid']] = (c['p_home'], g, _ts(m.get('pronostique_le')))
    return out


# ------------------------------------------------------------------ prix Kalshi / Polymarket
def charger_prix(racine, uids_debut, jours=None):
    """{(venue, uid): {'home': [(t, ask, mid)], 'away': [...]}} — ticks entre début − 12 h et le début."""
    out = collections.defaultdict(lambda: {'home': [], 'away': []})
    fichiers = []
    for venue, motif in (('kalshi', 'kx_ticks_*.jsonl*'), ('polymarket', 'pm_ticks_*.jsonl*')):
        vus = {}
        for p in sorted(glob.glob(os.path.join(racine, 'parts', motif))):
            jour = os.path.basename(p)[9:19]
            if p.endswith('.jsonl') or jour not in vus:
                vus[jour] = p                                  # le .jsonl l'emporte sur le .gz du même jour
        fichiers += [(venue, p) for _, p in sorted(vus.items())]
    for venue, p in fichiers:
        try:
            f = gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8')
        except OSError:
            continue
        with f:
            for l in f:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                uid, side = r.get('local_uid'), r.get('local_side')
                debut = uids_debut.get(uid)
                if debut is None or side not in ('home', 'away'):
                    continue
                if venue == 'polymarket' and r.get('market_type') != 'match':
                    continue
                if venue == 'kalshi' and r.get('status') not in (None, 'active', 'open'):
                    continue
                t = _ts(r.get('ts'))
                if not t or not (debut - dt.timedelta(hours=FENETRE_H) <= t <= debut):
                    continue
                ask = r.get('yes_ask') if venue == 'kalshi' else r.get('ask')
                mid = r.get('mid')
                try:
                    ask, mid = float(ask), float(mid)
                except (TypeError, ValueError):
                    continue
                if 0 < ask < 1 and 0 < mid < 1:
                    out[(venue, uid)][side].append((t, ask, mid))
    for v in out.values():
        v['home'].sort()
        v['away'].sort()
    return out


# ------------------------------------------------------------------ la règle
def paris(prix, M, prono, seuil, source, temoin=False):
    """Paris de la règle ; prono : {uid: (p_home, gagnant[, pronostiqué_le])}."""
    out = []
    for (venue, uid), s in prix.items():
        m = M.get(uid)
        pr = prono.get(uid)
        if not m or not pr:
            continue
        debut = m['debut']
        t_dec = debut - dt.timedelta(minutes=DECISION_MIN)
        if len(pr) > 2 and pr[2] and pr[2] > t_dec:
            continue                                            # pas encore pronostiqué à l'heure de la décision
        if temoin:
            pp = valeur_a(m['pin'], t_dec)
            if not pp:
                continue
            p_home = pp[1]
        else:
            p_home = pr[0]
        meilleur = None
        for side, p in (('home', p_home), ('away', 1 - p_home)):
            x = valeur_a(s[side], t_dec)
            if not x:
                continue
            ask = x[1]
            ecart = p - ask - frais(venue, ask)
            if ecart >= seuil and (meilleur is None or ecart > meilleur[0]):
                meilleur = (ecart, side, ask)
        if not meilleur:
            continue
        ecart, side, ask = meilleur
        cout = ask + frais(venue, ask)
        gagne = pr[1] == side
        pin = m['pin'][-1][1] if m['pin'] else None
        clv = ((pin if side == 'home' else 1 - pin) - ask) if pin is not None else None
        fin = s[side][-1][2] if s[side] else None
        out.append({'venue': venue, 'uid': uid, 'source': source, 'cote': side, 'ask': round(ask, 3), 'ecart': round(ecart, 4),
                    'gagne': gagne, 'roi': round(((1.0 if gagne else 0.0) - cout) / cout, 4),
                    'clv_pinnacle': round(clv, 4) if clv is not None else None,
                    'clv_marche': round(fin - ask, 4) if fin is not None else None})
    return out


def _ic(xs, n_boot=2000, graine=7):
    if len(xs) < 2:
        return None
    rnd = random.Random(graine)
    moy = sorted(sum(rnd.choice(xs) for _ in xs) / len(xs) for _ in range(n_boot))
    return [round(moy[int(0.025 * n_boot)], 4), round(moy[int(0.975 * n_boot)], 4)]


def bilan(P):
    if not P:
        return {'n': 0}
    roi = [p['roi'] for p in P]
    clv = [p['clv_pinnacle'] for p in P if p['clv_pinnacle'] is not None]
    out = {'n': len(P), 'gagnes_pct': round(100 * sum(p['gagne'] for p in P) / len(P), 1),
           'roi_moyen': round(sum(roi) / len(roi), 4), 'roi_ic95': _ic(roi),
           'clv_pinnacle_moyenne': round(sum(clv) / len(clv), 4) if clv else None, 'clv_pinnacle_ic95': _ic(clv) if clv else None,
           'clv_positive_pct': round(100 * sum(c > 0 for c in clv) / len(clv), 1) if clv else None}
    if len(P) < MIN_N:
        out['verdict'] = f"moins de {MIN_N} paris : ne pas conclure"
    elif clv and out['clv_pinnacle_ic95'] and out['clv_pinnacle_ic95'][0] > 0:
        out['verdict'] = "bat la clôture Pinnacle (IC95 de la CLV au-dessus de 0)"
    elif clv and out['clv_pinnacle_ic95'] and out['clv_pinnacle_ic95'][1] < 0:
        out['verdict'] = "perd contre la clôture Pinnacle (IC95 de la CLV sous 0)"
    else:
        out['verdict'] = "ne tranche pas (IC95 de la CLV autour de 0)"
    return out


def main(argv):
    racine = next((a for a in argv[1:] if not a.startswith('--')), os.path.join(ICI, '..'))
    books = _books(racine)
    M = matchs_pinnacle(racine, books)
    hist, direct = pronostics_historiques(racine, M), pronostics_direct(racine)
    uids = set(hist) | set(direct)
    prix = charger_prix(racine, {u: M[u]['debut'] for u in uids if u in M})
    print(f"Matchs avec clôture Pinnacle : {len(M)} · pronostics reliés : {len(hist)} historiques, {len(direct)} en direct · "
          f"séries de prix : {len(prix)} (Kalshi {sum(1 for v, _ in prix if v == 'kalshi')}, "
          f"Polymarket {sum(1 for v, _ in prix if v == 'polymarket')})")
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': (f"prix acheteur entre {FENETRE_H} h et {DECISION_MIN} min avant le début ; frais preneur Kalshi 0,07·p(1−p), "
                     f"Polymarket 0,05·p(1−p) ; on joue si P_algo − prix − frais ≥ seuil (principal {SEUIL_PRINCIPAL}) ; "
                     f"jugé sur la CLV contre la clôture Pinnacle ; rien n'est conclu sous {MIN_N} paris"),
           'resultats': {}}
    for seuil in SEUILS:
        for nom, prono in (('historique', hist), ('direct', direct)):
            P = paris(prix, M, prono, seuil, nom)
            T = paris(prix, M, prono, seuil, nom, temoin=True)
            for venue in ('kalshi', 'polymarket'):
                k = f"{venue}|{nom}|{seuil}"
                doc['resultats'][k] = {'algorithme': bilan([p for p in P if p['venue'] == venue]),
                                       'temoin_pinnacle': bilan([p for p in T if p['venue'] == venue])}
    os.makedirs(os.path.dirname(os.path.join(racine, SORTIE)), exist_ok=True)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"\nRègle : {doc['regle']}\n")
    for k, v in doc['resultats'].items():
        a, t = v['algorithme'], v['temoin_pinnacle']
        print(f"{k:<28} algorithme : n {a['n']}" + (f" · ROI {a['roi_moyen']:+.3f} · CLV Pin {a['clv_pinnacle_moyenne']} "
                                                    f"IC95 {a['clv_pinnacle_ic95']} — {a['verdict']}" if a['n'] else '')
              + f"   |   témoin Pinnacle : n {t['n']}" + (f" · CLV {t['clv_pinnacle_moyenne']}" if t['n'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
