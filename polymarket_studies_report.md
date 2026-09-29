# Études Polymarket/Kalshi — rapport du 2026-09-29

```
--- polymarket_leadlag ---
Polymarket : 1 partition(s), 117769 ticks lus, 173 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 0 match(s) avec courbe exploitable

❌ aucun match commun entre les ticks Polymarket et les courbes.

--- polymarket_studies ---
Source(s) : kalshi (1 partition(s))
  117769 ticks lus · 171 match(s) exploitables (fourchette max 10 pts)
Books      : 0 match(s), dont 0 avec pinnacle

❌ aucun match commun entre les ticks et les courbes.

--- pm_calibration_track ---
ResultIndex : 1808 résultats · 1781 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 0 observation(s)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 0 observation(s)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1808 résultats · 1781 paires · fenêtre ±5 j
497 match(s) en contexte · 497 avec courbe pinnacle
polymarket : 90,442 ticks lus · 0 observation(s)
kalshi : 117,769 ticks lus · 0 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 0 observation(s)
==========================================================================
  avec résultat connu     : 0
  postérieures au gel     : 0
  avec prix pinnacle    : 0

  par marché (avec résultat) : 

  par niveau (avec résultat) : 

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             0               0
  15 – 30 %            0               0
  30 – 45 %            0               0
  45 – 55 %            0               0
  55 – 70 %            0               0
  70 – 85 %            0               0
  85 – 100 %           0               0

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  395 observation(s) construite(s) · 395 nouvelle(s) · 1479 au journal kalshi_lead_obs.jsonl

```
