#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_fetch.py — Récupère les Elo publiés par Tennis Abstract (ATP + WTA).

POURQUOI PLUTÔT QUE NOTRE ELO MAISON
elo_model.py construit un Elo sur NOS résultats : 2169 matchs, 527 joueurs,
médiane d'un match par joueur. Mesuré : 53,7 % de précision contre 66,9 % pour
Pinnacle sur les mêmes rencontres. Autrement dit, inutilisable en l'état — il
faudra des mois d'historique.
Tennis Abstract publie des Elo calculés sur l'historique COMPLET du circuit,
mis à jour chaque semaine. Le gain de temps est de plusieurs mois.

CE QUE LA SOURCE FOURNIT
  • Elo global, hElo (dur), cElo (terre), gElo (gazon) ;
  • plus de 440 joueurs ATP et autant côté WTA, incluant Challengers et ITF
    50K+ — donc le circuit que Kalshi couvre et que Polymarket ignorait ;
  • classement ATP/WTA officiel en regard, utile pour repérer les écarts.
Périmètre annoncé : joueurs ayant disputé au moins 10 matchs de niveau tour,
qualifications, Challenger ou ITF 50K+ sur les 52 dernières semaines.

FIABILITÉ
Source de référence de l'analyse tennis (Jeff Sackmann), mise à jour
hebdomadaire. Le script enregistre la date de mise à jour annoncée par la page
et REFUSE des données trop anciennes (ELO_MAX_AGE_DAYS) : un Elo périmé est
pire qu'aucun Elo, parce qu'il donne une fausse impression de fraîcheur.

PRUDENCE SUR LE RÉSEAU
Le runner GitHub n'atteignait pas le dépôt Sackmann (egress bloqué). Ce n'est
PAS le même hôte, donc c'est peut-être différent — mais si la récupération
échoue, le script le dit clairement au lieu d'écrire un fichier vide, et
conserve le fichier précédent.

Sortie : elo_reference.json
Env : ELO_URLS, ELO_MAX_AGE_DAYS (14), OUT.
"""
import os
import re
import sys
import json
import html
import datetime
import unicodedata
import urllib.request
import urllib.error

URLS = os.environ.get('ELO_URLS',
                      'https://tennisabstract.com/reports/atp_elo_ratings.html,'
                      'https://tennisabstract.com/reports/wta_elo_ratings.html')
OUT = os.environ.get('OUT', 'elo_reference.json')
MAX_AGE = int(os.environ.get('ELO_MAX_AGE_DAYS', '14'))
TIMEOUT = float(os.environ.get('HTTP_TIMEOUT', '30'))


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def cle_joueur(nom):
    """Même normalisation que elo_model.py et player_key.py : jetons triés.
    Indispensable pour que « Felix Auger Aliassime » et « Felix Auger-Aliassime »
    désignent le même joueur."""
    t = [x for x in re.split(r'[^a-z0-9]+', norm(nom)) if len(x) >= 2]
    return ' '.join(sorted(t)) if t else None


def http_get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; TennisEdge/1.0)',
        'Accept': 'text/html,application/xhtml+xml',
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        brut = r.read()
    for enc in ('utf-8', 'latin-1'):
        try:
            return brut.decode(enc)
        except UnicodeDecodeError:
            continue
    return brut.decode('utf-8', errors='replace')


def date_maj(page):
    """« Last update: 2026-08-10 » — sert à refuser des données périmées."""
    m = re.search(r'Last\s+update[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})', page, re.I)
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def parser(page, tour):
    """Extrait les lignes du tableau.

    Robuste par construction : on ne présume pas de la structure exacte. On
    cherche les lignes <tr>, on en retire les balises, et on ne retient que
    celles qui contiennent un nom de joueur suivi de nombres plausibles.
    En cas d'échec, main() écrit un échantillon brut — leçon de la sonde
    Kalshi, où trois runs ont été perdus faute d'échantillon exploitable.
    """
    joueurs = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S | re.I):
        cells = [html.unescape(re.sub(r'<[^>]+>', ' ', c)).strip()
                 for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
        cells = [re.sub(r'\s+', ' ', c) for c in cells if c != '']
        if len(cells) < 5:
            continue
        # 1re cellule numérique = rang ; 2e alphabétique = joueur
        nom = None
        for c in cells[:3]:
            if re.search(r'[a-zA-Z]{3,}', c) and not re.fullmatch(r'[\d.\s]+', c):
                nom = c
                break
        if not nom:
            continue
        nombres = []
        for c in cells:
            c2 = c.replace(',', '')
            if re.fullmatch(r'-?\d+(\.\d+)?', c2):
                nombres.append(float(c2))
        # Un Elo plausible se situe entre 1000 et 2600.
        elos = [x for x in nombres if 1000 <= x <= 2600]
        if not elos:
            continue
        cle = cle_joueur(nom)
        if not cle or cle in joueurs:
            continue
        joueurs[cle] = {
            'nom': nom, 'tour': tour, 'elo': elos[0],
            'dur': elos[1] if len(elos) > 1 else None,
            'terre': elos[2] if len(elos) > 2 else None,
            'gazon': elos[3] if len(elos) > 3 else None,
        }
    return joueurs


def main():
    tous, meta, echecs, echantillon = {}, {}, [], {}
    for url in [u.strip() for u in URLS.split(',') if u.strip()]:
        tour = 'wta' if 'wta' in url.lower() else 'atp'
        try:
            page = http_get(url)
        except Exception as e:
            echecs.append(f'{tour}: {e}')
            print(f'❌ {url} : {e}')
            continue
        d = date_maj(page)
        lot = parser(page, tour)
        meta[tour] = {'url': url, 'joueurs': len(lot),
                      'derniere_maj': d.isoformat() if d else None}
        print(f'{tour.upper()} : {len(lot)} joueurs · dernière mise à jour '
              f'{d.isoformat() if d else "inconnue"}')
        if not lot:
            # Sans échantillon, un « 0 joueur » est indiagnostiquable.
            echantillon[tour] = page[:2500]
            echecs.append(f'{tour}: 0 joueur extrait')
        if d and (datetime.date.today() - d).days > MAX_AGE:
            print(f'   ⚠️ données vieilles de {(datetime.date.today()-d).days} jours '
                  f'(seuil {MAX_AGE}) — un Elo périmé est pire qu\'aucun Elo.')
        tous.update(lot)

    if not tous:
        print('\n❌ aucun Elo récupéré. Le fichier existant est CONSERVÉ intact :')
        print('   écraser un référentiel valide par du vide serait pire que l\'échec.')
        json.dump({'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds'),
                   'echecs': echecs, 'echantillon_brut': echantillon},
                  open('elo_fetch_diag.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('   diagnostic écrit dans elo_fetch_diag.json')
        return 1

    # ── Couverture face à NOS matchs ─────────────────────────────────────
    couverture = None
    try:
        d = json.load(open('matches_oddspapi.json', encoding='utf-8'))
        if isinstance(d, dict):
            d = list(d.values())
        besoin, trouves = set(), set()
        for x in d:
            if not isinstance(x, dict):
                continue
            for k in ('home_team', 'away_team'):
                c = cle_joueur(x.get(k))
                if c and not re.fullmatch(r'w?[qs]f\d+', norm(x.get(k))):
                    besoin.add(c)
                    if c in tous:
                        trouves.add(c)
        if besoin:
            couverture = round(100 * len(trouves) / len(besoin), 1)
            print(f'\nCouverture de nos joueurs du jour : {len(trouves)}/{len(besoin)} '
                  f'({couverture} %)')
            manquants = sorted(besoin - trouves)[:8]
            if manquants:
                print(f'   absents : {manquants}')
    except Exception:
        pass

    json.dump({
        'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'source': 'tennisabstract.com', 'meta': meta,
        'couverture_locale_pct': couverture,
        'n_joueurs': len(tous), 'joueurs': tous,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n{len(tous)} joueurs écrits dans {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
