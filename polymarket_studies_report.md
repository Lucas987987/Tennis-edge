# Études Polymarket/Kalshi — rapport du 2026-09-16

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1512201 ticks lus, 537 match(s) avec série 'match'
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_leadlag.py EN ÉCHEC (code 1)

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1512201 ticks lus · 536 match(s) exploitables (fourchette max 10 pts)
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_studies.py EN ÉCHEC (code 1)

--- pm_calibration_track ---
ResultIndex : 2357 résultats · 2310 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 150 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        32     37.4%     28.1%    -9.3  [ -21.8 ;   +8.0]
                        il faudrait ~105 obs pour trancher à cet écart (73 manquantes)
  55 – 70 %        32     62.6%     71.9%    +9.3  [  -8.0 ;  +21.8]
                        il faudrait ~105 obs pour trancher à cet écart (73 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 360 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        86     37.2%     32.6%    -4.7  [ -13.6 ;   +5.8]
                        il faudrait ~414 obs pour trancher à cet écart (328 manquantes)
  55 – 70 %        86     62.7%     66.3%    +3.5  [  -7.0 ;  +12.6]
                        il faudrait ~717 obs pour trancher à cet écart (631 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2357 résultats · 2310 paires · fenêtre ±5 j
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
  964 observation(s) construite(s) · 440 nouvelle(s) · 4169 au journal kalshi_lead_obs.jsonl

```
