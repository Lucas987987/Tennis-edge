"""Stabilité Monte Carlo du score exact modal, sans modifier le pronostic.

La simulation de référence reste celle qui produit toutes les sorties publiques.
Des blocs indépendants, avec des graines distinctes, vérifient si le même score
serait encore modal. Aucun bloc de contrôle ne choisit ou ne remplace le scénario.
"""
import match_simule as MS

ECART_MIN = .002          # 0,2 point de pourcentage entre les deux premiers scores
ETENDUE_MAX = .01         # 1 point entre les fréquences minimale et maximale du modal


def _bloc(r, nom):
    scores = r.get('scores') or []
    modal, frequence = scores[0] if scores else (None, None)
    ecart = frequence - scores[1][1] if len(scores) > 1 else None
    return {'bloc': nom, 'score_modal': modal, 'frequence': frequence,
            'ecart_avec_deuxieme': round(ecart, 4) if ecart is not None else None,
            'top3': scores[:3]}


def synthetiser(reference, controles):
    """Diagnostic de la référence et de ses blocs ; ne renvoie aucune nouvelle prévision."""
    blocs = [_bloc(reference, 'reference')] + [_bloc(r, f'controle_{i+1}') for i, r in enumerate(controles)]
    score = blocs[0]['score_modal']
    memes = [b for b in blocs if b['score_modal'] == score]
    frequences = [b['frequence'] for b in memes if b['frequence'] is not None]
    ecarts = [b['ecart_avec_deuxieme'] for b in blocs if b['ecart_avec_deuxieme'] is not None]
    etendue = max(frequences) - min(frequences) if frequences else None
    if not controles or score is None:
        statut = 'non_controle'
    elif len(memes) != len(blocs):
        statut = 'instable'
    elif min(ecarts) < ECART_MIN or etendue > ETENDUE_MAX:
        statut = 'fragile'
    else:
        statut = 'stable'
    return {
        'statut': statut, 'score_reference': score,
        'n_par_bloc': reference.get('n'), 'blocs_controle': len(controles),
        'accord_modal': round(len(memes) / len(blocs), 4) if blocs else None,
        'etendue_frequence_score_reference': round(etendue, 4) if etendue is not None else None,
        'ecart_top2_min': round(min(ecarts), 4) if ecarts else None,
        'blocs': blocs,
        'regle': (f"stable = même modal partout, écart top 1/top 2 >= {ECART_MIN} et étendue des fréquences "
                  f"<= {ETENDUE_MAX} ; instable = au moins un modal différent ; fragile sinon."),
        'action': 'Diagnostic seulement : ni hausse automatique des tirages ni changement du score publié.',
    }


def controler(cA, cB, p_victoire, reference, sets_gagnants=2, n=20000, sigma=.15,
              cle='', tb_final=None, reglages=None, blocs=2):
    """Exécute des blocs réellement indépendants de la simulation de référence."""
    controles = []
    for i in range(max(0, int(blocs))):
        controles.append(MS.simuler(cA, cB, p_victoire, sets_gagnants, n, sigma,
                                    f'{cle}|stabilite|{i+1}', tb_final, False, reglages))
    return synthetiser(reference, controles)
