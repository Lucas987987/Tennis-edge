#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_recalage_service.py — le service annoncé est-il trop bas ? (22/11/2026, paquet 348, demande de Lucas)

CONSTAT (nos pronostics figés du 22/10 au 22/11/2026, par joueur et par match) : le % de points gagnés au service réel
dépasse l'annoncé d'environ 1 point sur les trois circuits, sur les deux quinzaines. Les « Points de vigilance »
le montraient déjà (points gagnés derrière la 1re et la 2e balle, % de jeux de service gagnés, points gagnés).
recalage_stats.py ne recale aujourd'hui que les aces, les doubles fautes, le % de 1res balles et les breaks.

CE QUI EST TESTÉ : un décalage AFFICHÉ, par circuit et par statistique, comme recalage_stats.py le fait déjà pour le
% de 1res balles (paquet 238). Il ne touche ni le % de victoire, ni la simulation, ni les lignes de jeux.
  • « service » : % de points gagnés au service (la probabilité de point de la production, a et b) ;
  • « jeux_service » : % de jeux de service gagnés de la feuille annoncée.
  δ = moyenne(réel − annoncé) × n / (n + 100) sur l'apprentissage.

RÈGLE FIXÉE AVANT DE REGARDER (22/11/2026), la même que celle des statistiques en salle (paquet 238) :
  • une ligne = un joueur dans un match (dernier pronostic figé avant le début, feuille réelle TennisApi) ;
  • APPRENTISSAGE : matchs commencés jusqu'au 22/11/2026 inclus ; JUGEMENT : SEULEMENT à partir du 23/11/2026 ;
  • RETENU pour une case (circuit × statistique) si, sur le jugement : au moins 1 000 cas, le biais moyen
    |réel − annoncé| baisse d'au moins moitié, l'écart moyen |réel − annoncé| ne monte pas, le décalage appris va
    dans le sens du biais jugé, et la baisse de l'écart est significative après correction de Holm sur les six cases
    (test apparié, unilatéral, 5 %) ; avant 1 000 cas : « pas encore jugeable », rien n'est conclu ;
  • rapport seulement : une case retenue entrera dans recalage_stats.py par un paquet à part (avec sa règle de retrait).
Sortie : simulateur/rapport_recalage_service.json (aucun nom, aucune cote). Usage : python simulateur/etude_recalage_service.py [racine]
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join(ICI, 'rapport_recalage_service.json')
CIRCUITS = ('ATP', 'WTA', 'CH')
STATS = ('service', 'jeux_service')
COUPURE = '2026-11-23'
PRIOR, N_MIN, ALPHA = 100.0, 1000, 0.05


def _lire_gz(p):
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError, EOFError):
        return None


def charger(racine):
    """[{circuit, debut, stat, annonce, reel}] — une ligne par joueur, match et statistique."""
    direct = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '2*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                d, debut = r.get('direct') or {}, r.get('debut_utc') or r.get('debut')
                if not d.get('a') or not d.get('b') or not debut:
                    continue
                if str(r.get('passage', '')) > str(debut).replace('+00:00', 'Z')[:19] + 'Z':
                    continue
                if r['uid'] not in direct or r['passage'] > direct[r['uid']][0]:
                    direct[r['uid']] = (r['passage'], d['a'], d['b'])
    fiches = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'fiches', '*.json.gz'))):
        for uid, x in (_lire_gz(f) or {}).items():
            fe = ((x or {}).get('dernier') or {}).get('feuille')
            if isinstance(fe, list) and len(fe) == 2:
                fiches[uid] = fe
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            res = json.load(f).get('matchs', [])
    except (OSError, ValueError):
        res = []
    out = []
    for m in res:
        re_ = m.get('reel') or {}
        fe = re_.get('feuille')
        if not (isinstance(fe, list) and len(fe) == 2) or re_.get('interrompu') or re_.get('score_invalide'):
            continue
        c, debut, uid = m.get('circuit'), str(m.get('debut') or '')[:10], m.get('uid')
        if c not in CIRCUITS or not debut:
            continue
        for i in (0, 1):
            v = fe[i] or {}
            try:
                srv = v['premiere_pct'] / 100 * v['gagnes_1re_pct'] + (1 - v['premiere_pct'] / 100) * v['gagnes_2e_pct']
            except (KeyError, TypeError):
                srv = None
            if uid in direct and srv is not None:
                out.append({'circuit': c, 'debut': debut, 'stat': 'service', 'annonce': 100 * direct[uid][1 + i], 'reel': srv})
            a = (fiches.get(uid) or [{}, {}])[i].get('jeux_service_gagnes_pct') if uid in fiches else None
            if a is not None and v.get('jeux_service_gagnes_pct') is not None:
                out.append({'circuit': c, 'debut': debut, 'stat': 'jeux_service', 'annonce': a, 'reel': v['jeux_service_gagnes_pct']})
    return out


def p_unilaterale(diffs):
    n = len(diffs)
    if n < 2:
        return 1.0
    m = sum(diffs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / (n - 1))
    if sd == 0:
        return 0.0 if m > 0 else 1.0
    return 0.5 * math.erfc(m / (sd / math.sqrt(n)) / math.sqrt(2))


def holm(pv, alpha=ALPHA):
    ordre, out, encore = sorted(pv, key=lambda k: pv[k]), {}, True
    for i, k in enumerate(ordre):
        encore = encore and pv[k] <= alpha / (len(ordre) - i)
        out[k] = encore
    return out


def etudier(R):
    cases, pv = {}, {}
    for c in CIRCUITS:
        for s in STATS:
            X = [r for r in R if r['circuit'] == c and r['stat'] == s]
            app = [r for r in X if r['debut'] < COUPURE]
            jug = [r for r in X if r['debut'] >= COUPURE]
            cle = f'{c}|{s}'
            if not app:
                cases[cle] = {'n_app': 0, 'n_jug': len(jug), 'retenu': False, 'raison': "aucun cas d'apprentissage"}
                continue
            b_app = sum(r['reel'] - r['annonce'] for r in app) / len(app)
            delta = b_app * len(app) / (len(app) + PRIOR)
            e = {'n_app': len(app), 'n_jug': len(jug), 'biais_app_pts': round(b_app, 3), 'decalage_pts': round(delta, 3)}
            if jug:
                b0 = sum(r['reel'] - r['annonce'] for r in jug) / len(jug)
                b1 = sum(r['reel'] - r['annonce'] - delta for r in jug) / len(jug)
                m0 = [abs(r['reel'] - r['annonce']) for r in jug]
                m1 = [abs(r['reel'] - r['annonce'] - delta) for r in jug]
                e.update({'biais_jug_sans': round(b0, 3), 'biais_jug_avec': round(b1, 3),
                          'ecart_jug_sans': round(sum(m0) / len(jug), 3), 'ecart_jug_avec': round(sum(m1) / len(jug), 3)})
                pv[cle] = p_unilaterale([a - b for a, b in zip(m0, m1)])
            cases[cle] = e
    sig = holm(pv) if pv else {}
    for cle, e in cases.items():
        if 'raison' in e:
            continue
        if e['n_jug'] < N_MIN:
            e['retenu'] = False
            e['raison'] = f"pas encore jugeable : {e['n_jug']} cas jugés sur {N_MIN} (rien n'est conclu)"
            continue
        raisons = []
        if abs(e['biais_jug_avec']) > abs(e['biais_jug_sans']) / 2:
            raisons.append("le biais ne baisse pas de moitié")
        if e['ecart_jug_avec'] > e['ecart_jug_sans']:
            raisons.append("l'écart moyen monte")
        if e['decalage_pts'] * e['biais_jug_sans'] <= 0:
            raisons.append('décalage dans le mauvais sens')
        if not sig.get(cle):
            raisons.append('non significatif après Holm')
        e['retenu'] = not raisons
        e['raison'] = 'RETENU' if not raisons else ' ; '.join(raisons)
    return cases


def main(argv):
    racine = argv[0] if argv else os.path.join(ICI, '..')
    R = charger(racine)
    rapport = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'regle': "décalage affiché par circuit et statistique, appris jusqu'au 22/11/2026, jugé seulement à partir "
                        "du 23/11/2026 : ≥ 1 000 cas, biais divisé au moins par deux, écart moyen qui ne monte pas, bon "
                        "sens, Holm sur 6 cases ; rapport seulement",
               'cas': len(R), 'cases': etudier(R)}
    for cle, e in rapport['cases'].items():
        print(f"{cle}: apprentissage {e.get('n_app')} (biais {e.get('biais_app_pts')} pt) · jugés {e.get('n_jug')} → "
              f"{e.get('raison')}")
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
