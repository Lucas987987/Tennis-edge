#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest.py — le simulateur bat-il la clôture Pinnacle ? (21/10/2026)

Protocole, fixé AVANT de voir les résultats :
  * POINT-IN-TIME : chaque lundi, notes recalculées avec les seuls tournois
    terminés avant ce lundi ; elles servent pour les matchs de la semaine.
  * RÉGLAGE sur 2023 seulement (demi-vie × prior, 4 combinaisons, critère :
    log loss de la victoire) ; JUGEMENT sur 2024 → fin des données, jamais vu
    pendant le réglage.
  * Référence : clôture Pinnacle de tennis-data, marge retirée (méthode
    puissance du Lab). Matchs ATP / WTA principaux (tennis-data ne couvre pas
    les Challengers).

Trois versions du modèle :
  pur    : statistiques seules (service / retour) ;
  ancré  : niveau pris à Pinnacle, profil service/retour pris aux statistiques ;
  marché : niveau pris à Pinnacle, deux joueurs au profil moyen (sans statistiques).
L'écart « ancré » contre « marché » mesure ce que les statistiques AJOUTENT au
marché sur les sets et les jeux — le seul usage réaliste si « pur » ne bat pas
Pinnacle sur la victoire.

Usage : python simulateur/backtest.py DOSSIER_SACKMANN [historique/tennis_data.csv.gz]
Sorties : simulateur/rapport_backtest.json, simulateur/notes_joueurs.json
"""
import collections
import datetime as dt
import importlib.util
import json
import math
import os
import random
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees  # noqa: E402
import modele  # noqa: E402
import notes as N  # noqa: E402

_spec = importlib.util.spec_from_file_location('tennis_edge_sim_books', os.path.join(ICI, '..', 'Tennis_Edge_Lab', 'books.py'))
books = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(books)

GRILLE = [(250, 150), (250, 500), (500, 150), (500, 500)]   # (demi-vie jours, prior points)
DEBUT_REGLAGE, DEBUT_TEST = dt.date(2023, 1, 1), dt.date(2024, 1, 1)
N_MIN = 200            # points de service pondérés minimum pour chacun des deux joueurs
SEUILS_PARI = (0.0, 0.03, 0.05, 0.10)


def lundi(d):
    return d - dt.timedelta(days=d.weekday())


def juste(psw, psl):
    """Probabilité juste du vainqueur (puissance), repli proportionnel."""
    k = books.power_exponent(psw, psl)
    if k is None:
        a, b = 1 / psw, 1 / psl
        return a / (a + b)
    return (1 / psw) ** k


def ll(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)


def par_semaine(paires):
    s = collections.defaultdict(list)
    for t, m in paires:
        s[lundi(t['date'])].append((t, m))
    return sorted(s.items())


def predire(paires, demi_vie, n0, rappel):
    """Itère les semaines, note au lundi, appelle rappel(notes, td, sackmann)."""
    prec = None
    for i, (lu, lot) in enumerate(par_semaine(paires)):
        notes = N.noter(MATCHS, lu, demi_vie, n0, depart=prec, tours=3 if prec else 8)
        prec = notes
        for t, m in lot:
            rappel(notes, t, m)


def orienter(t, m):
    """A = identifiant le plus petit (orientation neutre). Renvoie (A, B, y, cote A, cote B, p Pinnacle A)."""
    a, b = sorted((m['gagnant'], m['perdant']))
    y = int(a == m['gagnant'])
    pw = juste(t['psw'], t['psl'])
    return a, b, y, (t['psw'] if y else t['psl']), (t['psl'] if y else t['psw']), (pw if y else 1 - pw)


def bootstrap_jours(items, B=2000, graine=7):
    """items : [(jour, valeur)] -> IC95 de la moyenne, rééchantillonnage par jour."""
    g = collections.defaultdict(list)
    for j, v in items:
        g[j].append(v)
    jours = list(g)
    if len(jours) < 5:
        return None
    rnd = random.Random(graine)
    res = []
    for _ in range(B):
        xs = [x for j in rnd.choices(jours, k=len(jours)) for x in g[j]]
        res.append(sum(xs) / len(xs))
    res.sort()
    return [round(res[int(0.025 * B)], 4), round(res[int(0.975 * B)], 4)]


def reglage(paires):
    out = []
    for dv, n0 in GRILLE:
        acc = []

        def cb(notes, t, m):
            a, b, y, *_ = orienter(t, m)
            if notes.points(a) < N_MIN or notes.points(b) < N_MIN:
                return
            pa = notes.p_service(a, b, m['circuit'], m['surface'])
            pb = notes.p_service(b, a, m['circuit'], m['surface'])
            acc.append(ll(modele.match(pa, pb, 3 if m['bo'] == 5 else 2)['victoire'], y))
        t0 = time.time()
        predire(paires, dv, n0, cb)
        out.append({'demi_vie_jours': dv, 'prior_points': n0, 'n': len(acc),
                    'log_loss': round(sum(acc) / len(acc), 5) if acc else None, 'secondes': round(time.time() - t0)})
        print(f"  réglage demi-vie {dv} j · prior {n0} pts : n={len(acc)} log loss {out[-1]['log_loss']}", flush=True)
    meilleur = min((o for o in out if o['log_loss'] is not None), key=lambda o: o['log_loss'])
    return out, (meilleur['demi_vie_jours'], meilleur['prior_points'])


def reel(m, a):
    """Issues réelles du point de vue de A (match complet seulement)."""
    if not m['complet'] or not m['sets']:
        return None
    sets = m['sets'] if a == m['gagnant'] else [(y, x) for x, y in m['sets']]
    sa, sb = sum(x > y for x, y in sets), sum(y > x for x, y in sets)
    return {'set1': int(sets[0][0] > sets[0][1]), 'total': sum(x + y for x, y in sets),
            'sets': f"{sa}-{sb}", 'tiebreak': int(any(max(x, y) == 7 and min(x, y) == 6 for x, y in sets))}


def test(paires, demi_vie, n0):
    L = []

    def cb(notes, t, m):
        a, b, y, cote_a, cote_b, p_pin = orienter(t, m)
        if notes.points(a) < N_MIN or notes.points(b) < N_MIN:
            L.append(None)
            return
        sg = 3 if m['bo'] == 5 else 2
        pa = notes.p_service(a, b, m['circuit'], m['surface'])
        pb = notes.p_service(b, a, m['circuit'], m['surface'])
        r_pur = modele.match(pa, pb, sg)
        x, z = modele.ancrer(pa, pb, p_pin, sg)
        r_anc = modele.match(x, z, sg)
        base = 1 / (1 + math.exp(-notes.mu_de(m['circuit'], m['surface'])))
        x0, z0 = modele.ancrer(base, base, p_pin, sg)
        r_mar = modele.match(x0, z0, sg)
        L.append({'jour': t['date'].isoformat(), 'circuit': m['circuit'], 'bo': m['bo'], 'y': y,
                  'p_pur': r_pur['victoire'], 'p_pin': p_pin, 'cote_a': cote_a, 'cote_b': cote_b,
                  'reel': reel(m, a), 'pur': r_pur, 'anc': r_anc, 'mar': r_mar})
    predire(paires, demi_vie, n0, cb)
    return L


def resume(L):
    ok = [x for x in L if x]
    out = {'matchs_notes': len(ok), 'matchs_sans_note': len(L) - len(ok)}
    if not ok:
        return out
    # --- victoire : log loss, Brier
    def blend(x):
        return modele.sigmoide((modele.logit(min(max(x['p_pur'], 1e-4), 1 - 1e-4)) +
                                modele.logit(min(max(x['p_pin'], 1e-4), 1 - 1e-4))) / 2)
    vic = {}
    for nom, f in (('modele_pur', lambda x: x['p_pur']), ('pinnacle', lambda x: x['p_pin']), ('moyenne_50_50', blend)):
        vic[nom] = {'log_loss': round(sum(ll(f(x), x['y']) for x in ok) / len(ok), 5),
                    'brier': round(sum((f(x) - x['y']) ** 2 for x in ok) / len(ok), 5)}
    # différence de log loss par jour (IC) : modèle − Pinnacle
    vic['ecart_log_loss_modele_moins_pinnacle'] = {
        'moyenne': round(sum(ll(x['p_pur'], x['y']) - ll(x['p_pin'], x['y']) for x in ok) / len(ok), 5),
        'ic95': bootstrap_jours([(x['jour'], ll(x['p_pur'], x['y']) - ll(x['p_pin'], x['y'])) for x in ok])}
    out['victoire'] = vic
    # --- calibration du modèle pur
    cal = []
    for lo in [i / 10 for i in range(10)]:
        g = [x for x in ok if lo <= x['p_pur'] < lo + 0.1 or (lo == 0.9 and x['p_pur'] == 1)]
        if len(g) >= 30:
            cal.append({'tranche': f"{int(lo * 100)}–{int(lo * 100 + 10)} %", 'n': len(g),
                        'prevu': round(100 * sum(x['p_pur'] for x in g) / len(g), 1),
                        'realise': round(100 * sum(x['y'] for x in g) / len(g), 1),
                        'pinnacle': round(100 * sum(x['p_pin'] for x in g) / len(g), 1)})
    out['calibration_modele_pur'] = cal
    # --- paris à la cote de clôture Pinnacle quand le modèle voit de la valeur
    paris = []
    for s in SEUILS_PARI:
        items = []
        for x in ok:
            for p, cote, gagne in ((x['p_pur'], x['cote_a'], x['y']), (1 - x['p_pur'], x['cote_b'], 1 - x['y'])):
                if p * cote - 1 > s:
                    items.append((x['jour'], (cote - 1) if gagne else -1.0))
        if items:
            paris.append({'seuil_valeur': f"> {int(s * 100)} %", 'n': len(items),
                          'roi_pct': round(100 * sum(v for _, v in items) / len(items), 2),
                          'ic95_pct': [round(100 * v, 2) for v in (bootstrap_jours(items) or [])] or None})
    out['paris_cloture_pinnacle'] = paris
    # --- sets et jeux : ce que les statistiques ajoutent au marché
    comp = [x for x in ok if x['reel']]
    sj = {'matchs_complets': len(comp)}
    for nom in ('pur', 'anc', 'mar'):
        r = {}
        r['set1_log_loss'] = round(sum(ll(x[nom]['set1'], x['reel']['set1']) for x in comp) / len(comp), 5)
        lt = [-math.log(max(x[nom]['total_jeux'].get(x['reel']['total'], 0.0), 1e-6)) for x in comp]
        r['total_jeux_log_score'] = round(sum(lt) / len(lt), 4)
        r['total_jeux_erreur_moyenne'] = round(sum(modele.moyenne(x[nom]['total_jeux']) - x['reel']['total'] for x in comp) / len(comp), 3)
        r['total_jeux_erreur_absolue'] = round(sum(abs(modele.moyenne(x[nom]['total_jeux']) - x['reel']['total']) for x in comp) / len(comp), 3)
        r['tiebreak_log_loss'] = round(sum(ll(x[nom]['tiebreak'], x['reel']['tiebreak']) for x in comp) / len(comp), 5)
        r['score_sets_log_score'] = round(sum(-math.log(max(x[nom]['sets'].get(x['reel']['sets'], 0.0), 1e-6)) for x in comp) / len(comp), 4)
        sj[{'pur': 'modele_pur', 'anc': 'modele_ancre_pinnacle', 'mar': 'marche_seul'}[nom]] = r
    # IC de l'apport des statistiques sur le total de jeux (ancré − marché, par jour)
    d = [(x['jour'], -math.log(max(x['anc']['total_jeux'].get(x['reel']['total'], 0.0), 1e-6))
          + math.log(max(x['mar']['total_jeux'].get(x['reel']['total'], 0.0), 1e-6))) for x in comp]
    sj['apport_stats_total_jeux'] = {'ecart_log_score_ancre_moins_marche': round(sum(v for _, v in d) / len(d), 5),
                                     'ic95': bootstrap_jours(d), 'lecture': 'négatif = les statistiques améliorent la prévision du total de jeux'}
    d1 = [(x['jour'], ll(x['anc']['set1'], x['reel']['set1']) - ll(x['mar']['set1'], x['reel']['set1'])) for x in comp]
    sj['apport_stats_set1'] = {'ecart_log_loss_ancre_moins_marche': round(sum(v for _, v in d1) / len(d1), 5),
                               'ic95': bootstrap_jours(d1), 'lecture': 'négatif = les statistiques améliorent la prévision du set 1'}
    out['sets_et_jeux'] = sj
    return out


def couverture(matchs):
    c = collections.defaultdict(lambda: {'matchs': 0, 'avec_stats': 0, 'dernier': None})
    for m in matchs:
        k = f"{m['circuit']} {m['date'].year}"
        c[k]['matchs'] += 1
        c[k]['avec_stats'] += bool(m['stats'])
        c[k]['dernier'] = max(c[k]['dernier'] or '', m['date'].isoformat())
    return dict(sorted(c.items()))


def exporter_notes(matchs, demi_vie, n0, chemin):
    date = max(m['fin'] for m in matchs) + dt.timedelta(days=1)
    nt = N.noter(matchs, date, demi_vie, n0)
    noms = {}
    for m in matchs:
        noms[m['gagnant']], noms[m['perdant']] = m['nom_g'], m['nom_p']
    j = {p: {'nom': noms.get(p, p), 'service': round(nt.S.get(p, 0.0), 4), 'retour': round(nt.R.get(p, 0.0), 4),
             'points': round(nt.pts.get(p, 0.0))} for p in nt.pts if nt.pts.get(p, 0) >= N_MIN}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'donnees_jusqu_au': (date - dt.timedelta(days=1)).isoformat(), 'demi_vie_jours': demi_vie, 'prior_points': n0,
           'mu': {f"{c} {s}": round(v, 4) for (c, s), v in sorted(nt.mu.items())},
           'formule': 'logit P(A gagne le point sur son service contre B) = mu[circuit surface] + service_A − retour_B',
           'source': 'archive des CSV de Jeff Sackmann (CC BY-NC-SA 4.0)', 'joueurs': j}
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=0)
    return len(j)


def main(argv):
    global MATCHS
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    td_chemin = argv[2] if len(argv) > 2 else os.path.join(ICI, '..', 'historique', 'tennis_data.csv.gz')
    t0 = time.time()
    MATCHS = donnees.charger(dossier, 2018)
    print(f"Sackmann : {len(MATCHS)} matchs ({sum(bool(m['stats']) for m in MATCHS)} avec statistiques)", flush=True)
    if not MATCHS:
        print(f"::error::aucun fichier de matchs Sackmann sous {dossier}")
        return 1
    td = donnees.charger_td(td_chemin, DEBUT_REGLAGE.isoformat())
    paires = donnees.joindre(td, MATCHS)
    print(f"tennis-data depuis {DEBUT_REGLAGE} : {len(td)} matchs, {len(paires)} joints à Sackmann", flush=True)
    reg = [p for p in paires if p[0]['date'] < DEBUT_TEST]
    tst = [p for p in paires if p[0]['date'] >= DEBUT_TEST]
    grille, (dv, n0) = reglage(reg)
    print(f"retenu : demi-vie {dv} j, prior {n0} pts — test sur {len(tst)} matchs", flush=True)
    L = test(tst, dv, n0)
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'protocole': {'reglage': f"{DEBUT_REGLAGE} → {DEBUT_TEST - dt.timedelta(days=1)}",
                         'test': f"{DEBUT_TEST} → fin des données", 'point_in_time': 'notes au lundi, tournois terminés avant',
                         'reference': 'clôture Pinnacle tennis-data, marge retirée (puissance)', 'n_min_points': N_MIN},
           'couverture_sackmann': couverture(MATCHS),
           'jointure_tennis_data': {'matchs_td': len(td), 'joints': len(paires), 'reglage': len(reg), 'test': len(tst)},
           'reglage': grille, 'retenu': {'demi_vie_jours': dv, 'prior_points': n0},
           'test': resume(L)}
    rap['test']['par_circuit'] = {c: resume([x for x in L if x and x['circuit'] == c]).get('victoire') for c in ('ATP', 'WTA')}
    rap['notes_exportees'] = exporter_notes(MATCHS, dv, n0, os.path.join(ICI, 'notes_joueurs.json'))
    rap['duree_s'] = round(time.time() - t0)
    with open(os.path.join(ICI, 'rapport_backtest.json'), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    v = rap['test'].get('victoire', {})
    print(json.dumps({'victoire': v, 'paris': rap['test'].get('paris_cloture_pinnacle'),
                      'sets_et_jeux': rap['test'].get('sets_et_jeux')}, ensure_ascii=False, indent=1))
    return 0


MATCHS = []
if __name__ == '__main__':
    sys.exit(main(sys.argv))
