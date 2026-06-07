#!/usr/bin/env python3
"""
fetch_clv.py — Courbe complète Pinnacle (marché 123) via /historical-odds (GRATUIT).
v3 : ne grille plus les matchs sur échec, ré-ouvre les échecs précédents,
     et imprime la structure de la réponse au 1er échec pour diagnostic.
"""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
CLOSING_FILE = 'closing_lines.json'
CLV_LOG = 'clv_history.jsonl'
COOLDOWN = 5.5
MAX_PER_RUN = 40
MAX_ATTEMPTS = 3
STORE_FULL_CURVE = True

def api_get(path, params):
    params = dict(params); params['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True, 200
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode('utf-8','replace')[:160]
        except Exception: pass
        return None, False, e.code
    except Exception as e:
        print(f"  {path}: {e}")
        return None, False, 0

def probe_print(hist):
    """Imprime la forme de la réponse pour comprendre la structure réelle."""
    def keys(o):
        return list(o.keys())[:15] if isinstance(o, dict) else f"<{type(o).__name__}>"
    print("  ── STRUCTURE historical-odds ──")
    print("  top:", keys(hist))
    bk = hist.get('bookmakers') if isinstance(hist, dict) else None
    print("  bookmakers:", type(bk).__name__, keys(bk) if isinstance(bk,(dict,)) else
          (f"len={len(bk)}" if isinstance(bk,list) else bk))
    pin = None
    if isinstance(bk, dict):
        pin = bk.get('pinnacle')
    elif isinstance(bk, list) and bk:
        pin = bk[0]
        print("  bookmakers[0]:", keys(pin))
    if isinstance(pin, dict):
        mk = pin.get('markets')
        print("  pinnacle.markets:", type(mk).__name__,
              keys(mk) if isinstance(mk,dict) else (f"len={len(mk)}" if isinstance(mk,list) else mk))
        m = None
        if isinstance(mk, dict):
            m = mk.get(MARKET) or (list(mk.values())[0] if mk else None)
        elif isinstance(mk, list) and mk:
            m = mk[0]; print("  markets[0]:", keys(m))
        if isinstance(m, dict):
            print("  market keys:", keys(m))
            outs = m.get('outcomes')
            print("  outcomes:", type(outs).__name__,
                  keys(outs) if isinstance(outs,dict) else (f"len={len(outs)}" if isinstance(outs,list) else outs))
            sample = None
            if isinstance(outs, dict) and outs: sample = list(outs.values())[0]
            elif isinstance(outs, list) and outs: sample = outs[0]
            if isinstance(sample, dict):
                print("  outcome sample keys:", keys(sample))
                # chercher une liste de points quelque part dedans
                for k, v in sample.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        print(f"  -> points sous '{k}', 1er point keys:", keys(v[0]))
                        print(f"  -> 1er point:", json.dumps(v[0])[:200])
                        break
                    if isinstance(v, dict) and v:
                        sub = list(v.values())[0]
                        if isinstance(sub, list) and sub and isinstance(sub[0], dict):
                            print(f"  -> points sous '{k}'.<key>, 1er point keys:", keys(sub[0]))
                            print(f"  -> 1er point:", json.dumps(sub[0])[:200])
                            break
    print("  brut (1200c):", json.dumps(hist)[:1200])
    print("  ───────────────────────────────")

def parse_curve(hist, side):
    if not isinstance(hist, dict): return []
    bk = hist.get('bookmakers')
    if not isinstance(bk, dict): return []
    pin = bk.get('pinnacle')
    if not isinstance(pin, dict): return []
    mkts = pin.get('markets')
    if not isinstance(mkts, dict): return []
    mkt = mkts.get(MARKET)
    if not isinstance(mkt, dict): return []
    outs = mkt.get('outcomes')
    if not isinstance(outs, dict): return []
    for oid, oc in outs.items():
        if not isinstance(oc, dict): continue
        players = oc.get('players')
        if not isinstance(players, dict): continue
        for pk, points in players.items():
            if not isinstance(points, list) or not points: continue
            lbl = None
            for p in points:
                if p.get('bookmakerOutcomeId') in ('home','away'):
                    lbl = p['bookmakerOutcomeId']; break
            if lbl != side: continue
            parsed = []
            for p in points:
                t, pr = p.get('createdAt',''), p.get('price')
                if pr is None or not t: continue
                try:
                    dt = datetime.datetime.fromisoformat(t.replace('Z','+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
                parsed.append((dt, pr))
            parsed.sort(key=lambda x: x[0])
            return parsed
    return []

def analyze_side(curve, start):
    if not curve: return None
    open_price = curve[0][1]
    if start:
        before = [pr for dt, pr in curve if dt <= start]
        close_price = before[-1] if before else curve[-1][1]
    else:
        close_price = curve[-1][1]
    prices = [pr for _, pr in curve]
    move_pct = round((close_price-open_price)/open_price*100,2) if open_price else None
    amp = round(max(abs(max(prices)-open_price),abs(min(prices)-open_price))/open_price*100,2) if open_price else None
    return {'open':open_price,'close':close_price,'move_pct':move_pct,'amplitude_pct':amp,
            'min':min(prices),'max':max(prices),'n_points':len(curve),
            'first_t':curve[0][0].isoformat(),'last_t':curve[-1][0].isoformat()}

def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    if not os.path.exists(CLOSING_FILE):
        print("Pas de closing_lines.json"); return
    with open(CLOSING_FILE, encoding='utf-8') as f:
        closing = json.load(f)

    # ── self-heal : ré-ouvrir les 'done' sans courbe (échecs précédents) ──
    healed = 0
    for uid, m in closing.items():
        if m.get('clv_hist_done') and not m.get('clv_home') and m.get('clv_attempts',0) < MAX_ATTEMPTS:
            m['clv_hist_done'] = False; healed += 1
    if healed:
        print(f"♻️  {healed} entrées 'traitées' sans courbe ré-ouvertes (échec précédent)")

    now = datetime.datetime.utcnow()
    todo = []
    for uid, m in closing.items():
        ct = m.get('commence_time',''); fid = m.get('fixture_id') or m.get('id')
        if not ct or not fid or m.get('clv_hist_done'): continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start > now: continue
        todo.append((uid, m, fid, start))
    print(f"{len(todo)} matchs à traiter (max {MAX_PER_RUN}/run)")
    todo = todo[:MAX_PER_RUN]; done = 0
    dumped = False; warned_http = False

    with open(CLV_LOG, 'a', encoding='utf-8') as logf:
        for uid, m, fid, start in todo:
            time.sleep(COOLDOWN)
            hist, ok, code = api_get('historical-odds', {'fixtureId': fid, 'bookmakers':'pinnacle'})
            if not ok or not hist:
                m['clv_attempts'] = m.get('clv_attempts',0) + 1
                if not warned_http:
                    print(f"  ⚠️ pas de données (HTTP {code}) pour fixtureId={fid} — {m.get('home')} vs {m.get('away')}")
                    warned_http = True
                continue
            try:
                ch = parse_curve(hist,'home'); ca = parse_curve(hist,'away')
            except Exception as e:
                ch = ca = []; print(f"  parse error: {e}")
            ah = analyze_side(ch, start); aa = analyze_side(ca, start)
            if not ah or not aa:
                m['clv_attempts'] = m.get('clv_attempts',0) + 1
                if not dumped:
                    print(f"  ⚠️ réponse reçue mais courbe vide — {m.get('home')} vs {m.get('away')} (fixtureId={fid})")
                    probe_print(hist); dumped = True
                if m['clv_attempts'] >= MAX_ATTEMPTS:
                    m['clv_hist_done'] = True   # abandon après MAX_ATTEMPTS
                continue
            m['clv_home'] = ah; m['clv_away'] = aa; m['clv_hist_done'] = True
            m['clv_attempts'] = m.get('clv_attempts',0) + 1
            entry = {'uid':uid,'fixture_id':fid,'commence_time':m.get('commence_time'),
                     'home':m.get('home'),'away':m.get('away'),'tournament':m.get('tournament'),
                     'home_metrics':ah,'away_metrics':aa}
            if STORE_FULL_CURVE:
                entry['home_curve'] = [(dt.isoformat(),pr) for dt,pr in ch]
                entry['away_curve'] = [(dt.isoformat(),pr) for dt,pr in ca]
            logf.write(json.dumps(entry, ensure_ascii=False)+'\n')
            done += 1
            print(f"  ✅ {m.get('home')} vs {m.get('away')} | home {ah['open']}→{ah['close']} ({ah['move_pct']:+.1f}%, {ah['n_points']}pts)")

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {done} matchs analysés (courbe complète, gratuit hors quota)")

if __name__ == '__main__':
    main()
