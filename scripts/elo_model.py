#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_model.py — Classements Elo tennis, construits sur nos propres résultats.

POURQUOI CE MODÈLE
Tout ce que collecte Tennis Edge — Pinnacle, books mous, Polymarket, Kalshi —
c'est LE MARCHÉ QUI SE REGARDE LUI-MÊME. Ces sources sont corrélées par
construction : quand Polymarket bouge, c'est souvent parce que Pinnacle a bougé.
Un Elo est le premier signal ORTHOGONAL du projet : il ne regarde aucune cote.

CE QU'IL NE FAUT PAS EN ATTENDRE
Un Elo ne battra pas Pinnacle. Les Elo tennis publics plafonnent autour de
68-70 % de précision, le marché fait un peu mieux — il intègre déjà l'équivalent
d'un Elo PLUS les blessures, la fatigue, la météo, la motivation. Construire ça
en espérant une valeur brute serait une perte de temps.
L'intérêt est ailleurs : disposer d'un A PRIORI INDÉPENDANT pour juger si un
mouvement de marché est justifié. Un steam de 8 points sans changement
fondamental est probablement du bruit ou une information privée ; un steam que
le modèle confirme est plus crédible. C'est un filtre, pas un pronostiqueur.

LIMITE ASSUMÉE, ET ELLE EST SÉVÈRE AU DÉPART
Nos résultats couvrent 854 joueurs pour ~1900 matchs, soit une MÉDIANE D'UN
SEUL MATCH PAR JOUEUR. Un Elo a besoin de dizaines de matchs par joueur pour
converger. Le modèle ne produit donc une prédiction que si LES DEUX joueurs
dépassent MIN_MATCHS ; en dessous, il renvoie None plutôt qu'un chiffre
trompeur. La couverture est faible aujourd'hui et grandira avec l'historique.
C'est aussi pourquoi le script affiche toujours sa couverture : un modèle qui
ne couvre que 5 % des matchs ne sert à rien, et il faut le voir.

MÉTHODE
  • K décroissant avec l'expérience : un joueur à 3 matchs bouge vite, un
    joueur à 50 matchs est stable. Sans cela, les nouveaux entrants polluent
    durablement les classements de leurs adversaires.
  • Elo GLOBAL et Elo PAR SURFACE, mélangés selon la confiance : la surface
    change beaucoup le tennis, mais un Elo par surface converge trois fois
    moins vite. Le mélange évite d'avoir à choisir.
  • Ordre CHRONOLOGIQUE strict : un Elo calculé dans le désordre n'a aucun sens.
    Les matchs sans date exploitable sont écartés, pas devinés.

Sorties : elo_ratings.json (classements courants) et, en option, une évaluation
de la précision hors échantillon.

Env : SET_RESULTS, ODDSPAPI_RESULTS, K_BASE, MIN_MATCHS, OUT.
Usage : python scripts/elo_model.py [--eval]
"""
import os
import sys
import json
import math
import re
import unicodedata
import datetime
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
ODDS_RESULTS = os.environ.get('ODDSPAPI_RESULTS', 'resultats_oddspapi.json')
OUT = os.environ.get('OUT', 'elo_ratings.json')

ELO_INIT = float(os.environ.get('ELO_INIT', '1500'))
K_BASE = float(os.environ.get('K_BASE', '32'))
K_MIN = float(os.environ.get('K_MIN', '12'))
MIN_MATCHS = int(os.environ.get('MIN_MATCHS', '5'))
# Poids de l'Elo de surface dans le mélange, une fois la surface bien fournie.
POIDS_SURFACE = float(os.environ.get('POIDS_SURFACE', '0.4'))

GAZON = ('s-hertogenbosch', 'london', 'stuttgart', 'wimbledon', 'nottingham',
         'berlin', 'halle', 'eastbourne', 'bad homburg', 'mallorca', 'newport',
         'queen')
TERRE = ('hamburg', 'prague', 'estoril', 'kitzbuhel', 'bastad', 'gstaad',
         'umag', 'palermo', 'bucharest', 'roland garros', 'madrid', 'rome',
         'monte carlo', 'barcelona')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s.lower()).strip()


def cle_joueur(nom):
    """Identité normalisée d'un joueur. Deux jetons minimum quand c'est
    possible : « Tallon Griekspoor » et « Tallon Tien » ne doivent jamais
    fusionner (cf. player_key.py)."""
    t = [x for x in re.split(r'[^a-z0-9]+', norm(nom)) if len(x) >= 2]
    return ' '.join(sorted(t)) if t else None


def surface(tournoi):
    s = norm(tournoi)
    if any(k in s for k in GAZON):
        return 'gazon'
    if any(k in s for k in TERRE):
        return 'terre'
    return 'dur'


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def charger_matchs():
    """Liste chronologique de (date, joueur_A, joueur_B, A_a_gagne, surface).

    Deux sources, fusionnées et dédupliquées :
      • resultats_oddspapi.json — home/away explicites + resolved_at ;
      • set_results.json — clé = uid de l'ancienne convention, dont l'ordre des
        noms NE correspond PAS au home/away réel (52 % d'inversions). On résout
        donc le home/away et la date DEPUIS LES COURBES, jamais depuis la clé.
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
            cle = (frozenset((a, b)), d.date())
            if cle in vus:
                continue
            vus.add(cle)
            matchs.append((d, a, b, v['winner'] == 'home',
                           surface(v.get('tournament'))))

    # uid -> (date, tournoi, home, away) depuis les courbes
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

    sans_date = 0
    if os.path.exists(SET_RESULTS):
        for uid, v in json.load(open(SET_RESULTS, encoding='utf-8')).items():
            if not isinstance(v, dict) or v.get('match') not in ('home', 'away'):
                continue
            m = meta.get(uid)
            if not m or not m[0]:
                sans_date += 1
                continue
            d, tour, home, away = m
            a, b = cle_joueur(home), cle_joueur(away)
            if not a or not b or a == b:
                continue
            cle = (frozenset((a, b)), d.date())
            if cle in vus:
                continue
            vus.add(cle)
            matchs.append((d, a, b, v['match'] == 'home', surface(tour)))

    matchs.sort(key=lambda x: x[0])
    print(f"Matchs exploitables : {len(matchs)} "
          f"({sans_date} écartés faute de date — un Elo calculé dans le "
          f"désordre n'a aucun sens)")
    if matchs:
        print(f"  période : {matchs[0][0].date()} -> {matchs[-1][0].date()}")
    return matchs


def k_facteur(n):
    """K décroissant avec l'expérience. Un joueur à 3 matchs doit bouger vite ;
    un joueur à 50 matchs est déjà bien situé et ne doit plus osciller."""
    return max(K_MIN, K_BASE / (1.0 + n / 12.0))


def attendu(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


REFERENCE = os.environ.get('ELO_REFERENCE', 'elo_reference.json')


def charger_reference():
    """Elo publiés par Tennis Abstract, s'ils ont été récupérés.

    PRIORITAIRES sur notre Elo maison : ils sont calculés sur l'historique
    COMPLET du circuit, quand le nôtre ne dispose que de deux mois et demi et
    d'une médiane d'un match par joueur (53,7 % de précision contre 66,9 %
    pour Pinnacle). Voir elo_fetch.py.
    """
    if not os.path.exists(REFERENCE):
        return {}, None
    try:
        d = json.load(open(REFERENCE, encoding='utf-8'))
    except Exception as e:
        print(f"⚠️ {REFERENCE} illisible : {e}")
        return {}, None
    j = d.get('joueurs') or {}
    # DATE DE VALIDITÉ. Les Elo publiés sont calculés sur l'historique COMPLET
    # du circuit : ceux du 10/08 intègrent déjà le résultat de tous les matchs
    # antérieurs. Les utiliser pour « prédire » un match de juin, c'est du
    # look-ahead pur — et ça se voyait : l'Elo ressortait à 70,7 % contre
    # 65,7 % pour Pinnacle, soit un modèle amateur battant le book le plus
    # sharp du marché. 77 % des matchs évalués étaient dans ce cas.
    # On ne s'autorise donc la référence que pour les matchs POSTÉRIEURS.
    maj = None
    for m in (d.get('meta') or {}).values():
        v = m.get('derniere_maj')
        if v:
            try:
                x = datetime.datetime.fromisoformat(v)
                maj = x if maj is None else max(maj, x)
            except ValueError:
                pass
    if maj is None:
        try:
            maj = datetime.datetime.fromisoformat(str(d.get('genere_le'))[:19])
        except Exception:
            maj = None
    if j:
        print(f"Référence Tennis Abstract : {len(j)} joueurs · valable à partir du "
              f"{maj.date() if maj else 'inconnu'}")
    return j, maj


class Elo:
    def __init__(self, reference=None, ref_depuis=None):
        # clé joueur -> {elo, dur, terre, gazon}
        self.ref = reference or {}
        # Date à partir de laquelle la référence est utilisable sans look-ahead.
        self.ref_depuis = ref_depuis
        self.n_ref = 0          # prédictions issues de la référence
        self.n_maison = 0       # prédictions issues de l'Elo maison
        self.g = collections.defaultdict(lambda: ELO_INIT)          # global
        self.s = collections.defaultdict(lambda: ELO_INIT)          # (joueur, surface)
        self.n = collections.Counter()                              # matchs joués
        self.ns = collections.Counter()                             # par surface
        self.dernier = {}

    def _ref_elo(self, j, surf):
        r = self.ref.get(j)
        if not r:
            return None
        v = r.get(surf) if surf else None
        base = r.get('elo')
        if base is None:
            return None
        if v is None:
            return float(base)
        # Les Elo de surface de Tennis Abstract sont DÉJÀ un mélange de l'Elo
        # global et de l'Elo de surface : on les prend tels quels, sans
        # remélanger, sous peine de diluer deux fois.
        return float(v)

    def proba(self, a, b, surf=None, quand=None):
        """Probabilité que A batte B, ou None si l'on ne sait rien de fiable.

        Ordre de préférence : Elo publié (historique complet du circuit), puis
        Elo maison. Renvoyer un chiffre pour un joueur vu une fois serait pire
        que ne rien renvoyer : ce serait un faux signal.
        """
        utilisable = (self.ref_depuis is None or quand is None
                      or quand >= self.ref_depuis)
        if utilisable:
            ra, rb = self._ref_elo(a, surf), self._ref_elo(b, surf)
            if ra is not None and rb is not None:
                self.n_ref += 1
                return attendu(ra, rb)
        if self.n[a] < MIN_MATCHS or self.n[b] < MIN_MATCHS:
            return None
        self.n_maison += 1
        pg = attendu(self.g[a], self.g[b])
        if surf is None:
            return pg
        # Le poids de la surface croît avec le nombre de matchs sur celle-ci :
        # un Elo de surface converge environ trois fois moins vite.
        conf = min(self.ns[(a, surf)], self.ns[(b, surf)]) / 15.0
        w = POIDS_SURFACE * min(1.0, conf)
        ps = attendu(self.s[(a, surf)], self.s[(b, surf)])
        return (1 - w) * pg + w * ps

    def maj(self, a, b, a_gagne, surf, quand):
        ea = attendu(self.g[a], self.g[b])
        ka, kb = k_facteur(self.n[a]), k_facteur(self.n[b])
        res = 1.0 if a_gagne else 0.0
        self.g[a] += ka * (res - ea)
        self.g[b] += kb * ((1 - res) - (1 - ea))

        esa = attendu(self.s[(a, surf)], self.s[(b, surf)])
        ksa, ksb = k_facteur(self.ns[(a, surf)]), k_facteur(self.ns[(b, surf)])
        self.s[(a, surf)] += ksa * (res - esa)
        self.s[(b, surf)] += ksb * ((1 - res) - (1 - esa))

        self.n[a] += 1
        self.n[b] += 1
        self.ns[(a, surf)] += 1
        self.ns[(b, surf)] += 1
        self.dernier[a] = self.dernier[b] = quand.isoformat(timespec='seconds')



def comparer_au_marche(matchs):
    """Elo vs Pinnacle sur les MÊMES matchs, prédits dans les mêmes conditions."""
    import math as _m
    ref = {}
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
            if r.get('book') != 'pinnacle':
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue
            # COUPE PRÉ-MATCH OBLIGATOIRE. Sans elle, h[-1] est un point IN-PLAY :
            # la cote y intègre déjà le déroulement de la rencontre, donc le
            # résultat. Constaté ici même : Pinnacle ressortait à 95,5 % de
            # précision au lieu des ~70 % attendus. C'est la signature du
            # look-ahead, et c'est la quatrième fois qu'elle apparaît dans ce
            # projet — toujours au même endroit, le dernier point de courbe.
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
            except Exception:
                continue
            if oh <= 1 or oa <= 1:
                continue
            ih, ia = 1 / oh, 1 / oa
            ref[(frozenset((ka, kb)), ct.date())] = (ka, ih / (ih + ia))

    _r, _d = charger_reference()
    elo = Elo(_r, _d)
    e_n = e_ok = m_ok = 0
    e_br = m_br = 0.0
    for d, a, b, a_gagne, surf in matchs:
        p = elo.proba(a, b, surf, d)
        mk = ref.get((frozenset((a, b)), d.date()))
        if p is not None and mk:
            joueur_ref, p_mk = mk
            if joueur_ref == b:
                p_mk = 1 - p_mk
            e_n += 1
            cible = 1.0 if a_gagne else 0.0
            e_ok += 1 if ((p > 0.5) == a_gagne) else 0
            m_ok += 1 if ((p_mk > 0.5) == a_gagne) else 0
            e_br += (p - cible) ** 2
            m_br += (p_mk - cible) ** 2
        elo.maj(a, b, a_gagne, surf, d)

    print()
    print("=" * 68)
    print("ELO vs PINNACLE — mêmes matchs, mêmes conditions")
    print("=" * 68)
    if e_n < 20:
        print(f"  {e_n} match(s) comparables — trop peu.")
        return
    for lab, ok, br in (('Elo', e_ok, e_br), ('Pinnacle', m_ok, m_br)):
        p = 100.0 * ok / e_n
        se = _m.sqrt(max(p / 100 * (1 - p / 100), 1e-9) / e_n) * 100
        print(f"  {lab:<10} précision {p:5.1f}% IC95 [{p-1.96*se:.1f} ; "
              f"{p+1.96*se:.1f}] · Brier {br/e_n:.4f}")
    print(f"  n = {e_n} matchs")
    ecart = 100.0 * (m_ok - e_ok) / e_n
    print(f"\n  Pinnacle devance l'Elo de {ecart:+.1f} points de précision.")
    if e_br < m_br:
        print("  ⚠️ mais l'Elo a un MEILLEUR Brier : il est mieux calibré alors")
        print("     qu'il se trompe plus souvent — méfiance, c'est inhabituel.")
    print("  Rappel : l'objectif n'est PAS de battre le marché, mais de disposer")
    print("  d'un avis indépendant pour juger si un mouvement est justifié.")



def main():
    evaluer = '--eval' in sys.argv
    matchs = charger_matchs()
    if not matchs:
        print("❌ aucun match exploitable.")
        return

    ref, ref_depuis = charger_reference()
    elo = Elo(ref, ref_depuis)
    # Évaluation HORS ÉCHANTILLON par construction : chaque match est prédit
    # AVANT d'être appris. Aucun risque de look-ahead.
    predits, justes, brier = 0, 0, 0.0
    couverts_par_mois = collections.defaultdict(lambda: [0, 0])
    for d, a, b, a_gagne, surf in matchs:
        p = elo.proba(a, b, surf, d)
        mois = d.strftime('%Y-%m')
        couverts_par_mois[mois][1] += 1
        if p is not None:
            couverts_par_mois[mois][0] += 1
            predits += 1
            justes += 1 if ((p > 0.5) == a_gagne) else 0
            brier += (p - (1.0 if a_gagne else 0.0)) ** 2
        elo.maj(a, b, a_gagne, surf, d)

    print()
    print("=" * 68)
    print("COUVERTURE — un modèle qui ne couvre presque rien ne sert à rien")
    print("=" * 68)
    print(f"{'mois':>9} | {'prédits':>8} | {'matchs':>7} | {'couverture':>11}")
    print("-" * 68)
    for m in sorted(couverts_par_mois):
        c, t = couverts_par_mois[m]
        print(f"{m:>9} | {c:>8} | {t:>7} | {100*c/max(1,t):>10.0f}%")
    print("-" * 68)
    print(f"{'TOTAL':>9} | {predits:>8} | {len(matchs):>7} | "
          f"{100*predits/max(1,len(matchs)):>10.0f}%")

    print(f"\n  origine des prédictions : {elo.n_ref} par la référence externe "
          f"(matchs postérieurs à sa date), {elo.n_maison} par l'Elo maison")

    if predits >= 20:
        prec = 100.0 * justes / predits
        se = math.sqrt(max(prec / 100 * (1 - prec / 100), 1e-9) / predits) * 100
        print()
        print("=" * 68)
        print("PRÉCISION hors échantillon (chaque match prédit AVANT apprentissage)")
        print("=" * 68)
        print(f"  n = {predits} · précision {prec:.1f}% "
              f"IC95 [{prec-1.96*se:.1f} ; {prec+1.96*se:.1f}]")
        print(f"  score de Brier : {brier/predits:.4f}  (plus bas = mieux ; "
              f"0,25 = pile ou face)")
        if prec < 55:
            print("  → au niveau du hasard : pas assez d'historique par joueur.")
        elif prec < 65:
            print("  → modèle faible mais informatif. Loin d'un marché (~70 %).")
        else:
            print("  → niveau comparable aux Elo tennis publics (68-70 %).")
    else:
        print(f"\n  {predits} prédictions seulement — trop peu pour mesurer quoi que "
              f"ce soit.\n  Il faut plusieurs matchs par joueur ; l'historique est "
              f"encore trop mince.")

    # ── COMPARAISON AU MARCHÉ ────────────────────────────────────────────
    # Le seul chiffre qui compte. « 61,9 % » ne veut rien dire dans l'absolu :
    # tout dépend de la difficulté des matchs couverts. On mesure donc Pinnacle
    # sur EXACTEMENT les mêmes rencontres, avec sa cote de clôture dévigée.
    if evaluer:
        comparer_au_marche(matchs)

    classes = sorted(((j, elo.g[j], elo.n[j]) for j in elo.n if elo.n[j] >= MIN_MATCHS),
                     key=lambda x: -x[1])
    print(f"\n{len(classes)} joueur(s) avec au moins {MIN_MATCHS} matchs "
          f"sur {len(elo.n)} rencontrés")
    if classes:
        print("\nTop 12 :")
        for j, r, n in classes[:12]:
            print(f"   {r:7.0f}  ({n:3} matchs)  {j}")

    json.dump({
        'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'n_matchs': len(matchs), 'min_matchs': MIN_MATCHS,
        'couverture_pct': round(100 * predits / max(1, len(matchs)), 1),
        'precision_pct': round(100.0 * justes / predits, 1) if predits else None,
        'brier': round(brier / predits, 4) if predits else None,
        'joueurs': {j: {'elo': round(elo.g[j], 1), 'n': elo.n[j],
                        'dernier': elo.dernier.get(j),
                        'surfaces': {s: round(elo.s[(j, s)], 1)
                                     for s in ('dur', 'terre', 'gazon')
                                     if elo.ns[(j, s)] > 0}}
                    for j in elo.n},
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nClassements écrits dans {OUT}")


if __name__ == '__main__':
    main()
