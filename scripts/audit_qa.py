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

# --- contrôles du nouveau pipeline (élargissement books, dérivés, CLV, steam) ---
CURVES_FILE = 'book_curves.jsonl'
GAMES_FILE = 'games_markets.json'
RECENT_DAYS = int(os.environ.get('AUDIT_RECENT_DAYS', '21'))   # fenêtre "récent"
EXPECT_BOOKS_MIN = int(os.environ.get('AUDIT_EXPECT_BOOKS', '5'))  # >4 si CAPTURE_BOOKS=auto
CLV_RECENT_MIN_PCT = int(os.environ.get('AUDIT_CLV_MIN_PCT', '40'))  # alerte si fill récent <
STEAM_TRACK_MIN = int(os.environ.get('AUDIT_STEAM_TRACK_MIN', '40'))  # info si track record <
FALLBACK_SET = {'pinnacle', 'unibet', 'bwin', 'betsson'}


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

    # Point le PLUS PROCHE du départ, toutes sources confondues. hist[-1] seul est
    # trompeur : l'historique est dédoublonné (cote stable près du départ => pas de
    # ré-append), alors que le worker capture bien des snapshots pinnacle_t25/t15/t7/t3
    # et un objet 'closing' (le vrai minimum, avec flag reliable). On lit donc le min
    # de mins_before sur : closing + snapshots + historique.
    def _closest_mb(m):
        cands = []
        c = m.get('closing') or {}
        if isinstance(c.get('mins_before'), (int, float)):
            cands.append(c['mins_before'])
        for label in ('t25', 't15', 't7', 't3'):
            s = m.get(f'pinnacle_{label}') or {}
            if isinstance(s.get('mins_before'), (int, float)):
                cands.append(s['mins_before'])
        for p in m.get('history', []):
            if isinstance(p.get('mins_before'), (int, float)):
                cands.append(p['mins_before'])
        cands = [x for x in cands if x >= -2]   # ignore les points post-coup d'envoi
        return min(cands) if cands else None

    def _latest_capture(m):
        ts = []
        for p in m.get('history', []):
            t = p.get('t') or p.get('captured_at')   # l'historique utilise 't'
            if t:
                ts.append(t)
        for label in ('t25', 't15', 't7', 't3'):
            s = m.get(f'pinnacle_{label}') or {}
            if s.get('captured_at'):
                ts.append(s['captured_at'])
        c = m.get('closing') or {}
        if c.get('captured_at'):
            ts.append(c['captured_at'])
        return max(ts) if ts else None

    latest = None
    items = []
    for uid, m in closing.items():
        ct = m.get('commence_time', '')
        items.append((ct, _closest_mb(m)))
        lc = _latest_capture(m)
        if lc:
            try:
                t = datetime.datetime.fromisoformat(lc.replace('Z', ''))
                if latest is None or t > latest:
                    latest = t
            except Exception:
                pass

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


def _esc(s):
    """Échappe les caractères spéciaux HTML pour parse_mode=HTML (évite Bad Request)."""
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def format_report(problems):
    order = {'CRITIQUE': 0, 'ALERTE': 1, 'INFO': 2}
    icon = {'CRITIQUE': '🔴', 'ALERTE': '🟠', 'INFO': '🔵'}
    problems = sorted(problems, key=lambda p: order.get(p[0], 9))
    lines = ["🔍 <b>Audit QA — anomalies détectées</b>\n"]
    for sev, msg in problems:
        lines.append(f"{icon.get(sev,'•')} <b>{_esc(sev)}</b> — {_esc(msg)}")
    lines.append("\n<i>Audit automatique. Vérifie les points ci-dessus.</i>")
    return "\n".join(lines)


def _parse_any_dt(s):
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if d.tzinfo is not None:
            d = d.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return d
    except Exception:
        try:
            return datetime.datetime.strptime(str(s)[:10], '%Y-%m-%d')
        except Exception:
            return None


def check_new_pipeline(problems):
    """Contrôles des briques récentes : élargissement books, dérivés multi-books,
    remplissage CLV, accumulation du track record steam. Silencieux si tout va bien."""
    now = _utcnow()
    recent_cut = now - datetime.timedelta(days=RECENT_DAYS)

    # 1) Largeur de books dans la capture récente (fr_books a-t-il pris effet ?)
    if os.path.exists(CURVES_FILE):
        try:
            recent_books, all_books = set(), set()
            for line in open(CURVES_FILE, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                b = r.get('book')
                if not b:
                    continue
                all_books.add(b)
                ct = _parse_any_dt(r.get('commence_time'))
                if ct and ct >= recent_cut:
                    recent_books.add(b)
            ref = recent_books or all_books
            if ref and len(ref) < EXPECT_BOOKS_MIN:
                extra = ref - FALLBACK_SET
                hint = "élargissement non pris (repli 4 books ?)" if ref <= FALLBACK_SET \
                    else f"seulement {len(ref)} books"
                problems.append(('INFO',
                    f"Books capturés récemment : {len(ref)} ({hint}). "
                    f"Si CAPTURE_BOOKS=auto attendu, vérifie fr_books / l'appel /bookmakers."))
        except Exception as e:
            problems.append(('INFO', f"{CURVES_FILE} : lecture books impossible ({e})."))

    # 2) Dérivés multi-books : le champ 'books' contient-il des books mous ?
    if os.path.exists(GAMES_FILE):
        try:
            gm = json.load(open(GAMES_FILE, encoding='utf-8'))
            soft = set()
            for m in (gm.values() if isinstance(gm, dict) else []):
                for p in m.get('history', []):
                    for b in (p.get('books') or {}):
                        if b != 'pinnacle':
                            soft.add(b)
            if not soft:
                problems.append(('INFO',
                    "Dérivés (games_markets) : aucun book mou capté pour l'instant "
                    "(couverture EU ou patch games_markets pas encore actif)."))
        except Exception as e:
            problems.append(('INFO', f"{GAMES_FILE} : lecture dérivés impossible ({e})."))

    # 3) Remplissage CLV sur les matchs récents (le bug à 2% est-il bien résolu ?)
    if os.path.exists(BACKTEST_FILE):
        try:
            rows = list(csv.DictReader(open(BACKTEST_FILE, encoding='utf-8', errors='replace'),
                                       delimiter=CSV_SEP))
            rec = [r for r in rows if (_parse_any_dt(r.get('date_match')) or now) >= recent_cut] or rows
            filled = sum(1 for r in rec if (r.get('clv_closing_15') or '').strip() not in ('', 'nan', 'None'))
            pct = 100 * filled / len(rec) if rec else 0
            if rec and pct < CLV_RECENT_MIN_PCT:
                problems.append(('ALERTE',
                    f"CLV récent peu rempli : clv_closing_15 à {pct:.0f}% sur {len(rec)} matchs "
                    f"(< {CLV_RECENT_MIN_PCT}%). Vérifie que fetch_results patché a tourné."))
        except Exception as e:
            problems.append(('INFO', f"{BACKTEST_FILE} : calcul fill CLV impossible ({e})."))

    # 4) Track record steam : assez de matchs multi-books PASSÉS pour fiabiliser les paliers ?
    if os.path.exists(CURVES_FILE):
        try:
            per_uid = {}
            for line in open(CURVES_FILE, encoding='utf-8'):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                ct = _parse_any_dt(r.get('commence_time'))
                d = per_uid.setdefault(r['uid'], {'books': set(), 'ct': ct})
                d['books'].add(r.get('book'))
            usable = sum(1 for d in per_uid.values()
                         if d['ct'] and d['ct'] < now and 'pinnacle' in d['books']
                         and len(d['books'] - {'pinnacle'}) >= 1)
            if usable < STEAM_TRACK_MIN:
                problems.append(('INFO',
                    f"Track record steam : {usable} matchs multi-books passés "
                    f"(< {STEAM_TRACK_MIN}). Les paliers par book restent indicatifs — "
                    f"normal tant que le volume monte."))
        except Exception:
            pass


def run_audit():
    problems = []
    check_files_exist(problems)
    check_csv_integrity(problems)
    check_closing_health(problems)
    check_joins(problems)
    check_new_pipeline(problems)

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
