#!/usr/bin/env python3
"""
Script GitHub Actions — Récupère les résultats tennis depuis GitHub Sackmann
(JeffSackmann/tennis_atp et tennis_wta) via l'API GitHub.
Tourne chaque nuit à 2h UTC.
"""
import urllib.request, json, datetime, csv, io, os

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def github_get(url):
    headers = {
        'User-Agent': 'tennis-edge-bot/1.0',
        'Accept': 'application/vnd.github.v3+json',
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def fetch_sackmann_csv(repo, filename):
    """Récupère un CSV depuis GitHub Sackmann via l'API."""
    # Utiliser l'API contents pour obtenir le download_url
    api_url = f"https://api.github.com/repos/JeffSackmann/{repo}/contents/{filename}"
    meta = json.loads(github_get(api_url))
    download_url = meta.get('download_url')
    if not download_url:
        raise ValueError(f"Pas de download_url pour {filename}")
    # Télécharger le CSV directement
    req = urllib.request.Request(download_url, headers={'User-Agent': 'tennis-edge-bot/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

def get_recent_matches(csv_content, days=3):
    """Extrait les matchs des N derniers jours."""
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    cutoff_int = int(cutoff.strftime('%Y%m%d'))
    
    reader = csv.DictReader(io.StringIO(csv_content))
    recent = []
    for row in reader:
        try:
            date_int = int(row.get('tourney_date', '0'))
            if date_int >= cutoff_int:
                recent.append(row)
        except:
            continue
    return recent

def main():
    today = datetime.date.today()
    results = []
    
    datasets = [
        ('tennis_atp', 'atp_matches_2026.csv', 'ATP'),
        ('tennis_wta', 'wta_matches_2026.csv', 'WTA'),
    ]
    
    for repo, filename, circuit in datasets:
        print(f"Fetching {circuit} from {repo}/{filename}...")
        try:
            csv_content = fetch_sackmann_csv(repo, filename)
            matches = get_recent_matches(csv_content, days=3)
            print(f"  {len(matches)} matchs récents trouvés")
            
            for row in matches:
                date_str = row.get('tourney_date', '')
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                winner = row.get('winner_name', '')
                loser = row.get('loser_name', '')
                tournament = row.get('tourney_name', '')
                surface = row.get('surface', '')
                score = row.get('score', '')
                
                result = {
                    'id': f"{date_str}_{winner}_{loser}".replace(' ', '_').lower(),
                    'date': date_str,
                    'tournament': tournament,
                    'circuit': circuit,
                    'surface': surface,
                    'home_team': winner,   # winner = A (favori généralement)
                    'away_team': loser,
                    'winner': winner,
                    'winner_code': 1,      # home gagne toujours (c'est le winner)
                    'home_sets': None,
                    'away_sets': None,
                    'score': score,
                    'completed': True,
                    # Stats Sackmann si disponibles
                    'aces_home': row.get('w_ace', ''),
                    'aces_away': row.get('l_ace', ''),
                    'df_home': row.get('w_df', ''),
                    'df_away': row.get('l_df', ''),
                    'first_serve_pct_home': row.get('w_1stIn', ''),
                    'first_serve_pct_away': row.get('l_1stIn', ''),
                    'first_serve_won_home': row.get('w_1stWon', ''),
                    'first_serve_won_away': row.get('l_1stWon', ''),
                    'bp_conversion_home': row.get('w_bpSaved', ''),
                    'bp_conversion_away': row.get('l_bpSaved', ''),
                    'rank_home': row.get('winner_rank', ''),
                    'rank_away': row.get('loser_rank', ''),
                }
                results.append(result)
                print(f"  ✅ {winner} bt {loser} ({score})")
                
        except Exception as e:
            print(f"  ❌ Erreur {circuit}: {e}")
    
    # Sauvegarder resultats.json
    output = {
        'updated': today.strftime('%Y-%m-%d'),
        'generated_at': datetime.datetime.utcnow().isoformat(),
        'source': 'JeffSackmann/tennis_atp + tennis_wta',
        'count': len(results),
        'results': results
    }
    
    with open('resultats.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {len(results)} résultats sauvegardés dans resultats.json")

if __name__ == '__main__':
    main()
