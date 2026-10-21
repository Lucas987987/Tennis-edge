# Études Polymarket/Kalshi — rapport du 2026-10-21

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1802353 ticks lus, 603 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 50 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
44 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.039 | Polymarket devant
    -55min |       -0.007 | Polymarket devant
    -50min |       -0.006 | Polymarket devant
    -45min |       +0.007 | Polymarket devant
    -40min |       +0.011 | Polymarket devant
    -35min |       +0.011 | Polymarket devant
    -30min |       +0.018 | Polymarket devant
    -25min |       -0.035 | Polymarket devant
    -20min |       -0.017 | Polymarket devant
    -15min |       +0.002 | Polymarket devant
    -10min |       -0.046 | Polymarket devant
     -5min |       -0.026 | Polymarket devant
     +0min |       +0.180 | simultané  <<<
     +5min |       +0.121 | Pinnacle devant
    +10min |       +0.005 | Pinnacle devant
    +15min |       +0.050 | Pinnacle devant
    +20min |       +0.058 | Pinnacle devant
    +25min |       +0.004 | Pinnacle devant
    +30min |       -0.010 | Pinnacle devant
    +35min |       +0.026 | Pinnacle devant
    +40min |       -0.035 | Pinnacle devant
    +45min |       +0.011 | Pinnacle devant
    +50min |       -0.007 | Pinnacle devant
    +55min |       +0.001 | Pinnacle devant
    +60min |       -0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.180)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.074
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1802353 ticks lus · 599 match(s) exploitables (fourchette max 10 pts)
Books      : 50 match(s), dont 50 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 44 matchs (4890 instants, grille 5 min)
  écart moyen Shin - marché      : +0.05 pts  IC95 [-0.10 ; +0.20]
  écart médian par match : +0.16 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                 44       +0.05  [-0.10 ; +0.20]
  proportionnel        44       -0.07  [-0.34 ; +0.21]
  → plus proche de Polymarket : Shin (écart 0.05 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    21 |       -0.16 | [ -0.47 ;  +0.14]
           60-70% |    19 |       +0.02 | [ -0.31 ;  +0.35]
           70-80% |    12 |       +0.12 | [ -0.40 ;  +0.65]

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
      confirme |         0 | trop peu
       infirme |        10 |      +13.0% |     +14.6% | [ +10.9 ;  +18.4]
          muet |        37 |      +13.9% |     +15.3% | [ +12.3 ;  +18.4]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3506 résultats · 3412 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 14 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         3   trop peu
  55 – 70 %         3   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 80 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        21     37.2%     42.9%    +5.7  [ -12.7 ;  +26.3]
                        il faudrait ~280 obs pour trancher à cet écart (259 manquantes)
  55 – 70 %        20     62.5%     60.0%    -2.5  [ -23.8 ;  +15.7]
                        il faudrait ~1501 obs pour trancher à cet écart (1481 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3506 résultats · 3412 paires · fenêtre ±5 j
3606 match(s) en contexte · 3595 avec courbe pinnacle
polymarket : 4,419,073 ticks lus · 14 observation(s)
kalshi : 1,802,353 ticks lus · 90 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 104 observation(s)
==========================================================================
  avec résultat connu     : 94
  postérieures au gel     : 94
  avec prix pinnacle    : 104

  par marché (avec résultat) : kalshi 80 · polymarket 14

  par niveau (avec résultat) : challenger 80 · wta 10 · atp 4

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             1               1
  15 – 30 %           14              14
  30 – 45 %           24              24
  45 – 55 %           16              16
  55 – 70 %           23              23
  70 – 85 %           15              15
  85 – 100 %           1               1

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  837 observation(s) construite(s) · 382 nouvelle(s) · 17344 au journal kalshi_lead_obs.jsonl

```
