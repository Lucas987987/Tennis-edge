#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tournaments_probe.py — Quelles catégories de tournois existe-t-il, et que
coûterait leur suivi ? (sonde, n'écrit aucune donnée de production)

LE PROBLÈME
capture_closing ne suit que les tournois dont le categorySlug vaut « atp » ou
« wta » (TRACK_CATEGORY_SLUGS). Les Challengers et l'ITF ont leurs propres
slugs et sont donc écartés à la découverte — d'où « 2 tournois actifs » alors
que tournois_ids.json contient déjà des Challengers (Bratislava, Ilkley, Lyon,
Tucuman) rencontrés par le passé.

POURQUOI ÇA COMPTE MAINTENANT
Kalshi cote les Challengers et l'ITF (séries KXATPCHALLENGERMATCH, KXITFMATCH),
et c'est précisément le circuit où les opérateurs mous sont les plus lents,
donc là où Tennis Edge a le plus de valeur. Mais notre univers local s'arrête
à l'ATP/WTA : on ne peut rien apparier.

POURQUOI UNE SONDE PLUTÔT QU'UN ÉLARGISSEMENT DIRECT
On ne connaît pas les libellés exacts des slugs. Les deviner (« challenger »,
« atp-challenger », « itf-men »...) donnerait un filtre qui ne capte rien, EN
SILENCE — le mode de panne habituel de ce projet. Cette sonde liste les slugs
réels et chiffre ce que chacun ajouterait.

ELLE MESURE AUSSI LE COÛT
Ajouter des tournois multiplie les matchs suivis, donc les requêtes API, la
taille de closing_lines.json et le volume de courbes. Le rapport donne le
nombre de matchs du jour par catégorie pour décider en connaissance de cause.

Usage : python scripts/tournaments_probe.py
Sortie : tournaments_probe_report.json
"""
import os
import sys
import json
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SPORT_ID = int(os.environ.get('TENNIS_SPORT_ID', '12'))
OUT = os.environ.get('OUT', 'tournaments_probe_report.json')
ACTUELS = set(s.strip().lower() for s in
              os.environ.get('TRACK_CATEGORY_SLUGS', 'atp,wta').split(',') if s.strip())


def main():
    print("=" * 74)
    print("SONDE — catégories de tournois OddsPapi")
    print(f"actuellement suivies : {sorted(ACTUELS)}")
    print("=" * 74)

    catalog = ov.get_tournaments(SPORT_ID)
    if not catalog:
        print("❌ /tournaments a échoué — clé RAPIDAPI_KEY absente ou API HS.")
        return 1
    print(f"catalogue : {len(catalog)} tournois\n")

    # ── 1. Inventaire des slugs ──────────────────────────────────────────
    par_slug = collections.defaultdict(list)
    for t in catalog:
        cs = str(t.get('categorySlug') or '?').lower()
        nom = str(t.get('tournamentName') or '')
        par_slug[cs].append((str(t.get('tournamentId')), nom,
                             str(t.get('categoryName') or '')))

    print(f"{'categorySlug':<28}{'tournois':>9}  exemple")
    print("-" * 74)
    for cs, lot in sorted(par_slug.items(), key=lambda x: -len(x[1])):
        marque = ' ← suivi' if cs in ACTUELS else ''
        print(f"{cs:<28}{len(lot):>9}  {lot[0][1][:32]}{marque}")

    # ── 2. Ce qui a des matchs AUJOURD'HUI ───────────────────────────────
    # Le catalogue liste tout l'historique ; seul compte ce qui est actif.
    actifs = collections.Counter()
    tid2slug = {}
    for cs, lot in par_slug.items():
        for tid, nom, _ in lot:
            tid2slug[tid] = cs
    try:
        fixtures = ov.fixtures_today(SPORT_ID)
    except Exception as e:
        print(f"\n⚠️ fixtures_today a échoué : {e}")
        fixtures = []
    srl = 0
    for f in fixtures:
        if ov.is_srl(f):
            srl += 1
            continue
        tid = str(f.get('tournamentId') or '')
        cs = tid2slug.get(tid)
        if cs:
            actifs[cs] += 1

    print()
    print("=" * 74)
    print(f"MATCHS DU JOUR par catégorie ({len(fixtures)} fixtures, {srl} SRL écartées)")
    print("=" * 74)
    total_suivi = sum(v for k, v in actifs.items() if k in ACTUELS)
    total_hors = sum(v for k, v in actifs.items() if k not in ACTUELS)
    for cs, n in actifs.most_common():
        marque = ' ← DÉJÀ suivi' if cs in ACTUELS else ''
        print(f"   {cs:<28}{n:>5} match(s){marque}")
    print("-" * 74)
    print(f"   {'suivis ce jour':<28}{total_suivi:>5}")
    print(f"   {'NON suivis':<28}{total_hors:>5}")
    if total_suivi:
        print(f"\n→ élargir à tout multiplierait le volume par "
              f"{(total_suivi + total_hors) / total_suivi:.1f}")
        print("  (requêtes API, closing_lines.json, courbes historiques)")

    # ── 3. Où sont Challengers et ITF ? ──────────────────────────────────
    print()
    print("=" * 74)
    print("SLUGS CONTENANT CHALLENGER / ITF")
    print("=" * 74)
    trouve = False
    for cs, lot in sorted(par_slug.items()):
        blob = (cs + ' ' + ' '.join(x[2] for x in lot[:3])).lower()
        if 'challenger' in blob or 'itf' in blob:
            trouve = True
            print(f"   slug « {cs} » · {len(lot)} tournois · "
                  f"{actifs.get(cs, 0)} match(s) aujourd'hui")
            for tid, nom, cat in lot[:3]:
                print(f"       {nom[:60]}")
    if not trouve:
        print("   aucun slug ne mentionne Challenger ni ITF.")
        print("   → soit OddsPapi ne les couvre pas, soit ils sont noyés dans")
        print("     un slug générique. Voir l'inventaire complet ci-dessus.")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'suivis_actuellement': sorted(ACTUELS),
        'slugs': {cs: {'tournois': len(lot), 'actifs_aujourdhui': actifs.get(cs, 0),
                       'exemples': [x[1] for x in lot[:5]]}
                  for cs, lot in par_slug.items()},
        'matchs_suivis': total_suivi, 'matchs_non_suivis': total_hors,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
