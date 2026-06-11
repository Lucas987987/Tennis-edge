#!/usr/bin/env python3
"""
fetch_clv.py — Courbe complète Pinnacle (marché 123) via /historical-odds (GRATUIT).
v3 : ne grille plus les matchs sur échec, ré-ouvre les échecs précédents,
     et imprime la structure de la réponse au 1er échec pour diagnostic.
"""
import json, os, datetime, time
import oddspapi_v5 as ov   # client commun OddsPapi v5 (RapidAPI, curl)

# Auth v4 (ODDSPAPI_KEY/BASE) supprimée : gérée par oddspapi_v5.
MARKET = '121'             # marché vainqueur tennis en v5 (info ; le client gère l'extraction)
CLOSING_FILE = 'closing_lines.json'
CLV_LOG = 'clv_history.jsonl'
COOLDOWN = float(os.environ.get('CLV_COOLDOWN', '3.0'))   # v5 (payant) plus tolérant que le palier gratuit v4
MAX_PER_RUN = int(os.environ.get('CLV_MAX_PER_RUN', '40'))
MAX_ATTEMPTS = 3
STORE_FULL_CURVE = True


def _curve_dt(pts):
    """[(ts_ms, price)] -> [(datetime_utc, price)] trié (pour analyze_side / STORE_FULL_CURVE)."""
    out = []
    for ts, pr in (pts or []):
        if pr is None:
            continue
        try:
            out.append((datetime.datetime.utcfromtimestamp(int(ts) / 1000.0), float(pr)))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def _api_get_removed(*a, **k):
    raise RuntimeError("api_get v4 supprimé — utiliser oddspapi_v5")

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

def _pin_market(hist):
    if not isinstance(hist, dict): return None
    bk = hist.get('bookmakers')
    if not isinstance(bk, dict): return None
    pin = bk.get('pinnacle')
    if not isinstance(pin, dict): return None
    mkts = pin.get('markets')
    if not isinstance(mkts, dict): return None
    mkt = mkts.get(MARKET)
    if not isinstance(mkt, dict): return None
    outs = mkt.get('outcomes')
    if not isinstance(outs, dict) or not outs: return None
    return outs

def _outcome_curve(oc):
    if not isinstance(oc, dict): return []
    players = oc.get('players')
    if not isinstance(players, dict): return []
    parsed = []
    for pk, points in players.items():
        if not isinstance(points, list): continue
        for p in points:
            if not isinstance(p, dict): continue
            if p.get('active') is False: continue
            t, pr = p.get('createdAt',''), p.get('price')
            if pr is None or not t: continue
            try:
                dt = datetime.datetime.fromisoformat(t.replace('Z','+00:00')).replace(tzinfo=None)
                pr = float(pr)
            except (TypeError, ValueError, Exception):
                continue
            parsed.append((dt, pr))
    parsed.sort(key=lambda x: x[0])
    return parsed

def parse_two_curves(hist):
    """Renvoie (courbe_outcome0, courbe_outcome1), ordre = ids d'outcome triés."""
    outs = _pin_market(hist)
    if not outs: return [], []
    try:
        ids = sorted(outs.keys(), key=lambda k: int(k))
    except ValueError:
        ids = sorted(outs.keys())
    if len(ids) < 2: return [], []
    return _outcome_curve(outs[ids[0]]), _outcome_curve(outs[ids[1]])

def ref_home_away(m):
    """Prix home/away connu (snapshot/closing/history) pour verifier l'orientation."""
    for k in ('closing','pinnacle_15min','pinnacle_t7','pinnacle_t15','pinnacle_t25','pinnacle_t3'):
        v = m.get(k)
        if isinstance(v, dict) and v.get('home') and v.get('away'):
            try: return float(v['home']), float(v['away'])
            except (TypeError, ValueError): pass
    h = m.get('history')
    if isinstance(h, list) and h and isinstance(h[-1], dict) and h[-1].get('home') and h[-1].get('away'):
        try: return float(h[-1]['home']), float(h[-1]['away'])
        except (TypeError, ValueError): pass
    return None, None

def analyze_side(curve, start):
    if not curve: return None
    open_price = curve[0][1]
    if start:
        before = [pr for dt, pr in curve if dt <= start]
        close_price = before[-1] if before else curve[-1][1]
    else:
        close_price = curve[-1][1]
    # Métriques amplitude/min/max sur le PRE-MATCH uniquement (exclut le in-play,
    # qui sinon fausse min/max/amplitude). Le CLV (open->close) etait deja propre.
    pre = [pr for dt, pr in curve if (start is None) or dt <= start] or [pr for _, pr in curve]
    move_pct = round((close_price-open_price)/open_price*100,2) if open_price else None
    amp = round(max(abs(max(pre)-open_price),abs(min(pre)-open_price))/open_price*100,2) if open_price else None
    return {'open':open_price,'close':close_price,'move_pct':move_pct,'amplitude_pct':amp,
            'min':min(pre),'max':max(pre),'n_points':len(pre),'n_points_all':len(curve),
            'first_t':curve[0][0].isoformat(),'last_t':curve[-1][0].isoformat()}

def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return
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
            try:
                curves = ov.historical_h2h_curve(fid, 'pinnacle')   # home=outcome121, away=122 (canonique v5)
                ch = _curve_dt(curves.get('home'))
                ca = _curve_dt(curves.get('away'))
            except Exception as e:
                ch = ca = []; print(f"  parse error: {e}")
            if not ch and not ca:
                m['clv_attempts'] = m.get('clv_attempts', 0) + 1
                if not warned_http:
                    print(f"  ⚠️ pas de courbe Pinnacle pour fixtureId={fid} — {m.get('home')} vs {m.get('away')}")
                    warned_http = True
                continue
            ah = analyze_side(ch, start); aa = analyze_side(ca, start)
            if not ah or not aa:
                m['clv_attempts'] = m.get('clv_attempts',0) + 1
                if not dumped:
                    print(f"  ⚠️ courbe incomplète — {m.get('home')} vs {m.get('away')} (fixtureId={fid})")
                    dumped = True
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
