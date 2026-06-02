#!/usr/bin/env python3
"""
Détecteur de mouvement de cote (capteur défensif).

Analyse le history[] de chaque match dans closing_lines.json et envoie une
alerte Telegram quand la cote Pinnacle a bougé de façon notable (>= SEUIL_PCT)
entre le premier et le dernier point capturé.

PHILOSOPHIE : c'est un capteur DÉFENSIF, pas un signal d'entrée. L'alerte
informe ("le marché a bougé, réévalue"), elle ne dit jamais "parie maintenant".
Le mouvement de cote n'est PAS prouvé rentable sur tes données — on observe.

Anti-spam : on ne ré-alerte un match que si le mouvement s'est AGGRAVÉ d'au
moins RE_ALERT_PCT depuis la dernière alerte (état mémorisé dans alerts_sent).

À appeler à la FIN de capture_closing.py (les history[] viennent d'être mis
à jour). Lit TELEGRAM_TOKEN et TELEGRAM_CHAT_ID depuis les variables d'env.
"""
import os, json, urllib.request, urllib.parse, datetime

CLOSING_FILE = 'closing_lines.json'
ALERTS_FILE = 'odds_alerts_state.json'   # mémorise ce qui a déjà été notifié

SEUIL_PCT = 10.0        # amplitude minimale pour une 1re alerte (%)
RE_ALERT_PCT = 8.0      # ré-alerte seulement si ça bouge encore de +8 pts (%)
MIN_POINTS = 2          # il faut au moins 2 points d'historique pour comparer


def _pct_move(first, last):
    """Mouvement relatif de la cote 'home' entre premier et dernier point, en %.
    Signe négatif = la cote home a baissé (home devient plus favori)."""
    if not first or not last:
        return None
    try:
        return (last - first) / first * 100.0
    except ZeroDivisionError:
        return None


def detect_movements(closing):
    """Retourne la liste des matchs avec un mouvement >= SEUIL_PCT (sur home OU away)."""
    moves = []
    for uid, m in closing.items():
        hist = m.get('history', [])
        if len(hist) < MIN_POINTS:
            continue
        first, last = hist[0], hist[-1]
        mv_home = _pct_move(first.get('home'), last.get('home'))
        mv_away = _pct_move(first.get('away'), last.get('away'))
        if mv_home is None or mv_away is None:
            continue
        amp = max(abs(mv_home), abs(mv_away))
        if amp >= SEUIL_PCT:
            moves.append({
                'uid': uid,
                'home': m.get('home', '?'),
                'away': m.get('away', '?'),
                'tournament': m.get('tournament', ''),
                'commence_time': m.get('commence_time', ''),
                'o_home_first': first.get('home'),
                'o_home_last': last.get('home'),
                'o_away_first': first.get('away'),
                'o_away_last': last.get('away'),
                'mv_home': round(mv_home, 1),
                'mv_away': round(mv_away, 1),
                'amp': round(amp, 1),
                'mins_before': last.get('mins_before'),
            })
    return moves


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
    """Message défensif, neutre. N'incite jamais à parier."""
    # Sens : qui devient plus favori (cote qui baisse)
    if mv['mv_home'] < 0:
        sens = f"📉 {mv['home']} se renforce ({mv['o_home_first']} → {mv['o_home_last']})"
    else:
        sens = f"📉 {mv['away']} se renforce ({mv['o_away_first']} → {mv['o_away_last']})"
    t = ""
    if mv['mins_before'] is not None:
        t = f" · T-{mv['mins_before']} min"
    return (
        f"⚡ <b>Mouvement de cote</b> ({mv['amp']}%)\n"
        f"{mv['tournament']}{t}\n"
        f"<b>{mv['home']}</b> vs <b>{mv['away']}</b>\n"
        f"{sens}\n"
        f"\n"
        f"<i>Le marché a réagi à quelque chose. Si tu avais un pari prévu ici, "
        f"réévalue avant de jouer. Ceci n'est pas un signal d'entrée.</i>"
    )


def run_movement_detector():
    token = os.environ.get('TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        print("  ℹ️ Telegram non configuré (secrets absents) — détection sautée.")
        return

    if not os.path.exists(CLOSING_FILE):
        return
    with open(CLOSING_FILE, encoding='utf-8') as f:
        closing = json.load(f)

    # État des alertes déjà envoyées : { uid: amplitude_dernière_alerte }
    sent = {}
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, encoding='utf-8') as f:
                sent = json.load(f)
        except Exception:
            sent = {}

    moves = detect_movements(closing)
    n_sent = 0
    for mv in moves:
        uid = mv['uid']
        prev_amp = sent.get(uid)
        # 1re alerte, ou aggravation significative depuis la dernière
        if prev_amp is None or (mv['amp'] - prev_amp) >= RE_ALERT_PCT:
            if send_telegram(token, chat_id, format_alert(mv)):
                sent[uid] = mv['amp']
                n_sent += 1
                print(f"  📨 Alerte envoyée: {mv['home']} vs {mv['away']} ({mv['amp']}%)")

    # Nettoyage : retirer de l'état les matchs déjà commencés (absents du closing récent)
    live_uids = set(closing.keys())
    sent = {k: v for k, v in sent.items() if k in live_uids}

    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sent, f, ensure_ascii=False, indent=2)

    print(f"  ⚡ Détection mouvement: {len(moves)} match(s) au-dessus du seuil, {n_sent} alerte(s) envoyée(s).")


if __name__ == '__main__':
    run_movement_detector()
