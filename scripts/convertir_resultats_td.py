#!/usr/bin/env python3
"""convertir_resultats_td.py — les RÉSULTATS tennis-data (sans cotes) en un
fichier compact pour la règle R4 du suivi.

    python scripts/convertir_resultats_td.py dossier_xlsx/ historique/tennis_data_resultats.csv.gz

Pourquoi un second fichier : tennis_data.csv.gz ne garde que les matchs
avec cote Pinnacle, qui disparaît des fichiers tennis-data fin janvier
2026. R4 n'a besoin que de QUI A GAGNÉ (le % de victoires sur 365 jours),
et tennis-data continue de publier les résultats : on garde donc tous les
matchs terminés, cote ou pas.

À relancer quand on télécharge un nouveau fichier de l'année en cours
(ATP et WTA) : plus il est à jour, moins le suivi dépend de nos propres
résultats.

GARDÉ : matchs terminés (Comment = Completed), depuis DEPUIS (365 jours
avant le gel de R4, plus de la marge). COLONNES : date, circuit,
vainqueur, perdant — noms au format tennis-data (« Bublik A. »).
"""

import csv
import datetime
import glob
import gzip
import os
import sys

import openpyxl

DEPUIS = datetime.date(2024, 9, 1)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    source, sortie = sys.argv[1], sys.argv[2]
    lignes, vus = [], set()
    for f in sorted(glob.glob(os.path.join(source, '*.xlsx'))):
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        it = wb.worksheets[0].iter_rows(values_only=True)
        h = [str(c).strip() if c is not None else '' for c in next(it)]
        circuit = h[0]
        if circuit not in ('ATP', 'WTA'):
            continue
        n = 0
        for row in it:
            r = dict(zip(h, row))
            d = r.get('Date')
            if not isinstance(d, datetime.datetime) or d.date() < DEPUIS:
                continue
            if str(r.get('Comment') or '').strip().lower() != 'completed':
                continue
            w, l = str(r.get('Winner') or '').strip(), str(r.get('Loser') or '').strip()
            k = (d.date(), circuit, w, l)
            if not w or not l or k in vus:
                continue
            vus.add(k)
            lignes.append([d.date().isoformat(), circuit, w, l])
            n += 1
        if n:
            print(f'  {os.path.basename(f)} : {circuit} {n} matchs gardés')
    lignes.sort()
    os.makedirs(os.path.dirname(sortie) or '.', exist_ok=True)
    with gzip.open(sortie, 'wt', encoding='utf-8', newline='') as g:
        w = csv.writer(g)
        w.writerow(['date', 'circuit', 'vainqueur', 'perdant'])
        w.writerows(lignes)
    for c in ('ATP', 'WTA'):
        ds = [x[0] for x in lignes if x[1] == c]
        if ds:
            print(f'  {c} : {len(ds)} matchs, {ds[0]} -> {ds[-1]}')
    print(f'{sortie} : {os.path.getsize(sortie)/1e3:.0f} ko')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
