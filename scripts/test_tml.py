#!/usr/bin/env python3
"""
TEST — Vérifie le format et la fraîcheur de la base TennisMyLife (TML-Database).
Télécharge le CSV 2026 et affiche sa structure, les derniers matchs, et si
Roland-Garros y figure. Ne modifie RIEN.
"""
import urllib.request, csv, io, datetime

# Le dépôt TML stocke un CSV par année : 2026.csv
TML_URL = "https://raw.githubusercontent.com/Tennismylife/TML-Database/master/2026.csv"

def test():
    print(f"Téléchargement de {TML_URL}\n")
    try:
        req = urllib.request.Request(TML_URL, headers={'User-Agent': 'test/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            content = r.read().decode('utf-8')
    except Exception as e:
        print(f"❌ Erreur téléchargement: {e}")
        return

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    print(f"✅ {len(rows)} matchs dans 2026.csv\n")

    # Colonnes disponibles
    if rows:
        print("=== COLONNES ===")
        print(list(rows[0].keys()))
        print()

    # Chercher le champ date (tourney_date ou similaire)
    date_field = None
    for cand in ['tourney_date', 'Date', 'date', 'tourney_dt']:
        if rows and cand in rows[0]:
            date_field = cand
            break
    print(f"Champ date détecté: {date_field}\n")

    # Derniers matchs par date
    if date_field:
        dates = sorted(set(r.get(date_field,'') for r in rows if r.get(date_field)))
        print(f"=== PÉRIODE COUVERTE ===")
        print(f"  Première date: {dates[0] if dates else '?'}")
        print(f"  Dernière date: {dates[-1] if dates else '?'}")
        print()

    # Chercher Roland-Garros / French Open
    print("=== RECHERCHE ROLAND-GARROS ===")
    name_field = None
    for cand in ['tourney_name', 'Tournament', 'tourney', 'name']:
        if rows and cand in rows[0]:
            name_field = cand
            break
    if name_field:
        rg = [r for r in rows if 'roland' in r.get(name_field,'').lower() 
              or 'french' in r.get(name_field,'').lower()]
        print(f"  Champ nom tournoi: {name_field}")
        print(f"  Matchs RG/French Open trouvés: {len(rg)}")
        if rg:
            print(f"\n  Exemples de matchs RG:")
            for r in rg[:5]:
                w = r.get('winner_name') or r.get('Winner') or r.get('winner') or '?'
                l = r.get('loser_name') or r.get('Loser') or r.get('loser') or '?'
                sc = r.get('score') or r.get('Score') or '?'
                print(f"    {w} bat {l} — {sc}")
    else:
        print("  Champ nom tournoi non identifié")

if __name__ == '__main__':
    test()
