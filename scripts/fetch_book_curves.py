#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_book_curves.py — Recupere la COURBE historique d'un book MOU (defaut: unibet)
via /historical-odds (GRATUIT), pour la comparer ensuite a Pinnacle (book_lag.py).
Independant de fetch_clv (qui gere Pinnacle). Ecrit book_curves.jsonl (1 ligne/match/book).
Backfill les matchs deja captures + accumule en avant. Lecture closing_lines.json.
"""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
# Marqueurs de la FIN DU SET 1 : marchés de set 2 (vainqueur set2, score exact set2),
# qui ne s'activent qu'après le set 1. Leur 1er createdAt ≈ fin du set 1.
SET2_MARKERS = [s.strip() for s in os.environ.get('SET2_MARKERS', '12542,12624').split(',') if s.strip()]
CLOSING_FILE = 'closing_lines.json'
OUT = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
BOOKS = [b.strip() for b in os.environ.get('BOOKS', os.environ.get('BOOK', 'pinnacle,unibet,bwin,betsson')).split(',') if b.strip()]
COOLDOWN = float(os.environ.get('COOLDOWN', '3'))
MAX_PER_RUN = int(os.environ.get('MAX_PER_RUN', '120'))

def api_get(slug, fid):
    params = {'fixtureId': fid, 'bookmakers': slug, 'apiKey': ODDSPAPI_KEY}
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v), safe=',')}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/historical-odds?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), 200, ''
    except urllib.error.HTTPError as e:
        body = ''
        try: body = e.read().decode('utf-8', 'replace')[:160]
        except Exception: pass
        return None, e.code, body
    except Exception as e:
        return None, 0, str(e)[:160]

def unwrap(resp, fid):
    if not isinstance(resp, dict): return None
    if 'bookmakers' in resp: return resp
    if fid in resp and isinstance(resp[fid], dict): return resp[fid]
    for v in resp.values():
        if isinstance(v, dict) and 'bookmakers' in v: return v
    return None

def _book_market(hist, slug):
    b = (hist.get('bookmakers') or {}).get(slug) if isinstance(hist, dict) else None
    if not isinstance(b, dict): return None
    mkt = (b.get('markets') or {}).get(MARKET)
    if not isinstance(mkt, dict): return None
    outs = mkt.get('outcomes')
    return outs if isinstance(outs, dict) and outs else None

def _outcome_curve(oc):
    if not isinstance(oc, dict): return []
    parsed = []
    for pk, points in (oc.get('players') or {}).items():
        if not isinstance(points, list): continue
        for p in points:
            if not isinstance(p, dict) or p.get('active') is False: continue
            t, pr = p.get('createdAt', ''), p.get('price')
            if pr is None or not t: continue
            try:
                dt = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=None)
                pr = float(pr)
            except (TypeError, ValueError, Exception):
                continue
            parsed.append((dt, pr))
    parsed.sort(key=lambda x: x[0])
    return parsed

def parse_two_curves(hist, slug):
    outs = _book_market(hist, slug)
    if not outs: return [], []
    try: ids = sorted(outs.keys(), key=lambda k: int(k))
    except ValueError: ids = sorted(outs.keys())
    if len(ids) < 2: return [], []
    return _outcome_curve(outs[ids[0]]), _outcome_curve(outs[ids[1]])

def _market_first_ts(hist, slug, mid):
    """Premier createdAt (datetime) de tous les points d'un marché donné, ou None."""
    b = (hist.get('bookmakers') or {}).get(slug) if isinstance(hist, dict) else None
    if not isinstance(b, dict): return None
    mkt = (b.get('markets') or {}).get(mid)
    if not isinstance(mkt, dict): return None
    best = None
    for oc in (mkt.get('outcomes') or {}).values():
        if not isinstance(oc, dict): continue
        for points in (oc.get('players') or {}).values():
            if not isinstance(points, list): continue
            for p in points:
                if not isinstance(p, dict): continue
                t = p.get('createdAt')
                if not t: continue
                try:
                    dt = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=None)
                except (TypeError, ValueError, Exception):
                    continue
                if best is None or dt < best: best = dt
    return best

def set2_open_info(hist, slug):
    """Timing d'ouverture des marchés de set 2 -> fin du set 1.
    Renvoie {mid: iso|None, ..., 'set1_end': iso|None} (min des marqueurs présents)."""
    res, cands = {}, []
    for mid in SET2_MARKERS:
        dt = _market_first_ts(hist, slug, mid)
        res[mid] = dt.isoformat() if dt else None
        if dt: cands.append(dt)
    res['set1_end'] = min(cands).isoformat() if cands else None
    return res

def ref_home_away(m):
    for k in ('closing', 'pinnacle_15min', 'pinnacle_t7', 'pinnacle_t15', 'pinnacle_t25', 'pinnacle_t3'):
        v = m.get(k)
        if isinstance(v, dict) and v.get('home') and v.get('away'):
            try: return float(v['home']), float(v['away'])
            except (TypeError, ValueError): pass
    h = m.get('history')
    if isinstance(h, list) and h and isinstance(h[-1], dict) and h[-1].get('home') and h[-1].get('away'):
        try: return float(h[-1]['home']), float(h[-1]['away'])
        except (TypeError, ValueError): pass
    return None, None

def metrics(curve, start):
    if not curve: return None
    op = curve[0][1]
    before = [pr for dt, pr in curve if dt <= start] if start else None
    cl = before[-1] if before else curve[-1][1]
    prices = [pr for _, pr in curve]
    return {'open': op, 'close': cl, 'n_points': len(curve),
            'first_t': curve[0][0].isoformat(), 'last_t': curve[-1][0].isoformat()}

def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente"); return
    if not os.path.exists(CLOSING_FILE):
        print("Pas de closing_lines.json"); return
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))

    done = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            try:
                d = json.loads(line)
                done.add((d.get('uid'), d.get('book')))
            except json.JSONDecodeError:
                pass

    now = datetime.datetime.utcnow()
    started = []
    for uid, m in closing.items():
        fid = m.get('fixture_id') or m.get('id')
        ct = m.get('commence_time', '')
        if not fid or not ct: continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start > now: continue
        started.append((uid, m, fid, start))

    # 1 REQUÊTE PAR MATCH pour TOUS les books (historical-odds accepte une liste
    # de bookmakers séparés par virgule) -> ~3x moins de requêtes qu'un appel/book.
    books_csv = ','.join(BOOKS)
    # À traiter : les matchs où au moins un book n'est pas encore fait.
    todo = [x for x in started if any((x[0], b) not in done for b in BOOKS)][:MAX_PER_RUN]
    print(f"{len(todo)} matchs à traiter (1 requête multi-books : {books_csv})")
    total = 0; nreq = 0; warned = False
    with open(OUT, 'a', encoding='utf-8') as f:
        for uid, m, fid, start in todo:
            time.sleep(COOLDOWN)
            resp, code, body = api_get(books_csv, fid)      # UNE requête, tous les books
            nreq += 1
            if code != 200:
                if not warned:
                    print(f"  ⚠️ HTTP {code} (fixtureId={fid}) :: {body}")
                    warned = True
                continue                                    # transitoire : on réessaiera (pas de stub)
            hist = unwrap(resp, fid)
            for book in BOOKS:
                if (uid, book) in done:
                    continue                                # ce book est déjà capturé
                c0, c1 = parse_two_curves(hist, book) if hist else ([], [])
                if not c0 or not c1:
                    # Courbe vide = ce book ne couvre pas ce match. Stub pour le marquer
                    # 'traité' (il entre dans `done`) et ne plus le ré-essayer.
                    f.write(json.dumps({'uid': uid, 'fixture_id': fid, 'book': book,
                                        'commence_time': m.get('commence_time'),
                                        'no_curve': True}, ensure_ascii=False) + '\n')
                    continue
                ch, ca = c0, c1
                rh, ra = ref_home_away(m)
                if rh and abs(c0[-1][1] - rh) > abs(c1[-1][1] - rh):
                    ch, ca = c1, c0
                entry = {'uid': uid, 'fixture_id': fid, 'book': book,
                         'commence_time': m.get('commence_time'), 'home': m.get('home'),
                         'away': m.get('away'), 'tournament': m.get('tournament'),
                         'home_metrics': metrics(ch, start), 'away_metrics': metrics(ca, start),
                         'set2_open': set2_open_info(hist, book),
                         'home_curve': [(dt.isoformat(), pr) for dt, pr in ch],
                         'away_curve': [(dt.isoformat(), pr) for dt, pr in ca]}
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                total += 1
    print(f"\n✅ {total} courbes écrites · {nreq} requête(s) (1/match au lieu de {len(BOOKS)}/match) — books: {books_csv}")

if __name__ == '__main__':
    main()
