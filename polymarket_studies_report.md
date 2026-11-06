# Études Polymarket/Kalshi — rapport du 2026-11-06

```
--- polymarket_leadlag ---
Polymarket : 12 partition(s), 2926839 ticks lus, 876 match(s) avec série 'match'
  book_curves_live.jsonl: 4515 courbes reconstruites | 517674 points | 4 partitions
Pinnacle   : 610 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
570 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.002 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       -0.001 | Polymarket devant
    -45min |       +0.005 | Polymarket devant
    -40min |       -0.001 | Polymarket devant
    -35min |       -0.001 | Polymarket devant
    -30min |       -0.015 | Polymarket devant
    -25min |       +0.004 | Polymarket devant
    -20min |       -0.001 | Polymarket devant
    -15min |       -0.000 | Polymarket devant
    -10min |       +0.018 | Polymarket devant
     -5min |       +0.030 | Polymarket devant
     +0min |       +0.113 | simultané  <<<
     +5min |       +0.053 | Pinnacle devant
    +10min |       +0.016 | Pinnacle devant
    +15min |       +0.004 | Pinnacle devant
    +20min |       +0.007 | Pinnacle devant
    +25min |       +0.009 | Pinnacle devant
    +30min |       +0.003 | Pinnacle devant
    +35min |       +0.004 | Pinnacle devant
    +40min |       +0.003 | Pinnacle devant
    +45min |       +0.001 | Pinnacle devant
    +50min |       -0.008 | Pinnacle devant
    +55min |       +0.004 | Pinnacle devant
    +60min |       -0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.113)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.045
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (12 partition(s))
  2926839 ticks lus · 872 match(s) exploitables (fourchette max 10 pts)
Books      : 629 match(s), dont 610 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 582 matchs (83848 instants, grille 5 min)
  écart moyen Shin - marché      : +0.00 pts  IC95 [-0.05 ; +0.05]
  écart médian par match : +0.02 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                582       +0.00  [-0.05 ; +0.05]
  proportionnel       582       -0.07  [-0.15 ; +0.00]
  → plus proche de Polymarket : Shin (écart 0.00 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   192 |       +0.17 | [ -0.10 ;  +0.44]
           60-70% |   223 |       -0.05 | [ -0.15 ;  +0.05]
           70-80% |   137 |       +0.08 | [ -0.07 ;  +0.24]
           80-90% |    85 |       +0.05 | [ -0.08 ;  +0.18]
             90%+ |    29 |       +0.27 | [ -0.13 ;  +0.67]

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
      confirme |        27 |      +10.4% |      +9.0% | [  +6.5 ;  +11.5]
       infirme |         0 | trop peu
          muet |        79 |       +9.5% |     +14.6% | [ +11.1 ;  +18.0]

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
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
5097 match(s) en contexte · 5070 avec courbe pinnacle
polymarket : 6,138,733 ticks lus · 484 observation(s)
kalshi : 2,926,839 ticks lus · 1244 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1728 observation(s)
==========================================================================
  avec résultat connu     : 0
  postérieures au gel     : 0
  avec prix pinnacle    : 1648

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
  1138 observation(s) construite(s) · 359 nouvelle(s) · 26340 au journal kalshi_lead_obs.jsonl

```
