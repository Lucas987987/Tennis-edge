#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
densite_air.py — densité de l'air pendant un match (05/11/2026).

Une balle va plus vite et rebondit plus haut dans un air léger : en altitude, par la chaleur,
par l'humidité (la vapeur d'eau est plus légère que l'air sec). On s'attend donc à plus d'aces
et à plus de points gagnés au service quand l'air est léger.

Densité (kg/m³) = air sec + vapeur d'eau, à partir de la pression (hPa), de la température (°C)
et de l'humidité relative (%), formule de Tetens pour la vapeur saturante.

  — plein air : moyennes de 11 h à 20 h, heure locale (scripts/lieux_tournois.py, Open-Meteo) ;
  — salle : même pression qu'à l'extérieur (le toit ne change pas la pression), mais 20 °C et 50 % ;
  — pas de relevé : pression déduite de l'altitude (atmosphère standard), 20 °C, 50 % ;
  — lieu inconnu : neutre.

Variable des facteurs : air_leger = (1,20 − densité) / 0,10. Niveau de la mer, 20 °C : ≈ 0 ;
Bogota (2 640 m) : ≈ +3,3 ; Quito (2 850 m) : ≈ +3,6 ; 32 °C au bord de la mer : ≈ +0,55.
"""
import datetime as dt
import math

RHO_REF = 1.20
ECHELLE = 0.10
T_SALLE, RH_SALLE = 20.0, 50.0


def pression_altitude(alt_m):
    """Pression standard (hPa) à cette altitude."""
    return 1013.25 * (1.0 - 2.25577e-5 * max(float(alt_m or 0.0), -400.0)) ** 5.25588


def densite(p_hpa, t_c, rh_pct):
    """Densité de l'air humide (kg/m³)."""
    t_k = t_c + 273.15
    es = 6.1078 * 10 ** (7.5 * t_c / (t_c + 237.3))
    pv = max(0.0, min(100.0, rh_pct)) / 100.0 * es
    pd = p_hpa - pv
    return (pd * 100.0) / (287.058 * t_k) + (pv * 100.0) / (461.495 * t_k)


def densite_match(lieu, met, interieur):
    """Densité pour un tournoi (dict de tournois.json) et un relevé du jour (liste de meteo.json) ; None si lieu inconnu."""
    lieu = lieu or {}
    if lieu.get('lat') is None:
        return None
    p = t = rh = None
    if met and len(met) >= 6:
        p, t, rh = met[3], met[4], met[5]
    if p is None:
        p = pression_altitude(lieu.get('altitude'))
    if interieur or t is None or rh is None:
        t, rh = T_SALLE, RH_SALLE
    return densite(float(p), float(t), float(rh))


def air_leger(lieu, met, interieur):
    """Variable des facteurs : 0 au niveau de la mer à 20 °C, positive quand l'air est plus léger ; 0 si lieu inconnu."""
    r = densite_match(lieu, met, interieur)
    return 0.0 if r is None or not math.isfinite(r) else (RHO_REF - r) / ECHELLE


def jour_local(ts, lon):
    """Jour du match à l'heure solaire du lieu (longitude / 15 h), pour lire la météo du bon jour (paquet 191)."""
    return dt.datetime.fromtimestamp(ts + (lon or 0.0) / 15.0 * 3600, dt.timezone.utc).date().isoformat()
