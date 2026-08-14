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
MAX_PER_RUN = int(os.environ.get('CLV_MAX_PER_RUN', '40'))
COOLDOWN = float(os.environ.get('CLV_COOLDOWN', '3.0'))


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
    if not os.path.exists(CLOSING_FILE):
        print("Pas de closing_lines.json"); return
    closing = json.load(open(CLOSING_FILE, encoding='utf-8'))

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
    started.sort(key=lambda x: x[3], reverse=True)

    total = {'match': 0, 'set1': 0, 'set2': 0}
    # un seul appel ramene match + set1 + set2
    OUTCOMES = (ov.OUT_HOME, ov.OUT_AWAY, ov.SET1_HOME, ov.SET1_AWAY, ov.SET2_HOME, ov.SET2_AWAY)
    # ÉCRITURE : partition du MOIS COURANT, plus jamais le fichier monolithique
    # (voir note au-dessus d'iter_hist_lines dans oddspapi_v5.py -- book_curves.
    # jsonl a atteint 140,73 Mo et GitHub rejette tout push > 100 Mo).
    out_path = ov.current_hist_partition_path('book')
    set1_path = ov.current_hist_partition_path('set1')
    set2_path = ov.current_hist_partition_path('set2')
    with open(out_path, 'a', encoding='utf-8') as f, \
         open(set1_path, 'a', encoding='utf-8') as f1, \
         open(set2_path, 'a', encoding='utf-8') as f2:
        for book in BOOKS:
            todo = [x for x in started if (x[0], book) not in done][:MAX_PER_RUN]
            print(f"[{book}] {len(todo)} matchs a traiter")
            got = {'match': 0, 'set1': 0, 'set2': 0}; warned = False
            for uid, m, fid, start in todo:
                time.sleep(COOLDOWN)
                try:
                    curves = ov.historical_curves(fid, book, OUTCOMES, with_limit=True)
                except Exception as e:
                    if not warned:
                        print(f"  ⚠️ {book} fixtureId={fid}: {e}"); warned = True
                    continue
                ch = _curve_dt(curves.get(ov.OUT_HOME)); ca = _curve_dt(curves.get(ov.OUT_AWAY))
                if not ch or not ca:
                    continue  # book ne cote pas ce match
                f.write(json.dumps(build_entry(uid, fid, book, m, start, ch, ca), ensure_ascii=False) + '\n')
                got['match'] += 1
                # set 1 (123/124) — meme format, ecrit seulement si le book le cote
                c1h = _curve_dt(curves.get(ov.SET1_HOME)); c1a = _curve_dt(curves.get(ov.SET1_AWAY))
                if c1h and c1a:
                    f1.write(json.dumps(build_entry(uid, fid, book, m, start, c1h, c1a), ensure_ascii=False) + '\n')
                    got['set1'] += 1
                # set 2 (125/126)
                c2h = _curve_dt(curves.get(ov.SET2_HOME)); c2a = _curve_dt(curves.get(ov.SET2_AWAY))
                if c2h and c2a:
                    f2.write(json.dumps(build_entry(uid, fid, book, m, start, c2h, c2a), ensure_ascii=False) + '\n')
                    got['set2'] += 1
            print(f"  ✅ {book}: {got['match']} match | {got['set1']} set1 | {got['set2']} set2")
            for k in total: total[k] += got[k]
    print(f"\n✅ total — match {total['match']} | set1 {total['set1']} | set2 {total['set2']} ({', '.join(BOOKS)})")

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
        for p in glob.glob('parts/hist_*.jsonl'):
            sizes[p] = round(os.path.getsize(p) / 1e6, 1)
        with open('hist_curves_meta.json', 'w', encoding='utf-8') as f:
            json.dump({'last_write': datetime.datetime.utcnow().isoformat(),
                      'total': total, 'partition_sizes_mb': sizes}, f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Écriture hist_curves_meta.json: {e}")


if __name__ == '__main__':
    main()
