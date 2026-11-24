#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_outsider_peu_documente.py — PISTE SUIVIE : l'algo est-il trop sûr du favori quand l'OUTSIDER est peu documenté ?
(24/11/2026, paquet 399, Lucas : « il doit y avoir des erreurs dans nos données ou l'algo loupe quelque chose »)

D'OÙ VIENT LA PISTE (matchs jugés du 21/10 au 24/11) : outsider de moins de 60 matchs classés face à un favori qui en a
60 ou plus : favori annoncé ~80,6 %, gagnant ~72,9 % (210 matchs, environ 2,8 erreurs types), même sens sur les deux
moitiés. Sur l'archive (2018 → 2026), le même profil était bien calibré. La sonde du 24/11
(scripts/sonde_outsiders_inconnus.py, règle fixée avant) conclut : PAS de données manquantes en général (médiane
TennisApi 18 matchs depuis juin 2024 contre 14 chez nous) ; il manque surtout des matchs du circuit UTR (458 sur 81
joueurs). Selon la règle de la sonde, le profil passe en suivi comme un défaut possible du modèle. Les seuils (60 matchs)
ont été choisis en regardant ces 210 matchs : ils ne comptent PAS dans le jugement.

RÈGLE ÉCRITE LE 24/11/2026, AVANT TOUT MATCH JUGÉ (ne pas la modifier après coup) :
  • matchs : pronostics jugés (pronostics_resultats.json, dernier passage avant le début) commencés à partir du
    25/11/2026, vainqueur connu, sans abandon, forfait ni score interrompu ;
  • profil : outsider (le joueur sous 50 %) avec moins de 60 matchs classés, favori avec 60 ou plus ;
  • correction étudiée : p' = σ(a · logit p) sur la probabilité du favori ;
  • décision en CHALLENGER (ATP et WTA suivis à titre d'information), à 1 000 matchs du profil jugés : a appris sur la
    première moitié (ordre chronologique), jugé sur la seconde ; RETENUE si la log loss de la seconde moitié baisse
    d'au moins 0,001, d'au moins 2 erreurs types (test apparié par match), ET si a, appris séparément sur chaque
    moitié, est du même côté de 1 ; sinon ÉCARTÉE ;
  • rien ne change dans le % : une piste retenue est proposée à Lucas, un paquet à part la met en place.
Stock : simulateur/suivi_outsider_peu_documente_matchs.json (empreinte du match, aucun nom). Sortie :
simulateur/rapport_outsider_peu_documente.json (aucun nom, aucune cote).
Usage : python simulateur/suivi_outsider_peu_documente.py [racine]
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys

DEBUT_JUGEMENT = '2026-11-25'
SEUIL = 60
MIN_CAS, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
CIRCUITS = ('CH', 'ATP', 'WTA')
STOCK = os.path.join('simulateur', 'suivi_outsider_peu_documente_matchs.json')
SORTIE = os.path.join('simulateur', 'rapport_outsider_peu_documente.json')


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def empreinte(uid):
    return hashlib.sha256(str(uid).encode('utf-8')).hexdigest()[:16]


def profil(m):
    """(probabilité du favori, le favori a gagné) si le match est du profil, sinon None."""
    d = (m.get('dernier') or {}).get('combinaison') or {}
    p, mj, reel = d.get('p_home'), m.get('matchs_joues') or [None, None], m.get('reel') or {}
    if not isinstance(p, (int, float)) or None in mj or reel.get('gagnant') not in ('home', 'away'):
        return None
    if reel.get('interrompu') or reel.get('score_invalide'):
        return None
    fav_home = p >= 0.5
    mf, mo = (mj[0], mj[1]) if fav_home else (mj[1], mj[0])
    if mo >= SEUIL or mf < SEUIL:
        return None
    return (p if fav_home else 1 - p), int((reel['gagnant'] == 'home') == fav_home)


def mettre_a_jour(stock, resultats):
    n = 0
    for m in resultats.get('matchs') or []:
        if m.get('circuit') not in CIRCUITS or str(m.get('debut'))[:10] < DEBUT_JUGEMENT or not m.get('uid'):
            continue
        e = empreinte(m['uid'])
        if e in stock:
            continue
        x = profil(m)
        if x:
            stock[e] = {'c': m['circuit'], 'd': str(m['debut'])[:16], 'p': round(x[0], 4), 'y': x[1]}
            n += 1
    return n


def apprendre(L):
    """a maximisant la vraisemblance de σ(a · logit p) (Newton, 1 paramètre)."""
    a = 1.0
    for _ in range(50):
        g = h = 0.0
        for x in L:
            z = _lg(x['p'])
            q = 1 / (1 + math.exp(-a * z))
            g += (x['y'] - q) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        pas = g / h
        a += pas
        if abs(pas) < 1e-7:
            break
    return a


def mesurer(L, a=None):
    n = len(L)
    if not n:
        return {'matchs': 0}
    out = {'matchs': n, 'annonce_pct': round(100 * sum(x['p'] for x in L) / n, 1),
           'gagne_pct': round(100 * sum(x['y'] for x in L) / n, 1)}
    if a is not None:
        g = [_ll(x['p'], x['y']) - _ll(1 / (1 + math.exp(-a * _lg(x['p']))), x['y']) for x in L]
        mu = sum(g) / n
        et = (sum((v - mu) ** 2 for v in g) / (n - 1)) ** 0.5 / n ** 0.5 if n > 1 else None
        out.update(gain_log_loss=round(mu, 5), erreurs_types=round(mu / et, 2) if et else None)
    return out


def decision(L):
    L = sorted(L, key=lambda x: x['d'])
    if len(L) < MIN_CAS:
        return 'en cours', {**mesurer(L), 'pente_provisoire': round(apprendre(L), 3) if len(L) >= 50 else None}, \
            [f'{len(L)} matchs du profil jugés sur {MIN_CAS}']
    h = len(L) // 2
    a1, a2 = apprendre(L[:h]), apprendre(L[h:])
    m = mesurer(L[h:], a1)
    m.update(pente_apprise=round(a1, 3), pente_seconde_moitie=round(a2, 3), ensemble=mesurer(L))
    raisons = []
    if (m.get('gain_log_loss') or 0) < MARGE:
        raisons.append(f"gain {m.get('gain_log_loss')} < {MARGE}")
    if not m.get('erreurs_types') or m['erreurs_types'] < MIN_ERREURS_TYPES:
        raisons.append(f'gain sous {MIN_ERREURS_TYPES:g} erreurs types')
    if (a1 - 1) * (a2 - 1) <= 0:
        raisons.append('pente pas du même côté de 1 sur les deux moitiés')
    return ('écartée' if raisons else 'retenue'), m, raisons


def rapport(stock):
    par = {c: [x for x in stock.values() if x['c'] == c] for c in CIRCUITS}
    statut, m, raisons = decision(par['CH'])
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 399,
            'regle': (f"outsider < {SEUIL} matchs classés, favori ≥ {SEUIL}, matchs depuis le {DEBUT_JUGEMENT} ; "
                      f"p' = σ(a · logit p) ; décision en Challenger à {MIN_CAS} matchs : a appris sur la 1re moitié, "
                      f"gain ≥ {MARGE} et ≥ {MIN_ERREURS_TYPES:g} erreurs types sur la 2de, pente du même côté de 1 "
                      "sur les deux moitiés ; le % ne change pas"),
            'statut': statut, 'raisons': raisons, 'challenger': m,
            'information': {c: mesurer(par[c]) for c in ('ATP', 'WTA')}}


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    p_stock = os.path.join(racine, STOCK)
    try:
        with open(p_stock, encoding='utf-8') as f:
            stock = json.load(f).get('matchs') or {}
    except (OSError, ValueError):
        stock = {}
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            res = json.load(f)
    except (OSError, ValueError):
        res = {}
    n = mettre_a_jour(stock, res)
    with open(p_stock, 'w', encoding='utf-8') as f:
        json.dump({'debut_jugement': DEBUT_JUGEMENT, 'matchs': dict(sorted(stock.items()))}, f, ensure_ascii=False, indent=0)
        f.write('\n')
    R = rapport(stock)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
        f.write('\n')
    c = R['challenger']
    print(f"Outsider peu documenté : {n} nouveaux matchs, {c['matchs']} en Challenger depuis le {DEBUT_JUGEMENT} — {R['statut']}")
    if c.get('matchs'):
        print(f"  favori annoncé {c.get('annonce_pct')} %, gagnant {c.get('gagne_pct')} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
