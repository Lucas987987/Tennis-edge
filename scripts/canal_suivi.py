#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_suivi.py — Suivi quotidien des écarts publiés sur le canal.

Un seul message par jour qui montre ce que sont devenus les écarts signalés la
veille : combien se sont refermés, de combien, avec le meilleur ET le moins bon
cas. Publier les échecs autant que les réussites est le point central — c'est ce
qui rend le suivi crédible et impossible à sélectionner a posteriori.

Mesure : prix signalé dans le message vs DERNIER PRIX PRÉ-MATCH du MÊME
opérateur. Pas de résultat de match, pas de gain : uniquement du prix.

Env : LOG (canal_public_log.jsonl), CURVES, DAYS (1 = la veille),
      TELEGRAM_TOKEN, TELEGRAM_PUBLIC_CHAT_ID, DRY_RUN, MIN_ROWS (3),
      REPO_URL (lien vers le détail public).
"""
import os, json, glob, datetime, statistics as st, urllib.request, urllib.parse

LOG      = os.environ.get('LOG', 'canal_public_log.jsonl')
CURVES   = [c.strip() for c in os.environ.get(
    'CURVES', 'book_curves_live.jsonl,book_curves.jsonl').split(',') if c.strip()]
DAYS     = int(os.environ.get('DAYS', '1'))
MIN_ROWS = int(os.environ.get('MIN_ROWS', '3'))
# Exchanges : sans marge intégrée, leur prix est structurellement plus haut,
# donc ils ressortent en permanence comme « en retard » sans l'être
# (CLV médian -1,7 %, 14 % de refermeture sur les alertes publiées).
# canal_public.py ne les signale plus depuis le 06/08/2026 ; on filtre ici
# aussi, au cas où d'anciennes alertes remonteraient dans la fenêtre.
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())
REPO_URL = os.environ.get('REPO_URL', '')
TOKEN    = os.environ.get('TELEGRAM_TOKEN', '')
CHAT     = os.environ.get('TELEGRAM_PUBLIC_CHAT_ID', '')
DRY      = os.environ.get('DRY_RUN', '') == '1' or not (TOKEN and CHAT)

FOOTER = ("\n—\nℹ️ Suivi de prix uniquement : prix signalé comparé au dernier prix "
          "pré-match du même opérateur. Aucun résultat de match, aucun gain. "
          "Ceci n'est pas un conseil.\n"
          "18+ | joueurs-info-service.fr · 09 74 75 13 13")


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    closes = {}
    for src in CURVES:
        for path in glob.glob(src):
            if not os.path.exists(path):
                continue
            for line in open(path, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                ct = _dt(r.get('commence_time'))
                if not ct:
                    continue
                home = r.get('home_team') or r.get('home') or ''
                away = r.get('away_team') or r.get('away') or ''
                for key, name in (('home_curve', home), ('away_curve', away)):
                    pts = [(_dt(p[0]), p[1]) for p in (r.get(key) or []) if _dt(p[0]) and p[1] and p[1] > 1]
                    pts = sorted(p for p in pts if p[0] < ct)   # PRÉ-MATCH uniquement
                    if pts and name:
                        closes[(r.get('uid'), r.get('book'), name)] = pts[-1][1]
    return closes


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
    day = (now - datetime.timedelta(days=DAYS)).date()
    closes = load_closes()
    rows = []
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        t = _dt(m.get('t'))
        if not t or t.date() != day:
            continue
        joueur = m.get('joueur')
        for entry in (m.get('retards') or []):
            try:
                book, prix = entry[0], float(entry[1])
            except Exception:
                continue
            if book in EXCHANGES:
                continue      # cf. note EXCHANGES en tête
            cl = closes.get((m.get('uid'), book, joueur))
            if not cl:
                continue
            rows.append(dict(joueur=joueur, book=book, prix=prix, close=cl,
                             clv=(prix/cl - 1) * 100))
    if len(rows) < MIN_ROWS:
        print(f"suivi : seulement {len(rows)} écart(s) mesurable(s) pour le {day} — pas de publication")
        return

    # DÉDUPLICATION : un match ne compte qu'UNE fois (moyenne de ses lignes).
    # Un même match génère plusieurs alertes (paliers successifs) et chaque
    # alerte plusieurs opérateurs ; les compter séparément gonfle le "n"
    # affiché et présente un seul match comme plusieurs observations
    # indépendantes. Le détail par opérateur reste affiché en dessous
    # (plus net / moins bon), mais le comptage porte sur les MATCHS.
    par_match = {}
    for r in rows:
        par_match.setdefault(r['joueur'], []).append(r['clv'])
    clv = [st.mean(v) for v in par_match.values()]
    refermes = sum(1 for x in clv if x > 0)
    best = max(rows, key=lambda r: r['clv'])
    worst = min(rows, key=lambda r: r['clv'])
    L = [f"📋 SUIVI DES ÉCARTS SIGNALÉS — {day.strftime('%d/%m')}", "",
         f"{len(clv)} matchs signalés ({len(rows)} écarts) · {refermes} se sont "
         f"refermés ({100*refermes/len(clv):.0f}%)",
         f"Refermement médian par match : {st.median(clv):+.1f}%", "",
         f"Le plus net : {best['book']} {best['prix']:.2f} → {best['close']:.2f} "
         f"sur {best['joueur']} ({best['clv']:+.0f}%)",
         f"Le moins bon : {worst['book']} {worst['prix']:.2f} → {worst['close']:.2f} "
         f"sur {worst['joueur']} ({worst['clv']:+.0f}%)", "",
         "Méthode : prix signalé comparé au dernier prix pré-match du même opérateur. "
         "On publie autant les écarts qui ne se referment pas que les autres."]
    if REPO_URL:
        L.append(f"Historique complet : {REPO_URL}")
    tg("\n".join(L) + FOOTER)
    print(f"suivi publié : {len(clv)} matchs / {len(rows)} écarts, "
          f"{refermes} refermés, médian {st.median(clv):+.1f}%")


if __name__ == '__main__':
    main()
