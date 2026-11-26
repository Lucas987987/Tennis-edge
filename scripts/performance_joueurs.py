# -*- coding: utf-8 -*-
"""Performance des joueurs (25/11/2026, paquet 438, Lucas : « un espace Performance des joueurs »).

Pour la page de chaque joueur (scripts/pages_seo.py) : ce que l'algo avait annoncé pour lui, contre ce qui est arrivé.
HISTORIQUE ET DESCRIPTIF : rien ici n'entre dans le modèle ni ne change le % d'un match.

  · fenêtre : ses FENETRE (20) derniers matchs jugés (terminés, vainqueur connu, sans abandon), hors ITF ;
  · probabilité moyenne annoncée pour lui, victoires réelles, écart (réel − attendu, en victoires et en points de %) ;
  · aces et breaks : prévu contre réel, par match (bilans après match), écart moyen et tendance, à côté de l'écart
    moyen de l'algo sur tous les joueurs du même circuit (repère) ;
  · par surface et contre chaque style d'adversaire (catégories internes de styles_descriptifs : style figé au moment
    du match quand il a été gardé, sinon le dernier connu), sur tous ses matchs jugés ;
  · FIABILITÉ DU JOUEUR (0-100) : ses résultats suivent-ils nos % ? z = (victoires − attendues) / écart-type attendu
    (somme des p(1−p)) ; note = 100 × (1 − min(|z|, Z_MAX) / Z_MAX). 100 : exactement comme annoncé ; 0 : il gagne
    (ou perd) bien plus souvent que prévu. Pas de note sous MIN_NOTE matchs ; « provisoire » sous MIN_STABLE.
    Échantillon d'un joueur : petit par nature — la page le dit, et la note ne sert à rien d'autre qu'à l'afficher.
Aucune cote, aucun mot de pari.
"""
import glob
import gzip
import json
import math
import os

FENETRE = 20
# 26/11/2026 (paquet 458, Lucas) : sur 5 à 10 matchs, une note de joueur reflète surtout la chance (« comparer des joueurs
# avec 2 matchs » ne veut rien dire) — note affichée à partir de 20 matchs (avant : 5, provisoire sous 15) ; une
# surface ou un style à partir de 10 matchs (avant : 3). Le critère « joueur peu fiable » de la note du match
# (note_par_match.py) garde 5 matchs : son effet y est appris et ramené vers zéro quand les matchs manquent.
MIN_NOTE = 20
MIN_STABLE = 20
Z_MAX = 2.5
MIN_GROUPE = 10             # en dessous, une surface ou un style est affiché « trop peu de matchs »
STATS = ('aces', 'breaks')
STYLES = ('grand_serveur', 'serveur_attaquant', 'retourneur_pressant', 'contreur', 'equilibre')


def lire_bilans(racine):
    """{uid: {home, away, circuit, prevu: {feuille, styles}, reel: {feuille}}} — seulement ce qui sert ici."""
    out = {}
    for f in sorted(glob.glob(os.path.join(racine, 'simulateur', 'journal_pronostics', 'apres_match', '*.json.gz'))):
        try:
            with gzip.open(f, 'rt', encoding='utf-8') as g:
                d = json.load(g)
        except (OSError, ValueError):
            continue
        for uid, b in (d or {}).items():
            if not isinstance(b, dict):
                continue
            pv, rl = b.get('prevu') or {}, b.get('reel') or {}
            out[uid] = {'home': b.get('home'), 'away': b.get('away'), 'circuit': b.get('circuit'),
                        'prevu': {'feuille': pv.get('feuille'), 'styles': pv.get('styles')},
                        'reel': {'feuille': rl.get('feuille')}}
    return out


def styles_connus(bilans, donnees=None):
    """Dernier style connu de chaque joueur : bilans (figé au match), puis les matchs du jour (donnees.json)."""
    st = {}
    for b in bilans.values():                       # dans l'ordre des jours : le plus récent l'emporte
        for nom, s in zip((b.get('home'), b.get('away')), ((b.get('prevu') or {}).get('styles') or [None, None])):
            if nom and s in STYLES:
                st[nom] = s
    for m in (donnees or {}).get('matchs') or []:
        for j in ((m.get('styles_descriptifs') or {}).get('joueurs')) or []:
            if isinstance(j, dict) and j.get('joueur') and j.get('style') in STYLES:
                st[j['joueur']] = j['style']
    return st


def lire_donnees(racine):
    try:
        with open(os.path.join(racine, 'algo', 'donnees.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _feuilles(b, nom):
    """(prévu, réel) du joueur dans un bilan, ou None."""
    if not b:
        return None
    i = 0 if b.get('home') == nom else 1 if b.get('away') == nom else None
    fp, fr = (b.get('prevu') or {}).get('feuille'), (b.get('reel') or {}).get('feuille')
    if i is None or not isinstance(fp, list) or not isinstance(fr, list) or len(fp) < 2 or len(fr) < 2:
        return None
    return fp[i] or {}, fr[i] or {}


def reperes(bilans):
    """Écart moyen |prévu − réel| de l'algo sur tous les joueurs, par circuit et par statistique."""
    acc = {}
    for b in bilans.values():
        for nom in (b.get('home'), b.get('away')):
            x = _feuilles(b, nom)
            if not x:
                continue
            for k in STATS:
                if isinstance(x[0].get(k), (int, float)) and isinstance(x[1].get(k), (int, float)):
                    a = acc.setdefault((b.get('circuit'), k), [0.0, 0])
                    a[0] += abs(x[0][k] - x[1][k])
                    a[1] += 1
    return {c: round(s / n, 2) for c, (s, n) in acc.items() if n >= 30}


def _groupe(lignes):
    n = len(lignes)
    if not n:
        return None
    v = sum(y for _, y in lignes)
    return {'n': n, 'v': v, 'annonce': round(sum(p for p, _ in lignes) / n, 4), 'reel': round(v / n, 4)}


def note_fiabilite(lignes, min_n=None):
    """lignes : [(p annoncé pour le joueur, 1 si victoire)]. → (note 0-100, z) ou (None, None).
    min_n : minimum de matchs (par défaut MIN_NOTE ; note_par_match.py passe le sien)."""
    if len(lignes) < (MIN_NOTE if min_n is None else min_n):
        return None, None
    att = sum(p for p, _ in lignes)
    var = sum(p * (1 - p) for p, _ in lignes)
    if var <= 0:
        return None, None
    z = (sum(y for _, y in lignes) - att) / math.sqrt(var)
    return int(round(100 * (1 - min(abs(z), Z_MAX) / Z_MAX))), round(z, 2)


def performance(nom, matchs, p_pour, bilans, styles, reps):
    """matchs : ses matchs publiés (du plus récent au plus ancien) ; p_pour(m) : % annoncé pour lui (0-1)."""
    jug = [m for m in matchs if not (m.get('reel') or {}).get('interrompu') and (m.get('reel') or {}).get('gagnant') in ('home', 'away')]
    if not jug:
        return None
    gagne = lambda m: (m['reel']['gagnant'] == 'home') == (m['home'] == nom)  # noqa: E731
    der = jug[:FENETRE]
    L = [(p_pour(m), 1 if gagne(m) else 0) for m in der]
    n = len(L)
    att = sum(p for p, _ in L)
    v = sum(y for _, y in L)
    note, z = note_fiabilite(L)
    out = {'n': n, 'annonce_moyen': round(att / n, 4), 'victoires': v, 'attendues': round(att, 1),
           'ecart_victoires': round(v - att, 1), 'ecart_pts': round(100 * (v - att) / n, 1),
           'fiabilite': note, 'z': z, 'provisoire': note is not None and n < MIN_STABLE, 'stats': {}}
    circ = (der[0].get('circuit') if der else None)
    for k in STATS:
        ecarts = []
        for m in der:
            x = _feuilles(bilans.get(m.get('uid')), nom)
            if x and isinstance(x[0].get(k), (int, float)) and isinstance(x[1].get(k), (int, float)):
                ecarts.append((x[0][k], x[1][k]))
        if ecarts:
            out['stats'][k] = {'n': len(ecarts), 'prevu': round(sum(a for a, _ in ecarts) / len(ecarts), 1),
                               'reel': round(sum(b for _, b in ecarts) / len(ecarts), 1),
                               'ecart_moyen': round(sum(abs(a - b) for a, b in ecarts) / len(ecarts), 1),
                               'repere': reps.get((circ, k))}
    surf, sty = {}, {}
    for m in jug:
        ligne = (p_pour(m), 1 if gagne(m) else 0)
        if m.get('surface'):                       # surface inconnue : pas de ligne « — »
            surf.setdefault(m['surface'], []).append(ligne)
        adv = m['away'] if m['home'] == nom else m['home']
        s = _style_au_match(bilans.get(m.get('uid')), adv) or styles.get(adv)
        if s in STYLES:
            sty.setdefault(s, []).append(ligne)
    out['surfaces'] = {k: _groupe(x) for k, x in sorted(surf.items(), key=lambda kv: -len(kv[1]))}
    out['styles'] = {k: _groupe(sty[k]) for k in STYLES if k in sty}
    out['n_tous'] = len(jug)
    return out


def _style_au_match(b, adv):
    if not b:
        return None
    st = (b.get('prevu') or {}).get('styles') or [None, None]
    return st[0] if b.get('home') == adv else st[1] if b.get('away') == adv else None
