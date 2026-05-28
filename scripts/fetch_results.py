#!/usr/bin/env python3
"""
Script GitHub Actions — Récupère les résultats tennis depuis Sofascore
et met à jour resultats.json dans le repo.
Tourne chaque nuit à 2h du matin (UTC).
"""
import urllib.request, json, datetime, os

def fetch_sofascore(date_str):
    """Récupère les résultats tennis d'une date donnée."""
    url = f"https://api.sofascore.com/api/v1/sport/tennis/scheduled-events/{date_str}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
        'sec-fetch-dest': 'empty',
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def fetch_match_stats(event_id):
    """Récupère les statistiques détaillées d'un match."""
    url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.sofascore.com/',
        'Origin': 'https://www.sofascore.com',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'cors',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except:
        return None

def parse_stats(stats_data):
    """Extrait les stats utiles pour le backtest."""
    if not stats_data or 'statistics' not in stats_data:
        return {}
    
    result = {}
    for period in stats_data['statistics']:
        if period.get('period') != 'ALL':
            continue
        for group in period.get('groups', []):
            for item in group.get('statisticsItems', []):
                name = item.get('name', '').lower()
                home = item.get('home', '')
                away = item.get('away', '')
                
                if 'ace' in name:
                    result['aces_home'] = home
                    result['aces_away'] = away
                elif 'double fault' in name:
                    result['df_home'] = home
                    result['df_away'] = away
                elif 'first serve' in name and '%' in str(home):
                    result['first_serve_pct_home'] = home
                    result['first_serve_pct_away'] = away
                elif 'first serve points won' in name:
                    result['first_serve_won_home'] = home
                    result['first_serve_won_away'] = away
                elif 'second serve points won' in name:
                    result['second_serve_won_home'] = home
                    result['second_serve_won_away'] = away
                elif 'break point' in name and 'conversion' in name:
                    result['bp_conversion_home'] = home
                    result['bp_conversion_away'] = away
                elif 'total points won' in name:
                    result['total_points_home'] = home
                    result['total_points_away'] = away
    return result

def main():
    today = datetime.date.today()
    results = []
    
    # Récupérer les 3 derniers jours
    for days_back in range(1, 4):
        date = today - datetime.timedelta(days=days_back)
        date_str = date.strftime('%Y-%m-%d')
        print(f"Fetching {date_str}...")
        
        try:
            data = fetch_sofascore(date_str)
            events = data.get('events', [])
            finished = [e for e in events if e.get('status', {}).get('type') == 'finished']
            print(f"  {len(finished)} matchs terminés")
            
            for event in finished:
                match_id = event['id']
                home = event.get('homeTeam', {}).get('name', '')
                away = event.get('awayTeam', {}).get('name', '')
                winner_code = event.get('winnerCode')  # 1=home, 2=away
                tournament = event.get('tournament', {}).get('name', '')
                category = event.get('tournament', {}).get('category', {}).get('name', '')
                
                # Score sets
                home_score = event.get('homeScore', {})
                away_score = event.get('awayScore', {})
                
                # Stats détaillées du match
                stats = fetch_match_stats(match_id)
                parsed_stats = parse_stats(stats)
                
                match_result = {
                    'id': match_id,
                    'date': date_str,
                    'tournament': tournament,
                    'category': category,
                    'home_team': home,
                    'away_team': away,
                    'winner': home if winner_code == 1 else away if winner_code == 2 else None,
                    'winner_code': winner_code,
                    'home_sets': home_score.get('current'),
                    'away_sets': away_score.get('current'),
                    'completed': True,
                    **parsed_stats
                }
                results.append(match_result)
                print(f"  ✅ {home} vs {away} → {match_result['winner']}")
                
        except Exception as e:
            print(f"  ❌ Erreur {date_str}: {e}")
    
    # Sauvegarder
    output = {
        'updated': today.strftime('%Y-%m-%d'),
        'generated_at': datetime.datetime.utcnow().isoformat(),
        'count': len(results),
        'results': results
    }
    
    with open('resultats.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ {len(results)} résultats sauvegardés dans resultats.json")

if __name__ == '__main__':
    main()
              
