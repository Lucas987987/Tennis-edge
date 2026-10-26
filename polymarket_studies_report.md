# Études Polymarket/Kalshi — rapport du 2026-10-26

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 2198357 ticks lus, 667 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 456 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
418 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.008 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       -0.004 | Polymarket devant
    -45min |       -0.001 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       -0.007 | Polymarket devant
    -30min |       -0.004 | Polymarket devant
    -25min |       -0.010 | Polymarket devant
    -20min |       +0.006 | Polymarket devant
    -15min |       -0.009 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       +0.006 | Polymarket devant
     +0min |       +0.179 | simultané  <<<
     +5min |       +0.085 | Pinnacle devant
    +10min |       +0.023 | Pinnacle devant
    +15min |       +0.009 | Pinnacle devant
    +20min |       +0.012 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       -0.001 | Pinnacle devant
    +35min |       +0.006 | Pinnacle devant
    +40min |       -0.007 | Pinnacle devant
    +45min |       +0.003 | Pinnacle devant
    +50min |       +0.002 | Pinnacle devant
    +55min |       -0.011 | Pinnacle devant
    +60min |       +0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.179)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.047
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  2198357 ticks lus · 663 match(s) exploitables (fourchette max 10 pts)
Books      : 458 match(s), dont 456 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 432 matchs (71193 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.04 ; +0.08]
  écart médian par match : -0.00 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                432       +0.02  [-0.04 ; +0.08]
  proportionnel       432       -0.08  [-0.17 ; +0.02]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   172 |       -0.01 | [ -0.12 ;  +0.10]
           60-70% |   170 |       -0.12 | [ -0.44 ;  +0.19]
           70-80% |   110 |       +0.13 | [ -0.10 ;  +0.36]
           80-90% |    54 |       +0.14 | [ -0.24 ;  +0.52]
             90%+ |    25 |       +0.14 | [ -0.39 ;  +0.66]

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
      confirme |        12 |       +1.4% |      +1.9% | [  -1.7 ;   +5.5]
       infirme |         2 | trop peu
          muet |        80 |      +14.0% |     +16.2% | [ +13.4 ;  +18.9]

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

  HORS ÉCHANTILLON (décisif) — 74 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        19     38.2%     42.1%    +3.9  [ -15.1 ;  +25.5]
                        il faudrait ~607 obs pour trancher à cet écart (588 manquantes)
  55 – 70 %        19     61.8%     57.9%    -3.9  [ -25.5 ;  +15.1]
                        il faudrait ~607 obs pour trancher à cet écart (588 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 234 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        56     37.5%     41.1%    +3.5  [  -8.4 ;  +16.6]
                        il faudrait ~721 obs pour trancher à cet écart (665 manquantes)
  55 – 70 %        56     62.5%     58.9%    -3.5  [ -16.6 ;   +8.4]
                        il faudrait ~717 obs pour trancher à cet écart (661 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4455 match(s) en contexte · 4444 avec courbe pinnacle
polymarket : 5,894,781 ticks lus · 420 observation(s)
kalshi : 2,198,357 ticks lus · 888 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1308 observation(s)
==========================================================================
  avec résultat connu     : 308
  postérieures au gel     : 308
  avec prix pinnacle    : 1302

  par marché (avec résultat) : kalshi 234 · polymarket 74

  par niveau (avec résultat) : challenger 160 · atp 92 · wta 56

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            13              13
  15 – 30 %           35              35
  30 – 45 %           75              75
  45 – 55 %           62              62
  55 – 70 %           75              75
  70 – 85 %           35              35
  85 – 100 %          13              13

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  990 observation(s) construite(s) · 496 nouvelle(s) · 19417 au journal kalshi_lead_obs.jsonl

```
