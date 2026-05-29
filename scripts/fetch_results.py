#!/usr/bin/env python3
"""
Script GitHub Actions — Récupère les résultats tennis depuis GitHub Sackmann
et enrichit le CSV backtest avec Elo/stats depuis players_data.json.
Tourne chaque nuit à 2h UTC.
"""
import urllib.request, json, datetime, csv, io, os, re, unicodedata

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# ── Chargement des données joueurs ────────────────────────────────────────
def load_players():
    """Charge players_data.json depuis le repo."""
    if os.path.exists('players_data.json'):
        with open('players_data.json', encoding='utf-8') as f:
            return json.load(f)
    return None

def norm_name(s):
    """Normalise un nom pour la recherche."""
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[.\s]+', ' ', s).strip()


def detect_anomalie(score):
    """Détecte abandon ou renversement anormal depuis le score Sackmann."""
    if not score: return ''
    s = str(score).upper()
    # Abandon / walkover
    if 'RET' in s or 'W/O' in s or 'WO' in s or 'DEF' in s or 'ABD' in s:
        return 'abandon'
    # Renversement: le winner a perdu les 2 premiers sets (adversaire effondré)
    sets = s.split()
    if len(sets) >= 4:
        winner_first_two = 0
        for st in sets[:2]:
            if '-' in st:
                try:
                    a = st.split('-')[0]
                    b = st.split('-')[1].split('(')[0]
                    if int(a) > int(b): winner_first_two += 1
                except: pass
        if winner_first_two == 0:
            return 'renversement'
    return ''

def find_player(D, name):
    """Trouve un joueur dans D par nom."""
    if not D: return None
    k = norm_name(name)
    if k in D.get('atp', {}): return D['atp'][k]
    if k in D.get('wta', {}): return D['wta'][k]
    last = k.split(' ')[-1]
    for circuit in ['atp', 'wta']:
        for key, p in D.get(circuit, {}).items():
            if last in norm_name(p.get('name', '')).split(' '):
                return p
    return None

def elo_key(surface):
    s = str(surface).lower()
    if 'clay' in s: return 'cElo'
    if 'grass' in s: return 'gElo'
    return 'hElo'

# ── GitHub API ────────────────────────────────────────────────────────────
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
    api_url = f"https://api.github.com/repos/JeffSackmann/{repo}/contents/{filename}"
    meta = json.loads(github_get(api_url))
    download_url = meta.get('download_url')
    if not download_url:
        raise ValueError(f"Pas de download_url pour {filename}")
    req = urllib.request.Request(download_url, headers={'User-Agent': 'tennis-edge-bot/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

def get_recent_matches(csv_content, days=30):
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    cutoff_int = int(cutoff.strftime('%Y%m%d'))
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    if rows:
        dates = [r.get('tourney_date','0') for r in rows if r.get('tourney_date','0').isdigit()]
        if dates:
            print(f"  Dernière date dans CSV: {max(dates)}")
    return [r for r in rows if r.get('tourney_date','0').isdigit() and int(r.get('tourney_date','0')) >= cutoff_int]

# ── Enrichissement backtest CSV ───────────────────────────────────────────
def get_surf_key(surf):
    s = str(surf).lower()
    if 'clay' in s: return 'clay'
    if 'grass' in s: return 'grass'
    return 'hard'

def enrich_backtest(D):
    """Met à jour le CSV backtest avec toutes les données depuis players_data.json."""
    BACKTEST_FILE = 'backtest_tennis.csv'
    if not os.path.exists(BACKTEST_FILE):
        print("  Pas de fichier backtest_tennis.csv")
        return
    # Diagnostic : vérifier que le rank est bien présent dans D
    test = find_player(D, 'Jannik Sinner')
    if test:
        print(f"  [diag] Sinner: rank={test.get('rank')}, trend={test.get('elo_trend')}, form={'oui' if test.get('form') else 'non'}")
    test2 = find_player(D, 'Iga Swiatek')
    if test2:
        print(f"  [diag] Swiatek: rank={test2.get('rank')}")

    with open(BACKTEST_FILE, encoding='utf-8') as f:
        raw = f.read()

    lines = raw.strip().split('\n')
    if len(lines) < 2: return
    headers = lines[0].split(';')

    def col(name): return headers.index(name) if name in headers else -1

    iJA    = col('joueurA'); iJB = col('joueurB')
    iSurf  = col('surf')
    iEloA  = col('elo_a');   iEloB  = col('elo_b')
    iSrvA  = col('srv_a');   iSrvB  = col('srv_b')
    iRetA  = col('ret_a');   iRetB  = col('ret_b')
    iTrA   = col('trend_elo_a'); iTrB = col('trend_elo_b')
    iRkA   = col('rank_a');  iRkB   = col('rank_b')
    iFsA   = col('forme_surf_a'); iFsB = col('forme_surf_b')
    print(f"  [diag] index: rank_a={iRkA}, rank_b={iRkB}, trend_a={iTrA}, elo_a={col('elo_a')}")
    print(f"  [diag] header ({len(headers)} cols): {headers}")

    updated = 0
    new_lines = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            new_lines.append(line)
            continue
        cols = line.split(';')
        # Étendre si colonnes manquantes
        while len(cols) < len(headers):
            cols.append('')

        name_a = cols[iJA] if iJA >= 0 and iJA < len(cols) else ''
        name_b = cols[iJB] if iJB >= 0 and iJB < len(cols) else ''
        surf   = cols[iSurf] if iSurf >= 0 and iSurf < len(cols) else 'Hard'
        ek     = elo_key(surf)
        sk     = get_surf_key(surf)

        pA = find_player(D, name_a) if name_a else None
        pB = find_player(D, name_b) if name_b else None

        changed = False
        def set_col(i, val):
            nonlocal changed
            if i >= 0 and i < len(cols) and (not cols[i] or cols[i] == '') and val is not None:
                cols[i] = str(val)
                changed = True

        if pA:
            set_col(iEloA, (pA.get('elo') or {}).get(ek) or (pA.get('elo') or {}).get('elo'))
            set_col(iSrvA, pA.get('serve',{}).get('spw') if pA.get('serve') else None)
            set_col(iRetA, pA.get('ret',{}).get('rpw') if pA.get('ret') else None)
            set_col(iTrA,  pA.get('elo_trend'))
            set_col(iRkA,  pA.get('rank'))
            form_a = (pA.get('form') or {}).get(sk)
            if form_a:
                set_col(iFsA, f"{form_a.get('w',0)}V{form_a.get('l',0)}D")

        if pB:
            set_col(iEloB, (pB.get('elo') or {}).get(ek) or (pB.get('elo') or {}).get('elo'))
            set_col(iSrvB, pB.get('serve',{}).get('spw') if pB.get('serve') else None)
            set_col(iRetB, pB.get('ret',{}).get('rpw') if pB.get('ret') else None)
            set_col(iTrB,  pB.get('elo_trend'))
            set_col(iRkB,  pB.get('rank'))
            form_b = (pB.get('form') or {}).get(sk)
            if form_b:
                set_col(iFsB, f"{form_b.get('w',0)}V{form_b.get('l',0)}D")

        if changed:
            updated += 1
        new_lines.append(';'.join(cols))

    with open(BACKTEST_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    print(f"  ✅ Backtest enrichi: {updated} matchs mis à jour")

def update_backtest_results(sackmann_results):
    """Met à jour la colonne resultat dans le CSV backtest."""
    BACKTEST_FILE = 'backtest_tennis.csv'
    if not os.path.exists(BACKTEST_FILE): return

    with open(BACKTEST_FILE, encoding='utf-8') as f:
        content = f.read()

    lines = content.strip().split('\n')
    if len(lines) < 2: return
    headers = lines[0].split(';')

    iJA  = headers.index('joueurA') if 'joueurA' in headers else -1
    iJB  = headers.index('joueurB') if 'joueurB' in headers else -1
    iRes = headers.index('resultat') if 'resultat' in headers else -1
    iDt  = headers.index('date_match') if 'date_match' in headers else -1
    iAno = headers.index('anomalie') if 'anomalie' in headers else -1

    if iJA < 0 or iRes < 0: return

    updated = 0
    new_lines = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            new_lines.append(line)
            continue
        cols = line.split(';')
        while len(cols) < len(headers):
            cols.append('')
        if cols[iRes] != '':  # déjà rempli
            new_lines.append(line)
            continue

        ja = norm_name(cols[iJA] if iJA < len(cols) else '')
        jb = norm_name(cols[iJB] if iJB >= 0 and iJB < len(cols) else '')
        dt = cols[iDt].replace('-','') if iDt >= 0 and iDt < len(cols) else ''

        for m in sackmann_results:
            mdt = m.get('date','').replace('-','')
            if dt and mdt and abs(int(dt or 0) - int(mdt or 0)) > 5:
                continue
            winner = norm_name(m.get('winner',''))
            mja = norm_name(m.get('home_team',''))
            mjb = norm_name(m.get('away_team',''))

            last_ja = ja.split(' ')[-1]
            last_jb = jb.split(' ')[-1]
            last_mja = mja.split(' ')[-1]
            last_mjb = mjb.split(' ')[-1]

            match = (last_ja == last_mja and last_jb == last_mjb) or \
                    (last_ja == last_mjb and last_jb == last_mja)
            if not match: continue

            last_winner = winner.split(' ')[-1]
            cols[iRes] = '1' if last_winner == last_ja else '0'
            # Marquer l'anomalie (abandon/renversement)
            if iAno >= 0 and m.get('anomalie'):
                cols[iAno] = m['anomalie']
            updated += 1
            break

        new_lines.append(';'.join(cols))

    with open(BACKTEST_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    print(f"  ✅ Résultats backtest: {updated} matchs mis à jour")

# ── Main ──────────────────────────────────────────────────────────────────

def enrich_closing_lines():
    """Calcule le CLV vs closing lines Pinnacle pour le backtest."""
    BACKTEST_FILE = 'backtest_tennis.csv'
    CLOSING_FILE = 'closing_lines.json'
    if not os.path.exists(BACKTEST_FILE) or not os.path.exists(CLOSING_FILE):
        print("  Pas de backtest ou closing_lines.json")
        return

    with open(CLOSING_FILE, encoding='utf-8') as f:
        closing = json.load(f)

    with open(BACKTEST_FILE, encoding='utf-8') as f:
        raw = f.read()
    lines = raw.strip().split('\n')
    if len(lines) < 2: return
    headers = lines[0].split(';')

    def col(n): return headers.index(n) if n in headers else -1
    iJA = col('joueurA'); iJB = col('joueurB')
    iCoteA = col('coteA'); iCoteB = col('coteB')
    iDt = col('date_match')
    iC60 = col('clv_closing_60'); iC15 = col('clv_closing_15')

    if iC60 < 0 or iC15 < 0:
        print("  Colonnes clv_closing absentes")
        return

    # Indexer les closing lines par nom de famille
    def last_name(s):
        return norm_name(s).split(' ')[-1] if s else ''

    updated = 0
    new_lines = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            new_lines.append(line); continue
        cols = line.split(';')
        while len(cols) < len(headers): cols.append('')

        ja = last_name(cols[iJA]) if iJA>=0 else ''
        jb = last_name(cols[iJB]) if iJB>=0 else ''
        coteA = cols[iCoteA] if iCoteA>=0 else ''

        # Chercher le match dans closing_lines
        for uid, cl in closing.items():
            clh = last_name(cl.get('home',''))
            cla = last_name(cl.get('away',''))
            if {ja, jb} != {clh, cla}: continue

            # joueurA correspond à home ou away ?
            a_is_home = (ja == clh)

            try:
                ca = float(coteA) if coteA else 0
            except: ca = 0
            if ca <= 1: break

            # CLV 60min
            p60 = cl.get('pinnacle_60min')
            if p60 and iC60>=0 and not cols[iC60]:
                pin_a = p60['home'] if a_is_home else p60['away']
                if pin_a and pin_a > 1:
                    clv60 = (ca/pin_a - 1) * 100
                    cols[iC60] = f"{clv60:.2f}"
                    updated += 1

            # CLV 15min (vraie closing)
            p15 = cl.get('pinnacle_15min')
            if p15 and iC15>=0 and not cols[iC15]:
                pin_a = p15['home'] if a_is_home else p15['away']
                if pin_a and pin_a > 1:
                    clv15 = (ca/pin_a - 1) * 100
                    cols[iC15] = f"{clv15:.2f}"
            break

        new_lines.append(';'.join(cols))

    with open(BACKTEST_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    print(f"  ✅ CLV closing: {updated} matchs mis à jour")


def main():
    today = datetime.date.today()
    results = []

    # Charger données joueurs
    D = load_players()
    if D:
        print(f"✅ players_data.json chargé: {len(D.get('atp',{}))} ATP, {len(D.get('wta',{}))} WTA")
    else:
        print("⚠️ players_data.json non trouvé")

    datasets = [
        ('tennis_atp', 'atp_matches_2026.csv', 'ATP'),
        ('tennis_wta', 'wta_matches_2026.csv', 'WTA'),
    ]

    for repo, filename, circuit in datasets:
        print(f"\nFetching {circuit}...")
        try:
            csv_content = fetch_sackmann_csv(repo, filename)
            matches = get_recent_matches(csv_content, days=30)
            print(f"  {len(matches)} matchs sur 30 jours")

            for row in matches:
                date_str = row.get('tourney_date', '')
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

                winner = row.get('winner_name', '')
                loser = row.get('loser_name', '')
                tournament = row.get('tourney_name', '')
                surface = row.get('surface', '')

                # Enrichir avec Elo/stats
                ek = elo_key(surface)
                pW = find_player(D, winner) if D else None
                pL = find_player(D, loser) if D else None

                result = {
                    'id': f"{date_str}_{norm_name(winner)}_{norm_name(loser)}".replace(' ','_'),
                    'date': date_str,
                    'tournament': tournament,
                    'circuit': circuit,
                    'surface': surface,
                    'home_team': winner,
                    'away_team': loser,
                    'winner': winner,
                    'winner_code': 1,
                    'score': row.get('score', ''),
                    'completed': True,
                    # Stats Sackmann
                    'aces_home': row.get('w_ace', ''),
                    'aces_away': row.get('l_ace', ''),
                    'df_home': row.get('w_df', ''),
                    'df_away': row.get('l_df', ''),
                    'first_serve_won_home': row.get('w_1stWon', ''),
                    'first_serve_won_away': row.get('l_1stWon', ''),
                    'rank_home': row.get('winner_rank', ''),
                    'rank_away': row.get('loser_rank', ''),
                    'anomalie': detect_anomalie(row.get('score', '')),
                    # Elo/stats depuis players_data.json
                    'elo_home': pW.get('elo', {}).get(ek) if pW else '',
                    'elo_away': pL.get('elo', {}).get(ek) if pL else '',
                    'spw_home': pW.get('serve', {}).get('spw', '') if pW else '',
                    'spw_away': pL.get('serve', {}).get('spw', '') if pL else '',
                    'rpw_home': pW.get('ret', {}).get('rpw', '') if pW else '',
                    'rpw_away': pL.get('ret', {}).get('rpw', '') if pL else '',
                }
                results.append(result)

        except Exception as e:
            print(f"  Erreur: {e}")

    print(f"\n{len(results)} résultats au total")

    # Sauvegarder resultats.json
    output = {
        'updated': today.strftime('%Y-%m-%d'),
        'generated_at': datetime.datetime.utcnow().isoformat(),
        'source': 'JeffSackmann + players_data.json',
        'count': len(results),
        'results': results
    }
    with open('resultats.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ resultats.json: {len(results)} résultats")

    # Enrichir et mettre à jour le backtest
    if D:
        print("\nEnrichissement backtest...")
        enrich_backtest(D)
        update_backtest_results(results)
        enrich_closing_lines()

if __name__ == '__main__':
    main()
