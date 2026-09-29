#!/usr/bin/env python3
"""
watchdog_capture.py — surveille la CAPTURE elle-même.

CRÉÉ LE 04/09/2026, en même temps que le retrait du cron '*/5' de
capture_closing.yml. Ce cron ne se déclenchait jamais (mesuré :
passages_par_declencheur ne contient que `repository_dispatch`), mais on
croyait avoir une redondance. En le retirant on assume enfin la réalité —
un seul déclencheur, le worker Cloudflare — et il faut donc un vrai filet.

watchdog_collecteurs.py surveille Kalshi et Polymarket. PERSONNE ne
surveillait capture_closing, qui est pourtant le cœur du dispositif : sans
lui, pas de closing lines, donc pas de CLV, donc plus rien à valider.

Ce que fait ce script, appelé par un cron HORAIRE :
  - lit capture_state.json['last_capture_at'] (le seul horodatage fiable ;
    le mtime, en CI, est celui du checkout — piège corrigé le 04/09) ;
  - si le retard dépasse SEUIL_MIN, alerte sur Telegram ET relance
    capture_closing.yml par workflow_dispatch.

Pourquoi un cron horaire est acceptable ici alors que le '*/5' ne l'était
pas : un watchdog livré avec 20 minutes de retard fait toujours son travail.
Une capture livrée avec 20 minutes de retard a perdu son closing.

Env : SEUIL_MIN (défaut 30), DRY_RUN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
      GH_TOKEN (pour `gh workflow run`).
"""
import os
import sys
import json
import datetime
import subprocess
import urllib.request
import urllib.parse

ETAT = os.environ.get('ETAT_CAPTURE', 'capture_state.json')
SEUIL_MIN = float(os.environ.get('SEUIL_MIN', '30'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'
WORKFLOW = os.environ.get('WORKFLOW_CAPTURE', 'capture_closing.yml')


def age_minutes():
    """Retard de la dernière capture, en minutes. inf si illisible.

    Un état absent ou illisible compte comme un retard MAXIMAL : mieux vaut
    une relance inutile qu'un silence de 24 h. C'est le même parti pris que
    watchdog_collecteurs.py.
    """
    try:
        d = json.load(open(ETAT, encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f"  ⚠️ {ETAT} illisible ({e}) — retard supposé maximal.")
        return float('inf')
    ts = d.get('last_capture_at')
    if not ts:
        print(f"  ⚠️ {ETAT} sans last_capture_at — retard supposé maximal.")
        return float('inf')
    try:
        t = datetime.datetime.fromisoformat(str(ts).replace('Z', ''))
    except ValueError:
        print(f"  ⚠️ last_capture_at illisible ({ts!r}) — retard supposé maximal.")
        return float('inf')
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    return (maintenant - t).total_seconds() / 60


def alerter(texte):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print(f"  ℹ️ Telegram non configuré, message : {texte}")
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode({'chat_id': chat, 'text': texte}).encode())
        urllib.request.urlopen(req, timeout=15)
        print("  ✅ alerte Telegram envoyée.")
    except Exception as e:
        print(f"  ⚠️ envoi Telegram : {e}")


def relancer():
    if DRY_RUN:
        print(f"  [dry] gh workflow run {WORKFLOW}")
        return True
    r = subprocess.run(['gh', 'workflow', 'run', WORKFLOW],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # Jamais avalé en silence : un watchdog qui échoue sans le dire est
        # pire que pas de watchdog du tout — on croit être couvert.
        print(f"  ⚠️ relance de {WORKFLOW} ÉCHOUÉE : {r.stderr.strip()[:200]}")
        return False
    print(f"  ✅ {WORKFLOW} relancé (workflow_dispatch via API).")
    return True


def main():
    age = age_minutes()
    lisible = 'inconnu' if age == float('inf') else f'{age:.0f} min'
    print(f"WATCHDOG CAPTURE — retard {lisible}, seuil {SEUIL_MIN:.0f} min"
          + (" [DRY RUN]" if DRY_RUN else ""))

    if age <= SEUIL_MIN:
        print("  ✅ la capture tourne, rien à faire.")
        return 0

    print(f"  🆘 aucune capture depuis {lisible} — le worker Cloudflare "
          f"semble muet.")
    ok = relancer()
    alerter(
        f"🆘 Capture tennis à l'arrêt : aucune capture depuis {lisible} "
        f"(seuil {SEUIL_MIN:.0f} min).\n"
        f"Relance automatique de {WORKFLOW} : "
        f"{'envoyée' if ok else 'ÉCHOUÉE'}.\n"
        f"Le worker Cloudflare est le déclencheur unique depuis le 04/09 — "
        f"vérifier son cron et ses logs s'il ne repart pas.")
    # Sortie 1 : le run est ROUGE. Un watchdog qui se déclenche est un
    # événement anormal, il doit se voir dans l'onglet Actions sans qu'on
    # ait à ouvrir les logs.
    return 1


if __name__ == '__main__':
    sys.exit(main())
