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


def compute_score(cols, headers):
    """Score de confiance 0-100 = Signal x Fiabilite.
    Combine qualite des donnees, forme/tendance, convergence bookmakers, ecart Elo.
    Ne depend PAS de l'EV (souvent gonfle par le modele)."""
    def col(n): return headers.index(n) if n in headers else -1
    def gv(n):
        i = col(n)
        if i < 0 or i >= len(cols): return None
        v = cols[i]
        if v in ('', 'nan'): return None
        try: return float(v)
        except: return None
    def gs(n):
        i = col(n)
        if i < 0 or i >= len(cols): return ''
        return cols[i]

    coteA = gv('coteA'); coteB = gv('coteB')
    if not coteA or not coteB: return None

    # Cote favorite = cote la plus basse = cote sur laquelle on raisonne
    side_A = coteA <= coteB
    cote_s = coteA if side_A else coteB

    elo_a = gv('elo_a'); elo_b = gv('elo_b')
    srv_a = gv('srv_a'); srv_b = gv('srv_b')
    ret_a = gv('ret_a'); ret_b = gv('ret_b')
    trend_a = gv('trend_elo_a'); trend_b = gv('trend_elo_b')
    rank_a = gv('rank_a'); rank_b = gv('rank_b')
    psA = gv('psA'); psB = gv('psB')
    mxA = gv('mxA'); mxB = gv('mxB')
    avA = gv('avA'); avB = gv('avB')
    forme_a = gs('forme_surf_a'); forme_b = gs('forme_surf_b')

    elo_s = elo_a if side_A else elo_b
    elo_o = elo_b if side_A else elo_a
    trend_s = trend_a if side_A else trend_b
    forme_s = forme_a if side_A else forme_b

    # ── SIGNAL (conviction 0-100) ────────────────────────────────────────
    signal = 0

    # Forme recente + tendance (priorite 2) — max 35 pts
    # Forme: "5V0D" = 5 victoires 0 defaites
    if forme_s:
        try:
            v = int(forme_s.split('V')[0])
            d = int(forme_s.split('V')[1].replace('D',''))
            tot = v + d
            if tot > 0:
                wr = v / tot
                if   wr >= 0.8: signal += 20
                elif wr >= 0.6: signal += 14
                elif wr >= 0.4: signal += 8
                else: signal += 3
        except: pass
    if trend_s is not None:
        if   trend_s >= 50: signal += 15
        elif trend_s >= 20: signal += 10
        elif trend_s >= 0:  signal += 5
        elif trend_s <= -50: signal += 0  # forte baisse = pas de bonus

    # Convergence bookmakers (priorite 3) — max 30 pts
    # Les cotes Pinnacle/Max/Avg sont-elles alignees ?
    ps_s = psA if side_A else psB
    mx_s = mxA if side_A else mxB
    av_s = avA if side_A else avB
    books = [b for b in [ps_s, mx_s, av_s] if b and b > 1]
    if len(books) >= 2:
        spread = (max(books) - min(books)) / min(books)
        if   spread < 0.02: signal += 30   # tres aligne = signal fiable
        elif spread < 0.05: signal += 20
        elif spread < 0.10: signal += 10
        else: signal += 3                   # divergence = signal flou
    elif len(books) == 1:
        signal += 8

    # Ecart Elo (priorite 4) — max 35 pts
    if elo_s is not None and elo_o is not None:
        diff = abs(elo_s - elo_o)
        if   diff >= 200: signal += 35
        elif diff >= 120: signal += 25
        elif diff >= 60:  signal += 15
        elif diff >= 20:  signal += 8
        else: signal += 3

    signal = min(100, signal)

    # ── FIABILITE (multiplicateur 40-100%) ───────────────────────────────
    # Priorite 1 : qualite/presence des donnees
    # Donnees incompletes = score modere (pas exclu) → plancher a 40%
    present = 0; total = 6
    if elo_a is not None and elo_b is not None: present += 1
    if srv_a is not None and srv_b is not None: present += 1
    if ret_a is not None and ret_b is not None: present += 1
    if trend_a is not None or trend_b is not None: present += 1
    if rank_a is not None or rank_b is not None: present += 1
    if forme_a or forme_b: present += 1

    fiab = 0.40 + 0.60 * (present / total)  # 40% si rien, 100% si tout

    score = round(signal * fiab)
    return max(0, min(100, score))

def enrich_backtest(D):
    """Met à jour le CSV backtest avec toutes les données depuis players_data.json."""
    BACKTEST_FILE = 'backtest_tennis.csv'
    if not os.path.exists(BACKTEST_FILE):
        print("  Pas de fichier backtest_tennis.csv")
        return

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

        # Score de confiance auto — toujours recalculé (métrique dérivée des données)
        iSc = col('score_confiance')
        if iSc >= 0:
            sc = compute_score(cols, headers)
            if sc is not None:
                while len(cols) <= iSc: cols.append('')
                if cols[iSc] != str(sc):
                    cols[iSc] = str(sc)
                    changed = True

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
    iSrc = headers.index('src_resultat') if 'src_resultat' in headers else -1

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
        _prov = (iSrc >= 0 and iSrc < len(cols) and cols[iSrc] == 'api_fast')
        if cols[iRes] != '' and not _prov:  # déjà CONFIRMÉ par Sackmann → on garde
            new_lines.append(line)
            continue
        # (si _prov : on re-traite pour confirmer + lever le marqueur)

        ja = norm_name(cols[iJA] if iJA < len(cols) else '')
        jb = norm_name(cols[iJB] if iJB >= 0 and iJB < len(cols) else '')
        dt = cols[iDt].replace('-','') if iDt >= 0 and iDt < len(cols) else ''

        best_match = None
        best_gap = 99999
        # Date du match backtest en objet date (pour calcul d'écart en JOURS réels)
        dt_obj = None
        if dt and len(dt) == 8:
            try: dt_obj = datetime.datetime.strptime(dt, '%Y%m%d')
            except: dt_obj = None

        for m in sackmann_results:
            mdt = m.get('date','').replace('-','')
            # Écart en JOURS réels entre les deux dates
            gap = 0
            if dt_obj and mdt and len(mdt) == 8:
                try:
                    mdt_obj = datetime.datetime.strptime(mdt, '%Y%m%d')
                    gap = abs((dt_obj - mdt_obj).days)
                except:
                    gap = 0
            # Tolérance 18 jours : Sackmann date tous les matchs d'un tournoi à la
            # tourney_date (lundi de début). Un Grand Chelem dure ~13-14j ; 18j donne
            # une marge de sécurité pour ne jamais rater la finale. Le matching reste
            # fiable car il s'appuie sur les noms des DEUX joueurs (très discriminants).
            if dt_obj and mdt and gap > 18:
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

            # Garder le résultat le plus proche en date (évite de confondre
            # deux rencontres des mêmes joueurs dans des tournois différents)
            if gap < best_gap:
                best_gap = gap
                best_match = m

        if best_match is not None:
            winner = norm_name(best_match.get('winner',''))
            last_ja = ja.split(' ')[-1]
            last_winner = winner.split(' ')[-1]
            cols[iRes] = '1' if last_winner == last_ja else '0'
            if iAno >= 0 and best_match.get('anomalie'):
                cols[iAno] = best_match['anomalie']
            if iSrc >= 0 and iSrc < len(cols):
                cols[iSrc] = ''   # confirmé par Sackmann → marqueur provisoire levé
            updated += 1

        new_lines.append(';'.join(cols))

    with open(BACKTEST_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    print(f"  ✅ Résultats backtest: {updated} matchs mis à jour")

# ── Main ──────────────────────────────────────────────────────────────────

def _parse_dt(s):
    """Parse un timestamp ISO (avec ou sans Z/tz) en datetime naïf UTC."""
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if d.tzinfo is not None:
            d = d.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return d
    except Exception:
        return None


def _hist_snapshot(cl, target_mins):
    """Reconstruit le snapshot Pinnacle {home, away} à ~target_mins avant le match,
    à partir de l'history (utilisé quand pinnacle_60min/15min est absent).
    On recalcule mins_before depuis commence_time quand possible (le champ stocké
    est parfois incohérent), et on prend le point capturé le plus proche de la cible,
    parmi les captures d'avant-match.
    """
    hist = cl.get('history', [])
    if not hist:
        return None
    ct = _parse_dt(cl.get('commence_time'))
    cand = []
    for p in hist:
        h, a = p.get('home'), p.get('away')
        if not (h and a and h > 1 and a > 1):
            continue
        mb = None
        if ct is not None:
            t = _parse_dt(p.get('t'))
            if t is not None:
                mb = (ct - t).total_seconds() / 60.0
        if mb is None:
            mb = p.get('mins_before')
        if mb is None:
            continue
        if mb < -5:                       # capture postérieure au match -> ignorée
            continue
        cand.append((abs(mb - target_mins), p))
    if not cand:
        p = hist[-1]                       # repli : dernier point connu
        if p.get('home') and p.get('away'):
            return {'home': p['home'], 'away': p['away']}
        return None
    cand.sort(key=lambda x: x[0])
    p = cand[0][1]
    return {'home': p['home'], 'away': p['away']}


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

    # ── Jointure robuste backtest <-> closing_lines ───────────────────────
    SUFFIX = {'jr', 'sr', 'jnr', 'snr', 'ii', 'iii', 'iv'}

    def _name_tokens(s):
        return [t for t in norm_name(s).split() if t and t not in SUFFIX]

    def _ln(s):
        t = _name_tokens(s)
        return t[-1] if t else ''

    def _player_eq(bt, cln):
        """Même joueur ? Nom de famille égal (suffixes Jr/II… ignorés) ET même
        initiale de prénom si dispo — distingue les frères (Cerundolo J. vs F.)."""
        if not bt or not cln or _ln(bt) != _ln(cln):
            return False
        a, b = _name_tokens(bt), _name_tokens(cln)
        if len(a) >= 2 and len(b) >= 2 and a[0] and b[0] and a[0][0] != b[0][0]:
            return False
        return True

    def _cl_date(cl):
        return cl.get('date') or str(cl.get('commence_time', ''))[:10] or ''

    def _date_dist(d1, d2):
        a = re.sub(r'[^0-9]', '', d1 or '')[:8]
        b = re.sub(r'[^0-9]', '', d2 or '')[:8]
        if len(a) == 8 and len(b) == 8:
            try:
                return abs(int(a) - int(b))
            except Exception:
                return 10 ** 9
        return 0 if not (a or b) else 10 ** 9

    def _best_closing(fullA, fullB, bt_date):
        """(uid, cl, a_is_home) du meilleur match ; si plusieurs, le plus proche en date."""
        cands = []
        for uid, cl in closing.items():
            h, a = cl.get('home', ''), cl.get('away', '')
            if _player_eq(fullA, h) and _player_eq(fullB, a):
                cands.append((uid, cl, True))
            elif _player_eq(fullA, a) and _player_eq(fullB, h):
                cands.append((uid, cl, False))
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        return min(cands, key=lambda c: _date_dist(bt_date, _cl_date(c[1])))

    updated = 0
    new_lines = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            new_lines.append(line); continue
        cols = line.split(';')
        while len(cols) < len(headers): cols.append('')

        coteA = cols[iCoteA] if iCoteA >= 0 else ''
        fullA = cols[iJA] if iJA >= 0 else ''
        fullB = cols[iJB] if iJB >= 0 else ''
        bt_date = cols[iDt].strip() if (iDt >= 0 and iDt < len(cols)) else ''

        best = _best_closing(fullA, fullB, bt_date)
        if best:
            uid, cl, a_is_home = best

            # Cote de référence = cote d'ouverture (1er point de l'history).
            hist = cl.get('history', [])
            ref_a = None
            if hist:
                first = hist[0]
                ref_a = first['home'] if a_is_home else first['away']
            if not ref_a or ref_a <= 1:
                try:
                    ref_a = float(coteA) if coteA else 0
                except Exception:
                    ref_a = 0

            if ref_a and ref_a > 1:
                # CLV 60min : ouverture vs Pinnacle ~60min (ponctuel sinon history)
                p60 = cl.get('pinnacle_60min') or _hist_snapshot(cl, 60)
                if p60 and iC60 >= 0:
                    pin_a = p60['home'] if a_is_home else p60['away']
                    if pin_a and pin_a > 1:
                        clv60 = (ref_a / pin_a - 1) * 100
                        if cols[iC60] != f"{clv60:.2f}":
                            cols[iC60] = f"{clv60:.2f}"
                            updated += 1
                # CLV 15min : ouverture vs Pinnacle ~15min / clôture (ponctuel sinon history)
                p15 = cl.get('pinnacle_15min') or _hist_snapshot(cl, 15)
                if p15 and iC15 >= 0:
                    pin_a = p15['home'] if a_is_home else p15['away']
                    if pin_a and pin_a > 1:
                        clv15 = (ref_a / pin_a - 1) * 100
                        cols[iC15] = f"{clv15:.2f}"

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
