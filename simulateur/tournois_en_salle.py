#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tournois_en_salle.py — quels tournois de l'ARCHIVE se jouent en salle (12/11/2026, audit, paquet 238)

L'archive Sackmann donne la surface (dur, terre, gazon) mais pas « en salle ». Cette table l'ajoute pour l'ATP et la
WTA, de 2019 à juin 2026. Elle a été écrite à partir du calendrier des circuits — le nom du tournoi, son mois, sa
surface — SANS regarder un seul résultat ni une seule statistique. Elle ne sert qu'aux ÉTUDES : en production, « en
salle » vient de la feuille du match (surface « Hardcourt indoor »), pas de cette table.

Trois réponses : True (en salle), False (plein air), None (inconnu : Challenger, ITF, ou tournoi douteux écarté).
Un nom de tournoi qui a changé de surface selon les années est tranché par la surface (Belgrade, Linz, Budapest).
"""

# nom du tournoi dans l'archive → surfaces pour lesquelles il se joue en salle
SALLE = {
    'ATP': {
        'Almaty': ('Hard',), 'Antwerp': ('Hard',), 'Astana': ('Hard',), 'Athens': ('Hard',), 'Basel': ('Hard',),
        'Belgrade': ('Hard',), 'Brussels': ('Hard',), 'Cologne 1': ('Hard',), 'Cologne 2': ('Hard',), 'Dallas': ('Hard',),
        'Florence': ('Hard',), 'Gijon': ('Hard',), 'Laver Cup': ('Hard',), 'Marseille': ('Hard',), 'Metz': ('Hard',),
        'Montpellier': ('Hard',), 'Moscow': ('Hard',), 'New York': ('Hard',), 'Next Gen Finals': ('Hard',),
        'NextGen Finals': ('Hard',), 'Nur-Sultan': ('Hard',), 'Paris Masters': ('Hard',), 'Rotterdam': ('Hard',),
        'Singapore': ('Hard',), 'Sofia': ('Hard',), 'St Petersburg': ('Hard',), 'St. Petersburg': ('Hard',),
        'Stockholm': ('Hard',), 'Tel Aviv': ('Hard',), 'Tour Finals': ('Hard',), 'Vienna': ('Hard',),
    },
    'WTA': {
        'Budapest': ('Hard',), 'Cluj Napoca': ('Hard',), 'Cluj-Napoca': ('Hard',), 'Cluj-Napoca 2': ('Hard',),
        'Courmayeur': ('Hard',), 'Fort Worth Finals': ('Hard',), 'Limoges': ('Hard',), 'Linz': ('Hard',),
        'Luxembourg': ('Hard',), 'Lyon': ('Hard',), 'Moscow': ('Hard',), 'Nur-Sultan': ('Hard',), 'Ostrava': ('Hard',),
        'Riyadh Finals': ('Hard',), 'Rouen': ('Clay',), 'Shenzhen Finals': ('Hard',), 'St. Petersburg': ('Hard',),
        'Stuttgart': ('Clay',), 'Tallinn': ('Hard',),
    },
}
# tournois dont je ne suis pas sûr (toit, salle selon l'édition) : écartés des deux groupes
INCERTAINS = {
    'ATP': ('Tokyo', 'Antalya'),
    'WTA': ('Zhuhai', 'Singapore', 'Tokyo', 'W50+H Macon', 'W35+H Tauste', 'W50+H Palma del Río'),
}
CIRCUITS = tuple(SALLE)


def en_salle(circuit, tournoi, surface):
    """True : en salle ; False : plein air ; None : inconnu (autre circuit, tournoi douteux, nom vide)."""
    if circuit not in SALLE or not tournoi:
        return None
    nom = str(tournoi).strip()
    if nom in INCERTAINS.get(circuit, ()):
        return None
    return surface in SALLE[circuit].get(nom, ())
