#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
suivi_desaccord_modeles.py — PISTE SUIVIE : en Challenger, quand la version « stats » et la simulation ne désignent
pas le même vainqueur, le % affiché ferait-il mieux de suivre la version « stats » ? (23/11/2026, paquet 383,
décision de Lucas : « Lance les 2 »).

D'OÙ VIENT LA PISTE : diagnostic privé du 23/11/2026 sur les pronostics du 21/10 au 22/11 : 213 désaccords en
Challenger, Brier du % affiché 0,0071 plus haut que la version « stats » seule (± 0,0053, 1,3 erreur type). Pas
conclu : trop peu de cas, trouvé en regardant une dizaine de découpages, sens contraire en ATP et en WTA. Ces 213
matchs ont servi à trouver la piste : ils ne comptent PAS dans le jugement.

RÈGLE ÉCRITE LE 23/11/2026, AVANT TOUT MATCH JUGÉ (ne pas la modifier après coup) :
  • matchs : pronostics du journal (simulateur/journal_pronostics), dernier passage avant le début, matchs commencés
    à partir du 24/11/2026, vainqueur connu (sans abandon, forfait ni score interrompu) ;
  • désaccord : version « stats » et simulation de part et d'autre de 50 % ;
  • comparaison : log loss du vainqueur du % affiché (combinaison) contre la version « stats » seule (Brier donné aussi) ;
  • décision en CHALLENGER seulement ; ATP et WTA sont suivis à titre d'information (circuit par circuit) ;
  • EN COURS tant que moins de 1 000 désaccords Challenger jugés ;
  • à 1 000 : RETENUE si gain de log loss ≥ 0,001, gain ≥ 2 erreurs types (test apparié par match) et gain du même
    signe sur les deux moitiés chronologiques ; sinon ÉCARTÉE ;
  • rien ne change dans le % : une piste retenue reste une proposition, Lucas décide, un paquet à part la met en place
    avec sa règle de retrait.
Les matchs jugés sont gardés dans simulateur/suivi_desaccord_modeles_matchs.json (empreinte du match, aucun nom) :
le suivi ne dépend pas de la durée de conservation des résultats.
Sortie : simulateur/rapport_desaccord_modeles.json (aucun nom de joueur, aucune cote).
Usage : python simulateur/suivi_desaccord_modeles.py [racine]
"""
import datetime as dt
import glob
import gzip
import hashlib
import json
import math
import os
import sys

DEBUT_JUGEMENT = '2026-11-24'
MIN_CAS, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
CIRCUITS = ('CH', 'ATP', 'WTA')
STOCK = os.path.join('simulateur', 'suivi_desaccord_modeles_matchs.json')
SORTIE = os.path.join('simulateur', 'rapport_desaccord_modeles.json')


def _ll(p, y):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def empreinte(uid):
    return hashlib.sha256(str(uid).encode('utf-8')).hexdigest()[:16]


def derniers_passages(racine, debut=DEBUT_JUGEMENT):
    """{uid: {circuit, debut, comb, stats, simu}} : dernier passage avant le début, matchs depuis `debut`."""
    out = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '2*.jsonl.gz'))):
        if os.path.basename(f)[:10] < (dt.date.fromisoformat(debut) - dt.timedelta(days=3)).isoformat():
            continue
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                d0 = r.get('debut_utc') or r.get('debut')
                if not r.get('uid') or not d0 or str(d0)[:10] < debut or r.get('circuit') not in CIRCUITS:
                    continue
                if str(r.get('passage', '')) > str(d0).replace('+00:00', 'Z')[:19] + 'Z':
                    continue
                ps = {k: (r.get(k) or {}).get('p_home') for k in ('combinaison', 'stats', 'simulation')}
                if any(not isinstance(v, (int, float)) or not 0 < v < 1 for v in ps.values()):
                    continue
                if r['uid'] not in out or r['passage'] > out[r['uid']]['passage']:
                    out[r['uid']] = {'passage': r['passage'], 'circuit': r['circuit'], 'debut': str(d0)[:10],
                                     'comb': float(ps['combinaison']), 'stats': float(ps['stats']),
                                     'simu': float(ps['simulation'])}
    return out


def resultats(racine):
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            return {m['uid']: m for m in json.load(f).get('matchs', []) if isinstance(m, dict) and m.get('uid')}
    except (OSError, ValueError):
        return {}


def mettre_a_jour(stock, passages, res):
    """Ajoute au stock les désaccords dont le vainqueur est connu. Un match déjà jugé n'est jamais réécrit."""
    n = 0
    for uid, x in passages.items():
        e = empreinte(uid)
        if e in stock:
            continue
        if (x['stats'] >= 0.5) == (x['simu'] >= 0.5):
            continue
        re_ = (res.get(uid) or {}).get('reel') or {}
        if re_.get('gagnant') not in ('home', 'away') or re_.get('interrompu') or re_.get('score_invalide'):
            continue
        stock[e] = {'c': x['circuit'], 'd': x['debut'], 'comb': round(x['comb'], 4), 'stats': round(x['stats'], 4),
                    'simu': round(x['simu'], 4), 'y': 1 if re_['gagnant'] == 'home' else 0}
        n += 1
    return n


def mesurer(L):
    n = len(L)
    if not n:
        return {'matchs': 0}
    g = [_ll(x['comb'], x['y']) - _ll(x['stats'], x['y']) for x in L]     # > 0 : la version « stats » fait mieux
    mu = sum(g) / n
    et = (sum((v - mu) ** 2 for v in g) / (n - 1)) ** 0.5 / n ** 0.5 if n > 1 else None
    br = lambda k: round(sum((x[k] - x['y']) ** 2 for x in L) / n, 4)  # noqa: E731
    pct = lambda k: round(100 * sum((x[k] >= 0.5) == (x['y'] == 1) for x in L) / n, 1)  # noqa: E731
    return {'matchs': n, 'gain_log_loss': round(mu, 5), 'erreur_type': round(et, 5) if et else None,
            'erreurs_types': round(mu / et, 2) if et else None,
            'brier': {'affiche': br('comb'), 'stats': br('stats'), 'simulation': br('simu')},
            'vainqueurs_pct': {'affiche': pct('comb'), 'stats': pct('stats'), 'simulation': pct('simu')}}


def decision(L):
    m = mesurer(L)
    if m['matchs'] < MIN_CAS:
        return 'en cours', m, [f"{m['matchs']} désaccords jugés sur {MIN_CAS}"]
    L = sorted(L, key=lambda x: x['d'])
    h = len(L) // 2
    m['moities'] = [mesurer(L[:h])['gain_log_loss'], mesurer(L[h:])['gain_log_loss']]
    raisons = []
    if m['gain_log_loss'] < MARGE:
        raisons.append(f"gain {m['gain_log_loss']} < {MARGE}")
    if not m['erreurs_types'] or m['erreurs_types'] < MIN_ERREURS_TYPES:
        raisons.append(f"gain sous {MIN_ERREURS_TYPES} erreurs types")
    if not all(v > 0 for v in m['moities']):
        raisons.append('pas le même sens sur les deux moitiés')
    return ('écartée' if raisons else 'retenue'), m, raisons


def rapport(stock):
    par = {c: [x for x in stock.values() if x['c'] == c] for c in CIRCUITS}
    statut, m, raisons = decision(par['CH'])
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 383,
            'regle': (f"Challenger, version « stats » et simulation en désaccord sur le vainqueur, matchs depuis le "
                      f"{DEBUT_JUGEMENT} ; % affiché contre la version « stats » seule (log loss) ; décision à "
                      f"{MIN_CAS} désaccords : gain ≥ {MARGE}, ≥ {MIN_ERREURS_TYPES:g} erreurs types, même signe sur "
                      "les deux moitiés ; le % ne change pas"),
            'statut': statut, 'raisons': raisons, 'challenger': m,
            'information': {c: mesurer(par[c]) for c in ('ATP', 'WTA')},
            'premier_match': min((x['d'] for x in stock.values()), default=None),
            'dernier_match': max((x['d'] for x in stock.values()), default=None)}


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    p_stock = os.path.join(racine, STOCK)
    try:
        with open(p_stock, encoding='utf-8') as f:
            stock = json.load(f).get('matchs') or {}
    except (OSError, ValueError):
        stock = {}
    n = mettre_a_jour(stock, derniers_passages(racine), resultats(racine))
    with open(p_stock, 'w', encoding='utf-8') as f:
        json.dump({'debut_jugement': DEBUT_JUGEMENT, 'matchs': dict(sorted(stock.items()))}, f, ensure_ascii=False,
                  indent=0)
        f.write('\n')
    R = rapport(stock)
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
        f.write('\n')
    c = R['challenger']
    print(f"Désaccords stats / simulation : {n} nouveaux jugés, {c['matchs']} en Challenger depuis le {DEBUT_JUGEMENT}"
          f" — {R['statut']}")
    if c.get('matchs'):
        print(f"  gain de log loss en suivant la version stats : {c['gain_log_loss']} (erreurs types : {c['erreurs_types']})")
    for k in ('ATP', 'WTA'):
        print(f"  {k} (information) : {R['information'][k]['matchs']} désaccords")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
