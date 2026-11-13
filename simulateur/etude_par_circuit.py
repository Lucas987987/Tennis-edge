#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_par_circuit.py — ce qui est encore COMMUN aux circuits mérite-t-il un réglage propre à chacun ? (13/11/2026,
paquet 255, demande de Lucas : « chaque circuit est différent ; ce qui est vrai chez l'un ne l'est pas forcément chez
l'autre »)

INVENTAIRE (relu le 13/11/2026) — ce qui est déjà propre à chaque circuit : pentes du format et des Grands Chelems,
signaux combinés et réappris, fantômes, forme du jour σ, amplification des profils, recalage des statistiques, poids
propres du mélange (jugés chaque lundi), arbres et corrections de situation (circuits_regles), groupes de facteurs
(jugés aussi par circuit), départ ITF, réévaluation du % en direct, garde-fou de la forme des scores (paquet 254).
Ce qui reste COMMUN et qui est jugé ici :
  A. les deux réglages de l'Elo qui n'agissent qu'au moment du pronostic (le classement lui-même reste commun : les
     joueurs passent d'un circuit à l'autre) : poids de la surface dans la note (0,3) et prudence pour les joueurs peu
     vus (« incertitude », 5) ;
  B. les poids du mélange Elo + simulation appris sur l'archive (0,78 / 0,24, communs à l'ATP et à la WTA) ;
  C. le modèle complet des facteurs (arbres) : ses données ne sont que dans le flux du lundi ; il y est mis en FANTÔME
     par circuit (facteurs.py), jugé avec la règle cumulée, sans effet sur le % tant qu'il n'est pas adopté.
Restent communs sans étude ici, avec la raison : les réglages du classement Elo lui-même (welo, vitesse : un joueur
change de circuit), le rétrécissement des profils de service (n0 : réglé par composante, sa vérification demande le
rejeu complet des profils), la règle de stabilité (300 matchs, 2 erreurs types : un seuil de décision, pas un réglage
du modèle).

RÈGLE ÉCRITE LE 13/11/2026 AVANT TOUT CALCUL, pour A et B, circuit par circuit :
  A. grille poids de la surface {0 ; 0,1 ; … ; 0,6} × incertitude {0 ; 2,5 ; 5 ; 7,5 ; 10 ; 15}, choisie sur 2018–2022,
     jugée sur 2023 → juin 2026 contre le réglage en place (0,3 ; 5), pente du format et des Grands Chelems en place ;
     RETENUE pour ce circuit si elle gagne au moins 0,001 de log loss sur au moins 1 000 matchs jugés ET gagne aussi
     sur 2018–2022 (même sens). Elo réglé comme la production, mis à jour après chaque match. Challenger : l'archive
     n'a pas les résultats ITF hommes du classement de production → non concluant (paquets 229 et 230).
  B. poids propres au circuit appris sur 2024 (comme la combinaison en place), jugés sur 2025 → janvier 2026 contre
     les poids communs appris sur 2024 (explorateur_pronostics.json.gz : % donnés au vrai vainqueur, matchs de
     l'archive rejoués avant l'heure) ; même règle (0,001, 1 000 matchs, même sens sur 2024). ATP et WTA seulement.
Retenu → candidat (décision de Lucas ou fantôme), jamais en production dans ce paquet.

Usage : python simulateur/etude_par_circuit.py /tmp/sackmann .
"""
import datetime as dt
import gzip
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join(ICI, 'rapport_par_circuit.json')
DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
CIRCUITS = ('ATP', 'WTA', 'CH')
GRILLE_PS = tuple(round(0.1 * i, 1) for i in range(7))
GRILLE_INC = (0.0, 2.5, 5.0, 7.5, 10.0, 15.0)
MIN_JUGES, MARGE = 1000, 0.001
EXPLORATEUR = os.path.join('Tennis_Edge_Lab', 'live', 'explorateur_pronostics.json.gz')


def _ll(z):
    return math.log1p(math.exp(-z)) if z > -30 else -z


def composantes(archive, racine):
    """Une ligne par match jugeable, vue du vainqueur : notes générales et de surface, matchs vus, pente en place."""
    import donnees as DN
    import elo as E
    import etude_signaux_reappris as ER
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    fmt, gc = ER.pentes_en_place(racine)
    el, bas = E.de_production(racine)
    rows = []
    for m in sorted(DN.charger(archive, 2012), key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D' \
                and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            sv = s in E.SURFACES
            rows.append((d, c, el._g(g) - el._g(p), (el._s(g, s) - el._s(p, s)) if sv else None,
                         el.n.get(g, 0), el.n.get(p, 0), ER.pente_du_match(m, fmt, gc)))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def z_elo(r, ps, inc):
    _, _, dg, ds, na, nb, pente = r
    diff = dg if ds is None else (1 - ps) * dg + ps * ds
    z = diff / 400 * math.log(10)
    if inc:
        z /= math.sqrt(1 + inc * (1 / (na + 5) + 1 / (nb + 5)))
    return pente * z


def ll_moy(R, ps, inc):
    return sum(_ll(z_elo(r, ps, inc)) for r in R) / len(R) if R else None


def partie_a(rows, en_place):
    out = {}
    for c in CIRCUITS:
        av = [r for r in rows if r[1] == c and r[0] < COUPURE]
        ju = [r for r in rows if r[1] == c and r[0] >= COUPURE]
        grille = {(ps, inc): ll_moy(av, ps, inc) for ps in GRILLE_PS for inc in GRILLE_INC}
        ps, inc = min(grille, key=grille.get)
        l0a, l1a = ll_moy(av, *en_place), grille[(ps, inc)]
        l0, l1 = ll_moy(ju, *en_place), ll_moy(ju, ps, inc)
        d = [_ll(z_elo(r, *en_place)) - _ll(z_elo(r, ps, inc)) for r in ju]
        m = sum(d) / len(d)
        et = math.sqrt(sum((x - m) ** 2 for x in d) / len(d)) / math.sqrt(len(d))
        ok = len(ju) >= MIN_JUGES and (l0 - l1) >= MARGE and (l0a - l1a) > 0
        out[c] = {'matchs': {'2018–2022': len(av), '2023 → juin 2026': len(ju)},
                  'choisi': {'poids_surface': ps, 'incertitude': inc}, 'en_place': {'poids_surface': en_place[0], 'incertitude': en_place[1]},
                  'gain_apprentissage': round(l0a - l1a, 5), 'gain_jugement': round(l0 - l1, 5), 'erreur_type': round(et, 5),
                  'retenu': bool(ok and c != 'CH'),
                  **({'note': "non concluant : l'archive n'a pas les résultats ITF hommes du classement de production"}
                     if c == 'CH' else {})}
    return out


def partie_b(racine):
    import backtest_match_simule as BMS
    with gzip.open(os.path.join(racine, EXPLORATEUR), 'rt', encoding='utf-8') as f:
        doc = json.load(f)
    col = {n: i for i, n in enumerate(doc['colonnes'])}
    lg = lambda p: math.log(min(max(p, 1e-6), 1 - 1e-6) / (1 - min(max(p, 1e-6), 1 - 1e-6)))  # noqa: E731
    L = [(str(r[col['date']]), r[col['circuit']], r[col['elo']], r[col['simulation']]) for r in doc['lignes']
         if r[col['elo']] is not None and r[col['simulation']] is not None]
    app = [x for x in L if x[0] < '2025-01-01']
    w = BMS.ajuster_poids([[lg(e), lg(s)] for _, _, e, s in app])
    commun = {'elo': w[0], 'simulation': w[1]}
    z = lambda P, e, s: P['elo'] * lg(e) + P['simulation'] * lg(s)  # noqa: E731
    out = {'poids_communs_2024': {k: round(v, 4) for k, v in commun.items()}}
    for c in ('ATP', 'WTA'):
        a = [x for x in app if x[1] == c]
        j = [x for x in L if x[1] == c and x[0] >= '2025-01-01']
        wc = BMS.ajuster_poids([[lg(e), lg(s)] for _, _, e, s in a])
        Pc = {'elo': wc[0], 'simulation': wc[1]}
        g = lambda R: sum(_ll(z(commun, e, s)) - _ll(z(Pc, e, s)) for _, _, e, s in R) / len(R) if R else None  # noqa: E731
        d = [_ll(z(commun, e, s)) - _ll(z(Pc, e, s)) for _, _, e, s in j]
        m = sum(d) / len(d) if d else 0.0
        et = math.sqrt(sum((x - m) ** 2 for x in d) / len(d)) / math.sqrt(len(d)) if d else None
        ok = len(j) >= MIN_JUGES and m >= MARGE and (g(a) or 0) > 0
        out[c] = {'matchs': {'2024': len(a), '2025 → janvier 2026': len(j)}, 'poids_du_circuit': {k: round(v, 4) for k, v in Pc.items()},
                  'gain_apprentissage': round(g(a), 5) if a else None, 'gain_jugement': round(m, 5),
                  'erreur_type': round(et, 5) if et is not None else None, 'retenu': bool(ok)}
    return out


def main(argv):
    import elo as E
    archive = argv[1] if len(argv) > 1 else '/tmp/sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    opt, _ = E.options_production(racine)
    en_place = (float(opt.get('poids_surface', 0.5)), float(opt.get('incertitude', 0.0)))
    A = partie_a(composantes(archive, racine), en_place)
    B = partie_b(racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 255, 'statut': 'etude',
           'regle': ("circuit par circuit : réglage propre choisi sur la période d'apprentissage, jugé sur la période suivante "
                     "contre le réglage commun ; retenu si −0,001 de log loss sur au moins 1 000 matchs jugés et gain aussi sur "
                     "l'apprentissage ; Challenger non concluant sur l'archive"),
           'A_elo_au_moment_du_pronostic': A, 'B_poids_du_melange_archive': B,
           'C_modele_complet_des_facteurs': "fantôme par circuit dans le flux du lundi (facteurs.py), règle cumulée à deux mesures",
           'restent_communs': {'welo et vitesse du classement': "le classement est commun : un joueur passe d'un circuit à l'autre",
                               'n0 des profils de service': "réglé par composante ; le rejeu complet des profils est hors de ce paquet",
                               'règle de stabilité': "seuil de décision, pas un réglage du modèle"}}
    doc['retenus'] = [f"A · {c}" for c, v in A.items() if v.get('retenu')] + \
                     [f"B · {c}" for c, v in B.items() if isinstance(v, dict) and v.get('retenu')]
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps({'A': A, 'B': B, 'retenus': doc['retenus']}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
