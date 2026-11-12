#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_statistiques_annoncees.py — les statistiques annoncées et leur fourchette, rejouées sur l'archive
(12/11/2026, audit, paquet 237)

D'où vient la question. Le site annonce pour chaque joueur des aces, des doubles fautes, un % de 1res balles et des
breaks, avec une fourchette « 8 fois sur 10 ». Le recalage en place (recalage_stats.py) est appris sur nos matchs
suivis : quelques centaines de cas par case. L'audit a relevé que c'est trop peu pour régler une largeur.

Rejeu. Archive Sackmann 2018 → juin 2026 ; profils service / retour ajustés à chaque trimestre comme en production
(ajustement.ajuster, mêmes n0), niveau ancré sur l'Elo de production corrigé des pentes en place, match joué N_SIM fois
(match_simule.simuler, écart type de la forme du jour du circuit, élargissement de la 1re balle compris). Les
facteurs du match adoptés chaque semaine ne sont pas rejoués. Un match sur PAS[circuit], choisi par son numéro.
Une ligne = un joueur, un match, une statistique : annoncé (moyenne, fourchette 10e–90e centile) et réel.

RÈGLE ÉCRITE À L'AUDIT (rapport_audit.json, constat « statistiques_annoncees », paquet 227) :
  décalages et largeurs appris sur l'archive rejouée (profil contre réel, par circuit et par statistique, 2018–2022),
  jugés sur 2023 → : couverture entre 78 et 82 % sur au moins 1 000 cas par case.
PRÉCISIONS ÉCRITES LE 12/11/2026, AVANT DE LANCER LE REJEU :
  - apprentissage 2019–2022 (2018 sert à constituer les profils) ; même méthode que recalage_stats.apprendre
    (décalage = écart moyen ; largeur sur la grille 0,50 … 2,00 pour approcher 80 %) ;
  - une case est « réglée » si, sur 2023 → juin 2026, sa couverture recalée est entre 78 et 82 % sur ≥ 1 000 cas ;
  - CONTRÔLE AVANT TOUTE MISE EN PRODUCTION, sur nos matchs suivis (réel = feuilles en direct, une AUTRE source que
    l'archive) : pour une case, les coefficients de l'archive ne remplacent ceux en place que si, sur nos cas (au moins
    150), la couverture n'est pas plus loin de 80 % et l'écart moyen |annoncé − réel| n'est pas plus grand qu'avec ce
    qui est en place. Un décalage appris sur l'archive n'est pas transposé si le biais mesuré en direct est de signe
    contraire ou plus de deux fois plus grand : il vient alors de la source, pas du modèle.
  Rien ne change le % de victoire.

SECOND VOLET — LA SAISON (ajouté le 12/11/2026 après le premier résultat). Sur l'archive, le % de 1res balles annoncé
n'a pas de biais d'ensemble (+0,3 point en ATP), alors qu'en direct, fin octobre et début novembre, il est 3 à 4 points
trop bas. Le biais par mois, lu sur 2019–2022, montre une saison : en ATP +1,6 à +1,9 point en janvier, octobre et
novembre (tournois en salle), −1,4 à −1,8 en juillet et août (plein air, chaleur). L'archive ne dit pas si un tournoi
se joue en salle : le mois en tient lieu.
RÈGLE ÉCRITE LE 12/11/2026 AVANT DE JUGER (aveu : le biais d'octobre-novembre 2023–2025 en ATP, +2,6 points, avait été
vu avant d'écrire cette règle ; aucune autre mesure de la période jugée) :
  un décalage par circuit et par mois pour le % de 1res balles = biais du mois sur 2019–2022, réduit par n / (n + 300) ;
  jugé une seule fois sur 2023 → juin 2026, par circuit : RETENU si la moyenne des |biais mensuels| (mois d'au moins
  200 cas) baisse d'au moins un tiers ET si l'écart moyen |annoncé − réel| ne monte pas, sur au moins 1 000 cas.
  En production, le décalage du mois s'applique AVANT le recalage appris en direct, à l'affichage comme à
  l'apprentissage (sinon il serait compté deux fois).

Usage : python simulateur/etude_statistiques_annoncees.py /tmp/sackmann . [--lignes cache.json.gz]
"""
import datetime as dt
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import recalage_stats as RS  # noqa: E402

DEBUT, COUPURE, FIN = dt.date(2019, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
PAS = {'ATP': 2, 'WTA': 2, 'CH': 8}
N_SIM = 400
MIN_CAS, BORNES, MIN_CAS_DIRECT = 1000, (78.0, 82.0), 150
SORTIE = os.path.join(ICI, 'rapport_statistiques_annoncees.json')


def reels(det_j, det_adv):
    """Statistiques réelles d'un joueur à partir du détail de l'archive (donnees.DETAIL)."""
    return {'aces': float(det_j[4]), 'doubles_fautes': float(det_j[5]),
            'premiere_pct': 100.0 * det_j[1] / det_j[0] if det_j[0] else None,
            'breaks': float(det_adv[6] - det_adv[7])}


def lignes(archive, racine, n_sim=N_SIM, pas=None, journal=True, simuler=True):
    """simuler=False : les mêmes matchs dans le même ordre, sans profil ni simulation (une ligne par match : jour, circuit,
    tournoi, surface) — pour rattacher une information du match aux lignes déjà rejouées."""
    import ajustement as AJ
    import donnees as DN
    import elo as E
    import etude_outsiders as EO
    import etude_signaux_reappris as ER
    import match_simule as MS
    import pronostics_du_jour as PJ
    pas = pas or PAS
    with open(os.path.join(racine, 'simulateur', 'choix_simulation.json'), encoding='utf-8') as f:
        ch = json.load(f)
    n0, n0c = float(ch.get('n0') or AJ.N0), ch.get('n0_par_composante') or None
    sigmas = PJ.charger_sigma_circuit(racine) or {}
    reglages = PJ.charger_reglages(racine)
    fmt, gc = ER.pentes_en_place(racine)
    Mt = DN.charger(archive, 2018)
    Mt.sort(key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0)))
    k = E.cle
    el, bas = E.de_production(racine)

    def maj(m):
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            return
        if bas and m['circuit'] in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        el.maj(g, p, m['surface'], m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)

    for m in sorted((x for x in DN.charger(archive, 2012) if Mt and x['date'] < Mt[0]['date']),
                    key=lambda x: (x['date'], x.get('tour', 0), x.get('num', 0))):
        maj(m)
    T = sorted(dt.date(y, mo, 1) for y in range(2018, FIN.year + 1) for mo in (1, 4, 7, 10) if dt.date(2018, 10, 1) <= dt.date(y, mo, 1) < FIN)
    rows, A, ti = [], None, -1
    for m in Mt:
        d = m['date']
        while ti + 1 < len(T) and d >= T[ti + 1]:
            ti += 1
            A = AJ.ajuster(Mt, T[ti], k, n0=n0, n0_par_composante=n0c) if simuler else True
            if journal and simuler:
                print(f"ajustement au {T[ti]} ({len(rows)} lignes)", flush=True)
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m['surface']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        det = m.get('detail')
        if (A is not None and c in pas and DEBUT <= d < FIN and m.get('complet') and not m.get('abandon') and m.get('sets')
                and m.get('niveau') != 'D' and det and det.get('w') and det.get('l') and det['w'][0] and det['l'][0]
                and int(m.get('num') or 0) % pas[c] == 0 and el.matchs(g) >= 10 and el.matchs(p) >= 10):
            if not simuler:
                rows.append({'jour': d.isoformat(), 'c': c, 'tournoi': m.get('tournoi'), 'surface': s})
                maj(m)
                continue
            pg = EO._sg(ER.pente_du_match(m, fmt, gc) * EO._lg(el.proba(g, p, s)))
            pg = min(max(pg, 0.02), 0.98)
            sg = 3 if m.get('bo') == 5 else 2
            cG, cP = MS.composantes_ajustees(A, g, p, c, s), MS.composantes_ajustees(A, p, g, c, s)
            r = MS.simuler(cG, cP, pg, sg, n_sim, sigmas.get(c, PJ.SIGMA), cle=f"{m.get('tournoi_id')}|{m.get('num')}",
                           reglages=reglages, circuit=c)
            for i, (dj, da) in enumerate(((det['w'], det['l']), (det['l'], det['w']))):
                vrai = reels(dj, da)
                for stat in RS.STATS:
                    f = r['feuille'][i].get(stat)
                    if f and vrai[stat] is not None and f.get('p10') is not None:
                        rows.append({'jour': d.isoformat(), 'c': c, 'k': stat, 'moy': float(f['moy']), 'p10': float(f['p10']),
                                     'p90': float(f['p90']), 'reel': float(vrai[stat]), 'tournoi': m.get('tournoi'), 'surface': s})
        maj(m)
    return rows


def biais(rows):
    out = {}
    for c in RS.CIRCUITS:
        for stat in RS.STATS:
            R = [r for r in rows if r['c'] == c and r['k'] == stat]
            if R:
                out[f'{c}|{stat}'] = {'n': len(R), 'biais': round(sum(r['reel'] - r['moy'] for r in R) / len(R), 3)}
    return out


STAT_SAISON, PRIOR_SAISON, MIN_MOIS, REDUCTION_MIN = 'premiere_pct', 300.0, 200, 1 / 3


def _par_mois(rows, c, decalages=None):
    G = {}
    for r in rows:
        if r['c'] == c and r['k'] == STAT_SAISON:
            mois = int(r['jour'][5:7])
            G.setdefault(mois, []).append(r['reel'] - r['moy'] - ((decalages or {}).get(str(mois), 0.0)))
    return G


def apprendre_saison(appr):
    """{circuit: {mois: décalage du % de 1res balles}} — biais du mois réduit par n / (n + 300)."""
    return {c: {str(m): round(sum(v) / len(v) * len(v) / (len(v) + PRIOR_SAISON), 2) for m, v in sorted(_par_mois(appr, c).items())}
            for c in RS.CIRCUITS}


def juger_saison(rows):
    appr = [r for r in rows if r['jour'] < COUPURE.isoformat()]
    juge = [r for r in rows if r['jour'] >= COUPURE.isoformat()]
    S = apprendre_saison(appr)
    out = {}
    for c in RS.CIRCUITS:
        avant, apres = _par_mois(juge, c), _par_mois(juge, c, S[c])
        mois = [m for m, v in avant.items() if len(v) >= MIN_MOIS]
        n = sum(len(v) for v in avant.values())
        b0 = sum(abs(sum(avant[m]) / len(avant[m])) for m in mois) / max(1, len(mois))
        b1 = sum(abs(sum(apres[m]) / len(apres[m])) for m in mois) / max(1, len(mois))
        e0 = sum(abs(x) for v in avant.values() for x in v) / max(1, n)
        e1 = sum(abs(x) for v in apres.values() for x in v) / max(1, n)
        raisons = []
        if n < MIN_CAS:
            raisons.append(f"moins de {MIN_CAS} cas")
        if b1 > b0 * (1 - REDUCTION_MIN):
            raisons.append("le biais mensuel ne baisse pas d'un tiers")
        if e1 > e0:
            raisons.append("l'écart moyen monte")
        out[c] = {'decalages_par_mois': S[c], 'cas_juges': n, 'mois_juges': len(mois),
                  'biais_mensuel_moyen': {'avant': round(b0, 3), 'apres': round(b1, 3)},
                  'ecart_moyen': {'avant': round(e0, 3), 'apres': round(e1, 3)},
                  'biais_par_mois_2023': {str(m): {'avant': round(sum(avant[m]) / len(avant[m]), 2), 'apres': round(sum(apres[m]) / len(apres[m]), 2),
                                                  'cas': len(avant[m])} for m in sorted(mois)},
                  'retenu': not raisons, 'raisons': raisons}
    return out


def juger(rows, directs=None, en_place=None):
    appr = [r for r in rows if r['jour'] < COUPURE.isoformat()]
    juge = [r for r in rows if r['jour'] >= COUPURE.isoformat()]
    coefs = RS.apprendre(appr)
    sans, avec = RS.mesurer(juge), RS.mesurer(juge, coefs)
    b_appr, b_juge = biais(appr), biais(juge)
    b_dir = biais(directs) if directs else {}
    d_sans = RS.mesurer(directs) if directs else {'cases': {}}
    d_arch = RS.mesurer(directs, coefs) if directs else {'cases': {}}
    d_place = RS.mesurer(directs, en_place) if directs else {'cases': {}}
    cases = {}
    for c in RS.CIRCUITS:
        for stat in RS.STATS:
            cle = f'{c}|{stat}'
            co = (coefs.get(c) or {}).get(stat)
            a, s0 = avec['cases'].get(cle) or {}, sans['cases'].get(cle) or {}
            reglee = bool(co and a.get('n', 0) >= MIN_CAS and BORNES[0] <= a.get('couverture', 0) <= BORNES[1])
            x = {'coefficients': {'delta': round(co['delta'], 3), 'largeur': co['largeur']} if co else None,
                 'biais_2019_2022': (b_appr.get(cle) or {}).get('biais'), 'biais_2023': (b_juge.get(cle) or {}).get('biais'),
                 'cas_juges': a.get('n', 0), 'couverture_sans': s0.get('couverture'), 'couverture_recalee': a.get('couverture'),
                 'ecart_sans': s0.get('ecart'), 'ecart_recale': a.get('ecart'), 'reglee_sur_l_archive': reglee}
            if directs:
                ds, da, dp = d_sans['cases'].get(cle) or {}, d_arch['cases'].get(cle) or {}, d_place['cases'].get(cle) or {}
                bd = (b_dir.get(cle) or {}).get('biais')
                x['en_direct'] = {'cas': ds.get('n', 0), 'biais': bd,
                                  'couverture': {'sans': ds.get('couverture'), 'archive': da.get('couverture'), 'en_place': dp.get('couverture')},
                                  'ecart': {'sans': ds.get('ecart'), 'archive': da.get('ecart'), 'en_place': dp.get('ecart')}}
                raisons = []
                if not reglee:
                    raisons.append("pas réglée sur l'archive")
                if ds.get('n', 0) < MIN_CAS_DIRECT:
                    raisons.append(f"moins de {MIN_CAS_DIRECT} cas en direct")
                elif da and dp:
                    if abs(da['couverture'] - RS.CIBLE) > abs(dp['couverture'] - RS.CIBLE):
                        raisons.append("couverture en direct plus loin de 80 % qu'avec ce qui est en place")
                    if da['ecart'] > dp['ecart']:
                        raisons.append("écart moyen en direct plus grand qu'avec ce qui est en place")
                if co and bd is not None and abs(co['delta']) >= 0.05 and (co['delta'] * bd < 0 or abs(bd) > 2 * abs(co['delta'])):
                    raisons.append("biais en direct de signe contraire ou plus de deux fois plus grand : il vient de la source")
                x['remplace_ce_qui_est_en_place'] = not raisons
                x['raisons'] = raisons
            cases[cle] = x
    return {'cas': {'apprentissage': len(appr), 'jugement': len(juge), 'en_direct': len(directs or [])}, 'cases': cases}


def main(argv):
    archive, racine = argv[1], (argv[2] if len(argv) > 2 and not argv[2].startswith('--') else '.')
    cache = argv[argv.index('--lignes') + 1] if '--lignes' in argv else None
    if cache and os.path.exists(cache):
        with gzip.open(cache, 'rt', encoding='utf-8') as f:
            rows = json.load(f)
    else:
        rows = lignes(archive, racine)
        if cache:
            with gzip.open(cache, 'wt', encoding='utf-8') as f:
                json.dump(rows, f)
    try:
        directs, en_place = RS.charger(racine), RS.lire_coefs(racine)
    except Exception:  # noqa: BLE001 — pas de fiches en direct : le contrôle est sauté, rien n'est transposé
        directs, en_place = None, None
    doc = juger(rows, directs, en_place)
    doc['saison_premieres_balles'] = juger_saison(rows)
    doc.update(genere_le=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               regle=("décalages et largeurs appris sur l'archive rejouée (2019–2022), jugés sur 2023 → juin 2026 : couverture entre "
                      "78 et 82 % sur au moins 1 000 cas par case ; puis contrôle sur nos matchs suivis avant toute mise en production"),
               rejeu={'simulations_par_match': N_SIM, 'un_match_sur': PAS,
                      'limites': "les facteurs du match adoptés chaque semaine ne sont pas rejoués ; le niveau est ancré sur l'Elo corrigé, pas sur le mélange complet"},
               en_production=False)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(doc['cas'])
    for cle, x in doc['cases'].items():
        e = x.get('en_direct') or {}
        print(f"{cle:20s} biais {x['biais_2019_2022']:+.2f} / {x['biais_2023']:+.2f} | coef {x['coefficients']} | jugés {x['cas_juges']} : couverture "
              f"{x['couverture_sans']} → {x['couverture_recalee']} {'RÉGLÉE' if x['reglee_sur_l_archive'] else ''} | direct n={e.get('cas')} biais {e.get('biais')} "
              f"couv {e.get('couverture')} écart {e.get('ecart')} | remplace : {x.get('remplace_ce_qui_est_en_place')} {x.get('raisons')}")
    for c, v in doc['saison_premieres_balles'].items():
        print(f"SAISON {c} : {v['cas_juges']} cas, biais mensuel moyen {v['biais_mensuel_moyen']}, écart moyen {v['ecart_moyen']} | "
              f"retenu : {v['retenu']} {v['raisons']} | décalages {v['decalages_par_mois']}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
