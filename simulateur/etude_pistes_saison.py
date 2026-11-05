#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pistes_saison.py — pistes non encore analysées (05/11/2026, demande de Lucas), jugées circuit par circuit :

1. FIN DE SAISON : en octobre-novembre, le favori de l'Elo tient-il moins (ou mieux) son rang ? Motivation, fatigue
   de fin d'année. x_fin = (+1 si A est le favori Elo, −1 sinon) × [mois ≥ 10].
2. POINTS À DÉFENDRE : matchs gagnés par le joueur dans l'édition PRÉCÉDENTE du même tournoi (plafonné à 6) —
   tenant du titre, finaliste de l'an passé sous pression. x_defendre = n_A − n_B.
3. LUCKY LOSER : repêché après une défaite en qualifications. x_ll = [A lucky loser] − [B lucky loser].

Pistes NON testables faute de données (dit à Lucas) : double joué la même semaine (l'archive n'a pas les doubles),
heure du match (l'archive n'a pas d'heure ; nos feuilles en ont depuis septembre 2026 seulement).

RÈGLE FIXÉE LE 05/11/2026, AVANT DE REGARDER LE RÉSULTAT — la même que etude_pistes_tournoi.py :
  a) SEULE contre l'Elo : β appris sur 2016–2022, jugé sur 2023 → ; positive si −0,001 de log loss sur les matchs
     concernés (x ≠ 0, au moins 300) ET gain positif sur tous les matchs ;
  b) AJOUTÉE au modèle combiné en place (6 paramètres) : 7 paramètres ré-appris ENSEMBLE sur 2016–2022 ; il faut
     ENCORE au moins 0,001 de gain sur tous les matchs jugés 2023 →.
  Les deux exigées. Retrait : même règle que les signaux combinés.
Usage : python simulateur/etude_pistes_saison.py /tmp/sackmann .
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_age as EA  # noqa: E402
import etude_changement_surface as ECS  # noqa: E402
import etude_pistes_tournoi as EPT  # noqa: E402
import etude_profils_contexte as EPC  # noqa: E402
import etude_retour_absence as ERA  # noqa: E402

DEBUT, PLAFOND = dt.date(2016, 1, 1), 6
SORTIE = os.path.join(ICI, 'rapport_pistes_saison.json')
PISTES = ('fin_de_saison', 'points_a_defendre', 'lucky_loser')


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    M = DN.charger(archive, 2012)                 # archive seule : l'entrée (LL) n'existe que là
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    naiss = EA.naissances(archive, k)
    M.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    el, su, rt, RS = E.Elo(), ECS.Suivi(), ERA.Retours(), EPC.Residus()
    victoires = collections.defaultdict(int)       # (joueur, tournoi_base, édition) → matchs gagnés
    jour, attente, rows = None, [], []
    for m in M:
        d = m['date']
        if d != jour:
            for g, p, s, gc in attente:
                el.maj(g, p, s, gc, None)
            attente, jour = [], d
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if c in ('CH', 'ITF'):
            el.presenter(g, 1200.0)
            el.presenter(p, 1200.0)
        pe = el.proba(g, p, s)
        base, ed = m.get('tournoi_base') or m.get('tournoi'), m.get('edition') or d.year
        role_g, role_p = ('fav', 'out') if pe >= 0.5 else ('out', 'fav')
        if c in ('ATP', 'WTA', 'CH') and d >= DEBUT and not m.get('abandon') and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            xs = su.nouveau(g, d, s) - su.nouveau(p, d, s)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            xr = RS.moy(g, role_g) - RS.moy(p, role_p)
            dfd = lambda j: min(victoires.get((j, base, ed - 1), 0), PLAFOND)
            rows.append({'d': d, 'c': c, 'z': EPT._lg(pe), 'x6': (float(xs), xa[0], xa[1], xg[0], xg[1], xr),
                         'fin_de_saison': (1.0 if pe >= 0.5 else -1.0) * (1.0 if d.month >= 10 else 0.0),
                         'points_a_defendre': float(dfd(g) - dfd(p)),
                         'lucky_loser': float((m.get('entree_g') == 'LL') - (m.get('entree_p') == 'LL'))})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        victoires[(g, base, ed)] += 1
        if not m.get('abandon'):
            RS.ajouter(g, role_g, 1 - pe)
            RS.ajouter(p, role_p, -(1 - pe))
        attente.append((g, p, s, m.get('niveau') == 'G'))
    return rows


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else os.path.join(ICI, '..'))
    EPT.PISTES = PISTES                              # même jugement que les pistes du tournoi
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par piste et par circuit : seule, −0,001 sur ≥ 300 matchs concernés et gain positif sur tous ; ET "
                     "ajoutée au combiné, encore −0,001 sur tous les matchs jugés 2023 →"),
           'non_testables': {'double_meme_semaine': "pas de doubles dans l'archive",
                             'heure_du_match': "pas d'heure dans l'archive ; feuilles horodatées depuis septembre 2026 seulement"},
           'circuits': EPT.juger(lignes(archive, racine))}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
