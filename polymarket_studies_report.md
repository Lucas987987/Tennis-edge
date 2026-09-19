# Études Polymarket/Kalshi — rapport du 2026-09-19

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1431065 ticks lus, 486 match(s) avec série 'match'
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_leadlag.py EN ÉCHEC (code 1)

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1431065 ticks lus · 483 match(s) exploitables (fourchette max 10 pts)
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_studies.py EN ÉCHEC (code 1)

--- pm_calibration_track ---
ResultIndex : 2454 résultats · 2405 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 272 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        66     37.3%     30.3%    -7.0  [ -16.8 ;   +4.9]
                        il faudrait ~182 obs pour trancher à cet écart (116 manquantes)
  55 – 70 %        67     62.5%     68.7%    +6.1  [  -5.7 ;  +16.0]
                        il faudrait ~241 obs pour trancher à cet écart (174 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 570 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       138     37.6%     34.1%    -3.6  [ -10.9 ;   +4.7]
                        il faudrait ~714 obs pour trancher à cet écart (576 manquantes)
  55 – 70 %       138     62.2%     64.5%    +2.2  [  -6.0 ;   +9.7]
                        il faudrait ~1784 obs pour trancher à cet écart (1646 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2454 résultats · 2405 paires · fenêtre ±5 j
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: pm_observations.py EN ÉCHEC (code 1)

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  813 observation(s) construite(s) · 190 nouvelle(s) · 5107 au journal kalshi_lead_obs.jsonl

```
