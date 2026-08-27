#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validation_report.py — Tableau de validation FORWARD du steam-following.

Lit les journaux paper_trades_*.jsonl et dit, avec des INTERVALLES DE CONFIANCE,
si l'edge est prouve ou pas (et combien de paris il reste a accumuler). C'est le
juge objectif : tant que les bornes basses n'excluent pas 0 (ROI) ou 50% (%CLV+),
l'edge n'est PAS confirme, quel que soit le point estime.

Pour chaque surface (match/set1/set2) et par book :
  - CLV vs cloture : mediane, moyenne, %positif + IC95 (Wilson)
  - ROI reel : moyenne/mise + IC95 | taux de reussite + IC95 (Wilson)
  - verdict CLV / ROI + taille d'echantillon estimee pour la significativite
  - tendance (cumul) premiers vs derniers paris

Env : JOURNALS (glob, def 'paper_trades_*.jsonl'). Aucune dependance externe.
"""
import os, sys, glob, json, math, datetime, random, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov
import match_key as mk


def _hist_sources():
    """Sources historiques a scanner : live (nom fixe) + toutes les partitions
    mensuelles. book_curves.jsonl (monolithique) a ete retire le 14/08/2026
    (140,73 Mo -> GitHub rejetait tout push > 100 Mo) et remplace par
    parts/hist_book_<YYYY-MM>.jsonl -- voir migrate_hist_partitions.py."""
    # ov.hist_partitions() couvre .jsonl ET .jsonl.gz : depuis la compression
    # du 16/08/2026 un glob sur '*.jsonl' seul ne renvoie plus rien, et les
    # scripts sautant les fichiers absents perdaient TOUT l'historique en
    # silence. Les chemins sont renvoyés sans suffixe .gz, ov.open_any() résout.
    return ['book_curves_live.jsonl'] + ov.hist_partitions('book')

JOURNALS = os.environ.get('JOURNALS', 'paper_trades_*.jsonl')
Z = 1.96  # 95%


def wilson(k, n):
    """IC95 de Wilson pour une proportion (k succes sur n)."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (p, max(0, c - h), min(1, c + h))


def mean_ci(xs, bootstrap=True, n_boot=3000, graine=1234567):
    """IC95 de la moyenne.

    CORRIGÉ LE 27/08/2026 (audit §3.4), deux défauts cumulés :
    1. pstdev() (écart-type de POPULATION) sous-estimait l'écart-type
       d'échantillon d'un facteur sqrt(n/(n-1)) -- 3,4 % d'erreur à n=30 ;
       remplacé par stdev() (non biaisé).
    2. L'approximation normale donne des IC trop ÉTROITS quand la
       distribution est asymétrique/bimodale -- exactement le profil d'un
       P&L de pari (-1 ou +cote-1, cote moyenne ~2,9) à n<100, le régime où
       ce dispositif se trouve. Le bootstrap percentile (3000 tirages,
       graine FIXE pour la reproductibilité -- deux lectures du même
       fichier doivent donner le même IC) n'a besoin d'aucune hypothèse de
       forme. Défaut : bootstrap=True. Repli sur l'approximation normale UNIQUEMENT
       si bootstrap=False ou n<8 (le bootstrap n'est pas fiable en dessous).
    """
    n = len(xs)
    if n < 2:
        return (xs[0] if xs else 0.0, None, None, 0.0)
    m = st.mean(xs)
    s = st.stdev(xs)
    if not bootstrap or n < 8:
        half = Z * s / math.sqrt(n)
        return (m, m - half, m + half, s)
    rng = random.Random(graine)
    moyennes = []
    for _ in range(n_boot):
        tirage = [xs[rng.randrange(n)] for _ in range(n)]
        moyennes.append(sum(tirage) / n)
    moyennes.sort()
    lo = moyennes[int(0.025 * n_boot)]
    hi = moyennes[int(0.975 * n_boot) - 1]
    return (m, lo, hi, s)


def n_needed(mean, s):
    """Taille d'echantillon estimee pour que l'IC95 de la moyenne exclue 0.

    ORDRE DE GRANDEUR SEULEMENT (audit §3.4) : calcul de puissance POST-HOC
    à partir de la moyenne OBSERVÉE -- répond « combien faudrait-il si
    l'effet observé était le vrai effet », optimiste par construction quand
    l'effet observé n'est pas significatif. À afficher comme repère, jamais
    comme objectif à atteindre.
    """
    if not mean or s == 0:
        return None
    return int(math.ceil((Z * s / abs(mean)) ** 2))


def report_group(name, trades):
    settled = [t for t in trades if t.get('status') == 'SETTLED']
    opens = [t for t in trades if t.get('status') == 'OPEN']
    print(f"\n{'='*60}\n{name}  —  {len(settled)} denoues | {len(opens)} ouverts")
    if not settled:
        print("  (pas encore de pari denoue — rien a juger)"); return

    clv = [t['clv_book'] for t in settled if 'clv_book' in t]
    # AJOUTÉ LE 27/08/2026 (audit v2 §E) : clv_pin (contre le juste-prix
    # Pinnacle) à côté de clv_book (contre la clôture du book qui a SERVI À
    # SÉLECTIONNER l'entrée -- pick_signal() prend le max sur ~20 books).
    # Si clv_pin s'effondre pendant que clv_book reste haut, c'est la
    # sélection qui gonfle le chiffre, pas un edge. Coût nul, la colonne
    # existe déjà dans chaque trade.
    clv_pin = [t['clv_pin'] for t in settled if 'clv_pin' in t]
    pnl = [t['pnl'] for t in settled if 'pnl' in t]
    won = [1 if t.get('won') else 0 for t in settled if 'won' in t]

    # CLV
    if clv:
        kpos = sum(1 for x in clv if x > 0)
        p, lo, hi = wilson(kpos, len(clv))
        verdict = ("✅ CONFIRME (>50%)" if lo > 0.50 else
                   "⚠ tendance +" if p > 0.50 else "❌ non positif")
        print(f"  CLV vs cloture book : mediane {st.median(clv):+.1f}% | moyenne {st.mean(clv):+.1f}% "
              f"| %positif {p*100:.0f}% (IC95 {lo*100:.0f}-{hi*100:.0f}%)  -> {verdict}")
    if clv_pin:
        kpos = sum(1 for x in clv_pin if x > 0)
        p, lo, hi = wilson(kpos, len(clv_pin))
        print(f"  CLV vs juste-prix Pinnacle : mediane {st.median(clv_pin):+.1f}% | "
              f"moyenne {st.mean(clv_pin):+.1f}% | %positif {p*100:.0f}% "
              f"(IC95 {lo*100:.0f}-{hi*100:.0f}%)")
        if clv and abs(st.median(clv) - st.median(clv_pin)) > 5:
            print(f"  ⚠️ écart >5 pts entre les deux références -- la mesure "
                  f"'vs cloture book' peut être gonflée par la sélection du "
                  f"book (max sur ~20), pas par un edge réel.")
    # ROI
    if pnl:
        m, lo, hi, s = mean_ci(pnl)
        roi = m * 100
        if lo is None:
            print(f"  ROI reel       : {roi:+.1f}%/mise (n trop faible pour IC)")
        else:
            sig = "✅ PROFIT CONFIRME (IC>0)" if lo > 0 else \
                  ("⚠ tendance + (IC inclut 0)" if m > 0 else "❌ non profitable")
            print(f"  ROI reel       : {roi:+.1f}%/mise (IC95 {lo*100:+.1f}..{hi*100:+.1f}%)  -> {sig}")
            if lo <= 0 < m:
                nn = n_needed(m, s)
                if nn:
                    print(f"                   ordre de grandeur (optimiste, non un objectif) : "
                          f"~{nn} paris pour confirmer SI l'effet observé est le vrai effet "
                          f"(actuel {len(pnl)})")
    # win rate
    if won:
        p, lo, hi = wilson(sum(won), len(won))
        print(f"  Reussite       : {p*100:.0f}% (IC95 {lo*100:.0f}-{hi*100:.0f}%, n={len(won)})")
    # par book
    # CORRIGÉ LE 27/08/2026 (audit §3.6) : ce découpage n'est PAS dans la
    # famille Holm et n'importe quel run donnait un « meilleur book » lu à
    # tort comme un résultat (vu en test : leovegas n=2 -> ROI +137,5 %,
    # williamhill n=2 -> -20,5 %). Un book sous n=30 est affiché SANS ses
    # statistiques -- juste son effectif, pour qu'on voie qu'il accumule
    # sans jamais publier un chiffre invendable.
    books = sorted(set(t['book'] for t in settled if t.get('book')))
    if len(books) > 1:
        print("  -- par book (n>=30 seulement pour CLV/ROI -- audit §3.6) --")
        for b in books:
            sub = [t for t in settled if t.get('book') == b]
            if len(sub) < 30:
                print(f"     {b:10} n={len(sub):3d} — sous 30, en accumulation")
                continue
            c = [t['clv_book'] for t in sub if 'clv_book' in t]
            pl = [t['pnl'] for t in sub if 'pnl' in t]
            cm = f"{st.median(c):+.1f}%" if c else "n/a"
            rm = f"{100*st.mean(pl):+.1f}%" if pl else "n/a"
            print(f"     {b:10} n={len(sub):3d} | CLV med {cm} | ROI {rm}")
    # tendance (cumul ROI : 1re moitie vs 2e)
    seq = [t['pnl'] for t in settled if 'pnl' in t]
    if len(seq) >= 6:
        half = len(seq) // 2
        r1, r2 = 100 * st.mean(seq[:half]), 100 * st.mean(seq[half:])
        fleche = "↗ s'ameliore" if r2 > r1 else "↘ se degrade" if r2 < r1 else "→ stable"
        print(f"  Tendance ROI   : 1re moitie {r1:+.1f}% -> 2e moitie {r2:+.1f}%  {fleche}")



# ── Suivi de l'hypothèse OUT-OF-SAMPLE "calibration 2,20-3,50" ────────────────
# Figée le 03/08/2026 après analyse : sur juin-août 2026 (n=925 matchs), les
# côtés clôturant 2,20-3,50 (Pinnacle, devig Shin) gagnaient +5,8 pts de plus
# que leur proba (z≈+2,7), miroir -5,1 sur les favoris 1,20-1,80. Hypothèses
# concurrentes : biais réel vs été à surprises vs artefact de fouille. Cette
# section suit le résidu mois par mois SUR LES NOUVELLES DONNÉES UNIQUEMENT :
# s'il retombe à ~0, c'était du bruit ; s'il persiste, on en reparle.
FREEZE_DATE = '2026-08-04'
FREEZE_DATE_MARGIN = '2026-08-09'
FREEZE_DATE_ROUND  = '2026-08-10'
FREEZE_DATE_BIGMOVE = '2026-08-10'
FREEZE_DATE_EARLYOPEN = '2026-08-13'  # hypothèse 'book ouvert avant Pinnacle' gelée ce jour
FREEZE_DATE_REINFORCE = '2026-08-14'  # hypothèse 'renforcement de l'outsider d'ouverture' gelée ce jour
FREEZE_DATE_REACTIVE = '2026-08-14'  # hypothèse 'book rapide en anomalie > book lent chronique' gelée ce jour
FREEZE_DATE_BETFAIR = '2026-08-16'  # hypothèse 'confirmation Betfair Exchange' gelée ce jour
FREEZE_DATE_MOVEAGE = '2026-08-16'  # hypothèse 'âge du mouvement à ampleur fixée (5%)' gelée ce jour
# Critère PRIMAIRE : CLV du groupe alerté vs groupe témoin.
# REQUALIFIÉ LE 27/08/2026 (audit §3.1) : un gel rétroactif n'est PAS un
# pré-enregistrement -- le 25/08, ce critère avait déjà été vu sur les
# données d'août, donc son statut « hors famille, jugé seul » n'était pas
# défendable. Choix retenu (2 options proposées par l'audit) : requalifié
# EXPLORATOIRE à partir d'aujourd'hui. Le résultat du test de contrôle
# d'août (+11,2 pts) reste une observation descriptive utile, mais n'est
# plus cité comme preuve confirmatoire tant qu'il n'est pas revalidé sur des
# données POSTÉRIEURES à cette date, avec un protocole écrit avant lecture.
# N_CIBLE : gel à un n PRÉ-ENREGISTRÉ, pas au premier franchissement du
# plancher (audit v2 §C, 27/08/2026). Le seuil maison n>=30 est un plancher
# de PUISSANCE MINIMALE, pas une cible -- geler dès qu'il est franchi fige
# le verdict au point où l'échantillon est le plus faible et jette toute
# l'information accumulée ensuite. Constaté sur "ouverture précoce" : gelé
# à n=34 le jour même du gel, alors que n=75 le lendemain matin -- le
# rapport affichait deux pourcentages contradictoires dans le même run
# (97,1 % gelé vs 88,0 % mesuré). 100 est un nombre rond, choisi maintenant,
# identique pour toutes les hypothèses -- pas un choix a posteriori par
# hypothèse (qui serait une resucée du même biais à un cran au-dessus).
N_CIBLE = 100

FREEZE_DATE_PRIMAIRE = '2026-08-27 (requalifié exploratoire, ex-hors-famille)'

def _shin_ph(oh, oa):
    ih, ia = 1/oh, 1/oa; ssum = ih + ia
    if ssum <= 1: return ih/ssum
    z = 0.02
    for _ in range(50):
        ph = (math.sqrt(z*z + 4*(1-z)*ih*ih/ssum) - z) / (2*(1-z))
        pa = (math.sqrt(z*z + 4*(1-z)*ia*ia/ssum) - z) / (2*(1-z))
        t = ph + pa
        if abs(t-1) < 1e-9: break
        z = min(max(z + (t-1), 0.0), 0.3)
    return ph/(ph+pa)

def calibration_watch():
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    try:
        sr = json.load(open('set_results.json', encoding='utf-8'))
    except Exception:
        return
    sides = []
    seen = set()
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: c = json.loads(line)
            except Exception: continue
            if c.get('book') != 'pinnacle' or c.get('uid') in seen: continue
            ct = _d(c.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE): continue   # OUT-OF-SAMPLE only
            res = (sr.get(c['uid']) or {}).get('match')
            if res not in ('home', 'away'): continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1]]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(c.get('home_curve')), _pre(c.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            oh, oa = h[-1][1], a[-1][1]
            if min(oh, oa) <= 1: continue
            seen.add(c['uid'])
            ph = _shin_ph(oh, oa); hw = (res == 'home')
            sides.append((oh, ph, hw)); sides.append((oa, 1-ph, not hw))
    band = [(o, p, w) for o, p, w in sides if 2.20 <= o < 3.50]
    print(f"\n{'='*60}\nSUIVI HYPOTHÈSE — calibration cotes 2,20-3,50 (out-of-sample depuis {FREEZE_DATE})")
    if len(band) < 30:
        print(f"  n={len(band)} côtés — trop tôt pour juger (seuil 30). Référence gelée : +5,8 pts.")
        return
    wr = sum(1 for *_ , w in band if w) / len(band)
    ex = st.mean(p for _, p, _ in band)
    se = (wr*(1-wr)/len(band))**0.5
    verdict = "PERSISTE (à surveiller)" if (wr-ex) - 1.96*se > 0 else ("retombé -> bruit probable" if abs(wr-ex) < se else "indéterminé")
    print(f"  n={len(band)} | réel {100*wr:.1f}% vs attendu Shin {100*ex:.1f}% | résidu {100*(wr-ex):+.1f} pts (±{196*se:.0f}) -> {verdict}")
    print(f"  (référence in-sample juin-août: +5,8 pts ; si le résidu retombe ~0, c'était un été à surprises)")
    return sum(1 for *_, w in band if w), len(band), ex

def hour_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'heure du match'. Constat in-sample
    (07/08/2026, n=729, sur tous les matchs jusqu'à FREEZE_DATE) : le côté
    steamé (celui vers qui Pinnacle se raccourcit) gagne plus souvent quand le
    match est tard dans la journée (Spearman heure~résultat = +0,204, le seul
    facteur testé -ampleur/durée/jour/tournoi- à dépasser le seuil de
    significativité). Hypothèse à un seul test parmi plusieurs -> à confirmer
    strictement out-of-sample avant d'y accorder du crédit (cf. calibration
    2,20-3,50 : même précaution)."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    try:
        sr = json.load(open('set_results.json', encoding='utf-8'))
    except Exception:
        return
    rows, seen = [], set()
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: c = json.loads(line)
            except Exception: continue
            if c.get('book') != 'pinnacle' or c.get('uid') in seen: continue
            ct = _d(c.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE): continue   # OUT-OF-SAMPLE only
            res = (sr.get(c['uid']) or {}).get('match')
            if res not in ('home', 'away'): continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1]]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(c.get('home_curve')), _pre(c.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            oh0, oa0 = h[0][1], a[0][1]
            oh1, oa1 = h[-1][1], a[-1][1]
            if min(oh0, oa0, oh1, oa1) <= 1: continue
            seen.add(c['uid'])
            p0, p1 = _shin_ph(oh0, oa0), _shin_ph(oh1, oa1)
            steam_h = p1 > p0
            won = (res == 'home') if steam_h else (res == 'away')
            pfair = p1 if steam_h else 1 - p1
            rows.append((ct.hour, won, pfair))
    print(f"\n{'='*60}\nSUIVI HYPOTHÈSE — heure du match (out-of-sample depuis {FREEZE_DATE})")
    if len(rows) < 30:
        print(f"  n={len(rows)} matchs — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : rho=+0.20 (heure tardive -> steamé gagne plus).")
        return
    late = [(w, p) for h, w, p in rows if h >= 18]
    early = [(w, p) for h, w, p in rows if h < 18]
    for label, grp in (('tard (>=18h)', late), ('tôt (<18h)', early)):
        if len(grp) < 10:
            print(f"  {label:14} n={len(grp)} (trop petit)"); continue
        wr = sum(1 for w, _ in grp if w) / len(grp)
        ex = st.mean(p for _, p in grp)
        se = (wr*(1-wr)/len(grp))**0.5
        print(f"  {label:14} n={len(grp):3} | réel {100*wr:.1f}% vs attendu {100*ex:.1f}% "
              f"| résidu {100*(wr-ex):+.1f} pts (±{196*se:.0f})")
    print(f"  (in-sample : le steamé gagnait davantage tard -> ici on vérifie si l'écart tard/tôt se confirme)")
    # p-value : « tard » bat-il son attendu Shin ? (proxy unilatéral du
    # différentiel tard/tôt — le test à 2 échantillons viendra si n grossit)
    if len(late) >= 30:
        return (sum(1 for w, _ in late if w), len(late),
                st.mean(p for _, p in late))


def margin_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'variation de marge'. Constat in-sample
    (08/08/2026, n=37 écarts publiés) : quand la marge de l'opérateur signalé
    S'ÉLARGIT entre le signal et la clôture, l'écart s'est refermé dans 100% des
    cas (CLV médian +26,4%, n=7) contre 23% quand la marge reste stable
    (corrélation marge~CLV : r=+0,65).
    Lecture proposée : le book n'élargit pas symétriquement, il rabaisse le côté
    sur lequel il est exposé -> l'élargissement est la signature de la correction
    en cours, pas de la prudence.
    RÉSERVES : n=7 sur la cellule clé, et risque de circularité (la marge finale
    et le CLV sont tous deux mesurés à la clôture). D'où ce suivi strictement
    out-of-sample avant toute exploitation."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    if not os.path.exists(log):
        return
    curves = {}
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'), ct)

    def _val(seq, t):
        v = None
        for tt, o in seq:
            if tt <= t: v = o
            else: break
        return v

    def _marge(h, a, t):
        oh, oa = _val(h, t), _val(a, t)
        return (1/oh + 1/oa) if (oh and oa and oh > 1 and oa > 1) else None

    groups = {'élargie': [], 'stable': [], 'resserrée': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        tsig = _d(m.get('t'))
        if not tsig or tsig < _dtm.datetime.fromisoformat(FREEZE_DATE_MARGIN):
            continue                                   # OUT-OF-SAMPLE only
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            key = (m.get('uid'), book)
            if key not in curves: continue
            h, a, home, ct = curves[key]
            joueur = (m.get('joueur') or '').strip()
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            ms, mc = _marge(h, a, tsig), _marge(h, a, ct)
            if not close or ms is None or mc is None: continue
            clv = (prix/close - 1) * 100
            d = (mc - ms) * 100
            key2 = 'élargie' if d > 0.5 else ('resserrée' if d < -0.5 else 'stable')
            groups[key2].append(clv)

    n_tot = sum(len(v) for v in groups.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — variation de marge (out-of-sample depuis {FREEZE_DATE_MARGIN})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : marge élargie -> 100% refermés (n=7), stable -> 23%.")
        return
    for lab in ('élargie', 'stable', 'resserrée'):
        g = groups[lab]
        if len(g) < 5:
            print(f"  marge {lab:10} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  marge {lab:10} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si 'élargie' ne se distingue plus de 'stable', l'effet était du bruit)")
    g = groups['élargie']
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def round_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'phase de tournoi'. Constat in-sample
    (09/08/2026, n=84 écarts) : le CLV décroît quand le tournoi avance --
    premiers tours (>=16 matchs/jour) +16,0% et 100% refermés, contre
    demies/finale (<4 matchs/jour) +10,2% et 77% refermés. Gradient monotone.
    Lecture : les books tiennent mieux leurs prix sur les phases finales
    (plus de volume, plus d'attention) ; l'inattention du marché -- donc l'edge
    -- se concentre sur les premiers tours.
    Proxy du tour : nombre de matchs du MEME tournoi le MEME jour (32 matchs =
    premiers tours, 2 = demi-finales). Pas de champ 'round' dans l'API."""
    import datetime as _dtm
    from collections import defaultdict as _dd
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    if not os.path.exists(log):
        return
    # date + tournoi de chaque match, depuis les courbes
    meta, per_day = {}, _dd(set)
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            uid = r.get('uid')
            meta[uid] = (r.get('tournament') or '', ct)
            per_day[(r.get('tournament') or '', ct.date())].add(uid)
    curves = {}
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            def _pre(seq):
                pts = [(_d(x[0]), x[1]) for x in (seq or []) if _d(x[0]) and x[1] and x[1] > 1]
                return sorted(q for q in pts if q[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'))
    buckets = {'premiers tours': [], 'milieu': [], 'phases finales': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_ROUND):
            continue                                    # OUT-OF-SAMPLE only
        uid = m.get('uid')
        if uid not in meta: continue
        tour, ct = meta[uid]
        nday = len(per_day[(tour, ct.date())])
        lab = ('premiers tours' if nday >= 16 else
               ('milieu' if nday >= 4 else 'phases finales'))
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            key = (uid, book)
            if key not in curves: continue
            h, a, home = curves[key]
            joueur = (m.get('joueur') or '').strip()
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            if close:
                buckets[lab].append((prix/close - 1) * 100)
    n_tot = sum(len(v) for v in buckets.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — phase de tournoi (out-of-sample depuis {FREEZE_DATE_ROUND})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"premiers tours +16,0% / 100% refermés, phases finales +10,2% / 77%.")
        return
    for lab in ('premiers tours', 'milieu', 'phases finales'):
        g = buckets[lab]
        if len(g) < 5:
            print(f"  {lab:16} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:16} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si le gradient premiers tours > phases finales disparaît, l'effet était du bruit)")
    g = buckets['premiers tours']
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def bigmove_watch():
    """Suivi OUT-OF-SAMPLE : un gros mouvement (>=15pts) SANS retard détecté au
    moment du signal a-t-il quand même de la valeur ? Constat in-sample
    (09/08/2026) : à ampleur égale 3-10pts, un retard détecté fait passer le
    CLV de +3,3% (sans) à +13,5% (avec) -- n=475. Sur les moves >=15pts,
    échantillon insuffisant pour trancher (n=0) : c'est précisément ce que ce
    suivi va combler avec les prochaines semaines de collecte.
    Cas déclencheur : Baez/Brooksby (04/08) -- move ~30pts, aucun retard
    détecté au moment du signal, donc non publiés sur le canal principal."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z','').replace('+00:00',''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    if not os.path.exists(log):
        return
    curves = {}
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            def _pre(seq):
                pts = [(_d(x[0]), x[1]) for x in (seq or []) if _d(x[0]) and x[1] and x[1] > 1]
                return sorted(q for q in pts if q[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a,
                    r.get('home_team') or r.get('home'))
    buckets = {'grand mouvement, sans retard': [], 'grand mouvement, avec retard': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_BIGMOVE):
            continue                                    # OUT-OF-SAMPLE only
        mag_pts = abs(m.get('cote_ref_avant', 1) and
                     (1/m['cote_ref_apres'] - 1/m['cote_ref_avant'])) * 100 if m.get('cote_ref_apres') else 0
        if mag_pts < 15:
            continue                                    # seuil 'gros mouvement'
        lags = m.get('retards') or []
        lab = 'grand mouvement, avec retard' if lags else 'grand mouvement, sans retard'
        joueur = (m.get('joueur') or '').strip()
        uid = m.get('uid')
        # CLV du meilleur prix dispo (même sans retard >=5%, on veut voir ce qu'il y avait)
        best_book, best_price = None, None
        for b, (h, a, home) in curves.items():
            if b[0] != uid: continue
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            pr = seq[-1][1] if b[1] != 'pinnacle' else None   # ignore pinnacle lui-même
        # on utilise directement les retards loggés s'il y en a, sinon on ne peut
        # pas juger le CLV (aucun prix mou capté) -> on compte juste la fréquence
        if lags:
            book, prix = lags[0][0], float(lags[0][1])
            key = (uid, book)
            if key in curves:
                h, a, home = curves[key]
                seq = h if (home and home.strip() == joueur) else a
                if seq and seq[-1][1]:
                    buckets[lab].append((prix / seq[-1][1] - 1) * 100)
        else:
            buckets[lab].append(None)   # pas de prix mou loggé : fréquence seulement

    n_tot = sum(len(v) for v in buckets.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — gros mouvement sans retard détecté (depuis {FREEZE_DATE_BIGMOVE})")
    if n_tot < 15:
        print(f"  n={n_tot} gros mouvements (>=15pts) — trop tôt pour juger (seuil 15). "
              f"Cas déclencheur : Baez/Brooksby, 0 retard détecté malgré ~30pts de move.")
        return
    for lab in buckets:
        g = [x for x in buckets[lab] if x is not None]
        n_all = len(buckets[lab])
        if g:
            pos = 100 * sum(1 for x in g if x > 0) / len(g)
            print(f"  {lab:32} n={n_all:3} (CLV mesurable sur {len(g)}) | "
                  f"CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
        else:
            print(f"  {lab:32} n={n_all:3} (aucun prix mou loggé pour mesurer le CLV)")
    g = [x for vals in buckets.values() for x in vals if x is not None]
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def earlyopen_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'book ouvert avant Pinnacle' (voir
    scripts/early_open_signal.py pour le contexte complet). Constat IN-SAMPLE
    (1042 matchs, formulé le 13/08) : au moment où Pinnacle publie son 1er
    prix, un book déjà ouvert depuis des heures avec un écart >=5% a un CLV
    médian de +8,6% et se referme dans 81% des cas (n=144) -- mais le ROI
    reste non concluant (IC95 [-32%,+4%]).
    Source : early_open_log.jsonl (écrit par early_open_signal.py), qui
    contient déjà le prix signalé + le book -- il suffit de retrouver la
    clôture réelle du même book dans les courbes pour mesurer le CLV réalisé,
    exactement comme canal_clv.py le fait pour les écarts du canal public."""
    import datetime as _dtm
    log = 'early_open_log.jsonl'
    if not os.path.exists(log):
        return
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None

    closes = {}
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            home = r.get('home_team') or r.get('home') or ''
            away = r.get('away_team') or r.get('away') or ''
            for key, name in (('home_curve', home), ('away_curve', away)):
                pts = [(_d(p[0]), p[1]) for p in (r.get(key) or []) if _d(p[0]) and p[1] and p[1] > 1]
                pts = sorted(p for p in pts if p[0] < ct)
                if pts and name:
                    closes[(r.get('uid'), r.get('book'), name)] = pts[-1][1]

    rows = []
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_EARLYOPEN):
            continue                                    # OUT-OF-SAMPLE only
        joueur = m['home'] if m.get('side') == 'home' else m.get('away')
        cl = closes.get((m.get('uid'), m.get('book'), joueur))
        if cl:
            rows.append((m['price'] / cl - 1) * 100)

    print(f"\n{'='*60}")
    print(f"SUIVI HYPOTHÈSE — book ouvert avant Pinnacle (out-of-sample depuis {FREEZE_DATE_EARLYOPEN})")
    if len(rows) < 30:
        print(f"  n={len(rows)} signaux mesurables — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : CLV médian +8,6%, 81% refermés (n=144).")
        return
    pos = 100 * sum(1 for x in rows if x > 0) / len(rows)
    print(f"  n={len(rows)} | CLV médian {st.median(rows):+.1f}% | refermés {pos:.0f}%")
    print("  (si ces chiffres tiennent près des références in-sample, l'hypothèse est confirmée ;")
    print("   s'ils s'effondrent vers 0%/50%, c'était du bruit -- comme la marge et l'heure du match)")
    return sum(1 for x in rows if x > 0), len(rows), 'temoin'


def reinforce_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'renforcement de l'outsider
    d'ouverture'. Question testée : entre l'ouverture et la clôture Pinnacle,
    l'outsider d'ouverture a-t-il tendance à s'enfoncer encore, ou le marché
    corrige-t-il vers lui (l'écart d'ouverture était souvent trop large) ?

    Constat IN-SAMPLE (1040 matchs, formulé le 14/08) : sur les matchs avec
    mouvement net, l'outsider d'ouverture se RENFORCE (le marché corrige vers
    lui) dans 56,1% des cas -- z=-3,74, significatif -- avec un gradient net
    selon l'ampleur de l'écart d'ouverture : 49% (serré) -> 65% (écrasant).
    ATTENTION : ceci porte sur le MOUVEMENT DE PRIX, pas sur le résultat du
    match. Le ROI d'une stratégie 'miser l'outsider écrasant à l'ouverture'
    a été testé et est NON CONCLUANT (n=118, ROI -5,6% IC95[-48%,+37%]) --
    ce suivi ne sert donc qu'à confirmer/infirmer le mouvement de prix,
    jamais une recommandation de mise.

    Contrairement aux autres suivis (qui relisent les alertes publiées),
    celui-ci scanne TOUS les matchs (mouvement Pinnacle open->close),
    puisque la question porte sur le comportement général du marché, pas
    sur des écarts de retard spécifiques."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None

    rows = []
    for src in _hist_sources():
        if not os.path.exists(src): continue
        games = {}
        _recs = []
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct or ct < _dtm.datetime.fromisoformat(FREEZE_DATE_REINFORCE):
                continue                                    # OUT-OF-SAMPLE only
            def pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
            if len(h) < 3 or len(a) < 3: continue
            _recs.append(r)
            g = games.setdefault(r['uid'], {})
            g[r['book']] = {'h': h, 'a': a}
        # DÉDUPLICATION CANONIQUE : deux conventions d'uid ont coexisté du 11/06
        # au 09/08/2026, et l'horaire annoncé bouge selon la source -> 208 uid
        # désignent un match DÉJÀ compté. Sans ça, n surévalué d'environ 10 %
        # sur juin-août et IC trop étroits. Voir match_key.py.
        _idx = mk.build_index(_recs)
        _vus = set()
        for uid, g in games.items():
            _k = _idx.key_of(uid)
            if _k in _vus:
                continue
            _vus.add(_k)
            pin = g.get('pinnacle')
            if not pin: continue
            p_open = _shin_ph(pin['h'][0][1], pin['a'][0][1])
            p_close = _shin_ph(pin['h'][-1][1], pin['a'][-1][1])
            delta = p_close - p_open
            if abs(delta) < 0.005: continue                # quasi-stable, ignoré
            fav_open_home = p_open > 0.5
            reinforced = (delta > 0) if fav_open_home else (delta < 0)
            gap_open = abs(p_open - 0.5) * 200
            rows.append((reinforced, gap_open))

    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — renforcement de l'outsider d'ouverture (depuis {FREEZE_DATE_REINFORCE})")
    if len(rows) < 30:
        print(f"  n={len(rows)} matchs — trop tôt pour juger (seuil 30). "
              f"Référence in-sample : 56,1% global, gradient 49%->65% selon l'écart d'ouverture.")
        return
    n_reinf = sum(1 for r, _ in rows if r)
    pct = 100 * n_reinf / len(rows)
    print(f"  n={len(rows)} | outsider d'ouverture renforcé : {pct:.1f}% (référence 56,1%)")
    for lo, hi, lab in ((0, 15, 'serré'), (15, 35, 'modéré'), (35, 60, 'net'), (60, 200, 'écrasant')):
        g = [r for r, gp in rows if lo <= gp < hi]
        if len(g) >= 15:
            p = 100 * sum(1 for x in g if x) / len(g)
            print(f"    {lab:10} n={len(g):4} | renforcé {p:.0f}%")
    print("  (si le gradient disparaît ou repasse sous 50% partout, c'était du bruit)")
    # CORRIGÉ LE 27/08/2026 (audit v2 §D) : le commentaire du 25/08 disait
    # « hors famille, pas testable contre p0 témoin ni 0,5 » -- confusion
    # entre deux choses différentes. p0_temoin (le taux de base CLV>0) n'a
    # effectivement aucun sens ici, CE N'EST PAS UN CLV. Mais un événement
    # BINAIRE (renforcé / pas renforcé) a bien un null naturel à 50% par
    # symétrie -- exactement comme round ou marge, qui utilisent aussi 0,5
    # sans que ce soit leur "témoin CLV". Sans ce retour, reinforce_watch ne
    # pouvait JAMAIS entrer dans Holm : une réfutation à n=324 (52,2% contre
    # une référence in-sample de 56,1%) n'était jamais formellement actée.
    return n_reinf, len(rows), 0.5


def reactive_watch():
    """Suivi OUT-OF-SAMPLE de l'hypothèse 'book habituellement RAPIDE en
    anomalie > book habituellement LENT chronique'. Question testée : quand
    deux books affichent un écart ≥5%, celui qui est normalement réactif
    (score de fiabilité sous la médiane, voir book_reliability.py) referme-
    t-il mieux son écart que celui qui est structurellement lent ?

    Constat IN-SAMPLE (123 écarts, formulé le 14/08) : CONTRE-INTUITIF -- le
    book habituellement RAPIDE bat systématiquement le book habituellement
    LENT sur les 3 comparaisons testées (CLV +18,7% vs +9,1% à ampleur
    égale ; 92% vs 73% de refermeture). Hypothèse explicative : un book
    rapide qui montre un écart vit une vraie ANOMALIE ponctuelle (son
    système va "rattraper" son comportement habituel) ; un book lent qui
    montre un écart est peut-être juste dans son état normal (marge large
    en continu), donc rien ne le pousse à converger.
    RÉSERVE : direction cohérente sur 3 comparaisons indépendantes (pas une
    coïncidence isolée), mais échantillons individuels modestes (10 à 70).
    book_scores.json étant recalculé chaque nuit sur une fenêtre glissante
    de 45 jours, la médiane de référence évolue avec le temps -- c'est
    voulu, elle doit refléter l'état ACTUEL des books, pas un instantané figé."""
    import datetime as _dtm
    def _d(x):
        try: return _dtm.datetime.fromisoformat(str(x).replace('Z', '').replace('+00:00', ''))
        except Exception: return None
    log = 'canal_public_log.jsonl'
    scores_file = 'book_scores.json'
    if not os.path.exists(log) or not os.path.exists(scores_file):
        return
    try:
        with open(scores_file, encoding='utf-8') as f:
            scores = json.load(f).get('scores', {})
    except Exception:
        return
    reliab = {b: v.get('reliability_score', 0) for b, v in scores.items()}
    if len(reliab) < 4:
        return                                          # trop peu de books scorés pour un split médian utile
    med = st.median(reliab.values())

    curves = {}
    for src in _hist_sources():
        try:
            _f = ov.open_any(src)
        except FileNotFoundError:
            continue
        for line in _f:
            line = line.strip()
            if not line: continue
            try: r = json.loads(line)
            except Exception: continue
            ct = _d(r.get('commence_time'))
            if not ct: continue
            def _pre(seq):
                pts = [(_d(p[0]), p[1]) for p in (seq or []) if _d(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = _pre(r.get('home_curve')), _pre(r.get('away_curve'))
            if h and a:
                curves[(r.get('uid'), r.get('book'))] = (h, a, r.get('home_team') or r.get('home'))

    groups = {'rapide (< médiane)': [], 'lent (>= médiane)': []}
    for line in open(log, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: m = json.loads(line)
        except Exception: continue
        t = _d(m.get('t'))
        if not t or t < _dtm.datetime.fromisoformat(FREEZE_DATE_REACTIVE):
            continue                                    # OUT-OF-SAMPLE only
        joueur = (m.get('joueur') or '').strip()
        for entry in (m.get('retards') or []):
            try: book, prix = entry[0], float(entry[1])
            except Exception: continue
            if book not in reliab:
                continue                                # book pas encore scoré (trop peu d'historique)
            key = (m.get('uid'), book)
            if key not in curves: continue
            h, a, home = curves[key]
            seq = h if (home and home.strip() == joueur) else a
            if not seq: continue
            close = seq[-1][1]
            if not close: continue
            clv = (prix / close - 1) * 100
            lab = 'rapide (< médiane)' if reliab[book] < med else 'lent (>= médiane)'
            groups[lab].append(clv)

    n_tot = sum(len(v) for v in groups.values())
    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — book rapide en anomalie vs book lent chronique (depuis {FREEZE_DATE_REACTIVE})")
    if n_tot < 30:
        print(f"  n={n_tot} écarts — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"rapide +18,7%/92% refermés vs lent +9,1%/73% (à ampleur égale, 3-10pts).")
        return
    for lab in groups:
        g = groups[lab]
        if len(g) < 8:
            print(f"  {lab:20} n={len(g):3} (trop petit)"); continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:20} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si 'rapide' ne bat plus 'lent', l'effet était du bruit malgré la cohérence in-sample)")
    g = [x for lab, vals in groups.items() if lab.startswith('rapide')
         for x in vals]
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def adaptive_threshold_watch():
    """9e hypothèse gelée : le seuil adaptatif par book (best_threshold(),
    steam_alert.py) est-il un vrai signal, ou en partie un artefact de
    sur-ajustement (data snooping) ? Une revue externe du projet (ChatGPT,
    15/08/2026) a identifié ce risque précis : le seuil est choisi en
    cherchant, sur 90 jours glissants, celui qui maximise le %CLV+ observé
    -- puis ce MÊME %CLV+ sert de preuve de performance affichée dans les
    alertes. C'est structurellement circulaire (une forme de data snooping).

    Ce suivi fige la sélection ACTUELLE (frozen_thresholds.json, écrit une
    fois par freeze_thresholds.py -- SANS TOUCHER au système en production,
    qui continue de se ré-optimiser en continu comme avant) et mesure, sur
    des matchs STRICTEMENT POSTÉRIEURS au gel, si le book continue de
    performer au niveau annoncé -- avec le MÊME seuil, jamais re-choisi.
    Si l'OOS s'effondre vers ~50%, c'était en partie du sur-ajustement.
    Si l'OOS tient, la méthode de sélection est validée.

    Réutilise DIRECTEMENT detect()/_at()/load_curves() de steam_alert.py
    (import, pas réimplémentation) pour garantir une fidélité totale à ce
    qui tourne réellement en production."""
    if not os.path.exists('frozen_thresholds.json'):
        print("\n" + "=" * 60)
        print("SUIVI HYPOTHÈSE — seuils adaptatifs gelés")
        print("  frozen_thresholds.json absent -- lancer freeze_thresholds.py une première fois.")
        return
    try:
        import steam_alert as sa
    except Exception as e:
        print(f"  ⚠️ impossible d'importer steam_alert.py : {e}")
        return
    try:
        frozen_all = json.load(open('frozen_thresholds.json', encoding='utf-8'))
    except Exception:
        return
    if not frozen_all:
        return
    _pool_adaptatif = []
    freeze = frozen_all[0]   # premier gel (walk-forward futur : historique complet dans le fichier)
    import datetime as _dtm
    try:
        frozen_at_ts = _dtm.datetime.fromisoformat(freeze['frozen_at']).replace(
            tzinfo=_dtm.timezone.utc).timestamp()
    except Exception as e:
        print(f"  ⚠️ frozen_at illisible : {e}")
        return

    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — seuils adaptatifs gelés (out-of-sample depuis {freeze['frozen_at'][:10]})")

    MARKET_TRACK = {'match': 'book_curves.jsonl', 'set1': 'set1_curves.jsonl', 'set2': 'set2_curves.jsonl'}
    for market, frozen_books in freeze.get('markets', {}).items():
        if not frozen_books:
            continue
        track = sa.load_curves(MARKET_TRACK[market])
        oos_matches = {u: bk for u, bk in track.items()
                      if bk.get('_commence') and bk['_commence'] >= frozen_at_ts}
        print(f"\n  [{market}] {len(oos_matches)} matchs strictement postérieurs au gel")
        for sb, info in sorted(frozen_books.items()):
            thr = info['threshold']
            clvs = []
            for uid, bk in oos_matches.items():
                if sa.SHARP not in bk or sb not in bk:
                    continue
                d = sa.detect(bk[sa.SHARP], thr)
                if not d:
                    continue
                t_e, side = d
                commence = bk.get('_commence')
                if commence is not None and (commence - t_e) / 60.0 < sa.MIN_LEAD:
                    continue
                ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
                entry = sa._at(ser, t_e)
                if not entry or entry <= 1 or not ser:
                    continue
                close = ser[-1][1]
                if close and close > 1:
                    clvs.append((entry / close - 1) * 100)
            if len(clvs) < 10:
                print(f"    {sb:14} seuil {thr*100:.0f}pt | OOS n={len(clvs):2} — trop tôt "
                      f"(réf in-sample {info['in_sample_pct']}%, n={info['in_sample_n']})")
                continue
            oos_pct = round(100 * sum(1 for x in clvs if x > 0) / len(clvs))
            _pool_adaptatif.extend(clvs)
            oos_med = round(st.median(clvs), 1)
            drift = oos_pct - info['in_sample_pct']
            flag = (" ⚠ dégradation nette (sur-ajustement probable)" if drift <= -15
                    else (" ✅ tient" if drift >= -5 else " (à surveiller)"))
            print(f"    {sb:14} seuil {thr*100:.0f}pt | in-sample {info['in_sample_pct']}% "
                  f"(n={info['in_sample_n']}) -> OOS {oos_pct}% (n={len(clvs)}, méd {oos_med:+.1f}%){flag}")
    print("\n  (si la plupart des books s'effondrent vers ~50%, la sélection de seuil était")
    print("   en partie du sur-ajustement -- si ça tient, la méthode est validée)")
    if _pool_adaptatif:
        return (sum(1 for x in _pool_adaptatif if x > 0),
                len(_pool_adaptatif), 'temoin')


def betfair_confirm_watch():
    """10e hypothèse gelée : quand Betfair Exchange CONFIRME le mouvement
    Pinnacle (même sens, amplitude non-négligeable, sur la même fenêtre),
    l'écart détecté sur un book mou referme-t-il mieux qu'quand Betfair ne
    confirme pas ?

    Origine : axe n°4 d'une revue externe du projet (ChatGPT, 15/08/2026),
    qui proposait de distinguer "steam confirmé" / "steam suspect" /
    "mouvement épuisé" via plusieurs critères (dont la confirmation par
    Betfair). Testé isolément (les autres critères de la revue -- âge du
    mouvement, best vs médiane soft -- n'ont rien donné ou étaient
    contradictoires sur nos données).

    Constat IN-SAMPLE (32 signaux, formulé le 16/08/2026) : Betfair confirme
    -> CLV médian +11,4%, 95% refermés (n=22) ; ne confirme pas -> CLV
    médian +6,8%, 90% refermés (n=10). Cohérent sur les deux mesures à la
    fois (contrairement au test best-vs-médiane), mais IC95 des taux de
    refermeture qui se chevauchent largement [78-99%] vs [60-98%] --
    encore possiblement du bruit, à confirmer sur davantage de données.

    Réutilise DIRECTEMENT detect()/_fair()/_at() de steam_alert.py (import,
    pas réimplémentation) pour garantir la fidélité à la méthode déjà
    validée ailleurs dans ce fichier (adaptive_threshold_watch)."""
    try:
        import steam_alert as sa
    except Exception as e:
        print(f"  ⚠️ impossible d'importer steam_alert.py : {e}")
        return
    import datetime as _dtm

    def _ts(x):
        """Timestamp FLOTTANT (pas un objet datetime) -- convention de
        steam_alert.py (_dt() y renvoie .timestamp()). detect()/_fair()/_at()
        exigent ce format ; les mélanger avec des objets datetime casse les
        comparaisons/soustractions silencieusement ou avec une TypeError."""
        try:
            return _dtm.datetime.fromisoformat(
                str(x).replace('Z', '').replace('+00:00', '')).timestamp()
        except Exception:
            return None

    def val_at(seq, t):
        v = None
        for tt, o in seq:
            if tt <= t:
                v = o
            else:
                break
        return v

    freeze_ts = _ts(FREEZE_DATE_BETFAIR)
    games = {}
    _recs = []
    for src in _hist_sources():
        if not os.path.exists(src):
            continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _ts(r.get('commence_time'))
            if not ct or ct < freeze_ts:
                continue                                    # OUT-OF-SAMPLE only
            def pre(seq):
                pts = [(_ts(p[0]), p[1]) for p in (seq or []) if _ts(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
            if h and a:
                _recs.append(r)
                games.setdefault(r['uid'], {'_ct': ct})[r['book']] = {'h': h, 'a': a}

    rows = []
    # DÉDUPLICATION CANONIQUE : deux conventions d'uid ont coexisté du 11/06
    # au 09/08/2026, et l'horaire annoncé bouge selon la source -> 208 uid
    # désignent un match DÉJÀ compté. Sans ça, n surévalué d'environ 10 %
    # sur juin-août et IC trop étroits. Voir match_key.py.
    _idx = mk.build_index(_recs)
    _vus = set()
    for uid, bk in games.items():
        _k = _idx.key_of(uid)
        if _k in _vus:
            continue
        _vus.add(_k)
        if sa.SHARP not in bk or 'betfair-ex' not in bk:
            continue
        pin, bf = bk[sa.SHARP], bk['betfair-ex']
        commence = bk['_ct']
        d = sa.detect(pin, 0.03)
        if not d:
            continue
        t_e, side = d
        if (commence - t_e) / 60.0 < sa.MIN_LEAD:
            continue
        times = sorted(set(t for t, _ in pin['h']))
        f0, fe = sa._fair(pin, times[0]), sa._fair(pin, t_e)
        bf0, bfe = sa._fair(bf, times[0]), sa._fair(bf, t_e)
        if None in (f0, fe, bf0, bfe):
            continue
        pin_move, bf_move = fe - f0, bfe - bf0
        confirms = (pin_move * bf_move > 0) and abs(bf_move) >= 0.01

        fair = fe if side == 'home' else 1 - fe
        fair_odds = 1 / fair
        best = None
        for b, sb in bk.items():
            if b.startswith('_') or b in ('pinnacle', 'betfair-ex'):
                continue
            ser = sb['h'] if side == 'home' else sb['a']
            entry = val_at(ser, t_e)
            if not entry or entry <= 1 or not ser:
                continue
            close = ser[-1][1]
            if not close or close <= 1:
                continue
            gap = (entry / fair_odds - 1) * 100
            if gap >= 5 and (best is None or gap > best[0]):
                best = (gap, entry, close)
        if not best:
            continue
        clv = (best[1] / best[2] - 1) * 100
        rows.append((confirms, clv))

    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — confirmation Betfair Exchange (depuis {FREEZE_DATE_BETFAIR})")
    if len(rows) < 30:
        print(f"  n={len(rows)} signaux — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"confirme +11,4%/95% refermés (n=22) vs ne confirme pas +6,8%/90% (n=10).")
        return
    for label, cond in (('Betfair confirme', lambda r: r[0]), ('Betfair ne confirme pas', lambda r: not r[0])):
        g = [r[1] for r in rows if cond(r)]
        if len(g) < 8:
            print(f"  {label:24} n={len(g):3} (trop petit)")
            continue
        pos = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {label:24} n={len(g):3} | CLV médian {st.median(g):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si 'confirme' ne bat plus 'ne confirme pas', c'était du bruit malgré la cohérence in-sample)")
    g = [r[1] for r in rows if r[0]]
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def move_age_watch():
    """11e hypothèse gelée : à AMPLITUDE FIXÉE (~5%, seuil de détection), le
    CLV varie-t-il selon l'ÂGE du mouvement (temps écoulé depuis son tout
    premier frémissement, pas depuis la détection elle-même) ?

    Origine : axe n°2 d'une revue externe du projet (ChatGPT, 15/08/2026).
    Un premier test (14/08, toutes amplitudes mélangées) n'avait montré
    AUCUN signal d'âge -- mais en FIXANT l'amplitude à 5% précisément
    (16/08), un vrai écart apparaît sur les deux extrêmes les mieux
    peuplés : mélanger les amplitudes masquait probablement un effet réel
    propre à ce palier.

    Constat IN-SAMPLE (221 signaux à ~5%, formulé le 16/08/2026) :
      <5min  (n=92) : CLV médian +11,4%, 88% refermés [80-93]
      >2h    (n=73) : CLV médian  +6,4%, 81% refermés [70-88]
    Les paliers intermédiaires (5-15min, 30-60min, n=10-19) ne suivent PAS
    un escalier propre -- trop peu de données pour leur faire confiance
    individuellement, seuls les deux extrêmes sont considérés fiables.

    Réutilise DIRECTEMENT detect()/_fair()/_at() de steam_alert.py (import,
    pas réimplémentation)."""
    try:
        import steam_alert as sa
    except Exception as e:
        print(f"  ⚠️ impossible d'importer steam_alert.py : {e}")
        return
    import datetime as _dtm

    def _ts(x):
        try:
            return _dtm.datetime.fromisoformat(
                str(x).replace('Z', '').replace('+00:00', '')).timestamp()
        except Exception:
            return None

    def val_at(seq, t):
        v = None
        for tt, o in seq:
            if tt <= t:
                v = o
            else:
                break
        return v

    AGE_BUCKETS = [(0, 5, '<5min'), (5, 15, '5-15min'), (15, 30, '15-30min'),
                   (30, 60, '30-60min'), (60, 120, '1-2h'), (120, 999999, '>2h')]

    def age_bucket(v):
        for lo, hi, lab in AGE_BUCKETS:
            if lo <= v < hi:
                return lab
        return None

    freeze_ts = _ts(FREEZE_DATE_MOVEAGE)
    games = {}
    _recs = []
    for src in _hist_sources():
        if not os.path.exists(src):
            continue
        for line in open(src, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _ts(r.get('commence_time'))
            if not ct or ct < freeze_ts:
                continue                                    # OUT-OF-SAMPLE only
            def pre(seq):
                pts = [(_ts(p[0]), p[1]) for p in (seq or []) if _ts(p[0]) and p[1] and p[1] > 1]
                return sorted(x for x in pts if x[0] < ct)
            h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
            if h and a:
                _recs.append(r)
                games.setdefault(r['uid'], {'_ct': ct})[r['book']] = {'h': h, 'a': a}

    rows = []
    # DÉDUPLICATION CANONIQUE : deux conventions d'uid ont coexisté du 11/06
    # au 09/08/2026, et l'horaire annoncé bouge selon la source -> 208 uid
    # désignent un match DÉJÀ compté. Sans ça, n surévalué d'environ 10 %
    # sur juin-août et IC trop étroits. Voir match_key.py.
    _idx = mk.build_index(_recs)
    _vus = set()
    for uid, bk in games.items():
        _k = _idx.key_of(uid)
        if _k in _vus:
            continue
        _vus.add(_k)
        if sa.SHARP not in bk:
            continue
        pin = bk[sa.SHARP]
        commence = bk['_ct']
        d5 = sa.detect(pin, 0.05)
        if not d5:
            continue
        t_5, side = d5
        if (commence - t_5) / 60.0 < sa.MIN_LEAD:
            continue
        d_start = sa.detect(pin, 0.005)
        if not d_start:
            continue
        t_start, side_start = d_start
        if side_start != side:
            continue
        age_min = (t_5 - t_start) / 60.0
        if age_min < 0:
            continue
        ab = age_bucket(age_min)
        if not ab:
            continue
        fe = sa._fair(pin, t_5)
        if fe is None:
            continue
        fair = fe if side == 'home' else 1 - fe
        fair_odds = 1 / fair
        best = None
        for b, sb in bk.items():
            if b.startswith('_') or b == sa.SHARP:
                continue
            ser = sb['h'] if side == 'home' else sb['a']
            entry = val_at(ser, t_5)
            if not entry or entry <= 1 or not ser:
                continue
            close = ser[-1][1]
            if not close or close <= 1:
                continue
            gap = (entry / fair_odds - 1) * 100
            if best is None or gap > best[0]:
                best = (gap, entry, close)
        if not best or best[0] < 0:
            continue
        clv = (best[1] / best[2] - 1) * 100
        rows.append((ab, clv))

    print("\n" + "=" * 60)
    print(f"SUIVI HYPOTHÈSE — âge du mouvement à amplitude fixée ~5% (depuis {FREEZE_DATE_MOVEAGE})")
    if len(rows) < 30:
        print(f"  n={len(rows)} signaux — trop tôt pour juger (seuil 30). Référence in-sample : "
              f"<5min +11,4%/88% refermés (n=92) vs >2h +6,4%/81% (n=73).")
        return
    grid = {}
    for ab, clv in rows:
        grid.setdefault(ab, []).append(clv)
    for _, _, lab in AGE_BUCKETS:
        vals = grid.get(lab, [])
        if len(vals) < 8:
            print(f"  {lab:10} n={len(vals):3} (trop petit)")
            continue
        pos = 100 * sum(1 for x in vals if x > 0) / len(vals)
        print(f"  {lab:10} n={len(vals):3} | CLV médian {st.median(vals):+6.1f}% | refermés {pos:3.0f}%")
    print("  (si <5min ne bat plus >2h, c'était du bruit malgré l'écart in-sample)")
    g = grid.get(AGE_BUCKETS[0][2], [])
    if g:
        return sum(1 for x in g if x > 0), len(g), 'temoin'


def _p_binomial_unilateral(k, n, p0=0.5):
    """P(X >= k) sous H0 p=p0 — binomial exact unilatéral, sans dépendance.

    p0=0,5 : test de signe (« refermés » vs pile ou face). p0 quelconque :
    nécessaire pour calibration/heure, où l'hypothèse nulle est le taux
    ATTENDU PAR SHIN — tester ces suivis contre 50 % serait faux.
    Fonction pure, couverte par tests/test_pure_functions.py."""
    if n <= 0:
        return 1.0
    if not 0 < p0 < 1:
        return 1.0 if k > n * p0 else 0.0
    # Log-espace : math.comb(n, i) déborde le float dès n ~ 1030
    # (OverflowError constaté sur le renforcement outsider, n=1287).
    lp, l1p = math.log(p0), math.log(1 - p0)
    lg = math.lgamma
    total = 0.0
    for i in range(max(k, 0), n + 1):
        total += math.exp(lg(n + 1) - lg(i + 1) - lg(n - i + 1)
                          + i * lp + (n - i) * l1p)
    return min(total, 1.0)


_P0_TEMOIN_CACHE = None


def p0_temoin(chemin='moves_detail_hist.csv'):
    """Taux de base de CLV>0 sur la POPULATION des moves détectés.

    (audit du 25/08 soir) : « sans edge, 50 % de CLV>0 » est faux — la
    dérive asymétrique des outsiders déplace le point d'équilibre, et le
    dispositif POSSÈDE son étalon : les 800+ moves de moves_detail_hist.
    Chaque hypothèse sélectionne un sous-groupe de cette activité ; son
    H0 honnête est « pas mieux que le move moyen », pas « pas mieux
    qu'une pièce ». Mesuré le 25/08 : 593/821 = 0,722 — contre 0,5 en
    dur, les verdicts changent du tout au tout.
    Réserve assumée : les sous-groupes issus d'autres détecteurs
    (ouverture précoce, seuils par book) sont comparés au même étalon —
    l'hypothèse de comparabilité est « tout ceci est du steam-following ».
    Renvoie (p0, n) ; repli (0.5, 0) SIGNALÉ si le fichier manque.
    """
    global _P0_TEMOIN_CACHE
    if _P0_TEMOIN_CACHE is not None:
        return _P0_TEMOIN_CACHE
    import csv
    vals = []
    try:
        for r in csv.DictReader(open(chemin, encoding='utf-8')):
            try:
                vals.append(float(r['clv_book_pct']))
            except (TypeError, ValueError, KeyError):
                continue
    except OSError:
        pass
    if len(vals) < 100:
        print(f"⚠️ p0_temoin : {chemin} absent ou trop maigre "
              f"({len(vals)} CLV) — repli p0=0,5, verdicts à lire avec "
              f"prudence.")
        _P0_TEMOIN_CACHE = (0.5, 0)
    else:
        pos = sum(1 for v in vals if v > 0)
        _P0_TEMOIN_CACHE = (pos / len(vals), len(vals))
    return _P0_TEMOIN_CACHE


def _p_deux_proportions(k1, n1, k2, n2):
    """Test à DEUX échantillons (Wald, variance groupée), unilatéral :
    H1 = la proportion 1 (sous-groupe) DÉPASSE la proportion 2 (référence).

    AJOUTÉ LE 27/08/2026 (audit §3.2) : p0_temoin() traite le taux de base
    comme une CONSTANTE connue, alors que c'est une estimation à erreur-type
    ~1,5 pt (n=891). Un test à un échantillon (binomial vs p0 fixe) sous-
    estime l'incertitude -- à n=30-60 pour le sous-groupe, ça peut faire
    basculer un verdict. Ce test à deux échantillons propage l'incertitude
    des DEUX proportions. Repli sur une approximation normale (pas de
    scipy) ; n1,n2 >= 30 dans tous les cas d'usage ici, la normale tient.
    RÉSERVE ASSUMÉE (non résolue ce soir) : la référence (k2,n2) INCLUT le
    sous-groupe testé -- l'auto-référencement partiel décrit par l'audit
    reste présent. L'exclusion complète demanderait de retracer, pour
    CHAQUE hypothèse, quelles lignes de moves_detail_hist.csv composent son
    sous-groupe -- pas toutes ne sourcent de ce fichier. Amélioration
    future, documentée plutôt que cachée.
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    if p_pool in (0, 1):
        # CORRIGÉ LE 27/08/2026 (audit v2 §K) : les deux branches valaient
        # 1.0, ternaire mort. p_pool ne vaut 0 ou 1 QUE si k1=n1=k2=n2 (100%
        # des deux côtés) ou k1=k2=0 (0% des deux côtés) -- p1=p2 dans les
        # deux cas, donc p=1,0 est le résultat correct, pas un repli faute
        # de mieux.
        return 1.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (p1 - p2) / se
    # queue supérieure de la normale standard, sans scipy (erf de math)
    return 0.5 * math.erfc(z / math.sqrt(2))


def holm(pvals, alpha=0.05):
    """Correction de Holm (step-down). pvals -> liste de booléens alignée :
    True = rejet de H0 en contrôlant le risque global à alpha.

    Principe : on trie les p-values ; la plus petite doit battre alpha/m, la
    suivante alpha/(m-1), etc. Dès qu'une échoue, toutes les suivantes
    échouent (procédure séquentielle). Moins brutal que Bonferroni, aucune
    hypothèse d'indépendance requise — valide même sur nos tests corrélés.
    Fonction pure, couverte par tests/test_pure_functions.py."""
    m = len(pvals)
    if m == 0:
        return []
    ordre = sorted(range(m), key=lambda i: pvals[i])
    rejets = [False] * m
    for rang, i in enumerate(ordre):
        if pvals[i] <= alpha / (m - rang):
            rejets[i] = True
        else:
            break                      # step-down : le premier échec arrête tout
    return rejets




def bilan_tests_multiples(resultats):
    """Le filtre opérationnel : comptages OOS -> p-values -> Holm.

    resultats = [(nom, gel, (k, n, p0) | None)] ; p0 vaut un nombre
    (attendu Shin) ou 'temoin' (taux de base CLV>0 de la population de
    moves). Plancher n>=30 EN AMONT de la famille : la règle maison est
    pré-enregistrée et indépendante du résultat, donc l'exclure avant
    Holm est légitime — une hypothèse à n=6 ne peut jamais rejeter mais
    durcirait le seuil de toutes les autres.
    """
    m = len(resultats)
    p0t, nt = p0_temoin()
    print(f"\n{'=' * 60}")
    print(f"BILAN TESTS MULTIPLES — {m} hypothèses gelées suivies "
          f"(Holm, alpha=0,05, plancher n>=30)")
    print(f"  p0 témoin = {100 * p0t:.1f}% de CLV>0 sur la population "
          f"de moves (n={nt}) — l'étalon des hypothèses CLV.")
    print(f"  Critère PRIMAIRE (EXPLORATOIRE depuis le 27/08, requalifié — "
          f"gel {FREEZE_DATE_PRIMAIRE}) : le +11,2 pts d'août est descriptif, "
          f"non confirmatoire tant qu'il n'est pas revalidé sur données "
          f"postérieures à ce gel.")
    # LECTURE UNIQUE PAR HYPOTHÈSE (audit §3.3), CORRIGÉ LE 27/08/2026
    # (audit v2 §C) : geler à N_CIBLE (n pré-enregistré), pas au premier
    # n>=30 -- voir la constante N_CIBLE pour le raisonnement complet.
    GELES_FICHIER = 'verdicts_geles.json'
    try:
        geles = json.load(open(GELES_FICHIER, encoding='utf-8'))
    except (OSError, ValueError):
        geles = {}
    resolus = []
    for idx, (nom, gel, r) in enumerate(resultats):
        if not r:
            resolus.append((idx, None))
            continue
        k, n, p0 = r
        resolus.append((idx, (k, n, p0t if p0 == 'temoin' else p0, nt if p0 == 'temoin' else None)))
    a_geler = []
    for idx, r in resolus:
        nom = resultats[idx][0]
        if nom in geles:
            continue                              # déjà gelé, jamais recalculé
        if r is not None and r[1] >= N_CIBLE:
            a_geler.append((idx, r))
    for idx, (k, n, p0, n_ref) in a_geler:
        nom = resultats[idx][0]
        if n_ref is not None:
            k_ref = round(p0 * n_ref)
            p = _p_deux_proportions(k, n, k_ref, n_ref)
        else:
            p = _p_binomial_unilateral(k, n, p0)
        geles[nom] = {'k': k, 'n': n, 'p0': p0, 'p_value': p,
                     'date_lecture': datetime.date.today().isoformat()}
    if a_geler:
        json.dump(geles, open(GELES_FICHIER, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    # Holm s'applique à TOUTES les hypothèses gelées à ce jour (anciennes
    # et nouvelles) -- la famille grandit au fil des gels, jamais un même
    # verdict individuel n'est recalculé.
    noms_geles = [nom for nom, _, _ in resultats if nom in geles]
    pvals = [geles[nom]['p_value'] for nom in noms_geles]
    rejets = holm(pvals, alpha=0.05)
    verdicts = dict(zip(noms_geles, rejets))
    for idx, (nom, gel, r) in enumerate(resultats):
        if nom in geles:
            g = geles[nom]
            k, n, p0, p = g['k'], g['n'], g['p0'], g['p_value']
            rej = verdicts[nom]
            if rej:
                v = 'REJETTE H0 sous Holm ✅'
            elif k / n < p0:
                v = 'ne rejette pas H0 (SOUS le taux de base témoin ⚠️)'
            else:
                v = 'ne rejette pas H0'
            print(f"  {nom:24} gel {str(gel)[:10]} | lu le "
                  f"{g['date_lecture']} (verrouillé) | {k}/{n} vs "
                  f"p0={p0:.3f} | p={p:.4f} -> {v}")
        elif r is not None and r[1] < 30:
            k, n = r[0], r[1]
            print(f"  {nom:24} gel {str(gel)[:10]} | {k}/{n} — n<30 : "
                  f"suivi, HORS famille (seuil maison pré-enregistré)")
        elif r is not None and r[1] < N_CIBLE:
            # AJOUTÉ LE 27/08/2026 (audit v2 §C) : entre le plancher (30) et
            # la cible de gel (N_CIBLE), la puissance existe déjà mais la
            # lecture N'EST PAS ENCORE ACTÉE -- distinct du cas n<30
            # (aucune conclusion possible) et du cas gelé (verdict figé).
            k, n = r[0], r[1]
            print(f"  {nom:24} gel {str(gel)[:10]} | {k}/{n} — en "
                  f"accumulation (cible n>={N_CIBLE}, {N_CIBLE - n} restants "
                  f"avant lecture)")
        else:
            print(f"  {nom:24} gel {str(gel)[:10]} | — pas de comptage "
                  f"OOS (n insuffisant, hors périmètre binomial, ou trop tôt)")
    n_rej = sum(1 for v in verdicts.values() if v)
    print(f"  Famille : {len(pvals)} verdict(s) gelé(s) au total, {n_rej} "
          f"rejet(s) au risque global 5 % (chaque verdict lu UNE SEULE FOIS, "
          f"à sa qualification n>={N_CIBLE} pré-enregistrée).")
    print('  Verdict CONFIRMATOIRE = hypothèse gelée AVANT ses données '
          'de test, jugée out-of-sample puis passée dans holm().')
    print('  Tout angle exploré in-sample reste EXPLORATOIRE : il peut '
          'motiver un nouveau gel daté, jamais justifier une décision.')
    print('  Un « survivant » in-sample non répliqué out-of-sample sous '
          'ce filtre doit être lu comme du bruit.')

# Une SEULE source de vérité (audit du 25/08 soir, consolidée le soir
# même : la première version vivait dans main() pendant que l'ancienne
# liste parallèle servait encore l'en-tête — la duplication supprimée
# était revenue par la fenêtre). Nom, date de gel et fonction voyagent
# ENSEMBLE, au niveau module, lus par l'en-tête ET par la boucle.
HYPOTHESES = [
    ('calibration 2,20-3,50', FREEZE_DATE,           calibration_watch),
    ('heure du match',        FREEZE_DATE,           hour_watch),
    ('variation de marge',    FREEZE_DATE_MARGIN,    margin_watch),
    ('round',                 FREEZE_DATE_ROUND,     round_watch),
    ('gros move',             FREEZE_DATE_BIGMOVE,   bigmove_watch),
    ('ouverture précoce',     FREEZE_DATE_EARLYOPEN, earlyopen_watch),
    ('renforcement outsider', FREEZE_DATE_REINFORCE, reinforce_watch),
    ('book réactif',          FREEZE_DATE_REACTIVE,  reactive_watch),
    ('seuil adaptatif',       FREEZE_DATE,           adaptive_threshold_watch),
    ('confirmation Betfair',  FREEZE_DATE_BETFAIR,   betfair_confirm_watch),
    ('âge du mouvement',      FREEZE_DATE_MOVEAGE,   move_age_watch),
]


def rappel_value_clv(fichier='value_clv_report.json'):
    """AJOUTÉ LE 27/08/2026 (audit §3.7) : une réfutation propre mérite
    autant de visibilité qu'un signal qui survit -- sinon le rapport ne
    montre que ce qui a marché, ce qui est exactement le biais que tout ce
    dispositif existe pour combattre. Le détecteur de « value » sélectionne
    des paris dont le CLV est MOINS bon que celui des matchs non
    sélectionnés (corrélation score/CLV légèrement négative, n=374)."""
    if not os.path.exists(fichier):
        return
    try:
        d = json.load(open(fichier, encoding='utf-8'))
    except (OSError, ValueError):
        return
    print(f"\n{'=' * 60}\nRÉFUTATION (à garder visible, pas seulement les signaux qui "
          f"survivent) — détecteur de value")
    print(f"  candidats     : CLV moyen {d.get('candidats_clv_moyen', 0):+.2f}% | "
          f"%positif {d.get('candidats_clv_pct_positif', 0):.1f}% "
          f"(n={d.get('n_candidats_avec_clv', '?')})")
    print(f"  non-candidats : CLV moyen {d.get('non_candidats_clv_moyen', 0):+.2f}%")
    print(f"  corr(score, CLV) = {d.get('corr_score_clv', 0):+.3f}")
    print("  Le détecteur sélectionne des paris au CLV MOINS bon que le "
          "tout-venant -- réfutation propre, à ne pas retester sous une "
          "autre forme sans nouveau protocole daté.")


def report_canal(fichier='paper_trades_canal.jsonl',
                 clv_fichier='canal_clv_detail.csv'):
    """Lecteur DÉDIÉ pour le journal canal (audit §1.2, 27/08/2026).

    Schéma différent du journal forward : statut='REGLE' (pas status=
    'SETTLED'), gagne (pas won), pas de clv_book natif -- le CLV est joint
    depuis canal_clv_detail.csv (indexé uid+book) plutôt que reconstruit
    approximativement. C'est le SEUL journal avec de vrais résultats ET,
    avant ce correctif, le SEUL sans CLV dans le verdict -- la règle « le
    CLV est la métrique de validation » ne s'appliquait nulle part où il y
    avait de quoi la vérifier.
    """
    if not os.path.exists(fichier):
        return
    trades = [json.loads(l) for l in open(fichier, encoding='utf-8') if l.strip()]
    regles = [t for t in trades if t.get('statut') == 'REGLE']
    ouverts = [t for t in trades if t.get('statut') != 'REGLE']
    print(f"\n{'=' * 60}\nJOURNAL CANAL (produit réellement publié aux abonnés) "
          f"— {len(regles)} réglés | {len(ouverts)} ouverts")
    if not regles:
        print("  (pas encore de pari réglé)")
        return
    clv_par_cle = {}
    if os.path.exists(clv_fichier):
        import csv
        for r in csv.DictReader(open(clv_fichier, encoding='utf-8')):
            try:
                clv_par_cle[(r['uid'], r['book'])] = float(r['clv'])
            except (KeyError, ValueError):
                continue
    clv = [clv_par_cle[(t['uid'], t['book'])] for t in regles
           if (t['uid'], t['book']) in clv_par_cle]
    pnl = [t['pnl'] for t in regles if 'pnl' in t]
    won = [1 if t.get('gagne') else 0 for t in regles]
    if clv:
        pos = sum(1 for x in clv if x > 0)
        p, lo, hi = wilson(pos, len(clv))
        print(f"  CLV (joint via {clv_fichier}) : n={len(clv)} | moyen "
              f"{st.mean(clv):+.2f}% | médian {st.median(clv):+.2f}% | "
              f"positif {100 * p:.0f}% (IC95 {100 * lo:.0f}-{100 * hi:.0f}%)")
    else:
        print(f"  ⚠️ aucun CLV apparié via {clv_fichier} (uid+book absents "
              f"du fichier de calibration)")
    if pnl:
        n = len(pnl)
        # CORRIGÉ LE 27/08/2026 (audit v2 §F) : cette fonction recalculait
        # son IC à la main (approximation normale) alors que mean_ci() a été
        # réécrite en bootstrap précisément pour ce cas -- un P&L de pari
        # bimodal/asymétrique à cote moyenne ~2,9, sur LE journal qui a de
        # vrais résultats. L'ancien calcul manuel n'était pas faux (le x100
        # était correct), juste redondant avec un outil déjà construit pour
        # être plus fiable ici.
        m, lo, hi, _sd = mean_ci(pnl)
        roi, ic_lo, ic_hi = 100 * m, 100 * lo, 100 * hi
        wr = 100 * sum(won) / len(won) if won else 0
        print(f"  ROI RÉEL : n={n} | {roi:+.1f}% [IC95 {ic_lo:+.1f}%, "
              f"{ic_hi:+.1f}%] | {wr:.0f}% gagnés")


def main():
    files = sorted(glob.glob(JOURNALS))
    if not files:
        print(f"Aucun journal trouve ({JOURNALS}). Le pipeline n'a pas encore ouvert/denoue de pari.")
        return
    print("TABLEAU DE VALIDATION FORWARD — steam-following")
    print(f"{len(HYPOTHESES)} hypothèses gelées suivies — verdicts individuels à lire à travers le filtre Holm-Bonferroni (bilan en fin de rapport).")
    print("Regle : un edge n'est CONFIRME que si la borne basse de l'IC95 exclut 0 (ROI) / 50% (CLV+).")
    for f in files:
        # CORRIGÉ LE 27/08/2026 (audit §1.2) : paper_trades_canal.jsonl a un
        # schéma différent (statut/gagne vs status/won) — report_group() le
        # filtrait sur 'status' == 'SETTLED', qui n'existe jamais dans ce
        # fichier, donc affichait silencieusement « pas encore dénoué » alors
        # que 77 paris y sont réglés. C'est le SEUL journal qui reflète ce
        # que reçoivent vraiment les abonnés (68 alertes canal vs 17 au
        # journal forward le 24/08) -- il a désormais son lecteur dédié,
        # appelé séparément plus bas.
        if os.path.basename(f) == 'paper_trades_canal.jsonl':
            continue
        name = os.path.basename(f).replace('paper_trades_', 'surface ').replace('.jsonl', '')
        trades = []
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if line:
                try: trades.append(json.loads(line))
                except Exception: pass
        report_group(name, trades)
    report_canal()
    rappel_value_clv()
    print(f"\n{'='*60}\nRappel : CLV+ = prix battu ; le ROI net subit encore marge + gubbing.")
    resultats = []
    for i, (nom, gel, w) in enumerate(HYPOTHESES, 1):
        print(f"\n─── hypothèse {i}/{len(HYPOTHESES)} : {nom} (gel {gel}) ───")
        resultats.append((nom, gel, w()))
    bilan_tests_multiples(resultats)


if __name__ == '__main__':
    main()
