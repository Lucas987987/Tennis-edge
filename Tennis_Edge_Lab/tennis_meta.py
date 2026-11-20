#!/usr/bin/env python3
"""Métadonnées tennis partagées (V6.7) : circuit, niveau, surface, tranches.

Un seul endroit pour ces conventions, utilisé par l'explorateur et la
stabilité 16 ans. Aucune donnée réseau.
"""
from __future__ import annotations

import collections
import csv
import gzip
import pathlib
import re
import unicodedata

GRAND_SLAM_KEYS = ("australian open", "french open", "roland garros", "wimbledon", "us open")
THOUSAND_KEYS = (
    "bnp paribas open", "indian wells", "miami open", "sony ericsson open",
    "monte carlo masters", "mutua madrid open", "madrid open", "internazionali bnl",
    "italian open", "rogers masters", "canadian open", "rogers cup", "national bank open",
    "western & southern", "cincinnati", "shanghai masters", "bnp paribas masters",
    "paris masters",
)
# Tranches de cote : identiques à history_stability.py.
ODDS_BANDS = ((1.01, 1.30), (1.30, 1.60), (1.60, 2.00), (2.00, 2.50),
              (2.50, 3.20), (3.20, 5.00), (5.00, None))
LEAD_BANDS = ((0, 30, "< 30 min"), (30, 90, "30–90 min"), (90, 180, "1h30–3h"),
              (180, 480, "3–8 h"), (480, 1440, "8–24 h"), (1440, None, "> 24 h"))
PIN_MOVE_BANDS = ((-1e9, -5, "≤ −5 %"), (-5, -2, "−5 à −2 %"), (-2, 0, "−2 à 0 %"),
                  (0, 2, "0 à +2 %"), (2, None, "≥ +2 %"))
MOVE_BANDS = ((0, 2, "< 2 pts"), (2, 3, "2–3 pts"), (3, 5, "3–5 pts"), (5, 8, "5–8 pts"),
              (8, None, "≥ 8 pts"))

# Table manuelle pour nos noms de tournois (OddsPapi). Challengers : seulement
# lorsque la surface est connue avec assurance ; sinon « inconnue ».
HAND_SURFACES = {
    "shanghai": "Hard", "beijing": "Hard", "wuhan": "Hard", "cincinnati": "Hard",
    "toronto": "Hard", "montreal": "Hard", "winston salem": "Hard", "washington": "Hard",
    "tokyo": "Hard", "chengdu": "Hard", "hangzhou": "Hard", "seoul": "Hard",
    "monterrey": "Hard", "guadalajara": "Hard", "memphis": "Hard", "singapore": "Hard",
    "los cabos": "Hard", "sao paulo": "Hard", "us open": "Hard", "wimbledon": "Grass",
    "french open": "Clay", "hamburg": "Clay", "estoril": "Clay", "kitzbuhel": "Clay",
    "prague": "Clay", "stuttgart": "Grass", "halle": "Grass", "london": "Grass",
    "eastbourne": "Grass", "nottingham": "Grass", "s hertogenbosch": "Grass",
    "mallorca": "Grass", "bad homburg": "Grass", "berlin": "Grass",
    # Challengers (table manuelle, à vérifier si nécessaire)
    "challenger palermo": "Clay", "challenger genoa": "Clay", "challenger seville": "Clay",
    "challenger szczecin": "Clay", "challenger braga": "Clay", "challenger tulln": "Clay",
    "challenger augsburg": "Clay", "challenger como": "Clay", "challenger prague": "Clay",
    "challenger sion": "Clay", "challenger buenos aires": "Clay", "challenger curitiba": "Clay",
    "challenger antofagasta": "Clay", "challenger santa cruz": "Clay", "challenger plovdiv": "Clay",
    "challenger catania": "Clay", "challenger roehampton": "Grass",
    "challenger rennes": "Hard", "challenger roanne": "Hard", "challenger mouilleron le captif": "Hard",
    "challenger columbus": "Hard", "challenger quebec city": "Hard", "challenger san diego": "Hard",
    "challenger tiburon": "Hard", "challenger shanghai": "Hard", "challenger guangzhou": "Hard",
    "challenger jinan": "Hard", "challenger phan thiet": "Hard", "challenger cancun": "Hard",
    "challenger istanbul": "Hard", "challenger saint tropez": "Hard", "challenger olbia": "Hard",
    "challenger cassis": "Hard", "challenger manacor": "Hard", "challenger zhangjiagang": "Hard",
    "challenger wuning": "Hard", "challenger jingshan": "Hard", "challenger villena": "Hard",
}


def norm_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def band(value, bands):
    if value is None:
        return "inconnu"
    for low, high, label in bands:
        if value >= low and (high is None or value < high):
            return label
    return "inconnu"


def odds_band(odds) -> str:
    if odds is None:
        return "inconnue"
    for low, high in ODDS_BANDS:
        if odds >= low and (high is None or odds < high):
            return (f"{low:.2f}–{high:.2f}" if high else f"≥ {low:.2f}").replace(".", ",")
    return "inconnue"


def level_of(tournament: str) -> str:
    name = str(tournament or "").lower()
    if any(slam in name for slam in GRAND_SLAM_KEYS):
        return "Grand Chelem"
    if any(item in name for item in THOUSAND_KEYS):
        return "1000"
    return "Autre"


def circuit_of(tournament: str) -> str:
    """Challenger / ATP / WTA / Grand Chelem / Autre (nom de tournoi OddsPapi)."""
    name = str(tournament or "").lower()
    if "challenger" in name:
        return "Challenger"
    if any(slam in name for slam in GRAND_SLAM_KEYS):
        return "Grand Chelem"
    if name.startswith("atp") or " atp " in f" {name} ":
        return "ATP"
    if name.startswith("wta") or " wta " in f" {name} ":
        return "WTA"
    return "Autre"


def _place(tournament: str) -> str:
    text = norm_text(tournament)
    text = re.sub(r"\b(atp|wta|men|women|singles|ii|iii|\d+)\b", " ", text)
    text = re.sub(r"\(.*?\)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class SurfaceMap:
    """Tournoi -> surface : table manuelle, puis tennis-data (nom contenant la ville)."""

    def __init__(self, history_path: pathlib.Path | None = None):
        self.history = collections.defaultdict(collections.Counter)
        if history_path and pathlib.Path(history_path).is_file():
            with gzip.open(history_path, "rt", encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    if str(row.get("date", ""))[:4] >= "2018" and row.get("surface"):
                        self.history[norm_text(row.get("tournoi"))][row["surface"].capitalize()] += 1

    def lookup(self, tournament: str) -> tuple[str, str]:
        place = _place(tournament)
        if not place:
            return "inconnue", "aucune"
        challenger = "challenger" in place
        for key, surface in HAND_SURFACES.items():
            if (key.startswith("challenger") == challenger) and (place == key or place.startswith(key + " ") or (not challenger and key in place)):
                return surface, "table manuelle"
        if challenger:
            return "inconnue", "aucune"
        city = place.split(" ")[0] if place else ""
        votes = collections.Counter()
        for name, counter in self.history.items():
            if place and (place in name or (len(city) > 4 and city in name.split())):
                votes.update(counter)
        if votes:
            return votes.most_common(1)[0][0], "tennis-data"
        return "inconnue", "aucune"
