#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalshi_probe.py — Kalshi couvre-t-il NOS matchs ? (sonde, n'écrit aucune donnée)

CE QUE LES DEUX PREMIERS RUNS ONT APPRIS
  1. Paginer /markets est SANS ESPOIR : 199 319 des 200 000 marchés lus étaient
     des KXMVECROSSCATEGORY, c'est-à-dire des paris combinés multi-jambes
     (« yes A's, yes Seattle, yes Sabalenka... »). Soit 99,7 % de bruit, et le
     curseur n'était toujours pas épuisé. C'est aussi pourquoi la recherche par
     patronyme remontait 27 499 « résultats » : Sabalenka apparaît dans des
     milliers de combinés, jamais comme match simple.
  2. /series est le BON point d'entrée : 13 305 séries, dont 178 tennis.
     On interroge ensuite /markets?series_ticker=X, ciblé et peu coûteux.
  3. Le schéma réel n'a rien à voir avec la documentation généraliste :
     yes_bid_dollars, no_bid_dollars, volume_fp, open_interest_fp,
     liquidity_dollars -- et non yes_bid / volume / open_interest.

D'où cette version : découverte par séries, puis marchés série par série.

Env : KALSHI_BASE, MATCHES_FILE, MAX_SERIES, OUT.
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

BASE       = os.environ.get('KALSHI_BASE', 'https://api.elections.kalshi.com/trade-api/v2')
MATCHES    = os.environ.get('MATCHES_FILE', 'matches_oddspapi.json')
MAX_SERIES = int(os.environ.get('MAX_SERIES', '250'))
OUT        = os.environ.get('OUT', 'kalshi_probe_report.json')
TIMEOUT    = float(os.environ.get('HTTP_TIMEOUT', '25'))
# 0,06 s (16 req/s) provoquait 55 rejets 429 sur 134 séries. 0,3 s = ~3 req/s.
PAUSE      = float(os.environ.get('KALSHI_PAUSE_S', '0.3'))

TENNIS_KW = ('tennis', 'atp', 'wta', 'itf', 'challenger', 'wimbledon',
             'us open', 'roland garros', 'australian open', 'slam')
# Séries à écarter : elles portent sur autre chose que le vainqueur du match.
# Séries écartées : elles ne portent pas sur le vainqueur d'un match de tennis.
# Les trois dernières familles sont des FAUX POSITIFS observés au 1er run :
# « TT Elite Series Table Tennis » (tennis de table), « Freestyle Chess Grand
# Slam » (le mot « slam »), « Reputation (Taylor's Version) ».
HORS_SUJET = ('total', 'spread', 'doubles', 'game winner', 'set ', 'ranked',
              'winner (', 'championship', 'job cuts', 'qualify', 'field winner',
              'table tennis', 'tt elite', 'chess', 'reputation', 'announce')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def toks(s):
    return set(t for t in re.split(r'[^a-z0-9]+', norm(s)) if len(t) >= 2)


def joueur_match(nom, blob):
    """DEUX jetons communs minimum : un seul est presque toujours un prénom
    partagé (« Tallon Griekspoor » vs « Tallon Tien »). Même règle que
    player_key.py."""
    return len(toks(nom) & toks(blob)) >= 2


def txt(m):
    """Tout le texte d'un objet, sans présumer du nom des champs — le schéma
    Kalshi varie et certains marchés n'ont pas de 'title'."""
    return " ".join(str(v) for v in m.values() if isinstance(v, str))


def http_get(path, params=None, essais=4):
    """GET avec repli exponentiel sur 429.

    La limite publique non authentifiée est bien plus basse que les ~20 req/s
    annoncés pour les comptes autorisés : à 16 req/s, 55 séries sur 134 sont
    tombées en 429 -- dont KXATPMATCH, la série principale des matchs ATP.
    Un 429 non retenté équivaut à une donnée perdue en silence.
    """
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'TennisEdge-KalshiProbe/3.0'})
    for i in range(essais):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < essais - 1:
                time.sleep(1.5 * (2 ** i))      # 1,5s · 3s · 6s
                continue
            raise


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
        out.append({'home': h, 'away': a,
                    'tournoi': x.get('sport_title') or '',
                    'commence': x.get('commence_time') or '',
                    # Tours futurs, qui se rempliront au fil du tournoi.
                    # Le motif doit couvrir Qf, WQF, SF, WSF... ET porter sur
                    # LES DEUX joueurs : « Iga Swiatek vs Qf8 » a un joueur
                    # nommé mais un adversaire inconnu, donc il ne peut
                    # s'apparier à rien. Ne tester que `home` gonflait le
                    # dénominateur et faisait afficher 4/7 là où le vrai taux
                    # sur les matchs complets était de 4/4.
                    'placeholder': bool(re.fullmatch(r'w?[qs]f\d+', norm(h))
                                        or re.fullmatch(r'w?[qs]f\d+', norm(a)))})
    return out


def prix(m, cle):
    """Kalshi renvoie des dollars (0-1) dans *_dollars. Les anciennes clés en
    centimes n'existent plus : les lire donnait None partout, donc aucun
    spread ni volume dans le rapport précédent."""
    for k in (f'{cle}_dollars', cle):
        v = m.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        return f if f <= 1.5 else f / 100.0
    return None


def entier(m, *cles):
    for k in cles:
        v = m.get(k)
        if v is None:
            continue
        try:
            return int(float(v))
        except (TypeError, ValueError):
            continue
    return 0


def main():
    print("=" * 76)
    print("SONDE KALSHI — découverte par SÉRIES (et non par pagination globale)")
    print(BASE)
    print("=" * 76)

    locaux = matchs_locaux()
    reels = [m for m in locaux if not m['placeholder']]
    print(f"Matchs locaux : {len(locaux)} dont {len(reels)} nommés "
          f"({len(locaux) - len(reels)} tours à venir)")
    for m in reels:
        print(f"   · {m['home']} vs {m['away']}  ({m['tournoi']})")

    # ── 1. Séries tennis ─────────────────────────────────────────────────
    try:
        d = http_get('/series')
    except Exception as e:
        print(f"❌ /series injoignable : {e}")
        return
    series = d.get('series') or (d if isinstance(d, list) else [])
    print(f"\n/series : {len(series)} séries")

    tennis_s = [s for s in series if any(k in norm(txt(s)) for k in TENNIS_KW)]
    print(f"   dont tennis : {len(tennis_s)}")
    singles = [s for s in tennis_s
               if not any(k in norm(txt(s)) for k in HORS_SUJET)]

    # PRIORITÉ. Le budget de requêtes est limité par le 429 : il faut interroger
    # d'abord ce qui a le plus de chances de contenir des matchs à l'unité.
    # Une série dont le TICKER se termine par MATCH (KXATPMATCH,
    # KXWTACHALLENGERMATCH...) est exactement ce qu'on cherche ; au 1er run,
    # KXATPMATCH est tombée en 429 et n'a jamais été lue.
    def rang(s):
        tk = norm(s.get('ticker'))
        ti = norm(s.get('title'))
        if tk.endswith('match'):
            return 0
        if 'match' in tk:
            return 1
        if 'match' in ti:
            return 2
        return 3
    singles.sort(key=rang)
    print(f"   dont vainqueur de match probable : {len(singles)} "
          f"(totals/spreads/doubles écartés)")
    for s in singles[:20]:
        print(f"      {str(s.get('ticker')):<28} {str(s.get('title'))[:44]}")

    # ── 2. Marchés, série par série ──────────────────────────────────────
    marches, erreurs, trop_vite = [], 0, 0
    cibles = (singles or tennis_s)[:MAX_SERIES]
    print(f"\nInterrogation de {len(cibles)} série(s)…")
    for i, s in enumerate(cibles, 1):
        tk = s.get('ticker')
        if not tk:
            continue
        try:
            r = http_get('/markets', {'series_ticker': tk,
                                      'status': 'open', 'limit': 200})
            marches.extend(r.get('markets') or [])
        except urllib.error.HTTPError as e:
            erreurs += 1
            if e.code == 429:
                trop_vite += 1
            if erreurs <= 5:
                print(f"   ⚠️ {tk} : HTTP {e.code}")
        except Exception as e:
            erreurs += 1
            if erreurs <= 5:
                print(f"   ⚠️ {tk} : {e}")
        time.sleep(PAUSE)         # cadence prudente : cf. note http_get
    print(f"   {len(marches)} marché(s) ouvert(s) récupéré(s), {erreurs} erreur(s)"
          + (f" dont {trop_vite} × 429" if trop_vite else ""))
    if trop_vite:
        print(f"   ⚠️ {trop_vite} série(s) perdue(s) sur limite de débit malgré les")
        print("      relances — augmenter KALSHI_PAUSE_S au prochain run.")

    if not marches:
        print("\n❌ aucun marché ouvert sur les séries tennis.")
        print("   Soit aucun match en cours, soit les séries de simple portent")
        print("   un libellé que HORS_SUJET écarte à tort — voir le rapport.")
        json.dump({'series_tennis': [s.get('ticker') for s in tennis_s],
                   'echantillon_series': tennis_s[:20]},
                  open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        return

    print("\n── schéma réel ──")
    print(f"   {sorted(marches[0].keys())}")
    for m in marches[:3]:
        print(f"   · {str(m.get('ticker'))[:44]:<46}{str(m.get('title'))[:44]}")

    # ── 3. Appariement, PAR ÉVÉNEMENT ────────────────────────────────────
    # Chez Kalshi, un marché = UN RÉSULTAT, pas un match :
    #   KXATPCHALLENGERMATCH-26AUG20GOMPAP-PAP -> « Radu Mihai Papoe wins »
    #   KXATPCHALLENGERMATCH-26AUG20GOMPAP-GOM -> « Norbert Gombos wins »
    # Chaque libellé ne nomme donc qu'UN SEUL joueur. Exiger que les deux
    # joueurs apparaissent dans le MÊME marché était impossible par
    # construction : c'est ce qui plafonnait l'appariement à 2 sur 7.
    # L'unité correcte est l'ÉVÉNEMENT (event_ticker), qui regroupe les
    # marchés d'une même rencontre. On apparie donc sur le texte cumulé de
    # l'événement.
    par_event = collections.defaultdict(list)
    for m in marches:
        par_event[str(m.get('event_ticker') or m.get('ticker'))].append(m)
    print(f"\n{len(par_event)} événement(s) distinct(s) pour {len(marches)} marchés "
          f"({len(marches)/max(1,len(par_event)):.1f} marchés par événement)")

    details = {}
    for loc in reels:
        trouve = []
        for ev, lot in par_event.items():
            blob = " ".join(txt(m) for m in lot)
            if joueur_match(loc['home'], blob) and joueur_match(loc['away'], blob):
                trouve.extend(lot)
        if not trouve:
            continue
        spreads = []
        for m in trouve:
            b, a = prix(m, 'yes_bid'), prix(m, 'yes_ask')
            if b is not None and a is not None and a > b:
                spreads.append((a - b) * 100)
        details[f"{loc['home']} vs {loc['away']}"] = {
            'tournoi': loc['tournoi'], 'n_marches': len(trouve),
            'volume': sum(entier(m, 'volume_fp', 'volume') for m in trouve),
            'open_interest': sum(entier(m, 'open_interest_fp', 'open_interest')
                                 for m in trouve),
            'spread_min_pts': round(min(spreads), 1) if spreads else None,
            'tickers': [m.get('ticker') for m in trouve][:6]}

    print("\n" + "=" * 76)
    print(f"APPARIEMENT : {len(details)} / {len(reels)} de nos matchs nommés")
    print("=" * 76)
    if details:
        print(f"{'match':<42}{'mkts':>5}{'volume':>12}{'spread':>9}")
        print("-" * 76)
        for k, v in sorted(details.items(), key=lambda x: -x[1]['volume']):
            sp = f"{v['spread_min_pts']}pt" if v['spread_min_pts'] is not None else "-"
            print(f"{k[:41]:<42}{v['n_marches']:>5}{v['volume']:>12,}{sp:>9}")
    else:
        print("  aucun apparié — comparer nos joueurs aux libellés ci-dessus.")

    json.dump({
        'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'n_series': len(series), 'n_series_tennis': len(tennis_s),
        'n_series_simple': len(singles), 'n_marches': len(marches),
        'locaux_nommes': len(reels), 'apparies': len(details),
        'series_simple': [{'ticker': s.get('ticker'), 'title': s.get('title')}
                          for s in singles[:60]],
        'schema_cles': sorted(marches[0].keys()),
        'echantillon_marches': marches[:5],
        'detail': details,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nRapport écrit dans {OUT}")

    print("\n" + "=" * 76)
    if len(details) >= max(1, len(reels) * 0.5):
        print("→ Couverture SUFFISANTE : un collecteur a du sens.")
    elif marches:
        print("→ Kalshi cote du tennis mais peu de NOS matchs. Vérifier si les")
        print("  séries de simple sont écartées à tort par HORS_SUJET.")
    print("=" * 76)


if __name__ == '__main__':
    main()
