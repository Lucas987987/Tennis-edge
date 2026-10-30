#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
facteurs.py — ce qui fait basculer un match, au-delà du niveau habituel des joueurs (22/10/2026).

Onze groupes de facteurs, mesurés sur les feuilles de match collectées (TennisApi),
chacun appris sur juin–août 2026 et JUGÉ sur septembre–octobre 2026, jamais vus :

  1. forme_fatigue : forme des 30 derniers jours (points gagnés au service et au retour,
     au-delà de ce que prévoit le modèle ajusté aux adversaires), sets joués les 3
     derniers jours, jours de repos — pour le serveur et pour le relanceur ;
  2. vitesse_court : ce que les joueurs obtiennent au service et en aces dans CE tournoi
     (tours déjà joués, éditions précédentes collectées), au-delà de leur niveau habituel ;
  3. morphologie : gaucher (serveur, relanceur, gaucher contre droitier), taille ;
  4. points_importants : balles de break sauvées au-delà de ce que le joueur gagne sur ses
     autres points de service (archive Sackmann + feuilles), et balles de break converties
     au retour ; plus l'effet moyen d'une balle de break ;
  5. styles : duels de styles — service du serveur × retour de l'adversaire (aces contre
     retour de 1re, 1re contre retour de 1re, 2e contre retour de 2e), effets qui ne
     s'additionnent pas ;
  6. face_a_face : ce que le serveur a réellement fait contre CET adversaire (archive des
     4 dernières années + feuilles), au-delà de l'attendu, ramené vers 0 ;
  7. conditions : altitude, salle, chaleur et vent en plein air (Open-Meteo), joueur à
     domicile, décalage horaire depuis le tournoi précédent (scripts/lieux_tournois.py) ;
  8. contexte_tournoi : déjà joué dans ce tournoi, retour après plus de 45 jours sans
     match, matchs dans d'autres tournois les 10 derniers jours ;
  9. charting : Match Charting Project (charting.py) — points de service gagnés en 3
     frappes ou moins, retours remis en jeu, goût pour les longs échanges.
  10. blessure : abandon, forfait ou disqualification récents (demi-vie 15 jours), nombre
     d'abandons sur 90 jours, 1er match depuis un abandon (archive + feuilles TennisApi).
  12. duree : minutes jouées dans le tournoi, sur 7 jours, durée du dernier match (feuilles TennisApi).
  13. matchup : le relanceur face aux GROS SERVEURS et le serveur face aux GRANDS RELANCEURS, au-delà de leur
     niveau (pentes mesurées sur les points, archive + feuilles) — 24/10/2026 ;
  14. adversaires_communs : points gagnés au-delà de l'attendu contre les mêmes adversaires — 24/10/2026.
  11. pression : point par point (scripts/points_match.py) — points gagnés au service à 30-30 et à
     l'égalité, au-delà de son % du match ; rebond juste après avoir été breaké ; servir pour le set.

Chaque facteur décale, en logit, les points gagnés au service (1re et 2e balle), les aces,
ou le point joué sur balle de break, PAR RAPPORT AU MODÈLE AJUSTÉ AUX ADVERSAIRES (base).
Coefficients : régression logistique avec la base en décalage (petit rappel vers 0).

RÈGLE FIXÉE D'AVANCE, par groupe : adopté si, sur septembre–octobre, il améliore la
vraisemblance des points concernés ET ne dégrade pas l'erreur (log loss) du vainqueur de la
simulation pure de plus de 0,001. (Un facteur qui touche les deux joueurs pareil — la vitesse
du court — change surtout la FORME du match : aces, jeux, tie-breaks, presque pas le
vainqueur ; il doit donc aider sur les points sans nuire au vainqueur.) Le rapport dit aussi
si le vainqueur est mieux trouvé. Les groupes adoptés sont ensuite ré-appris sur toutes les
feuilles pour les pronostics.

Usage : python simulateur/facteurs.py <archive Sackmann> [racine] [dépôt Match Charting Project]
Sorties : simulateur/facteurs.json (coefficients, groupes adoptés, rapport) ;
          contexte_actuel() / exporter_contexte() pour les pronostics du jour.
"""
import collections
import datetime as dt
import heapq
import json
import math
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import ajustement as AJ  # noqa: E402
import charting as CH  # noqa: E402
import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402
import match_simule as S  # noqa: E402

SORTIE = os.path.join(ICI, 'facteurs.json')
CONTEXTE = os.path.join(ICI, 'facteurs_contexte.json')
SIGMA = 0.15
DEBUT_APPR, DEBUT_JUGE = dt.date(2026, 6, 1), dt.date(2026, 9, 1)
# 22/10/2026 — APPRENTISSAGE CONTINU : l'algorithme se nourrit des nouveaux matchs. Chaque semaine, chaque
# groupe est ré-appris sur toutes les feuilles sauf les 6 dernières semaines, et JUGÉ sur ces 6 dernières
# semaines (jamais avant le 1er septembre 2026). Même règle d'adoption ; seule la fenêtre avance.
FENETRE_JUGE_J = 42


def fenetres(aujourdhui=None):
    """(début de l'apprentissage, début du jugement) : le jugement porte sur les 6 dernières semaines."""
    aujourdhui = aujourdhui or dt.date.today()
    return DEBUT_APPR, max(DEBUT_JUGE, aujourdhui - dt.timedelta(days=FENETRE_JUGE_J))
FENETRE_FORME_J = 30
K_FORME, K_VITESSE, K_CLUTCH = 200.0, 1500.0, 60.0
DISPO_H = 3                     # un match compte dans l'historique 3 h après son début
RIDGE = 2.0
TOLERANCE_VAINQUEUR = 0.001
GROUPES = {
    'forme_fatigue': {'service': ['forme_srv', 'forme_ret_adv', 'sets3_srv', 'sets3_adv', 'repos_srv', 'repos_adv']},
    'vitesse_court': {'service': ['vit_srv'], 'aces': ['vit_ace']},
    'morphologie': {'service': ['gaucher_srv', 'gaucher_adv', 'gaucher_contre_droitier', 'taille_srv', 'taille_adv'],
                    'aces': ['taille_srv', 'gaucher_srv', 'gaucher_adv']},
    'points_importants': {'bp': ['bp_constante', 'clutch_srv', 'clutch_ret_adv']},
    # 22/10/2026 — point 4 : DUELS DE STYLES (un gros serveur souffre-t-il plus ou moins qu'attendu face à un
    # grand relanceur ? effets qui ne s'additionnent pas) et FACE-À-FACE (ce que le serveur a réellement fait
    # contre CET adversaire, au-delà de l'attendu).
    'styles': {'service': ['style_ace_x_retour', 'style_1re_x_retour', 'style_2e_x_retour'], 'aces': ['style_ace_x_retour']},
    'face_a_face': {'service': ['h2h_srv']},
    # 22/10/2026 — point 5 : CONDITIONS DU JOUR (altitude, salle, chaleur et vent en plein air, joueur à domicile,
    # voyage depuis le tournoi précédent) ; point 6 : CONTEXTE DU TOURNOI (déjà joué ici, retour après une longue
    # absence, tournois enchaînés).
    'conditions': {'service': ['altitude', 'interieur', 'chaleur', 'vent', 'domicile_srv', 'domicile_adv', 'voyage_srv', 'voyage_adv'],
                   'aces': ['altitude', 'interieur', 'chaleur', 'vent']},
    'contexte_tournoi': {'service': ['deja_ici_srv', 'deja_ici_adv', 'absence_srv', 'absence_adv', 'enchaine_srv', 'enchaine_adv']},
    # 22/10/2026 — point 7 : Match Charting Project (charting.py) — points gagnés en 3 frappes ou moins,
    # retours remis en jeu, goût pour les longs échanges ; le duel premier coup du serveur × retour adverse.
    'charting': {'service': ['mcp_premier_coup_srv', 'mcp_retour_adv', 'mcp_duel', 'mcp_echanges'], 'aces': ['mcp_premier_coup_srv']},
    # 22/10/2026 — BLESSURES : abandon, forfait ou disqualification récents (archive + feuilles TennisApi :
    # statuts « Retired », « Walkover », « Defaulted »), poids qui décroît avec le temps (demi-vie 15 jours),
    # nombre d'abandons sur 90 jours, et 1er match depuis un abandon — pour le serveur et l'adversaire.
    'blessure': {'service': ['abandon_srv', 'abandon_adv', 'abandons90_srv', 'abandons90_adv', 'retour_abandon_srv',
                             'retour_abandon_adv']},
}
DEMI_VIE_ABANDON_J = 15.0
GROUPES['pression'] = {'service': ['pression_srv', 'pression_ret_adv', 'rebond_srv', 'pour_le_set_srv']}
# 23/10/2026 — DURÉE DES MATCHS (feuilles TennisApi, champ « time »), pour le serveur et l'adversaire, en centaines
# de minutes : minutes déjà jouées DANS CE TOURNOI (qualifications comprises — un tournoi dure une à deux
# semaines), minutes des 7 derniers jours (tournois enchaînés), durée du dernier match s'il date de moins de 2 jours.
GROUPES['duree'] = {'service': ['minutes_tournoi_srv', 'minutes_tournoi_adv', 'minutes7_srv', 'minutes7_adv',
                                'minutes_dernier_srv', 'minutes_dernier_adv']}
K_PRESSION = 60.0
# 24/10/2026 — MATCHUP (cas Li – Krueger : « Li ne supporte pas les grosses serveuses ») et ADVERSAIRES COMMUNS.
#  · matchup : comment CE relanceur s'en sort, au-delà de son niveau, quand le serveur d'en face est fort
#    (pente de ses points gagnés en retour, mesurés au-delà de l'attendu, selon la force du service adverse) ;
#    et pareil pour CE serveur face aux grands relanceurs. On mesure les POINTS (stables), pas les victoires.
#  · adversaires_communs : sur les adversaires que les deux joueurs ont affrontés (archive 4 ans + feuilles),
#    qui a gagné le plus de points au-delà de l'attendu — un face-à-face indirect.
GROUPES['matchup'] = {'service': ['mu_srv', 'mu_ret_adv'], 'aces': ['mu_srv']}
GROUPES['adversaires_communs'] = {'service': ['communs_srv']}
K_MU = 20.0                      # ~6 matchs avant d'y croire (n × force² ≈ 3 par match)
K_COM = 300.0                    # points communs avant d'y croire
# 28/10/2026 — PROFIL DE RÉACTION (demande « rien n'écarter », cas Hurkacz – Rune) : pour CHAQUE joueur, comment ses
# points au service et au retour s'écartent de l'attendu (modèle ajusté à la force des adversaires) selon CHAQUE trait
# de l'adversaire — 8 curseurs continus au lieu de 6 cases : ses aces, sa 1re et sa 2e balle, son retour de 1re et de
# 2e, gaucher, taille, goût pour les longs échanges (Match Charting). On mesure des POINTS (des milliers par joueur),
# pas des victoires. Chaque pente est ramenée vers 0 (K_PF ≈ 6 matchs). Le groupe est jugé comme les autres.
PF_TRAITS = ('ace', 'srv1', 'srv2', 'ret1', 'ret2', 'gaucher', 'taille', 'echanges')
# centre et échelle de chaque trait (mesurés le 28/10/2026 sur les 8 786 feuilles juin–oct. 2026, puis figés) :
# trait standardisé ≈ moyenne 0, écart 1 ; un trait inconnu (taille, main, pas de Match Charting) vaut le centre (0).
PF_CENTRE = (0.050, 0.085, 0.049, 0.086, 0.057, 0.121, 0.0, 0.003)
# 28/10/2026 (audit par circuit) : la taille était centrée sur 185 cm pour TOUS ; mesuré dans feuilles/joueurs.json :
# WTA 174 cm (210 joueuses), ATP 186, Challenger 184 (895), ITF hommes 182. Toutes les joueuses passaient pour
# « petites » (−1,1 écart) et une joueuse de taille inconnue (comptée 185) prenait un léger avantage de service sur
# une adversaire de taille connue. Désormais : centre du circuit (femmes 174, hommes 184) ; inconnue = centre (0).
TAILLE_CENTRE = {True: 174.0, False: 184.0}


def taille_centree(i):
    """(taille − centre de son circuit) / 10 ; 0 si inconnue. i : infos du joueur ({taille_cm, femme})."""
    i = i or {}
    if not i.get('taille_cm'):
        return 0.0
    return (i['taille_cm'] - TAILLE_CENTRE[bool(i.get('femme'))]) / 10.0
PF_ECHELLE = (0.43, 0.146, 0.074, 0.099, 0.082, 0.326, 0.775, 0.030)
K_PF = 500.0
GROUPES['profil'] = {'service': [f'pf_srv_{d}' for d in PF_TRAITS] + [f'pf_ret_adv_{d}' for d in PF_TRAITS]}


def charger_points(racine):
    """{id du match: [[set, jeu, serveur, « HAHH… »]]} depuis feuilles_points/ (scripts/points_match.py)."""
    import glob
    import gzip
    out = {}
    for p in sorted(glob.glob(os.path.join(racine, 'feuilles_points', '*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    r = json.loads(l)
                    if r.get('jeux'):
                        out[r['id']] = r['jeux']
        except (OSError, ValueError, EOFError):
            continue
    return out


def pression_du_match(jeux, p_srv):
    """Écarts au service de chaque joueur (0 = home, 1 = away) dans les moments chauds d'un match.
    p_srv : (% de points gagnés au service dans CE match, home, away) — l'écart ne mesure que la situation.
    Renvoie {joueur: [Σ écart pression, n points, Σ écart rebond, n, Σ écart pour le set (jeux), n]}."""
    import modele as Mo
    acc = {0: [0.0, 0, 0.0, 0, 0.0, 0], 1: [0.0, 0, 0.0, 0, 0.0, 0]}
    jeux_set = {}
    dernier_jeu_service_perdu = {0: False, 1: False}
    for st, num, serveur, seq in jeux:
        k = 0 if serveur == 1 else 1
        p = p_srv[k]
        gh, ga = jeux_set.get(st, (0, 0))
        gs, gr = (gh, ga) if k == 0 else (ga, gh)
        tb = gh == 6 and ga == 6
        ps = pr = 0
        gagne_jeu = None
        rebond = dernier_jeu_service_perdu[k]
        for c in seq:
            gagne = (c == 'H') == (k == 0)
            if not tb:
                chaud = (ps == 2 and pr == 2) or (ps >= 3 and pr >= 3 and ps >= pr)   # 30-30, égalité, avantage service
                if chaud:
                    acc[k][0] += gagne - p
                    acc[k][1] += 1
                if rebond:
                    acc[k][2] += gagne - p
                    acc[k][3] += 1
            ps, pr = (ps + 1, pr) if gagne else (ps, pr + 1)
            if not tb and ((ps >= 4 and ps - pr >= 2) or (pr >= 4 and pr - ps >= 2)):
                gagne_jeu = ps > pr
                break
        if gagne_jeu is None:
            gagne_jeu = (seq[-1] == 'H') == (k == 0) if seq else None
        if gagne_jeu is None:
            continue
        if not tb and gs >= 5 and gs > gr:                    # sert pour le set
            acc[k][4] += gagne_jeu - Mo.p_jeu(min(max(p, 0.3), 0.95))
            acc[k][5] += 1
        if not tb:
            dernier_jeu_service_perdu[k] = not gagne_jeu
        if gagne_jeu == (k == 0):                                # home gagne le jeu
            gh += 1
        else:
            ga += 1
        jeux_set[st] = (gh, ga)
    return acc
MCP_DIR = os.environ.get('MCP_DIR', '/tmp/mcp')
ABSENCE_J = 45
# Code pays des joueurs (TennisApi, ISO alpha-3) → ISO alpha-2 (géocodage des tournois).
ISO3_2 = {'ARG': 'AR', 'AUS': 'AU', 'AUT': 'AT', 'BEL': 'BE', 'BGR': 'BG', 'BIH': 'BA', 'BLR': 'BY', 'BOL': 'BO', 'BRA': 'BR',
          'CAN': 'CA', 'CHE': 'CH', 'CHL': 'CL', 'CHN': 'CN', 'COL': 'CO', 'CRI': 'CR', 'CYP': 'CY', 'CZE': 'CZ', 'DEU': 'DE',
          'DNK': 'DK', 'DOM': 'DO', 'ECU': 'EC', 'EGY': 'EG', 'ESP': 'ES', 'EST': 'EE', 'FIN': 'FI', 'FRA': 'FR', 'GBR': 'GB',
          'GEO': 'GE', 'GRC': 'GR', 'HKG': 'HK', 'HRV': 'HR', 'HUN': 'HU', 'IDN': 'ID', 'IND': 'IN', 'IRL': 'IE', 'ISR': 'IL',
          'ITA': 'IT', 'JPN': 'JP', 'KAZ': 'KZ', 'KOR': 'KR', 'LTU': 'LT', 'LUX': 'LU', 'LVA': 'LV', 'MAR': 'MA', 'MCO': 'MC',
          'MDA': 'MD', 'MEX': 'MX', 'MKD': 'MK', 'MLT': 'MT', 'MNE': 'ME', 'NLD': 'NL', 'NOR': 'NO', 'NZL': 'NZ', 'PAK': 'PK',
          'PER': 'PE', 'PHL': 'PH', 'POL': 'PL', 'PRT': 'PT', 'PRY': 'PY', 'ROU': 'RO', 'RUS': 'RU', 'SAU': 'SA', 'SGP': 'SG',
          'SRB': 'RS', 'SVK': 'SK', 'SVN': 'SI', 'SWE': 'SE', 'THA': 'TH', 'TPE': 'TW', 'TWN': 'TW', 'TUN': 'TN', 'TUR': 'TR',
          'UKR': 'UA', 'URY': 'UY', 'USA': 'US', 'UZB': 'UZ', 'VEN': 'VE', 'VNM': 'VN', 'ZAF': 'ZA', 'ZWE': 'ZW', 'ARE': 'AE',
          'QAT': 'QA', 'BHR': 'BH', 'ARM': 'AM', 'AZE': 'AZ', 'ISL': 'IS', 'LBN': 'LB', 'JOR': 'JO', 'KEN': 'KE', 'NGA': 'NG',
          'MYS': 'MY', 'PRI': 'PR', 'GTM': 'GT', 'SLV': 'SV', 'PAN': 'PA', 'BRB': 'BB', 'JAM': 'JM', 'TTO': 'TT', 'CUB': 'CU',
          'ALB': 'AL', 'AND': 'AD', 'MON': 'MC', 'GER': 'DE', 'NED': 'NL', 'SUI': 'CH', 'POR': 'PT', 'CRO': 'HR', 'GRE': 'GR',
          'RSA': 'ZA', 'CHI': 'CL', 'URU': 'UY', 'PAR': 'PY', 'BUL': 'BG', 'SLO': 'SI', 'DEN': 'DK', 'LAT': 'LV', 'INA': 'ID'}


def charger_lieux(racine):
    """(tournois, météo) écrits par scripts/lieux_tournois.py ; vides si absents."""
    out = []
    for nom in ('tournois.json', 'meteo.json'):
        try:
            with open(os.path.join(racine, 'feuilles', nom), encoding='utf-8') as f:
                out.append(json.load(f))
        except (OSError, ValueError):
            out.append({})
    return tuple(out)
K_H2H = 150.0
STYLE_COMPS = (('a', 'S'), ('w1', 'S'), ('w2j', 'S'), ('w1', 'R'), ('w2j', 'R'))


def style(adj, j):
    """Style d'un joueur dans le modèle ajusté : (ace, 1re, 2e au service ; 1re, 2e au retour), en logit."""
    A = getattr(adj, 'fond', adj)
    if A is None or not hasattr(A, 'eff'):
        return (0.0,) * 5
    return tuple(A.eff[c][t].get(j, 0.0) for c, t in STYLE_COMPS)


def variables_style(st_j, st_adv):
    """Produits service du serveur × retour de l'adversaire (×4 : effets de l'ordre de 0,1–0,3 en logit)."""
    return {'style_ace_x_retour': 16 * st_j[0] * st_adv[3], 'style_1re_x_retour': 16 * st_j[1] * st_adv[3],
            'style_2e_x_retour': 16 * st_j[2] * st_adv[4]}


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sg(z):
    return 1 / (1 + math.exp(-z))


# ------------------------------------------------------------------ historique (accumulateurs point-in-time)
class Historique:
    """Ce qu'on sait de chaque joueur et de chaque tournoi à un instant donné."""

    def __init__(self):
        self.forme = collections.defaultdict(collections.deque)   # joueur -> (t, res_srv, n_srv, res_ret, n_ret)
        self.sets = collections.defaultdict(list)                 # joueur -> [(t, sets joués)]
        self.clutch = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])   # Σ(sauvées−attendu), Σ bp, Σ(conv−att), Σ bp obtenues
        self.vit = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])      # tournoi -> Σres srv, Σn, Σres aces, Σ in1
        self.h2h = collections.defaultdict(lambda: [0.0, 0.0])                # (serveur, adversaire) -> Σres, Σn
        self.parcours = collections.defaultdict(list)                          # joueur -> [(t, tournoi)]
        self.pays, self.interieur = {}, {}
        self.lieux, self.meteo = {}, {}
        self.charting = None
        self.abandons = collections.defaultdict(list)                          # joueur -> [t] (abandon, forfait)
        self.minutes = collections.defaultdict(list)                           # joueur -> [(t, minutes)] (durée)
        self.pression = collections.defaultdict(lambda: [0.0, 0, 0.0, 0, 0.0, 0, 0.0, 0])   # + Σ, n au retour (pression)
        # 24/10/2026 — matchup : [Σ résidu retour × force service adverse, Σ n × force², Σ résidu service × force
        # retour adverse, Σ n × force²] ; adversaires déjà affrontés (adversaires communs)
        self.mu = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        self.adv = collections.defaultdict(set)
        # 28/10/2026 — profil de réaction : joueur -> [Σ résidu × trait, Σ n × trait²] par trait, au service ('s') et au retour ('r')
        self.pf = collections.defaultdict(lambda: {'s': [[0.0, 0.0] for _ in PF_TRAITS], 'r': [[0.0, 0.0] for _ in PF_TRAITS]})
        self.infos = {}

    def ajouter_h2h(self, j, adv, res, n):
        h = self.h2h[(j, adv)]
        h[0] += res
        h[1] += n
        self.adv[j].add(adv)
        self.adv[adv].add(j)

    def ajouter_matchup(self, x):
        """Pentes du matchup, depuis les styles du modèle ajusté (force du service : ace + 1re ; du retour : 1re + 2e)."""
        st = x.get('style')
        if not st:
            return
        for k in (0, 1):
            j, o = (x['a'], x['b'])[k], (x['b'], x['a'])[k]
            r = x['srv'][k]
            s_srv = st[k][0] + st[k][1]
            q_ret = st[1 - k][3] + st[1 - k][4]
            m_o, m_j = self.mu[o], self.mu[j]
            m_o[0] += -r['res'] * s_srv
            m_o[1] += r['n'] * s_srv * s_srv
            m_j[2] += r['res'] * q_ret
            m_j[3] += r['n'] * q_ret * q_ret

    def traits(self, j, st, jour=None):
        """Traits standardisés d'un joueur, tels qu'un adversaire les voit (point-in-time)."""
        i = self.infos.get(j) or {}
        g = (1.0 if i['main'] == 'gauche' else 0.0) if i.get('main') else PF_CENTRE[5]
        h = taille_centree(i) if i.get('taille_cm') else PF_CENTRE[6]
        ech = 0.0
        if self.charting is not None:
            try:
                ech = self.charting.profil(j, jour)[2]
            except Exception:
                ech = 0.0
        brut = (st[0], st[1], st[2], st[3], st[4], g, h, ech or PF_CENTRE[7])
        return tuple((v - c) / e for v, c, e in zip(brut, PF_CENTRE, PF_ECHELLE))

    def ajouter_profil(self, x):
        """Pentes du profil de réaction, après le match (résidus de points au-delà du modèle ajusté)."""
        st = x.get('style')
        if not st:
            return
        T = (self.traits(x['a'], st[0], x.get('jour')), self.traits(x['b'], st[1], x.get('jour')))
        for k in (0, 1):
            j, o = (x['a'], x['b'])[k], (x['b'], x['a'])[k]
            r = x['srv'][k]
            if not r['n']:
                continue
            pj, po = self.pf[j]['s'], self.pf[o]['r']
            for d in range(len(PF_TRAITS)):
                zo, zj = T[1 - k][d], T[k][d]
                pj[d][0] += r['res'] * zo                 # j au service, selon le trait d de son adversaire
                pj[d][1] += r['n'] * zo * zo
                po[d][0] += -r['res'] * zj                # o au retour, selon le trait d du serveur j
                po[d][1] += r['n'] * zj * zj

    def variables_profil(self, j, adv, st_j, st_adv, jour=None):
        """Profil de réaction, du point de vue de j au service contre adv : 8 + 8 variables (logit ×4)."""
        zj, za = self.traits(j, st_j, jour), self.traits(adv, st_adv, jour)
        pj, pa = self.pf.get(j), self.pf.get(adv)
        out = {}
        for d, nom in enumerate(PF_TRAITS):
            s_ = pj['s'][d] if pj else (0.0, 0.0)
            r_ = pa['r'][d] if pa else (0.0, 0.0)
            out[f'pf_srv_{nom}'] = 4 * za[d] * s_[0] / (s_[1] + K_PF)
            out[f'pf_ret_adv_{nom}'] = -4 * zj[d] * r_[0] / (r_[1] + K_PF)
        return out

    def variables_avancees(self, j, adv, st_j, st_adv):
        """Matchup et adversaires communs, du point de vue de j au service contre adv."""
        s_j = st_j[0] + st_j[1]
        q_a = st_adv[3] + st_adv[4]
        ma, mj = self.mu.get(adv) or [0.0] * 4, self.mu.get(j) or [0.0] * 4
        num = den = 0.0
        communs = (self.adv.get(j) or set()) & (self.adv.get(adv) or set())
        for o in communs - {j, adv}:
            vals = []
            for p in (j, adv):
                hs, hr = self.h2h.get((p, o)) or (0.0, 0.0), self.h2h.get((o, p)) or (0.0, 0.0)
                n = hs[1] + hr[1]
                vals.append(((hs[0] - hr[0]) / n, n) if n else None)
            if vals[0] and vals[1]:
                w = min(vals[0][1], vals[1][1])
                num += w * (vals[0][0] - vals[1][0])
                den += w
        return {'mu_ret_adv': 4 * s_j * ma[0] / (ma[1] + K_MU), 'mu_srv': 4 * q_a * mj[2] / (mj[3] + K_MU),
                'communs_srv': 4 * num / (den + K_COM)}

    def ajouter_clutch(self, j, adv, det_j, det_adv):
        sv, in1, w1, w2 = det_j[:4]
        bpf, bps = det_j[6], det_j[7]
        p = (w1 + w2) / sv if sv else 0.6
        c = self.clutch[j]
        c[0] += bps - bpf * p
        c[1] += bpf
        osv, _, ow1, ow2 = det_adv[:4]
        obpf, obps = det_adv[6], det_adv[7]
        po = (ow1 + ow2) / osv if osv else 0.6
        c[2] += (obpf - obps) - obpf * (1 - po)
        c[3] += obpf

    def ajouter(self, x):
        """x : ligne préparée (après le match)."""
        t = x['t']
        for k, j in enumerate((x['a'], x['b'])):
            r = x['srv'][k]
            ro = x['srv'][1 - k]
            self.forme[j].append((t, r['res'], r['n'], -ro['res'], ro['n']))
            self.sets[j].append((t, x['nb_sets']))
            if x.get('duree_min'):
                self.minutes[j].append((t, x['duree_min'], x['tournoi']))
            self.ajouter_h2h(j, (x['b'], x['a'])[k], r['res'], r['n'])
            self.parcours[j].append((t, x['tournoi']))
            if (x.get('pays') or (None, None))[k]:
                self.pays[j] = x['pays'][k]
        if x.get('interieur'):
            self.interieur[x['tournoi']] = True
        if x.get('pbp'):
            dh, da = x['det']
            p_srv = tuple(((d[2] + d[3]) / d[0]) if d[0] else 0.6 for d in (dh, da))
            acc = pression_du_match(x['pbp'], p_srv)
            for k, j in ((0, x['a']), (1, x['b'])):
                P_ = self.pression[j]
                for i in range(6):
                    P_[i] += acc[k][i]
                o = self.pression[(x['b'], x['a'])[k]]          # au retour : l'inverse de l'adversaire sous pression
                o[6] -= acc[k][0]
                o[7] += acc[k][1]
        self.ajouter_matchup(x)
        self.ajouter_profil(x)
        da, db = x['det']
        self.ajouter_clutch(x['a'], x['b'], da, db)
        self.ajouter_clutch(x['b'], x['a'], db, da)
        v = self.vit[x['tournoi']]
        for r in x['srv']:
            v[0] += r['res']
            v[1] += r['n']
            v[2] += r['res_ace']
            v[3] += r['in1']

    def variables(self, j, adv, tournoi, t, infos):
        """Variables du point de vue de j au service contre adv, à l'instant t (secondes)."""
        def forme(p):
            q = self.forme[p]
            while q and q[0][0] < t - FENETRE_FORME_J * 86400:
                q.popleft()
            rs = sum(e[1] for e in q)
            ns = sum(e[2] for e in q)
            rr = sum(e[3] for e in q)
            nr = sum(e[4] for e in q)
            return rs / (ns + K_FORME), rr / (nr + K_FORME)

        def fatigue(p):
            L = self.sets[p]
            s3 = sum(s for tt, s in L if t - 3 * 86400 <= tt < t)
            der = max((tt for tt, _ in L if tt < t), default=None)
            repos = min((t - der) / 86400, 10.0) if der else 10.0
            return s3, repos

        def duree(p):
            L = [e if len(e) == 3 else (e[0], e[1], None) for e in (self.minutes.get(p) or ())]
            mt = sum(m for tt, m, tr in L if tr == tournoi and t - 16 * 86400 <= tt < t)
            m7 = sum(m for tt, m, _ in L if t - 7 * 86400 <= tt < t)
            der = max(((tt, m) for tt, m, _ in L if tt < t), default=None)
            return mt / 100.0, m7 / 100.0, (der[1] / 100.0 if der and t - der[0] <= 2 * 86400 else 0.0)

        fs, _ = forme(j)
        _, fr_adv = forme(adv)
        s3, rep = fatigue(j)
        s3a, repa = fatigue(adv)
        v = self.vit.get(tournoi) or [0.0, 0.0, 0.0, 0.0]
        cj, ca = self.clutch.get(j) or [0, 0, 0, 0], self.clutch.get(adv) or [0, 0, 0, 0]
        ij, ia = infos.get(j) or {}, infos.get(adv) or {}
        g_j, g_a = 1.0 if ij.get('main') == 'gauche' else 0.0, 1.0 if ia.get('main') == 'gauche' else 0.0
        taille = taille_centree
        lieu = self.lieux.get(tournoi) or {}
        inter = 1.0 if (lieu.get('interieur') or self.interieur.get(tournoi)) else 0.0
        jour = dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
        met = (self.meteo.get(tournoi) or {}).get(jour)

        def domicile(p):
            c = ISO3_2.get(str(self.pays.get(p) or '').upper())
            return 1.0 if c and lieu.get('code') and c == str(lieu['code']).upper() else 0.0

        def parcours(p):
            L = [e for e in self.parcours.get(p, ()) if e[0] < t]
            if not L:
                return 0.0, 0.0, 0.0, 0.0
            der = L[-1]
            absence = 1.0 if t - der[0] > ABSENCE_J * 86400 else 0.0
            ici = sum(1 for tt, tr in L if tr == tournoi and t - tt <= 14 * 86400)
            ailleurs = sum(1 for tt, tr in L if tr != tournoi and t - tt <= 10 * 86400)
            voyage = 0.0
            if der[1] != tournoi and t - der[0] <= 10 * 86400:
                l0 = self.lieux.get(der[1]) or {}
                if l0.get('lon') is not None and lieu.get('lon') is not None:
                    dlon = abs(l0['lon'] - lieu['lon'])
                    voyage = min(min(dlon, 360 - dlon) / 15.0, 12.0) / 6.0          # heures de décalage / 6
            return min(ici, 4) / 4, absence, min(ailleurs, 5) / 5, voyage
        ici_j, abs_j, ench_j, voy_j = parcours(j)
        ici_a, abs_a, ench_a, voy_a = parcours(adv)
        cond = {'altitude': (lieu.get('altitude') or 0.0) / 1000.0, 'interieur': inter,
                'chaleur': (1 - inter) * ((met[0] - 25.0) / 10.0) if met else 0.0,
                'vent': (1 - inter) * ((met[1] - 15.0) / 10.0) if met else 0.0,
                'domicile_srv': domicile(j), 'domicile_adv': domicile(adv), 'voyage_srv': voy_j, 'voyage_adv': voy_a,
                'deja_ici_srv': ici_j, 'deja_ici_adv': ici_a, 'absence_srv': abs_j, 'absence_adv': abs_a,
                'enchaine_srv': ench_j, 'enchaine_adv': ench_a}
        def blessure(p):
            A = [ta for ta in self.abandons.get(p, ()) if ta < t]
            if not A:
                return 0.0, 0.0, 0.0
            der = max(A)
            poids = 0.5 ** ((t - der) / 86400 / DEMI_VIE_ABANDON_J)
            n90 = sum(1 for ta in A if t - ta <= 90 * 86400)
            joue_depuis = any(der < tt < t for tt, _ in self.parcours.get(p, ()))
            return poids, min(n90, 2) / 2, (0.0 if joue_depuis else poids)
        bj, bj90, rj = blessure(j)
        ba, ba90, ra = blessure(adv)
        pj, pa_ = self.pression.get(j) or [0.0] * 8, self.pression.get(adv) or [0.0] * 8
        (mtj, m7j, mdj), (mta, m7a, mda) = duree(j), duree(adv)
        cond.update({'minutes_tournoi_srv': mtj, 'minutes_tournoi_adv': mta, 'minutes7_srv': m7j, 'minutes7_adv': m7a,
                     'minutes_dernier_srv': mdj, 'minutes_dernier_adv': mda})
        cond.update({'pression_srv': 4 * pj[0] / (pj[1] + K_PRESSION), 'pression_ret_adv': 4 * pa_[6] / (pa_[7] + K_PRESSION),
                     'rebond_srv': 4 * pj[2] / (pj[3] + K_PRESSION), 'pour_le_set_srv': 4 * pj[4] / (pj[5] + K_PRESSION / 6)})
        cond.update({'abandon_srv': bj, 'abandon_adv': ba, 'abandons90_srv': bj90, 'abandons90_adv': ba90,
                     'retour_abandon_srv': rj, 'retour_abandon_adv': ra})
        if self.charting is not None:
            d_ = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
            cond.update(CH.variables(self.charting.profil(j, d_), self.charting.profil(adv, d_)))
        else:
            cond.update(CH.variables((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
        return {**cond, 'forme_srv': 4 * fs, 'forme_ret_adv': 4 * fr_adv, 'sets3_srv': s3 / 3, 'sets3_adv': s3a / 3,
                'repos_srv': rep / 10, 'repos_adv': repa / 10,
                'vit_srv': 4 * v[0] / (v[1] + K_VITESSE), 'vit_ace': 10 * v[2] / (v[3] + K_VITESSE),
                'gaucher_srv': g_j, 'gaucher_adv': g_a, 'gaucher_contre_droitier': g_j * (1 - g_a),
                'taille_srv': taille(ij), 'taille_adv': taille(ia),
                'bp_constante': 1.0, 'clutch_srv': 4 * cj[0] / (cj[1] + K_CLUTCH), 'clutch_ret_adv': 4 * ca[2] / (ca[3] + K_CLUTCH),
                'h2h_srv': 4 * (self.h2h.get((j, adv)) or [0.0, 0.0])[0] / ((self.h2h.get((j, adv)) or [0.0, 0.0])[1] + K_H2H)}


# ------------------------------------------------------------------ préparation des lignes
def preparer(fiches, adj_pour, cle=E.cle):
    """Lignes chronologiques des feuilles (ATP/WTA/CH, terminées, feuille complète), avec la base
    du modèle ajusté au moment du match (adj_pour(date) -> Ajuste)."""
    out = []
    for r in sorted(fiches, key=lambda r: r.get('debut') or 0):
        if FE.circuit_de(r.get('categorie')) not in ('ATP', 'WTA', 'CH') or not r.get('debut'):
            continue
        if str((r.get('statut') or {}).get('texte') or '').lower() != 'ended':
            continue
        st = (r.get('stats') or {}).get('ALL') or {}
        dh, da = FE.detail(st, 0), FE.detail(st, 2)
        if not dh or not da:
            continue
        circ, surf = FE.circuit_de(r.get('categorie')), FE.surface_de(r.get('surface'))
        a, b = cle(r['home'].get('nom')), cle(r['away'].get('nom'))
        jour = dt.date.fromisoformat(r['jour'])
        adj = adj_pour(jour)
        srv = []
        for j, o, d in ((a, b, dh), (b, a, da)):
            tx = S.borner(adj.taux(j, o, circ, surf))
            sv, in1, w1, w2, ace, df = d[:6]
            sec = sv - in1
            p = S.p_service(tx)
            srv.append({'tx': tx, 'n': sv, 'res': (w1 + w2) - sv * p, 'in1': in1, 'res_ace': ace - in1 * tx['a'],
                        'w1': (in1, w1), 'w2j': (sec - df, w2), 'ace': (in1, ace), 'bp': (d[6], d[7]), 'p': p})
        nb_sets = len(r['score_home'].get('sets') or [])
        out.append({'style': (style(adj, a), style(adj, b)), 'id': r.get('id'),
                    'interieur': 'indoor' in str(r.get('surface') or '').lower(),
                    'pays': (r['home'].get('pays'), r['away'].get('pays')), 't': r['debut'], 'jour': jour, 'a': a, 'b': b, 'circuit': circ, 'surface': surf,
                    'tournoi': str(r.get('tournoi_id') or r.get('tournoi')), 'nom_tournoi': r.get('tournoi_unique') or r.get('tournoi'),
                    'srv': srv, 'det': (dh, da), 'nb_sets': nb_sets, 'duree_min': r.get('duree_min'),
                    # 23/10/2026 : rang relevé le jour du match ou avant (jamais un rang relevé après coup)
                    'rangs': tuple((r[c].get('rang') if (r[c].get('rang_releve_le') or '9999') <= str(jour) else None)
                                   for c in ('home', 'away')),
                    'vainqueur': 0 if r.get('vainqueur') == 1 else 1, 'bo': r.get('meilleur_des') or 3,
                    'tour': r.get('tour')})
    return out


def infos_par_cle(racine, fiches, cle=E.cle):
    """{clé joueur: {main, taille_cm, femme}} depuis feuilles/joueurs.json (ids) et les noms des fiches.
    femme : le joueur apparaît dans une catégorie WTA ou ITF femmes (centre de taille de son circuit)."""
    try:
        with open(os.path.join(racine, 'feuilles', 'joueurs.json'), encoding='utf-8') as f:
            J = json.load(f)
    except (OSError, ValueError):
        J = {}
    out = {}
    for r in fiches:
        for c in ('home', 'away'):
            j = r.get(c) or {}
            i = str(j.get('id'))
            if i in J:
                cat = str(r.get('categorie') or '').lower()
                out[cle(j.get('nom'))] = dict(J[i], femme=('wta' in cat or 'women' in cat))
    return out


def abandons_des_fiches(fiches, cle=E.cle):
    """[(t, joueur)] : perdant d'un match « Retired », « Walkover » ou « Defaulted » (feuilles TennisApi)."""
    out = []
    for r in fiches:
        txt = str((r.get('statut') or {}).get('texte') or '').lower()
        if txt in ('retired', 'walkover', 'defaulted') and r.get('vainqueur') in (1, 2) and r.get('debut'):
            perdant = r['away'] if r['vainqueur'] == 1 else r['home']
            out.append((float(r['debut']), cle(perdant.get('nom'))))
    return sorted(out)


# ------------------------------------------------------------------ 22/10/2026 : qualifiés, changement de surface
QUALIF_J = 10                # un match de qualification ici dans les 10 jours = joueur sorti des qualifications
TRANSITION_J = 21            # aucun match sur cette surface parmi ceux des 21 derniers jours = il vient d'en changer


def parcours_des_fiches(fiches, cle=E.cle):
    """(qualifs, surfaces) : {joueur: [(t, tournoi)]} des matchs de QUALIFICATION, et {joueur: [(t, surface)]}
    de tous ses matchs (Hard / Clay / Grass), depuis les feuilles TennisApi."""
    Q, Sf = {}, {}
    for r in fiches:
        if not r.get('debut'):
            continue
        t, tr = float(r['debut']), str(r.get('tournoi_id') or r.get('tournoi'))
        su = FE.surface_de(r.get('surface'))
        q = 'qualif' in str(r.get('tour') or '').lower()
        for cote in ('home', 'away'):
            j = cle((r.get(cote) or {}).get('nom'))
            if not j:
                continue
            Sf.setdefault(j, []).append((t, su))
            if q:
                Q.setdefault(j, []).append((t, tr))
    for d in (Q, Sf):
        for L in d.values():
            L.sort()
    return Q, Sf


def qualifie(Q, j, tournoi, t):
    """1 si le joueur a joué un match de qualification dans CE tournoi dans les 10 jours avant t."""
    return 1.0 if any(tr == tournoi and 0 < t - tt <= QUALIF_J * 86400 for tt, tr in Q.get(j) or ()) else 0.0


def transition(Sf, j, surface, t):
    """1 si le joueur a joué dans les 21 jours avant t, mais jamais sur cette surface : il vient d'en changer."""
    rec = [su for tt, su in Sf.get(j) or () if 0 < t - tt <= TRANSITION_J * 86400]
    return 1.0 if rec and surface not in rec else 0.0


def avec_variables(lignes, infos, avant=None, final=False, adj_avant=None, lieux=None, charting=None, abandons=None, points=None):
    """Ajoute à chaque ligne les variables point-in-time des deux serveurs ; avant : matchs de
    l'archive pour les balles de break (format donnees.charger) ; adj_avant : modèle ajusté à la fin
    de l'archive, pour les face-à-face de l'archive (écart au service attendu, 4 dernières années)."""
    H = Historique()
    H.infos = infos or {}
    if lieux:
        H.lieux, H.meteo = lieux[0] or {}, lieux[1] or {}
    H.charting = charting
    lim = None
    if avant and adj_avant is not None:
        lim = max(m['date'] for m in avant) - dt.timedelta(days=4 * 365)
    for m in avant or []:
        if m.get('abandon'):
            fin_ = m.get('fin') or m['date']
            H.abandons[E.cle(m['nom_p'])].append(dt.datetime(fin_.year, fin_.month, fin_.day, tzinfo=dt.timezone.utc).timestamp())
        d = m.get('detail')
        if d:
            g, p = E.cle(m['nom_g']), E.cle(m['nom_p'])
            H.ajouter_clutch(g, p, d['w'], d['l'])
            H.ajouter_clutch(p, g, d['l'], d['w'])
            if lim is not None and m['date'] >= lim and m['circuit'] in ('ATP', 'WTA', 'CH'):
                for j, o, dj in ((g, p, d['w']), (p, g, d['l'])):
                    sv, in1, w1, w2 = dj[:4]
                    if sv:
                        H.ajouter_h2h(j, o, (w1 + w2) - sv * S.p_service(S.borner(adj_avant.taux(j, o, m['circuit'], m['surface']))), sv)
    attente = []
    ab = list(abandons or [])
    k_ab = 0
    for x in lignes:
        while attente and attente[0][0] <= x['t']:
            _, _, y = heapq.heappop(attente)
            H.ajouter(y)
        while k_ab < len(ab) and ab[k_ab][0] + DISPO_H * 3600 <= x['t']:
            H.abandons[ab[k_ab][1]].append(ab[k_ab][0])
            k_ab += 1
        if points and x.get('id') in points:
            x['pbp'] = points[x['id']]
        x['var'] = [H.variables(x['a'], x['b'], x['tournoi'], x['t'], infos),
                    H.variables(x['b'], x['a'], x['tournoi'], x['t'], infos)]
        st = x.get('style') or ((0.0,) * 5, (0.0,) * 5)
        x['var'][0].update(variables_style(st[0], st[1]))
        x['var'][1].update(variables_style(st[1], st[0]))
        x['var'][0].update(H.variables_avancees(x['a'], x['b'], st[0], st[1]))
        x['var'][1].update(H.variables_avancees(x['b'], x['a'], st[1], st[0]))
        x['var'][0].update(H.variables_profil(x['a'], x['b'], st[0], st[1], x['jour']))
        x['var'][1].update(H.variables_profil(x['b'], x['a'], st[1], st[0], x['jour']))
        heapq.heappush(attente, (x['t'] + DISPO_H * 3600, x['id'] or 0, x))
    while final and attente:                    # contexte du jour : tout ce qui est joué compte
        H.ajouter(heapq.heappop(attente)[2])
    while final and k_ab < len(ab):
        H.abandons[ab[k_ab][1]].append(ab[k_ab][0])
        k_ab += 1
    return H


# ------------------------------------------------------------------ régression logistique avec décalage
def lignes_modele(lignes, modele, feats):
    """[(n, k, offset, x)] pour le modèle 'service' (1re et 2e balle), 'aces' ou 'bp'."""
    out = []
    for x in lignes:
        for k in (0, 1):
            r, v = x['srv'][k], x['var'][k]
            xs = [v[f] for f in feats]
            if modele == 'service':
                out.append((r['w1'][0], r['w1'][1], _lg(r['tx']['w1']), xs))
                out.append((r['w2j'][0], r['w2j'][1], _lg(r['tx']['w2j']), xs))
            elif modele == 'aces':
                out.append((r['ace'][0], r['ace'][1], _lg(r['tx']['a']), xs))
            else:
                out.append((r['bp'][0], r['bp'][1], _lg(r['p']), xs))
    return [o for o in out if o[0] > 0]


def ajuster_logit(L, nf, ridge=RIDGE, tours=25):
    b = [0.0] * nf
    for _ in range(tours):
        g = [0.0] * nf
        H = [[0.0] * nf for _ in range(nf)]
        for n, k, off, x in L:
            p = _sg(off + sum(bi * xi for bi, xi in zip(b, x)))
            w = n * p * (1 - p)
            for i in range(nf):
                g[i] += (k - n * p) * x[i]
                for j in range(nf):
                    H[i][j] += w * x[i] * x[j]
        for i in range(nf):
            g[i] -= ridge * b[i]
            H[i][i] += ridge
        pas = resoudre(H, g)
        b = [bi + pi for bi, pi in zip(b, pas)]
        if max(abs(p) for p in pas) < 1e-7:
            break
    return b


def resoudre(A, y):
    n = len(y)
    M = [row[:] + [y[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def log_vrais(L, b):
    tot, n_tot = 0.0, 0
    for n, k, off, x in L:
        p = min(max(_sg(off + sum(bi * xi for bi, xi in zip(b, x))), 1e-9), 1 - 1e-9)
        tot -= k * math.log(p) + (n - k) * math.log(1 - p)
        n_tot += n
    return tot / n_tot if n_tot else None


# ------------------------------------------------------------------ deltas et vainqueur
def deltas(v, coefs):
    """(d_service, d_aces, d_bp) en logit pour un serveur, depuis ses variables et les coefficients.
    28/10/2026 : si coefs['_arbres_service'] (modèle complet adopté), il donne la correction des points de service."""
    d = {}
    for modele in ('service', 'aces', 'bp'):
        c = coefs.get(modele) or {}
        d[modele] = sum(b * v.get(f, 0.0) for f, b in c.items())
    arb = coefs.get('_arbres_service')
    if arb and arb.get('arbres'):
        import arbres as A
        d['service'] += A.correction(arb, [v.get(f, 0.0) for f in arb['variables']])
    return d['service'], d['aces'], d['bp']


def victoire_ligne(x, coefs, sigma=SIGMA):
    """P(vrai vainqueur) de la simulation pure (exacte), base + facteurs."""
    ca = S.appliquer_facteurs(x['srv'][0]['tx'], *deltas(x['var'][0], coefs))
    cb = S.appliquer_facteurs(x['srv'][1]['tx'], *deltas(x['var'][1], coefs))
    sg = 3 if x['bo'] == 5 else 2
    p = S.victoire_pure(ca, cb, sg, sigma)
    return p if x['vainqueur'] == 0 else 1 - p


def log_loss_vainqueur(lignes, coefs):
    L = [victoire_ligne(x, coefs) for x in lignes]
    if not L:
        return None, None
    ll = -sum(math.log(min(max(p, 1e-6), 1 - 1e-6)) for p in L) / len(L)
    ok = sum(1.0 if p > 0.5 else 0.5 if p == 0.5 else 0.0 for p in L) / len(L)
    return round(ll, 5), round(100 * ok, 1)


def apprendre(lignes, groupes):
    """Coefficients {modèle: {variable: β}} pour un ensemble de groupes."""
    coefs = {}
    for modele in ('service', 'aces', 'bp'):
        feats = []
        for g in groupes:
            for f in GROUPES[g].get(modele, []):
                if f not in feats:
                    feats.append(f)
        if feats:
            b = ajuster_logit(lignes_modele(lignes, modele, feats), len(feats))
            coefs[modele] = {f: round(x, 5) for f, x in zip(feats, b)}
    return coefs


def juger_groupe(appr, juge, g):
    coefs = apprendre(appr, [g])
    rapport = {'coefs': coefs, 'points': {}}
    mieux_points = True
    for modele, c in coefs.items():
        L = lignes_modele(juge, modele, list(c))
        base, avec = log_vrais(L, [0.0] * len(c)), log_vrais(L, list(c.values()))
        rapport['points'][modele] = {'base': round(base, 6) if base else None, 'avec': round(avec, 6) if avec else None}
        if base is None or avec is None or avec >= base:
            mieux_points = False
    ll0, ok0 = log_loss_vainqueur(juge, {})
    ll1, ok1 = log_loss_vainqueur(juge, coefs)
    rapport['vainqueur'] = {'base': {'log_loss': ll0, 'reussite_pct': ok0}, 'avec': {'log_loss': ll1, 'reussite_pct': ok1}}
    rapport['adopte'] = bool(mieux_points and ll0 is not None and ll1 <= ll0 + TOLERANCE_VAINQUEUR)
    rapport['vainqueur_mieux_trouve'] = bool(ll0 is not None and ll1 < ll0)
    rapport['raison'] = (f"points {'mieux' if mieux_points else 'pas mieux'} ; vainqueur log loss {ll0} → {ll1} "
                         f"(réussite {ok0} % → {ok1} %)")
    return rapport


# ------------------------------------------------------------------ 28/10/2026 : MODÈLE COMPLET (« rien n'écarter »)
# Toutes les variables de tous les groupes — adoptés ou non — données d'un coup à des arbres (arbres.py, boosting
# binomial sur les points de service, départ = base ajustée aux adversaires). Les arbres trouvent eux-mêmes ce qui
# compte et les combinaisons (ex. « bon contre les gros serveurs, mais seulement en salle »).
# RÈGLE FIXÉE LE 28/10/2026, AVANT TOUT RÉSULTAT — sur la fenêtre de jugement (6 dernières semaines, jamais vue) :
#   le modèle complet (appris sur l'apprentissage) remplace la partie « service » des groupes en place SI
#   (a) il prédit mieux les points de service que les groupes en place (vraisemblance) ET
#   (b) il baisse la log loss du vainqueur de la simulation pure d'AU MOINS 0,001 par rapport aux groupes en place ;
#   puis règle de stabilité : deux semaines de suite du même verdict pour entrer comme pour sortir.
# Adopté, il est ré-appris sur toutes les feuilles ; aces et balles de break restent ceux des groupes en place.
MARGE_COMPLET = 0.001


def variables_completes():
    """Toutes les variables « service » de tous les groupes, dans un ordre fixe."""
    out = []
    for g in GROUPES:
        for f in GROUPES[g].get('service', []):
            if f not in out:
                out.append(f)
    return out


def apprendre_complet(lignes, noms=None):
    import arbres as A
    noms = noms or variables_completes()
    L = lignes_modele(lignes, 'service', noms)
    m = A.apprendre_binomial([x for _, _, _, x in L], [n for n, _, _, _ in L], [k for _, k, _, _ in L],
                             [o for _, _, o, _ in L])
    m['variables'] = noms
    m['importance'] = A.importance(m, noms)
    return m


def log_vrais_complet(L, m):
    import arbres as A
    tot, n_tot = 0.0, 0
    for n, k, off, x in L:
        p = min(max(_sg(off + A.correction(m, x)), 1e-9), 1 - 1e-9)
        tot -= k * math.log(p) + (n - k) * math.log(1 - p)
        n_tot += n
    return tot / n_tot if n_tot else None


def juger_complet(appr, juge, adoptes):
    """Rapport du modèle complet contre les groupes en place (règle fixée ci-dessus), verdict BRUT."""
    champion = apprendre(appr, adoptes) if adoptes else {}
    m = apprendre_complet(appr)
    noms = m['variables']
    Lj = lignes_modele(juge, 'service', noms)
    c_srv = champion.get('service') or {}
    b_ch = [c_srv.get(f, 0.0) for f in noms]
    pts_ch, pts_co = log_vrais(Lj, b_ch), log_vrais_complet(Lj, m)
    complet = {k: v for k, v in champion.items() if k != 'service'}
    complet['_arbres_service'] = m
    ll_ch, ok_ch = log_loss_vainqueur(juge, champion)
    ll_co, ok_co = log_loss_vainqueur(juge, complet)
    adopte = bool(pts_ch is not None and pts_co is not None and pts_co < pts_ch
                  and ll_ch is not None and ll_co is not None and ll_co <= ll_ch - MARGE_COMPLET)
    return {'variables': len(noms), 'groupes_en_place': list(adoptes),
            'points_service': {'en_place': round(pts_ch, 6) if pts_ch else None, 'complet': round(pts_co, 6) if pts_co else None},
            'vainqueur': {'en_place': {'log_loss': ll_ch, 'reussite_pct': ok_ch}, 'complet': {'log_loss': ll_co, 'reussite_pct': ok_co}},
            'importance': dict(list(m['importance'].items())[:25]), 'reglages': m['reglages'], 'adopte': adopte,
            'raison': (f"points de service {pts_ch and round(pts_ch, 6)} → {pts_co and round(pts_co, 6)} ; vainqueur log loss "
                       f"{ll_ch} → {ll_co} (réussite {ok_ch} % → {ok_co} %) ; marge exigée {MARGE_COMPLET}")}


# ------------------------------------------------------------------ contexte pour les pronostics du jour
def contexte(H, infos, noms_tournois, maintenant_ts):
    """Ce que les pronostics du jour doivent savoir, à exporter en JSON."""
    t = maintenant_ts
    joueurs = {}
    tous = set(H.forme) | set(H.sets) | set(H.clutch) | set(infos)
    for j in tous:
        q = [e for e in H.forme.get(j, ()) if e[0] >= t - FENETRE_FORME_J * 86400]
        sets = [(tt, s) for tt, s in H.sets.get(j, ()) if tt >= t - 10 * 86400]
        c = H.clutch.get(j)
        i = infos.get(j) or {}
        e = {}
        if q:
            e['forme'] = [round(sum(x[1] for x in q), 2), round(sum(x[2] for x in q)), round(sum(x[3] for x in q), 2), round(sum(x[4] for x in q))]
        if sets:
            e['sets'] = [[int(tt), s] for tt, s in sets]
        mins = [e_ for e_ in H.minutes.get(j, ()) if e_[0] >= t - 16 * 86400]
        if mins:
            e['minutes'] = [[int(e_[0]), e_[1], e_[2] if len(e_) > 2 else None] for e_ in mins]
        if c and (c[1] or c[3]):
            e['clutch'] = [round(c[0], 2), round(c[1], 1), round(c[2], 2), round(c[3], 1)]
        if i.get('main') or i.get('taille_cm'):
            e['infos'] = {k: i[k] for k in ('main', 'taille_cm', 'femme') if i.get(k)}
        if e:
            joueurs[j] = e
    vit = {k: [round(x, 2) for x in v] for k, v in H.vit.items() if v[1] > 0}
    h2h = {f"{a}|{b}": [round(v[0], 2), round(v[1])] for (a, b), v in H.h2h.items() if v[1] > 0}
    for j, L in H.parcours.items():
        rec = [[int(tt), tr] for tt, tr in L if tt >= t - 60 * 86400]
        if not rec and L:
            rec = [[int(L[-1][0]), L[-1][1]]]                 # dernier match, pour l'« absence »
        if rec:
            joueurs.setdefault(j, {})['parcours'] = rec
        if H.pays.get(j):
            joueurs.setdefault(j, {})['pays'] = H.pays[j]
    for j, L in (getattr(H, 'qualifs', None) or {}).items():
        rec = [[int(tt), tr] for tt, tr in L if tt >= t - 30 * 86400]
        if rec:
            joueurs.setdefault(j, {})['qualifs'] = rec
    for j, L in (getattr(H, 'surfaces', None) or {}).items():
        rec = [[int(tt), su] for tt, su in L if tt >= t - 30 * 86400]
        if rec:
            joueurs.setdefault(j, {})['surfaces'] = rec
    for j, P_ in H.pression.items():
        if isinstance(j, str) and any(P_):
            joueurs.setdefault(j, {})['pression'] = [round(v, 3) for v in P_]
    for j, m_ in H.mu.items():
        if isinstance(j, str) and any(m_):
            joueurs.setdefault(j, {})['mu'] = [round(v, 4) for v in m_]
    for j, pf in H.pf.items():
        if isinstance(j, str) and any(e[1] for c in ('s', 'r') for e in pf[c]):
            joueurs.setdefault(j, {})['pf'] = {c: [[round(a, 4), round(b, 1)] for a, b in pf[c]] for c in ('s', 'r')}
    for j, A in H.abandons.items():
        rec = [int(ta) for ta in A if ta >= t - 90 * 86400]
        if rec:
            joueurs.setdefault(j, {})['abandons'] = rec
    actifs = {tr for L in H.parcours.values() for tt, tr in L if tt >= t - 60 * 86400}
    jour0 = (dt.datetime.fromtimestamp(t, dt.timezone.utc).date() - dt.timedelta(days=3)).isoformat()
    lieux = {k: v for k, v in H.lieux.items() if k in actifs or k in (noms_tournois or {})}
    meteo = {k: {j: v for j, v in d.items() if j >= jour0} for k, d in H.meteo.items() if k in lieux}
    ch_date = dt.datetime.fromtimestamp(t, dt.timezone.utc).date() + dt.timedelta(days=1)
    ch = H.charting.exporter(set(joueurs) | set(getattr(H.charting, 'D', {})), ch_date) if hasattr(H.charting, 'exporter') else {}
    ch_doc = {}
    if hasattr(H.charting, 'documentation'):
        for j in set(joueurs) | set(getattr(H.charting, 'D', {})):
            d = H.charting.documentation(j, ch_date)
            if d.get('matchs'):
                ch_doc[j] = d
    return {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'instant': t,
            'joueurs': joueurs, 'vitesse': vit, 'h2h': h2h, 'noms_tournois': noms_tournois,
            'interieur': sorted(H.interieur), 'lieux': lieux, 'meteo': meteo, 'charting': ch,
            'charting_documentation': ch_doc}


class Contexte:
    """Lecture du contexte exporté : variables d'un serveur pour un match à venir."""

    def __init__(self, doc):
        self.doc = doc or {}
        self.H = Historique()
        for j, e in (self.doc.get('joueurs') or {}).items():
            if 'forme' in e:
                rs, ns, rr, nr = e['forme']
                self.H.forme[j].append((self.doc.get('instant', 0), rs, ns, rr, nr))
            for v in e.get('minutes') or []:
                self.H.minutes[j].append(tuple(v) if len(v) == 3 else (v[0], v[1], None))
            for tt, s in e.get('sets') or []:
                self.H.sets[j].append((tt, s))
            if 'clutch' in e:
                self.H.clutch[j] = list(e['clutch'])
        for k, v in (self.doc.get('vitesse') or {}).items():
            self.H.vit[k] = list(v)
        for j, e in (self.doc.get('joueurs') or {}).items():
            for tt, tr in e.get('parcours') or []:
                self.H.parcours[j].append((tt, tr))
            if e.get('pays'):
                self.H.pays[j] = e['pays']
            if e.get('pression'):
                self.H.pression[j] = list(e['pression'])
            if e.get('mu'):
                self.H.mu[j] = list(e['mu'])
            if e.get('pf'):
                self.H.pf[j] = {c: [list(v) for v in e['pf'][c]] for c in ('s', 'r')}
            for ta in e.get('abandons') or []:
                self.H.abandons[j].append(float(ta))
        for k in self.doc.get('interieur') or []:
            self.H.interieur[k] = True
        self.H.lieux, self.H.meteo = self.doc.get('lieux') or {}, self.doc.get('meteo') or {}
        self.H.charting = CH.ChartingFige(self.doc.get('charting'), self.doc.get('charting_documentation'))
        for k, v in (self.doc.get('h2h') or {}).items():
            a, b = k.split('|', 1)
            self.H.h2h[(a, b)] = list(v)
            self.H.adv[a].add(b)
            self.H.adv[b].add(a)
        self.infos = {j: e['infos'] for j, e in (self.doc.get('joueurs') or {}).items() if e.get('infos')}
        self.H.infos = self.infos
        self.noms = self.doc.get('noms_tournois') or {}
        J = self.doc.get('joueurs') or {}
        self.qualifs = {j: [(float(tt), str(tr)) for tt, tr in e['qualifs']] for j, e in J.items() if e.get('qualifs')}
        self.surfaces = {j: [(float(tt), su) for tt, su in e['surfaces']] for j, e in J.items() if e.get('surfaces')}

    def qualifie(self, j, nom_tournoi, debut_ts):
        return qualifie(self.qualifs, j, self.tournoi(nom_tournoi), debut_ts)

    def transition(self, j, surface, debut_ts):
        return transition(self.surfaces, j, surface, debut_ts)

    def tournoi(self, nom):
        """Identifiant du tournoi collecté dont le nom partage le plus de mots avec `nom`."""
        import nos_resultats as NR
        cible = set(NR.mots_tournoi(nom))
        best, bs = None, 0
        for k, n in self.noms.items():
            s = len(cible & set(NR.mots_tournoi(n)))
            if s > bs:
                best, bs = k, s
        return best

    def variables(self, j, adv, nom_tournoi, debut_ts, adj=None):
        v = self.H.variables(j, adv, self.tournoi(nom_tournoi), debut_ts, self.infos)
        st_j, st_a = style(adj, j), style(adj, adv)
        v.update(variables_style(st_j, st_a))
        v.update(self.H.variables_avancees(j, adv, st_j, st_a))
        jour = dt.datetime.fromtimestamp(debut_ts, dt.timezone.utc).date() if debut_ts else None
        v.update(self.H.variables_profil(j, adv, st_j, st_a, jour))
        return v


# ------------------------------------------------------------------ programme principal
def main(argv):
    t0 = time.time()
    dossier = argv[1] if len(argv) > 1 else 'sackmann'
    racine = argv[2] if len(argv) > 2 else os.path.join(ICI, '..')
    M = donnees.charger(dossier, 2016)
    fiches = FE.lire(racine)
    fin_sack = max(x['date'] for x in M) if M else None             # calculé une fois (pas à chaque feuille)
    F = [m for m in FE.charger(racine) if fin_sack is None or m['date'] > fin_sack]
    tout = sorted(M + F, key=lambda m: m['date'])
    try:
        with open(os.path.join(ICI, 'choix_simulation.json'), encoding='utf-8') as f:
            choix = json.load(f)
    except (OSError, ValueError):
        choix = {}
    n0 = float(choix.get('n0') or AJ.N0)
    n0_comp = choix.get('n0_par_composante') or None
    dyn = AJ.lire_dynamique(choix)
    cache = {}

    def adj_pour(jour):
        m0 = jour.replace(day=1)
        if m0 not in cache:
            prec = cache[max(cache)] if cache else None
            cache[m0] = AJ.ajuster_choisi(tout, m0, E.cle, n0=n0, dyn=dyn, depart=prec,
                                          tours=6 if prec is None else 2, n0_par_composante=n0_comp)
            print(f"  base ajustée aux adversaires au {m0} ({round(time.time() - t0)} s)", flush=True)
        return cache[m0]

    lignes = preparer(fiches, adj_pour)
    infos = infos_par_cle(racine, fiches)
    mcp = argv[3] if len(argv) > 3 else MCP_DIR
    charting = CH.Charting(CH.charger(mcp))
    print(f"Match Charting Project : {len(charting.D)} joueurs relevés ({mcp})", flush=True)
    H = avec_variables(lignes, infos, avant=M, adj_avant=adj_pour(DEBUT_APPR), lieux=charger_lieux(racine), charting=charting,
                       abandons=abandons_des_fiches(fiches), points=charger_points(racine))
    d_appr, d_juge = fenetres()
    appr = [x for x in lignes if d_appr <= x['jour'] < d_juge]
    juge = [x for x in lignes if x['jour'] >= d_juge]
    print(f"Feuilles : {len(lignes)} matchs ATP/WTA/Challenger · apprentissage {len(appr)} ({d_appr} → {d_juge}) · "
          f"jugement {len(juge)} ({d_juge} →, 6 dernières semaines) · infos joueurs {len(infos)}", flush=True)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'fenetres': {'apprentissage': str(d_appr), 'jugement': str(d_juge)},
           'regle': ("Chaque groupe appris sur les feuilles jusqu'aux 6 dernières semaines, jugé sur ces 6 dernières "
                     "semaines (apprentissage continu, chaque semaine) : adopté s'il améliore la "
                     "vraisemblance des points concernés et ne dégrade pas l'erreur (log loss) du vainqueur de la "
                     "simulation pure de plus de 0,001."),
           'apprentissage': len(appr), 'jugement': len(juge), 'groupes': {}, 'adoptes': [], 'coefs': {}}
    if len(appr) < 300 or len(juge) < 300:
        doc['verdict'] = f"en attente de feuilles : {len(appr)} matchs d'apprentissage, {len(juge)} de jugement (300 de chaque au moins)"
        print(doc['verdict'])
    else:
        for g in GROUPES:
            rap = juger_groupe(appr, juge, g)
            doc['groupes'][g] = rap
            print(f"  {g:<18} {'ADOPTÉ' if rap['adopte'] else 'non adopté'} — {rap['raison']} · coefs {rap['coefs']}", flush=True)
        # 23/10/2026 — stabilité (stabilite.py) : un groupe entre ou sort après DEUX semaines de suite du même
        # verdict (pas de marge en log loss : la règle des groupes juge la vraisemblance des points).
        import stabilite as ST
        etat_st = ST.lire()
        try:
            with open(SORTIE, encoding='utf-8') as f:
                en_place = set(json.load(f).get('adoptes') or [])
        except (OSError, ValueError):
            en_place = set()
        for g, r in doc['groupes'].items():
            ok, note = ST.decider(etat_st, f"facteur:{g}", g in en_place, r['adopte'])
            r['adopte_brut'], r['adopte'], r['stabilite'] = r['adopte'], ok, note
            if ok != r['adopte_brut'] or g in en_place:
                print(f"    {g:<18} → {'en place' if ok else 'hors du modèle'} ({note})", flush=True)
        ST.ecrire(etat_st)
        doc['adoptes'] = [g for g, r in doc['groupes'].items() if r['adopte']]
        if doc['adoptes']:
            doc['coefs'] = apprendre(appr + juge, doc['adoptes'])          # ré-appris sur toutes les feuilles
            ll0, ok0 = log_loss_vainqueur(juge, {})
            ll1, ok1 = log_loss_vainqueur(juge, apprendre(appr, doc['adoptes']))
            doc['ensemble_sur_le_jugement'] = {'base': {'log_loss': ll0, 'reussite_pct': ok0},
                                               'avec': {'log_loss': ll1, 'reussite_pct': ok1}}
        doc['verdict'] = f"groupes adoptés : {', '.join(doc['adoptes']) or 'aucun'}"
        # 28/10/2026 — modèle complet (toutes les variables, arbres) contre les groupes en place
        try:
            try:
                with open(SORTIE, encoding='utf-8') as f:
                    complet_en_place = bool((json.load(f).get('modele_complet') or {}).get('adopte'))
            except (OSError, ValueError):
                complet_en_place = False
            rc = juger_complet(appr, juge, doc['adoptes'])
            etat_st = ST.lire()
            ok, note = ST.decider(etat_st, 'facteur:modele_complet', complet_en_place, rc['adopte'])
            ST.ecrire(etat_st)
            rc['adopte_brut'], rc['adopte'], rc['stabilite'] = rc['adopte'], ok, note
            if ok:
                m = apprendre_complet(appr + juge)
                doc['coefs'] = {k: v for k, v in (doc.get('coefs') or {}).items() if k != 'service'}
                doc['coefs']['_arbres_service'] = {k: m[k] for k in ('pas', 'arbres', 'variables', 'reglages')}
                doc['verdict'] += ' + modèle complet (service)'
            doc['modele_complet'] = rc
            print(f"  modele_complet     {'ADOPTÉ' if ok else 'non adopté'} — {rc['raison']} ({note})", flush=True)
            print(f"    variables les plus utilisées : {list(rc['importance'])[:10]}", flush=True)
        except Exception as e:
            print(f"::warning::Modèle complet non jugé : {type(e).__name__}: {e}")
        # 28/10/2026 — forme des scores selon les profils (forme_scores.py) : vainqueur inchangé par construction
        try:
            import forme_scores as FS
            import profil_rythme as PRY
            Lp = PRY.lignes(M + F, lambda n: E.cle(n) if n else None)
            prof_a, _ = PRY.calculer([x for x in Lp if x[0] < d_appr], d_appr)
            prof_j, _ = PRY.calculer([x for x in Lp if x[0] < d_juge], d_juge)

            def sets_reels(r):
                s_ = list(zip(r['score_home'].get('sets') or [], r['score_away'].get('sets') or []))
                return s_ if len(s_) in (2, 3) and all(u is not None and v is not None for u, v in s_) else None
            reels = {r.get('id'): sets_reels(r) for r in fiches}
            try:
                with open(SORTIE, encoding='utf-8') as f:
                    prec = json.load(f)
                    fs_prec = prec.get('forme_scores') or {}
                    fs_en_place = bool(fs_prec.get('adopte') and fs_prec.get('version') == 3)
                    sg_prec = prec.get('sigma_circuit') or {}
            except (OSError, ValueError):
                fs_en_place, sg_prec = False, {}
            # 28/10/2026 — forme du jour (σ) par circuit (sigma_circuit.py) : règle fixée, deux semaines de suite
            sigmas_en_place = None
            t_sg = time.time()
            try:
                import sigma_circuit as SGC
                rs = SGC.juger(appr, juge, reels)
                etat_st = ST.lire()
                # 28/10/2026 : en production par décision de Lucas → part « en place » ; sort après 2 semaines moins bien
                ok_s, note_s = ST.decider(etat_st, 'sigma_circuit_production', bool(sg_prec.get('adopte', True)), rs['adopte'])
                ST.ecrire(etat_st)
                rs['adopte_brut'], rs['adopte'], rs['stabilite'] = rs['adopte'], ok_s, note_s
                if ok_s and not rs['adopte_brut']:              # en place, pas encore sorti : on garde les σ en place
                    rs['sigmas'] = sg_prec.get('sigmas') or dict(SGC.DECISION)
                doc['sigma_circuit'] = rs
                sigmas_en_place = rs['sigmas'] if ok_s else None
                print(f"  sigma_circuit      {'ADOPTÉ' if ok_s else 'non adopté'} — gain {rs['gain']} · σ {rs['sigmas']} · "
                      f"par circuit {rs['par_circuit']} ({note_s}) · {round((time.time() - t_sg) / 60, 1)} min", flush=True)
            except Exception as e:
                print(f"::warning::σ par circuit non jugé : {type(e).__name__}: {e}")
            t_fs = time.time()
            rf = FS.juger(appr, juge, prof_a, prof_j, reels, sigmas=sigmas_en_place)
            print(f"  (forme des scores jugée en {round((time.time() - t_fs) / 60, 1)} min)", flush=True)
            etat_st = ST.lire()
            ok, note = ST.decider(etat_st, 'forme_scores_v3', fs_en_place, rf['adopte'])     # 28/10/2026 : v3 par circuit, série neuve
            ST.ecrire(etat_st)
            rf['adopte_brut'], rf['adopte'], rf['stabilite'] = rf['adopte'], ok, note
            doc['forme_scores'] = rf
            print(f"  forme_scores       {'ADOPTÉE' if ok else 'non adoptée'} — gain {rf['gain']} (marge {FS.MARGE}) · "
                  f"par circuit {rf.get('par_circuit')} · coefs {rf['coefs']} ({note})", flush=True)
        except Exception as e:
            print(f"::warning::Forme des scores non jugée : {type(e).__name__}: {e}")
    # Dépendances dynamiques : testées sur les points, jamais publiées sans backtest du vainqueur.
    try:
        import dependances_points as DP
        dep = DP.evaluer(lignes, doc.get('coefs') or {})
        dep['genere_le'] = dt.datetime.now(dt.timezone.utc).isoformat()
        with open(os.path.join(ICI, 'rapport_dependances_points.json'), 'w', encoding='utf-8') as f:
            json.dump(dep, f, ensure_ascii=False, indent=2)
        doc['dependances_points'] = {k: (v.get('confirmation') or {}).get('gain') for k, v in (dep.get('candidats') or {}).items()}
        print('Dépendances entre points :', dep['statut'], flush=True)
    except Exception as e:
        print(f"::warning::Tests de dépendances non faits : {type(e).__name__}: {e}")
    # 22/10/2026 — ENTRAÎNEMENT PROGRESSIF : la saison des feuilles rejouée semaine après semaine, l'algorithme
    # ré-entraîné à chaque fois sur le passé seulement (entrainement_progressif.py).
    try:
        import entrainement_progressif as EP
        import backtest_match_simule as BMS
        try:
            with open(os.path.join(ICI, 'elo_etat.json'), encoding='utf-8') as f:
                et = json.load(f)
        except (OSError, ValueError):
            et = {}
        rg = choix.get('reglage_simulation') or {}
        sigma = float(rg['sigma']) if rg.get('adopte') else SIGMA
        cb = choix.get('combinaison') or {}
        experience = {}
        p_elo = EP.elo_au_moment(M, lignes, et.get('options'), et.get('depart_bas'), experience=experience)
        Q, Sf = parcours_des_fiches(fiches)
        import classements as CLS
        CL = CLS.charger(dossier, racine)                      # 23/10/2026 : classement au jour du match
        CLS.exporter(CLS.charger(dossier), os.path.join(ICI, 'classements_sackmann.json'))
        situations = {}
        try:                                                   # 29/10/2026 : activité récente (activite.py)
            import activite as ACT
            AC = ACT.Activite.depuis(racine, fiches)
        except Exception as e_:  # noqa: BLE001
            print(f"::warning::activité non calculée : {type(e_).__name__}: {e_}")
            AC = None
        for x in lignes:                                       # (vrai vainqueur, perdant) pour chaque situation
            w, l = (x['a'], x['b']) if x['vainqueur'] == 0 else (x['b'], x['a'])
            jour_m = dt.datetime.fromtimestamp(x['t'], dt.timezone.utc)
            rh, ra = x.get('rangs') or (None, None)
            rw, rl = (rh, ra) if x['vainqueur'] == 0 else (ra, rh)
            rw, rl = rw or CL.rang_au(w, jour_m), rl or CL.rang_au(l, jour_m)
            nw, nl = experience.get(id(x), (None, None))
            w_rel = max(0.0, 1 - (nw or 0) / EP.SEUIL_RANG_RELATIF, 1 - (nl or 0) / EP.SEUIL_RANG_RELATIF) if nw is not None else 0.0
            situations[id(x)] = {'rangs': (rw, rl),
                                 # 28/10/2026 : classement relatif quand un joueur est peu connu (v_w − v_l = poids·(ln rl − ln rw))
                                 'classement_relatif': ((-w_rel * math.log(rw), -w_rel * math.log(rl))
                                                        if rw and rl and nw is not None else None),
                                 'qualifies': (qualifie(Q, w, x['tournoi'], x['t']), qualifie(Q, l, x['tournoi'], x['t'])),
                                 'transition': (transition(Sf, w, x['surface'], x['t']), transition(Sf, l, x['surface'], x['t'])),
                                 'classement': ((CLS.niveau_inconnu(rw, nw), CLS.niveau_inconnu(rl, nl))
                                                if nw is not None else None),
                                 'activite': (ACT.ecarts(AC.variables(w, x['jour']), AC.variables(l, x['jour']))
                                              if AC is not None else None),
                                 'tour': EP.variables_tour(x.get('tour')) if x.get('tour') else None,
                                 # 30/10/2026 : points ATP/WTA des deux joueurs au jour du match (vrai vainqueur, perdant)
                                 'points': CLS.ecart_points(CL.points_au(w, jour_m), CL.points_au(l, jour_m))}
        doc['entrainement_progressif'] = EP.rejouer_saison(
            lignes, p_elo, doc.get('adoptes') or [], apprendre, victoire_ligne, BMS.ajuster_poids, sigma,
            poids_archive=cb.get('poids') if cb.get('adopte') else None, experience=experience, situations=situations)
        ep = doc['entrainement_progressif']
        export = ep.pop('export', None) or []
        if export:                                     # 23/10/2026 : pour l'étude « l'algorithme sur les marchés »
            import gzip
            with gzip.open(os.path.join(ICI, 'pronostics_hors_echantillon.jsonl.gz'), 'wt', encoding='utf-8') as f:
                for e in export:
                    f.write(json.dumps(e, separators=(',', ':')) + '\n')
        print(f"Entraînement progressif : {len(ep.get('semaines', []))} semaines rejouées · "
              f"{'ADOPTÉ' if ep.get('adopte') else 'non adopté'} — {ep.get('raison')}", flush=True)
        for w in ep.get('semaines', []):
            c = w.get('combinaison') or {}
            print(f"  semaine {w['semaine']:>2} ({w['debut']}) · {w['n']:>4} matchs · simulation {w['simulation']['reussite_pct']} % · "
                  f"Elo {w['elo']['reussite_pct']} % · simulation + Elo {c.get('reussite_pct', '—')} % · poids simulation "
                  f"{w.get('poids_simulation_pct') if w.get('poids_simulation_pct') is not None else '—'} %", flush=True)
        # 23/10/2026 — chaque décision passe par la règle de stabilité (stabilite.py) : entrer = mieux d'au moins
        # 0,001 deux semaines de suite ; sortir = moins bien d'au moins 0,001 deux semaines de suite.
        import stabilite as ST
        etat_st = ST.lire()
        avant = {k: choix.get(k) for k in ('combinaison_feuilles', 'poids_challenger', 'poids_ATP', 'poids_WTA',
                                           'nouveaux_venus', 'modele_arbres', 'modele_arbres_activite', 'modele_arbres_tour',
                                           'modele_arbres_points',
                                           'desaccord_wta',
                                           'qualifies', 'transition', 'classement', 'classement_relatif')}
        choix['combinaison_feuilles'] = ST.appliquer(etat_st, 'combinaison_feuilles', avant['combinaison_feuilles'],
                                                     {k: ep.get(k) for k in ('adopte', 'poids', 'raison', 'poids_simulation_pct', 'll')},
                                                     ('poids', 'poids_simulation_pct'))
        choix['poids_challenger'] = ST.appliquer(etat_st, 'poids_challenger', avant['poids_challenger'],
                                                 {k: (ep.get('poids_challenger') or {}).get(k) for k in ('adopte', 'poids', 'raison', 'll')},
                                                 ('poids',))
        for c_ in ('ATP', 'WTA'):                          # 29/10/2026 : poids propres, même règle que les Challenger
            choix['poids_' + c_] = ST.appliquer(etat_st, 'poids_' + c_, avant['poids_' + c_],
                                                {k: (ep.get('poids_' + c_) or {}).get(k) for k in ('adopte', 'poids', 'raison', 'll')},
                                                ('poids',))
        choix['nouveaux_venus'] = ST.appliquer(etat_st, 'nouveaux_venus', avant['nouveaux_venus'],
                                               {k: (ep.get('nouveaux_venus') or {}).get(k) for k in ('adopte', 'delta', 'raison', 'll')},
                                               ('delta',))
        ma = ep.get('modele_arbres') or {}
        choix['modele_arbres'] = ST.appliquer(etat_st, 'modele_arbres', avant['modele_arbres'],
                                              {k: ma.get(k) for k in ('adopte', 'raison', 'variables', 'modele', 'poids', 'll')},
                                              ('variables', 'modele', 'poids'))
        print(f"Arbres (tout combiné) : {'ADOPTÉS' if choix['modele_arbres']['adopte'] else 'non adoptés'} — "
              f"{choix['modele_arbres']['raison']}", flush=True)
        dw_ = ep.get('desaccord_wta') or {}                     # 29/10/2026 : désaccords Elo / simulation en WTA
        choix['desaccord_wta'] = ST.appliquer(etat_st, 'desaccord_wta', avant['desaccord_wta'],
                                              {k: dw_.get(k) for k in ('adopte', 'poids', 'raison', 'll')}, ('poids',))
        print(f"Désaccords Elo / simulation en WTA : {'ADOPTÉ' if choix['desaccord_wta']['adopte'] else 'non adopté'} — "
              f"{choix['desaccord_wta']['raison']}", flush=True)
        for cle_c, lib_c in (('modele_arbres_activite', 'Arbres + activité récente'), ('modele_arbres_tour', 'Arbres + tour du tableau'),
                             ('modele_arbres_points', 'Arbres + points ATP/WTA')):
            maa = ep.get(cle_c) or {}                          # 29/10/2026 : candidats de la famille des arbres
            if cle_c in EP.DECISION_CANDIDATS and not avant.get(cle_c):
                # 30/10/2026 : décision de Lucas — en place dès la première semaine ; la stabilité ne sert qu'à la sortie
                avant[cle_c] = {'adopte': True, 'decision': EP.DECISION_CANDIDATS[cle_c]}
            choix[cle_c] = ST.appliquer(etat_st, cle_c, avant[cle_c],
                                        {k: maa.get(k) for k in ('adopte', 'raison', 'variables', 'modele', 'poids', 'll', 'par_circuit')},
                                        ('variables', 'modele', 'poids'))
            print(f"{lib_c} : {'ADOPTÉS' if choix[cle_c]['adopte'] else 'non adoptés'} — {choix[cle_c]['raison']}", flush=True)
        for cle_s in ('qualifies', 'transition', 'classement', 'classement_relatif'):
            choix[cle_s] = ST.appliquer(etat_st, cle_s, avant[cle_s],
                                        {k: (ep.get(cle_s) or {}).get(k) for k in ('adopte', 'delta', 'raison', 'll')}, ('delta',))
            print(f"{EP.SITUATIONS[cle_s]} : {'correction ADOPTÉE' if choix[cle_s]['adopte'] else 'pas de correction'} — "
                  f"{choix[cle_s]['raison']}", flush=True)
        ST.ecrire(etat_st)
        for c, b in (ep.get('par_circuit') or {}).items():
            sx = b['six_dernieres_semaines']
            print(f"  {b['circuit']:<10} simulation {b['simulation']['reussite_pct']} % · Elo {b['elo']['reussite_pct']} % "
                  f"(n {b['simulation']['n']}) · 6 dernières semaines : mélange "
                  f"{(sx.get('combinaison') or {}).get('reussite_pct', '—')} %", flush=True)
        print(f"Poids propres aux Challenger : {'ADOPTÉS' if choix['poids_challenger']['adopte'] else 'non adoptés'} — "
              f"{choix['poids_challenger']['raison']}", flush=True)
        for c_ in ('ATP', 'WTA'):
            print(f"Poids propres {c_} : {'ADOPTÉS' if choix['poids_' + c_]['adopte'] else 'non adoptés'} — "
                  f"{choix['poids_' + c_]['raison']}", flush=True)
        print(f"Nouveaux venus : {'correction ADOPTÉE' if choix['nouveaux_venus']['adopte'] else 'pas de correction'} — "
              f"{choix['nouveaux_venus']['raison']}", flush=True)
        with open(os.path.join(ICI, 'choix_simulation.json'), 'w', encoding='utf-8') as f:
            json.dump(choix, f, ensure_ascii=False, indent=1)
    except Exception as e:  # l'étude des facteurs reste valable sans cette partie
        print(f"::warning::Entraînement progressif non fait : {type(e).__name__}: {e}")
    doc['duree_s'] = round(time.time() - t0)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(doc['verdict'])
    return 0


def exporter_contexte(racine, M, adj, cle=E.cle, mcp=None):
    """Contexte actuel (pour pronostics_du_jour) : toutes les feuilles + archive ; adj = ajustement actuel."""
    fiches = FE.lire(racine)
    lignes = preparer(fiches, lambda jour: adj, cle)
    infos = infos_par_cle(racine, fiches, cle)
    H = avec_variables(lignes, infos, avant=M, final=True, adj_avant=adj, lieux=charger_lieux(racine),
                       charting=CH.Charting(CH.charger(mcp or MCP_DIR)), abandons=abandons_des_fiches(fiches, cle),
                       points=charger_points(racine))
    noms = {str(r.get('tournoi_id') or r.get('tournoi')): (r.get('tournoi_unique') or r.get('tournoi') or '') for r in fiches}
    H.qualifs, H.surfaces = parcours_des_fiches(fiches, cle)
    doc = contexte(H, infos, noms, dt.datetime.now(dt.timezone.utc).timestamp())
    with open(CONTEXTE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    return doc


if __name__ == '__main__':
    sys.exit(main(sys.argv))
