#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sante_chaine.py — alerte Telegram (canal PRIVÉ) quand un maillon de la chaîne s'arrête (23/10/2026).

La nuit du 22 au 23/10, la collecte des feuilles s'est arrêtée 11 h sans que personne le sache : 75 matchs
pronostiqués joués, 2 jugés. watchdog_capture.py ne surveille que la capture des cotes. Ici, les autres
maillons, d'après l'horodatage écrit par chacun :
    pronostics du Lab      Tennis_Edge_Lab/live/pronostics.json   genere_le        > 4 h
    feuilles de match      feuilles/etat.json                     dernier_passage  > 6 h
    verdicts en direct     verdicts_direct.json                   genere_le        > 30 h
Une alerte quand un maillon passe en retard, rappelée toutes les 6 h tant qu'il l'est, et un message
« reparti » quand il revient. État : sante_chaine_etat.json. Lancé par « Courbes live + alertes » (~3 min).
Env : TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (sans eux : affiché seulement), DRY_RUN=1.
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

ETAT = os.environ.get('SANTE_ETAT', 'sante_chaine_etat.json')
RAPPEL_H = 6
MAILLONS = (
    ('pronostics', 'Pronostics du Lab', 'Tennis_Edge_Lab/live/pronostics.json', ('genere_le',), 4,
     'workflow « Pronostics du jour » (déclenché toutes les 2 h par le worker)'),
    ('feuilles', 'Feuilles de match (résultats, stats, point par point)', 'feuilles/etat.json', ('dernier_passage', 'le'), 6,
     'workflow « Feuilles de match » (toutes les 2 h par le worker) ; quota TennisApi'),
    ('verdicts', 'Verdicts en direct (page Tennis Edge)', 'verdicts_direct.json', ('genere_le',), 30,
     'workflow « steam_pipeline » (quotidien)'),
)


def lire_date(racine, chemin, cles):
    try:
        x = json.load(open(os.path.join(racine, chemin), encoding='utf-8'))
        for k in cles:
            x = x[k]
        t = dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def verifier(racine, maintenant, etat):
    """Liste des messages à envoyer ; met à jour `etat` ({maillon: {'retard': bool, 'alerte_le': iso}})."""
    msgs = []
    for cle, lib, chemin, cles, seuil_h, source in MAILLONS:
        t = lire_date(racine, chemin, cles)
        age_h = (maintenant - t).total_seconds() / 3600 if t else float('inf')
        e = etat.setdefault(cle, {'retard': False})
        if age_h > seuil_h:
            der = e.get('alerte_le')
            rappel = der and (maintenant - dt.datetime.fromisoformat(der)).total_seconds() / 3600 >= RAPPEL_H
            if not e['retard'] or rappel:
                age = 'inconnu' if age_h == float('inf') else f"{age_h:.0f} h"
                msgs.append(f"⚠️ {lib} : pas de mise à jour depuis {age} (seuil {seuil_h} h).\nÀ regarder : {source}.")
                e['alerte_le'] = maintenant.isoformat(timespec='seconds')
            e['retard'] = True
        else:
            if e.get('retard'):
                msgs.append(f"✅ {lib} : reparti (dernière mise à jour il y a {age_h * 60:.0f} min).")
            e['retard'] = False
            e.pop('alerte_le', None)
    return msgs


def envoyer(texte):
    token, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat or os.environ.get('DRY_RUN') == '1':
        print(f"[non envoyé] {texte}")
        return False
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=urllib.parse.urlencode({'chat_id': chat, 'text': texte}).encode())
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as ex:  # noqa: BLE001 — une alerte ratée ne casse pas le workflow des courbes
        print(f"⚠️ Telegram : {ex}")
        return False


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    try:
        etat = json.load(open(ETAT, encoding='utf-8'))
    except (OSError, ValueError):
        etat = {}
    avant = json.dumps(etat, sort_keys=True)
    msgs = verifier(racine, dt.datetime.now(dt.timezone.utc), etat)
    for m in msgs:
        print(m)
        envoyer(m)
    if json.dumps(etat, sort_keys=True) != avant:                 # réécrit seulement si quelque chose a changé
        with open(ETAT, 'w', encoding='utf-8') as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
    if not msgs:
        print('Chaîne : tous les maillons à jour.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
