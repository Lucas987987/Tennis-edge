#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alert_control_test.py — LE test décisif : le filtre d'alerte apporte-t-il
quelque chose par rapport à suivre TOUS les mouvements Pinnacle ?

LA QUESTION, ET POURQUOI LES TESTS PRÉCÉDENTS N'Y RÉPONDENT PAS
Un premier test de contrôle comparait, DANS UN MÊME MATCH, les books signalés
(+11,9 % de CLV) aux books non signalés (+1,4 %). Il prouve que la détection
identifie bien un retardataire parmi les opérateurs.
Mais il ne dit RIEN de l'utilité du filtre au niveau du MATCH. Car le groupe
témoin n'existe pas dans ce test : tous les matchs comparés avaient déclenché
une alerte.

Le vrai contrefactuel est celui-ci :
    GROUPE ALERTE  Pinnacle bouge + un book traîne  -> on publie
    GROUPE TÉMOIN  Pinnacle bouge + aucun book ne traîne -> on ne publie pas
Si le CLV du témoin est proche de celui des alertes, le filtre n'ajoute presque
rien : il suffirait de suivre tout mouvement Pinnacle. S'il est SUPÉRIEUR, le
filtre DÉTRUIT de la valeur — il écarte les meilleures occasions.

Illustration du raisonnement :
    témoin +8 %  vs alertes +12 %  -> le filtre apporte +4 points. Excellent.
    témoin +11 % vs alertes +12 %  -> apport marginal, à peine défendable.
    témoin +13 % vs alertes +12 %  -> le filtre coûte de la valeur.

LES DEUX LECTURES
  1. « Même mesure » : CLV du MEILLEUR book des deux côtés. Comparaison
     honnête d'une même grandeur, alerte ou pas.
  2. « Décision réelle » : ce qu'un abonné obtient en suivant les alertes,
     contre ce qu'il obtiendrait en suivant tout mouvement Pinnacle.

LA MATRICE 2x2
Second axe : le marché de prédiction confirme-t-il le mouvement Pinnacle ?
        A  retard + confirmation      B  retard + divergence
        C  pas de retard + confirm.   D  pas de retard + divergence
Croiser les deux dimensions dit lequel des deux filtres porte l'information —
et s'ils se cumulent. Aucune étude prise séparément ne peut le dire.

GARDE-FOUS
  • Coupe PRÉ-MATCH stricte : le dernier point de courbe est in-play et encode
    déjà le déroulement du match. Quatre faux positifs de ce projet viennent
    de là, dont un Pinnacle mesuré à 95,5 % de précision.
  • Une observation par MATCH CANONIQUE (match_key.py) : deux conventions
    d'uid ont coexisté et 208 uid désignaient un match déjà compté.
  • Exchanges exclus : sans marge à rattraper, ils paraissent toujours « en
    retard » sans l'être.
  • Test de permutation : on rebat l'étiquette alerte/témoin au hasard. Si
    l'écart ressort autant, il n'y a rien.

Env : CURVES, SHARP_BOOK, PALIERS, GAP_MIN_PCT, MIN_LEAD_MIN, MAX_MAG_PTS,
      N_PERMUT, OUT.
Usage : python scripts/alert_control_test.py
"""
import os
import sys
import json
import math
import random
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov      # noqa: E402
import match_key as mk        # noqa: E402

CURVES = os.environ.get('CURVES', 'book_curves_live.jsonl')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
PALIERS = [float(x) / 100 for x in os.environ.get('PALIERS', '5,8,12').split(',')]
GAP_MIN = float(os.environ.get('GAP_MIN_PCT', '3')) / 100
MIN_LEAD = float(os.environ.get('MIN_LEAD_MIN', '45'))
MAX_LEAD = float(os.environ.get('MAX_LEAD_MIN', '2880'))
MAX_MAG = float(os.environ.get('MAX_MAG_PTS', '20')) / 100
N_PERMUT = int(os.environ.get('N_PERMUT', '400'))
OUT = os.environ.get('OUT', 'alert_control_report.json')
EXCHANGES = set(b.strip() for b in os.environ.get(
    'EXCHANGES', 'betfair-ex,betfair,matchbook,smarkets,betdaq').split(',') if b.strip())
PM_GLOB = os.environ.get('PM_TICKS_GLOB', '')
INDEX_CANONIQUE = None      # rempli par charger()


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def shin_ph(oh, oa):
    """Probabilité du home, marge retirée par itération sur z (Shin)."""
    try:
        ih, ia = 1.0 / float(oh), 1.0 / float(oa)
    except Exception:
        return None
    s = ih + ia
    if s <= 0:
        return None
    if s <= 1:
        return ih / s
    z, ph, pa = 0.02, None, None
    for _ in range(50):
        ph = (math.sqrt(z * z + 4 * (1 - z) * ih * ih / s) - z) / (2 * (1 - z))
        pa = (math.sqrt(z * z + 4 * (1 - z) * ia * ia / s) - z) / (2 * (1 - z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t - 1), 0.0), 0.3)
    return ph / (ph + pa) if (ph and pa) else None


def valeur_a(seq, t):
    v = None
    for ts, p in seq:
        if ts > t:
            break
        v = p
    return v


def charger():
    """{uid_canonique: {book: [(t, cote_home, cote_away)], '_ct': commence}}"""
    brut, recs = collections.defaultdict(dict), []
    for src in (CURVES, 'book_curves.jsonl'):
        try:
            lignes = list(ov.open_curves(src, verbose=False))
        except Exception:
            continue
        for ligne in lignes:
            try:
                r = json.loads(ligne)
            except Exception:
                continue
            bk = r.get('book')
            ct = _dt(r.get('commence_time'))
            if not bk or not ct or bk in EXCHANGES:
                continue
            recs.append(r)
            # COUPE PRÉ-MATCH : un point postérieur au coup d'envoi encode
            # déjà le déroulement de la rencontre.
            h = sorted((_dt(q[0]), float(q[1])) for q in (r.get('home_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1 and _dt(q[0]) < ct)
            a = sorted((_dt(q[0]), float(q[1])) for q in (r.get('away_curve') or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1 and _dt(q[0]) < ct)
            if len(h) < 2 or len(a) < 2:
                continue
            brut[r['uid']][bk] = {'h': h, 'a': a}
            brut[r['uid']]['_ct'] = ct
            # NOMS RÉELS de la courbe. La clé canonique (match_key) TRIE les
            # joueurs par ordre alphabétique : son premier joueur n'est donc
            # PAS le 'home' des courbes. Interroger les résultats avec la clé
            # revient à tirer l'orientation à pile ou face — et le contrôle de
            # calibration ne le détecte pas, puisqu'une orientation aléatoire
            # ramène le taux de réussite vers 50 %, ce qui paraît normal.
            brut[r['uid']]['_home'] = r.get('home_team') or r.get('home')
            brut[r['uid']]['_away'] = r.get('away_team') or r.get('away')

    idx = mk.build_index(recs)
    # L'index est exposé au niveau du module : les autres scripts en ont besoin
    # pour traduire leurs propres uid en clés canoniques. Sans ça, la jointure
    # avec set_results.json échoue silencieusement — 0 pari simulé sur 1230
    # matchs, constaté le 22/08/2026.
    global INDEX_CANONIQUE
    INDEX_CANONIQUE = idx
    out = {}
    for uid, d in brut.items():
        k = idx.key_of(uid)
        if k not in out:              # doublon d'uid : le même match
            out[k] = d
    print(f"{len(brut)} uid -> {len(out)} match(s) canonique(s)")
    return out


def declenchement(pin, ct):
    """Premier instant où le mouvement Pinnacle franchit le plus petit palier,
    dans la fenêtre de publication. Reproduit canal_public."""
    h, a = pin['h'], pin['a']
    p0 = shin_ph(h[0][1], a[0][1])
    if p0 is None:
        return None
    pmin = min(PALIERS)
    for t in sorted({x[0] for x in h} | {x[0] for x in a}):
        oh, oa = valeur_a(h, t), valeur_a(a, t)
        if not oh or not oa:
            continue
        lead = (ct - t).total_seconds() / 60
        if lead > MAX_LEAD:
            continue
        if lead < MIN_LEAD:
            break
        p1 = shin_ph(oh, oa)
        if p1 is None:
            continue
        mag = abs(p1 - p0)
        if pmin <= mag <= MAX_MAG:
            return t, p1 - p0, p1
    return None


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def ligne(lab, v):
    if len(v) < 5:
        return f"  {lab:<34}{len(v):>5}   trop peu"
    m, lo, hi = ic(v)
    return (f"  {lab:<34}{len(v):>5}{st.median(v):>+9.1f}%{m:>+9.1f}%"
            f"  [{lo:>+6.1f} ; {hi:>+6.1f}]")


def main():
    matchs = charger()
    if not matchs:
        print("❌ aucune courbe exploitable.")
        return

    # Confirmation par le marché de prédiction (optionnelle, 2e axe).
    pm = {}
    if PM_GLOB:
        try:
            import polymarket_common as pc
            pm = pc.charger_pm()
        except Exception as e:
            print(f"⚠️ marché de prédiction indisponible : {e}")

    alerte, temoin = [], []
    quad = collections.defaultdict(list)
    n_sans_move = 0
    for uid, d in matchs.items():
        pin = d.get(SHARP)
        ct = d.get('_ct')
        if not pin or not ct:
            continue
        decl = declenchement(pin, ct)
        if not decl:
            n_sans_move += 1
            continue
        t, shift, p_now = decl
        side = 'h' if shift > 0 else 'a'
        p_side = p_now if side == 'h' else 1 - p_now
        if p_side <= 0:
            continue
        juste = 1.0 / p_side

        # Écart et CLV de CHAQUE book mou, au même instant.
        clvs, gaps = [], []
        for bk, s in d.items():
            if bk.startswith('_') or bk == SHARP:
                continue
            seq = s[side]
            cur = valeur_a(seq, t)
            close = seq[-1][1]
            if not cur or close <= 1:
                continue
            gaps.append((cur / juste - 1, (cur / close - 1) * 100, bk))
        if not gaps:
            continue
        gaps.sort(reverse=True)
        meilleur_gap, meilleur_clv, _ = gaps[0]
        flagges = [c for g, c, _ in gaps if g >= GAP_MIN]

        obs = {'uid': uid, 'meilleur_clv': meilleur_clv,
               'clv_flagges': st.mean(flagges) if flagges else None,
               'gap': meilleur_gap * 100, 'shift': shift * 100}

        if flagges:
            alerte.append(obs)
        else:
            temoin.append(obs)

        # ── 2e axe : le marché de prédiction confirme-t-il ? ──────────────
        if pm:
            serie = pm.get(uid)
            if serie:
                s2 = [(x[0], x[1]) for x in serie]
                p_t = valeur_a(s2, t)
                p_av = valeur_a(s2, t - datetime.timedelta(minutes=30))
                if p_t is not None and p_av is not None:
                    d_pm = p_t - p_av
                    conf = (d_pm * shift) > 0 if abs(d_pm) > 0.005 else None
                    if conf is not None:
                        g = ('A' if flagges else 'C') if conf else ('B' if flagges else 'D')
                        quad[g].append(meilleur_clv)

    print(f"{n_sans_move} match(s) sans mouvement Pinnacle exploitable\n")
    print("=" * 78)
    print("LE FILTRE D'ALERTE APPORTE-T-IL QUELQUE CHOSE ?")
    print(f"Mouvement Pinnacle >= {min(PALIERS)*100:.0f} pts · "
          f"écart book >= {GAP_MIN*100:.0f} % pour déclencher")
    print("=" * 78)
    print(f"  {'groupe':<34}{'n':>5}{'médian':>10}{'moyen':>9}{'IC95 (moyen)':>20}")
    print("-" * 78)

    a_best = [o['meilleur_clv'] for o in alerte]
    t_best = [o['meilleur_clv'] for o in temoin]
    a_flag = [o['clv_flagges'] for o in alerte if o['clv_flagges'] is not None]

    print("  — même mesure des deux côtés : CLV du MEILLEUR book —")
    print(ligne("ALERTE  (un book traîne)", a_best))
    print(ligne("TÉMOIN  (aucun book ne traîne)", t_best))
    print()
    print("  — décision réelle de l'abonné —")
    print(ligne("suivre les alertes", a_flag))
    print(ligne("suivre TOUT mouvement Pinnacle", a_best + t_best))

    verdict = {}
    if len(a_best) >= 5 and len(t_best) >= 5:
        ma, la, ha = ic(a_best)
        mt, lt, ht = ic(t_best)
        ecart = ma - mt
        chevauche = not (la > ht or lt > ha)
        print()
        print(f"  APPORT DU FILTRE : {ecart:+.1f} points de CLV moyen")
        if chevauche:
            print("  → les intervalles se CHEVAUCHENT : apport NON démontré.")
            print("    Suivre tout mouvement Pinnacle donnerait un résultat")
            print("    statistiquement indiscernable.")
        elif ecart > 0:
            print("  → intervalles disjoints et écart POSITIF : le filtre ajoute")
            print("    de la valeur. À confirmer hors échantillon.")
        else:
            print("  ⚠️ intervalles disjoints et écart NÉGATIF : le filtre")
            print("    DÉTRUIT de la valeur — il écarte les meilleures occasions.")
        verdict = {'apport_pts': round(ecart, 2), 'chevauchement': bool(chevauche),
                   'n_alerte': len(a_best), 'n_temoin': len(t_best)}

        # ── Permutation : l'étiquette alerte/témoin est-elle informative ? ─
        tous = a_best + t_best
        rng = random.Random(20260822)
        na = len(a_best)
        nul = []
        for _ in range(N_PERMUT):
            rng.shuffle(tous)
            nul.append(st.mean(tous[:na]) - st.mean(tous[na:]))
        nul.sort()
        seuil = nul[int(0.95 * (len(nul) - 1))]
        print(f"\n  Seuil de bruit (95e centile, {N_PERMUT} rebattages) : {seuil:+.1f} pts")
        if ecart <= seuil:
            print("  → l'écart n'excède pas ce que produit une étiquette TIRÉE AU")
            print("    HASARD. Rien de démontré.")
        verdict['seuil_bruit'] = round(seuil, 2)
        verdict['depasse_bruit'] = bool(ecart > seuil)

    # ── Matrice 2x2 ───────────────────────────────────────────────────────
    if quad:
        print()
        print("=" * 78)
        print("MATRICE 2x2 — retard du book × confirmation du marché de prédiction")
        print("=" * 78)
        print(f"  {'groupe':<34}{'n':>5}{'médian':>10}{'moyen':>9}{'IC95 (moyen)':>20}")
        print("-" * 78)
        libelles = {'A': 'A  retard + confirmation',
                    'B': 'B  retard + divergence',
                    'C': 'C  pas de retard + confirmation',
                    'D': 'D  pas de retard + divergence'}
        for g in ('A', 'B', 'C', 'D'):
            print(ligne(libelles[g], quad.get(g, [])))
        print()
        print("  Lecture : si A >> B, la confirmation du marché de prédiction")
        print("  ajoute quelque chose AU-DELÀ du retard. Si A ≈ B, elle n'apporte")
        print("  rien. Si C ≈ A, c'est le retard qui n'apporte rien.")
    elif PM_GLOB:
        print("\n  (matrice 2x2 : pas assez de matchs communs avec le marché "
              "de prédiction)")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'palier_min_pts': min(PALIERS) * 100, 'gap_min_pct': GAP_MIN * 100,
        'verdict': verdict,
        'groupes': {
            'alerte_meilleur': {'n': len(a_best),
                                'median': round(st.median(a_best), 2) if a_best else None},
            'temoin_meilleur': {'n': len(t_best),
                                'median': round(st.median(t_best), 2) if t_best else None},
            'alerte_flagges': {'n': len(a_flag),
                               'median': round(st.median(a_flag), 2) if a_flag else None},
        },
        'matrice': {g: {'n': len(v), 'median': round(st.median(v), 2)}
                    for g, v in quad.items() if v},
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
