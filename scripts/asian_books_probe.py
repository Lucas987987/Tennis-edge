#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asian_books_probe.py — Singbet et SBOBet sont-ils accessibles, et mènent-ils
Pinnacle ? (sonde, n'écrit aucune donnée de production)

L'HYPOTHÈSE
Tennis Edge calcule son « juste prix » sur Pinnacle. Mais Pinnacle n'est qu'un
des trois books du trio sharp : Singbet (Crown) et SBOBet encaissent le flux
des syndicats asiatiques, avec des limites bien supérieures. Si quelque chose
anticipe Pinnacle, c'est plus probablement eux qu'un marché de prédiction.

Or les 19 books qui répondent réellement chez nous sont TOUS européens ou
français — aucun asiatique. Ce n'est pas un réglage : c'est ce que le
fournisseur sert.

CE QUE CETTE SONDE VÉRIFIE, DANS L'ORDRE
  1. Les slugs singbet / sbobet existent-ils dans le catalogue /bookmakers ?
  2. Renvoient-ils réellement des cotes sur NOS matchs de tennis ?
  3. Leurs prix diffèrent-ils de Pinnacle, et dans quel sens ?
Une réponse négative à l'étape 1 ou 2 clôt le sujet sans rien coder de plus.

POURQUOI C'EST IMPORTANT QU'ILS PASSENT PAR L'API
Singbet n'a pas de site public : l'accès direct exige un agent (BetInAsia,
VOdds, VIP-IBC), avec dépôt minimum et compte limitable. Passer par
l'agrégateur qui a déjà le flux évite tout compte chez un opérateur non agréé
en France — le point bloquant qui rendait cette piste inenvisageable.

CE QU'ELLE NE PROUVE PAS
Qu'ils mènent Pinnacle. Un écart de prix instantané n'est pas une avance
temporelle : les deux peuvent simplement avoir des marges différentes. La
mesure du lead/lag demande des séries temporelles et un test de permutation —
c'est polymarket_leadlag.py qui fait ça, une fois qu'on sait que les données
existent.

Env : RAPIDAPI_KEY, ASIAN_SLUGS, OUT.
Usage : python scripts/asian_books_probe.py
"""
import os
import sys
import json
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SLUGS = [s.strip() for s in os.environ.get(
    'ASIAN_SLUGS',
    'singbet,sbobet,sbobet-asia,crown,ibcbet,matchbook,orbit,'
    'sharp-exchange,fair999,piwi247,4casters').split(',') if s.strip()]
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
MATCHES = os.environ.get('MATCHES_FILE', 'matches_oddspapi.json')
OUT = os.environ.get('OUT', 'asian_books_probe_report.json')


def main():
    print("=" * 74)
    print("SONDE — books sharp asiatiques chez OddsPapi")
    print("=" * 74)

    # ── 1. Le catalogue les connaît-il ? ─────────────────────────────────
    try:
        catalogue = ov.get_bookmakers("all")
    except Exception as e:
        print(f"❌ /bookmakers injoignable : {e}")
        print("   (RAPIDAPI_KEY absente ou endpoint indisponible sur cette formule)")
        return 1

    if isinstance(catalogue, dict):
        catalogue = catalogue.get('bookmakers') or list(catalogue.values())
    connus = {}
    for b in (catalogue or []):
        if isinstance(b, dict):
            k = b.get('bookmakerSlug') or b.get('slug') or b.get('key') or b.get('name')
        else:
            k = str(b)
        if k:
            connus[str(k).lower()] = b
    print(f"catalogue : {len(connus)} bookmakers exposés par l'API\n")

    presents = [s for s in SLUGS if s.lower() in connus]
    absents = [s for s in SLUGS if s.lower() not in connus]
    print(f"  recherchés : {SLUGS}")
    print(f"  ✅ présents au catalogue : {presents or 'aucun'}")
    print(f"  ❌ absents               : {absents or 'aucun'}")

    # Filet : un slug peut porter un autre nom (crown, ibc...). On cherche
    # aussi par sous-chaîne, sinon un simple écart de nommage ferait conclure
    # à tort à l'absence — l'erreur commise sur la sonde Kalshi.
    proches = sorted(k for k in connus
                     if any(x in k for x in ('sbo', 'sing', 'crown', 'ibc',
                                             'asia', 'orbit', 'sharp', 'piwi',
                                             'fair', 'caster', 'matchbook')))
    if proches:
        print(f"\n  slugs approchants dans le catalogue : {proches}")

    if not presents and not proches:
        print("\n❌ aucun book asiatique au catalogue. Le sujet est clos :")
        print("   il faudrait un autre fournisseur, ou un courtier — donc un")
        print("   compte chez un opérateur non agréé en France. À éviter.")
        json.dump({'catalogue': len(connus), 'presents': [], 'proches': []},
                  open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return 0

    # ── 2. Renvoient-ils des cotes sur NOS matchs ? ──────────────────────
    # Le catalogue peut lister un book sans qu'il cote le tennis, ou sans que
    # notre formule y donne accès. Seul un appel réel tranche.
    a_tester = presents + [p for p in proches if p not in presents]
    demande = ','.join([SHARP] + a_tester)
    print()
    print("=" * 74)
    print(f"COTES RÉELLES — {demande}")
    print("=" * 74)

    try:
        locaux = json.load(open(MATCHES, encoding='utf-8'))
        if isinstance(locaux, dict):
            locaux = list(locaux.values())
    except Exception as e:
        print(f"❌ {MATCHES} illisible : {e}")
        return 1
    fids = [str(m.get('id') or m.get('fixture_id')) for m in locaux
            if isinstance(m, dict) and (m.get('id') or m.get('fixture_id'))]
    if not fids:
        print("❌ aucun fixture_id local — relancer après une capture.")
        return 1
    print(f"{len(fids)} match(s) local(aux) à interroger\n")

    vus = collections.Counter()
    comparaisons = []
    try:
        for fo in ov.odds_main_by_fixtures(fids[:40], demande):
            books = {b['key']: b for b in ov.all_books_h2h(fo)}
            for k in books:
                vus[k] += 1
            ref = books.get(SHARP)
            if not ref:
                continue
            for k, b in books.items():
                if k == SHARP:
                    continue
                try:
                    ih, ia = 1 / float(ref['home']), 1 / float(ref['away'])
                    p_ref = ih / (ih + ia)
                    jh, ja = 1 / float(b['home']), 1 / float(b['away'])
                    p_b = jh / (jh + ja)
                except (TypeError, ValueError, ZeroDivisionError):
                    continue
                comparaisons.append({
                    'book': k,
                    'ecart_pts': (p_b - p_ref) * 100,
                    'marge_ref': (ih + ia - 1) * 100,
                    'marge_book': (jh + ja - 1) * 100,
                })
    except Exception as e:
        print(f"❌ appel odds échoué : {e}")
        return 1

    if not vus:
        print("❌ aucune cote renvoyée. Les books existent au catalogue mais ne")
        print("   cotent pas nos matchs, ou la formule n'y donne pas accès.")
        return 0

    print(f"{'book':<20}{'matchs cotés':>13}{'marge moy':>11}{'écart vs ' + SHARP:>18}")
    print("-" * 74)
    par_book = collections.defaultdict(list)
    for c in comparaisons:
        par_book[c['book']].append(c)
    import statistics as st
    marge_ref = st.mean(c['marge_ref'] for c in comparaisons) if comparaisons else 0
    print(f"{SHARP:<20}{vus.get(SHARP, 0):>13}{marge_ref:>10.2f}%{'—':>18}")
    for k in sorted(par_book, key=lambda x: -vus[x]):
        lot = par_book[k]
        m = st.mean(c['marge_book'] for c in lot)
        e = st.median(c['ecart_pts'] for c in lot)
        asiatique = any(x in k for x in ('sbo', 'sing', 'crown', 'ibc', 'asia'))
        print(f"{k:<20}{vus[k]:>13}{m:>10.2f}%{e:>+17.2f}"
              + ("  ← ASIATIQUE" if asiatique else ""))

    trouves = [k for k in vus if any(x in k for x in
               ('sbo', 'sing', 'crown', 'ibc', 'asia'))]
    print()
    print("=" * 74)
    if trouves:
        print(f"→ {len(trouves)} book(s) sharp asiatique(s) EXPLOITABLE(S) : {trouves}")
        print("  Étape suivante : les ajouter à CAPTURE_BOOKS, accumuler quelques")
        print("  jours de courbes, puis mesurer le lead/lag face à Pinnacle avec")
        print("  polymarket_leadlag.py — variations et test de permutation.")
        print("  ⚠️ un écart de prix N'EST PAS une avance temporelle : deux books")
        print("     peuvent différer par leur seule marge.")
    else:
        print("→ aucun book asiatique ne cote nos matchs. Sujet clos sans risque.")
    print("=" * 74)

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'catalogue': len(connus), 'presents': presents, 'proches': proches,
        'books_cotant': dict(vus), 'asiatiques_exploitables': trouves,
        'ecarts': {k: {'n': len(v),
                       'ecart_median_pts': round(st.median(c['ecart_pts'] for c in v), 3),
                       'marge_moy_pct': round(st.mean(c['marge_book'] for c in v), 3)}
                   for k, v in par_book.items()},
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
