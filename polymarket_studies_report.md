# Études Polymarket/Kalshi — rapport du 2026-09-24

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1364976 ticks lus, 422 match(s) avec série 'match'
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_leadlag.py EN ÉCHEC (code 1)

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1364976 ticks lus · 419 match(s) exploitables (fourchette max 10 pts)
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_studies.py EN ÉCHEC (code 1)

--- pm_calibration_track ---
ResultIndex : 2703 résultats · 2641 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 278 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        70     37.2%     34.3%    -3.0  [ -13.0 ;   +8.7]
                        il faudrait ~1027 obs pour trancher à cet écart (957 manquantes)
  55 – 70 %        71     62.6%     64.8%    +2.1  [  -9.5 ;  +12.2]
                        il faudrait ~1962 obs pour trancher à cet écart (1891 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 472 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       109     37.6%     41.3%    +3.7  [  -5.1 ;  +13.0]
                        il faudrait ~677 obs pour trancher à cet écart (568 manquantes)
  55 – 70 %       109     62.3%     57.8%    -4.5  [ -13.9 ;   +4.4]
                        il faudrait ~452 obs pour trancher à cet écart (343 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2703 résultats · 2641 paires · fenêtre ±5 j
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
  1389 observation(s) construite(s) · 580 nouvelle(s) · 7139 au journal kalshi_lead_obs.jsonl

```
