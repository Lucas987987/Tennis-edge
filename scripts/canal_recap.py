#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_recap.py — Récap hebdomadaire du canal « Évolution des cotes ».

Publie chaque semaine un bilan VÉRIFIABLE des évolutions signalées :
  - combien de mouvements publiés,
  - dans quelle proportion les prix « en retard » signalés se sont ensuite
    resserrés vers le juste prix avant le match (convergence), et de combien,
  - les plus gros mouvements de la semaine.

Tout est reconstruit depuis canal_public_log.jsonl (ce qui a été publié,
horodaté) + les courbes (ce que le marché a fait ensuite) : chaque chiffre du
récap correspond à des messages publics antérieurs — c'est le principe du
canal : transparence totale, y compris les semaines où le marché ne converge
pas. Aucun vocabulaire d'incitation, pied de page 18+.

Env : LOG, CURVES, DAYS (7), TELEGRAM_TOKEN, TELEGRAM_PUBLIC_CHAT_ID, DRY_RUN.
"""
import os, json, datetime, statistics as st, urllib.request, urllib.parse

LOG    = os.environ.get('LOG', 'canal_public_log.jsonl')
CURVES = os.environ.get('CURVES', 'book_curves_live.jsonl')
DAYS   = int(os.environ.get('DAYS', '7'))
TOKEN  = os.environ.get('TELEGRAM_TOKEN', '')
CHAT   = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY    = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Récap d'information sur les marchés de cotes — pas un conseil. "
          "Chaque ligne correspond à un message publié en amont sur ce canal.\n"
          "18+ | joueurs-info-service.fr · 09 74 75 13 13")


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def close_price(uid, book, side_name):
    """Dernier prix pré-match du book pour le joueur signalé (par nom)."""
    if not os.path.exists(CURVES):
        return None
    for line in open(CURVES, encoding='utf-8'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('uid') != uid or r.get('book') != book:
            continue
        ct = _dt(r.get('commence_time'))
        home = r.get('home_team') or r.get('home') or ''
        key = 'home_curve' if home == side_name else 'away_curve'
        pts = [(_dt(x[0]), x[1]) for x in (r.get(key) or []) if _dt(x[0]) and x[1]]
        pts = sorted(x for x in pts if ct is None or x[0] < ct)
        return pts[-1][1] if pts else None
    return None


def tg_send(text):
    if DRY:
        print("--- DRY RUN ---")
        print(text)
        return
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=urllib.parse.urlencode({'chat_id': CHAT, 'text': text,
                                     'disable_web_page_preview': 'true'}).encode())
    urllib.request.urlopen(req, timeout=15)


def main():
    now = datetime.datetime.utcnow()
    cut = now - datetime.timedelta(days=DAYS)
    rows = []
    if os.path.exists(LOG):
        for line in open(LOG, encoding='utf-8'):
            try:
                r = json.loads(line)
            except Exception:
                continue
            t = _dt(r.get('t'))
            if t and t >= cut:
                rows.append(r)
    if not rows:
        print("récap : aucune évolution publiée sur la période")
        return
    conv = []
    for r in rows:
        for b, price, gap in (r.get('retards') or []):
            cl = close_price(r['uid'], b, r['joueur'])
            if cl and price:
                conv.append((price / cl - 1) * 100)   # >0 = le prix signalé s'est resserré
    biggest = sorted(rows, key=lambda r: -(r.get('cote_ref_avant', 0) - r.get('cote_ref_apres', 0))
                     / max(r.get('cote_ref_avant', 1), 1))[:3]
    lines = [f"📈 RÉCAP DE LA SEMAINE — évolutions de cotes tennis",
             f"• {len(rows)} mouvements significatifs signalés (paliers 5/8/12 pts)"]
    if conv:
        pos = 100 * sum(1 for x in conv if x > 0) / len(conv)
        lines.append(f"• Prix « en retard » signalés : {len(conv)} · "
                     f"{pos:.0f}% se sont resserrés ensuite · resserrement médian {st.median(conv):+.1f}%")
    lines.append("• Plus gros mouvements de la semaine (indépendant d'un retard détecté) :")
    for r in biggest:
        drop = (r['cote_ref_avant'] - r['cote_ref_apres']) / r['cote_ref_avant'] * 100
        lines.append(f"   – {r['joueur']} : {r['cote_ref_avant']:.2f} → {r['cote_ref_apres']:.2f} (−{drop:.0f}%)")
    lines.append("Note : ces mouvements figurent ici pour leur ampleur — un opérateur n'y était "
                 "pas forcément en retard au moment du signal (ligne 🏪 absente = tous avaient déjà "
                 "ajusté). Les écarts avec un vrai retard détecté sont ceux du récap 📊 quotidien.")
    lines.append("Méthodo : mouvements mesurés sur le prix de référence (Pinnacle), "
                 "juste prix par dévig Shin, données horodatées — tout est rejouable.")
    tg_send("\n".join(lines) + FOOTER)
    print(f"récap publié : {len(rows)} mouvements, {len(conv)} prix suivis")


if __name__ == '__main__':
    main()
