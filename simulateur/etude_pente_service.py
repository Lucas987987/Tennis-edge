#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_pente_service.py — DUELS DE SERVEURS : l'écart de niveau compte-t-il moins quand les deux joueurs gardent
facilement leur service ? (19/11/2026, paquet 289)

QUESTION. Le % de l'Elo traduit un écart de niveau en chances de victoire de la même façon pour tous les matchs.
Or, quand les deux joueurs servent fort et retournent mal, les jeux de service tombent rarement, les sets se jouent
sur un break ou un tie-break, et un petit nombre de points décide du match : l'outsider devrait gagner PLUS souvent
que l'écart d'Elo ne l'annonce (pente < 1). À l'inverse, dans un duel de retourneurs, les breaks pleuvent et l'écart
de niveau devrait s'exprimer davantage (pente > 1). Ce n'est pas encore étudié : les pentes par surface (paquet 236)
mélangent tous les joueurs d'une surface ; le CPI (vitesse du court) croisé avec l'avantage au service a été rejeté ;
les « serveuses WTA » sont un décalage pour un profil, pas une pente. Ici on mesure le DUEL lui-même, avant le match.

INDICE DU DUEL (connu avant le match, symétrique : il ne dit rien du vainqueur). Pour chaque joueur, sur ses matchs
des 365 jours précédents (archive, feuilles de stats) : s = part de ses points de service gagnés, r = part des points
de retour gagnés, chacune rapprochée de la moyenne de son circuit avec 300 points fictifs (joueur peu vu ≈ moyen).
    x = ½ (s_A + s_B) − ½ (r_A + r_B) + 1 − 2·m      (m = moyenne de son circuit des points de service gagnés,
                                                         cumulée sur les matchs précédents seulement)
x > 0 : duel de serveurs ; x < 0 : duel de retourneurs.

CORRECTION ÉTUDIÉE, une par circuit : z' = z · (1 + β · x), z = logit du % de BASE (Elo de production, mis à jour
après chaque match, + les trois signaux solides, comme etude_outsiders.py). β est appris par maximum de
vraisemblance. β < 0 = l'écart de niveau compte moins dans les duels de serveurs.

RÈGLE ÉCRITE AVANT TOUT RÉSULTAT (19/11/2026), CIRCUIT PAR CIRCUIT (ATP, WTA, Challenger analysés séparément) :
  1. β est appris sur 2018–2022 SEULEMENT ;
  2. il est jugé UNE SEULE FOIS sur 2023 → juin 2026 (matchs jugés : sans abandon, sans compétition par équipes,
     ITF jamais jugée ; les résultats ITF ne servent qu'à l'Elo et aux indices) ;
  3. le signal est RETENU sur un circuit seulement si, sur la période jugée :
       a. au moins 1 000 matchs jugés,
       b. gain de log loss ≥ 0,001 par match par rapport à la base,
       c. même sens sur les deux périodes : β réappris sur 2023 → juin 2026 a le même signe que β appris sur
          2018–2022, et le gain sur 2018–2022 est positif ;
  4. publiés à côté, sans décider : erreur type du gain (et « ≥ 2 erreurs types », la condition des paquets récents),
     Brier, et le constat par quintile de x (favori réel contre annoncé, outsider réel contre annoncé) sur les deux
     périodes ;
  5. rien n'entre en production par ce paquet : un circuit retenu est PROPOSÉ à Lucas pour un paquet suivant, avec
     la règle de retrait cumulée habituelle ; un circuit non retenu est écarté et n'est pas rejoué.
Les pronostics en direct ne servent qu'à confirmer, jamais à décider ; rien n'est jugé sur une centaine de matchs.

Le rapport public (simulateur/rapport_pente_service.json) ne contient que des comptes et des moyennes : aucun nom de
joueur. L'entrée du journal (paquet 289) est écrite par cette étude avec ses résultats.

Usage : python simulateur/etude_pente_service.py /tmp/sackmann .
        python simulateur/etude_pente_service.py --journal-depuis-rapport simulateur/rapport_pente_service.json
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE, MIN_ERREURS_TYPES = 1000, 0.001, 2.0
FENETRE_JOURS, POINTS_FICTIFS = 365, 300.0
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
SORTIE = os.path.join(ICI, 'rapport_pente_service.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_289.json')
PAQUET = 289


# ------------------------------------------------------------------ outils
def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def ll(z):
    """Log loss du vainqueur quand le logit (vu du vainqueur) vaut z."""
    return -math.log(min(max(_sg(z), 1e-12), 1 - 1e-12))


def brier(z):
    return (1 - _sg(z)) ** 2


def corriger(z, x, beta):
    return z * (1 + beta * x)


def apprendre_beta(Z, X, iterations=50):
    """β du maximum de vraisemblance de z' = z (1 + β x), lignes vues du vainqueur (Newton à une dimension)."""
    b = 0.0
    for _ in range(iterations):
        g = h = 0.0
        for z, x in zip(Z, X):
            u = z * x
            q = _sg(z + b * u)
            g += (q - 1) * u
            h += q * (1 - q) * u * u
        if h < 1e-12:
            break
        pas = g / h
        b -= max(min(pas, 50.0), -50.0)
        if abs(pas) < 1e-9:
            break
    return b


def bilan(Z, Zc):
    n = len(Z)
    if not n:
        return {'matchs': 0}
    d = [ll(a) - ll(b) for a, b in zip(Z, Zc)]
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5),
            'erreurs_types': round(g / et, 2) if et else None,
            'log_loss_base': round(sum(ll(a) for a in Z) / n, 5), 'log_loss': round(sum(ll(b) for b in Zc) / n, 5),
            'brier_base': round(sum(brier(a) for a in Z) / n, 5), 'brier': round(sum(brier(b) for b in Zc) / n, 5)}


def quintiles(X):
    s = sorted(X)
    if len(s) < 5:
        return []
    return [s[int(len(s) * k / 5)] for k in (1, 2, 3, 4)]


def constat(Z, X, bornes):
    """Par quintile de x : favori réel contre annoncé, outsider réel contre annoncé (base, sans correction)."""
    cases = [[] for _ in range(5)]
    for z, x in zip(Z, X):
        i = sum(1 for b in bornes if x >= b)
        cases[i].append(z)
    out = []
    for i, L in enumerate(cases):
        n = len(L)
        if not n:
            out.append({'quintile': i + 1, 'matchs': 0})
            continue
        fav_annonce = sum(max(_sg(z), 1 - _sg(z)) for z in L) / n
        fav_reel = sum(1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z in L) / n
        out.append({'quintile': i + 1, 'matchs': n,
                    'favori_annonce_pct': round(100 * fav_annonce, 1), 'favori_reel_pct': round(100 * fav_reel, 1),
                    'outsider_annonce_pct': round(100 * (1 - fav_annonce), 1),
                    'outsider_reel_pct': round(100 * (1 - fav_reel), 1)})
    return out


# ------------------------------------------------------------------ indice du duel (sans regarder le vainqueur)
class Service:
    """Points de service / de retour des 365 derniers jours, par joueur, et moyenne cumulée par circuit."""

    def __init__(self, fenetre=FENETRE_JOURS, fictifs=POINTS_FICTIFS):
        self.fenetre, self.fictifs = fenetre, fictifs
        self.h = collections.defaultdict(collections.deque)   # joueur -> (date, sn, sw, rn, rw)
        self.tot = collections.defaultdict(lambda: [0, 0])    # circuit -> [points de service, gagnés]

    def moyenne(self, circuit):
        n, w = self.tot[circuit]
        return w / n if n >= 1000 else 0.63

    def _somme(self, j, d):
        q = self.h.get(j)
        if not q:
            return 0, 0, 0, 0
        while q and (d - q[0][0]).days > self.fenetre:
            q.popleft()
        sn = sw = rn = rw = 0
        for _d, a, b, c, e in q:
            sn, sw, rn, rw = sn + a, sw + b, rn + c, rw + e
        return sn, sw, rn, rw

    def joueur(self, j, d, circuit):
        m = self.moyenne(circuit)
        sn, sw, rn, rw = self._somme(j, d)
        k = self.fictifs
        return (sw + k * m) / (sn + k), (rw + k * (1 - m)) / (rn + k)

    def duel(self, a, b, d, circuit):
        sa, ra = self.joueur(a, d, circuit)
        sb, rb = self.joueur(b, d, circuit)
        m = self.moyenne(circuit)
        return 0.5 * (sa + sb) - 0.5 * (ra + rb) + 1 - 2 * m

    def jouer(self, g, p, d, circuit, stats):
        """stats : {'w': (points de service, gagnés), 'l': (…)} de l'archive, ou None."""
        if not stats:
            return
        (nw, ww), (nl, wl) = stats['w'], stats['l']
        self.h[g].append((d, nw, ww, nl, nl - wl))
        self.h[p].append((d, nl, wl, nw, nw - ww))
        t = self.tot[circuit]
        t[0] += nw + nl
        t[1] += ww + wl


# ------------------------------------------------------------------ rejeu de l'archive (dépôt complet nécessaire)
def lignes(archive, racine):
    """Une ligne par match jugé, vue du VAINQUEUR : circuit, date, z de l'Elo de production, variables des trois
    signaux solides (comme etude_outsiders.lignes) et x, l'indice du duel connu avant le match."""
    import donnees as DN
    import elo as E
    import etude_age as EA
    import etude_changement_surface as ECS
    import etude_retour_absence as ERA
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, sv, rows = ECS.Suivi(), ERA.Retours(), Service(), []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            pr = min(max(el.proba(g, p, s), 1e-6), 1 - 1e-6)
            z = math.log(pr / (1 - pr))
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            rows.append({'c': c, 'd': d, 'z': z,
                         'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'x': sv.duel(g, p, d, c)})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        sv.jouer(g, p, d, c, m.get('stats'))
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


# ------------------------------------------------------------------ jugement (données factices possibles)
def juger_circuit(rows, c):
    A = [r for r in rows if r['c'] == c and r['d'] < COUPURE]
    J = [r for r in rows if r['c'] == c and r['d'] >= COUPURE]
    ZA, XA = [r['zb'] for r in A], [r['x'] for r in A]
    ZJ, XJ = [r['zb'] for r in J], [r['x'] for r in J]
    beta = apprendre_beta(ZA, XA) if A else 0.0
    beta_j = apprendre_beta(ZJ, XJ) if J else 0.0
    appr = bilan(ZA, [corriger(z, x, beta) for z, x in zip(ZA, XA)])
    juge = bilan(ZJ, [corriger(z, x, beta) for z, x in zip(ZJ, XJ)])
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append("moins de 1 000 matchs jugés")
    if juge.get('gain', -1.0) < MARGE:
        raisons.append("gain sous 0,001")
    if not (beta * beta_j > 0 and appr.get('gain', -1.0) > 0):
        raisons.append("pas le même sens sur les deux périodes")
    bornes = quintiles(XA)
    ecart = lambda X: round(100 * (sorted(X)[len(X) // 2]), 2) if X else None
    return {'circuit': NOM_CIRCUIT[c],
            'beta_appris_2018_2022': round(beta, 3), 'beta_reappris_2023_juin_2026': round(beta_j, 3),
            'indice_median_pts': ecart(XA),
            'bornes_quintiles_pts': [round(100 * b, 2) for b in bornes],
            '2018–2022': appr, '2023 → juin 2026': juge,
            'constat_par_quintile': {'2018–2022': constat(ZA, XA, bornes), '2023 → juin 2026': constat(ZJ, XJ, bornes)},
            'retenu': not raisons, 'raisons': raisons,
            'passe_deux_erreurs_types': (juge.get('erreurs_types') or 0) >= MIN_ERREURS_TYPES}


def etudier(rows):
    return {c: juger_circuit(rows, c) for c in CIRCUITS}


REGLE = ("Circuit par circuit (ATP, WTA, Challenger). Correction z' = z·(1 + β·x), x = indice du duel service / retour "
         "connu avant le match. β appris sur 2018–2022, jugé une fois sur 2023 → juin 2026. Retenu si : ≥ 1 000 matchs "
         "jugés, gain de log loss ≥ 0,001, même sens sur les deux périodes (β réappris de même signe, gain positif sur "
         "2018–2022). Erreur type, Brier et constat par quintile publiés sans décider. Rien en production par ce paquet.")


def fr(v):
    """Nombre écrit à la française (virgule décimale), comme le reste du journal."""
    return str(v).replace('.', ',')


def phrase_resultats(res):
    morceaux = []
    for c in CIRCUITS:
        v = res[c]
        j = v['2023 → juin 2026']
        if not j.get('matchs'):
            morceaux.append(f"{v['circuit']} : aucun match jugé")
            continue
        q = v['constat_par_quintile']['2023 → juin 2026']
        haut = q[-1] if q and q[-1].get('matchs') else None
        detail = (f" ; duels de serveurs (quintile haut) : outsider {fr(haut['outsider_reel_pct'])} % réels pour "
                  f"{fr(haut['outsider_annonce_pct'])} % annoncés") if haut else ''
        morceaux.append(f"{v['circuit']} : β {fr(v['beta_appris_2018_2022'])} (réappris {fr(v['beta_reappris_2023_juin_2026'])}), "
                        f"{j['matchs']} matchs jugés, gain {fr(j['gain'])} ± {fr(j['erreur_type'])}, Brier {fr(j['brier_base'])} → "
                        f"{fr(j['brier'])}{detail} — {'RETENU' if v['retenu'] else 'non retenu (' + ', '.join(v['raisons']) + ')'}")
    return ' ; '.join(morceaux) + '.'


def entree_journal(res, gabarit):
    retenus = [res[c]['circuit'] for c in CIRCUITS if res[c]['retenu']]
    fin = (f" Retenu sur : {', '.join(retenus)}. Proposé à Lucas pour un paquet suivant (règle de retrait cumulée) ; "
           f"rien n'est changé dans l'algo par ce paquet." if retenus else
           " Aucun circuit retenu : l'écart de niveau garde le même poids quel que soit le duel ; la piste est close et "
           "ne sera pas rejouée.")
    e = {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
         'quoi': gabarit['quoi_debut'] + ' RÉSULTAT : ' + phrase_resultats(res) + fin + ' Le % de victoire ne change pas.',
         'garde_fou': gabarit['garde_fou']}
    return e


# ------------------------------------------------------------------ journal (ajout sans réécrire le reste)
def ajouter_au_journal(chemin, entree):
    """Ajoute l'entrée, ou remplace celle du même paquet. Même mise en forme que le fichier (indentation 1, UTF-8,
    sans retour à la ligne final) : seules les lignes de l'entrée changent."""
    with open(chemin, encoding='utf-8') as f:
        doc = json.load(f)
    L = doc.setdefault('changements', [])
    for i, x in enumerate(L):
        if x.get('paquet') == entree['paquet']:
            L[i] = entree
            break
    else:
        L.append(entree)
    tmp = chemin + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    import etude_outsiders as EO
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    res = etudier(rows)
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        gabarit = json.load(f)
    entree = entree_journal(res, gabarit)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'paquet': PAQUET, 'regle': REGLE,
           'indice': ("x = ½(s_A + s_B) − ½(r_A + r_B) + 1 − 2m ; s, r = points de service / de retour gagnés sur 365 "
                      "jours, rapprochés de la moyenne du circuit avec 300 points fictifs ; affiché en points de %"),
           'elo': "réglé comme la production (elo.de_production), mis à jour après chaque match ; compétitions par équipes exclues",
           'base': {'signaux': ['changement_surface', 'retour_absence_court', 'retour_absence_long', 'age_vieux', 'age_jeune'],
                    'betas_2018_2022': betas},
           'circuits': res, 'en_production': False, 'entree_journal': entree}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, entree)
    for c in CIRCUITS:
        v = res[c]
        print(v['circuit'], '| β', v['beta_appris_2018_2022'], '/', v['beta_reappris_2023_juin_2026'], '| jugé',
              v['2023 → juin 2026'], '| retenu :', v['retenu'], v['raisons'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
