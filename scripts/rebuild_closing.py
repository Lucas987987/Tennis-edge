#!/usr/bin/env python3
"""
Reconstruction rétroactive du bloc 'closing' dans closing_lines.json.

CONTEXTE : avant que le bon script ne soit déployé, beaucoup de matchs ont un
history[] de cotes mais pas de bloc 'closing'. Ce script reconstruit ce bloc à
partir du point le PLUS TARDIF de chaque history[], pour récupérer le CLV des
matchs qui avaient une capture proche du coup d'envoi.

RÈGLES (non destructeur) :
- Ne touche QUE le champ 'closing'. history[] et autres champs intacts.
- N'écrase PAS un 'closing' déjà présent (on respecte l'existant).
- closing.reliable = True si le point le plus tardif est <= CLOSING_MAX_MINS.
  Sinon reliable=False : le match est conservé mais marqué non exploitable pour
  le CLV (on ne jette rien, on étiquette honnêtement).

Usage : python rebuild_closing.py
Fait une sauvegarde closing_lines.backup.json avant toute modification.
"""
import json, shutil, os

CLOSING_FILE = 'closing_lines.json'
BACKUP_FILE = 'closing_lines.backup.json'
CLOSING_MAX_MINS = 35


def rebuild():
    if not os.path.exists(CLOSING_FILE):
        print(f"❌ {CLOSING_FILE} introuvable.")
        return

    with open(CLOSING_FILE, encoding='utf-8') as f:
        closing = json.load(f)

    # Sauvegarde de sécurité avant toute modification
    shutil.copy(CLOSING_FILE, BACKUP_FILE)
    print(f"💾 Sauvegarde créée : {BACKUP_FILE}")

    rebuilt = 0
    reliable_count = 0
    already = 0
    no_history = 0

    for uid, m in closing.items():
        # Respecter un closing déjà présent
        if m.get('closing'):
            already += 1
            continue

        hist = m.get('history', [])
        if not hist:
            no_history += 1
            continue

        # Point le plus tardif = mins_before le plus petit (le plus proche du match)
        valid = [h for h in hist if h.get('mins_before') is not None]
        if not valid:
            no_history += 1
            continue
        best = min(valid, key=lambda h: h['mins_before'])

        reliable = best['mins_before'] <= CLOSING_MAX_MINS
        m['closing'] = {
            'home': best.get('home'),
            'away': best.get('away'),
            'mins_before': best['mins_before'],
            'captured_at': best.get('t'),
            'reliable': reliable,
            'rebuilt': True,   # marque que ce closing a été reconstruit a posteriori
        }
        rebuilt += 1
        if reliable:
            reliable_count += 1

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Reconstruction terminée :")
    print(f"   {rebuilt} closing reconstruits")
    print(f"   dont {reliable_count} FIABLES (<= {CLOSING_MAX_MINS} min) -> exploitables pour le CLV")
    print(f"   {rebuilt - reliable_count} non fiables (trop loin du coup d'envoi)")
    print(f"   {already} closing déjà présents (non touchés)")
    print(f"   {no_history} matchs sans history exploitable (ignorés)")


if __name__ == '__main__':
    rebuild()
