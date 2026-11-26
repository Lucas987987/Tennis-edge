#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_styles_approfondie.py — LES STYLES DE JEU, ÉTUDE PLUS POUSSÉE : UN PROFIL CONTINU À 8 MESURES ET TOUTES SES
RENCONTRES DEUX À DEUX, AU-DELÀ DE L'ELO (26/11/2026, paquet 457, Lucas : « On est d'accord que l'étude des styles de
jeu ne donne pas d'avantage ? On peut faire tourner une étude plus poussée ? »).

CE QUI A DÉJÀ ÉTÉ JUGÉ, ET NON RETENU (lu avant d'écrire, rien n'est refait) :
  — paires de CATÉGORIES de styles service–retour (etude_duels_styles.py, etude_matrice_styles.py,
    etude_matrice_profils_orientee.py, etude_serveurs_circuits.py) ; styles du Match Charting Project par paire et
    par joueur (etude_styles_jeu.py, paquets 252–253) ; bilans contre le style adverse, seuls, ajustés, 5 derniers
    (etude_styles_seuls.py, etude_styles_ajustes.py, etude_statistiques_styles.py, etude_5_derniers_styles.py) ;
  — effet propre à chaque joueur contre une catégorie d'adversaire (etude_profils_individuels.py, paquet 251) ;
  — UNE interaction continue écrite à la main, force du service × faiblesse du retour (styles_joueurs.py : +0,000028) ;
  — pente du duel de serveurs (paquet 289), vitesse du court × avantage au service (etude_cpi.py).
Leur point commun : soit le joueur est rangé dans 5 catégories (un joueur à la limite change de case, l'information à
l'intérieur de la case est perdue), soit UNE forme d'interaction est supposée d'avance.

CE QUI N'A PAS ÉTÉ TESTÉ, ET QUI L'EST ICI. Aucune catégorie et aucune forme supposée : chaque joueur est décrit par
8 mesures continues, et le modèle apprend LUI-MÊME quelles rencontres de mesures comptent (les 28 paires). Si un
« style contre style » existe sous n'importe quelle forme bilinéaire (gros serveur contre mauvais relanceur de 2e
balle, joueur lent contre joueur rapide, etc.), il est dans cette famille ; les études précédentes n'en sont que des
cas particuliers.

PROFIL D'UN JOUEUR (avant le match, sans fuite). Sur ses feuilles de stats de l'archive (matchs des tournois commencés
STRICTEMENT AVANT le jour du tournoi du match : ni le match, ni les tours précédents du même tournoi), pondérées par
l'ancienneté (demi-vie 365 jours), 8 mesures, chacune en ÉCART à la moyenne du circuit et de la surface du match où
elle a été relevée (moyenne cumulée sur les seuls matchs d'avant), et rapprochée de 0 par des essais fictifs :
    1 aces par point de service (300)          5 doubles fautes par point de service (300)
    2 premières balles dedans (300)            6 points gagnés au retour de 1re balle (180)
    3 points gagnés derrière la 1re (180)      7 points gagnés au retour de 2e balle (120)
    4 points gagnés derrière la 2e (120)       8 secondes par point joué — rythme, longueur des échanges (600 points)
    mesure = Σ poids · (réussites − essais · moyenne du circuit et de la surface) / (Σ poids · essais + essais fictifs)
Un joueur est « décrit » s'il a au moins 500 points de service pondérés ; un match est CONCERNÉ si les deux le sont.
Chaque mesure est divisée par sa moyenne quadratique sur la période d'apprentissage du circuit (jamais centrée).

CANDIDATE (une seule, fixée avant tout essai). Vu du joueur A contre B, a et b leurs profils :
    logit p' = logit p_Elo + Σ_{i<j} w_ij · (a_i·b_j − a_j·b_i)
28 poids par circuit. La forme est ANTISYMÉTRIQUE : échanger A et B change le signe, un joueur contre son double a 0,
et il n'y a AUCUN effet propre (« les gros serveurs sont sous-notés » n'est pas un style contre un style, et le
service et le retour entrent déjà dans le % publié par la simulation point par point). Poids appris par régression
logistique avec pénalité ridge λ ; λ choisi parmi 10, 30, 100, 300, 1 000, 3 000 UNIQUEMENT dans la période
d'apprentissage (appris sur sa première partie, meilleur gain sur sa seconde), puis poids réappris sur toute la
période d'apprentissage. Base : l'Elo de production rejoué match par match (etude_depart_itf.matchs,
elo.de_production, départs par niveau, mis à jour après chaque match ; sans abandon ni compétition par équipes).

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT ESSAI ET AVANT D'AVOIR VU UN SEUL CHIFFRE DE CETTE ÉTUDE :
  1. ATP et WTA, circuit par circuit : appris sur 2018–2022 (λ : appris 2018–2020, choisi sur 2021–2022) ; jugé UNE
     SEULE FOIS sur 01/01/2023 → 31/05/2026.
  2. Challenger : l'archive n'a pas les résultats ITF hommes avant juin 2024, son Elo Challenger y est faussé (pièges
     des paquets 229, 230, 317–319). Le Challenger est donc décidé sur la seule fenêtre « comme en production » :
     appris du 01/01/2025 au 30/09/2025 (λ : appris 01–05/2025, choisi sur 06–09/2025), jugé UNE SEULE FOIS du
     01/10/2025 au 31/05/2026. Le découpage 2018–2022 → 2023 est publié POUR MÉMOIRE et ne décide de rien.
  3. Mesure : gain de log loss par match CONCERNÉ, contre l'Elo seul (log loss de l'Elo − log loss corrigée).
  4. RETENU sur un circuit seulement si, à la fois :
       a. au moins 1 000 matchs concernés jugés (« on ne juge rien sur 100 matchs ») ;
       b. gain ≥ 0,001 par match concerné sur la période jugée ;
       c. même sens sur les deux périodes : gain > 0 sur la seconde partie de la période d'apprentissage (poids
          appris sur la première), ET gain > 0 dans l'autre sens (poids appris sur la période jugée avec le même λ,
          mesurés sur la période d'apprentissage). Le gain mesuré là où les poids sont appris est toujours positif :
          il est publié mais ne compte pas.
  5. Publiés sans décider : erreur type du gain ; gain rapporté à tous les matchs du circuit ; gain par surface ;
     les trois rencontres de mesures aux poids les plus forts (noms de mesures, jamais de joueurs).
  6. RIEN N'ENTRE EN PRODUCTION par ce paquet. Retenu : proposé à Lucas pour un suivi sur les matchs à venir. Non
     retenu : les styles restent une information descriptive, et la piste est classée.
Limites : l'Elo seul (sans la simulation ni les signaux du % publié) ; les feuilles de stats manquent pour une partie
des matchs (ITF, qualifications) ; aucune cote n'est lue.

Rapport public : simulateur/rapport_styles_approfondie.json — comptes et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_styles_approfondie.py /tmp/sackmann .
        python simulateur/etude_styles_approfondie.py --journal-depuis-rapport simulateur/rapport_styles_approfondie.json
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_etalonnage_cases as EC  # noqa: E402  (logit, log loss, journal)

PAQUET = 457
MESURES = ('aces', '1res balles dedans', 'points gagnés derrière la 1re', 'points gagnés derrière la 2e',
           'doubles fautes', 'retour de 1re gagné', 'retour de 2e gagné', 'secondes par point')
FICTIFS = (300.0, 300.0, 180.0, 120.0, 300.0, 180.0, 120.0, 600.0)
K = len(MESURES)
PAIRES = [(i, j) for i in range(K) for j in range(i + 1, K)]
DEMI_VIE, MIN_BALLES = 365.0, 500.0
LAMBDAS = (10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0)
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
# (début d'apprentissage, coupure interne pour choisir λ, début du jugement, fin)
ARCHIVE = (dt.date(2018, 1, 1), dt.date(2021, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 6, 1))
PRODUCTION = (dt.date(2025, 1, 1), dt.date(2025, 6, 1), dt.date(2025, 10, 1), dt.date(2026, 6, 1))
BORNES = {'ATP': ARCHIVE, 'WTA': ARCHIVE, 'CH': PRODUCTION}
SORTIE = os.path.join(ICI, 'rapport_styles_approfondie.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_457.json')


# ------------------------------------------------------------------ profils continus, sans fuite
def essais_du_match(det_j, det_adv, minutes):
    """[(essais, réussites)] des 8 mesures d'un joueur dans un match. det = (svpt, in1, w1, w2, ace, df, …)."""
    n, in1, w1, w2, ace, df = det_j[:6]
    an, ain1, aw1, aw2 = det_adv[:4]
    points = n + an
    return [(n, ace), (n, in1), (in1, w1), (n - in1, w2), (n, df), (ain1, ain1 - aw1), (an - ain1, an - ain1 - aw2),
            ((points, 60.0 * minutes) if minutes else (0, 0.0))]


class Profils:
    """Profils continus mis à jour par lots : un match n'entre qu'au changement de date (tournoi commencé avant)."""

    def __init__(self, demi_vie=DEMI_VIE):
        self.demi_vie = demi_vie
        self.j = {}            # joueur -> [dernier jour, num[K], den[K], points de service pondérés]
        self.base = {}         # (circuit, surface) -> [essais[K], réussites[K]] cumulés
        self.attente, self.jour = [], None

    def _avancer(self, jour):
        if self.jour is not None and jour > self.jour and self.attente:
            for m in self.attente:
                self._integrer(m)
            self.attente = []
        if self.jour is None or jour > self.jour:
            self.jour = jour

    def _integrer(self, m):
        det = m.get('detail')
        if not det:
            return
        cle = (m['circuit'], m.get('surface'))
        cotes = ((m['gagnant'], essais_du_match(det['w'], det['l'], m.get('minutes'))),
                 (m['perdant'], essais_du_match(det['l'], det['w'], m.get('minutes'))))
        b = self.base.get(cle)
        if b and b[0][0] >= 2000:                       # moyenne du circuit et de la surface assez établie
            for (joueur, E), d in zip(cotes, (det['w'], det['l'])):
                st = self.j.get(joueur)
                if st is None:
                    st = self.j[joueur] = [m['date'], [0.0] * K, [0.0] * K, 0.0]
                f = 0.5 ** (max((m['date'] - st[0]).days, 0) / self.demi_vie)
                st[0] = m['date']
                st[3] = st[3] * f + d[0]
                for k, (n, s) in enumerate(E):
                    mu = b[1][k] / b[0][k] if b[0][k] else 0.0
                    st[1][k] = st[1][k] * f + (s - n * mu if n else 0.0)
                    st[2][k] = st[2][k] * f + n
        if b is None:
            b = self.base[cle] = [[0.0] * K, [0.0] * K]
        for _, E in cotes:
            for k, (n, s) in enumerate(E):
                b[0][k] += n
                b[1][k] += s

    def profil(self, joueur, jour):
        """(mesures[K], points de service pondérés) au jour dit, avec les seuls matchs des jours d'avant."""
        self._avancer(jour)
        st = self.j.get(joueur)
        if st is None:
            return None, 0.0
        f = 0.5 ** (max((jour - st[0]).days, 0) / self.demi_vie)
        return [st[1][k] * f / (st[2][k] * f + FICTIFS[k]) for k in range(K)], st[3] * f

    def ajouter(self, m):
        self._avancer(m['date'])
        self.attente.append(m)


def rejeu(archive, racine):
    """[(circuit, date, surface, z Elo du vainqueur, profil du vainqueur ou None, profil du perdant ou None)]
    pour ATP, WTA, Challenger depuis 2018 : Elo de production seul, résultats ITF hommes compris."""
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    P = Profils()
    debut, fin = ARCHIVE[0], ARCHIVE[3]
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if c in CIRCUITS and debut <= m['date'] < fin and not m.get('abandon') and m.get('niveau') != 'D':
            fa, na = P.profil(m['gagnant'], m['date'])
            fb, nb = P.profil(m['perdant'], m['date'])
            ok = na >= MIN_BALLES and nb >= MIN_BALLES
            rows.append((c, m['date'], s, EC._lg(el.proba(g, p, s)), fa if ok else None, fb if ok else None))
        if m.get('detail') and m.get('gagnant') and m.get('perdant'):
            P.ajouter(m)
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


# ------------------------------------------------------------------ la candidate : rencontres deux à deux
def echelles(R):
    """Moyenne quadratique de chaque mesure sur les matchs concernés R (les deux joueurs)."""
    s, n = [0.0] * K, 0
    for r in R:
        for f in (r[4], r[5]):
            n += 1
            for k in range(K):
                s[k] += f[k] * f[k]
    return [math.sqrt(s[k] / n) if n and s[k] > 0 else 1.0 for k in range(K)]


def rencontres(fa, fb, ech):
    a = [fa[k] / ech[k] for k in range(K)]
    b = [fb[k] / ech[k] for k in range(K)]
    return [a[i] * b[j] - a[j] * b[i] for i, j in PAIRES]


def tableau(R, ech):
    """(X, Z) des matchs concernés : X = rencontres vues du vainqueur, Z = logit Elo du vainqueur."""
    return [rencontres(r[4], r[5], ech) for r in R], [r[3] for r in R]


def _cholesky_resoudre(A, b):
    n = len(b)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = A[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            L[i][j] = math.sqrt(max(s, 1e-12)) if i == j else s / L[j][j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def courbure(X, Z):
    """Σ q(1−q)·x·xᵀ aux probabilités de l'Elo (les corrections sont petites : calculée une fois par jeu de matchs)."""
    P = len(PAIRES)
    H = [[0.0] * P for _ in range(P)]
    for x, z in zip(X, Z):
        q = EC._sg(z)
        w = q * (1 - q)
        for i in range(P):
            xi = x[i] * w
            if xi:
                Hi = H[i]
                for j in range(i, P):
                    Hi[j] += xi * x[j]
    for i in range(P):
        for j in range(i):
            H[i][j] = H[j][i]
    return H


def _objectif(X, Z, beta, lam):
    return sum(EC.ll(z + sum(b * v for b, v in zip(beta, x))) for x, z in zip(X, Z)) + 0.5 * lam * sum(b * b for b in beta)


def ajuster(X, Z, lam, H=None, iterations=60):
    """Poids w (ridge λ) maximisant la vraisemblance du vainqueur σ(z + w·x) : quasi-Newton à courbure figée."""
    P = len(PAIRES)
    if not X:
        return [0.0] * P
    H = H or courbure(X, Z)
    A = [[H[i][j] + (lam if i == j else 0.0) for j in range(P)] for i in range(P)]
    beta = [0.0] * P
    f = _objectif(X, Z, beta, lam)
    for _ in range(iterations):
        g = [lam * b for b in beta]
        for x, z in zip(X, Z):
            e = EC._sg(z + sum(b * v for b, v in zip(beta, x))) - 1.0
            for i in range(P):
                g[i] += e * x[i]
        pas = _cholesky_resoudre(A, g)
        t = 1.0
        while t > 1e-4:
            essai = [b - t * d for b, d in zip(beta, pas)]
            fe = _objectif(X, Z, essai, lam)
            if fe <= f + 1e-12:
                break
            t /= 2
        else:
            break
        fini = max(abs(t * d) for d in pas) < 1e-7 or f - fe < 1e-9
        beta, f = essai, fe
        if fini:
            break
    return beta


def gain(X, Z, beta):
    """Gain moyen de log loss (Elo seul − Elo corrigé) par match concerné, avec son erreur type."""
    n = len(X)
    if not n:
        return {'matchs': 0}
    d = [EC.ll(z) - EC.ll(z + sum(b * v for b, v in zip(beta, x))) for x, z in zip(X, Z)]
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5)}


def juger_circuit(rows, bornes, decide=True):
    """rows : (circuit, date, surface, z, profil vainqueur, profil perdant) d'UN circuit. Applique la règle écrite."""
    debut, interne, coupure, fin = bornes
    tous_a = [r for r in rows if debut <= r[1] < coupure]
    tous_j = [r for r in rows if coupure <= r[1] < fin]
    A = [r for r in tous_a if r[4] is not None]
    J = [r for r in tous_j if r[4] is not None]
    out = {'apprentissage': f"{debut.isoformat()} → {coupure.isoformat()} (exclu)",
           'jugement': f"{coupure.isoformat()} → {fin.isoformat()} (exclu)",
           'matchs_apprentissage': len(tous_a), 'matchs_juges': len(tous_j),
           'concernes_apprentissage': len(A), 'concernes_juges': len(J)}
    if len(A) < 50 or len(J) < 50:
        out.update(retenu=False, raisons=['trop peu de matchs concernés pour apprendre ou juger'])
        return out
    ech = echelles(A)
    A1 = [r for r in A if r[1] < interne]
    A2 = [r for r in A if r[1] >= interne]
    X1, Z1 = tableau(A1, ech)
    X2, Z2 = tableau(A2, ech)
    XA, ZA = X1 + X2, Z1 + Z2
    XJ, ZJ = tableau(J, ech)
    # λ choisi dans la période d'apprentissage seulement
    H1 = courbure(X1, Z1)
    essais = {}
    for lam in LAMBDAS:
        essais[lam] = gain(X2, Z2, ajuster(X1, Z1, lam, H1))
    lam = max(LAMBDAS, key=lambda v: (essais[v].get('gain', -9), v))
    beta = ajuster(XA, ZA, lam)
    g_j = gain(XJ, ZJ, beta)
    g_a = gain(XA, ZA, beta)
    g_inverse = gain(XA, ZA, ajuster(XJ, ZJ, lam))
    out.update({
        'lambda_choisi': lam,
        'choix_de_lambda_dans_l_apprentissage': {str(int(v)): essais[v] for v in LAMBDAS},
        'gain_seconde_partie_apprentissage': essais[lam],
        'gain_la_ou_c_est_appris_ne_compte_pas': g_a,
        'gain_juge': g_j,
        'gain_sens_inverse': g_inverse,
        'gain_juge_rapporte_a_tous_les_matchs': round(g_j['gain'] * len(J) / max(len(tous_j), 1), 5),
        'gain_juge_par_surface': {s: gain(*tableau([r for r in J if r[2] == s], ech), beta)
                                  for s in sorted({r[2] for r in J if r[2]})},
        'taille_des_poids': round(math.sqrt(sum(b * b for b in beta)), 4),
        'rencontres_aux_poids_les_plus_forts': [
            {'mesures': f"{MESURES[PAIRES[i][0]]} × {MESURES[PAIRES[i][1]]}", 'poids': round(beta[i], 4)}
            for i in sorted(range(len(beta)), key=lambda i: -abs(beta[i]))[:3]],
    })
    raisons = []
    if g_j['matchs'] < MIN_JUGES:
        raisons.append(f"moins de {MIN_JUGES} matchs concernés jugés")
    if g_j['gain'] < MARGE:
        raisons.append(f"gain jugé sous {fr(MARGE)}")
    if essais[lam].get('gain', -1) <= 0:
        raisons.append("gain non positif sur la seconde partie de l'apprentissage")
    if g_inverse.get('gain', -1) <= 0:
        raisons.append("gain non positif dans le sens inverse")
    out['meme_sens_sur_les_deux_periodes'] = bool(g_j['gain'] > 0 and essais[lam].get('gain', -1) > 0
                                                  and g_inverse.get('gain', -1) > 0)
    if decide:
        out.update(retenu=not raisons, raisons=raisons)
    else:
        out.update(pour_memoire=True, lecture_si_c_etait_la_regle=raisons or ['passerait la règle'])
    return out


def etudier(rows):
    out = {'circuits': {}}
    for c in CIRCUITS:
        R = [r for r in rows if r[0] == c]
        out['circuits'][c] = juger_circuit(R, BORNES[c])
        if c == 'CH':
            out['circuits'][c]['note'] = ("fenêtre « comme en production » : les résultats ITF hommes sont dans l'Elo ; "
                                          "9 mois d'apprentissage seulement")
            pm = juger_circuit(R, ARCHIVE, decide=False)
            pm['note'] = ("POUR MÉMOIRE, NE DÉCIDE DE RIEN : avant juin 2024 l'archive n'a pas les résultats ITF hommes, "
                          "l'Elo du Challenger y est faussé")
            out['challenger_archive_2018_2022_puis_2023_pour_memoire'] = pm
    out['retenus'] = [NOM_CIRCUIT[c] for c in CIRCUITS if out['circuits'][c].get('retenu')]
    out['verdict'] = ("retenu sur " + ', '.join(out['retenus']) + " : proposé à Lucas pour un suivi sur les matchs à venir"
                      if out['retenus'] else
                      "NON RETENU sur aucun circuit : le profil continu et ses 28 rencontres n'ajoutent rien à l'Elo ; "
                      "les styles restent une information descriptive")
    return out


# ------------------------------------------------------------------ journal et sortie
def fr(v):
    if isinstance(v, float):
        v = f"{v:.5f}".rstrip('0').rstrip('.') or '0'
    return str(v).replace('.', ',')


def _phrase(nom, b):
    j = b.get('gain_juge') or {}
    if 'gain' not in j:
        return f"{nom} : trop peu de matchs concernés ({b.get('concernes_juges', 0)} jugés), non retenu"
    return (f"{nom} : {j['matchs']} matchs concernés jugés, gain {fr(j['gain'])} ± {fr(j['erreur_type'])} par match "
            f"(seconde partie de l'apprentissage {fr(b['gain_seconde_partie_apprentissage'].get('gain'))}, sens inverse "
            f"{fr(b['gain_sens_inverse'].get('gain'))}), {'RETENU' if b.get('retenu') else 'non retenu'}")


def entree_journal(doc, gabarit):
    e = doc['etude']
    res = (" RÉSULTAT (jugé une fois ; gain = log loss de l'Elo seul − log loss corrigée, positif = mieux) : "
           + ' ; '.join(_phrase(NOM_CIRCUIT[c], e['circuits'][c]) for c in CIRCUITS)
           + ". Verdict : " + e['verdict'] + ". Rien n'est changé par ce paquet.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + res + ' Le % de victoire ne change pas.', 'garde_fou': gabarit['garde_fou']}


def afficher(doc):
    """Ce qui part dans le journal du run (public) : comptes et moyennes seulement."""
    e = doc['etude']
    for c in CIRCUITS:
        print(_phrase(NOM_CIRCUIT[c], e['circuits'][c]))
    pm = e.get('challenger_archive_2018_2022_puis_2023_pour_memoire') or {}
    if pm.get('gain_juge'):
        print('Challenger sur l archive 2018–2022 puis 2023 (pour mémoire, Elo faussé avant juin 2024) —',
              pm['gain_juge']['matchs'], 'matchs, gain', fr(pm['gain_juge']['gain']), '±', fr(pm['gain_juge']['erreur_type']))
    print('Verdict —', e['verdict'])


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            EC.ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, n_itf = rejeu(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'itf_hommes_dans_le_rejeu': n_itf,
           'regle': ("profil continu à 8 mesures par joueur (matchs des tournois commencés avant), 28 rencontres "
                     "antisymétriques ajoutées au logit de l'Elo de production ; ATP et WTA : appris 2018–2022, jugé une "
                     "fois 2023 → mai 2026 ; Challenger : appris 01–09/2025, jugé une fois 10/2025 → mai 2026 ; retenu "
                     "par circuit si gain ≥ 0,001 par match concerné sur ≥ 1 000 matchs concernés jugés, gain positif "
                     "sur la seconde partie de l'apprentissage et dans le sens inverse"),
           'mesures': list(MESURES), 'essais_fictifs': list(FICTIFS), 'demi_vie_jours': DEMI_VIE,
           'points_de_service_minimum': MIN_BALLES, 'lambdas_essayes': list(LAMBDAS),
           'etude': etudier(rows), 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EC.ajouter_au_journal(JOURNAL, doc['entree_journal'])
    afficher(doc)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
