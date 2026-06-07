#!/usr/bin/env python3
"""
fetch_clv.py — Récupère le CLV (closing line value) des matchs via l'endpoint
/historical-odds d'OddsPapi, qui est GRATUIT (ne consomme pas le quota).

Principe : pour chaque match suivi dans closing_lines.json qui est déjà joué
(commence_time passé) et dont le CLV n'a pas encore été calculé, on appelle
/historical-odds?fixtureId=...&bookmakers=pinnacle. La réponse contient la courbe
complète des cotes (marché 123) ; on en extrait :
  - la cote d'OUVERTURE (point le plus ancien)
  - la cote de CLÔTURE (dernier point avant le coup d'envoi)
puis on calcule le mouvement ouverture->clôture (= le vrai CLV de référence).

Le résultat est stocké dans closing_lines.json (champs clv_open/clv_close/clv_pct)
ET dans un journal clv_history.jsonl, pour être réimporté dans le backtest.

Cooldown /historical-odds = 5s entre appels. On limite le nombre de matchs traités
par run (MAX_PER_RUN) pour ne pas faire un job interminable.
"""
import urllib.request, urllib.error, urllib.parse, json, os, datetime, time

ODDSPAPI_KEY = os.environ.get('ODDSPAPI_KEY', '')
BASE = 'https://api.oddspapi.io/v4'
MARKET = '123'
CLOSING_FILE = 'closing_lines.json'
CLV_LOG = 'clv_history.jsonl'
COOLDOWN = 5.5            # secondes entre appels historical-odds
MAX_PER_RUN = 40         # nb max de matchs traités par exécution


def api_get(path, params):
    params = dict(params); params['apiKey'] = ODDSPAPI_KEY
    qs = '&'.join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), True
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  HTTP {e.code} sur {path}: {e.read().decode('utf-8','replace')[:120]}")
        return None, False
    except Exception as e:
        print(f"  {path}: {e}")
        return None, False


def extract_curve(hist, start_iso):
    """Depuis la réponse historical-odds, renvoie (ouverture, cloture) du marché 123
    pour home et away : { 'home': (open, close), 'away': (open, close) }.
    Ouverture = point le plus ancien. Clôture = dernier point AVANT le coup d'envoi."""
    pin = hist.get('bookmakers', {}).get('pinnacle', {})
    mkt = pin.get('markets', {}).get(MARKET)
    if not mkt:
        return None
    start = None
    if start_iso:
        try:
            start = datetime.datetime.fromisoformat(start_iso.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            start = None

    res = {}
    for oid, oc in mkt.get('outcomes', {}).items():
        for pk, points in oc.get('players', {}).items():
            if not isinstance(points, list) or not points:
                continue
            label = None
            # bookmakerOutcomeId peut être au niveau du point
            for p in points:
                if p.get('bookmakerOutcomeId') in ('home', 'away'):
                    label = p['bookmakerOutcomeId']; break
            # parser les points (createdAt, price), trier par date croissante
            parsed = []
            for p in points:
                t = p.get('createdAt', '')
                pr = p.get('price')
                if pr is None or not t:
                    continue
                try:
                    dt = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception:
                    continue
                parsed.append((dt, pr))
            if not parsed:
                continue
            parsed.sort(key=lambda x: x[0])
            open_price = parsed[0][1]
            # clôture = dernier point avant le coup d'envoi (sinon dernier dispo)
            if start:
                before = [pr for dt, pr in parsed if dt <= start]
                close_price = before[-1] if before else parsed[-1][1]
            else:
                close_price = parsed[-1][1]
            if label:
                res[label] = (open_price, close_price)
    return res or None


def main():
    if not ODDSPAPI_KEY:
        print("❌ ODDSPAPI_KEY absente")
        return
    if not os.path.exists(CLOSING_FILE):
        print("Pas de closing_lines.json")
        return
    with open(CLOSING_FILE, encoding='utf-8') as f:
        closing = json.load(f)

    now = datetime.datetime.utcnow()
    # Matchs déjà joués (commence_time passé) sans CLV historique encore calculé
    todo = []
    for uid, m in closing.items():
        ct = m.get('commence_time', '')
        fid = m.get('fixture_id') or m.get('id')
        if not ct or not fid:
            continue
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start > now:
            continue  # pas encore joué
        if m.get('clv_hist_done'):
            continue  # déjà traité
        todo.append((uid, m, fid, ct))

    print(f"{len(todo)} matchs à traiter pour le CLV historique (max {MAX_PER_RUN}/run)")
    todo = todo[:MAX_PER_RUN]

    done = 0
    with open(CLV_LOG, 'a', encoding='utf-8') as logf:
        for uid, m, fid, ct in todo:
            time.sleep(COOLDOWN)
            hist, ok = api_get('historical-odds', {'fixtureId': fid, 'bookmakers': 'pinnacle'})
            if not ok or not hist:
                continue
            curve = extract_curve(hist, ct)
            if not curve or 'home' not in curve or 'away' not in curve:
                m['clv_hist_done'] = True  # pas d'historique exploitable, on ne réessaiera pas
                continue
            oh, ch = curve['home']
            oa, ca = curve['away']
            # CLV du favori = mouvement de SA cote (clôture vs ouverture), en %
            # négatif = la cote a baissé = le joueur s'est renforcé (CLV favorable si on l'avait pris à l'ouverture)
            clv_home = round((ch - oh) / oh * 100, 2) if oh else None
            clv_away = round((ca - oa) / oa * 100, 2) if oa else None
            m['clv_open_home'] = oh; m['clv_close_home'] = ch; m['clv_home_pct'] = clv_home
            m['clv_open_away'] = oa; m['clv_close_away'] = ca; m['clv_away_pct'] = clv_away
            m['clv_hist_done'] = True
            logf.write(json.dumps({
                'uid': uid, 'fixture_id': fid, 'commence_time': ct,
                'home': m.get('home'), 'away': m.get('away'),
                'open_home': oh, 'close_home': ch, 'clv_home_pct': clv_home,
                'open_away': oa, 'close_away': ca, 'clv_away_pct': clv_away,
            }, ensure_ascii=False) + '\n')
            done += 1
            print(f"  ✅ {m.get('home')} vs {m.get('away')} | home {oh}→{ch} ({clv_home:+.1f}%) | away {oa}→{ca} ({clv_away:+.1f}%)")

    with open(CLOSING_FILE, 'w', encoding='utf-8') as f:
        json.dump(closing, f, ensure_ascii=False, indent=2)
    print(f"\n✅ CLV historique calculé pour {done} matchs (gratuit, hors quota)")


if __name__ == '__main__':
    main()
