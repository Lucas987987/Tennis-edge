#!/usr/bin/env python3
"""build_profiles.py — construit players_profile.json, une fiche par joueur.

Assemble ce que le dépôt possède déjà, sans aucune source externe :

  moves_detail_hist.csv  les cotes : ouverture Pinnacle, entrée, book retenu
  set_results.json       les résultats : match, set 1, set 2
  player_form.json       forme sur 10 matchs et fatigue sur 7 / 14 jours

CE QUI N'EST PAS DANS LA FICHE, ET POURQUOI
-------------------------------------------
Pas de CLV par joueur, pas de taux de réussite des alertes, pas de dérive
du marché. Les trois sont du BIAIS DE SÉLECTION : moves_detail_hist ne
contient que des mouvements détectés, donc un joueur y figure parce que
le marché a bougé vers lui.

Mesuré : le côté steamé est raccourci dans 81 % des cas sur l'ensemble du
fichier. Afficher « le marché le raccourcit dans 80 % des cas » pour un
joueur donné décrit la détection, pas le joueur.

Même chose pour « 9 victoires sur 9 en favori » : neuf matchs steamés,
IC95 [70 ; 100]. C'est exactement le reproche fait aux sites de tipsters.

LES NOMS
--------
Trois conventions coexistent :
  moves_detail_hist  « Ben Shelton », « Mattia Bellucci »
  player_form        « ben shelton » MAIS « bellucci mattia » — ordre
                     inversé selon les entrées
  set_results        deux formats de clé, voir plus bas

D'où la clé par JEU DE TOKENS TRIÉ : accents retirés, minuscules, tokens
ordonnés. « Mattia Bellucci » et « bellucci mattia » donnent la même clé.
Taux de raccordement mesuré : 84 % sur la forme.

LES RÉSULTATS
-------------
set_results.json mélange deux formats :
  2 575 clés  {date}_{home}_{away}   = le uid de moves_detail_hist
    738 clés  {tournoi}_{home}_vs_{away}

Le premier se joint EXACTEMENT sur uid, sans deviner où finit le premier
nom — 76 % des matchs de moves. Le second se parse sur « _vs_ ».
"""

import csv
import json
import os
import math
import datetime
import gzip
import re
import statistics as st
import unicodedata
from collections import defaultdict

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
SETRES = os.environ.get('SETRES', 'set_results.json')
FORM = os.environ.get('FORM', 'player_form.json')
# Elo PUBLIÉ (tennisabstract.com), récupéré chaque lundi par elo_fetch.py
# dans elo.yml. On ne prend QUE celui-là : l'Elo maison s'auto-évalue à
# brier 0,235 quand les books sont à 0,209 — il prédit moins bien que le
# marché, il n'a rien à faire sur une fiche publique.
ELO = os.environ.get('ELO', 'elo_reference.json')
OUT = os.environ.get('OUT', 'players_profile.json')

# Nombre minimal d'observations pour publier une médiane de cote. En
# dessous, la fiche affiche le compte mais pas la médiane : une médiane
# sur 2 cotes n'est pas une médiane.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# Nombre minimal pour entrer au CLASSEMENT, plus exigeant que pour
# afficher une médiane. À 4 cotes, un joueur de challenger favori quatre
# fois d'affilée sortait devant Zverev et Sabalenka : la médiane était
# juste, le rang trompeur. À 8, les 145 classés sont ceux que le marché
# a réellement cotés assez souvent pour qu'un rang veuille dire quelque
# chose. Les autres gardent leur médiane, sans rang.
MIN_RANG = int(os.environ.get('MIN_RANG', '8'))

# Profondeur de l'historique conservé par joueur. À 8, neuf fiches
# étaient tronquées ; à 16 aucune ne l'est, pour quelques ko de plus.
N_DERNIERS = int(os.environ.get('N_DERNIERS', '16'))

# Profondeur du journal des mouvements détectés affiché sur la fiche.
N_ALERTES = int(os.environ.get('N_ALERTES', '6'))

# Avance minimale, en points d'Elo, pour qu'une surface soit déclarée
# PRIVILÉGIÉE. Mesuré sur les 1 078 joueurs de la référence : l'écart
# médian entre meilleure et pire surface vaut 94 points, le 10e centile
# 41. À 40 points d'avance sur la deuxième, une surface est nommée pour
# 52 % des joueurs ; en dessous, la page affiche les trois chiffres et se
# tait. Nommer une préférence sur 10 points d'écart serait du bruit.
ELO_ECART_SURFACE = int(os.environ.get('ELO_ECART_SURFACE', '40'))


def cle(nom):
    """Jeu de tokens trié — absorbe l'ordre prénom/nom et les accents."""
    if not nom:
        return ''
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    toks = [t for t in re.split(r'[^A-Za-z]+', s.lower()) if len(t) > 1]
    return ' '.join(sorted(toks))


def num(v):
    try:
        x = float(v)
        return x if x == x else None          # écarte NaN
    except (TypeError, ValueError):
        return None


def slug(nom):
    """Nom au format du uid : minuscules, accents retirés, _ entre mots."""
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]+', '_', s.lower()).strip('_')


def charger_resultats(setres, moves):
    """uid -> (nom_home, nom_away, resultat) pour ce qu'on sait nommer.

    Deux sources de noms, par ordre de fiabilité :
      1. moves_detail_hist, qui donne explicitement steame et opp ;
      2. le format _vs_, où la séparation est explicite.

    Le format {date}_{home}_{away} ne dit PAS où finit le premier nom
    (deux noms de plusieurs tokens collés). On ne devine pas : les uid
    absents de moves restent non nommés et ne comptent que dans le total.

    ATTENTION — `steame` N'EST PAS `home`.
    -------------------------------------
    `steame` est le côté vers lequel le marché a bougé ; il occupe la
    position « away » du uid dans 48 % des cas (mesuré sur 1 177 uid).
    Prendre (steame, opp) pour (home, away) inversait donc un résultat
    sur deux : Mattia Bellucci apparaissait battu quatre jours d'affilée,
    ce qui est impossible — on est éliminé à la première défaite.

    L'ordre se lit dans le uid lui-même : on compare le nom au préfixe
    qui suit la date. C'est exact, pas déduit.
    """
    noms = {}
    for r in moves:
        u, s, o = r.get('uid'), r.get('steame'), r.get('opp')
        if not (u and s and o):
            continue
        m = re.match(r'^\d{4}-\d{2}-\d{2}_(.+)$', u)
        if not m:
            continue
        reste = m.group(1)
        if reste.startswith(slug(s)):
            noms[u] = (s, o)
        elif reste.startswith(slug(o)):
            noms[u] = (o, s)
        # ni l'un ni l'autre : nom tronqué ou translittéré autrement.
        # On s'abstient plutôt que de risquer une inversion silencieuse.

    out = {}
    for k, v in setres.items():
        if k in noms:
            h, a = noms[k]
        elif '_vs_' in k:
            g, d = k.rsplit('_vs_', 1)
            parts = g.split('_')
            # le préfixe est le tournoi : « atp_stuttgart_jurij_rodionov »
            h = ' '.join(parts[2:]) if len(parts) > 2 else g
            a = d.replace('_', ' ')
        else:
            continue
        out[k] = (h, a, v)
    return out


def circuits_joueurs(moves, elo_k, paires=()):
    """clé -> 'atp' ou 'wta', par l'Elo puis par le GRAPHE DES ADVERSAIRES.

    POURQUOI PAS LE NOM DU TOURNOI
    -------------------------------
    Première idée : lire « ATP » ou « WTA » dans le champ `tour`. Mesuré :
    49 contradictions avec l'Elo, toutes dans le même sens — des joueuses
    rangées sous un tournoi ATP. Sabalenka apparaît dans six d'entre eux.

    La cause est claire : Cincinnati, Montréal/Toronto, Washington, Pékin
    sont des tournois COMBINÉS. Le collecteur garde un seul libellé par
    épreuve et c'est parfois le mauvais. Le libellé est donc inutilisable.

    LE GRAPHE
    ---------
    Un homme ne joue pas contre une femme. Deux joueurs reliés par un match
    sont donc du même circuit, et la propriété se propage de proche en
    proche. On construit le graphe des adversaires, on prend ses composantes
    connexes, et une composante dont tous les membres connus de l'Elo
    s'accordent transmet son circuit aux autres.

    Mesuré sur moves_detail_hist : 881 joueurs, 28 composantes, dont deux
    géantes de 569 et 254. ZÉRO composante ne mélange atp et wta.

    Cette dernière mesure est aussi un CONTRÔLE D'INTÉGRITÉ, et c'est la
    raison de la renvoyer : une composante mixte ne peut vouloir dire qu'une
    chose, deux joueurs différents réduits à la même clé de tokens. Le jour
    où ça arrive, on veut le lire dans le journal, pas le découvrir sur une
    fiche.

    Couverture : 701 par l'Elo, 185 de plus par le graphe, 146 sans circuit.
    """
    adj = defaultdict(set)
    for r in moves:
        a, b = cle(r.get('steame')), cle(r.get('opp'))
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    # Les matchs cotés hors alertes densifient le graphe (09/10/2026) : plus
    # de joueurs reliés, donc plus de circuits connus.
    for paire in paires:
        a, b = sorted(paire)
        adj[a].add(b)
        adj[b].add(a)

    circ = {k: v['tour'] for k, v in elo_k.items()
            if v.get('tour') in ('atp', 'wta')}

    vus = set()
    mixtes = []
    for depart in adj:
        if depart in vus:
            continue
        pile, comp = [depart], set()
        while pile:
            x = pile.pop()
            if x in vus:
                continue
            vus.add(x)
            comp.add(x)
            pile.extend(adj[x] - vus)
        connus = {circ[x] for x in comp if x in circ}
        if len(connus) > 1:
            # On ne propage RIEN dans une composante contradictoire : ses
            # membres gardent leur circuit Elo s'ils en ont un, et les
            # autres restent sans circuit. Mieux vaut pas de rang qu'un
            # rang dans le mauvais classement.
            mixtes.append(sorted(comp)[:6])
            continue
        if len(connus) == 1:
            s = connus.pop()
            for x in comp:
                circ.setdefault(x, s)
    return circ, mixtes


# Fenêtre de rattachement d'un résultat à son prix. Mesuré le 09/10 : la
# date de règlement (resolved_at) tombe le jour du match dans 85 cas, le
# lendemain dans 749, et jusqu'à cinq jours après dans 124.
FENETRE_JOURS = int(os.environ.get('FENETRE_JOURS', '5'))


def historique_tous_matchs(res):
    """Prix et résultats de TOUS les matchs cotés, pas seulement des alertes.

    POURQUOI (09/10/2026)
    ---------------------
    La cote du marché et le bilan ne portaient que sur moves_detail_hist :
    les matchs où une ALERTE est partie. Deux défauts mesurés :
      - couverture : 388 joueurs avec une médiane, 151 classés. Sur tous les
        matchs cotés : 533 et 293. Hynek Barton n'avait pas de cote ; il en
        a une sur 8 prix.
      - biais : un joueur n'entre dans les alertes que si le marché bouge
        vers lui. Laslo Djere : 1,47 sur ses alertes, 1,64 sur tous ses
        matchs. La fiche montrait le joueur tel que le marché le voit quand
        il le soutient, pas en général.
    Et la fiche se contredisait : « Matchs gagnés 0/2 » (alertes) à côté de
    « Sur ses 10 derniers 5/10 » (tous les matchs).

    LES SOURCES
    -----------
    Celles de player_form.py, réutilisées telles quelles :
      cotes_sharp()     clôture Pinnacle PRÉ-MATCH, marge retirée, lue dans
                        les courbes — avec la coupe qui écarte les points
                        in-play (piège qui a produit quatre faux positifs).
      charger_matchs()  tous les résultats connus, avec les sets gagnés.

    Le prix est rattaché au résultat dans les FENETRE_JOURS qui le précèdent :
    les deux sources ne datent pas pareil (coup d'envoi / règlement), et une
    jointure sur le même jour en perdait un tiers.

    Renvoie None si les courbes sont illisibles : la fiche retombe alors sur
    les alertes, comme avant, et le journal le dit.
    """
    import datetime as _dt
    try:
        import player_form as pf
        ref = pf.cotes_sharp()
        bruts = pf.charger_matchs()
    except Exception as e:                          # noqa: BLE001
        print(f"  TOUS LES MATCHS INDISPONIBLES ({type(e).__name__}: {e})")
        print("  -> repli sur les seules alertes (moves_detail_hist)")
        return None
    if not ref:
        print("  AUCUN PRIX dans les courbes -> repli sur les seules alertes")
        return None

    # Clés repassées dans cle() : player_form garde les chiffres dans les
    # noms, build_profiles non. Sans ça, un même joueur aurait deux clés.
    def k_(x):
        return cle(x) if x else ''

    # 1. Les prix : un par match coté, daté du coup d'envoi.
    prix = defaultdict(list)                       # paire -> [(date, {cle: proba})]
    for (paire, d), (j, p) in ref.items():
        duo = sorted(paire)
        if len(duo) != 2 or not (0.0 < p < 1.0):
            continue
        autre = duo[0] if duo[1] == j else duo[1]
        cj, ca = k_(j), k_(autre)
        if not cj or not ca or cj == ca:
            continue
        prix[frozenset((cj, ca))].append((d, {cj: p, ca: 1.0 - p}))

    # 2. Les résultats, chacun rattaché à son prix d'avant-match.
    resultats = []
    for d, a, b, a_gagne, sa, sb, tour in bruts:
        ca, cb = k_(a), k_(b)
        if not d or not ca or not cb or ca == cb:
            continue
        paire = frozenset((ca, cb))
        d_res = d.date()
        cand = [(dp, pr) for dp, pr in prix.get(paire, [])
                if 0 <= (d_res - dp).days <= FENETRE_JOURS]
        d_match, p_match = max(cand, key=lambda x: x[0]) if cand else (d_res, None)
        resultats.append((paire, d_res, d_match, p_match,
                          ca if a_gagne else cb, {ca: sa, cb: sb}, tour or ''))

    # Dédoublonnage. Un même match revient parfois 6 à 13, voire 28 à 32
    # jours plus tard : règlement provisoire puis définitif, ou seconde
    # source datée de son propre passage. Mesuré le 09/10 : 1 076 doublons
    # sur 7 301 lignes de fiches (15 %) avec une fenêtre de 5 jours seule.
    #
    # Même paire, même vainqueur, et MÊME TOURNOI à moins de 35 jours : un
    # joueur éliminé ne rejoue pas le même adversaire dans le même tournoi.
    # Sans tournoi commun, on garde la fenêtre courte. On conserve la ligne
    # qui porte une cote : sa date est celle du coup d'envoi, la plus sûre.
    resultats.sort(key=lambda x: (x[2], x[3] is None))
    garde = defaultdict(list)                       # (paire, gagnant) -> [idx]
    retenus = []
    for r in resultats:
        paire, d_res, d_match, p_match, gagnant, sets, tour = r
        doublon = None
        for i in garde[(paire, gagnant)]:
            q = retenus[i]
            jours = abs((d_match - q[2]).days)
            if jours <= FENETRE_JOURS or (tour and tour == q[6] and jours <= 35):
                doublon = i
                break
        if doublon is None:
            garde[(paire, gagnant)].append(len(retenus))
            retenus.append(r)
        elif retenus[doublon][3] is None and p_match is not None:
            retenus[doublon] = r                    # la version avec cote gagne
    resultats = retenus

    # 3. Le vainqueur du 1er set : set_results (déjà chargé, via `res`) et
    # resultats_oddspapi.json. Rattaché dans la même fenêtre.
    set1 = defaultdict(list)                       # paire -> [(date, cle gagnante)]
    for uid, (h, a, v) in res.items():
        m = re.match(r'^(\d{4}-\d{2}-\d{2})', uid)
        if not m or v.get('set1') not in ('home', 'away'):
            continue
        ch, ca = k_(h), k_(a)
        if ch and ca and ch != ca:
            set1[frozenset((ch, ca))].append(
                (_dt.date.fromisoformat(m.group(1)),
                 ch if v['set1'] == 'home' else ca))
    try:
        for v in json.load(open(os.environ.get(
                'ODDSPAPI_RESULTS', 'resultats_oddspapi.json'),
                encoding='utf-8')).values():
            if not isinstance(v, dict) or v.get('set1') not in ('home', 'away'):
                continue
            ch, ca = k_(v.get('home')), k_(v.get('away'))
            d = str(v.get('resolved_at') or '')[:10]
            if ch and ca and ch != ca and len(d) == 10:
                set1[frozenset((ch, ca))].append(
                    (_dt.date.fromisoformat(d), ch if v['set1'] == 'home' else ca))
    except (OSError, ValueError):
        pass

    # 4. Assemblage par joueur.
    par_joueur = defaultdict(list)
    for paire, d_res, d_match, p_match, gagnant, sets, tour in resultats:
        s1 = [g for d, g in set1.get(paire, [])
              if abs((d - d_res).days) <= FENETRE_JOURS
              or abs((d - d_match).days) <= FENETRE_JOURS]
        s1 = s1[0] if s1 and len(set(s1)) == 1 else None
        for moi in paire:
            adv = next(x for x in paire if x != moi)
            pm = p_match.get(moi) if p_match else None
            # Un 2-0 (ou 3-0) dit qui a pris le 1er set : inutile de le
            # chercher ailleurs. Seuls les matchs en trois sets en ont besoin.
            sm, sa_ = sets.get(moi, 0), sets.get(adv, 0)
            if s1 is not None:
                set1_moi = (s1 == moi)
            elif sm >= 2 and sa_ == 0:
                set1_moi = True
            elif sa_ >= 2 and sm == 0:
                set1_moi = False
            else:
                set1_moi = None
            par_joueur[moi].append({
                'date': d_match.isoformat(),
                'adv_cle': adv,
                'gagne': gagnant == moi,
                'sets': f"{sets.get(moi, 0)}-{sets.get(adv, 0)}",
                'set1': set1_moi,
                # Cote JUSTE (marge retirée) d'avant le match.
                'cote': round(1.0 / pm, 2) if pm else None,
                'tour': tour or None,
            })

    # Les prix seuls, y compris des matchs sans résultat : la médiane n'a
    # pas besoin du vainqueur.
    cotes, cotes_adv, dates = defaultdict(list), defaultdict(list), defaultdict(set)
    for paire, L in prix.items():
        for d, pr in L:
            for moi in paire:
                adv = next(x for x in paire if x != moi)
                cotes[moi].append(1.0 / pr[moi])
                cotes_adv[moi].append(1.0 / pr[adv])
                dates[moi].add(d.isoformat())

    # Les noms tels que les écrivent les courbes. Les prix et résultats ne
    # portent que des clés (jetons triés) : sans cette passe, un joueur vu
    # seulement dans les courbes s'afficherait « Latinovic Stefan ».
    noms_courbes = {}
    for src in ('book_curves.jsonl', 'book_curves_live.jsonl'):
        try:
            for ligne in pf.ov.open_curves(src, verbose=False):
                try:
                    r = json.loads(ligne)
                except ValueError:
                    continue
                for n in (r.get('home_team') or r.get('home'),
                          r.get('away_team') or r.get('away')):
                    if n:
                        noms_courbes.setdefault(k_(n), n)
        except Exception:                           # noqa: BLE001
            continue

    print(f"  tous les matchs : {sum(len(v) for v in prix.values())} prix, "
          f"{len(resultats)} résultats, {len(par_joueur)} joueurs avec un résultat")
    return {'matchs': par_joueur, 'cotes': cotes, 'cotes_adv': cotes_adv,
            'dates': dates, 'paires': list(prix.keys()),
            'noms': noms_courbes, 'prix': prix}


# ── HISTORIQUE tennis-data.co.uk (ajouté le 09/10/2026) ──────────────────
#
# Clôtures Pinnacle du circuit principal : ATP 2010-2026, WTA 2018-2026,
# 56 461 matchs terminés. Vérifié le 09/10 : ce sont des cotes de CLÔTURE
# (leur bet365 2026 colle à notre clôture bet365, écart médian 0,2 %, et
# pas à notre ouverture, 4 %). Produit une fois par
# scripts/convertir_tennis_data.py ; Pinnacle disparaît de tennis-data fin
# janvier 2026, nos courbes prennent le relais en juin.
#
# N'entre QUE dans le bilan en favori / en outsider. Le classement marché
# reste calculé sur nos seules cotes : le niveau d'un joueur en 2019 ne dit
# rien de son niveau aujourd'hui.
HISTO_TD = os.environ.get('HISTO_TD', 'historique/tennis_data.csv.gz')
# « Récent » = ses N_RECENT derniers matchs DANS CE STATUT, pas les 12
# derniers mois : Pinnacle manque partout de février à mai 2026 (fin de
# tennis-data, début de nos courbes en juin), un bilan sur 12 mois aurait
# eu 4 mois de trou et des tailles incomparables d'un joueur à l'autre.
N_RECENT = int(os.environ.get('N_RECENT', '20'))
TENDANCE_MIN_ANCIEN = int(os.environ.get('TENDANCE_MIN_ANCIEN', '20'))
TENDANCE_Z = float(os.environ.get('TENDANCE_Z', '1.96'))


def _jetons(nom):
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z. ]+', ' ', s.replace('-', ' ')).split()


def relier_tennis_data(fiches):
    """Nom tennis-data (« Bublik A. », « Fernandez L.A. », « Wang Xiy. »)
    -> clé de fiche, par circuit.

    fiches : {clé: (nom affiché, circuit 'atp'/'wta'/None, nb de cotes)}.
    Le nom de famille doit correspondre exactement à la fin du nom de la
    fiche, et l'abréviation au début du prénom (« xiy » distingue Xiyu de
    Xinyu). Plusieurs candidats : on garde celui qui a le plus de cotes,
    seulement s'il en a au moins trois fois plus que le suivant — sinon
    on ne relie pas (les frères Nakashima restent sans historique plutôt
    qu'avec celui de l'autre).
    """
    idx = defaultdict(list)
    for k, (nom, circ, n) in fiches.items():
        t = [x.replace('.', '') for x in _jetons(nom)]
        t = [x for x in t if x]
        for i in range(1, len(t)):
            idx[' '.join(t[i:])].append((k, t[0], circ, n))
    cache = {}

    def relier(nom_td, circuit):
        cle_c = (nom_td, circuit)
        if cle_c in cache:
            return cache[cle_c]
        t = _jetons(nom_td)
        res = None
        if len(t) >= 2:
            abr = t[-1]
            nom = ' '.join(x.replace('.', '') for x in t[:-1])
            # « l.a. » -> la première lettre ; « xiy. » -> le préfixe entier
            pre = abr.split('.')[0] if abr.count('.') > 1 else abr.replace('.', '')
            c = [(k, n) for k, prenom, circ, n in idx.get(nom, [])
                 if pre and prenom.startswith(pre)
                 and (circ is None or circ == circuit)]
            c = sorted(set(c), key=lambda x: -x[1])
            if len(c) == 1 or (len(c) > 1 and c[0][1] >= 3 * max(1, c[1][1])):
                res = c[0][0]
        cache[cle_c] = res
        return res
    return relier


def historique_tennis_data(fiches):
    """{clé: [{'date', 'cote' (juste), 'gagne'}]} depuis HISTO_TD."""
    if not os.path.exists(HISTO_TD):
        print(f"  {HISTO_TD} absent — bilans sur nos seules données")
        return {}, []
    relier = relier_tennis_data(fiches)
    out, n, relies, noms, noms_ok = defaultdict(list), 0, 0, set(), set()
    matchs = []          # (date, identité A, identité B, proba juste de A)
    with gzip.open(HISTO_TD, 'rt', encoding='utf-8') as g:
        for r in csv.DictReader(g):
            try:
                pw, pl = float(r['psw']), float(r['psl'])
            except (TypeError, ValueError):
                continue
            n += 1
            circ = (r.get('circuit') or '').lower()
            iw, il = 1 / pw, 1 / pl
            qw = iw / (iw + il)
            # Identité pour le classement : la clé de fiche si le joueur est
            # relié, sinon son nom tennis-data — un adversaire sans fiche
            # compte quand même pour juger la force de ceux qui l'ont affronté.
            ids = [relier(x, circ) or f"td:{circ}:{x}" for x in (r['vainqueur'], r['perdant'])]
            matchs.append((r['date'], ids[0], ids[1], qw))
            for nom, q, y in ((r['vainqueur'], qw, True), (r['perdant'], 1 - qw, False)):
                noms.add((nom, circ))
                k = relier(nom, circ)
                if k:
                    noms_ok.add((nom, circ))
                    relies += 1
                    out[k].append({'date': r['date'], 'cote': round(1 / q, 3), 'gagne': y})
    print(f"  historique tennis-data : {n} matchs, {len(noms_ok)}/{len(noms)} joueurs "
          f"reliés à une fiche, {relies} bilans ajoutés à {len(out)} fiches")
    return out, matchs


def bilan_statut(ms, aujourdhui=None):
    """Bilan sur une liste de matchs {date, cote juste, gagne} d'UN statut :
    global, N_RECENT derniers, et tendance.

    TENDANCE : l'écart au marché par match (victoires − attendu) / n sur
    les N_RECENT derniers matchs, comparé à celui des matchs d'avant.
    « hausse » ou « baisse » seulement si la différence dépasse ce que le
    hasard explique (z ≥ 1,96, variance binomiale p(1−p) de chaque match) ;
    sinon « stable ». Il faut N_RECENT matchs récents et au moins
    TENDANCE_MIN_ANCIEN avant, sinon pas de tendance.

    Ce n'est PAS une prévision : testé le 09/10 sur 16 saisons, un bilan
    au-dessus du marché ne se prolonge pas. C'est une description de
    l'évolution du joueur.
    """
    if not ms:
        return None
    ms = sorted(ms, key=lambda m: m['date'])

    def agr(L):
        return {'n': len(L), 'victoires': sum(1 for m in L if m['gagne']),
                'attendu': round(sum(1 / m['cote'] for m in L), 1)}
    rec, anc = ms[-N_RECENT:], ms[:-N_RECENT]
    b = agr(ms)
    b['depuis'] = ms[0]['date'][:4]
    if anc:                      # sinon « récent » = « global », inutile
        b['recent'] = agr(rec)
    tend = None
    if len(rec) >= N_RECENT and len(anc) >= TENDANCE_MIN_ANCIEN:
        def taux(L):
            r = sum((1 if m['gagne'] else 0) - 1 / m['cote'] for m in L) / len(L)
            v = sum((1 / m['cote']) * (1 - 1 / m['cote']) for m in L) / len(L) ** 2
            return r, v
        r1, v1 = taux(rec)
        r0, v0 = taux(anc)
        z = (r1 - r0) / math.sqrt(v1 + v0) if v1 + v0 > 0 else 0
        tend = 'hausse' if z >= TENDANCE_Z else ('baisse' if z <= -TENDANCE_Z else 'stable')
    b['tendance'] = tend
    return b


# ── CLASSEMENT MARCHÉ AJUSTÉ AUX ADVERSAIRES (10/10/2026) ──────────────
#
# L'ancien classement était la MÉDIANE des cotes d'un joueur. Elle dépend
# autant de ses adversaires que de lui : un joueur de Challenger qui
# affronte des joueurs faibles a des cotes basses et paraît fort.
#
# Ici, chaque joueur a une NOTE, et chaque match coté la corrige : la cote
# juste Pinnacle dit de combien A est plus fort que B (en logit), on compare
# à l'écart de leurs notes, et on déplace les deux notes d'une fraction
# K_CLASSEMENT de l'erreur. C'est un Elo nourri par les cotes au lieu des
# résultats ; il pèse naturellement davantage les matchs récents.
#
# MESURÉ le 10/10 sur 31 607 matchs 2016-2025 (tennis-data), en prédisant la
# proba du match suivant avec les seuls matchs passés :
#     médiane des cotes (ancien)        erreur moyenne 9,6 pts
#     notes ajustées, K = 0,3           erreur moyenne 6,6 pts
# K = 0,3 était le meilleur des essais (0,05 à 0,5).
#
# Un joueur NOUVEAU démarre à la note qui explique exactement sa première
# cote face à un adversaire déjà noté ; deux nouveaux démarrent de part et
# d'autre de zéro. L'historique tennis-data (circuit principal 2010 ->
# janvier 2026) passe d'abord, puis nos matchs depuis juin 2026.
K_CLASSEMENT = float(os.environ.get('K_CLASSEMENT', '0.3'))


def notes_marche(td_matchs, prix):
    """{identité: note}, {identité: nb de matchs notés}."""
    def lg(p):
        p = min(max(p, 1e-4), 1 - 1e-4)
        return math.log(p / (1 - p))
    M = [(d, a, b, p) for d, a, b, p in td_matchs]
    for paire, L in (prix or {}).items():
        for d, probs in L:
            (a, pa), (b, _pb) = sorted(probs.items())
            M.append((d.isoformat() if hasattr(d, 'isoformat') else str(d), a, b, pa))
    M.sort(key=lambda x: x[0])
    R, N = {}, defaultdict(int)
    for _d, a, b, p in M:
        z = lg(p)
        if a not in R and b not in R:
            R[a], R[b] = z / 2, -z / 2
        elif a not in R:
            R[a] = R[b] + z
        elif b not in R:
            R[b] = R[a] - z
        e = z - (R[a] - R[b])
        R[a] += K_CLASSEMENT * e
        R[b] -= K_CLASSEMENT * e
        N[a] += 1
        N[b] += 1
    print(f"  classement ajusté : {len(M)} matchs notés, {len(R)} joueurs")
    return R, N


def main():
    moves = [r for r in csv.DictReader(open(MOVES, encoding='utf-8'))]
    setres = json.load(open(SETRES, encoding='utf-8'))
    forme = json.load(open(FORM, encoding='utf-8')).get('joueurs', {})
    form_k = {cle(k): v for k, v in forme.items()}

    # L'Elo est indexé par son propre `nom`, pas par sa clé : les deux
    # conventions ne coïncident pas toujours, et c'est le nom affiché qui
    # fait foi. Absent ou illisible, on continue sans — l'Elo enrichit la
    # fiche, il ne la conditionne pas.
    elo_k = {}
    try:
        for k, v in json.load(open(ELO, encoding='utf-8')).get('joueurs', {}).items():
            if isinstance(v, dict) and v.get('elo'):
                elo_k[cle(v.get('nom') or k)] = v
    except (OSError, ValueError) as e:
        print(f"  {ELO} illisible ({e}) — fiches sans Elo")

    res = charger_resultats(setres, moves)
    H = historique_tous_matchs(res)

    circ_k, mixtes = circuits_joueurs(moves, elo_k, H['paires'] if H else ())
    if mixtes:
        print(f"  ALERTE : {len(mixtes)} composante(s) mélangent atp et wta "
              f"— collision de clés probable")
        for c in mixtes[:3]:
            print(f"    {', '.join(c)}")

    P = defaultdict(lambda: {
        'nom': None, 'cotes': [], 'cotes_adv': [], 'circuits': defaultdict(int),
        'books': defaultdict(int), 'matchs': [], 'dates': [], 'alertes': [],
    })

    # ── Le marché : cote d'ouverture Pinnacle ───────────────────────────
    #
    # Pour le côté steamé, pin_open est sa cote. Pour l'adversaire, on la
    # déduit de la probabilité complémentaire — approximation, la marge
    # n'est pas retirée, mais elle suffit à situer un joueur.
    for r in moves:
        po = num(r.get('pin_open'))
        s, o = r.get('steame'), r.get('opp')
        d, t = r.get('date'), r.get('tour')
        if s:
            k = cle(s)
            P[k]['nom'] = P[k]['nom'] or s
            if po:
                P[k]['cotes'].append(po)
            if t:
                P[k]['circuits'][t] += 1
            if d:
                P[k]['dates'].append(d)
            b = r.get('entry_book')
            if b:
                P[k]['books'][b] += 1
            # Le mouvement a été détecté SUR ce joueur : c'est vers lui que
            # le marché est allé. Il n'est journalisé que de son côté.
            e = num(r.get('entry'))
            if d and e:
                P[k]['alertes'].append({
                    'date': d, 'tour': t or None, 'entry': round(e, 2),
                    'book': b or None, 'adv': o or None,
                    'pin_open': round(po, 2) if po else None,
                })
            if po:
                P[k]['cotes_adv'].append(1 / max(0.02, 1 - 1 / po))
        if o:
            k = cle(o)
            P[k]['nom'] = P[k]['nom'] or o
            if t:
                P[k]['circuits'][t] += 1
            if d:
                P[k]['dates'].append(d)
            if po:
                P[k]['cotes'].append(1 / max(0.02, 1 - 1 / po))
                P[k]['cotes_adv'].append(po)

    # ── Les résultats : match, set 1, set 2 ─────────────────────────────
    for uid, (h, a, v) in res.items():
        date = uid[:10] if re.match(r'^\d{4}-\d{2}-\d{2}', uid) else None
        for nom, cote in ((h, 'home'), (a, 'away')):
            k = cle(nom)
            if not k:
                continue
            P[k]['nom'] = P[k]['nom'] or nom
            P[k]['matchs'].append({
                'date': date,
                'adv': a if cote == 'home' else h,
                'match': v.get('match') == cote if v.get('match') else None,
                'set1': v.get('set1') == cote if v.get('set1') else None,
                'set2': v.get('set2') == cote if v.get('set2') else None,
            })

    # ── Noms des joueurs vus seulement hors alertes ─────────────────────
    #
    # Les prix et résultats de tous les matchs ne portent que des CLÉS. Le
    # nom affiché vient, par ordre de fiabilité : des alertes (déjà dans P),
    # de l'Elo publié, puis des résultats OddsPapi.
    if H:
        noms = {}
        try:
            for v in json.load(open(os.environ.get(
                    'ODDSPAPI_RESULTS', 'resultats_oddspapi.json'),
                    encoding='utf-8')).values():
                if isinstance(v, dict):
                    for n in (v.get('home'), v.get('away')):
                        if n:
                            noms.setdefault(cle(n), n)
        except (OSError, ValueError):
            pass
        # set_results donne l'ordre réel prénom-nom, en minuscules : on le
        # garde en dernier recours, mis en capitales.
        for h, a, _v in res.values():
            for n in (h, a):
                if n:
                    noms.setdefault(cle(n), ' '.join(
                        t[:1].upper() + t[1:] for t in str(n).split()))
        for kk, n in H.get('noms', {}).items():
            noms.setdefault(kk, n)
        for kk, v in elo_k.items():
            if v.get('nom'):
                noms[kk] = v['nom']
        for kk in set(H['matchs']) | set(H['cotes']):
            if not P[kk]['nom'] and noms.get(kk):
                P[kk]['nom'] = noms[kk]

    # ── Historique tennis-data : relié aux fiches par le nom ────────────
    TD, TD_MATCHS = historique_tennis_data({
        kk: (pp['nom'], circ_k.get(kk), len(H['cotes'].get(kk, [])) if H else 0)
        for kk, pp in P.items() if pp['nom']})
    aujourdhui = datetime.datetime.now(datetime.timezone.utc).date()

    # ── Assemblage ──────────────────────────────────────────────────────
    out = {}
    for k, p in list(P.items()):
        if not p['nom']:
            continue
        f = form_k.get(k, {})
        ms = sorted([m for m in p['matchs'] if m['date']],
                    key=lambda m: m['date'], reverse=True)
        joues = [m for m in ms if m['match'] is not None]
        s1 = [m for m in ms if m['set1'] is not None]

        fiche = {
            'nom': p['nom'],
            'n_matchs_vus': len(set(p['dates'])),
            # Écrasés plus bas par tous les matchs quand ils sont disponibles.
            'periode': [min(p['dates']), max(p['dates'])] if p['dates'] else None,
            'circuits': [c for c, _ in sorted(p['circuits'].items(),
                                              key=lambda x: -x[1])[:4]],
        }
        # 'atp' ou 'wta'. Absent quand ni l'Elo ni le graphe ne tranchent :
        # la fiche existe alors sans circuit et sans rang.
        if circ_k.get(k):
            fiche['circuit'] = circ_k[k]

        # La cote du marché : sur TOUS les matchs cotés quand les courbes
        # sont lisibles (clôture Pinnacle pré-match, marge retirée) ; sinon
        # sur les alertes seules (ouverture Pinnacle, marge comprise).
        cotes = H['cotes'].get(k, []) if H else p['cotes']
        cotes_adv = H['cotes_adv'].get(k, []) if H else p['cotes_adv']
        if len(cotes) >= MIN_COTES:
            fiche['cote_mediane'] = round(st.median(cotes), 2)
            fiche['cote_min'] = round(min(cotes), 2)
            fiche['cote_max'] = round(max(cotes), 2)
            fiche['n_cotes'] = len(cotes)
            fiche['pct_favori'] = round(
                100 * sum(1 for c in cotes if c < 2) / len(cotes))
        if len(cotes_adv) >= MIN_COTES:
            fiche['cote_adversaires'] = round(st.median(cotes_adv), 2)

        if H:
            # TOUS les matchs joués, du plus récent au plus ancien, avec le
            # score en sets et la cote juste d'avant le match.
            tous = sorted(H['matchs'].get(k, []), key=lambda m: m['date'],
                          reverse=True)
            if tous:
                fiche['derniers'] = [
                    dict(m, adv=(P[m['adv_cle']]['nom']
                                 if m['adv_cle'] in P else None)
                         or m['adv_cle'].title())
                    for m in tous[:N_DERNIERS]]
                # UNE seule ligne de bilan, calculée sur les mêmes matchs que
                # la liste affichée : elle ne peut plus la contredire.
                dix = tous[:10]
                s1 = [m for m in dix if m['set1'] is not None]
                fiche['recent'] = {
                    'n': len(dix),
                    'victoires': sum(1 for m in dix if m['gagne']),
                    'set1_n': len(s1),
                    'set1_gagnes': sum(1 for m in s1 if m['set1']),
                }
                # BILAN EN FAVORI / EN OUTSIDER, sur TOUS les matchs joués qui
                # ont une cote (pas seulement les alertes, pas seulement les 10
                # derniers). « attendu » = somme des probabilités du marché
                # (1 / cote juste) : ce que le joueur aurait gagné s'il faisait
                # exactement ce que le marché prévoyait. Gagner 7 sur 10 en
                # favori n'est un exploit que si le marché en attendait 5.
                pass
                ds = sorted(H['dates'].get(k, set()) | {m['date'] for m in tous})
                fiche['periode'] = [ds[0], ds[-1]]
                fiche['n_matchs_vus'] = len(tous)
        # BILAN EN FAVORI / EN OUTSIDER — nos matchs cotés (depuis juin 2026)
        # PLUS l'historique tennis-data (circuit principal, 2010/2018 ->
        # janvier 2026). Les deux ne se chevauchent pas : tennis-data n'a
        # plus de Pinnacle après janvier, nos courbes commencent en juin.
        # Par sécurité, un match tennis-data postérieur à notre premier
        # match pour ce joueur est ignoré.
        nos = [m for m in (H['matchs'].get(k, []) if H else []) if m.get('cote')]
        debut = min((m['date'] for m in nos), default='9999')
        tout = [{'date': m['date'], 'cote': m['cote'], 'gagne': bool(m['gagne'])}
                for m in nos] + [m for m in TD.get(k, []) if m['date'] < debut]
        for cle_f, garder in (('en_favori', lambda c: c < 2),
                              ('en_outsider', lambda c: c >= 2)):
            b = bilan_statut([m for m in tout if garder(m['cote'])], aujourdhui)
            if b:
                fiche[cle_f] = b

        if not H:
            if joues:
                fiche['bilan'] = {
                    'n': len(joues),
                    'victoires': sum(1 for m in joues if m['match']),
                }
            if s1:
                fiche['set1'] = {
                    'n': len(s1),
                    'gagnes': sum(1 for m in s1 if m['set1']),
                }
            if ms:
                fiche['derniers'] = [
                    {'date': m['date'], 'adv': m['adv'], 'gagne': m['match'],
                     'set1': m['set1'], 'adv_cle': cle(m['adv'])}
                    for m in ms[:N_DERNIERS]
                ]

        if f:
            fiche['forme'] = f.get('forme')
            fiche['fatigue'] = f.get('fatigue')

        if p['books']:
            fiche['meilleur_prix'] = max(p['books'].items(), key=lambda x: x[1])[0]

        # ── Elo publié ──────────────────────────────────────────────────
        #
        # Le SEUL avis de la fiche qui ne vienne pas du marché. Quand il
        # diverge de la cote médiane, c'est l'information la plus
        # intéressante de la page.
        e = elo_k.get(k)
        if e:
            surf = {n: round(e[n]) for n in ('dur', 'terre', 'gazon')
                    if isinstance(e.get(n), (int, float))}
            bloc = {'valeur': round(e['elo'])}
            if e.get('tour'):
                bloc['tour'] = e['tour']
            if surf:
                bloc['surfaces'] = surf
            # Surface privilégiée : nommée seulement si elle devance
            # nettement la deuxième (voir ELO_ECART_SURFACE).
            # Deux faits distincts, et les deux comptent. Un joueur peut
            # n'avoir aucune surface de prédilection tout en étant nettement
            # mauvais sur une : Baez est à 1725 sur terre, 1702 sur dur —
            # 23 points, rien à dire — mais 1535 sur gazon, 190 plus bas.
            # Ne regarder que la meilleure faisait écrire « aucune surface
            # ne se détache » sous trois chiffres qui criaient le contraire.
            if len(surf) >= 3:
                ordre = sorted(surf.items(), key=lambda x: -x[1])
                if ordre[0][1] - ordre[1][1] >= ELO_ECART_SURFACE:
                    bloc['meilleure_surface'] = ordre[0][0]
                if ordre[-2][1] - ordre[-1][1] >= ELO_ECART_SURFACE:
                    bloc['pire_surface'] = ordre[-1][0]
            fiche['elo'] = bloc

        # ── Ce que le dispositif a vu ───────────────────────────────────
        #
        # Le journal des mouvements détectés sur ce joueur : date, tournoi,
        # prix d'entrée retenu, book. PAS de résultat, PAS de taux : ce
        # serait le biais de sélection décrit en tête de fichier.
        #
        # C'est un relevé, pas une performance. Il montre au lecteur qu'un
        # dispositif tourne derrière la page — ce qu'aucune statistique ne
        # dit aussi bien — et il sert de contrôle : une alerte qui apparaît
        # ici sans correspondre à rien signale un défaut dans la chaîne.
        if p['alertes']:
            fiche['alertes'] = sorted(p['alertes'],
                                      key=lambda a: a['date'],
                                      reverse=True)[:N_ALERTES]

        out[k] = fiche

    # ── Classement marché, UN PAR CIRCUIT ───────────────────────────────
    #
    # La médiane de la cote d'ouverture EST un classement, et c'est le
    # plus pertinent ici : il intègre la forme, la surface et le contexte,
    # ce qu'un classement ATP ne fait pas. Rang publié seulement au-delà
    # de MIN_RANG cotes — sinon il ferait croire à une précision qui
    # n'existe pas.
    #
    # DEUX CLASSEMENTS, PAS UN
    # ------------------------
    # Un classement unique mettait les 86 hommes et les 65 femmes dans la
    # même colonne. Les deux circuits ne se rencontrent jamais : aucun
    # match ne les relie, donc aucune cote ne les compare. Le rang croisé
    # ne mesurait pas « qui est le meilleur », il mesurait de quel côté le
    # marché cote le plus serré — autre chose, et personne ne le lisait
    # comme ça.
    #
    # Un joueur sans circuit n'entre dans aucun des deux. Il garde sa
    # médiane, comme ceux qui n'ont pas assez de cotes.
    # DEPUIS LE 10/10 : rang sur la NOTE ajustée aux adversaires (voir
    # notes_marche), plus sur la médiane. La médiane reste dans la fiche :
    # elle sert à « match plus facile / plus dur que son ordinaire ».
    #
    # « cote_classement » : la cote que le marché lui donnerait face à un
    # joueur MOYEN de son circuit (la note médiane des classés). Seul un
    # joueur ayant encore MIN_RANG cotes chez nous est classé : l'historique
    # renseigne la note, il ne suffit pas à classer un joueur inactif.
    R, NR = notes_marche(TD_MATCHS, H.get('prix') if H else None)
    classes = {}
    for cir in ('atp', 'wta'):
        elig = [k for k, v in out.items()
                if v.get('n_cotes', 0) >= MIN_RANG and v.get('circuit') == cir
                and k in R]
        if not elig:
            classes[cir] = 0
            continue
        ref = st.median(R[k] for k in elig)
        for k, v in out.items():
            if v.get('circuit') == cir and k in R and v.get('n_cotes', 0) >= MIN_COTES:
                pr = 1 / (1 + math.exp(-(R[k] - ref)))
                v['cote_classement'] = round(1 / pr, 2)
                v['n_notes'] = NR[k]
        cl = sorted(elig, key=lambda k: -R[k])
        for rang, k in enumerate(cl, 1):
            out[k]['rang_marche'] = rang
            out[k]['rang_sur'] = len(cl)
        classes[cir] = len(cl)

    n_sans = sum(1 for v in out.values()
                 if v.get('n_cotes', 0) >= MIN_RANG and not v.get('circuit'))

    import datetime as _dt
    meta = {
        'genere_le': _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec='seconds'),
        'n_joueurs': len(out),
        'n_classes': classes['atp'] + classes['wta'],
        'n_classes_atp': classes['atp'],
        'n_classes_wta': classes['wta'],
        'n_circuits_connus': sum(1 for v in out.values() if v.get('circuit')),
        'source_cotes': ('cloture Pinnacle pre-match, marge retiree, tous les '
                         'matchs cotes') if H else
                        'ouverture Pinnacle, alertes seules (repli)',
        'min_cotes': MIN_COTES,
        'classement': (f'note ajustee aux adversaires (Elo sur logits des cotes '
                       f'justes Pinnacle, K={K_CLASSEMENT}), historique tennis-data '
                       f'puis nos releves ; cote_classement = cote face a un joueur '
                       f'moyen du circuit'),
        'min_rang': MIN_RANG,
        'sources': ['moves_detail_hist.csv', 'set_results.json',
                    'player_form.json', 'elo_reference.json'],
        'elo_ecart_surface': ELO_ECART_SURFACE,
        'avertissement': (
            "Aucun CLV ni taux de reussite par joueur : moves_detail_hist "
            "ne contient que des mouvements detectes, donc tout taux calcule "
            "dessus est du biais de selection."),
    }
    json.dump({'meta': meta, 'joueurs': out},
              open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n_med = sum(1 for v in out.values() if 'cote_mediane' in v)
    print(f"{OUT} : {len(out)} joueurs, {n_med} avec mediane "
          f"(>= {MIN_COTES} cotes)")
    par_elo = sum(1 for k, v in out.items()
                  if v.get('circuit') and elo_k.get(k, {}).get('tour'))
    print(f"  circuit connu : {meta['n_circuits_connus']} joueurs "
          f"({par_elo} par l'Elo, "
          f"{meta['n_circuits_connus'] - par_elo} par le graphe)")
    print(f"  classement ATP : {classes['atp']} joueurs (>= {MIN_RANG} cotes)")
    print(f"  classement WTA : {classes['wta']} joueurs")
    if n_sans:
        print(f"  {n_sans} joueur(s) assez cotes mais sans circuit : pas de rang")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
