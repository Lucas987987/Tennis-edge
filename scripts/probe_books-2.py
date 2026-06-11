#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
probe_books.py (v5) — Diagnostic : pour un match temoin, dit quels books ont un
historique exploitable (/fixtures/odds/historical) et combien de points.
Utile pour choisir BOOKS avant fetch_book_curves.

Env : RAPIDAPI_KEY. FIXTURE_ID (optionnel). BOOKS (def "pinnacle,unibet,bwin,betsson,winamax,betclic").
"""

import os, json, datetime
import oddspapi_v5 as ov

CLOSING_FILE = 'closing_lines.json'
FIXTURE_ID = os.environ.get('FIXTURE_ID', '')
BOOKS = [b.strip() for b in os.environ.get('BOOKS', 'pinnacle,unibet,bwin,betsson,winamax,betclic').split(',') if b.strip()]


def pick_fixture():
    if FIXTURE_ID:
        return FIXTURE_ID
    now = datetime.datetime.utcnow()
    if os.path.exists(CLOSING_FILE):
        try:
            closing = json.load(open(CLOSING_FILE, encoding='utf-8'))
            cand = []
            for uid, m in closing.items():
                fid = m.get('fixture_id') or m.get('id')
                ct = m.get('commence_time', '')
                try:
                    dt = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
                if fid and dt < now:   # match deja commence -> a un historique
                    cand.append((dt, fid))
            cand.sort(reverse=True)
            if cand:
                return cand[0][1]
        except Exception:
            pass
    return None


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    fid = pick_fixture()
    if not fid:
        print("⚠️ Aucun match commence trouve (mets FIXTURE_ID)."); return
    print(f"Match temoin : fixtureId={fid}\n")
    print(f"  {'book':<16} pts(home/away)  ouverture->closing(home)")
    for book in BOOKS:
        try:
            c = ov.historical_curves(fid, book, (ov.OUT_HOME, ov.OUT_AWAY))
        except Exception as e:
            print(f"  {book:<16} ERREUR: {e}"); continue
        ch = c.get(ov.OUT_HOME, []); ca = c.get(ov.OUT_AWAY, [])
        if ch:
            print(f"  {book:<16} {len(ch)}/{len(ca):<10}  {ch[0][1]} -> {ch[-1][1]}")
        else:
            print(f"  {book:<16} 0/0          (pas d'historique pour ce book)")


if __name__ == '__main__':
    main()
