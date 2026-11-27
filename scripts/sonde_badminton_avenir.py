#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonde_badminton_avenir.py — LE BADMINTON ANNONCE-T-IL SES MATCHS À L'AVANCE ? (27/11/2026, paquet 518, Lucas : « oui »
à la sonde avant la page du badminton).

LECTURE SEULE. Rien n'est écrit dans le dépôt : tout est dans le journal du run, qui ne montre que des codes HTTP, des
comptes, des tailles, des écarts d'heures et des noms de tournoi (jamais la clé, jamais de cote, jamais un nom de joueur).

Pour aujourd'hui et les 4 jours suivants (UTC), une requête par jour sur la catégorie « International » du badminton
(numéro gardé par la collecte, 259) : combien de matchs, combien « à venir », avec ou sans les deux camps connus
(tableau publié ou « à déterminer »), combien d'heures à l'avance, le tour, le format annoncé, les tournois et les
épreuves, la taille des réponses. Environ 5 requêtes AllSportsApi.
Usage : python scripts/sonde_badminton_avenir.py
"""
import collections
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import allsports as AS  # noqa: E402

CATEGORIE = 259
JOURS = 5
VIDE = re.compile(r'^\s*$|tbd|à déterminer|winner|vainqueur|bye', re.I)


def camp_connu(c):
    return bool(c and c.get('id') and not VIDE.search(str(c.get('name') or '')))


def epreuve(tournoi):
    t = str(tournoi or '')
    for sig, nom in (('XD', 'mixte'), ('Mixed', 'mixte'), ('MS', 'SM'), ('WS', 'SD'), ('MD', 'DM'), ('WD', 'DD'),
                     ('Women', 'dames ?'), ('Men', 'messieurs ?')):
        if re.search(rf'(?<![A-Za-z]){sig}(?![A-Za-z])', t):
            return nom
    return 'non dit'


def tranche_heures(h):
    for lim, nom in ((0, 'déjà passé'), (3, '< 3 h'), (12, '3–12 h'), (24, '12–24 h'), (48, '24–48 h'), (96, '48–96 h')):
        if h < lim:
            return nom
    return '≥ 96 h'


def sonder(c, maintenant, journal=print):
    ts = maintenant.timestamp()
    total = collections.Counter()
    for k in range(JOURS):
        d = (maintenant + dt.timedelta(days=k)).date()
        avant = c.octets
        code, doc = c.get(f'/api/badminton/category/{CATEGORIE}/events/{d.day}/{d.month}/{d.year}')
        ev = [e for e in (doc or {}).get('events') or [] if e.get('startTimestamp')]
        ev = [e for e in ev if dt.datetime.fromtimestamp(e['startTimestamp'], dt.timezone.utc).date() == d]
        statuts = collections.Counter(str((e.get('status') or {}).get('type')) for e in ev)
        av = [e for e in ev if (e.get('status') or {}).get('type') == 'notstarted']
        connus = [e for e in av if camp_connu(e.get('homeTeam')) and camp_connu(e.get('awayTeam'))]
        heures = collections.Counter(tranche_heures((e['startTimestamp'] - ts) / 3600) for e in connus)
        tours = collections.Counter(str((e.get('roundInfo') or {}).get('name') or '—') for e in av)
        fmt = collections.Counter(str(e.get('defaultPeriodCount') or e.get('bestOf') or '—') for e in av)
        tournois = collections.Counter(str((e.get('tournament') or {}).get('name') or '?') for e in av)
        eps = collections.Counter(epreuve((e.get('tournament') or {}).get('name')) for e in av)
        heure_ronde = sum(1 for e in av if e['startTimestamp'] % 3600 == 0)
        journal(f"{d.isoformat()} : code {code}, {len(ev)} matchs ce jour, statuts {dict(statuts)}, "
                f"{(c.octets - avant) / 1e3:.0f} ko")
        journal(f"  à venir {len(av)}, dont les deux camps connus {len(connus)} ; heure pile {heure_ronde}")
        if av:
            journal(f"  à l'avance (camps connus) : {dict(heures)}")
            journal(f"  tours : {dict(tours.most_common(8))}")
            journal(f"  format annoncé (manches) : {dict(fmt)}")
            journal(f"  épreuves : {dict(eps)}")
            journal(f"  tournois : {dict(tournois.most_common(6))}")
        total['matchs'] += len(ev)
        total['a_venir'] += len(av)
        total['connus'] += len(connus)
    journal(f"total : {dict(total)}")
    return total


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY')
    if not cle:
        print('sonde badminton : RAPIDAPI_KEY absente')
        return 0
    c = AS.Client(cle, minutes=10)
    sonder(c, dt.datetime.now(dt.timezone.utc))
    print(c.bilan())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
