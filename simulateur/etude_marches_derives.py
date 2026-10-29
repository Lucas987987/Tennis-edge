#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_marches_derives.py — nos lignes figées contre Pinnacle : nombre de sets, 2-0, total et handicap de jeux (29/10/2026).

Données (aucune requête) :
  - nos probabilités FIGÉES AVANT le match : journal des pronostics (simulateur/journal_pronostics/AAAA-MM-JJ.jsonl.gz,
    dernier passage avant le début : score en sets) et journal des lignes (lignes_algo_v1.jsonl : total et handicap de
    jeux, depuis le 28/10) ;
  - Pinnacle : ouverture et clôture des marchés dérivés (parts/hist_derives_*, scripts/marches_derives.py, depuis le
    21/10, 0 requête de plus) ; cotes rendues justes (marge retirée, deux issues) ;
  - le score réel (Tennis_Edge_Lab/live/pronostics_resultats.json ; abandons écartés).
Conventions vérifiées sur les données (29/10) : handicap de sets / de jeux = celui du joueur 1 (home) — l'issue « 1 »
gagne si (home − away) + ligne > 0 ; total : « Over » = strictement plus que la ligne.

RÈGLE FIXÉE AVANT DE VOIR LES RÉSULTATS (29/10/2026, 15 h 10) — descriptif, rien n'entre dans l'algo :
  1. PRÉCISION : par marché, log loss de notre probabilité contre celle de la clôture Pinnacle (juste), sur les MÊMES
     matchs joués. Moins de 30 matchs : rien à conclure.
  2. CLV : quand notre probabilité s'écarte de plus de 5 points de l'ouverture Pinnacle (juste), on prend le côté que
     nous préférons ; CLV = cote d'ouverture / cote de clôture − 1 sur ce côté (la mesure de validation du projet), et
     part des cas où la clôture s'est rapprochée de nous. Moins de 30 signaux : rien à conclure. Un écart n'est « net »
     que si l'intervalle à 95 % de la CLV moyenne ne contient pas 0.
CONTRÔLE AJOUTÉ APRÈS LE PREMIER RÉSULTAT (29/10/2026, 15 h 30 — donc à juger sur les matchs SUIVANTS seulement) :
  notre pronostic est fait quelques heures avant le match, bien après l'ouverture Pinnacle ; la CLV « depuis
  l'ouverture » mesure surtout l'information arrivée entre-temps, que Pinnacle intègre aussi. La CLV qui compte part du
  prix DISPONIBLE AU MOMENT de notre pronostic : la dernière cote relevée avant notre passage (6 h, 2 h ou 30 min avant
  le début ; 6 h et 2 h relevées depuis le 29/10 ; un pronostic plus ancien est écarté). Même seuil (5 points), mêmes
  30 signaux.
Les cotes ne servent qu'à comparer : elles n'entrent jamais dans l'algo (indépendant du marché).
Usage : python simulateur/etude_marches_derives.py [racine]  →  simulateur/etude_marches_derives.json
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join('simulateur', 'etude_marches_derives.json')
ECART_SIGNAL = 0.05
N_MIN = 30
VERSIONS = ('combinaison', 'stats', 'simulation')


def _ouvrir(p):
    return gzip.open(p, 'rt', encoding='utf-8') if p.endswith('.gz') else open(p, encoding='utf-8')


def charger_derives(racine, book='pinnacle'):
    D = {}
    for p in sorted(glob.glob(os.path.join(racine, 'parts', 'hist_derives_*'))):
        try:
            with _ouvrir(p) as f:
                for l in f:
                    if l.strip():
                        r = json.loads(l)
                        if r.get('book') == book:
                            D[r['uid']] = r
        except (OSError, ValueError, EOFError):
            continue
    return D


def charger_journal(racine):
    """{uid: (debut, home, away, sets du dernier passage avant le début)}."""
    J = {}
    for p in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '20*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    if not l.strip():
                        continue
                    r = json.loads(l)
                    if str(r.get('passage', ''))[:16] > str(r.get('debut', ''))[:16]:
                        continue                                    # après le début : pas figé avant le match
                    v = next((r.get(k) for k in VERSIONS if (r.get(k) or {}).get('sets')), None)
                    if v:
                        J[r['uid']] = (r.get('debut'), r.get('home'), r.get('away'), v['sets'], r.get('passage'))
        except (OSError, ValueError, EOFError):
            continue
    return J


def charger_lignes(racine):
    out = {}
    try:
        with open(os.path.join(racine, 'simulateur', 'journal_pronostics', 'lignes_algo_v1.jsonl'), encoding='utf-8') as f:
            for l in f:
                if l.strip():
                    r = json.loads(l)
                    out.setdefault(r['uid'], r)                     # la première, figée avant le match
    except (OSError, ValueError):
        pass
    return out


def sets_du_score(score):
    try:
        S = [tuple(int(v) for v in s.split('-')[:2]) for s in str(score).split()]
        return S if S and all(len(s) == 2 for s in S) else None
    except ValueError:
        return None


def charger_resultats(racine):
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            M = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        return {}
    out = {}
    for m in M:
        r = m.get('reel') or {}
        if r.get('gagnant') not in ('home', 'away') or r.get('interrompu') or r.get('score_invalide'):
            continue
        S = sets_du_score(r.get('score'))
        if S:
            out[m['uid']] = S
    return out


def juste(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    return (1 / a) / (1 / a + 1 / b) if a > 1 and b > 1 else None


def evenements(D, J, L):
    """[(uid, marché, p_modele, cotes Pinnacle du marché, issue A, issue B, résultat(sets) -> 1 si A, heure du pronostic)]."""
    out = []
    for uid, d in D.items():
        m = d.get('marches') or {}
        j = J.get(uid)
        if j:
            s = j[3]
            p3 = (s.get('2-1') or 0) + (s.get('1-2') or 0)
            out.append((uid, 'nombre de sets : 3 sets', p3, m.get('total_sets 2.5'), 'Over', 'Under',
                        lambda S: int(len(S) >= 3), j[4]))
            out.append((uid, 'home gagne 2-0', s.get('2-0'), m.get('handicap_sets -1.5'), '1', '2',
                        lambda S: int(sum(a > b for a, b in S) - sum(b > a for a, b in S) > 1.5), j[4]))
            out.append((uid, 'away ne perd pas 0-2 → home +1,5 sets', 1 - (s.get('0-2') or 0), m.get('handicap_sets 1.5'), '1', '2',
                        lambda S: int(sum(a > b for a, b in S) - sum(b > a for a, b in S) + 1.5 > 0), j[4]))
        li = (L.get(uid) or {}).get('lignes') or {}
        if li.get('meilleur_des', 3) == 3:
            for k, p in li.items():
                if k.startswith('total_plus_'):
                    x = float(k[len('total_plus_'):])
                    out.append((uid, f'total de jeux > {x:g}', p, m.get(f'total_jeux {x:g}'), 'Over', 'Under',
                                lambda S, x=x: int(sum(a + b for a, b in S) > x), L[uid].get('fige_le')))
                elif k.startswith('handicap_favori_'):
                    x = float(k[len('handicap_favori_'):])
                    if li.get('favori') == 'home':                  # home −x : issue « 1 » à la ligne −x
                        out.append((uid, f'handicap de jeux du favori −{x:g}', p, m.get(f'handicap_jeux {-x:g}'), '1', '2',
                                    lambda S, x=x: int(sum(a - b for a, b in S) - x > 0), L[uid].get('fige_le')))
                    else:                                           # away −x : issue « 2 » à la ligne +x
                        out.append((uid, f'handicap de jeux du favori −{x:g}', p, m.get(f'handicap_jeux {x:g}'), '2', '1',
                                    lambda S, x=x: int(sum(b - a for a, b in S) - x > 0), L[uid].get('fige_le')))
    return out


def _moy_ic(v):
    n = len(v)
    if n < 2:
        return (sum(v) / n if n else None), None
    m = sum(v) / n
    e = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1) / n)
    return m, [m - 1.96 * e, m + 1.96 * e]


def etudier(D, J, L, R):
    par = {}
    for uid, nom, p, mk, A, B, res, quand in evenements(D, J, L):
        if p is None or not mk or A not in mk or B not in mk:
            continue
        qa, qb = mk[A], mk[B]
        po, pc = juste(qa.get('ouverture'), qb.get('ouverture')), juste(qa.get('cloture'), qb.get('cloture'))
        if pc is None:
            continue
        e = par.setdefault(nom, {'precision': [], 'signaux': []})
        S = R.get(uid)
        p = min(max(float(p), 1e-4), 1 - 1e-4)
        if S:
            y = res(S)
            ll = lambda q: -math.log(max(q if y else 1 - q, 1e-6))
            e['precision'].append((ll(p), ll(pc), (p - y) ** 2, (pc - y) ** 2))
        if po is not None and abs(p - po) > ECART_SIGNAL:
            cote = qa if p > po else qb                         # le côté que nous préférons
            try:
                clv = float(cote['ouverture']) / float(cote['cloture']) - 1
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            vers = (pc - po) * (1 if p > po else -1)
            e['signaux'].append((clv, vers))
        k_ = cle_au_pronostic(D[uid].get('commence_time'), quand)        # contrôle : le prix disponible au pronostic
        pd_ = juste(qa.get(k_), qb.get(k_)) if k_ else None
        if pd_ is not None and abs(p - pd_) > ECART_SIGNAL:
            cote = qa if p > pd_ else qb
            try:
                e.setdefault('signaux_pronostic', []).append((float(cote[k_]) / float(cote['cloture']) - 1, (pc - pd_) * (1 if p > pd_ else -1)))
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    out = {}
    for nom, e in sorted(par.items()):
        P, Sg = e['precision'], e['signaux']
        r = {'matchs_joues': len(P), 'signaux': len(Sg)}
        if P:
            n = len(P)
            r.update(log_loss_algo=round(sum(x[0] for x in P) / n, 4), log_loss_pinnacle=round(sum(x[1] for x in P) / n, 4),
                     brier_algo=round(sum(x[2] for x in P) / n, 4), brier_pinnacle=round(sum(x[3] for x in P) / n, 4))
            r['ecart_log_loss'] = round(r['log_loss_algo'] - r['log_loss_pinnacle'], 4)
            r['precision_conclusion'] = n >= N_MIN
        if Sg:
            m, ic = _moy_ic([x[0] for x in Sg])
            r.update(clv_moy_pct=round(100 * m, 2), clv_ic95_pct=[round(100 * x, 2) for x in ic] if ic else None,
                     vers_nous_pct=round(100 * sum(1 for x in Sg if x[1] > 0) / len(Sg), 1),
                     loin_de_nous_pct=round(100 * sum(1 for x in Sg if x[1] < 0) / len(Sg), 1))
            r['clv_conclusion'] = len(Sg) >= N_MIN
            r['clv_net'] = bool(ic and len(Sg) >= N_MIN and (ic[0] > 0 or ic[1] < 0))
        Sp = e.get('signaux_pronostic') or []
        if Sp:
            m, ic = _moy_ic([x[0] for x in Sp])
            r['au_pronostic'] = {'signaux': len(Sp), 'clv_moy_pct': round(100 * m, 2),
                                 'clv_ic95_pct': [round(100 * x, 2) for x in ic] if ic else None,
                                 'vers_nous_pct': round(100 * sum(1 for x in Sp if x[1] > 0) / len(Sp), 1),
                                 'immobile_pct': round(100 * sum(1 for x in Sp if x[1] == 0) / len(Sp), 1),
                                 'conclusion': len(Sp) >= N_MIN,
                                 'net': bool(ic and len(Sp) >= N_MIN and (ic[0] > 0 or ic[1] < 0))}
        out[nom] = r
    return out


def cle_au_pronostic(debut, quand):
    """La dernière cote relevée AVANT notre pronostic et proche de lui : 'a_30min', 'a_2h' ou 'a_6h' ; None si le
    pronostic est plus ancien que 6 h avant le début (l'ouverture peut dater de plusieurs jours : écartée)."""
    try:
        d = dt.datetime.fromisoformat(str(debut).replace('Z', '+00:00'))
        q = dt.datetime.fromisoformat(str(quand).replace('Z', '+00:00'))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    if q.tzinfo is None:
        q = q.replace(tzinfo=dt.timezone.utc)
    for k, h in (('a_30min', 0.5), ('a_2h', 2), ('a_6h', 6)):
        if q >= d - dt.timedelta(hours=h):
            return k
    return None


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    D, J, L, R = charger_derives(racine), charger_journal(racine), charger_lignes(racine), charger_resultats(racine)
    res = etudier(D, J, L, R)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'sources': {'pinnacle_matchs': len(D), 'journal_matchs': len(J), 'lignes_matchs': len(L), 'resultats': len(R)},
           'regle': __doc__.split('RÈGLE FIXÉE')[1].split('Les cotes ne servent')[0].strip(), 'marches': res}
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Sources : {doc['sources']}")
    for nom, r in res.items():
        txt = f"{nom:<42} joués {r['matchs_joues']:>4}"
        if r.get('log_loss_algo') is not None:
            txt += f" · log loss algo {r['log_loss_algo']:.4f} / Pinnacle {r['log_loss_pinnacle']:.4f}"
        if r.get('signaux'):
            txt += (f" · {r['signaux']} signaux, CLV {r['clv_moy_pct']:+.2f} % {r['clv_ic95_pct']}, vers nous "
                    f"{r['vers_nous_pct']} %")
        a = r.get('au_pronostic')
        if a:
            txt += f" | au moment du pronostic : {a['signaux']} signaux, CLV {a['clv_moy_pct']:+.2f} % {a['clv_ic95_pct']}"
        print(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
