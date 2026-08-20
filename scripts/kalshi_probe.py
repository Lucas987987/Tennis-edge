#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalshi_probe.py — Kalshi couvre-t-il NOS matchs ? (sonde, n'écrit aucune donnée)

POURQUOI UNE SONDE AVANT UN COLLECTEUR
Le collecteur Polymarket a coûté une journée et cinq allers-retours de
correctifs, pour découvrir à la fin que Polymarket ne cote que Cincinnati —
soit 13 matchs appariables. On inverse l'ordre cette fois : d'abord mesurer la
couverture réelle, ensuite décider s'il y a lieu de construire.

CE QUE LA SONDE RÉPOND
  1. Combien de marchés tennis Kalshi expose-t-il, et sous quels tickers de
     série ? (indispensable pour filtrer côté serveur ensuite)
  2. Combien de NOS matchs (matches_oddspapi.json) s'y retrouvent ?
  3. Ces marchés sont-ils liquides ? (volume, fourchette, intérêt ouvert)
  4. Kalshi couvre-t-il des tournois que Polymarket ignore — Challengers, ITF ?
     C'est là que se trouverait l'intérêt réel, puisque c'est le circuit où les
     bookmakers mous sont les plus lents.

ACCÈS
Aucune authentification : GET /markets, /events, /series et les carnets sont
publics. L'authentification RSA-PSS n'est requise que pour passer des ordres.
Limite : environ 20 requêtes/seconde. On pagine par curseur, avec une pause.

PRIX KALSHI
Exprimés en CENTIMES entiers de 1 à 99, et ce sont directement des
probabilités : yes_bid=62 signifie 62 %. Comme Polymarket, aucune marge à
retirer — d'où l'intérêt pour valider le dévigage de Pinnacle.
Le carnet ne publie que des offres (bids) des deux côtés : une offre No à
100-X équivaut à une demande Yes à X. Les deux côtés décrivent donc le carnet
complet.

Env : KALSHI_BASE, MATCHES_FILE, MAX_PAGES, OUT.
Usage : python scripts/kalshi_probe.py
"""
import os
import sys
import json
import time
import re
import unicodedata
import datetime
import collections
import urllib.request
import urllib.parse
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE       = os.environ.get('KALSHI_BASE', 'https://api.elections.kalshi.com/trade-api/v2')
MATCHES    = os.environ.get('MATCHES_FILE', 'matches_oddspapi.json')
# Le 1er run s'est arrêté à 25 pages x 1000 = 25 000 marchés AVEC UN CURSEUR
# ENCORE ACTIF : on ne voyait qu'une fenêtre arbitraire du catalogue Kalshi.
# « 0 tennis » ne prouvait donc rien -- le tennis pouvait être page 26.
MAX_PAGES  = int(os.environ.get('MAX_PAGES', '200'))
PAGE_LIMIT = int(os.environ.get('PAGE_LIMIT', '1000'))
OUT        = os.environ.get('OUT', 'kalshi_probe_report.json')
TIMEOUT    = float(os.environ.get('HTTP_TIMEOUT', '25'))

# Mots-clés d'identification du tennis dans les libellés Kalshi.
TENNIS_KW = ('tennis', 'atp', 'wta', 'itf', 'challenger', 'us open',
             'wimbledon', 'roland garros', 'australian open')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def toks(s):
    return set(t for t in re.split(r'[^a-z0-9]+', norm(s)) if len(t) >= 2)


def joueur_match(a, b):
    """DEUX jetons communs minimum.

    Un seul jeton commun est presque toujours un prénom partagé : « Tallon
    Griekspoor » et « Tallon Tien » ne sont pas le même joueur. Même règle que
    player_key.py, dont trois copies divergentes traînaient dans le dépôt.
    """
    return len(toks(a) & toks(b)) >= 2


def http_get(path, params=None):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'TennisEdge-KalshiProbe/1.0',
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode('utf-8'))


def matchs_locaux():
    if not os.path.exists(MATCHES):
        print(f"⚠️ {MATCHES} introuvable")
        return []
    try:
        d = json.load(open(MATCHES, encoding='utf-8'))
    except Exception as e:
        print(f"⚠️ {MATCHES} illisible : {e}")
        return []
    if isinstance(d, dict):
        d = list(d.values())
    out = []
    for x in d:
        if not isinstance(x, dict):
            continue
        h = x.get('home_team') or x.get('home')
        a = x.get('away_team') or x.get('away')
        if not h or not a:
            continue
        # Les entrées « Qf1 vs Qf2 » sont des tours futurs non encore résolus :
        # elles se rempliront au fil du tournoi, mais ne peuvent rien apparier
        # aujourd'hui. On les compte à part plutôt que de les jeter en silence.
        out.append({'home': h, 'away': a,
                    'tournoi': x.get('sport_title') or '',
                    'commence': x.get('commence_time') or '',
                    'placeholder': bool(re.fullmatch(r'w?qf\d+', norm(h)))})
    return out


def est_tennis(m):
    # Tous les champs texte : le schéma Kalshi varie selon le type de marché
    # (certains n'ont pas de 'title', seulement yes_sub_title / no_sub_title).
    blob = norm(" ".join(str(v) for v in m.values() if isinstance(v, str)))
    return any(k in blob for k in TENNIS_KW)


def main():
    print("=" * 74)
    print("SONDE KALSHI — couverture tennis face à nos matchs")
    print(f"{BASE}")
    print("=" * 74)

    locaux = matchs_locaux()
    reels = [m for m in locaux if not m['placeholder']]
    print(f"Matchs locaux : {len(locaux)} dont {len(reels)} avec joueurs nommés "
          f"({len(locaux) - len(reels)} tours futurs à venir)")

    # ── 1. Récupération paginée ──────────────────────────────────────────
    marches, cursor, pages = [], None, 0
    t0 = time.time()
    while pages < MAX_PAGES:
        params = {'status': 'open', 'limit': PAGE_LIMIT}
        if cursor:
            params['cursor'] = cursor
        try:
            d = http_get('/markets', params)
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP {e.code} sur /markets : {e.reason}")
            if e.code == 429:
                print("   (limite de débit — réessayer plus tard)")
            break
        except Exception as e:
            print(f"❌ /markets injoignable : {e}")
            break
        lot = d.get('markets') or []
        marches.extend(lot)
        pages += 1
        cursor = d.get('cursor')
        if not cursor or not lot:
            break
        time.sleep(0.1)          # ~20 req/s autorisées, on reste très en deçà

    tronque = bool(cursor) and pages >= MAX_PAGES
    print(f"Récupéré : {len(marches)} marchés ouverts en {pages} page(s), "
          f"{time.time() - t0:.1f}s")
    if tronque:
        print(f"⚠️ PAGINATION TRONQUÉE à {MAX_PAGES} pages : un curseur reste actif.")
        print("   Kalshi expose bien plus de marchés que ce qu'on a lu. Le tennis")
        print("   se trouve peut-être au-delà -- conclure ici serait une erreur.")
    if not marches:
        print("\n❌ aucun marché récupéré — API injoignable ou schéma changé.")
        return

    # SCHÉMA — à afficher TOUJOURS, pas seulement en cas de succès.
    # Le premier run a renvoyé « 0 tennis » sans le moindre indice sur la cause :
    # filtre trop strict, champ absent, ou tennis hors des 25 pages lues ?
    # C'est exactement le défaut du premier diagnostic Polymarket, qui
    # n'échantillonnait qu'un seul motif de rejet. On dumpe donc le schéma réel.
    print("\n── schéma d'un marché (clés réellement renvoyées) ──")
    print("   " + ", ".join(sorted(marches[0].keys())))
    print("\n── 3 marchés bruts, pour lecture ──")
    for m in marches[:3]:
        apercu = {k: m.get(k) for k in
                  ('ticker', 'event_ticker', 'series_ticker', 'title',
                   'subtitle', 'yes_sub_title', 'category', 'volume')
                  if k in m}
        print("   " + json.dumps(apercu, ensure_ascii=False)[:200])

    # HISTOGRAMME DES PRÉFIXES sur TOUS les marchés, pas seulement le tennis.
    # Si une série tennis existe, son préfixe apparaîtra ici même si le filtre
    # de libellé la rate -- KXATP, KXWTA, KXITF sont reconnaissables à l'œil.
    prefixes = collections.Counter(str(m.get('ticker') or '?').split('-')[0]
                                   for m in marches)
    print(f"\n── 40 préfixes de ticker les plus fréquents ({len(prefixes)} distincts) ──")
    for k, v in prefixes.most_common(40):
        marque = "  ← TENNIS ?" if any(w in k.lower() for w in
                                       ('tennis', 'atp', 'wta', 'itf', 'open')) else ""
        print(f"   {v:6}  {k}{marque}")

    tennis = [m for m in marches if est_tennis(m)]
    print(f"Dont tennis (mots-clés) : {len(tennis)}")

    # ── RECHERCHE AGNOSTIQUE AU SCHÉMA ───────────────────────────────────
    # On sérialise chaque marché en JSON et on y cherche les PATRONYMES de nos
    # joueurs, sans aucune hypothèse sur le nom des champs. Si un patronyme
    # apparaît, le tennis est présent et on découvre du même coup le champ qui
    # le porte. S'il n'apparaît nulle part, le problème est la pagination ou
    # l'endpoint -- pas le filtre.
    patronymes = {}
    for loc in reels:
        for nom in (loc['home'], loc['away']):
            bouts = [t for t in norm(nom).split() if len(t) >= 5]
            if bouts:
                patronymes[bouts[-1]] = nom
    trouves, champs = [], collections.Counter()
    for m in marches:
        blob = norm(json.dumps(m, ensure_ascii=False))
        for p in patronymes:
            if p in blob:
                trouves.append((p, m))
                for k, v in m.items():
                    if isinstance(v, str) and p in norm(v):
                        champs[k] += 1
                break
    print(f"\n── recherche par patronyme ({len(patronymes)} joueurs) ──")
    print(f"   {len(trouves)} marché(s) contiennent un de nos joueurs")
    if champs:
        print(f"   champs porteurs du nom : {dict(champs)}")
    for p, m in trouves[:6]:
        print(f"   · {p:14} {str(m.get('ticker'))[:38]:<40} {str(m.get('title'))[:52]}")

    print(f"\nDont tennis (filtre de libellé) : {len(tennis)}")

    # ── 2. Inventaire des séries : indispensable pour filtrer ensuite ────
    series = collections.Counter()
    tournois = collections.Counter()
    for m in tennis:
        tk = str(m.get('ticker') or '')
        series[tk.split('-')[0]] += 1
        ev = str(m.get('event_ticker') or '')
        tournois[ev.split('-')[0] if ev else '?'] += 1

    print("\n── séries tennis (préfixe de ticker) ──")
    for k, v in series.most_common(15):
        print(f"   {v:5}  {k}")

    # ── 3. Appariement avec NOS matchs ───────────────────────────────────
    apparies, details = {}, []
    for loc in reels:
        trouve = []
        for m in tennis:
            # TOUS les champs texte, pas une liste devinée. Le test a montré
            # que Kalshi place les deux joueurs dans yes_sub_title ET
            # no_sub_title : chercher dans un sous-ensemble choisi à la main
            # trouvait un joueur sur deux et concluait « 0 apparié » à tort.
            blob = " ".join(str(v) for v in m.values() if isinstance(v, str))
            if joueur_match(loc['home'], blob) and joueur_match(loc['away'], blob):
                trouve.append(m)
        if trouve:
            cle = f"{loc['home']} vs {loc['away']}"
            apparies[cle] = trouve
            vol = sum(int(m.get('volume') or 0) for m in trouve)
            oi = sum(int(m.get('open_interest') or 0) for m in trouve)
            spreads = []
            for m in trouve:
                yb, ya = m.get('yes_bid'), m.get('yes_ask')
                if isinstance(yb, int) and isinstance(ya, int) and ya > yb:
                    spreads.append(ya - yb)
            details.append({'match': cle, 'tournoi': loc['tournoi'],
                            'n_marches': len(trouve), 'volume': vol,
                            'open_interest': oi,
                            'spread_min_c': min(spreads) if spreads else None})

    print("\n" + "=" * 74)
    print(f"APPARIEMENT : {len(apparies)} / {len(reels)} de nos matchs nommés "
          f"trouvés sur Kalshi")
    print("=" * 74)
    if details:
        print(f"{'match':<44}{'mkts':>5}{'volume':>10}{'spread':>8}")
        print("-" * 74)
        for d in sorted(details, key=lambda x: -x['volume']):
            sp = f"{d['spread_min_c']}c" if d['spread_min_c'] is not None else "-"
            print(f"{d['match'][:43]:<44}{d['n_marches']:>5}"
                  f"{d['volume']:>10,}{sp:>8}")
    else:
        print("  aucun de nos matchs n'a été retrouvé.")

    # ── 4. Ce que Kalshi couvre EN PLUS ──────────────────────────────────
    # Le vrai enjeu : Polymarket ne cotait que Cincinnati. Si Kalshi expose
    # Challengers et ITF, il couvre le circuit où les books mous traînent le
    # plus -- et l'intérêt dépasse largement nos 23 matchs du jour.
    hors = collections.Counter()
    for m in tennis:
        blob = norm(f"{m.get('title','')} {m.get('event_ticker','')}")
        for k in ('challenger', 'itf', 'us open', 'atp', 'wta'):
            if k in blob:
                hors[k] += 1
                break
    print("\n── circuits couverts par Kalshi ──")
    for k, v in hors.most_common():
        print(f"   {v:5}  {k}")

    liq = [int(m.get('volume') or 0) for m in tennis]
    liq = [x for x in liq if x > 0]
    if liq:
        liq.sort()
        print(f"\nvolume par marché tennis : médian {liq[len(liq)//2]:,} · "
              f"max {liq[-1]:,} · {len(liq)} marchés avec volume > 0")

    # ── 5. Autres portes d'entrée ────────────────────────────────────────
    # /markets est plat et volumineux. /events regroupe par rencontre et porte
    # souvent un titre lisible ; /series liste les familles de marchés. Si le
    # tennis existe, l'une des trois le montrera.
    autres = {}
    for chemin, params in (('/events', {'status': 'open', 'limit': 200}),
                           ('/series', {}),
                           ('/series', {'category': 'Sports'})):
        cle = chemin + ('?' + urllib.parse.urlencode(params) if params else '')
        try:
            d = http_get(chemin, params)
        except urllib.error.HTTPError as e:
            autres[cle] = f"HTTP {e.code}"
            print(f"   {cle:38} HTTP {e.code}")
            continue
        except Exception as e:
            autres[cle] = str(e)[:80]
            print(f"   {cle:38} {str(e)[:60]}")
            continue
        items = d.get('events') or d.get('series') or []
        tn = [x for x in items
              if any(k in norm(json.dumps(x, ensure_ascii=False)) for k in TENNIS_KW)]
        autres[cle] = {'total': len(items), 'tennis': len(tn),
                       'exemples': [str(x.get('title') or x.get('ticker'))[:70]
                                    for x in tn[:5]]}
        print(f"   {cle:38} {len(items):5} éléments · {len(tn)} tennis")
        for x in tn[:5]:
            print(f"        · {str(x.get('title') or x.get('ticker'))[:70]}")

    json.dump({
        'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'pagination_tronquee': tronque,
        'cles_marche': sorted(marches[0].keys()),
        'prefixes_ticker': dict(prefixes.most_common(60)),
        'autres_endpoints': autres,
        'echantillon_brut': marches[:5],
        'marches_ouverts': len(marches), 'marches_tennis': len(tennis),
        'locaux_total': len(locaux), 'locaux_nommes': len(reels),
        'apparies': len(apparies),
        'series': dict(series.most_common(30)),
        'circuits': dict(hors),
        'detail_apparies': details,
        'tronque': tronque,
        'schema_cles': sorted(marches[0].keys()) if marches else [],
        'prefixes_tickers': dict(prefixes.most_common(60)),
        'echantillon_brut': marches[:5],
        'trouves_par_patronyme': [
            {k: m.get(k) for k in ('ticker', 'event_ticker', 'title', 'subtitle',
                                   'yes_sub_title', 'volume')}
            for _, m in trouves[:20]],
        'echantillon_tennis': [
            {k: m.get(k) for k in ('ticker', 'event_ticker', 'title', 'subtitle',
                                   'yes_sub_title', 'yes_bid', 'yes_ask',
                                   'volume', 'open_interest', 'close_time')}
            for m in tennis[:15]],
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nRapport écrit dans {OUT}")

    print("\n" + "=" * 74)
    if len(apparies) > len(reels) * 0.5:
        print("→ Couverture SUFFISANTE pour construire un collecteur.")
    elif tennis:
        print("→ Kalshi expose du tennis mais peu de NOS matchs. Regarder les")
        print("  séries ci-dessus : le filtre de libellé est peut-être trop strict.")
    else:
        print("→ Aucun tennis trouvé. Vérifier TENNIS_KW et l'échantillon du rapport.")
    print("=" * 74)


if __name__ == '__main__':
    main()
