#!/usr/bin/env python3
"""
Health check du système Tennis Edge.
Vérifie l'état de chaque composant et envoie un récap Telegram.
- Fraîcheur des fichiers de données
- Intégrité du backtest (colonnes, lignes collées)
- Quota des clés API The Odds
- Statut des derniers workflows GitHub
"""
import urllib.request, urllib.parse, json, os, datetime

# ── Config ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
GH_OWNER = os.environ.get('GH_OWNER', 'Lucas987987')
GH_REPO = os.environ.get('GH_REPO', 'Tennis-edge')
GH_TOKEN = os.environ.get('GH_TOKEN', '')  # optionnel (pour statut workflows)

now = datetime.datetime.utcnow()
alerts = []   # problèmes détectés
infos = []    # lignes d'info (toujours affichées)

def _esc(s):
    """Échappe les caractères spéciaux HTML pour parse_mode=HTML (évite Bad Request)."""
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configuré, message:\n", msg)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': msg,
        'parse_mode': 'HTML',
    }).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)
    except Exception as e:
        print(f"Erreur envoi Telegram: {e}")

# ── 1. Fraîcheur des fichiers ────────────────────────────
def file_age_hours(path):
    if not os.path.exists(path): return None
    mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(path))
    return (now - mtime).total_seconds() / 3600

FILES = {
    'closing_lines.json': 6,      # devrait bouger toutes les quelques heures
    'backtest_tennis.csv': 48,    # bouge quand tu charges des matchs
    'players_data.json': 200,     # hebdo (lundi)
    'resultats.json': 48,         # quotidien
}
for f, max_h in FILES.items():
    age = file_age_hours(f)
    if age is None:
        alerts.append(f"❌ {f} INTROUVABLE")
    elif age > max_h:
        alerts.append(f"⚠️ {f} pas mis à jour depuis {age:.0f}h (seuil {max_h}h)")
    else:
        infos.append(f"✅ {f} ({age:.0f}h)")

# ── 2. Intégrité du backtest ─────────────────────────────
if os.path.exists('backtest_tennis.csv'):
    try:
        with open('backtest_tennis.csv') as fh:
            lines = [l for l in fh.read().split('\n') if l.strip()]
        if lines:
            ncol = len(lines[0].split(';'))
            bad = sum(1 for l in lines[1:] if len(l.split(';')) != ncol)
            n = len(lines) - 1
            if bad > 0:
                alerts.append(f"⚠️ backtest: {bad} ligne(s) mal formée(s) sur {n}")
            else:
                infos.append(f"✅ backtest intègre ({n} matchs, {ncol} col)")
    except Exception as e:
        alerts.append(f"❌ Erreur lecture backtest: {_esc(e)}")

# ── 3. Quota des clés API ────────────────────────────────
def check_key(i):
    k = os.environ.get(f'ODDS_API_KEY_{i}')
    if not k: return None
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={k}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            remaining = r.headers.get('x-requests-remaining')
            return int(remaining) if remaining else -1
    except Exception:
        return -2  # clé morte / erreur

key_lines = []
for i in range(1, 8):  # jusqu'à 7 clés
    rem = check_key(i)
    if rem is None: continue
    if rem == -2:
        alerts.append(f"❌ Clé {i} ne répond pas (morte/invalide ?)")
        key_lines.append(f"❌ Clé {i}: erreur")
    elif rem == -1:
        key_lines.append(f"⚠️ Clé {i}: quota inconnu")
    elif rem < 50:
        alerts.append(f"⚠️ Clé {i} presque épuisée ({rem} req)")
        key_lines.append(f"⚠️ Clé {i}: {rem} req")
    else:
        key_lines.append(f"✅ Clé {i}: {rem} req")

# ── 4. Statut des derniers workflows (si GH_TOKEN dispo) ──
if GH_TOKEN:
    try:
        url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/actions/runs?per_page=10"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {GH_TOKEN}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'tennis-edge-health',
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            runs = json.loads(r.read()).get('workflow_runs', [])
        # Dernier statut par workflow
        seen = {}
        for run in runs:
            name = run.get('name', '?')
            if name in seen: continue
            seen[name] = run.get('conclusion', '?')
        for name, concl in seen.items():
            if concl == 'failure':
                alerts.append(f"❌ Workflow '{name}' a échoué au dernier run")
            elif concl == 'success':
                infos.append(f"✅ {name}: OK")
    except Exception as e:
        infos.append(f"(statut workflows indisponible: {_esc(e)})")

# ── Construction du message ──────────────────────────────
header = "🔴 <b>HEALTH CHECK — Problèmes détectés</b>" if alerts else "🟢 <b>HEALTH CHECK — Tout va bien</b>"
parts = [header, f"<i>{now.strftime('%Y-%m-%d %H:%M UTC')}</i>", ""]

if alerts:
    parts.append("<b>⚠️ À vérifier :</b>")
    parts.extend(alerts)
    parts.append("")

if key_lines:
    parts.append("<b>Clés API :</b>")
    parts.extend(key_lines)
    parts.append("")

parts.append("<b>Composants :</b>")
parts.extend(infos)

msg = "\n".join(parts)
print(msg)
send_telegram(msg)
