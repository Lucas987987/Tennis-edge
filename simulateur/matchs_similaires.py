"""Voisinage pré-match d'un pronostic, sans cote, résultat futur ni sélection par ROI.

Les distances utilisent uniquement les sorties et métadonnées figées avant le match.
L'historique doit être résolu et antérieur au début de la cible. Le résultat des voisins
n'est lu qu'après leur sélection, pour produire un contrôle descriptif de calibration.
"""
import datetime as dt
import math

CIRCUITS = ('ATP', 'WTA', 'CH', 'ITF', 'ITFH')
SURFACES = ('Hard', 'Clay', 'Grass')
K_DEFAUT = 150
MIN_VOISINS = 30


def _p(v):
    return min(max(float(v), 1e-6), 1 - 1e-6)


def _bloc(m, nom):
    return (m.get(nom) or (m.get('premier') or {}).get(nom) or {})


def _debut(m):
    return dt.datetime.fromisoformat(str(m['debut']).replace('Z', '+00:00'))


def vecteur(m):
    """Caractéristiques connues avant le coup d'envoi ; aucune variable de marché."""
    elo, sim = _bloc(m, 'stats'), _bloc(m, 'simulation')
    comb = _bloc(m, 'combinaison') or sim or elo
    pe = elo.get('p_home')
    ps = sim.get('p_home')
    pc = comb.get('p_home')
    if pc is None:
        return None
    pe, ps, pc = float(pe if pe is not None else pc), float(ps if ps is not None else pc), _p(pc)
    experience = m.get('matchs_joues') or [0, 0]
    connu = (comb.get('match_simule') or {}).get('profil_connu') or m.get('style_connu') or [False, False]
    documentation = sum(.5 * bool(c) + .5 * min(float(n or 0) / 30, 1)
                        for c, n in zip(connu, experience)) / 2
    circuit = m.get('circuit') if m.get('circuit') in CIRCUITS else '?'
    surface = m.get('surface') if m.get('surface') in SURFACES else '?'
    return {'p': pc, 'elo': pe, 'simulation': ps,
            'ecart': pe - ps, 'desaccord': float((pe >= .5) != (ps >= .5)),
            'documentation': documentation, 'circuit': circuit, 'surface': surface,
            'bo': int(m.get('meilleur_des') or m.get('bo') or 3)}


def distance(a, b):
    """Distance fixée avant l'étude ; les résultats historiques n'y entrent pas."""
    if a['circuit'] != '?' and b['circuit'] != '?' and a['circuit'] != b['circuit']:
        return math.inf
    d = 2.0 * abs(a['p'] - b['p'])
    d += .55 * abs(a['elo'] - b['elo']) + .55 * abs(a['simulation'] - b['simulation'])
    d += .80 * abs(a['ecart'] - b['ecart']) + .70 * abs(a['desaccord'] - b['desaccord'])
    d += .55 * abs(a['documentation'] - b['documentation'])
    d += .35 * (a['surface'] != b['surface']) + .30 * (a['bo'] != b['bo'])
    return d


def selectionner(cible, historique, k=K_DEFAUT):
    """Retourne les voisins sans consulter leurs résultats dans la fonction de distance."""
    if not cible.get('debut'):
        raise ValueError('La date de début de la cible est obligatoire pour éviter toute fuite.')
    vc = vecteur(cible)
    if vc is None:
        return []
    debut = _debut(cible)
    candidats = []
    for m in historique or []:
        reel = m.get('reel') or {}
        if (m.get('uid') == cible.get('uid') or not m.get('debut') or _debut(m) >= debut
                or reel.get('interrompu') or reel.get('gagnant') not in ('home', 'away')):
            continue
        v = vecteur(m)
        if v is None:
            continue
        d = distance(vc, v)
        if math.isfinite(d):
            candidats.append((d, str(m.get('uid')), m, v))
    candidats.sort(key=lambda x: (x[0], x[1]))
    return [{'distance': d, 'match': m, 'vecteur': v} for d, _, m, v in candidats[:max(0, int(k))]]


def resumer(cible, historique, k=K_DEFAUT):
    voisins = selectionner(cible, historique, k)
    if not voisins:
        return {'n': 0, 'statut': 'insuffisant', 'regle': 'matchs antérieurs seulement ; aucun marché ni ROI'}
    poids = [1 / (.03 + v['distance']) for v in voisins]
    total = sum(poids)
    prevu = sum(w * v['vecteur']['p'] for w, v in zip(poids, voisins)) / total
    reel = sum(w * int(v['match']['reel']['gagnant'] == 'home') for w, v in zip(poids, voisins)) / total
    pertes = [-math.log(_p(v['vecteur']['p'] if v['match']['reel']['gagnant'] == 'home'
                           else 1-v['vecteur']['p'])) for v in voisins]
    return {'n': len(voisins), 'n_effectif': round(total, 2),
            'statut': 'descriptif' if len(voisins) >= MIN_VOISINS else 'insuffisant',
            'probabilite_home_moyenne': round(prevu, 5), 'reussite_home': round(reel, 5),
            'ecart_reel_moins_prevu': round(reel-prevu, 5),
            'log_loss_voisins': round(sum(pertes)/len(pertes), 6),
            'distance_mediane': round(sorted(v['distance'] for v in voisins)[len(voisins)//2], 5),
            'regle': 'voisins choisis sur caractéristiques pré-match ; résultats lus après sélection ; aucun ROI'}
