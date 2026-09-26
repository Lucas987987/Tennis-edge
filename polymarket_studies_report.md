# Études Polymarket/Kalshi — rapport du 2026-09-26

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1520536 ticks lus, 450 match(s) avec série 'match'
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_leadlag.py EN ÉCHEC (code 1)

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1520536 ticks lus · 448 match(s) exploitables (fourchette max 10 pts)
❌ rebuild(match) : AUCUNE partition parts/live_match_*.jsonl.
   Le fichier plat serait vide et le pipeline tournerait sur
   des courbes inexistantes sans le signaler. Arrêt.
   Causes usuelles : cache non restauré, checkout partiel,
   purge trop agressive (LIVE_DAYS).
   Si le vide est légitime (1er démarrage) : AUTORISER_VIDE=1.
PMSTUDY_FAIL: polymarket_studies.py EN ÉCHEC (code 1)

--- pm_calibration_track ---
ResultIndex : 2777 résultats · 2709 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 290 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        77     37.4%     41.6%    +4.2  [  -6.2 ;  +15.3]
                        il faudrait ~515 obs pour trancher à cet écart (438 manquantes)
  55 – 70 %        78     62.5%     57.7%    -4.8  [ -15.9 ;   +5.5]
                        il faudrait ~386 obs pour trancher à cet écart (308 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 550 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       137     37.8%     41.6%    +3.8  [  -4.1 ;  +12.2]
                        il faudrait ~626 obs pour trancher à cet écart (489 manquantes)
  55 – 70 %       140     62.2%     57.9%    -4.3  [ -12.6 ;   +3.5]
                        il faudrait ~483 obs pour trancher à cet écart (343 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2777 résultats · 2709 paires · fenêtre ±5 j
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
  2009 observation(s) construite(s) · 418 nouvelle(s) · 8075 au journal kalshi_lead_obs.jsonl

```
