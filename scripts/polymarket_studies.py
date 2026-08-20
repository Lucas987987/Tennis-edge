#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polymarket_studies.py — Trois usages des données Polymarket.

Un marché de prédiction n'a pas de marge intégrée : son prix EST une
probabilité. C'est la seule source du projet qui offre une mesure directe de la
probabilité juste, sans passer par un dévigage. D'où trois études.

  1. DÉVIGAGE  — le dévigage Shin appliqué à Pinnacle colle-t-il au prix
     Polymarket ? Un écart systématique biaiserait TOUT le projet : CLV,
     opening_value, drift_outcome, la détection du canal. C'est l'étude la plus
     rentable, car elle améliore l'existant même si Polymarket ne sert à rien
     d'autre.

  2. CONFIRMATEUR — quand Pinnacle bouge et que Polymarket bouge DANS LE MÊME
     SENS, l'écart laissé chez un book mou se referme-t-il mieux ? Même forme
     que l'hypothèse gelée n°10 (Betfair), avec un marché indépendant et un
     public totalement différent.

  3. DIVERGENCE — quand les deux s'écartent nettement, lequel prédit mieux le
     vainqueur ? Réponse binaire, tranchée sur set_results.json.

GARDE-FOU COMMUN : chaque étude affiche son n et son intervalle de confiance,
et refuse de conclure quand l'IC traverse le point neutre. Quatre faux positifs
ont été démontés dans ce projet faute de ce réflexe.

Usage : python scripts/polymarket_studies.py [devig|confirm|divergence|all]
"""
import os
import sys
import math
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polymarket_common as pc  # noqa: E402

MOVE_MIN   = float(os.environ.get('MOVE_MIN_PTS', '3')) / 100.0
GAP_MIN    = float(os.environ.get('SOFT_GAP_PCT', '3')) / 100.0
DIVERG_MIN = float(os.environ.get('DIVERG_MIN_PTS', '5')) / 100.0
# Seuil de MATÉRIALITÉ : en dessous, un biais est statistiquement détectable
# mais sans conséquence pratique. Le CLV et le ROI du projet se mesurent en
# points entiers ; un décalage de dévigage de 0,3 pt ne change aucune décision.
# Sans ce seuil, un n élevé transforme n'importe quelle poussière en alerte.
BIAIS_MATERIEL = float(os.environ.get('BIAIS_MATERIEL_PTS', '0.5'))
LOOKBACK   = float(os.environ.get('LOOKBACK_MIN', '30'))
OUT        = os.environ.get('OUT', 'polymarket_studies_report.json')


def ic_moy(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def ic_prop(v):
    n = len(v)
    if n < 2:
        return None, None, None
    p = st.mean(v)
    se = math.sqrt(max(p * (1 - p), 1e-9) / n)
    return p, p - 1.96 * se, p + 1.96 * se


# ══════════════════════════════════════════════════════════════════════════
def etude_devig(pm, books):
    """1. Le dévigage Shin colle-t-il à la probabilité Polymarket ?"""
    print()
    print("=" * 74)
    print("1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs probabilité Polymarket")
    print("=" * 74)

    # UNITÉ = LE MATCH, pas l'instant. Les points d'un même match, échantillonnés
    # toutes les 5 min, sont fortement autocorrélés : les traiter comme
    # indépendants divise l'intervalle de confiance par racine de 20 ou 30 et
    # fait ressortir comme « significatif » un biais de 0,08 pt. On calcule donc
    # un écart moyen PAR MATCH, puis l'intervalle sur ces moyennes.
    par_tranche = collections.defaultdict(lambda: collections.defaultdict(list))
    par_match = collections.defaultdict(list)
    par_match_prop = collections.defaultdict(list)
    n_points = 0
    for uid, serie_pm in pm.items():
        b = books.get(uid, {}).get(pc.SHARP)
        if not b:
            continue
        # Les DEUX méthodes sont comparées au même prix Polymarket, sur les
        # mêmes instants : c'est la seule façon de savoir laquelle est la plus
        # juste, et l'écart entre elles atteint 1,6 pt sur les cotes
        # déséquilibrées.
        prop = {t: v for t, v in b.get('serie_prop', [])}
        for t, p_pm, p_pin in pc.instants_communs(
                [(x[0], x[1]) for x in serie_pm], b['serie'], b['ct']):
            ecart = (p_pin - p_pm) * 100.0
            n_points += 1
            par_match[uid].append(ecart)
            pp = pc.valeur_a(b.get('serie_prop', []), t)
            if pp is not None:
                par_match_prop[uid].append((pp - p_pm) * 100.0)
            # tranche par probabilité du favori : c'est là que les méthodes de
            # dévigage divergent le plus (favori très marqué)
            pf = max(p_pin, 1 - p_pin)
            for lo, hi, lab in ((0.50, 0.60, '50-60%'), (0.60, 0.70, '60-70%'),
                                (0.70, 0.80, '70-80%'), (0.80, 0.90, '80-90%'),
                                (0.90, 1.01, '90%+')):
                if lo <= pf < hi:
                    par_tranche[lab][uid].append(ecart)
                    break

    if not par_match:
        print("  aucun instant commun Polymarket / Pinnacle.")
        return {}

    tous = [st.mean(v) for v in par_match.values()]      # 1 valeur par match
    m, lo, hi = ic_moy(tous)
    if m is None:
        print(f"  {len(tous)} match(s) seulement — trop peu pour un intervalle.")
        return {'n_matchs': len(tous)}
    print(f"  n = {len(tous)} matchs ({n_points} instants, grille 5 min)")
    print(f"  écart moyen Shin - Polymarket : {m:+.2f} pts  IC95 [{lo:+.2f} ; {hi:+.2f}]")
    print(f"  écart médian par match : {st.median(tous):+.2f} pts")

    # ── Comparaison des deux dévigages ───────────────────────────────────
    prop_v = [st.mean(v) for v in par_match_prop.values() if v]
    if len(prop_v) >= 3:
        mp, lp, hp = ic_moy(prop_v)
        print()
        print(f"  {'méthode':<16}{'matchs':>7}{'écart moyen':>13}{'IC95':>20}")
        print("  " + "-" * 56)
        print(f"  {'Shin':<16}{len(tous):>7}{m:>+12.2f}  [{lo:>+5.2f} ; {hi:>+5.2f}]")
        print(f"  {'proportionnel':<16}{len(prop_v):>7}{mp:>+12.2f}  [{lp:>+5.2f} ; {hp:>+5.2f}]")
        gagnant = 'Shin' if abs(m) <= abs(mp) else 'proportionnel'
        print(f"  → plus proche de Polymarket : {gagnant} "
              f"(écart {min(abs(m), abs(mp)):.2f} contre {max(abs(m), abs(mp)):.2f} pt)")
        if abs(abs(m) - abs(mp)) < 0.1:
            print("    mais la différence entre les deux est elle-même négligeable :")
            print("    sur cet échantillon, le choix de méthode ne change rien.")
    print()
    print(f"  {'tranche favori':>15} | {'matchs':>5} | {'écart moyen':>12} | {'IC95':>18}")
    print("  " + "-" * 60)
    detail = {}
    for lab in ('50-60%', '60-70%', '70-80%', '80-90%', '90%+'):
        g = par_tranche.get(lab, {})
        v = [st.mean(x) for x in g.values()]             # 1 valeur par match
        if len(v) < 8:
            continue
        mm, ll, hh = ic_moy(v)
        signif = (ll > 0 or hh < 0)
        flag = "  ⚠️" if (signif and abs(mm) >= BIAIS_MATERIEL) else ""
        detail[lab] = {'n_matchs': len(v), 'ecart_moyen': round(mm, 3),
                       'ic': [round(ll, 3), round(hh, 3)],
                       'materiel': bool(signif and abs(mm) >= BIAIS_MATERIEL)}
        print(f"  {lab:>15} | {len(v):>5} | {mm:>+11.2f} | [{ll:>+6.2f} ; {hh:>+6.2f}]{flag}")

    print()
    signif = not (lo <= 0 <= hi)
    materiel = abs(m) >= BIAIS_MATERIEL
    if not signif:
        print("  → Shin est INDISCERNABLE du prix Polymarket : le dévigage utilisé")
        print("    partout dans le projet est validé.")
    elif not materiel:
        print(f"  → biais détectable ({m:+.2f} pts) mais SOUS le seuil de matérialité")
        print(f"    de {BIAIS_MATERIEL} pt. Statistiquement réel, pratiquement sans effet :")
        print("    aucune décision du projet ne change pour un tel décalage.")
    else:
        print(f"  → ⚠️ BIAIS SYSTÉMATIQUE ET MATÉRIEL de {m:+.2f} pts. Toutes les mesures")
        print("    passant par Shin (CLV, opening_value, drift_outcome, canal) sont")
        print("    décalées d'autant. À corriger avant toute nouvelle conclusion.")
    print("  ⚠️ ceci suppose que le milieu de fourchette Polymarket est non biaisé.")
    print("    Une fourchette large le rend imprécis, pas forcément faux — mais si")
    print("    l'écart varie fortement selon la tranche, suspecter Polymarket autant")
    print("    que Shin.")
    return {'n_matchs': len(tous), 'n_points': n_points,
            'ecart_moyen': round(m, 3), 'ic': [round(lo, 3), round(hi, 3)],
            'median': round(st.median(tous), 3),
            'significatif': bool(signif), 'materiel': bool(materiel),
            'seuil_materialite': BIAIS_MATERIEL, 'par_tranche': detail}


# ══════════════════════════════════════════════════════════════════════════
def etude_confirmateur(pm, books):
    """2. Polymarket confirme-t-il utilement un mouvement Pinnacle ?"""
    print()
    print("=" * 74)
    print("2. POLYMARKET COMME CONFIRMATEUR — l'écart chez un book mou se")
    print(f"   referme-t-il mieux quand Polymarket confirme ? (mouvement ≥ {MOVE_MIN*100:.0f} pts)")
    print("=" * 74)

    confirme, infirme, muet = [], [], []
    for uid, serie_pm in pm.items():
        bks = books.get(uid, {})
        pin = bks.get(pc.SHARP)
        if not pin:
            continue
        ct = pin['ct']
        p0 = pin['serie'][0][1]
        # instant où Pinnacle a bougé d'au moins MOVE_MIN depuis l'ouverture
        decl = None
        for t, p in pin['serie']:
            if abs(p - p0) >= MOVE_MIN:
                decl = (t, p - p0, p)
                break
        if not decl:
            continue
        t, shift, p_now = decl
        if (ct - t).total_seconds() / 60.0 < 45:
            continue                      # trop tard = bruit d'avant-match
        cote_side = 'home' if shift > 0 else 'away'

        # Polymarket a-t-il bougé dans le même sens sur la même fenêtre ?
        pm_serie = [(x[0], x[1]) for x in serie_pm]
        p_pm_t = pc.valeur_a(pm_serie, t)
        p_pm_0 = pc.valeur_a(pm_serie, t - datetime.timedelta(minutes=LOOKBACK))
        if p_pm_t is None or p_pm_0 is None:
            statut = 'muet'
        else:
            d_pm = p_pm_t - p_pm_0
            if abs(d_pm) < MOVE_MIN / 3:
                statut = 'muet'
            else:
                statut = 'confirme' if (d_pm * shift) > 0 else 'infirme'

        # écart laissé chez un book mou, et son refermement (CLV)
        p_side = p_now if cote_side == 'home' else 1 - p_now
        if p_side <= 0:
            continue
        juste = 1.0 / p_side
        for bk, d in bks.items():
            if bk == pc.SHARP:
                continue
            # cotes = (t, cote_home, cote_away). L'indice 1 correspond à home,
            # 2 à away. Une erreur d'indice ici lit la cote de l'ADVERSAIRE et
            # produit des écarts négatifs partout : le filtre GAP_MIN rejette
            # alors tout, silencieusement. Détecté au test.
            idx = 1 if cote_side == 'home' else 2
            dispo = [(x[0], x[idx]) for x in d['cotes']]
            cur = pc.valeur_a(dispo, t)
            if cur is None or not dispo:
                continue
            close = dispo[-1][1]
            if close <= 1 or cur / juste - 1 < GAP_MIN:
                continue
            clv = (cur / close - 1) * 100.0
            {'confirme': confirme, 'infirme': infirme, 'muet': muet}[statut].append(clv)

    lignes = []
    print(f"  {'Polymarket':>12} | {'n écarts':>9} | {'CLV médian':>11} | "
          f"{'CLV moyen':>10} | {'IC95':>18}")
    print("  " + "-" * 68)
    res = {}
    for lab, v in (('confirme', confirme), ('infirme', infirme), ('muet', muet)):
        if len(v) < 5:
            print(f"  {lab:>12} | {len(v):>9} | trop peu")
            continue
        m, lo, hi = ic_moy(v)
        res[lab] = {'n': len(v), 'median': round(st.median(v), 2),
                    'moyen': round(m, 2), 'ic': [round(lo, 2), round(hi, 2)]}
        print(f"  {lab:>12} | {len(v):>9} | {st.median(v):>+10.1f}% | "
              f"{m:>+9.1f}% | [{lo:>+6.1f} ; {hi:>+6.1f}]")
        lignes.append((lab, m, lo, hi))

    print()
    if 'confirme' in res and 'infirme' in res:
        d = res['confirme']['moyen'] - res['infirme']['moyen']
        chev = not (res['confirme']['ic'][0] > res['infirme']['ic'][1]
                    or res['infirme']['ic'][0] > res['confirme']['ic'][1])
        print(f"  différentiel confirme - infirme : {d:+.1f} pts de CLV")
        if chev:
            print("  → les intervalles se CHEVAUCHENT : aucun apport démontré.")
        else:
            print("  → intervalles disjoints. Piste à geler et valider hors échantillon.")
    else:
        print("  → pas encore assez d'écarts dans les deux groupes pour comparer.")
    return res


# ══════════════════════════════════════════════════════════════════════════
def etude_divergence(pm, books, resultats):
    """3. En cas de désaccord, qui prédit le mieux ?"""
    print()
    print("=" * 74)
    print(f"3. DIVERGENCE ≥ {DIVERG_MIN*100:.0f} PTS — qui a raison, Polymarket ou {pc.SHARP} ?")
    print("=" * 74)
    if not resultats:
        print("  set_results.json introuvable ou vide.")
        return {}

    pm_ok, pin_ok, ecarts = [], [], []
    for uid, serie_pm in pm.items():
        w = resultats.get(uid)
        if w not in ('home', 'away'):
            continue
        b = books.get(uid, {}).get(pc.SHARP)
        if not b:
            continue
        pts = pc.instants_communs([(x[0], x[1]) for x in serie_pm], b['serie'], b['ct'])
        if not pts:
            continue
        # dernier instant commun pré-match = état final des deux marchés
        t, p_pm, p_pin = pts[-1]
        d = p_pm - p_pin
        if abs(d) < DIVERG_MIN:
            continue
        ecarts.append(d * 100)
        gagnant_home = (w == 'home')
        # chacun "prédit" le côté auquel il donne la plus forte probabilité
        pm_ok.append(1.0 if ((p_pm > 0.5) == gagnant_home) else 0.0)
        pin_ok.append(1.0 if ((p_pin > 0.5) == gagnant_home) else 0.0)

    if len(pm_ok) < 5:
        print(f"  {len(pm_ok)} match(s) divergent(s) avec résultat connu — trop peu.")
        print("  Il en faut plusieurs centaines : compter quelques semaines.")
        return {'n': len(pm_ok)}

    a, alo, ahi = ic_prop(pm_ok)
    c, clo, chi = ic_prop(pin_ok)
    print(f"  n = {len(pm_ok)} matchs où les deux s'écartent de ≥ {DIVERG_MIN*100:.0f} pts")
    print(f"  écart médian : {st.median(ecarts):+.1f} pts (Polymarket - {pc.SHARP})")
    print()
    print(f"  {'Polymarket a raison':>22} : {a*100:5.1f}%  IC95 [{alo*100:5.1f} ; {ahi*100:5.1f}]")
    print(f"  {pc.SHARP + ' a raison':>22} : {c*100:5.1f}%  IC95 [{clo*100:5.1f} ; {chi*100:5.1f}]")
    print()
    if alo > chi:
        print("  → Polymarket devance nettement. À confirmer hors échantillon.")
    elif clo > ahi:
        print(f"  → {pc.SHARP} devance nettement : Polymarket n'apporte rien ici.")
    else:
        print("  → intervalles chevauchants : AUCUN des deux ne devance l'autre.")
    return {'n': len(pm_ok), 'pm': round(a, 3), 'sharp': round(c, 3),
            'ic_pm': [round(alo, 3), round(ahi, 3)],
            'ic_sharp': [round(clo, 3), round(chi, 3)]}


def main():
    quoi = (sys.argv[1] if len(sys.argv) > 1 else 'all').lower()
    pm = pc.charger_pm()
    if not pm:
        print("\n❌ aucune série Polymarket. Le collecteur a-t-il tourné ?")
        return
    books = pc.charger_books(set(pm))
    n_pin = sum(1 for u in books if pc.SHARP in books[u])
    print(f"Books      : {len(books)} match(s), dont {n_pin} avec {pc.SHARP}")
    if not n_pin:
        print("\n❌ aucun match commun entre ticks Polymarket et courbes.")
        return

    rapport = {'genere_le': datetime.datetime.utcnow().isoformat(timespec='seconds')}
    if quoi in ('devig', 'all'):
        rapport['devigage'] = etude_devig(pm, books)
    if quoi in ('confirm', 'all'):
        rapport['confirmateur'] = etude_confirmateur(pm, books)
    if quoi in ('divergence', 'all'):
        rapport['divergence'] = etude_divergence(pm, books, pc.charger_resultats())

    import json
    json.dump(rapport, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
