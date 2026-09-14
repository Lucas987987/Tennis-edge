# Études Polymarket/Kalshi — rapport du 2026-09-14

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1447674 ticks lus, 556 match(s) avec série 'match'
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_leadlag.py EN ÉCHEC (code 1)

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1447674 ticks lus · 552 match(s) exploitables (fourchette max 10 pts)
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_studies.py EN ÉCHEC (code 1)

--- pm_calibration_track ---
ResultIndex : 2206 résultats · 2162 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 180 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        41     37.7%     31.7%    -6.0  [ -18.1 ;   +9.3]
                        il faudrait ~255 obs pour trancher à cet écart (214 manquantes)
  55 – 70 %        41     62.3%     68.3%    +6.0  [  -9.3 ;  +18.1]
                        il faudrait ~255 obs pour trancher à cet écart (214 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 468 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       107     37.2%     32.7%    -4.5  [ -12.6 ;   +4.9]
                        il faudrait ~451 obs pour trancher à cet écart (344 manquantes)
  55 – 70 %       104     62.7%     65.4%    +2.6  [  -6.9 ;  +11.1]
                        il faudrait ~1280 obs pour trancher à cet écart (1176 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2206 résultats · 2162 paires · fenêtre ±5 j
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
  996 observation(s) construite(s) · 544 nouvelle(s) · 3220 au journal kalshi_lead_obs.jsonl

```
