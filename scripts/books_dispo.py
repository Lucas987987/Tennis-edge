#!/usr/bin/env python3
"""books_dispo.py — quels books le fournisseur sert-il réellement ?

    python scripts/books_dispo.py              # 3 matchs du jour
    N=8 python scripts/books_dispo.py          # sur plus de matchs

LECTURE SEULE. Aucun fichier écrit, aucune constante touchée, aucune
hypothèse concernée. Deux ou trois requêtes API.

POURQUOI
--------
Question posée : peut-on avoir un second book sharp, au niveau de
Pinnacle, pour comparer ? Avant d'ouvrir un compte courtier chez Vertex ou
ailleurs, il faut savoir ce que `odds-api1` distribue déjà. Le dépôt
n'interroge jamais `bookmakers="all"` : la liste complète n'a simplement
jamais été regardée.

CE QUE LA MARGE DIT, ET CE QU'ELLE NE DIT PAS
---------------------------------------------
La marge affichée ici est 1/cote_home + 1/cote_away − 1, sur le marché
vainqueur. Une marge basse est le signe habituel d'un book sharp : il vit
du volume, pas de l'écart.

Mais une marge basse NE SUFFIT PAS. Le dépôt l'a déjà mesuré sur coolbet :
marge la plus basse de toutes (3,24 %) et le CLV le plus FAIBLE du lot
(+2,2 %), quand bet365 à 5,69 % de marge donnait +7,7 %. Un book serré en
permanence n'est jamais en retard sur le marché : il attire le détecteur
sans apporter d'edge.

Ce tableau répond donc à « qui est disponible et à quelle marge », ce qui
est une question de catalogue. Savoir si un book prédit mieux que Pinnacle
demande de le journaliser pendant des semaines et de comparer les clôtures
aux résultats. Ce script est l'étape qui dit si ça vaut la peine de s'y
mettre, pas la réponse.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov

N = int(os.environ.get('N', '3'))

# Noms rencontrés sur les books à bas écart. Purement indicatif : sert à
# attirer l'œil dans une liste longue, jamais à filtrer.
SHARPS = {'pinnacle', 'betfair-ex', 'betfair', 'smarkets', 'matchbook',
          'sbobet', 'sbo', 'ibcbet', 'maxbet', 'vertex', 'vertex88',
          'betinasia', 'orbit', 'bet365'}


def marge(h, a):
    try:
        return (1 / float(h) + 1 / float(a) - 1) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    tournois = ov.discover_tennis_tournaments()
    if not tournois:
        print('Aucun tournoi de tennis aujourd’hui — relancer un jour de '
              'matchs.')
        return 0
    print(f'{len(tournois)} tournoi(s) aujourd’hui.')

    fixtures = []
    for tid, meta in tournois.items():
        for f in ov.odds_main(tid, bookmakers='all'):
            if not ov.is_srl(f):
                fixtures.append((meta['name'], f))
        if len(fixtures) >= N:
            break

    if not fixtures:
        print('Aucun match exploitable.')
        return 0

    vus = {}
    for nom_t, f in fixtures[:N]:
        m = ov.fixture_meta(f)
        print(f'\n{nom_t} — {m.get("home")} vs {m.get("away")}')
        lignes = []
        for bk in (f.get('odds') or {}).keys():
            h, a = ov._mw_quotes(f, bk)
            if not (h and a):
                continue
            mg = marge(h, a)
            lignes.append((mg if mg is not None else 99, bk, h, a, mg))
            vus.setdefault(bk, []).append(mg)
        if not lignes:
            print('  (pas de marché vainqueur coté)')
            continue
        for _, bk, h, a, mg in sorted(lignes)[:40]:
            etoile = ' ←' if bk.lower() in SHARPS else ''
            print(f'  {bk:16} {h:>7} / {a:<7} marge '
                  f'{mg:5.2f} %{etoile}' if mg is not None
                  else f'  {bk:16} {h:>7} / {a:<7}{etoile}')

    print(f'\n{"="*58}\n{len(vus)} books distincts servis sur ces matchs, '
          f'par marge moyenne :\n')
    moy = []
    for bk, ms in vus.items():
        ok = [x for x in ms if x is not None]
        if ok:
            moy.append((sum(ok) / len(ok), bk, len(ok)))
    for mg, bk, n in sorted(moy):
        etoile = ' ←' if bk.lower() in SHARPS else ''
        print(f'  {mg:5.2f} %  {bk:16} (n={n}){etoile}')

    manquants = sorted(SHARPS - {b.lower() for b in vus})
    if manquants:
        print(f'\nNon servis par le fournisseur : {", ".join(manquants)}')
    print('\nUne marge basse ne vaut pas un bon signal — voir l’en-tête.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
