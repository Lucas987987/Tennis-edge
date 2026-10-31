# Études Polymarket/Kalshi — rapport du 2026-10-31

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1917042 ticks lus, 592 match(s) avec série 'match'
  book_curves_live.jsonl: 3229 courbes reconstruites | 396558 points | 4 partitions
Pinnacle   : 484 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
453 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.003 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       -0.006 | Polymarket devant
    -45min |       +0.007 | Polymarket devant
    -40min |       +0.004 | Polymarket devant
    -35min |       -0.008 | Polymarket devant
    -30min |       -0.010 | Polymarket devant
    -25min |       -0.001 | Polymarket devant
    -20min |       +0.011 | Polymarket devant
    -15min |       -0.006 | Polymarket devant
    -10min |       +0.015 | Polymarket devant
     -5min |       +0.030 | Polymarket devant
     +0min |       +0.140 | simultané  <<<
     +5min |       +0.062 | Pinnacle devant
    +10min |       +0.012 | Pinnacle devant
    +15min |       +0.012 | Pinnacle devant
    +20min |       +0.007 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.006 | Pinnacle devant
    +35min |       -0.003 | Pinnacle devant
    +40min |       -0.003 | Pinnacle devant
    +45min |       +0.004 | Pinnacle devant
    +50min |       +0.001 | Pinnacle devant
    +55min |       -0.004 | Pinnacle devant
    +60min |       -0.013 | Pinnacle devant

Maximum à +0 min (corrélation +0.140)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.048
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1917042 ticks lus · 582 match(s) exploitables (fourchette max 10 pts)
Books      : 498 match(s), dont 484 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 468 matchs (67745 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.08 ; +0.04]
  écart médian par match : -0.06 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                468       -0.02  [-0.08 ; +0.04]
  proportionnel       468       -0.10  [-0.19 ; -0.01]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.10 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   166 |       +0.13 | [ -0.18 ;  +0.45]
           60-70% |   181 |       -0.14 | [ -0.27 ;  -0.02]
           70-80% |   105 |       -0.03 | [ -0.33 ;  +0.27]
           80-90% |    68 |       +0.05 | [ -0.10 ;  +0.20]
             90%+ |    25 |       +0.42 | [ -0.06 ;  +0.91]

  → Shin est INDISCERNABLE du prix du marché de prédiction : le dévigage
    partout dans le projet est validé.
  ⚠️ ceci suppose que le milieu de fourchette Polymarket est non biaisé.
    Une fourchette large le rend imprécis, pas forcément faux — mais si
    l'écart varie fortement selon la tranche, suspecter Polymarket autant
    que Shin.

==========================================================================
2. LE MARCHÉ DE PRÉDICTION COMME CONFIRMATEUR — l'écart chez un book mou
   se referme-t-il mieux quand il confirme ? (mouvement ≥ 3 pts)
==========================================================================
    Polymarket |  n écarts |  CLV médian |  CLV moyen |               IC95
  --------------------------------------------------------------------
      confirme |        23 |      +11.5% |     +11.3% | [  +8.3 ;  +14.4]
       infirme |         0 | trop peu
          muet |        62 |       +9.5% |     +14.7% | [ +10.5 ;  +18.8]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 2 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         1   trop peu
  55 – 70 %         1   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 4 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         1   trop peu
  55 – 70 %         1   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4811 match(s) en contexte · 4778 avec courbe pinnacle
polymarket : 5,171,307 ticks lus · 510 observation(s)
kalshi : 1,917,042 ticks lus · 998 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1508 observation(s)
==========================================================================
  avec résultat connu     : 6
  postérieures au gel     : 6
  avec prix pinnacle    : 1444

  par marché (avec résultat) : kalshi 4 · polymarket 2

  par niveau (avec résultat) : wta 4 · atp 2

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             0               0
  15 – 30 %            0               0
  30 – 45 %            2               2
  45 – 55 %            2               2
  55 – 70 %            2               2
  70 – 85 %            0               0
  85 – 100 %           0               0

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1329 observation(s) construite(s) · 511 nouvelle(s) · 21992 au journal kalshi_lead_obs.jsonl

```
