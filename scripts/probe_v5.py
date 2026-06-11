#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_v5.py — Sonde OddsPapi v5 via RapidAPI.

But : appeler l'API v5 UNE fois sur chaque endpoint clé et imprimer les vraies
reponses dans les logs Actions, pour :
  1) confirmer que l'auth RapidAPI marche (ta cle),
  2) confirmer les vrais chemins RapidAPI,
  3) voir le format reel d'un match tennis (participants + odds Pinnacle),
  4) valider l'extraction home/away avant de migrer le reste.

Aucune dependance pip : urllib uniquement.

Secret requis (Settings > Secrets > Actions) :
  RAPIDAPI_KEY   = ta cle x-rapidapi-key
(ou ODDSPAPI_RAPIDAPI_KEY / RAPID_API_KEY, le script teste les 3 noms)

Lancement : workflow_dispatch (bouton "Run workflow").
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

# --------------------------------------------------------------------------
# Config RapidAPI (host confirme par le snippet cURL de Lucas)
# --------------------------------------------------------------------------
RAPIDAPI_HOST = "odds-api1.p.rapidapi.com"
BASE = f"https://{RAPIDAPI_HOST}"

KEY = (os.environ.get("RAPIDAPI_KEY")
       or os.environ.get("ODDSPAPI_RAPIDAPI_KEY")
       or os.environ.get("RAPID_API_KEY")
       or "")

HEADERS = {
    "x-rapidapi-key": KEY,
    "x-rapidapi-host": RAPIDAPI_HOST,
    "Content-Type": "application/json",
}


def hr(title=""):
    print("\n" + "=" * 70)
    if title:
        print(title)
        print("=" * 70)


def call(path, params=None, label=""):
    """
    GET sur BASE+path. Renvoie (data, status, url_utilisee).
    Repli automatique : si 404 sur '/x', reessaie '/en/x' (prefixe langue v5).
    Imprime URL, status, et un extrait du corps en cas d'erreur.
    """
    params = params or {}
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    candidates = [path]
    if not path.startswith("/en"):
        candidates.append("/en" + path)  # repli prefixe langue

    last = (None, None, None)
    for p in candidates:
        url = f"{BASE}{p}" + (f"?{qs}" if qs else "")
        print(f"\n[{label}] GET {url}")
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
                raw = r.read().decode("utf-8", "replace")
                print(f"   -> HTTP {status}  ({len(raw)} octets)")
                try:
                    data = json.loads(raw)
                except Exception:
                    print("   !! reponse non-JSON, extrait:")
                    print("   " + raw[:500])
                    return (None, status, url)
                return (data, status, url)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            print(f"   -> HTTP {e.code}  (erreur)")
            if body:
                print("   corps: " + body[:500])
            last = (None, e.code, url)
            if e.code == 404:
                continue  # tente le repli /en
            return last
        except Exception as e:
            print(f"   !! exception: {type(e).__name__}: {e}")
            last = (None, None, url)
            continue
    return last


def find_tennis_sport(sports):
    """Trouve l'objet sport 'Tennis' dans la liste renvoyee par /sports."""
    if not isinstance(sports, list):
        return None
    # priorite a un nom == 'Tennis' exact, sinon contient 'tennis'
    exact = [s for s in sports if str(s.get("sportName", "")).strip().lower() == "tennis"]
    if exact:
        return exact[0]
    contains = [s for s in sports if "tennis" in str(s.get("sportName", "")).lower()]
    return contains[0] if contains else None


def find_moneyline_market(markets):
    """Trouve le marche vainqueur (moneyline, 2 issues) dans /markets."""
    if not isinstance(markets, list):
        return None
    for m in markets:
        if str(m.get("marketType", "")).lower() == "moneyline":
            return m
    # repli : 1er marche a 2 issues
    for m in markets:
        if m.get("marketLength") == 2 or len(m.get("outcomes", []) or []) == 2:
            return m
    return markets[0] if markets else None


def extract_h2h(fixture, bookmaker, mw_market_id):
    """
    Reproduit l'extraction cible : depuis fixture['odds'][bookmaker],
    garde le marche vainqueur (mw_market_id), trie les 2 outcomes par outcomeId
    -> home = plus petit outcomeId (== marketId), away = l'autre.
    Renvoie {'home': prix, 'away': prix} ou None.
    """
    odds = (fixture.get("odds") or {}).get(bookmaker)
    if not odds:
        return None
    quotes = []
    for v in odds.values():
        if not isinstance(v, dict):
            continue
        mid = v.get("marketId")
        if mw_market_id is not None and mid != mw_market_id:
            continue
        if v.get("playerId") not in (0, None):
            continue  # marche non-joueur uniquement
        quotes.append(v)
    if len(quotes) < 2:
        # si on n'a pas filtre par marche (mw inconnu), prendre les 2 1ers actifs
        if mw_market_id is None:
            quotes = [v for v in odds.values() if isinstance(v, dict)][:2]
        if len(quotes) < 2:
            return None
    quotes.sort(key=lambda q: (q.get("marketId", 0), q.get("outcomeId", 0)))
    home, away = quotes[0], quotes[1]
    return {
        "home": home.get("price"),
        "away": away.get("price"),
        "_home_outcomeId": home.get("outcomeId"),
        "_away_outcomeId": away.get("outcomeId"),
        "_marketId": home.get("marketId"),
    }


def main():
    hr("SONDE ODDSPAPI v5 / RapidAPI")
    if not KEY:
        print("❌ Aucune cle trouvee. Ajoute le secret RAPIDAPI_KEY dans GitHub.")
        sys.exit(1)
    print(f"Cle detectee : {KEY[:6]}...{KEY[-4:]} (longueur {len(KEY)})")
    print(f"Host : {RAPIDAPI_HOST}")

    # -- A. Sports -> tennis --------------------------------------------------
    hr("A. /sports  (trouver le sportId tennis)")
    sports, st, _ = call("/sports", {}, "sports")
    tennis = None
    if isinstance(sports, list):
        print(f"   {len(sports)} sports renvoyes. Echantillon :")
        for s in sports[:25]:
            print(f"     sportId={s.get('sportId')}  {s.get('sportName')}")
        tennis = find_tennis_sport(sports)
    if not tennis:
        print("❌ Tennis introuvable dans /sports. STOP (le reste depend de ce sportId).")
        # on continue quand meme pour voir les autres endpoints en erreur
    else:
        print(f"\n✅ Tennis : sportId={tennis.get('sportId')}  nom={tennis.get('sportName')}")
    tennis_sport_id = tennis.get("sportId") if tennis else None

    # -- B. Markets -> moneyline ---------------------------------------------
    hr("B. /markets?sportId=tennis  (trouver le marche vainqueur)")
    mw_market_id = None
    if tennis_sport_id is not None:
        markets, st, _ = call("/markets", {"sportId": tennis_sport_id}, "markets")
        if isinstance(markets, list):
            print(f"   {len(markets)} marches tennis. Echantillon :")
            for m in markets[:15]:
                print(f"     marketId={m.get('marketId')}  type={m.get('marketType')}  "
                      f"len={m.get('marketLength')}  nom={m.get('marketName')}  "
                      f"outcomes={[o.get('outcomeName') for o in (m.get('outcomes') or [])]}")
            mw = find_moneyline_market(markets)
            if mw:
                mw_market_id = mw.get("marketId")
                print(f"\n✅ Marche vainqueur : marketId={mw_market_id}  "
                      f"type={mw.get('marketType')}  nom={mw.get('marketName')}")

    # -- C. Fixtures tennis ---------------------------------------------------
    hr("C. Fixtures tennis  (recuperer un match + son tournamentId)")
    fixtures = None
    for path in ("/fixtures/today", "/fixtures/filtered", "/fixtures/live"):
        data, st, _ = call(path, {"sportId": tennis_sport_id}, f"fixtures{path}")
        if isinstance(data, list) and data:
            fixtures = data
            print(f"   ✅ {len(data)} fixtures via {path}")
            break
        elif isinstance(data, dict) and data.get("fixtures"):
            fixtures = data["fixtures"]
            print(f"   ✅ {len(fixtures)} fixtures via {path} (sous cle 'fixtures')")
            break
    sample_fixture_id = None
    sample_tournament_id = None
    if fixtures:
        print("   Echantillon de matchs :")
        for f in fixtures[:8]:
            pr = f.get("participants", {})
            print(f"     fixtureId={f.get('fixtureId')}  "
                  f"tournoi={(f.get('tournament') or {}).get('tournamentName')} "
                  f"({(f.get('tournament') or {}).get('tournamentId')})  "
                  f"{pr.get('participant1Name')} vs {pr.get('participant2Name')}  "
                  f"start={f.get('startTime')}")
        f0 = fixtures[0]
        sample_fixture_id = f0.get("fixtureId")
        sample_tournament_id = (f0.get("tournament") or {}).get("tournamentId")
    else:
        print("   ⚠️ Aucun fixture tennis trouve (peut-etre aucun match aujourd'hui, "
              "ou param a ajuster). On verra les chemins testes ci-dessus.")

    # -- D. Odds Main (Pinnacle) ---------------------------------------------
    hr("D. /fixtures/odds/main  (cotes Pinnacle du match) -- LE PLUS IMPORTANT")
    if sample_tournament_id is not None:
        data, st, _ = call("/fixtures/odds/main",
                           {"tournamentId": sample_tournament_id, "bookmakers": "pinnacle"},
                           "odds/main")
        flist = data if isinstance(data, list) else (data.get("fixtures") if isinstance(data, dict) else None)
        if flist:
            print(f"   {len(flist)} fixtures avec cotes.")
            target = None
            for f in flist:
                if f.get("fixtureId") == sample_fixture_id:
                    target = f
                    break
            target = target or flist[0]
            pr = target.get("participants", {})
            print(f"\n   --- MATCH ANALYSE ---")
            print(f"   fixtureId={target.get('fixtureId')}")
            print(f"   participant1 (home)={pr.get('participant1Name')} (id {pr.get('participant1Id')})")
            print(f"   participant2 (away)={pr.get('participant2Name')} (id {pr.get('participant2Id')})")
            print(f"   startTime(unix s)={target.get('startTime')}")
            print(f"\n   --- ODDS BRUTES (pinnacle) ---")
            raw = (target.get("odds") or {}).get("pinnacle") or {}
            print("   " + json.dumps(raw, indent=2)[:2000])
            print(f"\n   --- bookmakers presents : {list((target.get('odds') or {}).keys())}")
            h2h = extract_h2h(target, "pinnacle", mw_market_id)
            print(f"\n   ✅ EXTRACTION home/away -> {json.dumps(h2h)}")
            print("   (verifier : home doit etre la cote du participant1, away celle du participant2)")
        else:
            print("   ⚠️ Pas de liste de fixtures exploitable dans la reponse.")
    else:
        print("   (saute : pas de tournamentId d'exemple)")

    # -- E. Historical (CLV) --------------------------------------------------
    hr("E. /fixtures/odds/historical  (courbe Pinnacle pour le CLV)")
    if sample_fixture_id:
        data, st, _ = call("/fixtures/odds/historical",
                           {"fixtureId": sample_fixture_id, "bookmaker": "pinnacle"},
                           "odds/historical")
        odds = (data or {}).get("odds", {}) if isinstance(data, dict) else {}
        pinn = odds.get("pinnacle", {})
        if pinn:
            print(f"   {len(pinn)} series (oddsIds) pour pinnacle :")
            for odds_id, serie in list(pinn.items())[:4]:
                ts = sorted(serie.keys()) if isinstance(serie, dict) else []
                if ts:
                    first = serie[ts[0]]
                    last = serie[ts[-1]]
                    print(f"     {odds_id}")
                    print(f"        {len(ts)} points | "
                          f"outcomeId={first.get('outcomeId')} | "
                          f"ouverture={first.get('price')} (@{ts[0]}ms) "
                          f"-> closing={last.get('price')} (@{ts[-1]}ms)")
        else:
            print("   ⚠️ Pas de serie pinnacle (match peut-etre sans historique encore).")
    else:
        print("   (saute : pas de fixtureId d'exemple)")

    hr("FIN — colle TOUT ce log a Claude pour finaliser le client v5.")


if __name__ == "__main__":
    main()
