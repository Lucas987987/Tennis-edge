#!/usr/bin/env python3
"""
Détecteur EXPÉRIMENTAL : écart d'un book déjà ouvert au moment où Pinnacle
publie son premier prix.

CONTEXTE (mesuré sur 1042 matchs, 08/2026) : plusieurs opérateurs ouvrent
leur marché tennis des heures avant Pinnacle (tipico +353min médian, 1xbet
+374min, 22bet, unibet.fr, betsson...). Sans référence sharp disponible à cet
instant, leur prix d'ouverture est fixé à l'aveugle. Hypothèse testée :
au moment précis où Pinnacle apparaît enfin, ces books déjà en place sont-ils
mal calés par rapport au juste prix qui vient d'émerger ?

Résultat IN-SAMPLE (les mêmes 1042 matchs ayant servi à formuler l'idée) :
CLV médian +8,6%, 81% de refermeture (n=144, books>=5% d'écart au moment T).
ROI IC95 [-32%,+4%] -- non concluant.

STATUT : NON VALIDÉ. Ce script alimente deux choses en parallèle :
  1. Une alerte PRIVÉE clairement étiquetée "expérimental" (canal Telegram
     privé uniquement -- jamais le canal public, dont la crédibilité repose
     sur des signaux déjà démontrés).
  2. Un journal permanent (early_open_log.jsonl) pour le suivi out-of-sample
     dans validation_report.py (6e hypothèse gelée).
On ne saura si c'est réel qu'après plusieurs semaines de données FRAÎCHES,
distinctes de celles ayant servi à formuler l'hypothèse.

SOURCE DE DONNÉES -- point important, corrigé après une première tentative :
  - book_curves_live.jsonl (multi-books, alimenté en continu par la capture
    sur les matchs À VENIR) est la SEULE source utilisable pour une alerte
    PRÉ-MATCH en direct.
  - closing_lines.json ne contient que l'historique de Pinnacle seul (sert à
    odds_movement.py pour son propre calcul, pas multi-books).
  - book_curves.jsonl (historique complet) ne se remplit qu'APRÈS la fin des
    matchs (fetch_book_curves.py ignore tout match dont le coup d'envoi est
    encore dans le futur) -- inexploitable pour une alerte en direct.
"""
import os, json, math, datetime, urllib.request, urllib.parse

CURVES       = os.environ.get('CURVES', 'book_curves_live.jsonl')
STATE_FILE   = 'early_open_state.json'
LOG_FILE     = 'early_open_log.jsonl'

GAP_MIN_PCT  = float(os.environ.get('EARLY_GAP_MIN_PCT', '5'))
MAX_LEAD_MIN = float(os.environ.get('EARLY_MAX_LEAD_MIN', '600'))
EXCLUDE_BOOKS = {'pinnacle', 'betfair-ex', 'betfair', 'matchbook', 'smarkets'}


def shin_ph(oh, oa):
    ih, ia = 1/oh, 1/oa
    s = ih + ia
    if s <= 1:
        return ih / s
    z = 0.02
    for _ in range(40):
        ph = (math.sqrt(z*z + 4*(1-z)*ih*ih/s) - z) / (2*(1-z))
        pa = (math.sqrt(z*z + 4*(1-z)*ia*ia/s) - z) / (2*(1-z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t-1), 0.0), 0.3)
    return ph / (ph + pa)


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default
    return default


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
        'disable_web_page_preview': 'true',
    }).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram: {e}")
        return False


def x_search_url(home, away):
    def last(name):
        parts = [p for p in (name or '').split() if p]
        return parts[-1] if parts else (name or '')
    q = f'"{last(home)}" OR "{last(away)}"'
    return "https://x.com/search?q=" + urllib.parse.quote(q) + "&f=live"


def load_games():
    games = {}
    if not os.path.exists(CURVES):
        return games
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ct = _dt(r.get('commence_time'))
        if not ct:
            continue
        now = datetime.datetime.utcnow()
        if ct <= now:
            continue
        def pts(seq):
            p = [(_dt(t), o) for t, o in (seq or []) if _dt(t) and o and o > 1]
            return sorted(x for x in p if x[0] < ct)
        h, a = pts(r.get('home_curve')), pts(r.get('away_curve'))
        if not h or not a:
            continue
        g = games.setdefault(r['uid'], {'_ct': ct, '_home': r.get('home_team') or r.get('home'),
                                        '_away': r.get('away_team') or r.get('away'),
                                        '_tour': r.get('tournament') or ''})
        g[r['book']] = {'h': h, 'a': a}
    return games


def _find_signal(g):
    pin = g.get('pinnacle')
    if not pin or not pin['h'] or not pin['a']:
        return None
    t_pin = pin['h'][0][0]
    p_pin = shin_ph(pin['h'][0][1], pin['a'][0][1])
    fair = {'home': 1/p_pin, 'away': 1/(1-p_pin)}

    best = None
    for book, sb in g.items():
        if book.startswith('_') or book in EXCLUDE_BOOKS or not isinstance(sb, dict):
            continue
        h, a = sb.get('h') or [], sb.get('a') or []
        if not h or not a or h[0][0] >= t_pin:
            continue
        lead_min = (t_pin - h[0][0]).total_seconds() / 60
        if lead_min > MAX_LEAD_MIN:
            continue
        def val_at(seq, t):
            v = None
            for tt, o in seq:
                if tt <= t:
                    v = o
                else:
                    break
            return v
        val_h, val_a = val_at(h, t_pin), val_at(a, t_pin)
        if not val_h or not val_a:
            continue
        for side, price in (('home', val_h), ('away', val_a)):
            gap = (price / fair[side] - 1) * 100
            if gap >= GAP_MIN_PCT and (best is None or gap > best['gap']):
                best = dict(book=book, side=side, price=price, fair=fair[side],
                           gap=gap, lead_min=lead_min, t_pin=t_pin.isoformat())
    return best


def format_alert(g, sig):
    home, away = g['_home'], g['_away']
    joueur = home if sig['side'] == 'home' else away
    return (
        f"🆕 <b>SIGNAL EXPÉRIMENTAL — non validé</b>\n"
        f"{g['_tour']}\n"
        f"<b>{home}</b> vs <b>{away}</b>\n"
        f"{sig['book']} était ouvert {sig['lead_min']:.0f} min avant Pinnacle.\n"
        f"À l'apparition de Pinnacle : <b>{joueur}</b> encore à {sig['price']:.2f} "
        f"chez {sig['book']} (juste prix estimé {sig['fair']:.2f}, écart {sig['gap']:+.1f}%)\n"
        f"🔎 Posts X sur ce match : {x_search_url(home, away)}\n\n"
        f"<i>Hypothèse en cours de validation (voir validation_report). "
        f"Sur données passées : CLV médian +8,6%, ROI non démontré (IC95 large). "
        f"Ceci n'est pas un signal d'entrée.</i>"
    )


def run():
    token = os.environ.get('TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    games = load_games()
    if not games:
        print(f"  {CURVES} introuvable ou vide (ou aucun match pré-match)")
        return

    state = _load_json(STATE_FILE, {})
    n_sig, n_log = 0, 0

    for uid, g in games.items():
        if uid in state:
            continue
        sig = _find_signal(g)
        if sig is None:
            continue

        entry = dict(uid=uid, t=datetime.datetime.utcnow().isoformat(),
                    home=g['_home'], away=g['_away'], tournament=g['_tour'], **sig)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            n_log += 1
        except Exception as e:
            print(f"  ⚠️ Écriture journal early_open: {e}")

        if token and chat_id:
            if send_telegram(token, chat_id, format_alert(g, sig)):
                n_sig += 1

        state[uid] = True

    state = {k: v for k, v in state.items() if k in games}
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"  🆕 early_open_signal : {n_log} nouveau(x) signal(aux) loggé(s), {n_sig} alerte(s) envoyée(s) "
          f"sur {len(games)} matchs pré-match examinés")


if __name__ == '__main__':
    run()
