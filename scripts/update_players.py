#!/usr/bin/env python3
"""
Script GitHub Actions — Recalcule Elo, forme récente, tendance Elo,
classement ATP/WTA depuis les CSV Sackmann.
Tourne chaque lundi à 3h UTC.
"""
import urllib.request, json, datetime, csv, io, os, re, unicodedata
from collections import defaultdict

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
K_FACTOR = 32
YEARS = list(range(2015, 2027))
RECENT_DAYS = 90      # Fenêtre stats service/retour
FORM_MATCHES = 5      # Nombre de matchs pour la forme récente
TREND_DAYS = 90       # Fenêtre tendance Elo

def github_get(url):
    headers = {'User-Agent': 'tennis-edge-bot/1.0', 'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()

def fetch_csv(repo, filename):
    try:
        api_url = f"https://api.github.com/repos/JeffSackmann/{repo}/contents/{filename}"
        meta = json.loads(github_get(api_url))
        dl = meta.get('download_url')
        if not dl: return None
        req = urllib.request.Request(dl, headers={'User-Agent': 'tennis-edge-bot/1.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        print(f"  ⚠️ {filename}: {e}")
        return None

def expected_score(ra, rb):
    return 1 / (1 + 10**((rb - ra) / 400))

def update_elo(elo_dict, surf_dict, winner, loser, surface):
    ea = expected_score(elo_dict[winner], elo_dict[loser])
    elo_dict[winner] += K_FACTOR * (1 - ea)
    elo_dict[loser]  += K_FACTOR * (0 - (1 - ea))
    s = surface.lower()
    key = 'cElo' if 'clay' in s else 'gElo' if 'grass' in s else 'hElo'
    ea_s = expected_score(surf_dict[winner][key], surf_dict[loser][key])
    surf_dict[winner][key] += K_FACTOR * (1 - ea_s)
    surf_dict[loser][key]  += K_FACTOR * (0 - (1 - ea_s))
    return key

def norm_name(s):
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip()

def fetch_rankings(repo, filename):
    """Récupère le classement actuel ATP ou WTA."""
    rankings = {}  # player_id → rank
    content = fetch_csv(repo, filename)
    if not content: return rankings
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        pid = row.get('player','').strip()
        rank = row.get('rank','').strip()
        if pid and rank:
            try: rankings[pid] = int(rank)
            except: pass
    return rankings

def fetch_player_ids(repo, filename):
    """Récupère le mapping player_id → name."""
    players = {}  # player_id → full_name
    content = fetch_csv(repo, filename)
    if not content: return players
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        pid = row.get('player_id','').strip()
        fname = row.get('name_first','').strip()
        lname = row.get('name_last','').strip()
        if pid and lname:
            full = f"{fname} {lname}".strip()
            players[pid] = full
    return players

def main():
    today = datetime.date.today()
    cutoff_stats = today - datetime.timedelta(days=RECENT_DAYS)
    cutoff_trend = today - datetime.timedelta(days=TREND_DAYS)
    cutoff_stats_int = int(cutoff_stats.strftime('%Y%m%d'))
    cutoff_trend_int = int(cutoff_trend.strftime('%Y%m%d'))

    # Structures
    elo_global = defaultdict(lambda: 1500.0)
    elo_surf   = defaultdict(lambda: {'cElo':1500.0,'hElo':1500.0,'gElo':1500.0})
    stats_srv  = defaultdict(lambda: {'svpt':0,'won':0,'rpwon':0,'rpag':0,'m':0})
    # Forme récente: derniers N matchs par surface
    form_all   = defaultdict(list)   # name → [(date, win:bool)]
    form_clay  = defaultdict(list)
    form_hard  = defaultdict(list)
    form_grass = defaultdict(list)
    # Tendance Elo: valeur il y a TREND_DAYS
    elo_trend_start = defaultdict(lambda: None)  # name → elo quand on entre dans la fenêtre
    elo_at_trend_start = {}
    player_circuit = {}  # name → 'ATP'|'WTA'

    all_rows = []

    datasets = [('tennis_atp','ATP'), ('tennis_wta','WTA')]

    for repo, circuit in datasets:
        print(f"\n=== {circuit} ===")
        for year in YEARS:
            prefix = 'atp' if circuit=='ATP' else 'wta'
            content = fetch_csv(repo, f"{prefix}_matches_{year}.csv")
            if not content: continue
            rows = list(csv.DictReader(io.StringIO(content)))
            print(f"  {year}: {len(rows)} matchs")
            for r in rows:
                r['_circuit'] = circuit
            all_rows.extend(rows)

    all_rows.sort(key=lambda r: r.get('tourney_date','0'))
    print(f"\nTotal: {len(all_rows)} matchs")

    for row in all_rows:
        winner  = row.get('winner_name','').strip()
        loser   = row.get('loser_name','').strip()
        surface = row.get('surface','Hard')
        circuit = row.get('_circuit','ATP')
        date_int = int(row.get('tourney_date','0') or 0)
        if not winner or not loser: continue

        player_circuit[winner] = circuit
        player_circuit[loser]  = circuit

        # Elo
        surf_key = update_elo(elo_global, elo_surf, winner, loser, surface)

        # Tendance Elo: sauvegarder la valeur au début de la fenêtre
        if date_int >= cutoff_trend_int:
            if winner not in elo_at_trend_start:
                elo_at_trend_start[winner] = elo_global[winner] - K_FACTOR*(1-expected_score(elo_global[winner],elo_global[loser]))
            if loser not in elo_at_trend_start:
                elo_at_trend_start[loser] = elo_global[loser] - K_FACTOR*(0-expected_score(elo_global[loser],elo_global[winner]))

        # Forme récente
        if date_int >= cutoff_stats_int:
            form_all[winner].append((date_int, True))
            form_all[loser].append((date_int, False))
            if 'clay' in surface.lower():
                form_clay[winner].append((date_int, True))
                form_clay[loser].append((date_int, False))
            elif 'grass' in surface.lower():
                form_grass[winner].append((date_int, True))
                form_grass[loser].append((date_int, False))
            else:
                form_hard[winner].append((date_int, True))
                form_hard[loser].append((date_int, False))

        # Stats service/retour
        if date_int >= cutoff_stats_int:
            try:
                svpt_w = int(row.get('w_svpt',0) or 0)
                won_w  = int(row.get('w_1stWon',0) or 0) + int(row.get('w_2ndWon',0) or 0)
                svpt_l = int(row.get('l_svpt',0) or 0)
                won_l  = int(row.get('l_1stWon',0) or 0) + int(row.get('l_2ndWon',0) or 0)
                if svpt_w>0:
                    stats_srv[winner]['svpt']+=svpt_w; stats_srv[winner]['won']+=won_w
                    stats_srv[winner]['rpag']+=svpt_l; stats_srv[winner]['rpwon']+=(svpt_l-won_l)
                    stats_srv[winner]['m']+=1
                if svpt_l>0:
                    stats_srv[loser]['svpt']+=svpt_l; stats_srv[loser]['won']+=won_l
                    stats_srv[loser]['rpag']+=svpt_w; stats_srv[loser]['rpwon']+=(svpt_w-won_w)
                    stats_srv[loser]['m']+=1
            except: pass

    # Classements actuels
    print("\nChargement classements...")
    atp_player_ids = fetch_player_ids('tennis_atp', 'atp_players.csv')
    wta_player_ids = fetch_player_ids('tennis_wta', 'wta_players.csv')
    atp_rankings_raw = fetch_rankings('tennis_atp', 'atp_rankings_current.csv')
    wta_rankings_raw = fetch_rankings('tennis_wta', 'wta_rankings_current.csv')

    # Mapper player_id → rank → name
    atp_name_rank = {}
    for pid, rank in atp_rankings_raw.items():
        name = atp_player_ids.get(pid,'')
        if name: atp_name_rank[norm_name(name)] = rank

    wta_name_rank = {}
    for pid, rank in wta_rankings_raw.items():
        name = wta_player_ids.get(pid,'')
        if name: wta_name_rank[norm_name(name)] = rank

    print(f"  ATP: {len(atp_name_rank)} classés")
    print(f"  WTA: {len(wta_name_rank)} classés")

    # Charger ancien players_data.json
    old_data = {'atp':{},'wta':{},'aliases':{'atp':{},'wta':{}}}
    if os.path.exists('players_data.json'):
        with open('players_data.json', encoding='utf-8') as f:
            old_data = json.load(f)

    def calc_form(matches_list, n=5):
        """Calcule le bilan sur les N derniers matchs."""
        recent = sorted(matches_list, key=lambda x: -x[0])[:n]
        if not recent: return None
        wins = sum(1 for _, w in recent if w)
        return {'w': wins, 'l': len(recent)-wins, 'n': len(recent)}

    def calc_trend(name):
        """Calcule la tendance Elo sur TREND_DAYS jours."""
        start = elo_at_trend_start.get(name)
        if start is None: return None
        current = elo_global[name]
        return round(current - start, 1)

    # Construire le nouveau players_data
    new_atp = {}
    new_wta = {}

    all_players = set(elo_global.keys())
    for name in all_players:
        nk = norm_name(name)
        circuit = player_circuit.get(name, 'ATP')

        eg  = round(elo_global[name], 1)
        es  = elo_surf[name]
        s   = stats_srv[name]
        spw = round(s['won']/s['svpt']*100, 1) if s['svpt']>0 else None
        rpw = round(s['rpwon']/s['rpag']*100, 1) if s['rpag']>0 else None

        # Forme récente
        form = {
            'all':   calc_form(form_all[name]),
            'clay':  calc_form(form_clay[name]),
            'hard':  calc_form(form_hard[name]),
            'grass': calc_form(form_grass[name]),
        }

        # Tendance Elo
        trend = calc_trend(name)

        # Classement
        rank_map = atp_name_rank if circuit=='ATP' else wta_name_rank
        rank = rank_map.get(nk)

        player_obj = {
            'name': name,
            'elo': {
                'elo': eg,
                'cElo': round(es['cElo'],1),
                'hElo': round(es['hElo'],1),
                'gElo': round(es['gElo'],1),
                'eloRank': None,  # sera rempli après tri
            },
            'serve': {'spw': spw, 'matches': s['m']} if spw else None,
            'ret': {'rpw': rpw} if rpw else None,
            'form': form,
            'elo_trend': trend,  # points gagnés/perdus sur 90j
            'rank': rank,        # classement ATP/WTA actuel
        }

        # Préserver age et lastMatch
        for d in [old_data.get('atp',{}), old_data.get('wta',{})]:
            if nk in d:
                if d[nk].get('age'): player_obj['age'] = d[nk]['age']
                if d[nk].get('lastMatch'): player_obj['lastMatch'] = d[nk]['lastMatch']
                break

        if circuit == 'WTA':
            new_wta[nk] = player_obj
        else:
            new_atp[nk] = player_obj

    # Calculer eloRank (rang par Elo global)
    for circuit_dict in [new_atp, new_wta]:
        sorted_players = sorted(circuit_dict.items(), key=lambda x: -x[1]['elo']['elo'])
        for rank_pos, (nk, p) in enumerate(sorted_players, 1):
            p['elo']['eloRank'] = rank_pos

    output = {
        'meta': {
            'updated': today.strftime('%Y-%m-%d'),
            'source': 'JeffSackmann/tennis_atp + tennis_wta',
            'atp': len(new_atp),
            'wta': len(new_wta),
        },
        'atp': new_atp,
        'wta': new_wta,
        'aliases': old_data.get('aliases', {'atp':{},'wta':{}}),
    }

    with open('players_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=True, separators=(',',':'))

    print(f"\n✅ players_data.json: {len(new_atp)} ATP, {len(new_wta)} WTA")
    print(f"   Mise à jour: {today}")
    for name in ['Jannik Sinner', 'Carlos Alcaraz', 'Iga Swiatek', 'Aryna Sabalenka']:
        nk = norm_name(name)
        for d in [new_atp, new_wta]:
            if nk in d:
                p = d[nk]
                spw = p['serve']['spw'] if p.get('serve') else 'N/A'
                form = p['form']['all']
                form_str = f"{form['w']}V{form['l']}D" if form else 'N/A'
                print(f"   {name}: Elo={p['elo']['elo']}, cElo={p['elo']['cElo']}, "
                      f"spw={spw}%, trend={p['elo_trend']:+.0f}, "
                      f"rank=#{p['rank']}, form={form_str}")
                break

if __name__ == '__main__':
    main()
