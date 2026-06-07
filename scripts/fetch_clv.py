#!/usr/bin/env python3
"""
fetch_clv.py — Récupère via /historical-odds (GRATUIT) la COURBE COMPLÈTE des cotes
Pinnacle (marché 123) de chaque match joué, et en extrait des métriques d'analyse :
ouverture/clôture, amplitude max, mouvement net, nb de points, + la courbe brute.
Permet d'étudier rétrospectivement le pouvoir prédictif des mouvements, sans quota.
"""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
CLOSING_FILE = 'closing_lines.json'
CLV_LOG = 'clv_history.jsonl'
COOLDOWN = 5.5
MAX_PER_RUN = 40
STORE_FULL_CURVE = True

def api_get(path, params):
    params = dict(params); params['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  HTTP {e.code} {path}: {e.read().decode('utf-8','replace')[:120]}")
        return None, False
    except Exception as e:
        print(f"  {path}: {e}")
        return None, False

def parse_curve(hist, side):
    pin = hist.get('bookmakers', {}).get('pinnacle', {})
    mkt = pin.get('markets', {}).get(MARKET)
    if not mkt: return []
    for oid, oc in mkt.get('outcomes', {}).items():
        for pk, points in oc.get('players', {}).items():
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
    max_dev = max((pr-open_price) for pr in prices)
    min_dev = min((pr-open_price) for pr in prices)
    amp = round(max(abs(max_dev),abs(min_dev))/open_price*100,2) if open_price else None
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
    with open(CLV_LOG, 'a', encoding='utf-8') as logf:
        for uid, m, fid, start in todo:
            time.sleep(COOLDOWN)
            hist, ok = api_get('historical-odds', {'fixtureId': fid, 'bookmakers':'pinnacle'})
            if not ok or not hist: continue
            ch = parse_curve(hist,'home'); ca = parse_curve(hist,'away')
            ah = analyze_side(ch, start); aa = analyze_side(ca, start)
            if not ah or not aa:
                m['clv_hist_done'] = True; continue
            m['clv_home'] = ah; m['clv_away'] = aa; m['clv_hist_done'] = True
            entry = {'uid':uid,'fixture_id':fid,'commence_time':m.get('commence_time'),
                     'home':m.get('home'),'away':m.get('away'),'tournament':m.get('tournament'),
                     'home_metrics':ah,'away_metrics':aa}
            if STORE_FULL_CURVE:
                entry['home_curve'] = [(dt.isoformat(),pr) for dt,pr in ch]
                entry['away_curve'] = [(dt.isoformat(),pr) for dt,pr in ca]
            logf.write(json.dumps(entry, ensure_ascii=False)+'\n')
            done += 1
            print(f"  ✅ {m.get('home')} vs {m.get('away')} | home {ah['open']}→{ah['close']} ({ah['move_pct']:+.1f}%, amp {ah['amplitude_pct']}%, {ah['n_points']}pts)")
    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {done} matchs analysés (courbe complète, gratuit hors quota)")

if __name__ == '__main__':
    main()
