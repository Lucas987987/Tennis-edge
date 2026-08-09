#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_clv_recap.py — Récap HEBDO PUBLIÉ du CLV réalisé (le vrai track record).

Différent de canal_recap.py (qui liste les plus GROS mouvements, indépendamment
d'un retard détecté) : ici on résume la performance des écarts RÉELLEMENT
signalés (ligne 🏪 présente), sur les 7 derniers jours -- c'est la preuve
condensée en un message hebdomadaire, complémentaire du suivi quotidien
(canal_suivi.py) qui ne couvre qu'un jour à la fois.

Réutilise load_closes() de canal_clv.py pour ne pas dupliquer la logique de
mesure (prix signalé vs dernier prix pré-match du même opérateur).

Env : LOG (canal_public_log.jsonl), CURVES, DAYS (7), MIN_ROWS (10),
      TELEGRAM_TOKEN, TELEGRAM_PUBLIC_CHAT_ID, DRY_RUN, REPO_URL.
"""
import os, json, datetime, statistics as st, urllib.request, urllib.parse
import canal_clv as _clv   # réutilise load_closes() : même mesure, une seule source de vérité

LOG      = os.environ.get('LOG', 'canal_public_log.jsonl')
DAYS     = int(os.environ.get('DAYS', '7'))
MIN_ROWS = int(os.environ.get('MIN_ROWS', '10'))
REPO_URL = os.environ.get('REPO_URL', '')
TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
CHAT     = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY      = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Bilan de prix uniquement : prix signalé comparé au dernier prix "
          "pré-match du même opérateur. Aucun résultat de match, aucun gain. "
          "Ceci n'est pas un conseil.\n"
          "18+ | joueurs-info-service.fr · 09 74 75 13 13")


def tg(text):
    if DRY:
        print("--- DRY RUN ---\n" + text)
        return
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=urllib.parse.urlencode({'chat_id': CHAT, 'text': text,
                                     'disable_web_page_preview': 'true'}).encode())
    urllib.request.urlopen(req, timeout=15)


def main():
    if not os.path.exists(LOG):
        print(f"{LOG} introuvable"); return
    now = datetime.datetime.utcnow()
    cut = now - datetime.timedelta(days=DAYS)
    closes = _clv.load_closes()

    rows = []
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        t = _clv._dt(m.get('t'))
        if not t or t < cut:
            continue
        joueur = m.get('joueur')
        for entry in (m.get('retards') or []):
            try:
                book, prix = entry[0], float(entry[1])
            except Exception:
                continue
            cl = closes.get((m.get('uid'), book, joueur))
            if cl:
                rows.append((prix / cl - 1) * 100)

    if len(rows) < MIN_ROWS:
        print(f"récap CLV hebdo : seulement {len(rows)} écarts mesurables "
              f"(seuil {MIN_ROWS}) — pas de publication")
        return

    pos = 100 * sum(1 for x in rows if x > 0) / len(rows)
    lines = [
        "📐 BILAN DE LA SEMAINE — CLV réalisé",
        "",
        f"{len(rows)} écarts signalés avec un opérateur en retard, mesurés du "
        f"prix signalé à sa clôture réelle.",
        f"CLV médian : {st.median(rows):+.1f}%  ·  moyen : {st.mean(rows):+.1f}%",
        f"Écarts qui se sont refermés : {pos:.0f}%",
        "",
        "C'est ce chiffre — pas les plus gros mouvements — qui mesure la valeur "
        "réelle des signaux de la semaine.",
    ]
    if REPO_URL:
        lines.append(f"Détail ligne par ligne : {REPO_URL}")
    tg("\n".join(lines) + FOOTER)
    print(f"récap CLV hebdo publié : n={len(rows)}, médian {st.median(rows):+.1f}%, "
          f"{pos:.0f}% refermés")


if __name__ == '__main__':
    main()
