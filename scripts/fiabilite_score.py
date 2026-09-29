#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fiabilite_score.py — Note de fiabilité par pari (créée le 26/08/2026).

MODE OMBRE UNIQUEMENT. Cette note ne pilote AUCUNE mise réelle. Elle se
calcule et se journalise à chaque entrée pour qu'on puisse, dans quelques
semaines, juger PROPREMENT si elle mérite de servir au sizing — exactement
comme les 8 pistes gelées de ce week-end.

POURQUOI EN OMBRE ET PAS EN DIRECT. Ses composants viennent de pistes
EXPLORATOIRES d'hier soir (ampleur du move, timing, book en retard) — aucune
n'est confirmée out-of-sample. Composer plusieurs signaux non prouvés en un
seul score, c'est empiler du surapprentissage sur du surapprentissage : si
chaque brique a une petite chance d'être du bruit, leur combinaison a une
chance plus grande encore de sembler "marcher" par hasard sur l'historique
qui a servi à les repérer. D'où la règle : le score est journalisé dès
maintenant, mais jugé UNIQUEMENT sur les paris ouverts APRÈS ce gel — jamais
rejoué sur l'historique existant.

COMPOSANTS (additifs, simples, JAMAIS un modèle ajusté — même discipline que
"univarié seulement" des pistes). Chacun n'utilise QUE de l'information
disponible AU MOMENT DU PARI (aucun look-ahead) :
  +1  ampleur du move >= 6 % (piste 5 : les moves 6-12% referment mieux)
  -1  ampleur du move <  3 % (piste 5 : 46% de retournement)
  -1  détecté à < 60 min du coup d'envoi (piste 5 : 69% de retournement)
  +1  book identifié "en retard" à ce palier (canal_public, ligne 🏪ᵀ)
  +1  book absent du classement "rapide" de la cascade (piste 4, si dispo,
      sinon composant neutre — la piste elle-même n'est pas confirmée)
Score final : entre -3 et +3. AUCUN poids n'est appris sur des données —
chaque composant vaut 1 point, point.

USAGE : fiabilite(alerte: dict, book_lent: bool) -> int
"""
import os


def fiabilite(mag_pct, lead_min, book_en_retard=False, book_lent_confirme=None):
    """Calcule la note à partir d'infos connues à l'instant du pari.

    mag_pct       : amplitude du move en points (ex: 7.2)
    lead_min      : minutes avant le coup d'envoi au moment de la détection
    book_en_retard: le book d'entrée est-il encore en retard sur ce move ?
                    (déjà calculé par canal_public.py — voir sa ligne 🏪)
    book_lent_confirme : None (info non dispo -> neutre), True (le book
                    N'EST PAS dans le tiers rapide de la cascade), False
                    (le book EST dans le tiers rapide).
    """
    score = 0
    if mag_pct is not None:
        if mag_pct >= 6:
            score += 1
        elif mag_pct < 3:
            score -= 1
    if lead_min is not None and lead_min < 60:
        score -= 1
    if book_en_retard:
        score += 1
    if book_lent_confirme is True:
        score += 1
    return max(-3, min(3, score))


def explique(mag_pct, lead_min, book_en_retard=False, book_lent_confirme=None):
    """Version verbeuse pour le journal — traçabilité totale du calcul."""
    bouts = []
    if mag_pct is not None:
        if mag_pct >= 6:
            bouts.append('+1 ampleur>=6%')
        elif mag_pct < 3:
            bouts.append('-1 ampleur<3%')
    if lead_min is not None and lead_min < 60:
        bouts.append('-1 lead<60min')
    if book_en_retard:
        bouts.append('+1 book_en_retard')
    if book_lent_confirme is True:
        bouts.append('+1 book_hors_tiers_rapide')
    s = fiabilite(mag_pct, lead_min, book_en_retard, book_lent_confirme)
    return s, (' '.join(bouts) or 'aucun composant applicable')
