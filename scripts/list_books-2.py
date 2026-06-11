#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
list_books.py (v5) — Découvre les bookmakers disponibles pour comparer les cotes.

1) Catalogue complet (/bookmakers) avec drapeau "dispo en France".
2) Sur un VRAI match tennis à venir, liste les books qui cotent le marché vainqueur
   (1 appel odds/main, bookmakers=all) + leurs cotes home/away.
3) Propose une ligne CAPTURE_BOOKS prête à coller (Pinnacle + books FR qui cotent).

Env : RAPIDAPI_KEY (obligatoire). FIXTURE_ID (optionnel, force un match précis).
Lecture : closing_lines.json (pour piocher un match à venir) — sinon fixtures du jour.
Lancement : workflow_dispatch.
"""

import os
import json
import datetime
import oddspapi_v5 as ov

CLOSING_FILE = 'closing_lines.json'
FIXTURE_ID = os.environ.get('FIXTURE_ID', '')


def _parse_dt(s):
    try:
        return datetime.datetime.fromisoformat((s or '').replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def pick_fixture():
    """fixtureId d'un match À VENIR : env FIXTURE_ID > closing_lines.json > fixtures du jour."""
    if FIXTURE_ID:
        return FIXTURE_ID, "(FIXTURE_ID env)"
    now = datetime.datetime.utcnow()
    if os.path.exists(CLOSING_FILE):
        try:
            closing = json.load(open(CLOSING_FILE, encoding='utf-8'))
            cand = []
            for uid, m in closing.items():
                fid = m.get('fixture_id') or m.get('id')
                dt = _parse_dt(m.get('commence_time', ''))
                if fid and dt and dt > now:
                    cand.append((dt, fid, f"{m.get('home')} vs {m.get('away')}"))
            cand.sort()
            if cand:
                return cand[0][1], cand[0][2]
        except Exception:
            pass
    # repli : 1er match tennis du jour non-SRL a venir
    for f in ov.fixtures_today():
        if ov.is_srl(f):
            continue
        st = f.get('startTime')
        try:
            if st and datetime.datetime.utcfromtimestamp(int(st)) > now:
                pr = f.get('participants', {})
                return f.get('fixtureId'), f"{pr.get('participant1Name')} vs {pr.get('participant2Name')}"
        except Exception:
            continue
    return None, None


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return

    # 1) Catalogue + dispo FR
    cat = ov.get_bookmakers("all")
    fr = {}
    for b in cat:
        slug = b.get('slug')
        ac = b.get('availableCountries')
        in_fr = ('fr' in ac) if isinstance(ac, list) else None  # None = inconnu/global
        fr[slug] = {'name': b.get('bookmakerName'), 'fr': in_fr, 'active': b.get('active')}
    print(f"📚 Catalogue: {len(cat)} bookmakers disponibles pour ta cle.")

    # 2) Books cotant un vrai match tennis
    fid, label = pick_fixture()
    if not fid:
        print("⚠️ Aucun match a venir trouve (lance apres une capture, ou mets FIXTURE_ID).")
        return
    print(f"\n🎾 Match temoin : {label}  (fixtureId={fid})")
    books = ov.books_for_fixture(fid, "all")   # {slug: (home, away)}
    if not books:
        print("⚠️ Aucun book ne cote ce match (peut-etre deja commence). Mets un FIXTURE_ID a venir.")
        return

    rows = []
    for slug, (h, a) in books.items():
        meta = fr.get(slug, {})
        flag = 'FR' if meta.get('fr') is True else ('-' if meta.get('fr') is False else '?')
        rows.append((slug, meta.get('name') or slug, flag, h, a))
    rows.sort(key=lambda r: (r[2] != 'FR', r[0]))   # FR d'abord
    print(f"\n{len(rows)} books cotent ce match (marche vainqueur) :")
    print(f"  {'slug':<18} {'nom':<22} FR   home / away")
    for slug, name, flag, h, a in rows:
        print(f"  {slug:<18} {name[:22]:<22} {flag:<3}  {h} / {a}")

    # 3) Suggestion CAPTURE_BOOKS : pinnacle (sharp) + books FR qui cotent
    fr_books = [slug for slug, _n, flag, _h, _a in rows if flag == 'FR']
    suggested = ['pinnacle'] + [s for s in fr_books if s != 'pinnacle']
    if len(suggested) <= 1:   # repli si aucun FR detecte : tout ce qui cote
        suggested = ['pinnacle'] + [s for s in books.keys() if s != 'pinnacle']
    seen, uniq = set(), []
    for s in suggested:
        if s not in seen:
            seen.add(s); uniq.append(s)
    print("\n  >>> a coller dans capture_closing.yml (env) :")
    print(f"      CAPTURE_BOOKS: {','.join(uniq)}")
    print("  >>> et dans fetch_book_curves.yml (env) pour les courbes :")
    print(f"      BOOKS: {','.join(uniq)}")


if __name__ == '__main__':
    main()
