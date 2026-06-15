#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
steam_diag.py — Pourquoi pas d'alerte ? Diagnostic complet de la chaine steam.

Pour chaque surface (MARKET) : etat des courbes live, et pour chaque match A VENIR,
le verdict detaille (mouvement Pinnacle, book mou, seuil franchi ?, valeur ?, lead ?).
Option TEST_PING=1 : envoie un message Telegram de test pour valider le tuyau,
independamment de tout signal.

Usage (workflow_dispatch ou local) :
  CURVES=book_curves_live.jsonl MARKET=match python scripts/steam_diag.py
  TEST_PING=1 python scripts/steam_diag.py     # test Telegram seul
Env : memes que steam_alert (CURVES, MARKET, GRID, MIN_N, WINDOW_DAYS, MIN_LEAD...).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steam_alert as sa


def main():
    # 0. Tuyau Telegram
    print(f"== Telegram == token:{'OUI' if sa.TOKEN else 'NON'} chat:{'OUI' if sa.CHAT else 'NON'} "
          f"DRY_RUN:{sa.DRY_RUN}")
    if os.environ.get('TEST_PING') == '1':
        if sa.TOKEN and sa.CHAT:
            try:
                sa.send("✅ Test steam_diag : le tuyau Telegram fonctionne.")
                print("   -> message de test ENVOYE (verifie ton Telegram).")
            except Exception as e:
                print(f"   -> ECHEC envoi : {e}")
        else:
            print("   -> token/chat absents : impossible d'envoyer. Verifie les secrets du workflow.")

    # 1. Etat des courbes
    print(f"\n== Courbes == fichier:{sa.CURVES} | existe:{os.path.exists(sa.CURVES)} | MARKET:{os.environ.get('MARKET','match')}")
    data = sa.load_curves()
    now = sa._now()
    if not data:
        print("   AUCUNE courbe chargee. Causes probables : fichier absent/vide, ou <2 points par cote.")
        print("   -> la capture doit avoir tourne plusieurs cycles sur des matchs A VENIR.")
        return
    books = sorted({b for m in data.values() for b in m if not b.startswith('_')})
    upcoming = {u: bk for u, bk in data.items() if bk.get('_commence') and bk['_commence'] >= now}
    past = {u: bk for u, bk in data.items() if bk.get('_commence') and bk['_commence'] < now}
    print(f"   total:{len(data)} | a venir:{len(upcoming)} | passes(track record):{len(past)} | books:{books}")
    softbooks = [b for b in books if b != sa.SHARP]
    if sa.SHARP not in books:
        print(f"   ⚠ {sa.SHARP} (sharp) ABSENT des courbes -> aucune detection possible.")
        return
    if not softbooks:
        print("   ⚠ aucun book mou a cote de Pinnacle -> rien a suivre.")
        return

    stats = sa.compute_stats(past, softbooks)
    thr = {sb: sa.best_threshold(stats, sb) for sb in softbooks}
    print("   seuils/book :", ", ".join(f"{sb}>={int(thr[sb][0]*100)}pt" + ("" if thr[sb][1] else "?ind") for sb in softbooks))

    if not upcoming:
        print("\n   Aucun match A VENIR dans les courbes -> rien a alerter (normal hors heures de match).")
        return

    # 2. Verdict par match a venir
    print(f"\n== {len(upcoming)} matchs a venir ==")
    for u, bk in list(upcoming.items())[:25]:
        lead = bk['_commence'] - now
        pin = bk.get(sa.SHARP)
        line = f" • {bk.get('_home')} vs {bk.get('_away')} | depart {sa.fmt_lead(lead)}"
        if not pin:
            print(line + " | ⛔ pas de Pinnacle"); continue
        times = sorted(set(t for t, _ in pin['h']))
        if len(times) < 2:
            print(line + f" | ⛔ Pinnacle a 1 seul point (pas de trajectoire)"); continue
        f0, fn = sa._fair(pin, times[0]), sa._fair(pin, times[-1])
        mv = (fn - f0) if (f0 and fn) else 0
        line += f" | Pinnacle move {mv*100:+.1f}pt"
        if lead < sa.MIN_LEAD * 60:
            print(line + f" | ⛔ lead < {int(sa.MIN_LEAD)}min"); continue
        verdicts = []
        fired = False
        for sb in softbooks:
            if sb not in bk:
                continue
            mvthr = thr[sb][0]
            d = sa.detect(pin, mvthr)
            if not d:
                verdicts.append(f"{sb}:move<{int(mvthr*100)}pt"); continue
            _, side = d
            pf = sa._fair(pin, times[-1])
            pfair = (pf if side == 'home' else 1 - pf) if pf else None
            ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
            cur = ser[-1][1] if ser else None
            if not cur:
                verdicts.append(f"{sb}:pas de cote"); continue
            ev = (cur * pfair - 1) if pfair else None
            if ev is not None and ev < sa.EV_MIN_NOW:
                verdicts.append(f"{sb}:EV {ev*100:+.0f}%<{int(sa.EV_MIN_NOW*100)}"); continue
            verdicts.append(f"✅{sb}@{cur:.2f}(EV{ev*100:+.0f}%)"); fired = True
        print(line + (" | ALERTE: " if fired else " | ") + " ".join(verdicts))
    print("\nLecture : ✅ = aurait alerte. Sinon la raison est indiquee par book.")


if __name__ == '__main__':
    main()
