#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal_clv.py — CLV réalisé des écarts publiés sur le canal. LA métrique du canal.

Pour chaque opérateur signalé « en retard » dans un message publié, on compare le
prix affiché à ce moment-là à la CLÔTURE réelle du MÊME opérateur (dernier prix
pré-match). Si le prix signalé était plus élevé que sa clôture, l'écart s'est
refermé : CLV positif.

Deux garanties méthodologiques inchangées :
  • le prix comparé est celui du MÊME opérateur (pas une clôture sharp) : on
    mesure le refermement de l'écart, sans effet de marge entre books ;
  • points PRÉ-MATCH uniquement (un point in-play ferait entrer le résultat
    dans la mesure).

════════════════════════════════════════════════════════════════════════════
TROIS CORRECTIFS (16/08/2026)
════════════════════════════════════════════════════════════════════════════

1. REGISTRE GELÉ — l'historique ne s'autodétruit plus
   Le CSV était RÉÉCRIT intégralement à chaque run, en recalculant tout depuis
   les courbes. Or purge_data.py supprime les partitions live après LIVE_DAYS
   (3 jours), pendant que canal_public_log.jsonl en conserve douze. Chaque
   ligne dont la courbe avait été purgée DISPARAISSAIT donc du track record :
   18 écarts mesurés sur 42 publiés, et une fenêtre glissante de 3 jours.
   Pour un canal dont l'argument est la transparence vérifiable, et dont la
   monétisation dépend d'un track record prospectif publié, c'est fatal.
   Désormais : une ligne calculée est ÉCRITE UNE FOIS et JAMAIS recalculée.
   Le CSV est un registre append-only qui survit à toute purge.

2. SOURCES ÉLARGIES — récupération de l'historique déjà perdu
   Les courbes ne sont plus lues seulement dans les fichiers plats live : on
   lit aussi parts/hist_*, qui ne sont JAMAIS purgées (HIST_DAYS=0). Les
   alertes antérieures à la fenêtre live redeviennent mesurables.

3. DÉDUPLICATION — un match ne compte qu'une fois
   Un même match génère souvent plusieurs alertes (paliers successifs) et
   chaque alerte plusieurs opérateurs. Les compter séparément gonfle n et
   fait passer un seul match pour plusieurs observations indépendantes.
   Constaté : Titouan Droguet pesait 6 lignes sur 18, soit 33 % du total.
   Le chiffre de tête est désormais calculé PAR MATCH (une observation par
   match, moyenne de ses lignes). Le détail par opérateur reste disponible,
   mais n'est plus l'unité de mesure.

Env : LOG, OUT (canal_clv_detail.csv), MIN_N (5), REBUILD (1 = recalcule tout,
      à n'utiliser que pour une reconstruction volontaire).
"""
import os, sys, json, csv, datetime, statistics as st, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov

LOG     = os.environ.get('LOG', 'canal_public_log.jsonl')
OUT     = os.environ.get('OUT', 'canal_clv_detail.csv')
MIN_N   = int(os.environ.get('MIN_N', '5'))
REBUILD = os.environ.get('REBUILD', '0') == '1'

# EXCHANGES — retirés du registre actif, ARCHIVÉS à part.
# Un exchange n'a pas de marge intégrée : son prix est structurellement plus
# haut, donc il ressort en permanence comme « en retard » alors qu'il ne l'est
# pas. Mesuré sur les alertes réellement publiées : CLV médian -1,7 %, 14 % de
# refermeture (n=7), contre +9,4 % / 83 % pour les vrais opérateurs.
# canal_public.py ne les signale plus depuis le 06/08/2026 (constante EXCHANGES,
# même liste). Les lignes antérieures sont sorties du registre actif et écrites
# dans ARCHIVE (canal_clv_exclus.csv), avec leur date d'exclusion.
# CE N'EST PAS DU TRI SÉLECTIF : on exclut une CATÉGORIE entière d'opérateurs,
# pour une raison structurelle décidée et documentée à l'avance (un exchange
# n'a pas de marge, donc pas de retard à rattraper), et non des lignes choisies
# sur leur résultat. La distinction est ce qui sépare une correction de méthode
# d'un nettoyage de track record. L'archive garde la trace vérifiable des
# messages réellement publiés à l'époque.
# NB : ceci ne concerne QUE le rôle « book en retard ». L'usage de Betfair comme
# CONFIRMATEUR du mouvement Pinnacle (hypothèse gelée n°10, validation_report.py)
# est un tout autre rôle et n'est pas affecté.
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())

ARCHIVE = os.environ.get('ARCHIVE', 'canal_clv_exclus.csv')

FIELDS = ['date', 'uid', 'joueur', 'book', 'prix_signale', 'cloture',
          'ecart_annonce', 'clv', 'source', 'exclu', 'gele_le']


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def load_closes():
    """{(uid, book, nom_joueur): (dernier prix PRÉ-MATCH, origine)}

    Cascade de sources, de la plus fraîche à la plus permanente :
      1. fichiers plats live  (reconstruits depuis parts/live_*, ~3 jours)
      2. partitions hist      (parts/hist_*, JAMAIS purgées -> tout l'historique)
    La première source qui fournit une clôture gagne ; hist sert de filet pour
    tout ce qui est sorti de la fenêtre live.
    """
    closes = {}
    sources = [('live', 'book_curves_live.jsonl'),
               ('hist', 'book_curves.jsonl')]   # nom legacy -> partitions via open_curves
    for origine, p in sources:
        try:
            lines = ov.open_curves(p, verbose=False)
        except FileNotFoundError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except Exception:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            home = r.get('home_team') or r.get('home') or ''
            away = r.get('away_team') or r.get('away') or ''
            for key, name in (('home_curve', home), ('away_curve', away)):
                pts = [(_dt(q[0]), q[1]) for q in (r.get(key) or [])
                       if _dt(q[0]) and q[1] and q[1] > 1]
                pts = sorted(q for q in pts if q[0] < ct)   # PRÉ-MATCH uniquement
                if pts and name:
                    k = (r.get('uid'), r.get('book'), name)
                    if k not in closes:                     # priorité à la 1re source
                        closes[k] = (pts[-1][1], origine)
    return closes


def load_ledger():
    """Registre déjà gelé. Clé = (date d'alerte, uid, book) : une alerte donnée
    sur un opérateur donné n'est mesurée qu'une seule fois, définitivement."""
    if REBUILD or not os.path.exists(OUT):
        return {}
    out = {}
    try:
        with open(OUT, newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                try:
                    r['prix_signale'] = float(r['prix_signale'])
                    r['cloture'] = float(r['cloture'])
                    r['ecart_annonce'] = float(r['ecart_annonce'])
                    r['clv'] = float(r['clv'])
                except Exception:
                    continue
                r.setdefault('uid', '')
                r.setdefault('source', 'inconnue')
                r.setdefault('gele_le', '')
                # rétro-marquage des lignes gelées avant l'introduction du champ
                if not r.get('exclu'):
                    r['exclu'] = 'exchange' if r['book'] in EXCHANGES else ''
                out[(r['date'], r.get('uid', ''), r['book'])] = r
    except Exception as e:
        print(f"⚠️ registre illisible ({e}) — on repart des courbes.")
        return {}
    return out


def _ic95(v):
    n = len(v)
    if n < 2:
        return None, None
    se = st.stdev(v) / (n ** 0.5)
    mu = st.mean(v)
    return mu - 1.96 * se, mu + 1.96 * se


def main():
    if not os.path.exists(LOG):
        print(f"{LOG} introuvable"); return

    ledger = load_ledger()
    n_avant = len(ledger)
    closes = load_closes()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')

    nouveaux = 0
    non_mesurables = 0
    for line in open(LOG, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        date = str(m.get('t'))[:16]
        uid = m.get('uid') or ''
        joueur = m.get('joueur')
        for entry in (m.get('retards') or []):
            try:
                book, prix, ecart = entry[0], float(entry[1]), float(entry[2])
            except Exception:
                continue
            if book in EXCHANGES:
                continue          # catégorie exclue : n'entre plus au registre
            k = (date, uid, book)
            if k in ledger:
                continue                       # déjà gelé : on n'y retouche JAMAIS
            got = closes.get((uid, book, joueur))
            if not got:
                non_mesurables += 1
                continue
            cl, origine = got
            ledger[k] = dict(
                date=date, uid=uid, joueur=joueur, book=book,
                prix_signale=prix, cloture=cl, ecart_annonce=round(ecart, 1),
                clv=round((prix / cl - 1) * 100, 1),
                source=origine,
                exclu='exchange' if book in EXCHANGES else '',
                gele_le=today)
            nouveaux += 1

    # ── Sortie des exchanges déjà gelés vers l'archive ────────────────────
    a_archiver = [r for r in ledger.values() if r['book'] in EXCHANGES]
    if a_archiver:
        deja = set()
        if os.path.exists(ARCHIVE):
            with open(ARCHIVE, newline='', encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    deja.add((r.get('date'), r.get('uid'), r.get('book')))
        mode = 'a' if os.path.exists(ARCHIVE) else 'w'
        with open(ARCHIVE, mode, newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
            if mode == 'w':
                w.writeheader()
            n_arch = 0
            for r in sorted(a_archiver, key=lambda x: x['date']):
                if (r['date'], r.get('uid'), r['book']) in deja:
                    continue
                r['exclu'] = 'exchange'
                w.writerow(r); n_arch += 1
        for r in a_archiver:
            ledger.pop((r['date'], r.get('uid', ''), r['book']), None)
        print(f"→ {n_arch} ligne(s) d'exchange déplacée(s) vers {ARCHIVE} "
              f"(hors métrique, trace conservée)")

    rows = list(ledger.values())
    if not rows:
        print("Aucun écart signalé n'a encore de clôture connue.")
        return

    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x['date'], -x['clv'])):
            w.writerow(r)

    # ── Le chiffre de tête porte sur les opérateurs RETENUS ───────────────
    retenus = rows          # le registre ne contient plus que des lignes retenues

    # ── DÉDUPLICATION : une observation par MATCH ─────────────────────────
    par_match = collections.defaultdict(list)
    for r in retenus:
        par_match[r['uid'] or r['joueur']].append(r['clv'])
    match_clv = [st.mean(v) for v in par_match.values()]

    par_alerte = collections.defaultdict(list)
    for r in retenus:
        par_alerte[(r['date'], r['uid'])].append(r['clv'])
    alerte_clv = [st.mean(v) for v in par_alerte.values()]

    brut = [r['clv'] for r in retenus]
    lo, hi = _ic95(match_clv)
    pos = 100 * sum(1 for x in match_clv if x > 0) / len(match_clv)

    print("=== CLV RÉALISÉ DES ÉCARTS PUBLIÉS ===")
    print(f"registre : {n_avant} lignes gelées + {nouveaux} nouvelles = {len(rows)}"
          f"  ({non_mesurables} pas encore mesurables)")
    print()
    print("CHIFFRE DE TÊTE — une observation par MATCH (déduplication) :")
    print(f"  n = {len(match_clv)} matchs | CLV médian {st.median(match_clv):+.1f}% "
          f"| moyen {st.mean(match_clv):+.1f}%")
    if lo is not None:
        verdict = "IC95 exclut 0" if lo > 0 else "IC95 traverse 0 — non concluant"
        print(f"  IC95 [{lo:+.1f} ; {hi:+.1f}] -> {verdict}")
    print(f"  écarts refermés : {pos:.0f}%")
    print()
    print("Pour information — unités NON indépendantes, à ne pas publier comme n :")
    print(f"  par alerte        n={len(alerte_clv):3} | médian {st.median(alerte_clv):+5.1f}%")
    print(f"  par alerte×book   n={len(brut):3} | médian {st.median(brut):+5.1f}%")

    byb = collections.defaultdict(list)
    for r in retenus:
        byb[r['book']].append(r['clv'])
    print(f"\nPar opérateur (min {MIN_N} écarts, unités non indépendantes) :")
    for b, v in sorted(byb.items(), key=lambda x: -len(x[1])):
        if len(v) < MIN_N:
            continue
        p = 100 * sum(1 for x in v if x > 0) / len(v)
        print(f"  {b:14} n={len(v):3} | CLV médian {st.median(v):+5.1f}% | refermés {p:3.0f}%")

    print("\nPar ampleur de l'écart annoncé :")
    for lo_, hi_, lab in [(0, 5, '2-5%'), (5, 10, '5-10%'), (10, 20, '10-20%'), (20, 999, '20%+')]:
        g = [r['clv'] for r in retenus if lo_ <= r['ecart_annonce'] < hi_]
        if len(g) < 3:
            continue
        p = 100 * sum(1 for x in g if x > 0) / len(g)
        print(f"  {lab:7} n={len(g):3} | CLV médian {st.median(g):+5.1f}% | refermés {p:3.0f}%")

    src = collections.Counter(r.get('source', '?') for r in rows)
    print(f"\nOrigine des clôtures : {dict(src)}")
    print(f"Registre écrit dans {OUT} ({len(rows)} lignes, jamais recalculées)")


if __name__ == '__main__':
    main()
