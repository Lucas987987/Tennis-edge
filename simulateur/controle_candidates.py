#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_candidates.py — LES CANDIDATES DU CHERCHEUR CONTRÔLÉES SUR NOS PRONOSTICS EN DIRECT (22/11/2026, paquet 350,
demande de Lucas : « A et B »).

POURQUOI : le chercheur (chercheur.py, paquet 320) apprend et juge sur un rejeu de l'archive qui ne refait PAS toute
la production (ni la simulation, ni les arbres). Une candidate doit donc être revue sur de vrais pronostics, jamais vus
par le chercheur, avant toute décision. Jusqu'ici ce contrôle se faisait à la main (terre battue Challenger : 234
matchs, pente 1,21, adoptée au paquet 322 ; « qualifications, 1er tour » Challenger : 202 matchs, pente 1,02, log loss
dégradée, non adoptée le 22/11/2026). Il tourne maintenant chaque semaine, juste après le chercheur.

DONNÉES : la production elle-même. Pour chaque match, le dernier pronostic figé avant le début
(simulateur/journal_pronostics, % affiché = combinaison.p_home) ; le vainqueur (Tennis_Edge_Lab/live/
pronostics_resultats.json, sans abandon ni forfait) ; le tour vient de la feuille TennisApi du match (feuilles/),
traduit par feuilles.ordre_tour (paquet 349).

RÈGLE ÉCRITE LE 22/11/2026, AVANT D'APPLIQUER CE SCRIPT AUX FUTURES CANDIDATES (ne pas la modifier après coup) :
  • cases contrôlables ici : les PENTES des familles « tous les matchs », « format », « surface », « saison », « tour »
    (on sait les retrouver sur un pronostic en direct). Les autres (niveau du tournoi, expérience, décalages) sont
    listées « non contrôlable automatiquement » : contrôle à la main si l'une devient candidate ;
  • une candidate déjà en service (corrections_chercheur.json) n'est pas recontrôlée ici : sa règle de retrait la suit ;
  • mesure : log loss du vainqueur, % affiché de la production contre le même % corrigé par la pente de la candidate
    (logit × pente, paramètre du chercheur tel quel, rien n'est réappris pour la décision) ; on donne aussi la pente
    apprise sur le direct (pour le sens) et l'erreur type du gain ;
  • EN ATTENTE sous 200 matchs en direct dans la case (le même seuil que la règle de retrait du paquet 322) ;
  • CONFIRMÉE si gain > 0 ET pente apprise sur le direct du même côté de 1 que celle du chercheur ; sinon NON CONFIRMÉE ;
  • rien ne change dans les pronostics : une candidate confirmée reste une proposition, Lucas décide, un paquet à part
    la met en place avec sa règle de retrait.
Sortie : simulateur/rapport_controle_candidates.json (aucun nom de joueur, aucune cote).
Usage : python simulateur/controle_candidates.py [racine]
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import feuilles as FE  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_controle_candidates.json')
N_MIN, EPS = 200, 1e-6
TOURS = {0: 'qualifications, 1er tour', 1: 'qualifications, 2e tour', 2: 'qualifications, 3e tour', 3: 'qualifications, 4e tour',
         4: '1er tour (128)', 5: '64es', 6: '32es ou poule', 7: '8es', 8: 'quarts', 9: 'demies', 10: 'finale'}
CONTROLABLES = ('tous les matchs', 'format', 'surface', 'saison', 'tour')


def _lg(p):
    p = min(max(p, EPS), 1 - EPS)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def _ll(p, y):
    p = min(max(p, EPS), 1 - EPS)
    return -math.log(p if y else 1 - p)


def _cle_nom(n):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(n or '')).encode('ascii', 'ignore').decode().lower()
                   if ch.isalpha())


def tours_des_feuilles(racine):
    """{(jour, frozenset(noms)): ordre du tour} — tour de la feuille TennisApi du match (connu avant le match)."""
    out = {}
    for f in glob.glob(os.path.join(racine, 'feuilles', '2*.jsonl.gz')):
        try:
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                for l in fh:
                    r = json.loads(l)
                    h, a = (r.get('home') or {}).get('nom'), (r.get('away') or {}).get('nom')
                    if h and a and r.get('jour') and r.get('tour'):
                        out[(r['jour'], frozenset((_cle_nom(h), _cle_nom(a))))] = FE.ordre_tour(r['tour'])
        except (OSError, ValueError, EOFError):
            continue
    return out


def _tour_du_match(tours, x):
    k = frozenset((_cle_nom(x.get('home')), _cle_nom(x.get('away'))))
    j = dt.date.fromisoformat(x['debut'])
    for d in (j, j - dt.timedelta(days=1), j + dt.timedelta(days=1)):
        v = tours.get((d.isoformat(), k))
        if v is not None:
            return v
    return None


def charger(racine):
    """[{circuit, debut, surface, bo, p, y, tour}] — un par match terminé (sans abandon ni forfait), dernier pronostic
    figé avant le début ; p = % affiché du joueur « home », y = 1 s'il a gagné."""
    derniers = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '2*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                c = r.get('combinaison') or {}
                debut = r.get('debut_utc') or r.get('debut')
                if c.get('p_home') is None or not debut or not r.get('uid'):
                    continue
                if str(r.get('passage', '')) > str(debut).replace('+00:00', 'Z')[:19] + 'Z':
                    continue
                if r['uid'] not in derniers or r['passage'] > derniers[r['uid']]['passage']:
                    derniers[r['uid']] = {'passage': r['passage'], 'circuit': r.get('circuit'), 'debut': str(debut)[:10],
                                          'surface': r.get('surface'), 'bo': r.get('meilleur_des'), 'p': float(c['p_home']),
                                          'home': r.get('home'), 'away': r.get('away')}
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            res = {m['uid']: m for m in json.load(f).get('matchs', []) if isinstance(m, dict) and m.get('uid')}
    except (OSError, ValueError):
        res = {}
    tours = tours_des_feuilles(racine)
    out = []
    for uid, x in derniers.items():
        re_ = (res.get(uid) or {}).get('reel') or {}
        if re_.get('gagnant') not in ('home', 'away') or re_.get('interrompu') or not (0 < x['p'] < 1):
            continue
        x['y'] = 1 if re_['gagnant'] == 'home' else 0
        x['tour'] = _tour_du_match(tours, x)
        for k in ('passage', 'home', 'away'):
            x.pop(k, None)
        out.append(x)
    return out


def _saison(d):
    m = dt.date.fromisoformat(d).month
    return 'janvier-février' if m <= 2 else ('mars-mai' if m <= 5 else ('juin-août' if m <= 8 else 'septembre-décembre'))


def case_du_match(famille, x):
    """Valeur de la case du chercheur pour ce match (None : inconnue)."""
    if famille == 'tous les matchs':
        return 'tous'
    if famille == 'format':
        return str(x['bo']) if x.get('bo') else None
    if famille == 'surface':
        return x.get('surface')
    if famille == 'saison':
        return _saison(x['debut'])
    if famille == 'tour':
        return TOURS.get(x['tour']) if x.get('tour') is not None else None
    return None


def pente_apprise(X):
    """Pente k qui minimise la log loss de σ(k·logit p) (Newton, bornée 0,3–3)."""
    k = 1.0
    for _ in range(50):
        g = h = 0.0
        for x in X:
            z = _lg(x['p'])
            q = _sg(k * z)
            g += (q - x['y']) * z
            h += q * (1 - q) * z * z
        if h <= 0:
            break
        pas = g / h
        k = min(3.0, max(0.3, k - pas))
        if abs(pas) < 1e-7:
            break
    return k


def controler(X, piste):
    a = float(piste['parametre'])
    d = [_ll(x['p'], x['y']) - _ll(_sg(a * _lg(x['p'])), x['y']) for x in X]
    n = len(d)
    out = {'matchs_direct': n}
    if n < 2:
        out['verdict'] = 'en attente'
        return out
    moy = sum(d) / n
    et = math.sqrt(sum((v - moy) ** 2 for v in d) / (n - 1) / n)
    k = pente_apprise(X)
    out.update({'log_loss_production': round(sum(_ll(x['p'], x['y']) for x in X) / n, 5),
                'log_loss_avec_candidate': round(sum(_ll(_sg(a * _lg(x['p'])), x['y']) for x in X) / n, 5),
                'gain': round(moy, 5), 'erreur_type': round(et, 5), 'pente_direct': round(k, 3),
                'favori_annonce_pct': round(100 * sum(max(x['p'], 1 - x['p']) for x in X) / n, 1),
                'favori_reel_pct': round(100 * sum((x['y'] == 1) == (x['p'] >= .5) for x in X) / n, 1)})
    if n < N_MIN:
        out['verdict'] = 'en attente'
    elif moy > 0 and (k - 1) * (a - 1) > 0:
        out['verdict'] = 'confirmée'
    else:
        out['verdict'] = 'non confirmée'
    return out


def en_service(racine, piste):
    try:
        import corrections_chercheur as CC
        act = CC.actives(racine)
    except Exception:  # noqa: BLE001
        act = []
    return piste['famille'] == 'surface' and any(v['circuit'] == piste['circuit'] and v['surface'] == piste['case']
                                                  for v in act)


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    try:
        with open(os.path.join(ICI, 'rapport_chercheur.json'), encoding='utf-8') as f:
            ch = json.load(f)
    except (OSError, ValueError):
        print('Rapport du chercheur introuvable : rien à contrôler.')
        return 0
    cand = [p for p in ch.get('pistes') or [] if p.get('candidate')]
    X = charger(racine)
    lignes = []
    for p in cand:
        L = {'famille': p['famille'], 'circuit': p['circuit'], 'case': p['case'], 'forme': p['forme'],
             'parametre': p['parametre']}
        if en_service(racine, p):
            L['verdict'] = 'déjà en service (suivie par sa règle de retrait)'
        elif p['forme'] != 'pente' or p['famille'] not in CONTROLABLES:
            L['verdict'] = 'non contrôlable automatiquement (à la main)'
        else:
            Y = [x for x in X if x['circuit'] == p['circuit'] and case_du_match(p['famille'], x) == p['case']]
            L.update(controler(Y, p))
        lignes.append(L)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), 'paquet': 350,
           'rapport_chercheur_du': ch.get('genere_le'),
           'regle': ("Pentes des familles tous / format / surface / saison / tour, contrôlées sur nos pronostics en direct "
                     "(dernier % figé avant le début, sans abandon ni forfait) ; en attente sous 200 matchs ; confirmée si "
                     "la log loss baisse avec la pente du chercheur et si la pente apprise sur le direct est du même côté "
                     "de 1 ; sinon non confirmée. Rien ne change dans les pronostics."),
           'matchs_direct': len(X), 'matchs_avec_tour': sum(1 for x in X if x.get('tour') is not None),
           'candidates': lignes}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"Pronostics en direct utilisables : {len(X)} (tour connu : {doc['matchs_avec_tour']}) · candidates : {len(lignes)}")
    for L in lignes:
        s = f"  {L['circuit']} · {L['famille']} · {L['case']} (pente {L['parametre']}) : {L['verdict']}"
        if 'gain' in L:
            s += (f" — {L['matchs_direct']} matchs, log loss {L['log_loss_production']} → {L['log_loss_avec_candidate']}"
                  f" (gain {L['gain']:+.4f} ± {L['erreur_type']:.4f}), pente sur le direct {L['pente_direct']}")
        print(s)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
