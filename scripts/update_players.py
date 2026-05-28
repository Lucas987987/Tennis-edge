#!/usr/bin/env python3
"""
Script GitHub Actions — Recalcule les Elo surfaciques et stats service/retour
depuis les CSV Sackmann et met à jour players_data.json.
Tourne chaque semaine (ou à la demande).
"""
import urllib.request, json, datetime, csv, io, os, re, unicodedata
from collections import defaultdict

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
K_FACTOR = 32  # Facteur K standard pour l'Elo
YEARS = list(range(2015, 2027))  # Matchs depuis 2015 pour avoir assez d'historique
RECENT_DAYS = 90  # Fenêtre pour stats service/retour

def github_get(url):
    headers = {'User-Agent': 'tennis-edge-bot/1.0', 'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def fetch_csv(repo, filename):
    """Télécharge un CSV Sackmann."""
    api_url = f"https://api.github.com/repos/JeffSackmann/{repo}/contents/{filename}"
    try:
        meta = json.loads(github_get(api_url))
        download_url = meta.get('download_url')
        if not download_url: return None
        req = urllib.request.Request(download_url, headers={'User-Agent': 'tennis-edge-bot/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        print(f"  ⚠️ {filename}: {e}")
        return None

def expected_score(ra, rb):
    return 1 / (1 + 10**((rb - ra) / 400))

def update_elo(elo_dict, surf_dict, winner, loser, surface):
    """Met à jour l'Elo global et surfacique."""
    # Elo global
    ea = expected_score(elo_dict[winner], elo_dict[loser])
    elo_dict[winner] += K_FACTOR * (1 - ea)
    elo_dict[loser]  += K_FACTOR * (0 - (1 - ea))
    
    # Elo surfacique
    s = surface.lower()
    key = 'cElo' if 'clay' in s else 'gElo' if 'grass' in s else 'hElo'
    ea_s = expected_score(surf_dict[winner][key], surf_dict[loser][key])
    surf_dict[winner][key] += K_FACTOR * (1 - ea_s)
    surf_dict[loser][key]  += K_FACTOR * (0 - (1 - ea_s))

def norm_name(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip()

def main():
    today = datetime.date.today()
    cutoff_spw = today - datetime.timedelta(days=RECENT_DAYS)
    cutoff_int = int(cutoff_spw.strftime('%Y%m%d'))
    
    # Structures de données
    elo_global = defaultdict(lambda: 1500.0)
    elo_surf   = defaultdict(lambda: {'cElo': 1500.0, 'hElo': 1500.0, 'gElo': 1500.0})
    
    # Stats service/retour (90 derniers jours)
    stats_w = defaultdict(lambda: {'svpt':0, 'won':0, 'rpwon':0, 'rpagainst':0, 'matches':0})
    
    # Nom complet → info joueur
    player_info = {}  # name → {age, rank}
    
    datasets = [
        ('tennis_atp', 'ATP'),
        ('tennis_wta', 'WTA'),
    ]
    
    all_rows = []  # Pour trier tous les matchs par date
    
    for repo, circuit in datasets:
        print(f"\n=== {circuit} ===")
        for year in YEARS:
            prefix = 'atp' if circuit=='ATP' else 'wta'
            filename = f"{prefix}_matches_{year}.csv"
            content = fetch_csv(repo, filename)
            if not content:
                continue
            
            rows = list(csv.DictReader(io.StringIO(content)))
            print(f"  {year}: {len(rows)} matchs")
            for row in rows:
                row['_circuit'] = circuit
            all_rows.extend(rows)
    
    # Trier par date
    all_rows.sort(key=lambda r: r.get('tourney_date','0'))
    print(f"\nTotal: {len(all_rows)} matchs à traiter")
    
    # Calculer Elo et stats
    for row in all_rows:
        winner = row.get('winner_name','').strip()
        loser  = row.get('loser_name','').strip()
        surface = row.get('surface','Hard')
        date_int = int(row.get('tourney_date','0') or 0)
        
        if not winner or not loser: continue
        
        # Mettre à jour Elo
        update_elo(elo_global, elo_surf, winner, loser, surface)
        
        # Stats service/retour (seulement les 90 derniers jours)
        if date_int >= cutoff_int:
            # Winner stats service
            try:
                svpt_w = int(row.get('w_svpt',0) or 0)
                won_w  = int(row.get('w_1stWon',0) or 0) + int(row.get('w_2ndWon',0) or 0)
                svpt_l = int(row.get('l_svpt',0) or 0)
                won_l  = int(row.get('l_1stWon',0) or 0) + int(row.get('l_2ndWon',0) or 0)
                
                if svpt_w > 0:
                    stats_w[winner]['svpt']    += svpt_w
                    stats_w[winner]['won']     += won_w
                    stats_w[winner]['rpagainst'] += svpt_l  # points servis par l'adversaire
                    stats_w[winner]['rpwon']   += (svpt_l - won_l)  # points retour gagnés
                    stats_w[winner]['matches'] += 1
                
                if svpt_l > 0:
                    stats_w[loser]['svpt']    += svpt_l
                    stats_w[loser]['won']     += won_l
                    stats_w[loser]['rpagainst'] += svpt_w
                    stats_w[loser]['rpwon']   += (svpt_w - won_w)
                    stats_w[loser]['matches'] += 1
            except: pass
        
        # Infos joueur (rang, âge)
        try:
            wrank = int(row.get('winner_rank',0) or 0)
            if wrank > 0: player_info[winner] = {'rank': wrank}
            lrank = int(row.get('loser_rank',0) or 0)
            if lrank > 0: player_info[loser] = {'rank': lrank}
        except: pass
    
    # Construire players_data.json
    # Charger l'ancien pour préserver les données qu'on ne recalcule pas (age, lastMatch)
    old_data = {'atp':{}, 'wta':{}}
    if os.path.exists('players_data.json'):
        with open('players_data.json', encoding='utf-8') as f:
            old_data = json.load(f)
    
    new_atp = {}
    new_wta = {}
    
    all_players = set(elo_global.keys())
    print(f"\n{len(all_players)} joueurs avec Elo calculé")
    
    for name in all_players:
        nk = norm_name(name)
        eg = round(elo_global[name], 1)
        es = elo_surf[name]
        
        # Stats service/retour
        s = stats_w[name]
        spw = round(s['won']/s['svpt']*100, 1) if s['svpt']>0 else None
        rpw = round(s['rpwon']/s['rpagainst']*100, 1) if s['rpagainst']>0 else None
        
        player_obj = {
            'name': name,
            'elo': {
                'elo': eg,
                'cElo': round(es['cElo'], 1),
                'hElo': round(es['hElo'], 1),
                'gElo': round(es['gElo'], 1),
            },
            'serve': {'spw': spw, 'matches': s['matches']} if spw else None,
            'ret': {'rpw': rpw} if rpw else None,
        }
        
        # Préserver age et lastMatch depuis l'ancien fichier
        for circuit_old, circuit_dict in [('atp', old_data['atp']), ('wta', old_data['wta'])]:
            if nk in circuit_dict:
                old = circuit_dict[nk]
                if old.get('age'): player_obj['age'] = old['age']
                if old.get('lastMatch'): player_obj['lastMatch'] = old['lastMatch']
                break
        
        # Déterminer ATP ou WTA selon le circuit des matchs récents
        # (heuristique simple — les derniers matchs déterminent le circuit)
        new_atp[nk] = player_obj  # On met tout ensemble pour l'instant
    
    output = {
        'meta': {
            'updated': today.strftime('%Y-%m-%d'),
            'source': 'JeffSackmann/tennis_atp + tennis_wta — Elo recalculé',
            'atp': len(new_atp),
            'wta': 0,
        },
        'atp': new_atp,
        'wta': old_data.get('wta', {}),  # Garder WTA de l'ancien pour l'instant
        'aliases': old_data.get('aliases', {'atp':{}, 'wta':{}}),
    }
    
    with open('players_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=True, separators=(',',':'))
    
    print(f"\n✅ players_data.json mis à jour: {len(new_atp)} joueurs ATP")
    print(f"   Dernière mise à jour: {today}")
    
    # Exemples
    for name in ['Jannik Sinner', 'Carlos Alcaraz', 'Iga Swiatek']:
        nk = norm_name(name)
        if nk in new_atp:
            p = new_atp[nk]
            print(f"   {name}: Elo={p['elo']['elo']}, cElo={p['elo']['cElo']}, spw={p['serve']['spw'] if p.get('serve') else 'N/A'}")

if __name__ == '__main__':
    main()
