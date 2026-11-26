#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pages_seo.py — des pages web lisibles sans JavaScript, pour être trouvé sur Google.

24/11/2026 (paquet 418, Lucas : « on part sur 1-2 ») : une page par MATCH TERMINÉ et par JOUEUR.
24/11/2026 (paquet 419, Lucas : « fais 1-2-3-4 ») : une page par TOURNOI (édition), un BILAN par semaine, toutes les
pages AUSSI EN ANGLAIS (/en/…, reliées par hreflang), et plus de LIENS entre les pages (autres matchs du tournoi,
face-à-face, tournoi, semaine).

Ce qui y figure — uniquement du PASSÉ, déjà public dans le bilan :
  • match : % annoncé AVANT le match (première prédiction, jamais retouchée), vainqueur, score, statistiques réelles
    face à ce que l'algorithme avait prévu ;
  • joueur : matchs analysés, victoires et défaites (total, par surface), forme récente, ses matchs ;
  • tournoi : matchs terminés du tournoi, vainqueurs trouvés par l'algorithme ;
  • semaine : matchs jugés, vainqueurs trouvés (total et par circuit), plus grosses surprises.
Jamais : un match à venir ou pas terminé, une cote, une source de cotes, un classement interne de l'algorithme (il
permettrait de recalculer les % réservés à l'accès Plus), la calibration (interne), un match ITF, un conseil de pari.

Source : Tennis_Edge_Lab/live/pronostics_resultats.json (matchs jugés, rapatrié à jour de R2 par pages.yml).
Sortie (dossier du site public, envoyé ensuite à R2 sous site/algo/), en français à la racine et en anglais sous en/ :
  match/<uid>.html, joueur/<slug>.html, tournoi/<slug>.html, bilan/<AAAA-sNN>.html,
  matchs.html, joueurs.html, tournois.html, bilans.html, et sitemap.xml (toutes les pages, les deux langues).
Le worker les sert sans « .html » (/match/<uid>, /en/match/<uid>, /matchs…).

Usage : python scripts/pages_seo.py [racine] [dossier_site]     (défaut : . _site/algo)
"""
import collections
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import performance_joueurs as PJ  # noqa: E402
import profils_saison as PSA  # noqa: E402  (487 : profil de la saison, descriptif)

PROFILS = {}   # 487 : {clé du nom: profil de la saison}, rempli par main()

SITE = 'https://gamesetalgo.com'
LANGUES = ('fr', 'en')
CIRCUITS = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
MIN_MATCHS_JOUEUR = 2
# 25/11/2026 (paquet 437) : une page pour CHAQUE joueur d'au moins un match publié, pour que son nom soit cliquable dans
# la fiche d'un match. Sous MIN_MATCHS_JOUEUR, la page n'est pas proposée aux moteurs de recherche (noindex, hors du
# plan du site et de la liste des joueurs) : trop mince pour le référencement, utile au visiteur.
MIN_PAGE_JOUEUR = 1
ECART_EDITION_J = 9                # deux matchs d'un même tournoi à plus de 9 jours : deux éditions
SURPRISE = 0.75                    # « grosse surprise » : favori annoncé à 75 % ou plus, battu
UID = re.compile(r'^[a-z0-9_-]{5,140}$')
def e(x):
    """Échappe pour le HTML (attributs entre guillemets doubles) ; l'apostrophe reste lisible."""
    return html.escape(x, quote=False).replace('"', '&quot;')



T = {
    'fr': dict(
        surfaces={'Hard': 'dur', 'Clay': 'terre battue', 'Grass': 'gazon', 'Carpet': 'moquette'},
        mois=('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'),
        stats=(('premiere_pct', '% de 1res balles'), ('gagnes_1re_pct', 'Points gagnés derrière la 1re'),
               ('gagnes_2e_pct', 'Points gagnés derrière la 2e'), ('aces', 'Aces'), ('doubles_fautes', 'Doubles fautes'),
               ('breaks', 'Breaks'), ('jeux_service_gagnes_pct', 'Jeux de service gagnés'), ('points_gagnes', 'Points gagnés')),
        accueil='Accueil', matchs='Matchs analysés', joueurs='Joueurs', tournois='Tournois', bilans='Bilans de la semaine',
        methode='Comment ça marche', mentions='Mentions légales', cgv='Conditions de vente', autre_langue='English',
        pied="Des probabilités calculées par un algorithme indépendant, pas des certitudes. Ce site ne donne aucun conseil de pari. "
             "Les paris sportifs sont interdits aux mineurs ; jouer comporte des risques : 09 74 75 13 13 (appel non surtaxé).",
        avant='Avant le match', simule="L'algorithme, qui simule chaque match 20 000 fois point par point, donnait",
        resultat='Résultat', gagne='gagne', sets='sets', fav_ok="✓ Le favori de l'algorithme a gagné.",
        surprise="✗ Surprise : l'algorithme donnait {n} favori à {p}.",
        interrompu='Match interrompu ({x}) : il ne compte pas dans le bilan.',
        stats_titre='Statistiques du match : réel contre prévu', prevu='prévu',
        prevu_note='« Prévu » : la moyenne des 20 000 simulations faites avant le match.',
        cta_txt="Le % de chaque match est publié avant qu'il commence, pour les abonnés Plus ; le match du jour est offert à tous.",
        cta='Voir les matchs du jour', retour_matchs='← Tous les matchs analysés', retour_joueurs='← Tous les joueurs',
        retour_tournois='← Tous les tournois', retour_bilans='← Tous les bilans',
        meme_tournoi='Autres matchs du tournoi', face_a_face='Leurs autres matchs analysés', semaine_de='Bilan de la semaine',
        titre_match='{h} – {a} : analyse, % de victoire et statistiques | {t} {y}',
        desc_match='{h} – {a} ({t}, {d}) : Game Set Algo donnait {f} gagnant à {p} avant le match. Résultat : {w} gagne{s}. '
                   'Statistiques réelles contre prévues.',
        analyses='{n} match{s} analysé{s} par Game Set Algo', vd='{v} victoire{sv} – {d} défaite{sd}', sur='sur les matchs analysés.',
        par_surface='Par surface', forme='Forme récente (du plus récent au plus ancien)', ses_matchs='Ses matchs analysés',
        contre='contre', annonce="Annoncé à {p} par l'algorithme", V='V', D='D',
        cta_joueur='Le % de victoire de chaque match à venir est publié avant le match pour les abonnés Plus.',
        titre_joueur='{n} : pronostics, forme et statistiques | Game Set Algo',
        desc_joueur='{n} : {v} victoires et {d} défaites sur {t} matchs analysés par Game Set Algo, forme récente {f}, '
                    'résultats par surface et % annoncé avant chaque match.',
        titre_tournoi='{t} {y} : résultats et analyse de chaque match | Game Set Algo',
        desc_tournoi='{t} {y} : {n} matchs analysés par Game Set Algo, {p} de vainqueurs trouvés. % annoncé avant chaque match, '
                     'score et statistiques.',
        tournoi_sub='{c} · {s} · du {d1} au {d2}', trouves='{k} vainqueurs trouvés sur {n} matchs ({p}).',
        titre_bilan='Bilan de la semaine {w} ({y}) : {p} de vainqueurs trouvés | Game Set Algo',
        desc_bilan='Semaine {w} ({y}) : {n} matchs de tennis analysés par Game Set Algo, {p} de vainqueurs trouvés. Toutes les '
                   'erreurs comprises.',
        bilan_h1='Bilan de la semaine {w} ({y})', bilan_sub='Du {d1} au {d2}', en_cours=' — semaine en cours',
        par_circuit='Par circuit', surprises='Les plus grosses surprises', aucune_surprise="Aucun favori à 75 % ou plus n'a perdu.",
        matchs_semaine='Les matchs de la semaine', fav_bat='{f} annoncé à {p}, battu par {w}',
        titre_matchs="Matchs de tennis analysés par l'algorithme : % annoncé et résultats | Game Set Algo",
        desc_matchs="Tous les matchs de tennis ATP, WTA et Challenger analysés par Game Set Algo : le % de victoire annoncé avant "
                    "le match, le résultat et les statistiques réelles contre prévues.",
        h1_matchs='Matchs analysés', sub_matchs="Chaque match terminé, avec le % que l'algorithme annonçait avant le match et les "
                                                "statistiques réelles. Erreurs comprises.",
        titre_joueurs='Joueurs de tennis : forme et matchs analysés | Game Set Algo',
        desc_joueurs='Forme récente, résultats par surface et matchs analysés par Game Set Algo pour chaque joueur et joueuse des '
                     'circuits ATP, WTA et Challenger.',
        sub_joueurs='Les joueuses et joueurs dont Game Set Algo a analysé au moins {n} matchs.', nb_matchs='{n} matchs',
        titre_tournois='Tournois de tennis : résultats et analyse de chaque match | Game Set Algo',
        desc_tournois='Tous les tournois ATP, WTA et Challenger suivis par Game Set Algo : résultats, % annoncé avant chaque match '
                      'et vainqueurs trouvés.',
        sub_tournois="Chaque tournoi suivi par l'algorithme, avec ses matchs terminés.",
        titre_bilans="Bilans de la semaine de l'algorithme de tennis | Game Set Algo",
        desc_bilans="Chaque semaine, les vainqueurs trouvés par Game Set Algo, par circuit, et les plus grosses surprises. "
                    "Toutes les erreurs comprises.",
        sub_bilans='Chaque semaine, ce que l\'algorithme a trouvé et raté.', semaine='Semaine {w} ({y})'),
    'en': dict(
        surfaces={'Hard': 'hard', 'Clay': 'clay', 'Grass': 'grass', 'Carpet': 'carpet'},
        mois=('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'),
        stats=(('premiere_pct', '1st serve %'), ('gagnes_1re_pct', '1st serve points won'), ('gagnes_2e_pct', '2nd serve points won'),
               ('aces', 'Aces'), ('doubles_fautes', 'Double faults'), ('breaks', 'Breaks'),
               ('jeux_service_gagnes_pct', 'Service games won'), ('points_gagnes', 'Points won')),
        accueil='Home', matchs='Analysed matches', joueurs='Players', tournois='Tournaments', bilans='Weekly records',
        methode='How it works', mentions='Legal notice', cgv='Terms of sale', autre_langue='Français',
        pied='Probabilities computed by an independent algorithm, not certainties. This site gives no betting advice. '
             'Sports betting is for adults only and carries risks.',
        avant='Before the match', simule='The algorithm, which simulates every match 20,000 times point by point, gave',
        resultat='Result', gagne='wins', sets='sets', fav_ok="✓ The algorithm's favourite won.",
        surprise='✗ Upset: the algorithm had {n} as favourite at {p}.',
        interrompu='Match interrupted ({x}): it does not count in the record.',
        stats_titre='Match stats: actual vs expected', prevu='expected',
        prevu_note='“Expected”: the average of the 20,000 simulations run before the match.',
        cta_txt='The win % of every match is published before it starts for Plus subscribers; the match of the day is free for all.',
        cta="See today's matches", retour_matchs='← All analysed matches', retour_joueurs='← All players',
        retour_tournois='← All tournaments', retour_bilans='← All weekly records',
        meme_tournoi='Other matches in this tournament', face_a_face='Their other analysed matches', semaine_de='Weekly record',
        titre_match='{h} vs {a}: analysis, win probability and stats | {t} {y}',
        desc_match='{h} vs {a} ({t}, {d}): Game Set Algo gave {f} a {p} chance to win before the match. Result: {w} wins{s}. '
                   'Actual vs expected stats.',
        analyses='{n} match{s} analysed by Game Set Algo', vd='{v} win{sv} – {d} loss{sd}', sur='in analysed matches.',
        par_surface='By surface', forme='Recent form (most recent first)', ses_matchs='Analysed matches',
        contre='vs', annonce='Given {p} by the algorithm', V='W', D='L',
        cta_joueur='The win % of every upcoming match is published before the match for Plus subscribers.',
        titre_joueur='{n}: predictions, form and stats | Game Set Algo',
        desc_joueur='{n}: {v} wins and {d} losses in {t} matches analysed by Game Set Algo, recent form {f}, results by surface '
                    'and the win % given before each match.',
        titre_tournoi='{t} {y}: results and analysis of every match | Game Set Algo',
        desc_tournoi='{t} {y}: {n} matches analysed by Game Set Algo, {p} of winners found. Win % given before each match, '
                     'scores and stats.',
        tournoi_sub='{c} · {s} · {d1} to {d2}', trouves='{k} winners found out of {n} matches ({p}).',
        titre_bilan='Week {w} ({y}) record: {p} of winners found | Game Set Algo',
        desc_bilan='Week {w} ({y}): {n} tennis matches analysed by Game Set Algo, {p} of winners found. Every miss included.',
        bilan_h1='Week {w} ({y}) record', bilan_sub='{d1} to {d2}', en_cours=' — current week',
        par_circuit='By tour', surprises='Biggest upsets', aucune_surprise='No favourite at 75% or more lost.',
        matchs_semaine="This week's matches", fav_bat='{f} given {p}, beaten by {w}',
        titre_matchs='Tennis matches analysed by the algorithm: win % and results | Game Set Algo',
        desc_matchs='Every ATP, WTA and Challenger match analysed by Game Set Algo: the win % given before the match, the result '
                    'and actual vs expected stats.',
        h1_matchs='Analysed matches', sub_matchs='Every finished match, with the win % the algorithm gave before it and the actual '
                                                  'stats. Every miss included.',
        titre_joueurs='Tennis players: form and analysed matches | Game Set Algo',
        desc_joueurs='Recent form, results by surface and matches analysed by Game Set Algo for every ATP, WTA and Challenger player.',
        sub_joueurs='Players with at least {n} matches analysed by Game Set Algo.', nb_matchs='{n} matches',
        titre_tournois='Tennis tournaments: results and analysis of every match | Game Set Algo',
        desc_tournois='Every ATP, WTA and Challenger tournament followed by Game Set Algo: results, win % given before each match and '
                      'winners found.',
        sub_tournois='Every tournament followed by the algorithm, with its finished matches.',
        titre_bilans='Weekly records of the tennis algorithm | Game Set Algo',
        desc_bilans='Every week, the winners found by Game Set Algo, by tour, and the biggest upsets. Every miss included.',
        sub_bilans='Every week, what the algorithm got right and wrong.', semaine='Week {w} ({y})'),
}

# 25/11/2026 (paquet 445, Lucas : « on doit encore améliorer le référencement », choix « affiche + teaser Plus ») — une
# page par match À VENIR (« Pronostic A – B »), là où les gens cherchent avant le match. Rien de réservé n'y figure : ni
# le %, ni le scénario, ni la fiabilité du match — seulement l'affiche, la forme et la performance publiques des
# joueurs, et le face-à-face déjà publié. Après le match, la même adresse devient la page du match terminé.
T['fr']['venir'] = dict(
    titre='Pronostic {h} – {a} : % de victoire et scénario du match | {t} {y}',
    desc="{h} – {a} ({t}, {d}) : l'algorithme Game Set Algo simule le match 20 000 fois — % de victoire, score set par set, "
         "jeux, aces, breaks et durée. Forme et statistiques des deux joueurs.",
    h1='Pronostic {h} – {a}', calcule="Ce que l'algorithme a calculé pour ce match",
    calcule_p="Le match a été simulé 20 000 fois, point par point. Le résultat est publié avant le début, puis jugé après, "
              "dans le bilan public.",
    crit=['% de victoire de chaque joueur', 'Score set par set', 'Nombre de jeux', 'Tie-breaks', 'Durée',
          'Aces', 'Doubles fautes', 'Breaks', '% de 1res balles', 'Scénarios possibles'],
    cta='Voir le % et le scénario complet', cta_note='Réservé aux abonnés Plus ; le match du jour est offert à tous.',
    joueur_t='{n} : forme et performance', aucun='Premier match analysé par Game Set Algo pour ce joueur.',
    bilan='{v} victoire{sv} – {d} défaite{sd} sur ses matchs analysés', fiab='Fiabilité du joueur : {f}/100',
    annonce_vs="L'algo annonçait {a} en moyenne sur ses {n} derniers matchs ; victoires réelles : {r}.",
    voir_joueur='Toute sa performance →', a_venir='Matchs à venir', prochain='Prochain match',
    face='Leurs matchs déjà analysés', vs='{h} – {a}', le_='le {d} à {hh}')
T['en']['venir'] = dict(
    titre='{h} vs {a} prediction: win % and match scenario | {t} {y}',
    desc="{h} vs {a} ({t}, {d}): the Game Set Algo algorithm simulates the match 20,000 times — win %, set-by-set score, "
         "games, aces, breaks and duration. Form and stats for both players.",
    h1='{h} vs {a} prediction', calcule='What the algorithm computed for this match',
    calcule_p='The match was simulated 20,000 times, point by point. The result is published before the start, then '
              'judged after, in the public record.',
    crit=['Win % for each player', 'Score set by set', 'Number of games', 'Tie-breaks', 'Duration',
          'Aces', 'Double faults', 'Breaks', '1st-serve %', 'Possible scenarios'],
    cta='See the % and the full scenario', cta_note='For Plus subscribers; the match of the day is free for everyone.',
    joueur_t='{n}: form and performance', aucun='First match analysed by Game Set Algo for this player.',
    bilan='{v} win{sv} – {d} loss{sd} in analysed matches', fiab='Player reliability: {f}/100',
    annonce_vs='The algorithm gave {a} on average over the last {n} matches; actual wins: {r}.',
    voir_joueur='Full performance →', a_venir='Upcoming matches', prochain='Next match',
    face='Their previously analysed matches', vs='{h} vs {a}', le_='on {d} at {hh}')


def matchs_a_venir(donnees, deja, maintenant=None):
    """Matchs du fichier du jour pas encore terminés : hors ITF, identifiant propre, pas déjà publiés comme terminés.
    Seuls les champs de l'affiche sont gardés (jamais le %, le scénario ni la fiabilité)."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M')
    out = []
    for m in (donnees or {}).get('matchs') or []:
        uid = str(m.get('uid') or '')
        if m.get('circuit') not in CIRCUITS or not UID.match(uid) or uid in deja or not m.get('home') or not m.get('away'):
            continue
        if str(m.get('debut') or '')[:16] < (dt.datetime.fromisoformat(maintenant) - dt.timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M'):
            continue                                       # commencé depuis longtemps : sa page de fin arrive avec le résultat
        out.append({k: m.get(k) for k in ('uid', 'debut', 'home', 'away', 'tournoi', 'circuit', 'surface', 'meilleur_des')})
    out.sort(key=lambda m: (str(m['debut']), m['uid']))
    return out


# 25/11/2026 (paquet 438) : « Performance des joueurs » — l'algo face à ce joueur (historique, ne change aucun %)
T['fr']['perf'] = dict(
    titre='Performance des joueurs', sous="Ce que l'algorithme annonçait pour {n}, contre ce qui est arrivé — ses {k} derniers matchs analysés.",
    annonce='annoncé en moyenne', victoires='victoires réelles', ecart='victoire{s} {sens} que prévu', plus='de plus', moins='de moins',
    ecart_nul='autant de victoires que prévu', fiab='fiabilité du joueur', provisoire='provisoire',
    niveaux={'haut': 'fiable', 'moyen': 'moyenne', 'bas': 'imprévisible'},
    fiab_aide="Fiabilité du joueur : ses résultats suivent-ils nos % ? 100 : il gagne exactement aussi souvent qu'annoncé ; "
              "plus la note baisse, plus il gagne (ou perd) souvent à rebours de nos %. Calculée sur ses {k} derniers matchs analysés.",
    fiab_absente='Fiabilité du joueur : pas encore de note (au moins {m} matchs analysés).',
    barre="Trait : {a} annoncé · Barre : {r} réalisé", stats='Statistiques : prévu contre réel', stat='', prevu='Prévu',
    reel='Réel', ecart_moyen='Écart moyen', repere='Tous joueurs', par_match='par match',
    stats_aide="Moyennes par match sur ses {n} derniers matchs dont la feuille est connue. « Tous joueurs » : l'écart moyen de "
               "l'algorithme sur tous les joueurs du circuit — plus l'écart du joueur est petit, plus nos prévisions sont précises pour lui.",
    noms={'aces': 'Aces', 'breaks': 'Breaks réussis'}, surfaces='Par surface', styles='Contre les styles de jeu',
    matchs='Matchs', vd='V – D', groupe_aide="Sur tous ses matchs analysés : % moyen annoncé pour lui, puis % de victoires réel.",
    styles_aide="Style de l'adversaire : nos catégories internes, mesurées sur ses feuilles de match (style au moment du match, "
                "sinon le dernier connu).", peu='trop peu de matchs',
    style_noms={'grand_serveur': 'Grands serveurs', 'serveur_attaquant': 'Serveurs attaquants',
                'retourneur_pressant': 'Retourneurs pressants', 'contreur': 'Contreurs', 'equilibre': 'Profils équilibrés'},
    rien='Pas encore assez de matchs analysés pour ce joueur.',
    note="Historique de l'algorithme : il ne change pas le % de ses prochains matchs. Sur quelques dizaines de matchs, ces "
         "chiffres bougent vite : à lire comme une tendance, pas comme une règle.",
    liste_fiab='fiabilité {f}/100')
T['en']['perf'] = dict(
    titre='Player performance', sous="What the algorithm gave {n}, against what happened — last {k} analysed matches.",
    annonce='average announced', victoires='actual wins', ecart='win{s} {sens} than expected', plus='more', moins='fewer',
    ecart_nul='as many wins as expected', fiab='player reliability', provisoire='provisional',
    niveaux={'haut': 'reliable', 'moyen': 'average', 'bas': 'unpredictable'},
    fiab_aide="Player reliability: do his results follow our %? 100: he wins exactly as often as announced; the lower the score, "
              "the more often he wins (or loses) against our %. Based on his last {k} analysed matches.",
    fiab_absente='Player reliability: no score yet (at least {m} analysed matches).',
    barre="Mark: {a} announced · Bar: {r} actual", stats='Stats: predicted vs actual', stat='', prevu='Predicted',
    reel='Actual', ecart_moyen='Average gap', repere='All players', par_match='per match',
    stats_aide="Per-match averages over his last {n} matches with a known match sheet. \"All players\": the algorithm's average gap "
               "over every player on the tour — the smaller his gap, the more accurate our predictions are for him.",
    noms={'aces': 'Aces', 'breaks': 'Breaks won'}, surfaces='By surface', styles='Against playing styles',
    matchs='Matches', vd='W – L', groupe_aide="Over all his analysed matches: average % announced for him, then actual win %.",
    styles_aide="Opponent style: our own categories, measured from match sheets (style at the time of the match, otherwise the "
                "latest known).", peu='too few matches',
    style_noms={'grand_serveur': 'Big servers', 'serveur_attaquant': 'Attacking servers',
                'retourneur_pressant': 'Pressing returners', 'contreur': 'Counterpunchers', 'equilibre': 'Balanced profiles'},
    rien='Not enough analysed matches for this player yet.',
    note="Algorithm history: it does not change the % of his next matches. Over a few dozen matches these figures move fast: "
         "read them as a trend, not a rule.",
    liste_fiab='reliability {f}/100')


def slug(nom):
    s = unicodedata.normalize('NFKD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:80]


def date_txt(iso, L='fr'):
    try:
        d = dt.date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)[:10]
    m = T[L]['mois'][d.month - 1]
    return f"{d.day} {m} {d.year}" if L == 'fr' else f"{m} {d.day}, {d.year}"


def pc(x, L='fr'):
    return f"{100 * x:.0f} %" if L == 'fr' else f"{100 * x:.0f}%"


def p_annonce(m):
    pr = m.get('premier') or {}
    for k in ('combinaison', 'simulation', 'stats'):
        if isinstance(pr.get(k), dict) and pr[k].get('p_home') is not None:
            return float(pr[k]['p_home'])
    return float(m['p_affiche']) if m.get('p_affiche') is not None else None


def matchs_publiables(doc, maintenant=None):
    """Matchs terminés (vainqueur connu), commencés, hors ITF, avec un % annoncé et un identifiant propre."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M')
    out = []
    for m in (doc or {}).get('matchs') or []:
        r = m.get('reel') or {}
        if m.get('circuit') not in CIRCUITS or r.get('gagnant') not in ('home', 'away') or not UID.match(str(m.get('uid') or '')):
            continue
        if str(m.get('debut') or '')[:16] > maintenant or p_annonce(m) is None:
            continue
        out.append(m)
    out.sort(key=lambda m: (str(m.get('debut')), m['uid']), reverse=True)
    return out


def score_vu_par(score, a_domicile):
    """« 6-4 3-6 » vu du joueur : jeux inversés s'il était le second nommé."""
    if a_domicile or not score:
        return score
    return ' '.join('-'.join(reversed(s.split('-'))) if s.count('-') == 1 else s for s in str(score).split())


def vainqueur(m):
    return m['home'] if m['reel']['gagnant'] == 'home' else m['away']


def favori(m):
    p = p_annonce(m)
    return (m['home'], p) if p >= 0.5 else (m['away'], 1 - p)


def juge(m):
    return not (m.get('reel') or {}).get('interrompu')


def semaine(m):
    y, w, _ = dt.date.fromisoformat(str(m['debut'])[:10]).isocalendar()
    return f"{y}-s{w:02d}"


# ------------------------------------------------------------------------------------------------ gabarit commun
CSS = """:root{--bg:#0E0A24;--panel:#191338;--ink:#F4F1FF;--dim:#A9A2CC;--p1:#2EE6FF;--p2:#FF4FAE;--ok:#3ee08a;--ko:#ff6b7d;--ball:#D4FF3A;--line:rgba(255,255,255,.12);--chip:rgba(255,255,255,.04);--piste:rgba(255,255,255,.08);--trait:#fff;--cta-txt:#141225;color-scheme:dark}
html[data-theme="light"]{--bg:#F4F2FB;--panel:#FFFFFF;--ink:#1B1640;--dim:#5C5788;--p1:#0A7FA3;--p2:#C21F78;--ok:#0E8A57;--ko:#C92A4D;--ball:#6F9500;--line:rgba(30,20,80,.14);--chip:rgba(30,20,80,.04);--piste:rgba(30,20,80,.10);--trait:#1B1640;--cta-txt:#fff;color-scheme:light}
html[data-theme="light"] .panel{box-shadow:0 6px 22px rgba(40,20,120,.08)}html[data-theme="light"] header .b{box-shadow:none}
@font-face{font-family:"Bungee";font-display:swap;src:url(/polices/bungee-400.woff2) format("woff2")}
@font-face{font-family:"Barlow";font-weight:400;font-display:swap;src:url(/polices/barlow-400.woff2) format("woff2")}
@font-face{font-family:"Barlow";font-weight:600;font-display:swap;src:url(/polices/barlow-600.woff2) format("woff2")}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Barlow,system-ui,sans-serif}
.w{max-width:760px;margin:0 auto;padding:18px 16px 40px}a{color:var(--p1)}
header{display:flex;align-items:center;gap:10px;margin-bottom:18px}header a{color:var(--ink);text-decoration:none;font-family:Bungee,system-ui;font-size:1.15rem}
header .b{width:14px;height:14px;border-radius:50%;background:var(--ball);box-shadow:0 0 12px var(--ball)}header .lg{margin-left:auto;font:600 .85rem Barlow,system-ui;color:var(--dim)}
h1{font-family:Bungee,system-ui;font-weight:400;font-size:1.7rem;line-height:1.15;margin:0 0 6px}h2{font-size:1.15rem;margin:26px 0 8px}
.sub{color:var(--dim);margin:0 0 14px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0}
.a{color:var(--p1)}.b2{color:var(--p2)}.ok{color:var(--ok)}.ko{color:var(--ko)}
table{width:100%;border-collapse:collapse;font-size:.95rem}th,td{padding:7px 6px;border-bottom:1px solid var(--line);text-align:center}
th:first-child,td:first-child{text-align:left}small{color:var(--dim)}ul.l{list-style:none;padding:0;margin:0}ul.l li{padding:7px 0;border-bottom:1px solid var(--line)}
.cta{display:inline-block;margin-top:10px;background:var(--ball);color:var(--cta-txt);font-weight:600;padding:10px 16px;border-radius:999px;text-decoration:none}
footer{margin-top:34px;color:var(--dim);font-size:.85rem}footer a{color:var(--dim)}
h3{font-size:1rem;margin:18px 0 6px}.jaune{color:var(--ball)}.aide{color:var(--dim);font-size:.85rem;margin:6px 0 0}
.pf .note{color:var(--dim);font-size:.85rem;margin:14px 0 0;padding-top:10px;border-top:1px solid var(--line)}
.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}@media(min-width:640px){.kpis{grid-template-columns:repeat(4,minmax(0,1fr))}}
.k{background:var(--chip);border:1px solid var(--line);border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:2px}
.kv{font-family:Bungee,system-ui;font-size:1.45rem;line-height:1.1}.kv small{font:600 .85rem Barlow,system-ui;color:var(--dim);margin-left:2px}
.kl{color:var(--dim);font-size:.82rem;line-height:1.3}
.cmp{position:relative;height:10px;border-radius:999px;background:var(--piste);margin:16px 0 4px}
.cmp i{position:absolute;left:0;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,var(--p1),var(--p2))}
.cmp b{position:absolute;top:-4px;bottom:-4px;width:3px;margin-left:-1px;border-radius:2px;background:var(--trait);box-shadow:0 0 6px rgba(0,0,0,.6)}
.fj{font-size:.8rem;color:var(--dim);margin-left:6px}
.venir{border-color:var(--p1)}.crit{list-style:none;padding:0;margin:10px 0 4px;display:flex;flex-wrap:wrap;gap:6px}
.crit li{border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:.88rem;color:var(--dim)}
.duo{display:grid;gap:12px}@media(min-width:640px){.duo{grid-template-columns:1fr 1fr}}.duo .panel{margin:0}
/* 25/11/2026 (paquet 444) : liens au style du site — noms en clair, sans soulignement, petite flèche discrète */
ul.l a,.panel a:not(.cta),p a,td a{color:var(--ink);text-decoration:none;font-weight:600}
ul.l a:first-of-type::after{content:" ›";color:var(--dim);font-weight:400}
ul.l a+a,ul.l li>a~a{color:var(--dim);font-weight:400}ul.l a+a::after{content:""}
ul.l a:hover,p a:hover,td a:hover{color:var(--p1)}
footer a,footer p a{color:var(--dim);font-weight:400;text-decoration:none}footer p a:hover{color:var(--ink)}
header{flex-wrap:wrap;row-gap:8px}header>a:first-of-type{white-space:nowrap}
.th{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-left:auto}
.th button{background:transparent;color:var(--dim);border:0;font:600 .78rem Barlow,system-ui;padding:6px 9px;cursor:pointer;min-height:32px}
.th button[aria-pressed="true"]{background:var(--ball);color:var(--cta-txt)}"""


def pre(L):
    return '' if L == 'fr' else '/en'


# 25/11/2026 (paquet 441, Lucas : « la fiche des joueurs est sombre, on devrait pouvoir choisir clair ou sombre ») —
# mêmes réglages que la page d'accueil (Auto, Clair, Sombre ; sombre par défaut), même mémoire sur l'appareil (te_theme) :
# un choix fait sur l'accueil vaut pour les pages des joueurs, des matchs, des tournois et des bilans, et inversement.
THEME_TETE = ("(function(){try{var v=localStorage.getItem('te_theme')||'dark';var d=v==='auto'?(matchMedia('(prefers-color-scheme: dark)')"
              ".matches?'dark':'light'):v;document.documentElement.setAttribute('data-theme',d==='light'?'light':'dark');}catch(e){}})();")
THEME_BASCULE = ("(function(){var b=document.querySelectorAll('.th button');function app(v){var d=v==='auto'?(window.matchMedia&&matchMedia("
                 "'(prefers-color-scheme: dark)').matches?'dark':'light'):v;document.documentElement.setAttribute('data-theme',d==='light'?'light':'dark');"
                 "var m=document.querySelector('meta[name=theme-color]');if(m)m.setAttribute('content',d==='light'?'#F4F2FB':'#0E0A24');"
                 "for(var i=0;i<b.length;i++)b[i].setAttribute('aria-pressed',String(b[i].getAttribute('data-th')===v));}"
                 "var v='dark';try{v=localStorage.getItem('te_theme')||'dark';}catch(e){}app(v);"
                 "for(var i=0;i<b.length;i++)b[i].addEventListener('click',function(){v=this.getAttribute('data-th');"
                 "try{localStorage.setItem('te_theme',v);}catch(e){}app(v);});"
                 "if(window.matchMedia){var q=matchMedia('(prefers-color-scheme: dark)');if(q.addEventListener)q.addEventListener('change',function(){if(v==='auto')app(v);});}})();")


def bascule_theme(L):
    lib = [('auto', 'Auto'), ('light', 'Clair' if L == 'fr' else 'Light'), ('dark', 'Sombre' if L == 'fr' else 'Dark')]
    return ('<span class="th" role="group" aria-label="' + ('Thème' if L == 'fr' else 'Theme') + '">'
            + ''.join(f'<button type="button" data-th="{k}" aria-pressed="{str(k == "dark").lower()}">{e(v)}</button>' for k, v in lib) + '</span>')


def page(L, titre, description, chemin, corps, ld=None, og='article', indexer=True):
    """chemin : sans préfixe de langue (« /match/x ») ; la page existe dans les deux langues."""
    t = T[L]
    url = SITE + pre(L) + chemin
    alt = ''.join(f'<link rel="alternate" hreflang="{x}" href="{e(SITE + pre(x) + chemin)}">' for x in LANGUES) \
        + f'<link rel="alternate" hreflang="x-default" href="{e(SITE + chemin)}">'
    lds = ''.join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (ld if isinstance(ld, list) else [ld]) if x)
    accueil = '/' if L == 'fr' else '/?lang=en'
    autre = 'en' if L == 'fr' else 'fr'
    p = pre(L)
    return f"""<!doctype html>
<html lang="{L}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<script>{THEME_TETE}</script>
<title>{e(titre)}</title><meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(url)}">{alt}{'' if indexer else '<meta name="robots" content="noindex, follow">'}<meta name="theme-color" content="#0E0A24">
<meta property="og:title" content="{e(titre)}"><meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(url)}"><meta property="og:type" content="{og}"><meta property="og:site_name" content="Game Set Algo">
<meta property="og:locale" content="{'fr_FR' if L == 'fr' else 'en_GB'}"><meta property="og:image" content="{SITE}/partage.png"><link rel="icon" href="/icone-192.png">{lds}
<style>{CSS}</style></head><body><div class="w">
<header><span class="b" aria-hidden="true"></span><a href="{accueil}">Game Set Algo</a><a class="lg" href="{e(pre(autre) + chemin)}" hreflang="{autre}">{e(t['autre_langue'])}</a>{bascule_theme(L)}</header>
{corps}
<footer><p><a href="{accueil}">{e(t['accueil'])}</a> · <a href="{p}/matchs">{e(t['matchs'])}</a> · <a href="{p}/joueurs">{e(t['joueurs'])}</a> · <a href="{p}/tournois">{e(t['tournois'])}</a> · <a href="{p}/bilans">{e(t['bilans'])}</a> · <a href="/methode.html{'' if L == 'fr' else '?lang=en'}">{e(t['methode'])}</a> · <a href="/#mentions">{e(t['mentions'])}</a> · <a href="/#cgv">{e(t['cgv'])}</a></p>
<p>{e(t['pied'])}</p></footer>
</div><script>{THEME_BASCULE}</script></body></html>
"""


class Site:
    """Index des matchs publiables : joueurs, éditions de tournoi, semaines, face-à-face."""

    def __init__(self, matchs):
        self.matchs = matchs
        self.par_joueur = collections.defaultdict(list)
        for m in matchs:
            for n in (m['home'], m['away']):
                self.par_joueur[n].append(m)
        self.slugs_j, pris = {}, set()
        for n in sorted(self.par_joueur, key=lambda n: (-len(self.par_joueur[n]), n)):
            if len(self.par_joueur[n]) < MIN_PAGE_JOUEUR or not slug(n):
                continue
            s, i = slug(n), 2
            while s in pris:
                s, i = f"{slug(n)}-{i}", i + 1
            pris.add(s)
            self.slugs_j[n] = s
        self.bilans, self.styles, self.reperes, self.perf = {}, {}, {}, {}   # 438 : performance des joueurs
        self.a_venir = []                                                    # 445 : matchs à venir (affiche seulement)
        self.indexable = lambda n: len(self.par_joueur.get(n, ())) >= MIN_MATCHS_JOUEUR  # noqa: E731
        # éditions de tournoi : même nom, matchs à moins de ECART_EDITION_J jours les uns des autres
        par_nom = collections.defaultdict(list)
        for m in matchs:
            if m.get('tournoi'):
                par_nom[m['tournoi']].append(m)
        self.editions, self.edition_de = {}, {}
        for nom, ms in par_nom.items():
            ms = sorted(ms, key=lambda m: str(m['debut']))
            groupes, cour = [], [ms[0]]
            for m in ms[1:]:
                if (dt.date.fromisoformat(str(m['debut'])[:10]) - dt.date.fromisoformat(str(cour[-1]['debut'])[:10])).days > ECART_EDITION_J:
                    groupes.append(cour)
                    cour = [m]
                else:
                    cour.append(m)
            groupes.append(cour)
            annees = collections.Counter(str(g[0]['debut'])[:4] for g in groupes)
            for g in groupes:
                y = str(g[0]['debut'])[:4]
                s = f"{slug(nom)}-{y}" if annees[y] == 1 else f"{slug(nom)}-{str(g[0]['debut'])[:10]}"
                if not slug(nom):
                    continue
                self.editions[s] = {'nom': nom, 'annee': y, 'matchs': sorted(g, key=lambda m: (str(m['debut']), m['uid']), reverse=True)}
                for m in g:
                    self.edition_de[m['uid']] = s
        self.semaines = collections.defaultdict(list)
        for m in matchs:
            self.semaines[semaine(m)].append(m)
        self.duels = collections.defaultdict(list)
        for m in matchs:
            self.duels[frozenset((m['home'], m['away']))].append(m)

    def lien_j(self, n, L):
        return f'<a href="{pre(L)}/joueur/{self.slugs_j[n]}">{e(n)}</a>' if n in self.slugs_j else e(n)


def _li_match(m, L, extra=''):
    sc = f" · {e(m['reel']['score'])}" if m['reel'].get('score') else ''
    return f'<li><a href="{pre(L)}/match/{m["uid"]}">{e(m["home"])} – {e(m["away"])}</a> <small>{extra}{e(date_txt(m.get("debut"), L))}{sc}</small></li>'


def page_match(m, S, L):
    t = T[L]
    h, a = m['home'], m['away']
    r = m['reel']
    p = p_annonce(m)
    fav, pf = favori(m)
    w = vainqueur(m)
    circ = CIRCUITS.get(m['circuit'], m['circuit'])
    surf = t['surfaces'].get(m.get('surface'), m.get('surface') or '')
    date = date_txt(m.get('debut'), L)
    issue = f'<p class="ok">{e(t["fav_ok"])}</p>' if w == fav else f'<p class="ko">{e(t["surprise"].format(n=fav, p=pc(pf, L)))}</p>'
    if r.get('interrompu'):
        issue = f'<p><small>{e(t["interrompu"].format(x=r["interrompu"]))}</small></p>'
    diag = ((m.get('diagnostic') or {}).get('stats') or {})
    feuille = r.get('feuille') if isinstance(r.get('feuille'), list) and len(r['feuille']) == 2 else None
    lignes = []
    for cle, lib in t['stats']:
        pct = cle.endswith('_pct')
        d, vals = diag.get(cle) or {}, []
        for i, camp in enumerate(('home', 'away')):
            reel = (d.get(camp) or {}).get('reel')
            if reel is None and feuille:
                reel = (feuille[i] or {}).get(cle)
            prevu = (d.get(camp) or {}).get('prevu')
            if reel is None:
                vals = None
                break
            fmt = (lambda x: pc(float(x) / 100, L)) if pct else (lambda x: f"{float(x):.0f}")
            vals.append(fmt(reel) + (f"<br><small>{t['prevu']} {fmt(prevu)}</small>" if prevu is not None else ''))
        if vals:
            lignes.append(f"<tr><td>{e(lib)}</td><td>{vals[0]}</td><td>{vals[1]}</td></tr>")
    stats = (f"""<h2>{e(t['stats_titre'])}</h2><div class="panel"><table><thead><tr><th></th><th class="a">{e(h)}</th><th class="b2">{e(a)}</th></tr></thead>
<tbody>{''.join(lignes)}</tbody></table><p><small>{e(t['prevu_note'])}</small></p></div>""" if lignes else '')
    ed = S.edition_de.get(m['uid'])
    lieu = m.get('tournoi') or ''
    lieu_html = (f'<a href="{pre(L)}/tournoi/{ed}">{e(lieu)}</a>' if ed else e(lieu))
    if circ.lower() not in lieu.lower():
        lieu_html += f' · {e(circ)}'
    # 419 : liens entre les pages — autres matchs du tournoi, face-à-face, semaine
    autres = [x for x in (S.editions[ed]['matchs'] if ed else []) if x['uid'] != m['uid']][:10]
    duel = [x for x in S.duels[frozenset((h, a))] if x['uid'] != m['uid']]
    liens = ''
    if duel:
        liens += f"<h2>{e(t['face_a_face'])}</h2><ul class=\"l\">{''.join(_li_match(x, L, e(x.get('tournoi') or '') + ' · ') for x in duel)}</ul>"
    if autres:
        liens += f"<h2>{e(t['meme_tournoi'])}</h2><ul class=\"l\">{''.join(_li_match(x, L) for x in autres)}</ul>"
    sem = semaine(m)
    corps = f"""<h1>{e(h)} – {e(a)}</h1><p class="sub">{lieu_html} · {e(surf)} · {e(date)}</p>
<div class="panel"><h2 style="margin-top:0">{e(t['avant'])}</h2><p>{e(t['simule'])}
<b class="a">{S.lien_j(h, L)} {pc(p, L)}</b> – <b class="b2">{pc(1 - p, L)} {S.lien_j(a, L)}</b>.</p>
<h2>{e(t['resultat'])}</h2><p><b>{S.lien_j(w, L)}</b> {e(t['gagne'])}{(' ' + e(r['score'])) if r.get('score') else ''}{(' (' + t['sets'] + ' ' + e(r['sets']) + ')') if r.get('sets') else ''}.</p>{issue}</div>
{stats}{liens}
<div class="panel"><p>{e(t['cta_txt'])}</p><a class="cta" href="{'/' if L == 'fr' else '/?lang=en'}">{e(t['cta'])}</a></div>
<p><a href="{pre(L)}/bilan/{sem}">{e(t['semaine_de'])} {e(sem.replace('-s', ' · '))}</a> · <a href="{pre(L)}/matchs">{e(t['retour_matchs'])}</a></p>"""
    titre = t['titre_match'].format(h=h, a=a, t=m.get('tournoi') or circ, y=str(m.get('debut'))[:4])
    desc = t['desc_match'].format(h=h, a=a, t=m.get('tournoi') or circ, d=date, f=fav, p=pc(pf, L), w=w,
                                  s=(' ' + r['score']) if r.get('score') else '')
    ld = {'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': f"{h} – {a}", 'sport': 'Tennis',
          'startDate': str(m.get('debut')), 'location': {'@type': 'Place', 'name': m.get('tournoi') or circ},
          'competitor': [{'@type': 'Person', 'name': h}, {'@type': 'Person', 'name': a}], 'url': f"{SITE}{pre(L)}/match/{m['uid']}"}
    return page(L, titre, desc, f"/match/{m['uid']}", corps, [ld, _fil(L, [(t['matchs'], '/matchs'), (f"{h} – {a}", f"/match/{m['uid']}")])])


def _dec(x, L, k=1, signe=False):
    t = f"{x:+.{k}f}" if signe else f"{x:.{k}f}"
    return t.replace('.', ',').replace('-', '−') if L == 'fr' else t.replace('-', '−')


def _perf(S, nom):
    if nom not in S.perf:
        S.perf[nom] = PJ.performance(nom, S.par_joueur[nom], lambda m: p_annonce(m) if m['home'] == nom else 1 - p_annonce(m),
                                     S.bilans, S.styles, S.reperes)
    return S.perf[nom]


def _prochain(nom, S, L):
    """445 : le prochain match du joueur (page « à venir »), pour relier les pages entre elles."""
    x = next((m for m in S.a_venir if nom in (m['home'], m['away'])), None)
    if not x:
        return ''
    V = T[L]['venir']
    adv = x['away'] if x['home'] == nom else x['home']
    return (f'<p>{e(V["prochain"])} : <a href="{pre(L)}/match/{x["uid"]}">{e(T[L]["contre"])} {e(adv)}</a> '
            f'<small>— {e(x.get("tournoi") or "")}, {e(date_txt(x.get("debut"), L))}</small></p>')


def bloc_performance(nom, S, L):
    """25/11/2026 (paquet 438) — « Performance des joueurs » : l'algo face à ce joueur (scripts/performance_joueurs.py)."""
    t, P = T[L], T[L]['perf']
    x = _perf(S, nom)
    if not x:
        return f'<h2>{e(P["titre"])}</h2><div class="panel"><p>{e(P["rien"])}</p></div>'
    n = x['n']
    ev = x['ecart_victoires']
    sens = P['plus'] if ev > 0 else P['moins']
    ecart_txt = P['ecart_nul'] if abs(ev) < 0.05 else P['ecart'].format(s='s' if abs(ev) >= 2 else '', sens=sens)
    cl_ecart = 'ok' if ev > 0.05 else 'ko' if ev < -0.05 else ''
    f = x['fiabilite']
    if f is not None:
        niv = 'haut' if f >= 75 else 'moyen' if f >= 50 else 'bas'
        cl = {'haut': 'ok', 'moyen': 'jaune', 'bas': 'ko'}[niv]
        fiab = (f'<div class="k"><span class="kv {cl}">{f}<small>/100</small></span><span class="kl">{e(P["fiab"])} · '
                f'{e(P["niveaux"][niv])}{" · " + e(P["provisoire"]) if x["provisoire"] else ""}</span></div>')
        fiab_aide = f'<p class="aide">{e(P["fiab_aide"].format(k=n))}</p>'
    else:
        fiab, fiab_aide = '', f'<p class="aide">{e(P["fiab_absente"].format(m=PJ.MIN_NOTE))}</p>'
    a, r = x['annonce_moyen'], x['victoires'] / n
    kpis = (f'<div class="kpis"><div class="k"><span class="kv">{e(pc(a, L))}</span><span class="kl">{e(P["annonce"])}</span></div>'
            f'<div class="k"><span class="kv">{x["victoires"]}<small>/{n}</small></span><span class="kl">{e(P["victoires"])} ({e(pc(r, L))})</span></div>'
            f'<div class="k"><span class="kv {cl_ecart}">{e(_dec(ev, L, signe=True))}</span><span class="kl">{e(ecart_txt)} '
            f'({e(_dec(x["ecart_pts"], L, signe=True))} pts)</span></div>{fiab}</div>')
    barre = (f'<div class="cmp"><i style="width:{100 * r:.1f}%"></i><b style="left:{100 * a:.1f}%"></b></div>'
             f'<p class="aide">{e(P["barre"].format(a=pc(a, L), r=pc(r, L)))}</p>')
    stats = ''
    if x['stats']:
        lignes = ''.join(
            f'<tr><td>{e(P["noms"][k])}</td><td>{e(_dec(v["prevu"], L))}</td><td>{e(_dec(v["reel"], L))}</td>'
            f'<td><b>{e(_dec(v["ecart_moyen"], L))}</b></td><td>{e(_dec(v["repere"], L)) if v.get("repere") is not None else "—"}</td></tr>'
            for k, v in x['stats'].items())
        nst = max(v['n'] for v in x['stats'].values())
        stats = (f'<h3>{e(P["stats"])}</h3><table><tr><th>{e(P["stat"])}</th><th>{e(P["prevu"])}</th><th>{e(P["reel"])}</th>'
                 f'<th>{e(P["ecart_moyen"])}</th><th>{e(P["repere"])}</th></tr>{lignes}</table>'
                 f'<p class="aide">{e(P["stats_aide"].format(n=nst))}</p>')

    def table(titre, groupes, nommer, aide):
        if not groupes:
            return ''
        li = []
        for k, g in groupes.items():
            if g['n'] < PJ.MIN_GROUPE:
                li.append(f'<tr><td>{e(nommer(k))}</td><td>{g["n"]}</td><td colspan="2"><small>{e(P["peu"])}</small></td></tr>')
                continue
            d = g['reel'] - g['annonce']
            cl = 'ok' if d > 0.03 else 'ko' if d < -0.03 else ''
            li.append(f'<tr><td>{e(nommer(k))}</td><td>{g["n"]} <small>({g["v"]}–{g["n"] - g["v"]})</small></td>'
                      f'<td>{e(pc(g["annonce"], L))}</td><td class="{cl}"><b>{e(pc(g["reel"], L))}</b></td></tr>')
        return (f'<h3>{e(titre)}</h3><table><tr><th></th><th>{e(P["matchs"])}</th><th>{e(P["annonce"].split(" ")[0].capitalize())}</th>'
                f'<th>{e(P["reel"])}</th></tr>{"".join(li)}</table><p class="aide">{e(aide)}</p>')
    surf = table(P['surfaces'], x['surfaces'], lambda k: t['surfaces'].get(k, k if k != '?' else '—').capitalize(), P['groupe_aide'])
    sty = table(P['styles'], x['styles'], lambda k: P['style_noms'].get(k, k), P['styles_aide'])
    return (f'<h2 id="performance">{e(P["titre"])}</h2><p class="sub">{e(P["sous"].format(n=nom, k=n))}</p>'
            f'<div class="panel pf">{kpis}{barre}{fiab_aide}</div>'
            f'<div class="panel pf">{stats}{surf}{sty}<p class="note">{e(P["note"])}</p></div>')


def _bloc_joueur_venir(nom, S, L):
    V = T[L]['venir']
    x = _perf(S, nom) if nom in S.par_joueur else None
    lien = f' <a href="{pre(L)}/joueur/{S.slugs_j[nom]}">{e(V["voir_joueur"])}</a>' if nom in S.slugs_j else ''
    if not x:
        return f'<div class="panel"><h3>{e(V["joueur_t"].format(n=nom))}</h3><p><small>{e(V["aucun"])}</small></p></div>'
    jug = [m for m in S.par_joueur[nom] if juge(m)]
    v = sum(1 for m in jug if vainqueur(m) == nom)
    d = len(jug) - v
    pl = (lambda k: 's' if k > 1 else '') if L == 'fr' else (lambda k: ('s' if k > 1 else ''))
    forme = ' '.join(T[L]['V'] if vainqueur(m) == nom else T[L]['D'] for m in jug[:10])
    lignes = [f'<p><b>{e(V["bilan"].format(v=v, d=d, sv=pl(v), sd=pl(d) if L == "fr" else ("es" if d > 1 else "")))}</b></p>']
    if forme:
        lignes.append(f'<p>{e(T[L]["forme"])} : <b>{e(forme)}</b></p>')
    lignes.append(f'<p><small>{e(V["annonce_vs"].format(a=pc(x["annonce_moyen"], L), n=x["n"], r=pc(x["victoires"] / x["n"], L)))}</small></p>')
    if x.get('fiabilite') is not None:
        lignes.append(f'<p><small>{e(V["fiab"].format(f=x["fiabilite"]))}</small></p>')
    return f'<div class="panel"><h3>{e(V["joueur_t"].format(n=nom))}</h3>{"".join(lignes)}<p>{lien}</p></div>'


def page_a_venir(m, S, L):
    t, V = T[L], T[L]['venir']
    h, a = m['home'], m['away']
    circ = CIRCUITS.get(m['circuit'], m['circuit'])
    surf = t['surfaces'].get(m.get('surface'), m.get('surface') or '')
    date = date_txt(m.get('debut'), L)
    heure = str(m.get('debut') or '')[11:16]
    tour = m.get('tournoi') or circ
    crit = ''.join(f'<li>🔒 {e(c)}</li>' for c in V['crit'])
    cible = ('/' if L == 'fr' else '/?lang=en') + '#match=' + m['uid']
    duel = S.duels.get(frozenset((h, a))) or []
    face = (f"<h2>{e(V['face'])}</h2><ul class=\"l\">{''.join(_li_match(x, L, e(x.get('tournoi') or '') + ' · ') for x in duel)}</ul>"
            if duel else '')
    corps = f"""<h1>{e(V['h1'].format(h=h, a=a))}</h1>
<p class="sub">{e(tour)}{' · ' + e(circ) if circ.lower() not in tour.lower() else ''} · {e(surf)} · {e(V['le_'].format(d=date, hh=heure))} (UTC)</p>
<div class="panel venir"><h2 style="margin-top:0">{e(V['calcule'])}</h2><p>{e(V['calcule_p'])}</p><ul class="crit">{crit}</ul>
<a class="cta" href="{e(cible)}">{e(V['cta'])} →</a><p><small>{e(V['cta_note'])}</small></p></div>
<div class="duo">{_bloc_joueur_venir(h, S, L)}{_bloc_joueur_venir(a, S, L)}</div>
{face}
<p><a href="{pre(L)}/matchs">{e(t['retour_matchs'])}</a></p>"""
    titre = V['titre'].format(h=h, a=a, t=tour, y=str(m.get('debut'))[:4])
    desc = V['desc'].format(h=h, a=a, t=tour, d=date)
    ld = {'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': f"{h} – {a}", 'sport': 'Tennis',
          'startDate': str(m.get('debut')) + ':00Z' if len(str(m.get('debut'))) == 16 else str(m.get('debut')),
          'eventStatus': 'https://schema.org/EventScheduled', 'location': {'@type': 'Place', 'name': tour},
          'competitor': [{'@type': 'Person', 'name': h}, {'@type': 'Person', 'name': a}], 'url': f"{SITE}{pre(L)}/match/{m['uid']}"}
    return page(L, titre, desc, f"/match/{m['uid']}", corps, [ld, _fil(L, [(t['matchs'], '/matchs'), (V['vs'].format(h=h, a=a), f"/match/{m['uid']}")])])


def _fil(L, etapes):
    """Fil d'Ariane (BreadcrumbList) : Accueil > … (paquet 445)."""
    el = [{'@type': 'ListItem', 'position': 1, 'name': T[L]['accueil'], 'item': SITE + ('/' if L == 'fr' else '/?lang=en')}]
    for i, (nom, chemin) in enumerate(etapes, 2):
        el.append({'@type': 'ListItem', 'position': i, 'name': nom, 'item': SITE + pre(L) + chemin})
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': el}


# 26/11/2026 (paquet 487) — PROFIL DE LA SAISON (descriptif : ne change pas le % de l'algo) : statistiques de l'année
# par surface (scripts/profils_saison.py), une colonne « toutes surfaces » et une par surface d'au moins 3 matchs.
PS_TXT = {'fr': {'titre': 'Profil de la saison {an}', 'sous': "Statistiques de l'année {an}. Information descriptive : elle ne change pas le % de l'algo.",
                 'tout': 'Toutes surfaces', 'Clay': 'Terre battue', 'Hard': 'Dur', 'Grass': 'Gazon', 'Carpet': 'Moquette',
                 'lignes': [('m', 'Matchs avec statistiques (V – D)'), ('ps', 'Points gagnés au service'), ('p1', 'Derrière la 1re balle'),
                            ('p2', 'Derrière la 2e balle'), ('pr', '1res balles'), ('ac', 'Aces par match'), ('df', 'Doubles fautes par match'),
                            ('bs', 'Balles de break sauvées'), ('bc', 'Balles de break converties'), ('tb', 'Jeux décisifs (gagnés – perdus)')],
                 'rang': 'Classement : {r}{b}', 'meilleur': ' (meilleur : {b})', 'utr': 'Classement UTR : {u}'},
          'en': {'titre': '{an} season profile', 'sous': '{an} season statistics. Descriptive only: it does not change the algo\'s %.',
                 'tout': 'All surfaces', 'Clay': 'Clay', 'Hard': 'Hard', 'Grass': 'Grass', 'Carpet': 'Carpet',
                 'lignes': [('m', 'Matches with statistics (W – L)'), ('ps', 'Service points won'), ('p1', '1st-serve points won'),
                            ('p2', '2nd-serve points won'), ('pr', '1st serves in'), ('ac', 'Aces per match'), ('df', 'Double faults per match'),
                            ('bs', 'Break points saved'), ('bc', 'Break points converted'), ('tb', 'Tie-breaks (won – lost)')],
                 'rang': 'Ranking: {r}{b}', 'meilleur': ' (career high: {b})', 'utr': 'UTR ranking: {u}'}}


def _val_ps(k, b, L):
    if k == 'm':
        return f"{b['m']} ({b.get('v', 0)} – {b['m'] - b.get('v', 0)})"
    if k == 'tb':
        g, p = (b.get('tb') or [0, 0])[:2]
        return f"{g} – {p}" if g or p else '—'
    v = b.get(k)
    if v is None:
        return '—'
    if k in ('ac', 'df'):
        return f"{v:.1f}".replace('.', ',') if L == 'fr' else f"{v:.1f}"
    return (f"{v:.0f} %" if L == 'fr' else f"{v:.0f}%")


def bloc_profil_saison(nom, L, profils=None):
    p = (profils if profils is not None else PROFILS).get(PSA.cle(nom))
    if not p or not p.get('tout'):
        return ''
    t = PS_TXT[L]
    cols = [('tout', p['tout'])] + [(k, p[k]) for k in ('Hard', 'Clay', 'Grass', 'Carpet') if (p.get(k) or {}).get('m', 0) >= 3]
    tete = ''.join(f'<th>{e(t[k])}</th>' for k, _ in cols)
    corps = ''.join(f"<tr><td>{e(lib)}</td>{''.join(f'<td>{e(_val_ps(k, b, L))}</td>' for _, b in cols)}</tr>" for k, lib in t['lignes'])
    cl = p.get('cl') or {}
    rang = ''
    if cl.get('rang'):
        rang += e(t['rang'].format(r=cl['rang'], b=t['meilleur'].format(b=cl['meilleur']) if cl.get('meilleur') else ''))
    if cl.get('utr'):
        rang += (' · ' if rang else '') + e(t['utr'].format(u=cl['utr']))
    return (f"<h2>{e(t['titre'].format(an=p['an']))}</h2><p class=\"sub\">{e(t['sous'].format(an=p['an']))}</p>"
            f"<div class=\"panel\"><table><thead><tr><th></th>{tete}</tr></thead><tbody>{corps}</tbody></table>"
            + (f"<p><small>{rang}</small></p>" if rang else '') + "</div>")


def page_joueur(nom, S, L):
    t = T[L]
    ms = S.par_joueur[nom]
    jug = [m for m in ms if juge(m)]
    gagne = lambda m: vainqueur(m) == nom  # noqa: E731
    v = sum(1 for m in jug if gagne(m))
    d = len(jug) - v
    forme = ' '.join(t['V'] if gagne(m) else t['D'] for m in jug[:10])
    li = []
    for m in ms[:40]:
        adv = m['away'] if m['home'] == nom else m['home']
        pj = p_annonce(m) if m['home'] == nom else 1 - p_annonce(m)
        res = '·' if not juge(m) else (f'<span class="ok">{t["V"]}</span>' if gagne(m) else f'<span class="ko">{t["D"]}</span>')
        sc = (' · ' + e(score_vu_par(m['reel']['score'], m['home'] == nom))) if m['reel'].get('score') else ''
        ed = S.edition_de.get(m['uid'])
        tn = f'<a href="{pre(L)}/tournoi/{ed}">{e(m.get("tournoi") or "")}</a>' if ed else e(m.get('tournoi') or '')
        li.append(f'<li>{res} <a href="{pre(L)}/match/{m["uid"]}">{e(t["contre"])} {e(adv)}</a> — {tn}, {e(date_txt(m.get("debut"), L))}'
                  f'<br><small>{e(t["annonce"].format(p=pc(pj, L)))}{sc}</small></li>')
    circuits = sorted({CIRCUITS.get(m['circuit'], m['circuit']) for m in ms})
    pl = 's' if len(ms) > 1 else ''
    corps = f"""<h1>{e(nom)}</h1><p class="sub">{e(' · '.join(circuits))} · {e(t['analyses'].format(n=len(ms), s=pl if L == 'fr' else ('es' if len(ms) > 1 else '')))}</p>
<div class="panel"><p><b>{e(t['vd'].format(v=v, d=d, sv=('s' if v > 1 else ''), sd=(('s' if d > 1 else '') if L == 'fr' else ('es' if d > 1 else ''))))}</b> {e(t['sur'])}</p>
<p>{e(t['forme'])} : <b>{e(forme) or '—'}</b></p>{_prochain(nom, S, L)}</div>
{bloc_performance(nom, S, L)}
{bloc_profil_saison(nom, L)}
<h2>{e(t['ses_matchs'])}</h2><ul class="l">{''.join(li)}</ul>
<div class="panel"><p>{e(t['cta_joueur'])}</p><a class="cta" href="{'/' if L == 'fr' else '/?lang=en'}">{e(t['cta'])}</a></div>
<p><a href="{pre(L)}/joueurs">{e(t['retour_joueurs'])}</a></p>"""
    titre = t['titre_joueur'].format(n=nom)
    desc = t['desc_joueur'].format(n=nom, v=v, d=d, t=len(jug), f=forme[:9])
    ld = {'@context': 'https://schema.org', '@type': 'Person', 'name': nom, 'url': f"{SITE}{pre(L)}/joueur/{S.slugs_j[nom]}"}
    return page(L, titre, desc, f"/joueur/{S.slugs_j[nom]}", corps, [ld, _fil(L, [(t['joueurs'], '/joueurs'), (nom, f"/joueur/{S.slugs_j[nom]}")])],
                og='profile', indexer=S.indexable(nom))


def _trouves(ms):
    jug = [m for m in ms if juge(m)]
    k = sum(1 for m in jug if vainqueur(m) == favori(m)[0])
    return k, len(jug)


def page_tournoi(s, S, L):
    t = T[L]
    ed = S.editions[s]
    ms = ed['matchs']
    k, n = _trouves(ms)
    circ = CIRCUITS.get(ms[0]['circuit'], ms[0]['circuit'])
    surf = t['surfaces'].get(ms[0].get('surface'), ms[0].get('surface') or '')
    d1, d2 = date_txt(ms[-1]['debut'], L), date_txt(ms[0]['debut'], L)
    par_jour = collections.OrderedDict()
    for m in ms:
        par_jour.setdefault(str(m['debut'])[:10], []).append(m)
    blocs = ''.join(f"<h2>{e(date_txt(j, L))}</h2><ul class=\"l\">{''.join(_li_annonce(m, S, L) for m in x)}</ul>" for j, x in par_jour.items())
    corps = f"""<h1>{e(ed['nom'])} {e(ed['annee'])}</h1><p class="sub">{e(t['tournoi_sub'].format(c=circ, s=surf, d1=d1, d2=d2))}</p>
<div class="panel"><p><b>{e(t['trouves'].format(k=k, n=n, p=pc(k / n, L) if n else '—'))}</b></p></div>{blocs}
<div class="panel"><p>{e(t['cta_txt'])}</p><a class="cta" href="{'/' if L == 'fr' else '/?lang=en'}">{e(t['cta'])}</a></div>
<p><a href="{pre(L)}/tournois">{e(t['retour_tournois'])}</a></p>"""
    titre = t['titre_tournoi'].format(t=ed['nom'], y=ed['annee'])
    desc = t['desc_tournoi'].format(t=ed['nom'], y=ed['annee'], n=n, p=pc(k / n, L) if n else '—')
    ld = {'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': f"{ed['nom']} {ed['annee']}", 'sport': 'Tennis',
          'startDate': str(ms[-1]['debut'])[:10], 'endDate': str(ms[0]['debut'])[:10], 'url': f"{SITE}{pre(L)}/tournoi/{s}"}
    return page(L, titre, desc, f"/tournoi/{s}", corps, ld)


def _li_annonce(m, S, L):
    t = T[L]
    fav, pf = favori(m)
    marque = '·' if not juge(m) else ('<span class="ok">✓</span>' if vainqueur(m) == fav else '<span class="ko">✗</span>')
    sc = f" · {e(m['reel']['score'])}" if m['reel'].get('score') else ''
    return (f'<li>{marque} <a href="{pre(L)}/match/{m["uid"]}">{e(m["home"])} – {e(m["away"])}</a>'
            f'<br><small>{e(t["annonce"].format(p=pc(pf, L)))} ({e(fav)}){sc}</small></li>')


def page_bilan(sem, S, L, maintenant):
    t = T[L]
    ms = sorted(S.semaines[sem], key=lambda m: (str(m['debut']), m['uid']), reverse=True)
    y, w = sem.split('-s')
    lundi = dt.date.fromisocalendar(int(y), int(w), 1)
    dimanche = lundi + dt.timedelta(days=6)
    en_cours = lundi <= dt.date.fromisoformat(maintenant[:10]) <= dimanche
    k, n = _trouves(ms)
    par_c = collections.defaultdict(list)
    for m in ms:
        par_c[CIRCUITS.get(m['circuit'], m['circuit'])].append(m)
    circ = ''.join(f"<li>{e(c)}{' :' if L == 'fr' else ':'} {e(t['trouves'].format(k=a, n=b, p=pc(a / b, L) if b else '—'))}</li>"
                   for c, (a, b) in sorted(((c, _trouves(x)) for c, x in par_c.items()), key=lambda kv: -kv[1][1]) if b)
    surpr = sorted((m for m in ms if juge(m) and vainqueur(m) != favori(m)[0] and favori(m)[1] >= SURPRISE), key=lambda m: -favori(m)[1])[:8]
    li_s = ''.join(f'<li><a href="{pre(L)}/match/{m["uid"]}">{e(t["fav_bat"].format(f=favori(m)[0], p=pc(favori(m)[1], L), w=vainqueur(m)))}</a>'
                   f' <small>{e(m.get("tournoi") or "")}</small></li>' for m in surpr) or f"<li>{e(t['aucune_surprise'])}</li>"
    corps = f"""<h1>{e(t['bilan_h1'].format(w=int(w), y=y))}</h1><p class="sub">{e(t['bilan_sub'].format(d1=date_txt(lundi.isoformat(), L), d2=date_txt(dimanche.isoformat(), L)))}{e(t['en_cours']) if en_cours else ''}</p>
<div class="panel"><p><b>{e(t['trouves'].format(k=k, n=n, p=pc(k / n, L) if n else '—'))}</b></p><h2>{e(t['par_circuit'])}</h2><ul class="l">{circ}</ul></div>
<h2>{e(t['surprises'])}</h2><ul class="l">{li_s}</ul>
<h2>{e(t['matchs_semaine'])}</h2><ul class="l">{''.join(_li_annonce(m, S, L) for m in ms)}</ul>
<p><a href="{pre(L)}/bilans">{e(t['retour_bilans'])}</a></p>"""
    titre = t['titre_bilan'].format(w=int(w), y=y, p=pc(k / n, L) if n else '—')
    desc = t['desc_bilan'].format(w=int(w), y=y, n=n, p=pc(k / n, L) if n else '—')
    return page(L, titre, desc, f"/bilan/{sem}", corps)


def page_index(L, quoi, S):
    t = T[L]
    if quoi == 'matchs':
        par_jour = collections.OrderedDict()
        for m in S.matchs[:400]:
            par_jour.setdefault(str(m.get('debut'))[:10], []).append(m)
        V = t['venir']
        venir = ''.join(f'<li><a href="{pre(L)}/match/{m["uid"]}">{e(V["vs"].format(h=m["home"], a=m["away"]))}</a> '
                        f'<small>{e(m.get("tournoi") or "")} · {e(date_txt(m.get("debut"), L))}</small></li>' for m in S.a_venir[:200])
        corps = f"<h1>{e(t['h1_matchs'])}</h1><p class=\"sub\">{e(t['sub_matchs'])}</p>" + (
            f"<h2>{e(V['a_venir'])}</h2><ul class=\"l\">{venir}</ul>" if venir else '') + ''.join(
            f"<h2>{e(date_txt(j, L))}</h2><ul class=\"l\">{''.join(_li_match(m, L, e(m.get('tournoi') or '') + ' · ') for m in ms)}</ul>"
            for j, ms in par_jour.items())
        return page(L, t['titre_matchs'], t['desc_matchs'], '/matchs', corps, og='website')
    if quoi == 'joueurs':
        noms = sorted((n for n in S.slugs_j if S.indexable(n)), key=lambda n: slug(n))
        def fj(n):                                   # 438 : la fiabilité du joueur dans la liste, quand elle existe
            x = _perf(S, n)
            return f' <span class="fj">· {e(t["perf"]["liste_fiab"].format(f=x["fiabilite"]))}</span>' if x and x.get('fiabilite') is not None else ''
        li = ''.join(f'<li><a href="{pre(L)}/joueur/{S.slugs_j[n]}">{e(n)}</a> <small>{e(t["nb_matchs"].format(n=len(S.par_joueur[n])))}</small>{fj(n)}</li>' for n in noms)
        corps = f"<h1>{e(t['joueurs'])}</h1><p class=\"sub\">{e(t['sub_joueurs'].format(n=MIN_MATCHS_JOUEUR))}</p><ul class=\"l\">{li}</ul>"
        return page(L, t['titre_joueurs'], t['desc_joueurs'], '/joueurs', corps, og='website')
    if quoi == 'tournois':
        eds = sorted(S.editions.items(), key=lambda kv: str(kv[1]['matchs'][0]['debut']), reverse=True)
        li = ''.join(f'<li><a href="{pre(L)}/tournoi/{s}">{e(ed["nom"])} {e(ed["annee"])}</a> <small>{e(t["nb_matchs"].format(n=len(ed["matchs"])))}'
                     f' · {e(date_txt(ed["matchs"][-1]["debut"], L))}</small></li>' for s, ed in eds)
        corps = f"<h1>{e(t['tournois'])}</h1><p class=\"sub\">{e(t['sub_tournois'])}</p><ul class=\"l\">{li}</ul>"
        return page(L, t['titre_tournois'], t['desc_tournois'], '/tournois', corps, og='website')
    sems = sorted(S.semaines, reverse=True)
    li = ''.join(f'<li><a href="{pre(L)}/bilan/{s}">{e(t["semaine"].format(w=int(s.split("-s")[1]), y=s.split("-s")[0]))}</a> '
                 f'<small>{e(t["trouves"].format(k=_trouves(S.semaines[s])[0], n=_trouves(S.semaines[s])[1], p=pc(_trouves(S.semaines[s])[0] / max(1, _trouves(S.semaines[s])[1]), L)))}</small></li>'
                 for s in sems)
    corps = f"<h1>{e(t['bilans'])}</h1><p class=\"sub\">{e(t['sub_bilans'])}</p><ul class=\"l\">{li}</ul>"
    return page(L, t['titre_bilans'], t['desc_bilans'], '/bilans', corps, og='website')


def sitemap(entrees):
    l = ''.join(f"  <url><loc>{e(SITE + c)}</loc><lastmod>{d}</lastmod></url>\n" for c, d in entrees)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{l}</urlset>\n'


def _ecrire(dossier, rel, texte):
    p = os.path.join(dossier, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(texte)


def construire(doc, dossier, maintenant=None, bilans=None, donnees=None):
    """Écrit toutes les pages (deux langues) et le plan du site ; renvoie (matchs, joueurs).
    bilans (après match) et donnees (matchs du jour) : pour la « Performance des joueurs » (paquet 438), facultatifs."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M')
    S = Site(matchs_publiables(doc, maintenant))
    S.bilans = bilans or {}
    S.styles = PJ.styles_connus(S.bilans, donnees)
    S.reperes = PJ.reperes(S.bilans)
    S.a_venir = matchs_a_venir(donnees, {m['uid'] for m in S.matchs}, maintenant)
    jour = maintenant[:10]
    entrees = [('/', jour), ('/methode.html', jour), ('/apropos.html', jour)]
    for L in LANGUES:
        d = dossier if L == 'fr' else os.path.join(dossier, 'en')
        p = pre(L)
        for m in S.matchs:
            _ecrire(d, f"match/{m['uid']}.html", page_match(m, S, L))
            entrees.append((f"{p}/match/{m['uid']}", str(m['debut'])[:10]))
        for m in S.a_venir:                                  # 445 : pages des matchs à venir
            _ecrire(d, f"match/{m['uid']}.html", page_a_venir(m, S, L))
            entrees.append((f"{p}/match/{m['uid']}", jour))
        for n, s in S.slugs_j.items():
            _ecrire(d, f"joueur/{s}.html", page_joueur(n, S, L))
            if S.indexable(n):
                entrees.append((f"{p}/joueur/{s}", str(S.par_joueur[n][0]['debut'])[:10]))
        for s, ed in S.editions.items():
            _ecrire(d, f"tournoi/{s}.html", page_tournoi(s, S, L))
            entrees.append((f"{p}/tournoi/{s}", str(ed['matchs'][0]['debut'])[:10]))
        for sem in S.semaines:
            _ecrire(d, f"bilan/{sem}.html", page_bilan(sem, S, L, maintenant))
            entrees.append((f"{p}/bilan/{sem}", max(str(m['debut'])[:10] for m in S.semaines[sem])))
        for quoi in ('matchs', 'joueurs', 'tournois', 'bilans'):
            _ecrire(d, f"{quoi}.html", page_index(L, quoi, S))
            entrees.append((f"{p}/{quoi}", jour))
    _ecrire(dossier, 'sitemap.xml', sitemap(entrees))
    # 25/11/2026 (paquet 437, Lucas : « accéder à la fiche du joueur en cliquant dessus ») : nom → adresse de sa page,
    # pour que la fiche d'un match relie chaque joueur qui a une page (au moins MIN_MATCHS_JOUEUR matchs publiés).
    _ecrire(dossier, 'joueurs_pages.json', json.dumps(S.slugs_j, ensure_ascii=False, separators=(',', ':'), sort_keys=True))
    # 25/11/2026 (paquet 440) : « L'algo voit-il juste sur ce joueur ? » dans Demande à l'algo — nom → [matchs, % moyen
    # annoncé, victoires, fiabilité du joueur] (les mêmes chiffres que sa page)
    perf = {}
    for n in S.slugs_j:
        x = _perf(S, n)
        if x:
            perf[n] = [x['n'], x['annonce_moyen'], x['victoires'], x['fiabilite']]
    _ecrire(dossier, 'joueurs_perf.json', json.dumps(perf, ensure_ascii=False, separators=(',', ':'), sort_keys=True))
    construire.dernier = {'a_venir': len(S.a_venir), 'matchs': len(S.matchs), 'joueurs': sum(1 for n in S.slugs_j if S.indexable(n)), 'tournois': len(S.editions),
                          'semaines': len(S.semaines), 'adresses': len(entrees)}
    return len(S.matchs), construire.dernier['joueurs']


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    dossier = argv[2] if len(argv) > 2 else os.path.join('_site', 'algo')
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        print('Pages de référencement : résultats absents, rien de construit.')
        return 0
    try:                                                     # 487 : profil de la saison (descriptif)
        PROFILS.update(PSA.profils(racine))
    except Exception as x:  # noqa: BLE001 — jamais bloquant
        print(f'::warning::profils de la saison non lus : {type(x).__name__}')
    construire(doc, dossier, bilans=PJ.lire_bilans(racine), donnees=PJ.lire_donnees(racine))
    x = construire.dernier
    print(f"Pages de référencement : {x['a_venir']} matchs à venir, {x['matchs']} matchs, {x['joueurs']} joueurs, {x['tournois']} tournois, "
          f"{x['semaines']} semaines, en français et en anglais ; {x['adresses']} adresses dans le plan du site")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
