#!/usr/bin/env python3
"""sonde_courbes.py — UNE requête : l'API sert-elle encore la courbe d'un match passé ?

    python scripts/sonde_courbes.py 2026-10-14 [book]

Prend un match commencé ce jour-là dans closing_lines (archives comprises),
demande sa courbe historique (défaut : pinnacle) et affiche le nombre de points.
Sert à savoir si le rattrapage des matchs de la pause (14 → 26/10) est possible.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402
import closing_store  # noqa: E402


def main():
    jour = sys.argv[1] if len(sys.argv) > 1 else '2026-10-14'
    book = sys.argv[2] if len(sys.argv) > 2 else 'pinnacle'
    closing = closing_store.load_all('closing_lines.json', max_age_days=None)
    cands = [(m.get('commence_time', ''), m) for m in closing.values()
             if str(m.get('commence_time', '')).startswith(jour) and (m.get('fixture_id') or m.get('id'))]
    if not cands:
        print(f"❌ aucun match du {jour} dans closing_lines (archives comprises)")
        return 1
    ct, m = sorted(cands, key=lambda x: x[0])[len(cands) // 2]
    fid = m.get('fixture_id') or m.get('id')
    print(f"Match : {m.get('home')} – {m.get('away')} · {m.get('tournament')} · début {ct} · fixture {fid} · {book}")
    curves = ov.historical_curves(fid, book, (ov.OUT_HOME, ov.OUT_AWAY), with_limit=True)
    h, a = curves.get(ov.OUT_HOME) or [], curves.get(ov.OUT_AWAY) or []
    q = ov.QUOTA
    print(f"Requêtes réseau envoyées : {ov.REQUETES_RESEAU} · quota restant : {q.get('remaining')} / {q.get('limit')}")
    if h and a:
        t = lambda p: datetime.datetime.utcfromtimestamp(int(p[0]) / 1000).isoformat(timespec='minutes')
        print(f"✅ Courbe servie : {len(h)} points / {len(a)} points, du {t(h[0])} au {t(h[-1])}.")
        print("   Le rattrapage des matchs de la pause est possible.")
        return 0
    print("⚠️ Courbe vide : l'API ne sert plus ce match (ou le book ne le cotait pas).")
    print("   Essayer un autre book ou un jour plus récent avant de conclure.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
