#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_profils_individuels.py — chaque joueur a-t-il SON adversaire type ? (12/11/2026, paquet 251, demande de Lucas :
« voir de manière individuelle, propre à chaque joueur, et non de manière globale »)

L'étude 250 jugeait des duels de coups pour TOUS les joueurs à la fois (un seul β) : rien. Ici, l'effet est propre au
joueur : certains joueurs perdent-ils plus que prévu contre les grands serveurs, d'autres contre les contreurs ?

DONNÉES. Archive Sackmann 2015 → juin 2026 (ATP, WTA, Challenger), Elo réglé comme la production et mis à jour après
chaque match ; style de chaque joueur FIGÉ AVANT le match, avec ses seules feuilles déjà connues
(styles_descriptifs.classifier : grand serveur, serveur attaquant, retourneur pressant, contreur, équilibré ; au moins
500 points de service, sinon indéterminé) — les styles du site.

VARIABLE, ÉCRITE LE 12/11/2026 AVANT TOUT CALCUL (même forme que « contre gaucher », etude_profils_contexte.py) :
  pour chaque joueur et chaque style d'adversaire, résidu = résultat − probabilité Elo d'avant-match, sur ses seuls
  matchs passés, rétréci : somme / (n + 20) ; et son résidu contre TOUS les adversaires, rétréci de même.
  effet(j, style) = résidu contre ce style − résidu contre tous (ce qu'il fait de plus ou de moins contre CE style) ;
  x = effet(A, style de B) − effet(B, style de A), vu du vainqueur A ; 0 si un style est indéterminé.
RÈGLE (celle du dépôt) : par circuit, β appris sur 2018–2022, jugé sur 2023 → juin 2026, sur les matchs concernés
(x ≠ 0) : RETENU si la log loss du vainqueur baisse d'au moins 0,001 sur au moins 1 000 matchs concernés jugés ET si β
appris sur 2023 → a le même signe. Retenu → candidat au fantôme, jamais en production ici. Challenger : l'archive n'a
pas les résultats ITF hommes que le classement de production utilise → non concluant (paquets 229 et 230).
La variable est divisée par sa moyenne quadratique d'apprentissage (unité commune), JAMAIS centrée (paquet 250 : une
moyenne retirée sur des lignes vues du vainqueur fait une constante « le vainqueur gagne »).

Usage : python simulateur/etude_profils_individuels.py /tmp/sackmann .
"""
import collections
import datetime as dt
import heapq
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SORTIE = os.path.join(ICI, 'rapport_profils_individuels.json')
K = 20.0
DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_JUGES, MARGE = 1000, 0.001


class Residus:
    def __init__(self):
        self.s = collections.defaultdict(lambda: [0.0, 0])

    def moy(self, j, ctx):
        s, n = self.s[(j, ctx)]
        return s / (n + K)

    def ajouter(self, j, ctx, r):
        e = self.s[(j, ctx)]
        e[0] += r
        e[1] += 1

    def effet(self, j, style):
        if not style or style == 'indetermine':
            return None
        return self.moy(j, style) - self.moy(j, 'tous')


def lignes(archive, racine):
    import donnees as DN
    import elo as E
    import profils_service as PS
    import styles_descriptifs as SD
    with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
        alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    M = sorted(DN.charger(archive, 2015), key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    P, (el, bas), RS = PS.Profils(PS.DEMI_VIE, 1.0), E.de_production(racine), Residus()
    attente, serial, rows = [], 0, []
    for m in M:
        debut = dt.datetime.combine(m['date'], dt.time())
        while attente and attente[0][0] < debut:
            _, _, a = heapq.heappop(attente)
            P.ajouter(a, a['_g'], a['_p'])
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        m['_g'], m['_p'] = g, p
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        pe = el.proba(g, p, s)
        mu = P.moyenne(c, s)
        sg = SD.classifier(*P.profil(g, c, s, m['date']), mu)
        sp = SD.classifier(*P.profil(p, c, s, m['date']), mu)
        if c in CIRCUITS and DEBUT <= m['date'] < FIN and not m.get('abandon') and m.get('niveau') != 'D' \
                and el.matchs(g) >= 10 and el.matchs(p) >= 10:
            eg, ep = RS.effet(g, sp), RS.effet(p, sg)
            x = (eg - ep) if eg is not None and ep is not None else 0.0
            rows.append({'d': m['date'], 'c': c, 'z': _lg(pe), 'x': x})
        if not m.get('abandon') and c != 'ITF':
            for j, st_adv, r in ((g, sp, 1 - pe), (p, sg, -(1 - pe))):
                RS.ajouter(j, 'tous', r)
                if st_adv and st_adv != 'indetermine':
                    RS.ajouter(j, st_adv, r)
        heapq.heappush(attente, (dt.datetime.combine(m['fin'], dt.time()), serial, m))
        serial += 1
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows


def _lg(p):
    import math
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def juger(rows, c):
    import etude_outsiders as EO
    import etude_signaux_combines as ESC
    R = [r for r in rows if r['c'] == c and r['x']]
    av, ju = [r for r in R if r['d'] < COUPURE], [r for r in R if r['d'] >= COUPURE]
    out = {'matchs_concernes': {'2018–2022': len(av), '2023 → juin 2026': len(ju)},
           'matchs_du_circuit': sum(1 for r in rows if r['c'] == c)}
    if len(av) < 200 or not ju:
        return dict(out, retenu=False, note='trop peu de matchs concernés')
    rms = (sum(r['x'] ** 2 for r in av) / len(av)) ** .5 or 1.0
    b1 = ESC.apprendre([(r['z'], (r['x'] / rms,)) for r in av], k=1)[0]
    b2 = ESC.apprendre([(r['z'], (r['x'] / rms,)) for r in ju], k=1)[0]
    b = EO.bilan([r['z'] for r in ju], [r['z'] + b1 * r['x'] / rms for r in ju])
    ok = len(ju) >= MIN_JUGES and b['gain'] >= MARGE and b1 * b2 > 0
    out.update(beta_2018_2022=round(b1, 3), beta_2023=round(b2, 3), gain=b['gain'], erreur_type=b['erreur_type'],
               erreurs_types=b['erreurs_types'], retenu=bool(ok))
    if c == 'CH':
        out['note'] = "non concluant : l'archive n'a pas les résultats ITF hommes du classement de production"
    return out


def main(argv):
    archive = argv[1] if len(argv) > 1 else '/tmp/sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    rows = lignes(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 251, 'statut': 'etude',
           'regle': ("par circuit : effet propre à chaque joueur contre chaque style d'adversaire (résidu rétréci contre ce "
                     "style moins contre tous), β appris sur 2018–2022, jugé sur 2023 → juin 2026 ; retenu si −0,001 de log "
                     "loss sur au moins 1 000 matchs concernés et β de même signe ; Challenger non concluant"),
           'circuits': {c: juger(rows, c) for c in CIRCUITS}}
    doc['retenus'] = [c for c, v in doc['circuits'].items() if v.get('retenu') and c != 'CH']
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(json.dumps(doc['circuits'], ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
