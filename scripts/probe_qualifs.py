#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_qualifs.py — Vérifie si l'API distingue les tableaux de QUALIFICATIONS
du tableau principal, et localise les marchés SECONDAIRES disponibles.

Deux questions :
1. Un tournoi de qualifs a-t-il un tournamentId séparé, ou un champ dédié
   (categoryName, stage...) qui permet de les filtrer ? Sans ça, impossible
   de les étudier séparément du tableau principal.
2. Quels marchés secondaires (au-delà de Winner/Set1/Set2) sont RÉELLEMENT
   cotés sur un match tennis type -- total games, handicap games, player
   props -- pour préparer leur capture éventuelle.

Coût : 3-4 requêtes API.
"""
import os, re
import oddspapi_v5 as ov

QUAL_HINTS = ('qual', 'quali', 'q-')


def check_tournaments():
    trs = ov.get_tournaments()
    print(f"=== {len(trs)} tournois au catalogue ATP/WTA ===")
    quals = [t for t in trs if isinstance(t, dict) and
             any(h in str(t.get('name') or t.get('tournamentName') or '').lower() for h in QUAL_HINTS)]
    print(f"Tournois dont le NOM contient 'qual' : {len(quals)}")
    for t in quals[:10]:
        print(f"  {t}")
    if not quals:
        print("  Aucun -> les quals ne sont probablement PAS un tournoi séparé,")
        print("  elles font partie du même tournamentId que le tableau principal.")
    print("\n--- structure d'une entrée tournoi (pour voir les champs dispo) ---")
    if trs:
        for k, v in list(trs[0].items())[:15]:
            print(f"  {k:20} = {repr(v)[:60]}")


def check_fixture_stage():
    """Un fixture individuel a-t-il un champ indiquant qualif/main draw/round ?"""
    items = ov.fixtures_today() or []
    print(f"\n=== {len(items)} matchs tennis aujourd'hui : cherche un champ 'stage'/'round' ===")
    stage_fields = set()
    for f in items[:50]:
        if not isinstance(f, dict): continue
        for k in f.keys():
            if any(w in k.lower() for w in ('stage', 'round', 'qual', 'draw', 'phase')):
                stage_fields.add(k)
    if stage_fields:
        print(f"  champs candidats trouvés : {stage_fields}")
        for f in items[:5]:
            for k in stage_fields:
                if k in f: print(f"    {f.get('fixtureId')}: {k} = {f[k]}")
    else:
        print("  Aucun champ round/stage/qual trouvé sur /fixtures/today.")
        print("  Toutes les clés disponibles sur un fixture :")
        if items:
            print(f"    {sorted(items[0].keys())}")


def check_secondary_markets():
    """Marchés réellement cotés sur des matchs À VENIR CONFIRMÉS (pas terminés,
    pas sans cotes), au-delà de Winner/Set1/Set2. Le 1er essai prenait les 3
    premiers matchs du jour sans vérifier leur statut -> résultat vide possible
    si ces matchs étaient déjà finis ou sans marché actif."""
    import datetime as _dt
    now = _dt.datetime.utcnow()
    items = ov.fixtures_today() or []
    upcoming, parse_fail, past = [], 0, 0
    sample_raw = None
    for f in items:
        if not isinstance(f, dict): continue
        st = f.get('startTime')
        if sample_raw is None:
            sample_raw = st
        try:
            # startTime peut etre un timestamp Unix (secondes) OU une chaine ISO
            # selon l'endpoint -> on gere les deux formats.
            if isinstance(st, (int, float)) or (isinstance(st, str) and st.isdigit()):
                t = _dt.datetime.utcfromtimestamp(int(st))
            else:
                t = _dt.datetime.fromisoformat(str(st).replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            parse_fail += 1
            continue
        if t > now:
            upcoming.append((t, f.get('fixtureId') or f.get('id')))
        else:
            past += 1
    upcoming.sort()
    fids = [fid for _, fid in upcoming[:10] if fid]
    print(f"\n=== diagnostic sur {len(items)} fixtures : {len(upcoming)} à venir, "
          f"{past} passés, {parse_fail} non parsés ===")
    print(f"  exemple de startTime brut : {sample_raw!r}")
    print(f"  now (UTC) utilisé pour comparer : {now.isoformat()}")
    print(f"  test sur {len(fids)} matchs\n")
    if not fids:
        # filet de secours : si tout est "passe" a cause d'un decalage de format/fuseau,
        # on prend quand meme les fixtures dont le statut n'indique pas "termine"
        alt = []
        for f in items:
            if not isinstance(f, dict): continue
            status = f.get('status') or {}
            if isinstance(status, dict) and not status.get('live') and not status.get('finished'):
                fid = f.get('fixtureId') or f.get('id')
                if fid: alt.append(fid)
        fids = alt[:10]
        print(f"  filet de secours (statut != live/finished) : {len(fids)} matchs")
        if not fids:
            print("  Toujours rien -> impossible de tester les marchés secondaires cette fois.")
            return
    data = ov.odds_main_by_fixtures(fids, "pinnacle,bet365,unibet.fr,winamax.fr,bwin,betsson,1xbet")
    fixtures = data if isinstance(data, list) else (data.get('fixtures') or data.get('data') or [])
    seen = {}
    KNOWN = {121, 123, 125}
    total_entries = 0
    for fixture in fixtures:
        odds = fixture.get('odds') or {}
        for bk, entries in odds.items():
            if not isinstance(entries, dict): continue
            for _k, v in entries.items():
                if not isinstance(v, dict): continue
                total_entries += 1
                mid = v.get('marketId')
                if mid in KNOWN: continue
                seen.setdefault(mid, set()).add(bk)
    print(f"  {len(fixtures)} fixtures reçus | {total_entries} entrées de cote au total\n")
    if seen:
        print("  Marchés secondaires trouvés :")
        for mid, books in sorted(seen.items(), key=lambda x: -len(x[1]))[:25]:
            print(f"    marketId {mid} : coté par {len(books)} book(s) -> {sorted(books)}")
    else:
        print("  Aucun marché hors 121/123/125 trouvé, même sur des matchs à venir confirmés.")
        print("  -> ces opérateurs ne cotent probablement QUE vainqueur/set1/set2 sur cette API,")
        print("     ou les marchés secondaires n'apparaissent que très près du match (à retester")
        print("     sur un match démarrant dans <2h plutôt que dans plusieurs heures).")


if __name__ == '__main__':
    check_tournaments()
    check_fixture_stage()
    check_secondary_markets()
