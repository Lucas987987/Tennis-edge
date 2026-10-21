#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_book_curves.py (v6) — Courbes historiques par bookmaker, MATCH + SET1 + SET2.

Un seul appel /fixtures/odds/historical par (match, book) recupere en une fois :
  - vainqueur du match (121/122)  -> book_curves.jsonl       (inchange)
  - vainqueur du set 1 (123/124)  -> set1_curves.jsonl       (NOUVEAU)
  - vainqueur du set 2 (125/126)  -> set2_curves.jsonl       (NOUVEAU)
ZERO requete supplementaire : les marches set sont deja dans le meme payload.

Les fichiers set sont au MEME format que book_curves.jsonl (home_curve/away_curve =
cotes "joueur gagne le set"), donc steam_alert / steam_backtest / paper_journal
fonctionnent dessus sans modification : il suffit de pointer CURVES sur set1_curves.jsonl.

Env : RAPIDAPI_KEY. BOOKS (def "pinnacle,unibet,bwin,betsson").
      BOOK_CURVES (def book_curves.jsonl), SET1_CURVES (def set1_curves.jsonl),
      SET2_CURVES (def set2_curves.jsonl). CLV_MAX_PER_RUN (def 40), CLV_COOLDOWN (def 3.0).
"""
import os, json, datetime, time, re, unicodedata
import oddspapi_v5 as ov
from r2_collector_sink import finish_sink, sink_for
import closing_store   # closing_lines chaud + archives mensuelles (16/10/2026)


def _norm(s):
    # IDENTIQUE a build_live_curves._norm : meme normalisation partout, sinon
    # les uid divergent selon le script qui les a produits.
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def _slug(name):
    return _norm(name)

CLOSING_FILE = 'closing_lines.json'
OUT = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
SET1_OUT = os.environ.get('SET1_CURVES', 'set1_curves.jsonl')
SET2_OUT = os.environ.get('SET2_CURVES', 'set2_curves.jsonl')
BOOKS = [b.strip() for b in os.environ.get('BOOKS', os.environ.get('BOOK', 'pinnacle,unibet,bwin,betsson')).split(',') if b.strip()]
MAX_PER_RUN = int(os.environ.get('CLV_MAX_PER_RUN', '40'))   # ancien plafond, inutilisé depuis le 27/10
COOLDOWN = float(os.environ.get('CLV_COOLDOWN', '3.0'))

# ── 27/10/2026 : BUDGET au lieu d'un plafond fixe ──────────────────────────
# Avant : 40 matchs par book et par nuit, les plus récents d'abord. Avec ~55
# matchs/jour (pics à 117), des matchs n'étaient JAMAIS récupérés : un biais
# discret (il manquait surtout les grosses journées). Désormais :
#   — on prend TOUS les matchs commencés de la fenêtre (60 jours), les plus
#     ANCIENS d'abord (leur historique risque d'expirer côté API) ;
#   — niveau 1 (Pinnacle + books clés) pour TOUS les matchs en attente, puis
#     niveau 2 (les autres books) : si le budget manque, on perd des books
#     secondaires, jamais des matchs ;
#   — on s'arrête quand le quota restant ne couvre plus la capture jusqu'au
#     renouvellement (CAPTURE_PAR_JOUR × jours restants) ;
#   — un book qui ne cote pas un match est noté (courbes_absences.json) et
#     n'est redemandé qu'une fois, 24 h plus tard : avant, il était redemandé
#     CHAQUE nuit pendant 60 jours.
CAPTURE_PAR_JOUR = int(os.environ.get('CAPTURE_PAR_JOUR', '1100'))
MAX_RUN = int(os.environ.get('CURVES_MAX_RUN', '2500'))
NIVEAU1 = [b.strip() for b in os.environ.get(
    'BOOKS_NIVEAU1', 'pinnacle,betfair-ex,bet365,1xbet,22bet,unibet,winamax.fr,unibet.fr,pmu').split(',') if b.strip()]
ABSENCES = os.environ.get('CURVES_ABSENCES', 'courbes_absences.json')
COUVERTURE = os.environ.get('CURVES_COUVERTURE', 'courbes_couverture.json')
RETRY_H = 24
# 21/10/2026 : une seule tentative. La courbe historique est demandée APRÈS le
# match : un book absent l'est pour de bon (mesuré : la seconde tentative ne
# servait jamais, 50 % des requêtes perdues en « ne cote pas »).
MAX_ESSAIS = int(os.environ.get('CURVES_MAX_ESSAIS', '1'))
# Apprentissage : un book qui ne cote presque jamais un TYPE de tournoi
# (≥ APPRIS_MIN essais, < APPRIS_TAUX de réussite) n'y est plus demandé.
STATS = os.environ.get('CURVES_STATS', 'courbes_stats.json')
APPRIS_MIN = int(os.environ.get('CURVES_APPRIS_MIN', '40'))
APPRIS_TAUX = float(os.environ.get('CURVES_APPRIS_TAUX', '0.05'))


def categorie(tournoi):
    t = str(tournoi or '').lower()
    if 'itf' in t:
        return 'ITF'
    if 'challenger' in t:
        return 'Challenger'
    if '125' in t:
        return 'WTA 125'
    if t.startswith('wta') or 'women' in t:
        return 'WTA'
    return 'ATP'


def charger_stats(path=STATS):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def exclu(stats, book, cat):
    e, r = (stats.get(f"{book}|{cat}") or [0, 0])
    return book != 'pinnacle' and e >= APPRIS_MIN and r / e < APPRIS_TAUX


def charger_absences(path=ABSENCES):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def plan(started, done, absences, books, now, niveau1=NIVEAU1, stats=None):
    """Paires (match, book) à demander, dans l'ordre : niveau 1 puis niveau 2 ;
    dans chaque niveau, matchs du plus ancien au plus récent, Pinnacle d'abord.
    Les couples (book, type de tournoi) appris comme « ne cote jamais » sont sautés."""
    rang = {b: i for i, b in enumerate(books)}
    stats = stats or {}
    out = []
    for uid, m, fid, start in started:
        cat = categorie(m.get('tournament'))
        for book in books:
            if (uid, book) in done or exclu(stats, book, cat):
                continue
            a = absences.get(f"{uid}|{book}")
            if a:
                if a.get('essais', 0) >= MAX_ESSAIS:
                    continue
                try:
                    last = datetime.datetime.fromisoformat(a['dernier'])
                except (KeyError, ValueError):
                    last = None
                if last and (now - last).total_seconds() < RETRY_H * 3600:
                    continue
            niveau = 1 if book in niveau1 else 2
            out.append((niveau, start, rang[book], uid, m, fid, book))
    out.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    return [(uid, m, fid, start, book) for _, start, _, uid, m, fid, book in out]


def reserve_mesuree(prec, quota_debut, now, plancher=CAPTURE_PAR_JOUR):
    """Consommation RÉELLE du reste du projet (capture, CLV, résultats…) entre la fin
    du run précédent et le début de celui-ci, × 1,3 de marge ; jamais sous le plancher."""
    try:
        fin = prec['quota_fin']['remaining']
        t0 = datetime.datetime.fromisoformat(prec['quota_fin']['a'])
    except (KeyError, TypeError, ValueError):
        return plancher, None
    jours = (now - t0).total_seconds() / 86400
    if quota_debut is None or jours < 0.25 or quota_debut > fin:     # renouvellement entre-temps
        return plancher, None
    par_jour = (fin - quota_debut) / jours
    return max(plancher, int(1.3 * par_jour)), round(par_jour)


def marge_quota(reserve_par_jour=CAPTURE_PAR_JOUR):
    """Requêtes encore dépensables sans entamer la capture jusqu'au renouvellement.
    None tant qu'aucune réponse n'a donné le quota (on fait au moins un appel)."""
    q = ov.QUOTA
    if not q or q.get('remaining') is None:
        return None
    jours = max(1.0, (q.get('reset_s') or 0) / 86400.0)
    return q['remaining'] - int(reserve_par_jour * jours)


def _curve_dt(pts):
    """(ts_ms, price[, limit]) -> [(datetime, price, limit_or_None)] trie.
    La LIMITE DE MISE Pinnacle est exposee par /fixtures/odds/historical. Elle
    monte par paliers quand le marche murit (25 -> 50 -> 100 -> 125) : c'est un
    proxy de la confiance du book dans son prix. Recuperee ici sans requete
    supplementaire (meme appel historique). Hypothese a tester : un mouvement a
    limite elevee se referme-t-il plus souvent qu'a limite basse ?"""
    out = []
    for pt in (pts or []):
        if not pt:
            continue
        ts, pr = pt[0], pt[1]
        lim = pt[2] if len(pt) > 2 else None
        if pr is None:
            continue
        try:
            out.append((datetime.datetime.utcfromtimestamp(int(ts) / 1000.0), float(pr),
                        float(lim) if lim is not None else None))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def metrics(curve, start):
    if not curve:
        return None
    op = curve[0][1]
    before = [c[1] for c in curve if c[0] <= start] if start else None
    cl = before[-1] if before else curve[-1][1]
    lims = [c[2] for c in curve if len(c) > 2 and c[2] is not None]
    pre_lims = ([c[2] for c in curve if c[0] <= start and len(c) > 2 and c[2] is not None]
                if start else lims)
    return {'open': op, 'close': cl, 'n_points': len(curve),
            'first_t': curve[0][0].isoformat(), 'last_t': curve[-1][0].isoformat(),
            'limit_open': lims[0] if lims else None,
            'limit_close': pre_lims[-1] if pre_lims else None,
            'limit_max': max(pre_lims) if pre_lims else None}


def build_entry(uid, fid, book, m, start, ch, ca):
    """Entree au format book_curves (reutilisable pour match / set1 / set2)."""
    return {'uid': uid, 'fixture_id': fid, 'book': book,
            'commence_time': m.get('commence_time'), 'home': m.get('home'),
            'away': m.get('away'), 'tournament': m.get('tournament'),
            'home_metrics': metrics(ch, start), 'away_metrics': metrics(ca, start),
            'home_curve': [([c[0].isoformat(), c[1]] + ([c[2]] if len(c) > 2 and c[2] is not None else []))
                           for c in ch],
            'away_curve': [([c[0].isoformat(), c[1]] + ([c[2]] if len(c) > 2 and c[2] is not None else []))
                           for c in ca]}


def main():
    if not ov.KEY:
        print("❌ RAPIDAPI_KEY absente"); return
    if not closing_store.exists(CLOSING_FILE):
        print("Pas de closing_lines.json"); return
    closing = closing_store.load_all(CLOSING_FILE)

    done = set()
    # LECTURE : couvrir tout l'historique (fichier legacy + partitions
    # mensuelles), sinon le script re-traiterait des matchs déjà capturés
    # avant la migration -- voir iter_hist_lines() dans oddspapi_v5.py.
    for line in ov.iter_hist_lines('book'):
        try:
            d = json.loads(line); done.add((d.get('uid'), d.get('book')))
        except json.JSONDecodeError:
            pass

    now = datetime.datetime.utcnow()
    started = []
    for raw_uid, m in closing.items():
        fid = m.get('fixture_id') or m.get('id')
        ct = m.get('commence_time', '')
        if not fid or not ct:
            continue
        # UID CANONIQUE : closing_lines.json peut contenir des entrees a l'ANCIEN
        # format ('tournoi_joueur_vs_joueur') sur des matchs jamais migres. Sans
        # ce recalcul, l'historique hériterait du meme defaut -> ces matchs
        # deviennent introuvables par canal_clv/canal_suivi qui cherchent le
        # format date (bug identifie : matchs presents mais sous 2 uid distincts,
        # aucun ne matchant celui attendu par le canal).
        home = m.get('home', ''); away = m.get('away', '')
        uid = f"{ct[:10]}_{_slug(home)}_{_slug(away)}" if home and away else raw_uid
        try:
            start = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            continue
        if start > now:
            continue
        started.append((uid, m, fid, start))

    # PRIORITE AUX MATCHS RECENTS : sans tri, l'ordre est celui du dict
    # closing_lines.json (arbitraire). Avec des centaines de matchs en attente
    # (queue historique) et seulement MAX_PER_RUN traites par run, les matchs
    # RECENTS (ceux dont canal_clv_recap/canal_suivi ont besoin pour mesurer
    # les ecarts signales cette semaine) pouvaient rester indefiniment noyes
    # dans le backlog. On traite donc les plus recents en premier.
    started.sort(key=lambda x: x[3])
    # GARDE-FOU : si l'historique n'a pas été rapatrié (R2 indisponible, checkout
    # incomplet), `done` est presque vide et on redemanderait TOUT ce qu'on a déjà :
    # des milliers de requêtes perdues. On refuse dans ce cas.
    anciens = [x for x in started if (now - x[3]).days >= 3]
    vus = sum(1 for x in anciens if (x[0], 'pinnacle') in done)
    if len(anciens) >= 100 and vus < 0.3 * len(anciens) and os.environ.get('CURVES_FORCE') != '1':
        print(f"❌ historique incomplet ? Pinnacle connu pour {vus}/{len(anciens)} matchs de plus de 3 jours. "
              "Rien n'est demandé (CURVES_FORCE=1 pour passer outre).")
        raise SystemExit(1)
    absences = charger_absences()
    stats = charger_stats()
    if not stats:
        # Premier passage : on amorce l'apprentissage avec ce qu'on sait déjà
        # (courbes obtenues = réussites, absences notées = échecs).
        for uid, m, fid, start in started:
            cat = categorie(m.get('tournament'))
            for book in BOOKS:
                if (uid, book) in done:
                    st = stats.setdefault(f"{book}|{cat}", [0, 0]); st[0] += 1; st[1] += 1
                elif f"{uid}|{book}" in absences:
                    stats.setdefault(f"{book}|{cat}", [0, 0])[0] += 1
    todo = plan(started, done, absences, BOOKS, now, stats=stats)
    appris = sorted(k for k in stats if exclu(stats, *k.split('|', 1)))
    if appris:
        print(f"Appris « ne cote jamais » (sautés) : {', '.join(appris)}")
    try:
        with open(COUVERTURE, encoding='utf-8') as fp:
            precedent = json.load(fp)
    except (OSError, ValueError):
        precedent = {}
    reserve, conso_mesuree = CAPTURE_PAR_JOUR, None
    print(f"{len(started)} matchs commencés dans la fenêtre · {len(todo)} paires (match, book) à demander "
          f"(niveau 1 : {sum(1 for t in todo if t[4] in NIVEAU1)})")

    total = {'match': 0, 'set1': 0, 'set2': 0}
    # un seul appel ramene match + set1 + set2
    OUTCOMES = (ov.OUT_HOME, ov.OUT_AWAY, ov.SET1_HOME, ov.SET1_AWAY, ov.SET2_HOME, ov.SET2_AWAY)
    # ÉCRITURE : partition du MOIS COURANT, plus jamais le fichier monolithique
    # (voir note au-dessus d'iter_hist_lines dans oddspapi_v5.py -- book_curves.
    # jsonl a atteint 140,73 Mo et GitHub rejette tout push > 100 Mo).
    out_path = ov.current_hist_partition_path('book')
    set1_path = ov.current_hist_partition_path('set1')
    set2_path = ov.current_hist_partition_path('set2')
    demandes, absents, arret = 0, 0, None
    par_book = {}
    with open(out_path, 'a', encoding='utf-8') as f, \
         open(set1_path, 'a', encoding='utf-8') as f1, \
         open(set2_path, 'a', encoding='utf-8') as f2:
        for uid, m, fid, start, book in todo:
            if demandes >= MAX_RUN:
                arret = f"plafond du run ({MAX_RUN})"
                break
            if demandes == 1 and ov.QUOTA.get('remaining') is not None:
                reserve, conso_mesuree = reserve_mesuree(precedent, ov.QUOTA['remaining'] + 1, now)
                print(f"Réserve pour le reste du projet : {reserve}/jour"
                      f"{f' (consommation mesurée {conso_mesuree}/jour × 1,3)' if conso_mesuree is not None else ' (plancher)'}")
            marge = marge_quota(reserve)
            if marge is not None and marge <= 0:
                arret = (f"quota : {ov.QUOTA.get('remaining')} restants, réservés au reste du projet "
                         f"({reserve}/jour jusqu'au renouvellement)")
                break
            if ov.QUOTA_HIT:
                arret = "quota épuisé (429)"
                break
            time.sleep(COOLDOWN)
            demandes += 1
            try:
                curves = ov.historical_curves(fid, book, OUTCOMES, with_limit=True)
            except Exception as e:
                print(f"  ⚠️ {book} fixtureId={fid}: {e}")
                continue
            ch = _curve_dt(curves.get(ov.OUT_HOME)); ca = _curve_dt(curves.get(ov.OUT_AWAY))
            sk = f"{book}|{categorie(m.get('tournament'))}"
            st = stats.setdefault(sk, [0, 0])
            st[0] += 1
            if ch and ca:
                st[1] += 1
            if not ch or not ca:
                key = f"{uid}|{book}"
                a = absences.get(key) or {'essais': 0}
                absences[key] = {'essais': a.get('essais', 0) + 1, 'dernier': now.isoformat(timespec='seconds')}
                absents += 1
                continue  # book ne cote pas ce match : noté, redemandé au plus une fois
            absences.pop(f"{uid}|{book}", None)
            pb = par_book.setdefault(book, {'match': 0, 'set1': 0, 'set2': 0})
            entry = build_entry(uid, fid, book, m, start, ch, ca)
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            sink = sink_for('bookmakers')
            if sink is not None:
                sink.write_bookmaker_curve('match', entry)
            pb['match'] += 1; total['match'] += 1
            # set 1 (123/124) — meme format, ecrit seulement si le book le cote
            c1h = _curve_dt(curves.get(ov.SET1_HOME)); c1a = _curve_dt(curves.get(ov.SET1_AWAY))
            if c1h and c1a:
                entry = build_entry(uid, fid, book, m, start, c1h, c1a)
                f1.write(json.dumps(entry, ensure_ascii=False) + '\n')
                if sink is not None:
                    sink.write_bookmaker_curve('set1', entry)
                pb['set1'] += 1; total['set1'] += 1
            # set 2 (125/126)
            c2h = _curve_dt(curves.get(ov.SET2_HOME)); c2a = _curve_dt(curves.get(ov.SET2_AWAY))
            if c2h and c2a:
                entry = build_entry(uid, fid, book, m, start, c2h, c2a)
                f2.write(json.dumps(entry, ensure_ascii=False) + '\n')
                if sink is not None:
                    sink.write_bookmaker_curve('set2', entry)
                pb['set2'] += 1; total['set2'] += 1
    for book, got in sorted(par_book.items()):
        print(f"  ✅ {book}: {got['match']} match | {got['set1']} set1 | {got['set2']} set2")
    # Absences : on ne garde que la fenêtre de 60 jours (fichier borné).
    limite = (now - datetime.timedelta(days=61)).date().isoformat()
    absences = {k: v for k, v in absences.items() if k[:10] >= limite or not k[:4].isdigit()}
    with open(ABSENCES, 'w', encoding='utf-8') as fa:
        json.dump(absences, fa, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    with open(STATS, 'w', encoding='utf-8') as fs:
        json.dump(stats, fs, ensure_ascii=False, sort_keys=True, indent=0)
    restant = len(todo) - demandes
    couv = {'ecrit_le': now.isoformat(timespec='seconds'), 'demandes': demandes, 'courbes': total['match'],
            'book_ne_cote_pas': absents, 'paires_en_attente': max(0, restant), 'arret': arret,
            'quota': {k: ov.QUOTA.get(k) for k in ('limit', 'remaining', 'reset_s')},
            'capture_reservee_par_jour': reserve, 'conso_mesuree_par_jour': conso_mesuree,
            'quota_fin': {'remaining': ov.QUOTA.get('remaining'), 'a': datetime.datetime.utcnow().isoformat(timespec='seconds')},
            'appris_ne_cote_jamais': appris,
            'plus_ancien_en_attente': (todo[demandes][3].isoformat() if restant > 0 else None)}
    with open(COUVERTURE, 'w', encoding='utf-8') as fc:
        json.dump(couv, fc, ensure_ascii=False, indent=1)
    print(f"Couverture : {demandes} demandes, {total['match']} courbes, {absents} « ne cote pas », "
          f"{max(0, restant)} paires en attente{' — arrêt : ' + arret if arret else ''}")
    print(f"\n✅ total — match {total['match']} | set1 {total['set1']} | set2 {total['set2']} ({len(BOOKS)} books)")

    # Sidecar pour audit_qa.py : timestamp EMBARQUÉ DANS LE CONTENU (pas le
    # mtime, peu fiable dans un checkout GitHub Actions frais -- même logique
    # que matches_oddspapi_meta.json) + taille de CHAQUE partition, pour
    # détecter un run qui tourne "sans erreur" mais dont le push échoue
    # silencieusement (voir migrate_hist_partitions.py pour le contexte :
    # book_curves.jsonl a atteint 140,73 Mo le 14/08/2026, bloquant tout push
    # pendant 5 jours sans qu'aucune alerte ne se déclenche).
    try:
        import glob
        sizes = {}
        # .jsonl ET .jsonl.gz (compression du 16/08/2026)
        for p in glob.glob('parts/hist_*.jsonl') + glob.glob('parts/hist_*.jsonl.gz'):
            sizes[p] = round(os.path.getsize(p) / 1e6, 1)
        with open('hist_curves_meta.json', 'w', encoding='utf-8') as f:
            json.dump({'last_write': datetime.datetime.utcnow().isoformat(),
                      'total': total, 'partition_sizes_mb': sizes}, f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Écriture hist_curves_meta.json: {e}")

    report = finish_sink('bookmakers')
    if report:
        print(f"✅ V6.4 shadow vérifié: {report}")


if __name__ == '__main__':
    main()
