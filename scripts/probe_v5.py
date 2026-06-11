#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_v5.py (v2) — Sonde OddsPapi v5 via RapidAPI, appels par curl.

Pourquoi curl : le 1er essai (urllib) a pris un "HTTP 403 / error code: 1010"
= blocage Cloudflare. curl utilise le meme fingerprint que le snippet RapidAPI
officiel, + User-Agent navigateur, pour ecarter tout blocage cote client.

REQUIS AVANT DE LANCER :
  - Etre ABONNE a OddsPapi sur RapidAPI (plan gratuit "Basic" suffit pour ce test).
  - Secret GitHub RAPIDAPI_KEY = ta cle x-rapidapi-key.

Chemins corriges d'apres le 1er run :
  - /sports, /fixtures/today, /fixtures/live = valides (transmis au backend)
  - /fixtures/filtered = N'EXISTE PAS sur RapidAPI (abandonne)
  - pas de prefixe /en sur RapidAPI

Lancement : Actions > Probe OddsPapi v5 > Run workflow.
"""

import os
import sys
import json
import subprocess

RAPIDAPI_HOST = "odds-api1.p.rapidapi.com"
BASE = f"https://{RAPIDAPI_HOST}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

KEY = (os.environ.get("RAPIDAPI_KEY")
       or os.environ.get("ODDSPAPI_RAPIDAPI_KEY")
       or os.environ.get("RAPID_API_KEY")
       or "")

MARKER = "HTTPSTATUS:"


def hr(title=""):
    print("\n" + "=" * 70)
    if title:
        print(title)
        print("=" * 70)


def call(path, params=None, label=""):
    """GET via curl. Renvoie (data|None, status:int|None)."""
    params = params or {}
    pairs = [f"{k}={v}" for k, v in params.items() if v is not None]
    qs = "&".join(pairs)
    url = f"{BASE}{path}" + (f"?{qs}" if qs else "")
    print(f"\n[{label}] GET {url}")
    cmd = [
        "curl", "-s", "-S", "-m", "30",
        "-w", f"\n{MARKER}%{{http_code}}",
        "-H", f"x-rapidapi-key: {KEY}",
        "-H", f"x-rapidapi-host: {RAPIDAPI_HOST}",
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "--user-agent", UA,
        "--url", url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except Exception as e:
        print(f"   !! curl exception: {e}")
        return (None, None)
    raw = out.stdout
    status = None
    body = raw
    if MARKER in raw:
        body, _, scode = raw.rpartition(MARKER)
        scode = scode.strip()
        status = int(scode) if scode.isdigit() else None
    body = body.strip()
    print(f"   -> HTTP {status}  ({len(body)} octets)")
    if status and status >= 400:
        print("   corps: " + body[:500])
        return (None, status)
    try:
        return (json.loads(body), status)
    except Exception:
        print("   !! reponse non-JSON, extrait:")
        print("   " + body[:500])
        return (None, status)


def find_tennis_sport(sports):
    if not isinstance(sports, list):
        return None
    ex = [s for s in sports if str(s.get("sportName", "")).strip().lower() == "tennis"]
    if ex:
        return ex[0]
    co = [s for s in sports if "tennis" in str(s.get("sportName", "")).lower()]
    return co[0] if co else None


def find_moneyline_market(markets):
    if not isinstance(markets, list):
        return None
    for m in markets:
        if str(m.get("marketType", "")).lower() == "moneyline":
            return m
    for m in markets:
        if m.get("marketLength") == 2 or len(m.get("outcomes", []) or []) == 2:
            return m
    return markets[0] if markets else None


def extract_h2h(fixture, bookmaker, mw_market_id):
    odds = (fixture.get("odds") or {}).get(bookmaker)
    if not odds:
        return None
    quotes = []
    for v in odds.values():
        if not isinstance(v, dict):
            continue
        if mw_market_id is not None and v.get("marketId") != mw_market_id:
            continue
        if v.get("playerId") not in (0, None):
            continue
        quotes.append(v)
    if len(quotes) < 2 and mw_market_id is None:
        quotes = [v for v in odds.values() if isinstance(v, dict)][:2]
    if len(quotes) < 2:
        return None
    quotes.sort(key=lambda q: (q.get("marketId", 0), q.get("outcomeId", 0)))
    h, a = quotes[0], quotes[1]
    return {"home": h.get("price"), "away": a.get("price"),
            "_home_outcomeId": h.get("outcomeId"), "_away_outcomeId": a.get("outcomeId"),
            "_marketId": h.get("marketId")}


def main():
    hr("SONDE ODDSPAPI v5 / RapidAPI (v2 curl)")
    if not KEY:
        print("❌ Pas de cle. Ajoute le secret RAPIDAPI_KEY.")
        sys.exit(1)
    print(f"Cle : {KEY[:6]}...{KEY[-4:]} (len {len(KEY)})  |  Host : {RAPIDAPI_HOST}")
    print("Rappel : il faut etre ABONNE a OddsPapi sur RapidAPI (plan Basic gratuit OK).")

    # A. sports
    hr("A. /sports")
    sports, _ = call("/sports", {}, "sports")
    tennis = None
    if isinstance(sports, list):
        print(f"   {len(sports)} sports. Echantillon :")
        for s in sports[:30]:
            print(f"     sportId={s.get('sportId')}  {s.get('sportName')}")
        tennis = find_tennis_sport(sports)
    tsid = tennis.get("sportId") if tennis else None
    if tennis:
        print(f"\n✅ Tennis sportId={tsid}")
    else:
        print("❌ Tennis introuvable (si 403/1010 ci-dessus -> abonnement manquant).")

    # B. markets
    hr("B. /markets?sportId=tennis")
    mwid = None
    if tsid is not None:
        markets, _ = call("/markets", {"sportId": tsid}, "markets")
        if isinstance(markets, list):
            print(f"   {len(markets)} marches. Echantillon :")
            for m in markets[:15]:
                print(f"     marketId={m.get('marketId')}  type={m.get('marketType')}  "
                      f"len={m.get('marketLength')}  {m.get('marketName')}  "
                      f"outcomes={[o.get('outcomeName') for o in (m.get('outcomes') or [])]}")
            mw = find_moneyline_market(markets)
            if mw:
                mwid = mw.get("marketId")
                print(f"\n✅ Marche vainqueur marketId={mwid} ({mw.get('marketName')})")

    # C. fixtures
    hr("C. Fixtures tennis")
    fixtures = None
    for path in ("/fixtures/today", "/fixtures/live", "/fixtures"):
        data, st = call(path, {"sportId": tsid}, f"fix{path}")
        lst = data if isinstance(data, list) else (data.get("fixtures") if isinstance(data, dict) else None)
        if lst:
            fixtures = lst
            print(f"   ✅ {len(lst)} fixtures via {path}")
            break
    fid = tid = None
    if fixtures:
        print("   Echantillon :")
        for f in fixtures[:8]:
            pr = f.get("participants", {})
            print(f"     fixtureId={f.get('fixtureId')}  "
                  f"tournoi={(f.get('tournament') or {}).get('tournamentName')}"
                  f"({(f.get('tournament') or {}).get('tournamentId')})  "
                  f"{pr.get('participant1Name')} vs {pr.get('participant2Name')}")
        fid = fixtures[0].get("fixtureId")
        tid = (fixtures[0].get("tournament") or {}).get("tournamentId")
    else:
        print("   ⚠️ Aucun fixture (aucun match tennis aujourd'hui, ou abonnement/param).")

    # D. odds main
    hr("D. /fixtures/odds/main (Pinnacle) -- LE PLUS IMPORTANT")
    if tid is not None:
        data, _ = call("/fixtures/odds/main", {"tournamentId": tid, "bookmakers": "pinnacle"}, "odds/main")
        lst = data if isinstance(data, list) else (data.get("fixtures") if isinstance(data, dict) else None)
        if lst:
            tgt = next((f for f in lst if f.get("fixtureId") == fid), lst[0])
            pr = tgt.get("participants", {})
            print(f"\n   fixtureId={tgt.get('fixtureId')}")
            print(f"   participant1(home)={pr.get('participant1Name')} (id {pr.get('participant1Id')})")
            print(f"   participant2(away)={pr.get('participant2Name')} (id {pr.get('participant2Id')})")
            print(f"   startTime(unix s)={tgt.get('startTime')}")
            print(f"\n   ODDS BRUTES pinnacle :")
            print("   " + json.dumps((tgt.get('odds') or {}).get('pinnacle') or {}, indent=2)[:2200])
            print(f"\n   bookmakers presents : {list((tgt.get('odds') or {}).keys())}")
            print(f"\n   ✅ EXTRACTION home/away -> {json.dumps(extract_h2h(tgt, 'pinnacle', mwid))}")
            print("   (home doit = cote participant1 ; away = participant2)")
        else:
            print("   ⚠️ Pas de fixtures avec cotes.")
    else:
        print("   (saute : pas de tournamentId)")

    # E. historical
    hr("E. /fixtures/odds/historical (CLV)")
    if fid:
        data, _ = call("/fixtures/odds/historical", {"fixtureId": fid, "bookmaker": "pinnacle"}, "odds/hist")
        pinn = ((data or {}).get("odds", {}) or {}).get("pinnacle", {}) if isinstance(data, dict) else {}
        if pinn:
            print(f"   {len(pinn)} series :")
            for oid, serie in list(pinn.items())[:4]:
                ts = sorted(serie.keys()) if isinstance(serie, dict) else []
                if ts:
                    print(f"     {oid} : {len(ts)} pts | outcomeId={serie[ts[0]].get('outcomeId')} | "
                          f"open={serie[ts[0]].get('price')} -> close={serie[ts[-1]].get('price')}")
        else:
            print("   ⚠️ Pas de serie pinnacle (match sans historique encore).")
    else:
        print("   (saute : pas de fixtureId)")

    # F. tournois du jour (slug/categorie) -> pour caler le filtre ATP/WTA
    hr("F. Tournois tennis du jour (slug + categorie) -- POUR LE FILTRE ATP/WTA")
    catalog = {}
    tours, _ = call("/tournaments", {"sportId": tsid}, "tournaments")
    if isinstance(tours, list):
        for t in tours:
            catalog[str(t.get("tournamentId"))] = t
        print(f"   (catalogue tennis: {len(catalog)} tournois)")
    counts = {}
    for f in (fixtures or []):
        tr = f.get("tournament") or {}
        pr = f.get("participants") or {}
        blob = (f"{tr.get('tournamentName','')} {pr.get('participant1Name','')} "
                f"{pr.get('participant2Name','')}").lower()
        if "srl" in blob:
            continue
        k = str(tr.get("tournamentId"))
        counts[k] = counts.get(k, 0) + 1
    print(f"   {len(counts)} tournois tennis (hors SRL) avec match aujourd'hui :")
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        t = catalog.get(k, {})
        print(f"     id={k}  n={n}  name={t.get('tournamentName')}  "
              f"slug={t.get('tournamentSlug')}  cat={t.get('categoryName')}  "
              f"catSlug={t.get('categorySlug')}")

    hr("FIN — colle TOUT le log a Claude (surtout la section F).")


if __name__ == "__main__":
    main()
