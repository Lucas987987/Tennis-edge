# Études Polymarket/Kalshi — rapport du 2026-11-27

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1038332 ticks lus, 399 match(s) avec série 'match'
  book_curves_live.jsonl: 2795 courbes reconstruites | 262451 points | 4 partitions
Pinnacle   : 352 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
322 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.005 | Polymarket devant
    -55min |       -0.006 | Polymarket devant
    -50min |       +0.007 | Polymarket devant
    -45min |       -0.001 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       -0.002 | Polymarket devant
    -30min |       -0.012 | Polymarket devant
    -25min |       -0.006 | Polymarket devant
    -20min |       +0.012 | Polymarket devant
    -15min |       -0.002 | Polymarket devant
    -10min |       +0.021 | Polymarket devant
     -5min |       +0.049 | Polymarket devant
     +0min |       +0.112 | simultané  <<<
     +5min |       +0.069 | Pinnacle devant
    +10min |       +0.021 | Pinnacle devant
    +15min |       +0.022 | Pinnacle devant
    +20min |       +0.012 | Pinnacle devant
    +25min |       +0.006 | Pinnacle devant
    +30min |       +0.001 | Pinnacle devant
    +35min |       +0.017 | Pinnacle devant
    +40min |       +0.007 | Pinnacle devant
    +45min |       +0.005 | Pinnacle devant
    +50min |       -0.010 | Pinnacle devant
    +55min |       -0.000 | Pinnacle devant
    +60min |       -0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.112)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.079
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1038332 ticks lus · 399 match(s) exploitables (fourchette max 10 pts)
Books      : 367 match(s), dont 352 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 339 matchs (33195 instants, grille 5 min)
  écart moyen Shin - marché      : -0.01 pts  IC95 [-0.09 ; +0.07]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                339       -0.01  [-0.09 ; +0.07]
  proportionnel       339       -0.04  [-0.18 ; +0.09]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   102 |       +0.12 | [ -0.05 ;  +0.29]
           60-70% |   106 |       -0.09 | [ -0.41 ;  +0.22]
           70-80% |    89 |       +0.03 | [ -0.30 ;  +0.36]
           80-90% |    73 |       -0.10 | [ -0.27 ;  +0.07]
             90%+ |    35 |       -0.04 | [ -0.34 ;  +0.26]

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
      confirme |        36 |      +13.4% |     +15.7% | [ +10.6 ;  +20.9]
       infirme |         0 | trop peu
          muet |        30 |       +6.7% |     +15.6% | [  +8.0 ;  +23.2]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3924 résultats · 3821 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 34 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         7   trop peu
  55 – 70 %         7   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 58 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        14   trop peu
  55 – 70 %        13   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3924 résultats · 3821 paires · fenêtre ±5 j
6050 match(s) en contexte · 6003 avec courbe pinnacle
polymarket : 2,906,246 ticks lus · 338 observation(s)
kalshi : 1,038,332 ticks lus · 728 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1066 observation(s)
==========================================================================
  avec résultat connu     : 90
  postérieures au gel     : 90
  avec prix pinnacle    : 1016

  par marché (avec résultat) : kalshi 58 · polymarket 32

  par niveau (avec résultat) : challenger 88 · atp 2

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             5               5
  15 – 30 %           12              12
  30 – 45 %           21              21
  45 – 55 %           15              15
  55 – 70 %           20              20
  70 – 85 %           12              12
  85 – 100 %           5               5

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1062 observation(s) construite(s) · 332 nouvelle(s) · 35569 au journal kalshi_lead_obs.jsonl

```
