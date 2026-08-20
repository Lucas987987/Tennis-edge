#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
player_form.py — Fatigue et forme récente, sans aucune source externe.

POURQUOI CES DEUX VARIABLES
Tout ce que collecte Tennis Edge décrit LE MARCHÉ. L'Elo apporte un avis
indépendant, mais statique : il ignore qu'un joueur sort d'un 2h40 en trois
sets la veille, ou qu'il a perdu ses cinq derniers matchs. En tennis, deux
facteurs pèsent lourd et n'apparaissent dans aucun classement :
  • la FATIGUE — matchs récents et surtout SETS joués, un 2-1 coûtant bien plus
    qu'un 2-0 ;
  • la FORME — un joueur en fin de saison ou en reprise ne vaut pas son Elo.

Tout est calculable depuis set_results.json, resultats_oddspapi.json et les
courbes (pour les dates). Aucun collecteur, aucune clé d'API, aucun nouveau
mode de panne — c'est le principal intérêt face à l'ajout d'une source.

CE QU'IL NE FAUT PAS EN ATTENDRE
Ces variables ne prédisent pas un vainqueur à elles seules. Elles servent à
QUALIFIER un mouvement de marché : un steam vers un joueur qui a disputé
3 sets la veille est plus suspect qu'un steam vers un joueur frais.

DEUX GARDE-FOUS
  • STRICTEMENT ANTÉRIEUR. La fatigue d'un joueur au moment du match M ne
    compte que les matchs joués AVANT M. Inclure M lui-même serait du
    look-ahead — c'est le piège qui a déjà frappé cinq fois dans ce projet,
    dont deux fois cette semaine (dernier point de courbe in-play, et Elo
    publié appliqué à des matchs antérieurs).
  • COUVERTURE AFFICHÉE. Un joueur sans historique n'a pas une fatigue nulle :
    il a une fatigue INCONNUE. Le script renvoie None et compte à part, au lieu
    de laisser croire à un joueur frais.

Env : SET_RESULTS, ODDSPAPI_RESULTS, FENETRE_JOURS (7,14), FORME_N (10), OUT.
Usage : python scripts/player_form.py [--eval]
"""
import os
import sys
import json
import math
import random
import re
import math
import unicodedata
import datetime
import collections
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
ODDS_RESULTS = os.environ.get('ODDSPAPI_RESULTS', 'resultats_oddspapi.json')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
OUT = os.environ.get('OUT', 'player_form.json')
FENETRES = [int(x) for x in os.environ.get('FENETRE_JOURS', '7,14').split(',')]
FORME_N = int(os.environ.get('FORME_N', '10'))
MIN_HIST = int(os.environ.get('MIN_HIST', '3'))


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def cle_joueur(nom):
    """Jetons triés — même convention que elo_model.py et elo_fetch.py, pour
    que les trois modules parlent des mêmes joueurs."""
    t = [x for x in re.split(r'[^a-z0-9]+', norm(nom)) if len(x) >= 2]
    return ' '.join(sorted(t)) if t else None


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def charger_matchs():
    """(date, joueur_A, joueur_B, A_gagne, sets_A, sets_B, tournoi), triés.

    Deux sources fusionnées et dédupliquées. set_results.json est lu PAR UID
    et jamais par l'ordre des noms de sa clé : cet ordre ne correspond pas au
    home/away réel dans 52 % des cas (cf. results_bridge.py).
    """
    matchs, vus = [], set()

    if os.path.exists(ODDS_RESULTS):
        for v in json.load(open(ODDS_RESULTS, encoding='utf-8')).values():
            if not isinstance(v, dict) or v.get('winner') not in ('home', 'away'):
                continue
            a, b = cle_joueur(v.get('home')), cle_joueur(v.get('away'))
            d = _dt(v.get('resolved_at'))
            if not a or not b or a == b or not d:
                continue
            k = (frozenset((a, b)), d.date())
            if k in vus:
                continue
            vus.add(k)
            try:
                sa, sb = int(v.get('p1_sets') or 0), int(v.get('p2_sets') or 0)
            except (TypeError, ValueError):
                sa = sb = 0
            matchs.append((d, a, b, v['winner'] == 'home', sa, sb,
                           v.get('tournament') or ''))

    meta = {}
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        try:
            lignes = list(ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for ligne in lignes:
            try:
                r = json.loads(ligne)
            except Exception:
                continue
            u = r.get('uid')
            if u and u not in meta:
                meta[u] = (_dt(r.get('commence_time')), r.get('tournament'),
                           r.get('home_team') or r.get('home'),
                           r.get('away_team') or r.get('away'))

    if os.path.exists(SET_RESULTS):
        for uid, v in json.load(open(SET_RESULTS, encoding='utf-8')).items():
            if not isinstance(v, dict) or v.get('match') not in ('home', 'away'):
                continue
            m = meta.get(uid)
            if not m or not m[0]:
                continue
            d, tour, home, away = m
            a, b = cle_joueur(home), cle_joueur(away)
            if not a or not b or a == b:
                continue
            k = (frozenset((a, b)), d.date())
            if k in vus:
                continue
            vus.add(k)
            # set1/set2 renseignent le vainqueur de chaque set, pas le score :
            # on reconstitue une charge minimale (2 sets si un seul camp les a
            # pris, 3 sinon).
            s1, s2 = v.get('set1'), v.get('set2')
            trois = (s1 in ('home', 'away') and s2 in ('home', 'away') and s1 != s2)
            gagne = v['match'] == 'home'
            sa, sb = (2, 1) if (gagne and trois) else (2, 0) if gagne else \
                     (1, 2) if trois else (0, 2)
            matchs.append((d, a, b, gagne, sa, sb, tour or ''))

    matchs.sort(key=lambda x: x[0])
    return matchs


class Historique:
    """Fatigue et forme, calculées uniquement sur le passé STRICT."""

    def __init__(self):
        self.par_joueur = collections.defaultdict(list)   # [(date, sets, gagne)]

    def ajouter(self, quand, joueur, sets_joues, gagne):
        self.par_joueur[joueur].append((quand, sets_joues, gagne))

    def fatigue(self, joueur, quand):
        """Matchs et SETS disputés dans les N jours précédant `quand`.

        Les sets comptent plus que les matchs : un 2-1 en trois sets serrés
        coûte bien davantage qu'un 2-0 expédié, et c'est précisément ce que le
        simple décompte de matchs ignore.
        """
        h = self.par_joueur.get(joueur)
        if not h:
            return None
        out = {}
        for j in FENETRES:
            borne = quand - datetime.timedelta(days=j)
            # STRICTEMENT antérieur : `< quand`, jamais `<=`. Inclure le match
            # en cours serait du look-ahead.
            lot = [x for x in h if borne <= x[0] < quand]
            out[f'matchs_{j}j'] = len(lot)
            out[f'sets_{j}j'] = sum(x[1] for x in lot)
        dernier = [x for x in h if x[0] < quand]
        out['jours_depuis_dernier'] = (
            round((quand - dernier[-1][0]).total_seconds() / 86400.0, 1)
            if dernier else None)
        out['n_historique'] = len(dernier)
        return out

    def forme(self, joueur, quand, n=None):
        """Taux de victoire sur les N derniers matchs, antérieurs à `quand`."""
        h = [x for x in self.par_joueur.get(joueur, []) if x[0] < quand]
        if len(h) < MIN_HIST:
            return None
        lot = h[-(n or FORME_N):]
        return {'n': len(lot),
                'victoires': sum(1 for x in lot if x[2]),
                'taux': round(sum(1 for x in lot if x[2]) / len(lot), 3)}


def ic_prop(v):
    n = len(v)
    if n < 2:
        return None, None, None
    p = st.mean(v)
    se = math.sqrt(max(p * (1 - p), 1e-9) / n)
    return p, p - 1.96 * se, p + 1.96 * se



def cotes_sharp():
    """{(paire, date): (joueur_home, proba_home)} — clôture PRÉ-MATCH dévigée.

    COUPE PRÉ-MATCH OBLIGATOIRE : le dernier point de courbe est IN-PLAY et
    encode déjà le déroulement de la rencontre. Ce piège a produit quatre faux
    positifs dans ce projet, dont un Pinnacle mesuré à 95,5 % de précision.
    """
    ref = {}
    for src in (os.environ.get('CURVES', 'book_curves_live.jsonl'),
                'book_curves.jsonl'):
        try:
            lignes = list(ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for ligne in lignes:
            try:
                r = json.loads(ligne)
            except Exception:
                continue
            if r.get('book') != SHARP:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            h = [q for q in (r.get('home_curve') or [])
                 if q and q[1] and _dt(q[0]) and _dt(q[0]) < ct]
            a = [q for q in (r.get('away_curve') or [])
                 if q and q[1] and _dt(q[0]) and _dt(q[0]) < ct]
            if not h or not a:
                continue
            ka = cle_joueur(r.get('home_team') or r.get('home'))
            kb = cle_joueur(r.get('away_team') or r.get('away'))
            if not ka or not kb:
                continue
            try:
                oh, oa = float(h[-1][1]), float(a[-1][1])
            except (TypeError, ValueError):
                continue
            if oh <= 1 or oa <= 1:
                continue
            ih, ia = 1 / oh, 1 / oa
            ref[(frozenset((ka, kb)), ct.date())] = (ka, ih / (ih + ia))
    return ref


def ic_moy(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def residu_marche(lignes, ref):
    """LA question : le marché sous-estime-t-il ces facteurs ?

    « Ces variables prédisent-elles le résultat » est une question sans intérêt
    pratique : évidemment que la fatigue joue. Ce qui compte pour Tennis Edge,
    c'est de savoir si le prix l'intègre DÉJÀ. On mesure donc le RÉSIDU
    (résultat réel − probabilité du marché) par tranche. Un résidu nul signifie
    que le bookmaker connaît le calendrier aussi bien que nous, et que le
    signal ne vaut rien — même s'il influence réellement les matchs.
    """
    obs = []
    for x in lignes:
        d = _dt(x['date'])
        mk = ref.get((frozenset((x['a'], x['b'])), d.date())) if d else None
        if not mk:
            continue
        joueur_ref, p_ref = mk
        obs.append({
            'p': p_ref if joueur_ref == x['a'] else 1 - p_ref,
            'gagne': x['a_gagne'],
            'd_sets7': x['fatigue_a'].get('sets_7j', 0) - x['fatigue_b'].get('sets_7j', 0),
            'd_repos': x['fatigue_a'].get('jours_repos', 0) - x['fatigue_b'].get('jours_repos', 0),
            'd_forme': x['forme_a'].get('taux', .5) - x['forme_b'].get('taux', .5),
        })
    print()
    print("=" * 74)
    print(f"LE MARCHÉ SOUS-ESTIME-T-IL CES FACTEURS ? (résidu = réel − {SHARP})")
    print(f"{len(obs)} match(s) avec un prix pré-match disponible")
    print("=" * 74)
    if len(obs) < 60:
        print("  trop peu pour conclure — laisser l'historique grossir.")
        return {}, obs

    out = {}
    for cle, lib, bornes in (
        ('d_sets7', "Écart de SETS joués sur 7 jours (A − B)",
         [(-99, -3, 'A -3 ou moins'), (-3, 0, 'A -1 à -2'), (0, 1, 'égalité'),
          (1, 4, 'A +1 à +3'), (4, 99, 'A +4 ou plus')]),
        ('d_repos', "Écart de jours de repos (A − B)",
         [(-99, -2, 'A moins reposé'), (-2, 2, 'proches'), (2, 99, 'A plus reposé')]),
        ('d_forme', "Écart de forme (A − B)",
         [(-1.01, -0.2, 'A moins bonne'), (-0.2, 0.2, 'proches'),
          (0.2, 1.01, 'A meilleure')])):
        print(f"\n── {lib} ──")
        print(f"{'tranche':>16} | {'n':>4} | {'résidu':>8} | {'IC95':>18}")
        print("-" * 60)
        bloc = {}
        for lo, hi, lab in bornes:
            g = [o for o in obs if lo <= o[cle] < hi]
            if len(g) < 25:
                continue
            v = [(1.0 if o['gagne'] else 0.0) - o['p'] for o in g]
            m, l, h = ic_moy(v)
            sig = (l > 0 or h < 0)
            bloc[lab] = {'n': len(g), 'residu_pts': round(m * 100, 2),
                         'ic': [round(l * 100, 2), round(h * 100, 2)],
                         'significatif': bool(sig)}
            print(f"{lab:>16} | {len(g):>4} | {m*100:>+7.1f} | "
                  f"[{l*100:>+6.1f} ; {h*100:>+6.1f}]{'  ⚠️' if sig else ''}")
        out[cle] = bloc
    return out, obs


def permutation(obs, n_permut=300):
    """Combien de tirages ALÉATOIRES produisent une tranche « significative » ?

    On réattribue à chaque match la fatigue d'un AUTRE match. Au-delà de ~5 %,
    toute tranche signalée ci-dessus doit être tenue pour du bruit. C'est le
    test qui a démonté quatre faux positifs de ce projet.
    """
    if len(obs) < 60:
        return None
    rng = random.Random(20260820)
    faux = 0
    base = [(1.0 if o['gagne'] else 0.0) - o['p'] for o in obs]
    vals = [o['d_sets7'] for o in obs]
    for _ in range(n_permut):
        rng.shuffle(vals)
        for lo, hi in ((-99, -3), (4, 99)):
            g = [b for b, f in zip(base, vals) if lo <= f < hi]
            if len(g) < 25:
                continue
            m, l, h = ic_moy(g)
            if l is not None and (l > 0 or h < 0):
                faux += 1
                break
    return 100.0 * faux / n_permut


def main():
    evaluer = '--eval' in sys.argv
    matchs = charger_matchs()
    print(f"Matchs exploitables : {len(matchs)}")
    if not matchs:
        print("❌ aucun match.")
        return
    print(f"  période : {matchs[0][0].date()} -> {matchs[-1][0].date()}")

    hist = Historique()
    lignes = []
    couvert = 0
    # Chaque match est mesuré AVANT d'être ajouté à l'historique : la fatigue
    # et la forme sont donc toujours calculées sur le seul passé.
    for d, a, b, a_gagne, sa, sb, tour in matchs:
        fa, fb = hist.fatigue(a, d), hist.fatigue(b, d)
        ma, mb = hist.forme(a, d), hist.forme(b, d)
        if fa and fb and ma and mb:
            couvert += 1
            lignes.append({'date': d.isoformat(timespec='seconds'),
                           'a': a, 'b': b, 'a_gagne': a_gagne,
                           'fatigue_a': fa, 'fatigue_b': fb,
                           'forme_a': ma, 'forme_b': mb})
        total = sa + sb
        hist.ajouter(d, a, total, a_gagne)
        hist.ajouter(d, b, total, not a_gagne)

    print(f"  des DEUX joueurs connus : {couvert} "
          f"({100*couvert/len(matchs):.0f} %) — un joueur sans historique n'est "
          f"pas « frais », il est INCONNU")

    if evaluer and len(lignes) >= 30:
        print()
        print("=" * 72)
        print("CES VARIABLES PRÉDISENT-ELLES QUELQUE CHOSE ?")
        print("Comparaison hors échantillon : chaque match mesuré avant d'être appris")
        print("=" * 72)

        def bloc(sel, lab):
            if len(sel) < 20:
                print(f"  {lab:<34} n={len(sel):>4}  trop peu")
                return
            v = [1.0 if x['a_gagne'] else 0.0 for x in sel]
            p, lo, hi = ic_prop(v)
            flag = "  ✅" if (lo > 0.5 or hi < 0.5) else ""
            print(f"  {lab:<34} n={len(sel):>4}  {p*100:5.1f}% "
                  f"[{lo*100:5.1f} ; {hi*100:5.1f}]{flag}")

        for j in FENETRES:
            k = f'sets_{j}j'
            plus = [x for x in lignes if x['fatigue_a'][k] > x['fatigue_b'][k]]
            moins = [x for x in lignes if x['fatigue_a'][k] < x['fatigue_b'][k]]
            print(f"\n  — sur {j} jours —")
            bloc(plus, f"A a joué PLUS de sets -> A gagne")
            bloc(moins, f"A a joué MOINS de sets -> A gagne")

        print("\n  — forme récente —")
        mieux = [x for x in lignes if x['forme_a']['taux'] > x['forme_b']['taux'] + 0.2]
        pire = [x for x in lignes if x['forme_a']['taux'] < x['forme_b']['taux'] - 0.2]
        bloc(mieux, "A en bien meilleure forme")
        bloc(pire, "A en bien moins bonne forme")

        print()
        print("  Lecture : 50 % = aucun effet. Il faut que l'IC95 exclue 50 %.")
        print("  ⚠️ ces variables sont CORRÉLÉES au niveau des joueurs : un joueur")
        print("     fort joue plus de matchs (il gagne) ET gagne plus souvent. Un")
        print("     écart ici ne prouve donc pas un effet de fatigue — il faudrait")
        print("     comparer à Elo égal. À ne pas surinterpréter.")
    elif evaluer:
        print(f"\n  {len(lignes)} match(s) exploitables — trop peu pour évaluer.")

    residus, obs = ({}, [])
    if lignes:
        residus, obs = residu_marche(lignes, cotes_sharp())
        taux = permutation(obs)
        if taux is not None:
            print(f"\nTest de permutation : {taux:.0f} % des tirages ALÉATOIRES")
            print("produisent au moins une tranche « significative ».")
            if taux > 10:
                print("→ au-delà des 5 % attendus : toute tranche ⚠️ est du bruit")
                print("  tant qu'elle n'est pas confirmée hors échantillon.")
        n_sig = sum(1 for b in residus.values() for v in b.values()
                    if v.get('significatif'))
        print()
        if n_sig == 0:
            print("→ AUCUN résidu significatif : le marché intègre déjà fatigue et")
            print("  forme. Ces facteurs n'apportent rien à Tennis Edge, même s'ils")
            print("  influencent bel et bien les matchs.")
        else:
            print(f"→ {n_sig} tranche(s) significative(s) : à GELER et valider hors")
            print("  échantillon. Ne rien brancher dessus en l'état.")

    etat = {}
    for j, h in hist.par_joueur.items():
        if len(h) < MIN_HIST:
            continue
        fin = matchs[-1][0] + datetime.timedelta(seconds=1)
        etat[j] = {'fatigue': hist.fatigue(j, fin), 'forme': hist.forme(j, fin)}
    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_matchs': len(matchs), 'n_couverts': couvert,
        'fenetres_jours': FENETRES, 'forme_n': FORME_N,
        'residus_marche': residus,
        'joueurs': etat,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n{len(etat)} joueur(s) écrits dans {OUT}")


if __name__ == '__main__':
    main()
