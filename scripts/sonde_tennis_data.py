#!/usr/bin/env python3
"""sonde_tennis_data.py — que vaut tennis-data.co.uk pour remonter l'historique ?

    python scripts/sonde_tennis_data.py

LECTURE SEULE pour le dépôt : télécharge dans un dossier temporaire, n'écrit
rien dans le dépôt, ne commite rien. Lancé par le workflow « Sonde
tennis-data », qui envoie le résumé sur Telegram.

LA QUESTION (09/10/2026)
------------------------
Les fiches n'ont que ~4 mois de cotes (relevés depuis mi-juin). Le site
tennis-data.co.uk publie, saison par saison, les résultats ATP (depuis 2000)
et WTA (depuis 2007) du circuit principal avec des cotes de plusieurs
bookmakers, dont Pinnacle (colonnes PSW / PSL). Si ces cotes sont bonnes,
on pourrait remonter des années d'historique d'un coup.

CE QUE LA SONDE VÉRIFIE
-----------------------
  1. Quelles saisons sont disponibles, jusqu'à quelle date pour 2026.
  2. La part des matchs qui ont une cote Pinnacle.
  3. Les tournois couverts (colonne Series / Tier).
  4. Si les noms (« Bublik A. ») se relient aux fiches (« Alexander Bublik »).
  5. LE POINT DÉCISIF : sur les matchs communs depuis juin, la cote Pinnacle
     de tennis-data est-elle la MÊME que notre clôture Pinnacle ? Si oui,
     ce sont des cotes de clôture, comparables aux nôtres. Si l'écart est
     grand, ce sont des cotes d'ouverture ou d'une autre heure, et les
     mélanger fausserait les médianes.

Ne fait que MESURER. L'import, s'il vaut le coup, sera un autre script.
"""

import io
import json
import os
import re
import statistics as st
import sys
import tempfile
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

ANNEES = [int(a) for a in os.environ.get('ANNEES', '2024,2025,2026').split(',')]
BASE = 'http://www.tennis-data.co.uk'
PROFILS = os.environ.get('PROFILS', 'players_profile.json')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z ]+', ' ', s.replace('-', ' ')).split()


def telecharger(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 tennis-edge-sonde'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def lire(contenu):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    lignes = ws.iter_rows(values_only=True)
    entete = [str(c).strip() if c is not None else '' for c in next(lignes)]
    out = []
    for l in lignes:
        if not any(l):
            continue
        out.append(dict(zip(entete, l)))
    return entete, out


def en_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def num(v):
    try:
        x = float(v)
        return x if x > 1 else None
    except (TypeError, ValueError):
        return None


def index_fiches():
    """(nom de famille normalisé, initiale) -> {clé de fiche}, et la fiche."""
    try:
        J = json.load(open(PROFILS, encoding='utf-8'))['joueurs']
    except Exception as e:
        print(f'  fiches illisibles ({e}) — étape 4 et 5 sautées')
        return {}, {}
    idx = defaultdict(set)
    for k, p in J.items():
        t = norm(p.get('nom') or '')
        if len(t) < 2:
            continue
        # Toutes les façons de couper prénom / nom : « Felix Auger Aliassime »
        # -> nom « auger aliassime » ou « aliassime », initiale f.
        for i in range(1, len(t)):
            idx[(' '.join(t[i:]), t[0][0])].add(k)
    return idx, J


def relier(nom_td, idx):
    """« Auger-Aliassime F. » -> clé de fiche, ou None si absent/ambigu."""
    t = norm(nom_td)
    if len(t) < 2:
        return None
    ini = t[-1][0]
    nom = ' '.join(t[:-1])
    c = idx.get((nom, ini), set())
    return next(iter(c)) if len(c) == 1 else None


def main():
    tmp = tempfile.mkdtemp()
    idx, J = index_fiches()
    print(f'{len(J)} fiches chargées pour la jointure des noms')
    communs = []
    for circuit, suffixe in (('ATP', ''), ('WTA', 'w')):
        print('\n' + '=' * 70)
        print(f'{circuit}')
        print('=' * 70)
        for a in ANNEES:
            url = f'{BASE}/{a}{suffixe}/{a}.xlsx'
            try:
                brut = telecharger(url)
            except Exception as e:
                print(f'  {a} : indisponible ({type(e).__name__}: {e})')
                continue
            open(os.path.join(tmp, f'{circuit}_{a}.xlsx'), 'wb').write(brut)
            try:
                entete, L = lire(brut)
            except Exception as e:
                print(f'  {a} : illisible ({type(e).__name__}: {e})')
                continue
            ds = [d for d in (en_date(x.get('Date')) for x in L) if d]
            ps = [x for x in L if num(x.get('PSW')) and num(x.get('PSL'))]
            cotes = sorted(c for c in entete if re.fullmatch(r'[A-Z0-9]{1,5}[WL]', c))
            serie = Counter(str(x.get('Series') or x.get('Tier') or '?') for x in L)
            print(f'  {a} : {len(L)} matchs, du {min(ds) if ds else "?"} au {max(ds) if ds else "?"}'
                  f'   cote Pinnacle : {len(ps)} ({100*len(ps)/max(1,len(L)):.0f} %)')
            print(f'       colonnes de cotes : {" ".join(cotes)}')
            print(f'       niveaux : {", ".join(f"{k} {v}" for k, v in serie.most_common(6))}')
            if not idx:
                continue
            ok = 0
            for x in L:
                g, p = relier(x.get('Winner'), idx), relier(x.get('Loser'), idx)
                ok += bool(g) + bool(p)
                d = en_date(x.get('Date'))
                if g and p and d and d >= date(2026, 6, 1) and num(x.get('PSW')):
                    communs.append((circuit, d, g, p, num(x['PSW']), num(x['PSL'])))
            print(f'       noms reliés à une fiche : {ok} sur {2*len(L)} ({100*ok/max(1,2*len(L)):.0f} %)')

    print('\n' + '=' * 70)
    print('LE POINT DÉCISIF — leur Pinnacle contre notre clôture (matchs communs)')
    print('=' * 70)
    ecarts = []
    for circuit, d, g, p, pw, pl in communs:
        juste_td = (1 / pw) / (1 / pw + 1 / pl)              # vainqueur, marge retirée
        for m in J.get(g, {}).get('derniers', []):
            md = date.fromisoformat(m['date'])
            if m.get('adv_cle') == p and abs((md - d).days) <= 2 and m.get('cote'):
                ecarts.append(100 * (juste_td - 1 / m['cote']))
                break
    if not ecarts:
        print('  aucun match commun retrouvé — comparaison impossible')
    else:
        a = sorted(abs(e) for e in ecarts)
        print(f'  {len(ecarts)} matchs communs (fiche : 16 derniers matchs par joueur)')
        print(f'  écart de probabilité |tennis-data − notre clôture| :')
        print(f'    médiane {a[len(a)//2]:.1f} pts   90e centile {a[9*len(a)//10]:.1f} pts'
              f'   moyenne signée {st.mean(ecarts):+.2f} pts')
        print(f'    à moins de 1 pt : {100*sum(1 for e in a if e < 1)/len(a):.0f} %'
              f'    à moins de 3 pts : {100*sum(1 for e in a if e < 3)/len(a):.0f} %')
        if a[len(a)//2] < 1:
            print('  LECTURE : quasi identiques — ce sont des cotes de CLÔTURE, comparables.')
        elif a[len(a)//2] < 3:
            print('  LECTURE : proches mais pas identiques — clôture probable, à une autre heure.')
        else:
            print('  LECTURE : trop différentes — pas notre clôture (ouverture ?). NE PAS mélanger.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
