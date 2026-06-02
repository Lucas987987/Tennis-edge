#!/usr/bin/env python3
"""
Audit QA — contrôle de santé des données Tennis Edge.

PHILOSOPHIE : silence si tout va bien. N'envoie un message Telegram QUE si une
anomalie réelle est détectée. Un audit qui crie au loup pour rien finit ignoré ;
un audit muet quand tout va bien se fait lire quand il parle.

Contrôles, par gravité décroissante :
  [CRITIQUE] fichier absent / illisible (JSON cassé, CSV vide)
  [CRITIQUE] CSV corrompu : colonnes dupliquées, nb de colonnes incohérent
  [ALERTE]   capture closing en panne : trop peu de closings fiables récents
  [ALERTE]   capture périmée : pas de mise à jour depuis trop longtemps
  [INFO]     jointures : uid orphelins entre backtest / resultats / closing

Déterministe, gratuit, pas de LLM. À lancer via un workflow GitHub dédié
(ex : 1×/jour). Lit TELEGRAM_TOKEN / TELEGRAM_CHAT_ID depuis l'environnement.
"""
import os, json, csv, datetime

CLOSING_FILE = 'closing_lines.json'
BACKTEST_FILE = 'backtest_tennis.csv'
RESULTS_FILE = 'resultats.json'
ALERTS_LOG = 'odds_alerts_log.jsonl'

CSV_SEP = ';'
CLOSING_FRESH_MAX_MINS = 35      # un closing est "fiable" si capturé <= 35 min avant
CLOSING_MIN_RELIABLE_PCT = 50    # alerte si < 50% des closings récents sont fiables
CLOSING_RECENT_COUNT = 15        # on juge la santé sur les N derniers matchs closés
STALE_HOURS = 18                 # alerte si closing_lines pas mis à jour depuis N h


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def check_files_exist(problems):
    """Présence et lisibilité des fichiers essentiels."""
    for path, loader in [(CLOSING_FILE, 'json'), (RESULTS_FILE, 'json'),
                         (BACKTEST_FILE, 'csv')]:
        if not os.path.exists(path):
            problems.append(('CRITIQUE', f"{path} est absent du repo."))
            continue
        try:
            if loader == 'json':
                with open(path, encoding='utf-8') as f:
                    json.load(f)
            else:
                with open(path, encoding='utf-8') as f:
                    if not f.readline().strip():
                        problems.append(('CRITIQUE', f"{path} est vide."))
        except json.JSONDecodeError as e:
            problems.append(('CRITIQUE', f"{path} est un JSON corrompu ({e.msg} l.{e.lineno})."))
        except Exception as e:
            problems.append(('CRITIQUE', f"{path} illisible : {e}"))


def check_csv_integrity(problems):
    """Détecte colonnes dupliquées (bug passé) et lignes mal formées."""
    if not os.path.exists(BACKTEST_FILE):
        return
    try:
        with open(BACKTEST_FILE, encoding='utf-8') as f:
            rows = list(csv.reader(f, delimiter=CSV_SEP))
    except Exception as e:
        problems.append(('CRITIQUE', f"Lecture {BACKTEST_FILE} impossible : {e}"))
        return
    if not rows:
        problems.append(('CRITIQUE', f"{BACKTEST_FILE} n'a aucune ligne."))
        return
    header = rows[0]
    # Colonnes dupliquées
    seen, dups = set(), set()
    for c in header:
        if c in seen:
            dups.add(c)
        seen.add(c)
    if dups:
        problems.append(('CRITIQUE', f"Colonnes dupliquées dans {BACKTEST_FILE} : {', '.join(sorted(dups))}."))
    # Lignes avec un nb de colonnes différent du header
    ncol = len(header)
    bad = [i + 2 for i, r in enumerate(rows[1:]) if r and len(r) != ncol]
    if bad:
        ex = ', '.join(map(str, bad[:5]))
        more = '…' if len(bad) > 5 else ''
        problems.append(('CRITIQUE', f"{len(bad)} ligne(s) de {BACKTEST_FILE} ont un nb de colonnes anormal (l. {ex}{more})."))


def check_closing_health(problems):
    """Santé de la capture closing : assez de closings fiables récents ?"""
    if not os.path.exists(CLOSING_FILE):
        return
    try:
        with open(CLOSING_FILE, encoding='utf-8') as f:
            closing = json.load(f)
    except Exception:
        return  # déjà signalé par check_files_exist

    # Fraîcheur : date du point le plus récent toutes entrées confondues
    latest = None
    mins_recent = []
    items = []
    for uid, m in closing.items():
        hist = m.get('history', [])
        if not hist:
            continue
        last = hist[-1]
        ca = last.get('captured_at')
        if ca:
            try:
                t = datetime.datetime.fromisoformat(ca.replace('Z', ''))
                if latest is None or t > latest:
                    latest = t
            except Exception:
                pass
        ct = m.get('commence_time', '')
        items.append((ct, last.get('mins_before')))

    # Ne juger la santé closing que sur les matchs récents (coup d'envoi < 48h),
    # pour ne pas être pollué par les vieux matchs capturés avant la mise en route du worker.
    cutoff = (_utcnow() - datetime.timedelta(hours=48)).isoformat()

    # Périmé ?
    if latest is not None:
        age_h = (_utcnow() - latest).total_seconds() / 3600
        if age_h > STALE_HOURS:
            problems.append(('ALERTE', f"closing_lines.json pas mis à jour depuis {age_h:.0f}h "
                                       f"(seuil {STALE_HOURS}h). La capture tourne-t-elle ?"))

    # % de closings fiables sur les N matchs les plus récents (par commence_time)
    # On ne juge que les matchs DÉJÀ COMMENCÉS (closing pertinent seulement après coup d'envoi)
    now_iso = _utcnow().isoformat()
    started = [(ct, mb) for ct, mb in items if mb is not None and ct and cutoff < ct < now_iso]
    started.sort(key=lambda x: x[0], reverse=True)
    recent = started[:CLOSING_RECENT_COUNT]
    # Seuil de déclenchement : au moins 8 matchs récents pour juger (évite les faux
    # positifs en phase de démarrage où peu de matchs sont passés par le worker).
    if len(recent) >= 8:
        reliable = sum(1 for _, mb in recent if mb <= CLOSING_FRESH_MAX_MINS)
        pct = 100 * reliable / len(recent)
        if pct < CLOSING_MIN_RELIABLE_PCT:
            problems.append(('ALERTE', f"Seulement {pct:.0f}% des {len(recent)} derniers closings "
                                       f"sont fiables (<{CLOSING_FRESH_MAX_MINS}min). Le worker "
                                       f"déclenche-t-il bien la capture ?"))


def _csv_uids(path):
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding='utf-8') as f:
            r = csv.DictReader(f, delimiter=CSV_SEP)
            return {row['uid'] for row in r if row.get('uid')}
    except Exception:
        return set()


def check_joins(problems):
    """Cohérence des clés uid entre backtest et resultats.json (info, non bloquant)."""
    bt = _csv_uids(BACKTEST_FILE)
    if not bt:
        return
    res_ids = set()
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, encoding='utf-8') as f:
                data = json.load(f)
            for item in data.get('results', []):
                if item.get('id'):
                    res_ids.add(item['id'])
        except Exception:
            return
    # Combien de matchs du backtest AVEC résultat attendu trouvent leur id ?
    # On ne compte que ceux dont la date est passée (sinon normal qu'il manque).
    if not res_ids:
        return
    today = _utcnow().date().isoformat()
    res_dates = {r[:10] for r in res_ids}
    # On ne juge la jointure QUE sur la plage de dates couverte par resultats.json.
    # Si un match du backtest est plus récent que tout resultats.json, c'est normal
    # qu'il n'ait pas encore de résultat (resultats.json pas régénéré) -> pas une anomalie.
    res_max_date = max(res_dates)
    # matchs passés ET dans la plage temporelle des résultats disponibles
    checkable = {u for u in bt if u[:10] < today and u[:10] <= res_max_date}
    if len(checkable) >= 5:
        matched = sum(1 for u in checkable if u in res_ids)
        miss = len(checkable) - matched
        if miss / len(checkable) > 0.3:
            problems.append(('INFO', f"{miss}/{len(checkable)} matchs du backtest (dans la plage "
                                     f"de resultats.json) n'ont pas de résultat correspondant. "
                                     f"Jointure uid/id à vérifier (ordre des joueurs ?)."))


def send_telegram(token, chat_id, text):
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text,
                                   'parse_mode': 'HTML',
                                   'disable_web_page_preview': 'true'}).encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'tennis-edge-audit/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram: {e}")
        return False


def format_report(problems):
    order = {'CRITIQUE': 0, 'ALERTE': 1, 'INFO': 2}
    icon = {'CRITIQUE': '🔴', 'ALERTE': '🟠', 'INFO': '🔵'}
    problems = sorted(problems, key=lambda p: order.get(p[0], 9))
    lines = ["🔍 <b>Audit QA — anomalies détectées</b>\n"]
    for sev, msg in problems:
        lines.append(f"{icon.get(sev,'•')} <b>{sev}</b> — {msg}")
    lines.append("\n<i>Audit automatique. Vérifie les points ci-dessus.</i>")
    return "\n".join(lines)


def run_audit():
    problems = []
    check_files_exist(problems)
    check_csv_integrity(problems)
    check_closing_health(problems)
    check_joins(problems)

    if not problems:
        print("✅ Audit QA : aucune anomalie. (Silence Telegram.)")
        return

    print(f"⚠️ Audit QA : {len(problems)} anomalie(s) détectée(s) :")
    for sev, msg in problems:
        print(f"  [{sev}] {msg}")

    token = os.environ.get('TELEGRAM_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if token and chat_id:
        if send_telegram(token, chat_id, format_report(problems)):
            print("  📨 Rapport envoyé sur Telegram.")
    else:
        print("  ℹ️ Telegram non configuré — rapport non envoyé.")


if __name__ == '__main__':
    run_audit()
