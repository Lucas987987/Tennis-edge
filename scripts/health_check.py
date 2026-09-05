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

# CORRIGÉ LE 04/09/2026 (audit) : `closing_lines.json` était surveillé par
# son MTIME. En CI, le mtime de tout fichier suivi par git est celui du
# CHECKOUT -- 18h43:52 pour les deux fichiers ci-dessous lors du run de
# 18h43, alors que la dernière capture réelle datait de 18h40:17. Cette
# section répondait donc ✅ quoi qu'il arrive, y compris si la capture
# s'était arrêtée une semaine plus tôt : le filet quotidien du projet ne
# retenait rien. Même diagnostic que pour pipeline_status le 04/09 au
# matin, d'où était née _age_interne_h().
# `closing_lines.json` passe donc sous surveillance par HORODATAGE INTERNE
# (capture_state.json['last_capture_at'], écrit par le run qui capture) et
# sort de FILES. `backtest_tennis.csv` y reste : il est chargé à la main,
# son mtime git est un signal acceptable faute de mieux, et son seuil de
# 48 h tolère le décalage.
FILES = {
    'backtest_tennis.csv': 48,    # bouge quand tu charges des matchs
}
# players_data.json / resultats.json retirés des alertes : branche Sackmann/modèle
# DÉPRIORITISÉE (Sackmann injoignable sur ce runner ; le modèle Elo n'a pas d'edge).
# Les surveiller générerait de fausses alertes permanentes.
for f, max_h in FILES.items():
    age = file_age_hours(f)
    if age is None:
        alerts.append(f"❌ {f} INTROUVABLE")
    elif age > max_h:
        alerts.append(f"⚠️ {f} pas mis à jour depuis {age:.0f}h (seuil {max_h}h)")
    else:
        infos.append(f"✅ {f} ({age:.0f}h)")

# ── 1a. Capture : fraîcheur RÉELLE + budget de requêtes ──────────────────
# AJOUTÉ LE 04/09/2026. Deux signaux que rien ne surveillait :
#   - la capture a-t-elle tourné récemment ? (seul last_capture_at le dit)
#   - combien de requêtes OddsPapi consommées aujourd'hui ?
# Coût : 0 requête API, tout est déjà écrit dans capture_state.json.
CAPTURE_MAX_H = float(os.environ.get('CAPTURE_MAX_H', '6'))

# RELEVÉ DE 938 À 1400 LE 05/09/2026, après la découpe de capture_closing.
#
# 938 était calibré sur une cadence de capture de 5-10 min. La découpe du
# workflow (la capture prend 1,9 s, le post-traitement est parti dans
# courbes_alertes.yml) a permis de passer le cron Cloudflare à 3 min :
# ~20 captures/heure au lieu de 6, soit une consommation attendue autour de
# 840 req/jour contre 250 auparavant.
#
# Laisser 938 aurait fait sonner cette alerte à ~90 % TOUS LES MATINS, pour
# une consommation parfaitement nominale. Une alarme qui se déclenche chaque
# jour sans qu'il y ait rien à faire cesse d'être lue — et le jour où la
# consommation dérive vraiment, personne ne la voit. C'est le même mode de
# panne que les `|| true` avalés, par excès de bruit plutôt que de silence.
#
# 1400 vient du quota réel : 50 000 requêtes/mois, soit 1 613/jour sur un
# mois de 31 jours. 1400 laisse ~13 % de marge pour les passes étendues et
# les pics de calendrier (Grand Chelem : plus de tournois actifs, donc plus
# de requêtes par passe). 1400 x 31 = 43 400, sous le quota.
#
# Si la cadence change encore, c'est CETTE valeur qu'il faut revoir — pas le
# seuil de 90 % plus bas, qui reste le bon avertissement.
BUDGET_REQ_JOUR = int(os.environ.get('BUDGET_REQ_JOUR', '1400'))
try:
    _cs = json.load(open('capture_state.json', encoding='utf-8'))
    _lc = datetime.datetime.fromisoformat(str(_cs['last_capture_at']).replace('Z', ''))
    _age_cap = (now - _lc).total_seconds() / 3600
    if _age_cap > CAPTURE_MAX_H:
        alerts.append(f"❌ Aucune capture depuis {_age_cap:.1f}h "
                      f"(seuil {CAPTURE_MAX_H:.0f}h) — worker Cloudflare et "
                      f"cron */5 tous deux muets ?")
    else:
        infos.append(f"✅ dernière capture il y a {_age_cap:.1f}h")
    _req = _cs.get('requetes_cumul_jour')
    if isinstance(_req, int):
        _pct = 100.0 * _req / BUDGET_REQ_JOUR if BUDGET_REQ_JOUR else 0
        _ligne = f"requêtes OddsPapi aujourd'hui : {_req}/{BUDGET_REQ_JOUR} ({_pct:.0f}%)"
        # 90 % : il reste de quoi finir la journée, mais c'est le moment de
        # le savoir -- pas une fois le 429 tombé et les closings perdus.
        (alerts if _pct >= 90 else infos).append(
            ("❌ " if _pct >= 90 else "✅ ") + _ligne)
    _ppd = _cs.get('passages_par_declencheur')
    if isinstance(_ppd, dict) and _ppd:
        infos.append("ℹ️ passages : " +
                     ", ".join(f"{k}={v}" for k, v in sorted(_ppd.items())))
except (OSError, ValueError, KeyError, TypeError) as _e:
    alerts.append(f"❌ capture_state.json illisible ({_esc(_e)}) — "
                  f"fraîcheur de la capture NON vérifiée.")

# players_data.json : info seulement (non bloquant — Elo/Sackmann déprioritisé)
_pa = file_age_hours('players_data.json')
if _pa is not None:
    infos.append(f"ℹ️ players_data.json {_pa:.0f}h (Elo/Sackmann déprioritisé, non bloquant)")

# ── 1b. Résultats : source ACTIVE = API (set_results.json), plus Sackmann ──
if os.path.exists('set_results.json'):
    try:
        sr = json.load(open('set_results.json'))
        n = len(sr) if isinstance(sr, dict) else 0
        infos.append(f"✅ set_results.json: {n} matchs résolus (API oddspapi)")
    except Exception as e:
        alerts.append(f"❌ Erreur lecture set_results.json: {_esc(e)}")
else:
    infos.append("ℹ️ set_results.json absent (pas encore de résultats API)")

# ── 2. Intégrité du backtest ─────────────────────────────if os.path.exists('backtest_tennis.csv'):
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
