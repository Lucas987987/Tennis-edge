#!/usr/bin/env python3
"""
Script de TEST — vérifie ce que l'endpoint scores de The Odds API retourne pour le tennis.
Ne modifie RIEN. Affiche seulement le contenu pour évaluer la couverture.
"""
import urllib.request, json, os

# Récupérer une clé qui fonctionne
def get_keys():
    keys = []
    for i in range(1, 7):  # 6 clés
        k = os.environ.get(f'ODDS_API_KEY_{i}')
        if k: keys.append((i, k))
    return keys

SPORTS = ['tennis_atp_french_open', 'tennis_wta_french_open']

def test():
    keys = get_keys()
    if not keys:
        print("❌ Aucune clé trouvée dans les variables d'environnement")
        return
    print(f"✅ {len(keys)} clés disponibles\n")
    key_num, key = keys[0]

    for sport in SPORTS:
        print(f"=== {sport} ===")
        # daysFrom=3 = matchs terminés dans les 3 derniers jours
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/?apiKey={key}&daysFrom=3"
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                remaining = r.headers.get('x-requests-remaining', '?')
                data = json.loads(r.read())
            print(f"  Requêtes restantes: {remaining}")
            print(f"  {len(data)} événements retournés\n")

            completed = [m for m in data if m.get('completed')]
            with_scores = [m for m in data if m.get('scores')]
            print(f"  Terminés (completed=true): {len(completed)}")
            print(f"  Avec scores renseignés: {len(with_scores)}\n")

            # Afficher quelques exemples
            for m in data[:5]:
                home = m.get('home_team', '?')
                away = m.get('away_team', '?')
                comp = m.get('completed')
                scores = m.get('scores')
                ct = m.get('commence_time', '')[:10]
                print(f"  [{ct}] {home} vs {away}")
                print(f"     completed={comp}, scores={scores}")
            print()
        except Exception as e:
            print(f"  ❌ Erreur: {e}\n")

if __name__ == '__main__':
    test()
