#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_ancrage.py — l'ancrage déforme-t-il le nombre de jeux ? (22/11/2026, paquet 342, demande de Lucas : régler le
problème des jeux en Challenger, sur tous les circuits).

CONSTAT : la simulation pure (taux service / retour des deux joueurs) prévoit trop de jeux (Challenger : +1,9 jeu sur
1 111 matchs du 22/10 au 22/11) ; une fois ANCRÉE sur le % affiché, elle en prévoit un peu trop peu (−0,3), surtout
quand le favori est très net (−1,4 jeu au-dessus de 90 %). L'ancrage (match_simule.ancrer_rapide) écarte les deux
joueurs (+d au serveur A, −d au serveur B, en logit) jusqu'à retrouver le % : la SOMME des deux niveaux au service ne
bouge pas. Si le % affiché est plus tranché que la simulation, l'écart grandit, les sets deviennent plus déséquilibrés,
le match plus court. Question : faut-il, quand l'écart est grand, relever un peu le service des DEUX joueurs ?

DONNÉES : la production elle-même, rien de reconstruit. Pour chaque match, le dernier pronostic figé avant le début
(simulateur/journal_pronostics) donne les deux probabilités de point au service ancrées (« direct » : a, b), la forme
du jour σ et le format ; la distribution des jeux de la production s'en déduit EXACTEMENT (modele.match_forme, vérifié
au paquet 342 : même % de victoire, même nombre moyen de jeux). Résultats : Tennis_Edge_Lab/live/pronostics_resultats.json.

DEUX VARIANTES, chacune jugée à part : avant le réancrage, les deux logits reçoivent
  • ÉCART : + κ · |logit(a) − logit(b)| (plus l'ancrage écarte les joueurs, plus les deux servent mieux) ;
  • NIVEAU : + δ, le même pour tous les matchs (sur nos pronostics du 22/10 au 22/11, le % de points gagnés au service
    réel dépasse le prévu d'environ 1 point sur les trois circuits, alors que l'écart de jeux change de signe d'une
    quinzaine à l'autre en Challenger : +0,2 jeu avant le 08/11, −0,7 après) ;
puis réancrage sur le MÊME % (le % de victoire ne change jamais, ni la log loss du vainqueur). κ = δ = 0 : la
production actuelle.
22/11/2026 (paquet 344, Lucas : « fais-le ») — TROISIÈME VARIANTE, enregistrée à part et après le paquet 343 (en salle,
les serveurs gagnent environ 1 point de plus que prévu ; la log loss par point ne pouvait pas le retenir) :
  • SALLE : + δs sur les deux logits si le match se joue en salle (type de court de la feuille TennisApi du tournoi,
    connu avant le match), rien en plein air ; grille δs = 0 · 0,05 · 0,1 · 0,15 · 0,2 · 0,3 ;
  • APPRENTISSAGE : nos pronostics jusqu'au 22/11/2026 inclus ; JUGEMENT : SEULEMENT les matchs à partir du
    23/11/2026 (jamais vus au moment d'écrire cette règle) ; matchs dont on ne sait pas s'ils sont en salle écartés ;
  • même mesure (lignes « plus de L jeux »), mêmes seuils (≥ 1 000 matchs jugés dont ≥ 300 en salle, gain ≥ 0,001,
    même sens, service pas dégradé de plus de 1 %), correction de Holm sur ses trois circuits, à part des six cases
    du paquet 342 (qui gardent leur règle).

RÈGLE FIXÉE AVANT DE REGARDER (22/11/2026) :
  • population : matchs au meilleur des 3 sets, terminés (ni abandon ni score invalide), pronostic figé avant le début ;
  • circuit par circuit (ATP, WTA, Challenger) ; grilles κ = −0,2 · −0,1 · −0,05 · 0 · 0,05 · 0,1 · 0,2 · 0,3 · 0,4 et
    δ (logit) = −0,1 · −0,05 · 0 · 0,05 · 0,1 · 0,15 · 0,2 ;
  • mesure : log loss moyenne des six lignes « plus de L jeux », L = 18,5 … 23,5 ;
  • APPRENTISSAGE : matchs commencés avant le 08/11/2026 (κ choisi là) ; JUGEMENT : à partir du 08/11/2026, une
    seule fois par circuit quand il y a ≥ 1 000 matchs jugés (avant : « pas encore jugeable », rien n'est conclu) ;
  • RETENU pour une case (circuit × variante) si, sur le jugement : gain ≥ 0,001 par rapport à la production, gain du
    même sens sur l'apprentissage, écart moyen |prévu − réel| du % de points au service pas plus de 1 % au-dessus de la
    production (matchs avec feuille), significatif après correction de Holm sur les six cases (test apparié par match,
    unilatéral) ;
  • ce script n'écrit qu'un rapport : rien ne change dans les pronostics sans un paquet à part.
DIAGNOSTIC (ne décide rien) : jeux prévus − réels par tranche de % du favori, à κ = 0 et au κ appris.
Sortie : simulateur/rapport_ancrage.json (aucun nom, aucune cote). Usage : python simulateur/etude_ancrage.py [racine]
"""
import datetime as dt
import glob
import gzip
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import match_simule as S  # noqa: E402
import modele as MM  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_ancrage.json')
CIRCUITS = ('ATP', 'WTA', 'CH')
GRILLES = {'ECART': (-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2, 0.3, 0.4), 'NIVEAU': (-0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2),
           'SALLE': (0.0, 0.05, 0.1, 0.15, 0.2, 0.3)}
LIGNES = (18.5, 19.5, 20.5, 21.5, 22.5, 23.5)
COUPURE = '2026-11-08'
COUPURES = {'ECART': COUPURE, 'NIVEAU': COUPURE, 'SALLE': '2026-11-23'}
N_SALLE_MIN = 300
GAIN_MIN, N_MIN, TOL_MAE, ALPHA = 0.001, 1000, 1.01, 0.05
TRANCHES = ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


def charger(racine):
    """[{circuit, debut, p, a, b, sigma, sg, tb, total, service}] — un par match, dernier pronostic d'avant le début."""
    derniers = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', '2*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for l in fh:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                d, c = r.get('direct') or {}, r.get('combinaison') or {}
                debut = r.get('debut_utc') or r.get('debut')
                if not d.get('a') or not d.get('b') or c.get('p_home') is None or not debut:
                    continue
                if str(r.get('passage', '')) > str(debut).replace('+00:00', 'Z')[:19] + 'Z':
                    continue
                if r['uid'] not in derniers or r['passage'] > derniers[r['uid']]['passage']:
                    derniers[r['uid']] = {'uid': r['uid'], 'home': r.get('home'), 'away': r.get('away'), 'passage': r['passage'], 'circuit': r.get('circuit'), 'debut': str(debut)[:10],
                                          'p': c['p_home'], 'a': d['a'], 'b': d['b'], 'sigma': d.get('sigma') or 0.0,
                                          'sg': d.get('sets_gagnants') or 2, 'tb': d.get('tb_final'),
                                          'bo': r.get('meilleur_des'), 'salle_journal': r.get('en_salle')}
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            res = {m['uid']: m for m in json.load(f).get('matchs', [])}
    except (OSError, ValueError):
        res = {}
    salles = salles_des_feuilles(racine)
    out = []
    for uid, x in derniers.items():
        m = res.get(uid) or {}
        re_ = m.get('reel') or {}
        if x['bo'] != 3 or x['sg'] != 2 or not re_.get('jeux') or re_.get('interrompu') or re_.get('score_invalide'):
            continue
        x['total'] = re_['jeux']
        x['salle'] = x['salle_journal'] if x.get('salle_journal') is not None else salle_du_match(salles, x)
        x['service'] = None
        fe = re_.get('feuille')
        if isinstance(fe, list) and len(fe) == 2 and all(isinstance(v, dict) for v in fe):
            try:
                x['service'] = [v['premiere_pct'] / 100 * v['gagnes_1re_pct'] + (1 - v['premiere_pct'] / 100) * v['gagnes_2e_pct']
                                for v in fe]
            except (KeyError, TypeError):
                x['service'] = None
        out.append(x)
    return out


def _cle_nom(n):
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(n or '')).encode('ascii', 'ignore').decode().lower()
                   if ch.isalpha())


def salles_des_feuilles(racine):
    """{(jour, frozenset(noms)): True / False} — type de court de la feuille TennisApi du match (« … indoor » : salle).
    Le type de court est une propriété du tournoi, connue avant le match : pas une information d'après coup."""
    out = {}
    for f in glob.glob(os.path.join(racine, 'feuilles', '2*.jsonl.gz')):
        try:
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                for l in fh:
                    r = json.loads(l)
                    sb = str(r.get('surface') or '').lower()
                    h, a = (r.get('home') or {}).get('nom'), (r.get('away') or {}).get('nom')
                    if sb and h and a and r.get('jour'):
                        out[(r['jour'], frozenset((_cle_nom(h), _cle_nom(a))))] = 'indoor' in sb
        except (OSError, ValueError, EOFError):
            continue
    return out


def salle_du_match(salles, x):
    k = frozenset((_cle_nom(x.get('home')), _cle_nom(x.get('away'))))
    j = dt.date.fromisoformat(x['debut'])
    for d in (j, j - dt.timedelta(days=1), j + dt.timedelta(days=1)):
        v = salles.get((d.isoformat(), k))
        if v is not None:
            return v
    return None


def variante(x, kappa, delta=0.0, salle=0.0):
    """(distribution des jeux, a, b) après + δ + κ·|écart| (+ δs si en salle) sur les deux logits, réancrage sur le
    même %."""
    a, b = x['a'], x['b']
    ds = salle if x.get('salle') else 0.0
    if kappa or delta or ds:
        la, lb = _lg(a), _lg(b)
        c = delta + ds + kappa * abs(la - lb)
        a, b = S.ancrer_rapide(_sg(la + c), _sg(lb + c), x['p'], x['sg'], x['sigma'])
    o = MM.match_forme(a, b, x['sg'], x['sigma'], x['tb'])
    return o['total_jeux'], a, b


def log_loss_lignes(dist, total):
    tot = sum(dist.values()) or 1.0
    ll = 0.0
    for L in LIGNES:
        p = min(max(sum(v for k, v in dist.items() if k > L) / tot, 1e-6), 1 - 1e-6)
        ll -= math.log(p if total > L else 1 - p)
    return ll / len(LIGNES)


def mesurer(X, kappa, delta=0.0, salle=0.0):
    """Par match : (log loss des lignes, jeux prévus, écart |prévu − réel| du service en points ou None)."""
    out = []
    for x in X:
        dist, a, b = variante(x, kappa, delta, salle)
        tot = sum(dist.values()) or 1.0
        mae = None
        if x['service']:
            mae = (abs(100 * a - x['service'][0]) + abs(100 * b - x['service'][1])) / 2
        out.append((log_loss_lignes(dist, x['total']), sum(k * v for k, v in dist.items()) / tot, mae))
    return out


def p_unilaterale(diffs):
    n = len(diffs)
    if n < 2:
        return 1.0
    m = sum(diffs) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in diffs) / (n - 1))
    if sd == 0:
        return 0.0 if m > 0 else 1.0
    return 0.5 * math.erfc(m / (sd / math.sqrt(n)) / math.sqrt(2))


def holm(pv, alpha=ALPHA):
    ordre, out, encore = sorted(pv, key=lambda k: pv[k]), {}, True
    for i, k in enumerate(ordre):
        encore = encore and pv[k] <= alpha / (len(ordre) - i)
        out[k] = encore
    return out


def tranches(X, mes):
    out = {}
    for lo, hi in TRANCHES:
        I = [i for i, x in enumerate(X) if lo <= max(x['p'], 1 - x['p']) < hi]
        if I:
            out[f'{int(lo * 100)}-{min(100, int(hi * 100))}'] = {
                'n': len(I), 'jeux_prevus_moins_reels': round(sum(mes[i][1] - X[i]['total'] for i in I) / len(I), 2)}
    return out


def _mes(X, famille, v):
    return mesurer(X, v) if famille == 'ECART' else mesurer(X, 0.0, v) if famille == 'NIVEAU' else mesurer(X, 0.0, 0.0, v)


def etudier(X):
    rapport, pv, brut = {'cases': {}}, {}, {}
    for c in CIRCUITS:
        cache = {}
        for fam, grille in GRILLES.items():
            cle = f'{c}|{fam}'
            cut = COUPURES[fam]
            pop = [x for x in X if x['circuit'] == c and (fam != 'SALLE' or x.get('salle') is not None)]
            app = [x for x in pop if x['debut'] < cut]
            jug = [x for x in pop if x['debut'] >= cut]
            if (cut, fam == 'SALLE') not in cache:
                cache[(cut, fam == 'SALLE')] = (mesurer(app, 0.0) if app else [], mesurer(jug, 0.0) if jug else [])
            M_app0, M_jug0 = cache[(cut, fam == 'SALLE')]
            if not app:
                rapport['cases'][cle] = {'n_app': 0, 'n_jug': len(jug), 'retenu': False, 'raison': "aucun match d'apprentissage"}
                continue
            M_app = {v: (M_app0 if v == 0.0 else _mes(app, fam, v)) for v in grille}
            ll_app = {v: sum(r[0] for r in M_app[v]) / len(app) for v in grille}
            par = min(grille, key=lambda v: ll_app[v])
            Mk = (M_jug0 if par == 0.0 else _mes(jug, fam, par)) if jug else []
            dif = [a[0] - b[0] for a, b in zip(M_jug0, Mk)]
            maes = [(a[2], b[2]) for a, b in zip(M_jug0, Mk) if a[2] is not None]
            ref, R0, Rk = (jug, M_jug0, Mk) if jug else (app, M_app0, M_app[par])
            e = {'n_app': len(app), 'n_jug': len(jug), 'parametre_appris': par,
                 **({'n_jug_salle': sum(1 for x in jug if x.get('salle'))} if fam == 'SALLE' else {}),
                 'log_loss_app': {str(k): round(v, 5) for k, v in ll_app.items()},
                 'gain_app': round(ll_app[0.0] - ll_app[par], 5),
                 'gain_jug': round(sum(dif) / len(dif), 5) if dif else None,
                 'mae_service_jug': ({'production': round(sum(a for a, _ in maes) / len(maes), 3),
                                      'appris': round(sum(b for _, b in maes) / len(maes), 3), 'n': len(maes)} if maes else None),
                 'jeux_par_tranche': {'production': tranches(ref, R0), 'appris': tranches(ref, Rk)},
                 'jeux_moyens': {'reels': round(sum(x['total'] for x in ref) / len(ref), 2),
                                 'production': round(sum(v[1] for v in R0) / len(ref), 2),
                                 'appris': round(sum(v[1] for v in Rk) / len(ref), 2)}}
            pv[cle] = p_unilaterale(dif) if par != 0.0 and dif else 1.0
            brut[cle] = e
            rapport['cases'][cle] = e
    # Holm : les six cases du paquet 342 ensemble, les trois cases SALLE (paquet 344) à part
    sig = {}
    for groupe in (('ECART', 'NIVEAU'), ('SALLE',)):
        sous = {k: v for k, v in pv.items() if k.split('|')[1] in groupe}
        sig.update(holm(sous) if sous else {})
    for cle, e in brut.items():
        raisons = []
        if e['n_jug'] < N_MIN or ('n_jug_salle' in e and e['n_jug_salle'] < N_SALLE_MIN):
            e['retenu'] = False
            e['raison'] = (f"pas encore jugeable : {e['n_jug']} matchs jugés sur {N_MIN}"
                           + (f", dont {e['n_jug_salle']} en salle sur {N_SALLE_MIN}" if 'n_jug_salle' in e else '')
                           + " (rien n'est conclu)")
            continue
        if e['parametre_appris'] == 0.0:
            raisons.append("l'apprentissage garde la production actuelle")
        if e['gain_jug'] is None or e['gain_jug'] < GAIN_MIN:
            raisons.append(f"gain jugé {e['gain_jug']} < {GAIN_MIN}")
        if e['gain_app'] <= 0 or (e['gain_jug'] or 0) <= 0:
            raisons.append('pas le même sens sur les deux périodes')
        ms = e['mae_service_jug']
        if ms and ms['appris'] > ms['production'] * TOL_MAE:
            raisons.append('écart du % de points au service dégradé')
        if not sig.get(cle):
            raisons.append('non significatif après Holm')
        e['retenu'] = not raisons
        e['raison'] = 'RETENU' if not raisons else ' ; '.join(raisons)
    return rapport


def main(argv):
    racine = argv[0] if argv else os.path.join(ICI, '..')
    t0 = time.time()
    X = charger(racine)
    rapport = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'regle': "δ + κ·|écart| ajouté au service des deux joueurs puis réancrage sur le même % (deux variantes "
                        "jugées à part) ; appris avant le 08/11/2026, jugé ensuite une fois ≥ 1 000 matchs par circuit ; "
                        "retenu si gain ≥ 0,001 (lignes « plus de L jeux »), même sens, service pas dégradé de plus de "
                        "1 %, Holm sur les 6 cases ; rapport seulement",
               'matchs': len(X)}
    rapport.update(etudier(X))
    rapport['duree_s'] = round(time.time() - t0)
    for c, e in rapport['cases'].items():
        print(f"{c}: apprentissage {e.get('n_app')} · jugés {e.get('n_jug')} · appris {e.get('parametre_appris')} · "
              f"gain app {e.get('gain_app')} · jug {e.get('gain_jug')} · jeux {e.get('jeux_moyens')} → {e.get('raison')}")
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
