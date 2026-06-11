#!/usr/bin/env python3
"""
Détecteur de mouvement de cote (capteur défensif) + journal d'étude.

Deux mécanismes DISSOCIÉS :

1. ALERTE Telegram (en direct) : envoyée quand l'amplitude >= ALERT_PCT.
   But : te faire voir passer les mouvements notables. Défensif, jamais un
   signal d'entrée. Anti-spam via odds_alerts_state.json.

2. LOG d'étude (permanent) : UNE ligne par match, écrite une seule fois quand
   le match entre dans la fenêtre closing (<= LOG_AT_MINS avant le coup
   d'envoi). On logge TOUS les matchs, même ceux qui n'ont pas bougé (amplitude
   0%), car l'analyse a besoin des non-mouvements autant que des mouvements.
   Fichier odds_alerts_log.jsonl, append-only, jamais effacé.
   Clé de jointure 'uid' commune avec backtest_tennis.csv et le CLV.

PHILOSOPHIE : on mesure tout, on ne conclut rien tant qu'on n'a pas de volume.
"""
import os, json, urllib.request, urllib.parse, datetime

CLOSING_FILE = 'closing_lines.json'
ALERTS_FILE = 'odds_alerts_state.json'   # état anti-spam des alertes (éphémère)
ALERTS_LOG = 'odds_alerts_log.jsonl'     # journal d'étude (append-only, permanent)
LOGGED_FILE = 'odds_logged_state.json'   # mémorise quels matchs sont déjà loggés

ALERT_PCT = 3.0         # seuil d'ALERTE Telegram (%)
RE_ALERT_PCT = 5.0      # ré-alerte si le mouvement s'aggrave encore de ce % 
LOG_AT_MINS = 35        # on logge le match quand il est <= 35 min avant le coup d'envoi
MIN_POINTS = 2          # au moins 2 points d'historique pour calculer un mouvement
TRAJ_POINTS = int(os.environ.get('TRAJ_POINTS', '8'))  # nb max de points montrés dans la trajectoire


def _pct_move(first, last):
    """Mouvement relatif d'une cote entre premier et dernier point, en %."""
    if not first or not last:
        return None
    try:
        return (last - first) / first * 100.0
    except ZeroDivisionError:
        return None


def _compute_move(uid, m):
    """Calcule le mouvement complet d'un match (premier point -> dernier point).
    PRE-MATCH UNIQUEMENT : les matchs deja commences sont ignores, et les points
    in-play (mins_before < 0, anciens historiques pollues) sont ecartes — sinon
    on compare une cote pre-match a une cote live et on alerte sur du faux
    "mouvement" (ex: +394% sur un match en cours). Retourne None si pas assez
    de donnees."""
    # Match deja commence -> aucune alerte de mouvement (c'est du live, pas du marche pre-match)
    ct = m.get('commence_time', '')
    if ct:
        try:
            start = datetime.datetime.fromisoformat(str(ct).replace('Z', '+00:00')).replace(tzinfo=None)
            if start <= datetime.datetime.utcnow():
                return None
        except Exception:
            pass
    hist = [p for p in (m.get('history') or [])
            if p.get('mins_before') is None or p.get('mins_before') >= 0]
    if len(hist) < MIN_POINTS:
        return None
    first, last = hist[0], hist[-1]
    mv_home = _pct_move(first.get('home'), last.get('home'))
    mv_away = _pct_move(first.get('away'), last.get('away'))
    if mv_home is None or mv_away is None:
        return None
    amp = max(abs(mv_home), abs(mv_away))
    return {
        'uid': uid,
        'home': m.get('home', '?'),
        'away': m.get('away', '?'),
        'tournament': m.get('tournament', ''),
        'sport_key': m.get('sport_key', ''),
        'niveau': m.get('niveau', ''),
        'commence_time': m.get('commence_time', ''),
        'n_points': len(hist),
        'o_home_first': first.get('home'),
        'o_home_last': last.get('home'),
        'o_away_first': first.get('away'),
        'o_away_last': last.get('away'),
        'mv_home': round(mv_home, 1),
        'mv_away': round(mv_away, 1),
        'amp': round(amp, 1),
        'mins_before': last.get('mins_before'),
        'history': hist,
    }


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true',
    }).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'tennis-edge/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram: {e}")
        return False


def format_alert(mv):
    """Message défensif, neutre. N'incite jamais à parier.
    Montre le mouvement RÉEL de chaque joueur : 📉 baisse = se renforce,
    📈 hausse = se fragilise. Affiche les deux côtés pour ne rien cacher."""
    def ligne(nom, first, last, pct):
        if pct is None:
            return None
        if pct < 0:
            # cote baisse → joueur se renforce
            return f"📉 {nom} se renforce ({first} → {last}, {pct:+.1f}%)"
        elif pct > 0:
            # cote monte → joueur se fragilise
            return f"📈 {nom} se fragilise ({first} → {last}, {pct:+.1f}%)"
        else:
            return f"➡️ {nom} stable ({first})"

    l_home = ligne(mv['home'], mv['o_home_first'], mv['o_home_last'], mv['mv_home'])
    l_away = ligne(mv['away'], mv['o_away_first'], mv['o_away_last'], mv['mv_away'])
    sens = "\n".join(x for x in (l_home, l_away) if x)

    t = ""
    if mv['mins_before'] is not None:
        t = f" · T-{mv['mins_before']} min"
    traj = format_trajectory(mv.get('history') or [], mv['home'], mv['away'])
    return (
        f"⚡ <b>Mouvement de cote</b> ({mv['amp']}%)\n"
        f"{mv['tournament']}{t}\n"
        f"<b>{mv['home']}</b> vs <b>{mv['away']}</b>\n"
        f"{sens}\n"
        f"{traj}"
        f"\n"
        f"<i>Le marché a réagi à quelque chose. Si tu avais un pari prévu ici, "
        f"réévalue avant de jouer. Ceci n'est pas un signal d'entrée.</i>"
    )


def format_trajectory(hist, home, away):
    """Tableau compact de l'évolution des cotes (triées par horodatage), pour voir
    la trajectoire globale du match en un coup d'oeil. Sous-échantillonne si besoin."""
    pts = [p for p in hist if p.get('home') and p.get('away') and p.get('t')]
    pts.sort(key=lambda p: p['t'])
    if len(pts) < 2:
        return ""
    if len(pts) > TRAJ_POINTS:                       # garder 1er, dernier + répartis
        step = (len(pts) - 1) / (TRAJ_POINTS - 1)
        keep = sorted(set(round(i * step) for i in range(TRAJ_POINTS)))
        pts = [pts[i] for i in keep]
    rows = [f"{'date/heure':<11} {'cote1':>6} {'cote2':>6}"]
    for p in pts:
        dh = str(p['t'])[5:16].replace('T', ' ')   # MM-DD HH:MM
        rows.append(f"{dh:<11} {p['home']:>6} {p['away']:>6}")
    return (f"\n📊 Évolution (cote1={home}, cote2={away}, {len(hist)} pts) :\n"
            f"<pre>" + "\n".join(rows) + "</pre>\n")


def log_entry(mv):
    """Append UNE ligne d'étude (un match). Permanent, jamais effacé.
    Conçu pour être croisé avec backtest_tennis.csv et le CLV via 'uid'."""
    entry = {
        'logged_at': datetime.datetime.utcnow().isoformat(),
        'uid': mv['uid'],
        'home': mv['home'],
        'away': mv['away'],
        'tournament': mv['tournament'],
        'sport_key': mv.get('sport_key', ''),
        'niveau': mv.get('niveau', ''),
        'commence_time': mv['commence_time'],
        'mins_before': mv['mins_before'],
        'n_points': mv['n_points'],
        'o_home_first': mv['o_home_first'],
        'o_home_last': mv['o_home_last'],
        'o_away_first': mv['o_away_first'],
        'o_away_last': mv['o_away_last'],
        'mv_home_pct': mv['mv_home'],
        'mv_away_pct': mv['mv_away'],
        'amplitude_pct': mv['amp'],
    }
    try:
        with open(ALERTS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        print(f"  ⚠️ Écriture journal: {e}")
        return False


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return default
    return default


def run_movement_detector():
    token = os.environ.get('TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    closing = _load_json(CLOSING_FILE, None)
    if not closing:
        return

    sent = _load_json(ALERTS_FILE, {})      # {uid: amplitude dernière alerte}
    logged = _load_json(LOGGED_FILE, {})    # {uid: True} matchs déjà loggés

    n_alert, n_log = 0, 0
    live_uids = set(closing.keys())

    for uid, m in closing.items():
        mv = _compute_move(uid, m)
        if mv is None:
            continue

        # ---- LOG d'étude : une seule fois, quand le match entre en fenêtre closing ----
        mb = mv['mins_before']
        if uid not in logged and mb is not None and mb <= LOG_AT_MINS:
            if log_entry(mv):
                logged[uid] = True
                n_log += 1

        # ---- ALERTE Telegram : si amplitude >= ALERT_PCT (et Telegram configuré) ----
        if token and chat_id and mv['amp'] >= ALERT_PCT:
            prev = sent.get(uid)
            if prev is None or (mv['amp'] - prev) >= RE_ALERT_PCT:
                if send_telegram(token, chat_id, format_alert(mv)):
                    sent[uid] = mv['amp']
                    n_alert += 1
                    print(f"  📨 Alerte: {mv['home']} vs {mv['away']} ({mv['amp']}%)")

    # Nettoyage des états éphémères (pas le log, lui est permanent)
    sent = {k: v for k, v in sent.items() if k in live_uids}
    logged = {k: v for k, v in logged.items() if k in live_uids}

    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)
    with open(LOGGED_FILE, 'w', encoding='utf-8') as f:
        json.dump(logged, f, ensure_ascii=False, indent=2)

    if not token or not chat_id:
        print(f"  ℹ️ Telegram non configuré — {n_log} match(s) loggé(s), alertes désactivées.")
    else:
        print(f"  ⚡ {n_log} match(s) loggé(s), {n_alert} alerte(s) envoyée(s).")


if __name__ == '__main__':
    run_movement_detector()
