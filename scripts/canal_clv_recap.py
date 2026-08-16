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

    # SOURCE = LE REGISTRE GELÉ de canal_clv.py, plus les courbes.
    # Les courbes live sont purgées après 3 jours (purge_data.py) : recalculer
    # depuis elles faisait disparaître du bilan tout écart de plus de 3 jours.
    # Le registre, lui, est append-only et survit à toute purge.
    ledger = _clv.load_ledger()
    if not ledger:
        print("récap CLV hebdo : registre vide — lancer canal_clv.py d'abord")
        return

    # DÉDUPLICATION : un match ne compte qu'UNE fois. Un même match génère
    # plusieurs alertes (paliers successifs) × plusieurs opérateurs ; les
    # compter séparément gonfle n et présente un seul match comme plusieurs
    # observations indépendantes (constaté : 1 joueur = 33 % du total).
    par_match = {}
    for r in ledger.values():
        t = _clv._dt(r.get('date'))
        if not t or t < cut:
            continue
        par_match.setdefault(r.get('uid') or r.get('joueur'), []).append(r['clv'])
    rows = [st.mean(v) for v in par_match.values()]
    n_lignes = sum(len(v) for v in par_match.values())

    if len(rows) < MIN_ROWS:
        print(f"récap CLV hebdo : seulement {len(rows)} écarts mesurables "
              f"(seuil {MIN_ROWS}) — pas de publication")
        return

    pos = 100 * sum(1 for x in rows if x > 0) / len(rows)
    lines = [
        "📐 BILAN DE LA SEMAINE — CLV réalisé",
        "",
        f"{len(rows)} matchs signalés avec un opérateur en retard "
        f"({n_lignes} écarts au total), mesurés du prix signalé à sa clôture réelle.",
        f"CLV médian : {st.median(rows):+.1f}%  ·  moyen : {st.mean(rows):+.1f}%",
        f"Matchs dont l'écart s'est refermé : {pos:.0f}%",
        "",
        "Un match compte pour une seule observation, même s'il a déclenché "
        "plusieurs alertes ou concerné plusieurs opérateurs.",
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
