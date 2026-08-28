#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_journal.py — Journal de paper-trading FORWARD du steam-following.

But : prouver l'edge sur des donnees jamais backtestees. A chaque cycle :
  1. SETTLE : pour chaque pari fictif OUVERT dont le match est fini, renseigne la
     cloture (book + fair Pinnacle) et le resultat -> calcule CLV reel + P&L.
  2. OPEN   : detecte les nouveaux signaux (memes que steam_alert : drift Pinnacle
     >= seuil propre au book, value encore dispo) et logue un pari fictif OUVERT.
  3. RESUME : CLV moyen/median/%positif + ROI, global et par book, sur les settled.

Le pari fictif = exactement ce que steam_alert t'aurait dit de miser (meilleur book
par match). 1 unite de mise. Aucun argent reel, aucun appel API.

Modes :
  - normal (defaut) : forward. Ouvre les matchs A VENIR, settle ceux finis. Persiste.
  - BACKFILL=1 : rejoue tout l'historique d'un coup (ouvre au signal, settle au close)
    -> rapport CLV+ROI immediat sur tes donnees actuelles. Ne persiste pas le journal.

Env : JOURNAL (def paper_trades.jsonl), RESULTS_CSV (def backtest_tennis.csv),
  + tous les reglages de steam_alert (GRID, MIN_N, WINDOW_DAYS, MIN_LEAD, DEFAULT_THR,
  EV_MIN_NOW, SOFT_BOOKS, NOW_OVERRIDE, BACKFILL).
"""
import os, sys, json, csv, datetime, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# MARKET pilote la surface : match / set1 / set2. Choisit le fichier de courbes
# par defaut ET la source de resultats. (CURVES explicite l'emporte.)
MARKET = os.environ.get('MARKET', 'match').lower()
_DEF_CURVES = {'match': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl', 'set2': 'set2_curves.jsonl'}
os.environ.setdefault('CURVES', _DEF_CURVES.get(MARKET, 'book_curves.jsonl'))

import steam_alert as sa
import fiabilite_score as fs   # reutilise detection, seuils par book, helpers
import match_key as mk
import curves_common as cc

JOURNAL = os.environ.get('JOURNAL', f'paper_trades_{MARKET}.jsonl')
RESULTS_CSV = os.environ.get('RESULTS_CSV', 'backtest_tennis.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
BACKFILL = os.environ.get('BACKFILL', '0') == '1'

import unicodedata, re
def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[.\s]+', ' ', s).strip()
def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return t[-1] if t else ''


def load_results():
    out = {}
    if not os.path.exists(RESULTS_CSV):
        return out
    try:
        for r in csv.DictReader(open(RESULTS_CSV, encoding='utf-8', errors='replace'), delimiter=';'):
            res = (r.get('resultat') or '').strip()
            if res in ('0', '1'):
                out[r.get('uid')] = {'a_won': res == '1', 'ja': r.get('joueurA', '')}
    except Exception:
        pass
    return out


def load_set_results():
    """{uid: {'set1':'home'/'away', 'set2':..., 'match':...}} depuis set_results.json."""
    if not os.path.exists(SET_RESULTS):
        return {}
    try:
        return json.load(open(SET_RESULTS, encoding='utf-8'))
    except Exception:
        return {}


def build_result_side(data):
    """Cote gagnante ('home'/'away') par uid pour le MARKET courant."""
    rs = {}
    if MARKET == 'match':
        # 1) API set_results.json (settlement) — source qui FONCTIONNE sur ce runner.
        for uid, v in load_set_results().items():
            w = (v or {}).get('match')
            if w in ('home', 'away'):
                rs[uid] = w
        # 2) repli CSV backtest_tennis.csv (colonne resultat 0/1) pour ce qui manque
        #    encore (utile en BACKFILL si le CSV est rempli ; sinon sans effet).
        for uid, r in load_results().items():
            if uid in rs:
                continue
            bk = data.get(uid)
            if not bk:
                continue
            a_is_home = _ln(r['ja']) == _ln(bk.get('_home', ''))
            home_won = r['a_won'] if a_is_home else (not r['a_won'])
            rs[uid] = 'home' if home_won else 'away'
    else:  # set1 / set2
        for uid, v in load_set_results().items():
            w = (v or {}).get(MARKET)
            if w in ('home', 'away'):
                rs[uid] = w
    return rs


def load_journal():
    trades = {}
    if os.path.exists(JOURNAL):
        for line in open(JOURNAL, encoding='utf-8'):
            line = line.strip()
            if line:
                t = json.loads(line)
                trades[t['id']] = t
    return trades


def save_journal(trades):
    with open(JOURNAL, 'w', encoding='utf-8') as f:
        for t in trades.values():
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def pick_signal(bk, softbooks, thr_by_book, entry_at='now'):
    """Meilleur book actif. entry_at='detection' (t_e, pour backfill) ou 'now'
    (dernier point dispo, pour le live forward). Retourne le signal ou None."""
    if sa.SHARP not in bk:
        return None
    ptimes = sorted(set(t for t, _ in bk[sa.SHARP]['h']))
    cands = []
    for sb in softbooks:
        if sb not in bk:
            continue
        mv, sdat, conf = thr_by_book[sb]
        d = sa.detect(bk[sa.SHARP], mv)
        if not d:
            continue
        t_e, side = d
        et = t_e if entry_at == 'detection' else ptimes[-1]
        pf = sa._fair(bk[sa.SHARP], et)
        pfair = (pf if side == 'home' else 1 - pf) if pf else None
        ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
        cur = sa._at(ser, et)
        if not cur or cur <= 1:
            continue
        if pfair and (cur * pfair - 1) < sa.EV_MIN_NOW:
            continue
        pct = sdat['pct'] if sdat else 0
        cands.append({'book': sb, 'thr': mv, 'side': side, 'odds': cur, 'pct': pct, 't_e': t_e})
    if not cands:
        return None
    return max(cands, key=lambda c: (c['pct'], c['odds']))


def _dernier_avant(curve, ts_limite):
    """Dernier point de `curve` (liste de (ts, prix,...)) daté <= ts_limite."""
    ts_limite = str(ts_limite)[:19]
    meilleur = None
    for pt in curve:
        t = str(pt[0])[:19]
        if t <= ts_limite:
            if meilleur is None or t > str(meilleur[0])[:19]:
                meilleur = pt
    return meilleur[1] if meilleur else None


def cloture_fiable(home, away, commence_time, tournament, side, curve, _cache={}):
    """Clôture de référence pour le CLV -- AJOUTÉ LE 27/08/2026 (audit v2
    §L), RÉÉCRIT LE 27/08/2026 (audit v3 §P + §P-sémantique) après deux
    bugs successifs sur la même fonction :

    BUG 1 (§P) : `closing_lines.json` utilise une convention d'uid
    (circuit_tournoi_joueurs) totalement disjointe de celle des courbes/
    journaux (date_joueurs) -- intersection directe mesurée à 0/25. La
    version précédente faisait `.get(uid)` en direct : elle ne s'est JAMAIS
    déclenchée, un vrai no-op silencieux malgré des tests qui passaient
    (mes tests utilisaient un uid PRIS DANS closing_lines.json lui-même,
    donc auto-cohérents -- jamais un vrai uid de production). Corrigé ici
    par une clé NATURELLE (match_key.natural_key, agnostique au format
    d'uid) construite une fois pour tout closing_lines.json, mise en cache.

    BUG 2 (§P, sémantique) : closing_lines[uid]['closing'] est un prix
    PINNACLE (snapshots t25/t15/t7/t3), pas celui du book qui a servi à
    parier -- l'utiliser directement aurait redéfini clv_book en clv_pin
    SANS changer son nom, mélangé avec les anciennes valeurs dans le même
    fichier. Corrigé : on n'emprunte à closing_lines QUE son TIMESTAMP fiable
    (captured_at du dernier snapshot avant le départ), et on s'en sert pour
    trancher la courbe DU BOOK lui-même -- la fraîcheur et la référence de
    prix restent deux axes séparés, comme demandé.

    Compteur de résolutions exposé via cloture_fiable_stats() -- "un
    correctif qui échoue à 100% en silence est pire que pas de correctif".

    VÉRIFIÉ LE 28/08/2026 (audit v4 §T) : une fois le pont réellement
    branché (97,4% de résolution), l'effet mesuré est NUL -- 1364/1364
    prix strictement identiques à curve[-1] sur les partitions testées.
    Raison mécanique : steam_alert._pre() tronque déjà la courbe à
    commence_time avant qu'elle arrive ici, et captured_at (le snapshot
    fiable) est par construction antérieur au coup d'envoi -- il n'y a
    jamais rien APRÈS le dernier point de la courbe déjà tronquée pour que
    _dernier_avant() puisse trouver. L'écart de 7,9% que l'audit avait
    mesuré dans son addendum opposait deux sources PINNACLE entre elles
    (le snapshot vs le close de clv_history), pas la courbe du book à quoi
    que ce soit -- une divergence réelle, mais mesurée sur le mauvais
    objet, extrapolée à tort jusqu'ici.
    CE QUE CETTE FONCTION FAIT DONC RÉELLEMENT : elle n'a pas retiré de
    biais (il n'y en avait pas à cet endroit) -- elle a transformé une
    HYPOTHÈSE non vérifiée ("le dernier point est peut-être trop tardif")
    en INVARIANT MESURÉ, avec compteur et garde-fou. Conservée pour cette
    raison : filet de sécurité si un jour un book publie un point après
    captured_at, et preuve vivante que ce n'est actuellement pas le cas.

    CORRIGÉ LE 28/08/2026 (audit v5 §AA) : la clé complète posée hier
    (audit v4 §W, avec la date) neutralisait le pont exactement sur les
    matchs pour lesquels il sert -- 4 matchs perdus sur 160 (US Open, fin
    de soirée, commence_time à cheval sur minuit entre les deux sources).
    Délégué à curves_common.cherche_avec_tolerance() (±1 jour, un seul
    candidat accepté) -- fonction PARTAGÉE avec steam_alert/move_audit/
    canal_clv, pas une cinquième copie divergente."""
    if 'd' not in _cache:
        _cache['d'], _cache['idx'] = cc.build_closing_index()
        _cache['resolus'] = 0
        _cache['tentes'] = 0
    _cache['tentes'] += 1
    nat = mk.natural_key(home, away, commence_time)
    cl_uid = cc.cherche_avec_tolerance(_cache['idx'], nat)
    entree = _cache['d'].get(cl_uid) if cl_uid else None
    c = (entree or {}).get('closing') or {}
    if c.get('reliable') and c.get('captured_at') and curve:
        prix = _dernier_avant(curve, c['captured_at'])
        if prix:
            _cache['resolus'] += 1
            return prix, 'book_a_snapshot_fiable'
    if curve:
        return curve[-1][1], 'dernier_point'
    return None, None


def cloture_fiable_stats():
    """Compteur de résolutions -- appelé en fin de run, jamais silencieux."""
    c = cloture_fiable.__defaults__[0]
    t, r = c.get('tentes', 0), c.get('resolus', 0)
    return r, t


def settle_trade(t, data, result_side):
    """Renseigne cloture + resultat d'un pari ouvert si le match est dispo."""
    bk = data.get(t['uid'])
    if not bk or sa.SHARP not in bk:
        return False
    side = t['side']
    sb = t['book']
    if sb in bk:
        ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
        # CORRIGÉ LE 27/08/2026 (audit v3 §P) : signature complète (home,
        # away, commence, tournoi) -- l'ancienne version passait uid seul,
        # inutilisable pour retrouver l'entrée closing_lines (voir docstring
        # de cloture_fiable). bk['_commence'] est un EPOCH FLOAT (voir
        # steam_alert._dt) -- natural_key() attend une chaîne ISO pour en
        # extraire les 10 premiers caractères (YYYY-MM-DD) ; str(float)[:10]
        # aurait donné les premiers chiffres du nombre, pas une date.
        _ct = bk.get('_commence')
        _ct_iso = (datetime.datetime.utcfromtimestamp(_ct).isoformat()
                  if _ct else None)
        prix, source = cloture_fiable(bk.get('_home', ''), bk.get('_away', ''),
                                      _ct_iso, bk.get('_tour', ''),
                                      side, ser)
        if prix:
            t['close_book'] = prix
            t['close_source'] = source   # traçabilité -- jamais deviner après coup
    ptimes = sorted(set(x for x, _ in bk[sa.SHARP]['h']))
    fc = sa._fair(bk[sa.SHARP], ptimes[-1])
    if fc is not None:
        t['pin_fair_close'] = round(fc if side == 'home' else 1 - fc, 4)
    if t.get('close_book') and t['close_book'] > 1:
        t['clv_book'] = round((t['entry_odds'] / t['close_book'] - 1) * 100, 2)
    # AJOUTÉ LE 27/08/2026 (audit v3 §Q) : le VRAI test du biais de
    # sélection -- pick_signal() prend le MAX sur ~20 books pour choisir
    # l'entrée. clv_pin (ci-dessous) ne le teste PAS : même formule à
    # l'entrée et à la clôture, corrélation quasi mécanique (l'audit a
    # mesuré corr(clv_pin, pnl)=+0,178 sur n=45, et un %positif de 100% qui
    # est la signature d'une métrique qui reproduit son propre filtre).
    # clv_vs_median compare au book MÉDIAN parmi ceux actifs sur ce match --
    # si clv_vs_median s'effondre pendant que clv_book reste haut, c'est la
    # sélection du max qui gonfle le chiffre, pas un edge de marché.
    cloture_autres = []
    for _bkname, _bkval in bk.items():
        if _bkname in (sa.SHARP, sb) or _bkname.startswith('_'):
            continue
        _ser = _bkval.get('h') if side == 'home' else _bkval.get('a')
        if _ser:
            cloture_autres.append(_ser[-1][1])
    if cloture_autres and t.get('close_book'):
        cloture_autres.append(t['close_book'])   # le book d'entrée compte aussi dans la médiane
        med = st.median(cloture_autres)
        if med > 1:
            t['clv_vs_median'] = round((t['entry_odds'] / med - 1) * 100, 2)
            t['n_books_median'] = len(cloture_autres)
    if t.get('pin_fair_close'):
        # RENOMMÉ implicitement en pratique (audit v3 §Q) : ce champ reste
        # nommé clv_pin pour ne pas casser l'historique déjà committé, mais
        # ce N'EST PAS un CLV -- c'est l'EV au filtre d'entrée (EV_MIN_NOW),
        # relue avec le même pin_fair à la clôture. Voir report_group() pour
        # le libellé honnête affiché dans le rapport.
        t['clv_pin'] = round((t['entry_odds'] * t['pin_fair_close'] - 1) * 100, 2)
    # resultat + P&L (1 unite) selon le MARKET (match / set1 / set2)
    ws = result_side.get(t['uid'])
    if ws in ('home', 'away'):
        won = (side == ws)
        t['won'] = bool(won)
        t['pnl'] = round((t['entry_odds'] - 1) if won else -1.0, 3)
    # CORRIGÉ LE 27/08/2026 (audit v2 §A -- REFAIT après une divergence entre
    # ma copie de travail et le fichier réellement livré ce matin : le
    # correctif n'avait jamais atterri). SETTLED seulement avec un pnl réel.
    if 'pnl' in t:
        t['status'] = 'SETTLED'
        return True
    if 'clv_book' in t or 'clv_pin' in t:
        t['status'] = 'CLOSED_NO_RESULT'
        # AJOUTÉ LE 28/08/2026 (audit v4 §Z) : sans horodatage, un trade qui
        # n'obtient jamais de résultat (match jamais couvert par
        # set_results.json NI backtest_tennis.csv) reste CLOSED_NO_RESULT
        # indéfiniment, retraité à chaque cycle pour rien. Ne pose la date
        # qu'à la PREMIÈRE fois -- les cycles suivants ne l'écrasent pas.
        if 'closed_no_result_depuis' not in t:
            t['closed_no_result_depuis'] = datetime.date.today().isoformat()
        return True
    return False



def summary(trades):
    settled = [t for t in trades.values() if t.get('status') == 'SETTLED']
    op = [t for t in trades.values() if t.get('status') == 'OPEN']
    print(f"\n=== Journal : {len(settled)} denoues | {len(op)} ouverts ===")
    if not settled:
        print("  (pas encore de pari denoue)"); return
    def ag(name, lst):
        if not lst: return
        pos = 100 * sum(1 for x in lst if x > 0) / len(lst)
        print(f"  {name:22}: n={len(lst):3d} | moyen {st.mean(lst):+.2f} | median {st.median(lst):+.2f} | %pos {pos:.0f}%")
    ag("CLV vs cloture book", [t['clv_book'] for t in settled if 'clv_book' in t])
    ag("CLV vs fair Pinnacle", [t['clv_pin'] for t in settled if 'clv_pin' in t])
    pnls = [t['pnl'] for t in settled if 'pnl' in t]
    if pnls:
        roi = 100 * sum(pnls) / len(pnls)
        wr = 100 * sum(1 for t in settled if t.get('won')) / len([t for t in settled if 'won' in t])
        print(f"  RESULTAT REEL          : {len(pnls)} paris | ROI {roi:+.2f}% / mise | gagne {wr:.0f}%")
    # par book
    print("  -- par book (CLV book / ROI) --")
    for sb in sorted(set(t['book'] for t in settled)):
        sub = [t for t in settled if t['book'] == sb]
        clv = [t['clv_book'] for t in sub if 'clv_book' in t]
        pl = [t['pnl'] for t in sub if 'pnl' in t]
        clvm = f"{st.median(clv):+.1f}%" if clv else "n/a"
        roim = f"{100*sum(pl)/len(pl):+.1f}%" if pl else "n/a"
        print(f"     {sb:10}: n={len(sub):3d} | CLV med {clvm} | ROI {roim}")


def _truncate(bk, now):
    """Copie d'un match limitee aux points <= now (forward-only, anti look-ahead)."""
    out = {k: bk.get(k) for k in ('_commence', '_home', '_away', '_tour')}
    for k, v in bk.items():
        if k.startswith('_'):
            continue
        h = [(t, o) for t, o in v['h'] if t <= now]
        a = [(t, o) for t, o in v['a'] if t <= now]
        if len(h) >= 2 and len(a) >= 2:
            out[k] = {'h': h, 'a': a}
    return out


def main():
    data = sa.load_curves()
    now = sa._now()
    result_side = build_result_side(data)
    # track record pour les seuils : historique dedie (TRACK_CURVES) sinon les passes des donnees
    track = sa.load_curves(sa.TRACK_CURVES) if sa.TRACK_CURVES else data
    win_start = now - sa.WINDOW_DAYS * 86400 if sa.WINDOW_DAYS > 0 else 0
    past = {u: bk for u, bk in track.items()
            if bk.get('_commence') and win_start <= bk['_commence'] < now}
    # books mous : union (track passe + donnees a traiter), hors sharp
    softbooks = sorted({b for m in list(past.values()) + list(data.values())
                        for b in m if not b.startswith('_') and b != sa.SHARP})
    if sa.SOFT_PREF:
        keep = set(s.strip() for s in sa.SOFT_PREF.split(','))
        softbooks = [b for b in softbooks if b in keep]
    if not softbooks:
        print("Aucun book mou — rien a journaliser."); return

    stats = sa.compute_stats(past, softbooks)
    thr_by_book = {sb: sa.best_threshold(stats, sb) for sb in softbooks}

    if BACKFILL:
        print(f"MODE BACKFILL [{MARKET}] : rejoue tout l'historique (ne persiste pas).")
        trades = {}
        # DÉDUPLICATION CANONIQUE : deux conventions d'uid ont coexisté du 11/06 au
        # 09/08/2026 et l'horaire annoncé varie selon la source -> 208 uid désignent
        # un match DÉJÀ suivi. Sans ça, le journal ouvrirait DEUX positions sur le
        # même match, ce qui fausse le n et resserre à tort les IC. Voir match_key.py.
        _idx = mk.build_index([dict(uid=u, home=b.get('_home'), away=b.get('_away'),
                                                                commence_time=b.get('_commence'),
                                                                tournament=b.get('_tour'), fixture_id=b.get('_fx'))
                                                   for u, b in data.items()])
        _vus = set()
        for uid, bk in data.items():
            if not bk.get('_commence'):
                continue
            _k = _idx.key_of(uid)
            if _k in _vus:
                continue
            _vus.add(_k)
            sig = pick_signal(bk, softbooks, thr_by_book, entry_at=('detection' if BACKFILL else 'now'))
            if not sig:
                continue
            pser = bk[sa.SHARP]['h'] if sig['side'] == 'home' else bk[sa.SHARP]['a']
            # CORRIGÉ LE 27/08/2026 (audit §4.4) : clé CANONIQUE (_k), pas
            # l'uid brut -- deux uid du même match sur deux cycles
            # différents ouvraient deux trades séparés.
            t = {'id': f"{_k}|{sig['book']}|{int(sig['thr']*100)}", 'uid': uid,
                 'home': bk.get('_home'), 'away': bk.get('_away'), 'side': sig['side'],
                 'book': sig['book'], 'palier': int(sig['thr'] * 100),
                 'entry_odds': round(sig['odds'], 2), 'status': 'OPEN'}
            # NOTE DE FIABILITÉ (26/08/2026) — MODE OMBRE STRICT. Calculée à
            # l'entrée, journalisée, JAMAIS lue pour sizer la mise réelle
            # (pnl reste en 1 unité plus bas, inchangé). Sert uniquement au
            # suivi de shadow_sizing_study.py, qui juge SI cette note mérite
            # un jour de piloter une mise — verdict séparé, à sa propre date.
            try:
                lead_min = (bk.get('_commence', 0) - sig['t_e'].timestamp()) / 60 \
                    if bk.get('_commence') and hasattr(sig['t_e'], 'timestamp') else None
                edge_pct = (sig['odds'] * (sig.get('pct') or 0) - 1) * 100 \
                    if sig.get('pct') else None
                t['fiabilite_score'], t['fiabilite_detail'] = fs.explique(
                    mag_pct=sig['thr'] * 100, lead_min=lead_min,
                    book_en_retard=bool(edge_pct and edge_pct >= 3))
            except Exception as e:
                t['fiabilite_score'], t['fiabilite_detail'] = None, f'erreur: {e}'
            settle_trade(t, data, result_side)
            trades[t['id']] = t
        summary(trades)
        return

    # --- mode normal : forward ---
    trades = load_journal()
    n_settled = 0
    n_reste_a_regler = 0
    n_abandonnes = 0
    # AJOUTÉ LE 28/08/2026 (audit v4 §Z) : au-delà de 7 jours en
    # CLOSED_NO_RESULT, le match n'aura vraisemblablement JAMAIS de
    # résultat couvert (ni set_results.json ni backtest_tennis.csv) --
    # basculé en ABANDONNED avec la raison, sorti de la boucle de relecture
    # (sinon il tourne indéfiniment pour rien à chaque cycle). Rend aussi
    # visible un taux de perte de résultats qui est une mesure utile en soi.
    SEUIL_ABANDON_JOURS = 7
    aujourdhui = datetime.date.today()
    for t in trades.values():
        if t.get('status') == 'CLOSED_NO_RESULT' and t.get('closed_no_result_depuis'):
            try:
                depuis = datetime.date.fromisoformat(t['closed_no_result_depuis'])
                if (aujourdhui - depuis).days >= SEUIL_ABANDON_JOURS:
                    t['status'] = 'ABANDONNED'
                    t['abandon_raison'] = (f'aucun résultat après '
                                          f'{SEUIL_ABANDON_JOURS}j en CLOSED_NO_RESULT')
                    n_abandonnes += 1
            except ValueError:
                pass
    if n_abandonnes:
        print(f"  {n_abandonnes} trade(s) basculé(s) en ABANDONNED "
              f"(>{SEUIL_ABANDON_JOURS}j sans résultat).")
    # CORRIGÉ LE 27/08/2026 (audit v2 §A) : OPEN *et* CLOSED_NO_RESULT sont
    # retraités à chaque cycle -- avant, un trade sorti de OPEN sans pnl
    # n'était plus jamais revisité. Repli sur `track` (committé, recul plus
    # large) si le match n'est plus dans `data` (fenêtre plus courte).
    for t in trades.values():
        if t.get('status') in ('OPEN', 'CLOSED_NO_RESULT'):
            bk = data.get(t['uid']) or track.get(t['uid'])
            if bk and bk.get('_commence') and bk['_commence'] < now:
                src = data if t['uid'] in data else track
                if settle_trade(t, src, result_side):
                    # CORRIGÉ LE 27/08/2026 (audit v3 §S) : settle_trade()
                    # renvoie True pour SETTLED *et* CLOSED_NO_RESULT --
                    # n_settled comptait donc des trades sans résultat, le
                    # chiffre même qui sert à vérifier que le §A fonctionne.
                    if t.get('status') == 'SETTLED':
                        n_settled += 1
                    else:
                        n_reste_a_regler += 1
            elif not bk:
                n_reste_a_regler += 1
    if n_reste_a_regler:
        print(f"  {n_reste_a_regler} trade(s) toujours sans résultat "
              f"-- relecture au prochain cycle.")
    upcoming = {u: bk for u, bk in data.items()
                if bk.get('_commence') and bk['_commence'] >= now}
    n_open = 0
    # DÉDUPLICATION CANONIQUE : deux conventions d'uid ont coexisté du 11/06 au
    # 09/08/2026 et l'horaire annoncé varie selon la source -> 208 uid désignent
    # un match DÉJÀ suivi. Sans ça, le journal ouvrirait DEUX positions sur le
    # même match, ce qui fausse le n et resserre à tort les IC. Voir match_key.py.
    _idx = mk.build_index([dict(uid=u, home=b.get('_home'), away=b.get('_away'),
                                commence_time=b.get('_commence'),
                                tournament=b.get('_tour'), fixture_id=b.get('_fx'))
                           for u, b in upcoming.items()])
    _vus = set()
    for uid, bk in upcoming.items():
        _k = _idx.key_of(uid)
        if _k in _vus:
            continue
        _vus.add(_k)
        if bk['_commence'] - now < sa.MIN_LEAD * 60:
            continue
        tbk = _truncate(bk, now)               # forward-only : que les points <= now
        if sa.SHARP not in tbk:
            continue
        sig = pick_signal(tbk, softbooks, thr_by_book, entry_at='now')
        if not sig:
            continue
        # CORRIGÉ LE 27/08/2026 (audit §4.4) : _k au lieu de uid brut.
        tid = f"{_k}|{sig['book']}|{int(sig['thr']*100)}"
        if tid in trades:
            continue
        trades[tid] = {'id': tid, 'uid': uid, 'home': bk.get('_home'),
                       'away': bk.get('_away'), 'side': sig['side'], 'book': sig['book'],
                       'palier': int(sig['thr'] * 100), 'entry_odds': round(sig['odds'], 2),
                       'entry_pct_hist': sig['pct'], 'commence': bk['_commence'],
                       'status': 'OPEN'}
        n_open += 1
    save_journal(trades)
    print(f"ouverts ce cycle : {n_open} | denoues ce cycle : {n_settled}")
    summary(trades)


if __name__ == '__main__':
    main()
