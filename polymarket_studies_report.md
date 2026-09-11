# Études Polymarket/Kalshi — rapport du 2026-09-11

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1248526 ticks lus, 459 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 309 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
272 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.004 | Polymarket devant
    -55min |       -0.004 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       -0.008 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       +0.000 | Polymarket devant
    -30min |       -0.003 | Polymarket devant
    -25min |       -0.011 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.006 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       +0.003 | Polymarket devant
     +0min |       +0.054 | simultané  <<<
     +5min |       +0.041 | Pinnacle devant
    +10min |       +0.041 | Pinnacle devant
    +15min |       +0.015 | Pinnacle devant
    +20min |       +0.005 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.008 | Pinnacle devant
    +35min |       +0.008 | Pinnacle devant
    +40min |       +0.008 | Pinnacle devant
    +45min |       -0.001 | Pinnacle devant
    +50min |       +0.006 | Pinnacle devant
    +55min |       +0.006 | Pinnacle devant
    +60min |       -0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.054)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.054
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1248526 ticks lus · 454 match(s) exploitables (fourchette max 10 pts)
Books      : 309 match(s), dont 308 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 283 matchs (47219 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.10 ; +0.05]
  écart médian par match : -0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                283       -0.02  [-0.10 ; +0.05]
  proportionnel       283       -0.01  [-0.14 ; +0.11]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.02 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    90 |       -0.20 | [ -0.61 ;  +0.21]
           60-70% |    93 |       +0.13 | [ -0.10 ;  +0.36]
           70-80% |    86 |       -0.12 | [ -0.37 ;  +0.13]
           80-90% |    59 |       -0.12 | [ -0.49 ;  +0.25]
             90%+ |    19 |       +0.08 | [ -0.35 ;  +0.52]

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
       infirme |         0 | trop peu
          muet |       218 |      +17.4% |     +22.0% | [ +17.9 ;  +26.1]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2033 résultats · 2002 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 170 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        39     37.8%     35.9%    -1.9  [ -15.1 ;  +13.8]
                        il faudrait ~2476 obs pour trancher à cet écart (2437 manquantes)
  55 – 70 %        38     62.0%     63.2%    +1.2  [ -14.7 ;  +14.6]
                        il faudrait ~6601 obs pour trancher à cet écart (6563 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 550 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       116     37.7%     36.2%    -1.4  [  -9.6 ;   +7.6]
                        il faudrait ~4326 obs pour trancher à cet écart (4210 manquantes)
  55 – 70 %       112     62.2%     63.4%    +1.2  [  -8.0 ;   +9.5]
                        il faudrait ~6453 obs pour trancher à cet écart (6341 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2033 résultats · 2002 paires · fenêtre ±5 j
2246 match(s) en contexte · 2246 avec courbe pinnacle
polymarket : 1,852,787 ticks lus · 190 observation(s)
kalshi : 1,248,526 ticks lus · 596 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 786 observation(s)
==========================================================================
  avec résultat connu     : 720
  postérieures au gel     : 720
  avec prix pinnacle    : 784

  par marché (avec résultat) : kalshi 550 · polymarket 170

  par niveau (avec résultat) : challenger 516 · grand_chelem 204

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            38              38
  15 – 30 %          128             128
  30 – 45 %          155             155
  45 – 55 %           78              78
  55 – 70 %          150             150
  70 – 85 %          133             133
  85 – 100 %          38              38

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  580 observation(s) construite(s) · 78 nouvelle(s) · 2176 au journal kalshi_lead_obs.jsonl

```
