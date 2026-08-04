#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_books.py — Liste les bookmakers réellement disponibles avec ta clé API.

À lancer UNE FOIS (workflow manuel « Diag steam » ou en local) pour obtenir les
slugs EXACTS à mettre dans CAPTURE_BOOKS. Les slugs sont sensibles : un nom
inventé est ignoré (au mieux) ou fait échouer la requête (au pire) — ce script
supprime la devinette.

Coût : 1 requête API.

Sortie : la liste complète, puis une ligne prête à copier-coller dans le YAML,
composée des books connus pour être « lents » (utiles au repérage des écarts).
"""
import os
import oddspapi_v5 as ov

# books d'intérêt pour la couverture (référence + opérateurs grand public EU/FR)
PRIORITAIRES = [
    'pinnacle', 'betfair-ex', 'betfair', 'unibet', 'bwin', 'betsson',
    'bet365', 'williamhill', 'betway', '1xbet', 'marathonbet', 'betclic',
    'winamax', 'netbet', 'zebet', 'tipico', 'interwetten', '888sport',
    'leovegas', 'betsafe', 'nordicbet', 'comeon', 'expekt', 'coolbet',
    'vbet', 'bet-at-home', 'parionssport', 'pmu', 'olybet', 'barrierebet',
]


def main():
    books = ov.get_bookmakers("all")
    if not books:
        print("❌ aucune réponse de /bookmakers (clé API ? quota ?)")
        return
    rows = []
    for b in books:
        if isinstance(b, dict):
            slug = b.get('key') or b.get('slug') or b.get('id') or ''
            name = b.get('title') or b.get('name') or ''
        else:
            slug, name = str(b), ''
        if slug:
            rows.append((str(slug), str(name)))
    rows.sort()
    print(f"=== {len(rows)} bookmakers disponibles avec ta clé ===")
    for slug, name in rows:
        print(f"  {slug:24} {name}")

    dispo = {s for s, _ in rows}
    retenus = [s for s in PRIORITAIRES if s in dispo]
    manquants = [s for s in PRIORITAIRES if s not in dispo]
    print("\n=== À copier dans CAPTURE_BOOKS (books prioritaires réellement dispo) ===")
    print(",".join(retenus) if retenus else "(aucun des prioritaires n'est disponible)")
    if manquants:
        print(f"\n(non disponibles sur ton plan, ignorés : {', '.join(manquants)})")
    autres = sorted(dispo - set(PRIORITAIRES))
    if autres:
        print(f"\nAutres books dispo non retenus ({len(autres)}) : {', '.join(autres[:40])}"
              + (" …" if len(autres) > 40 else ""))


if __name__ == '__main__':
    main()
