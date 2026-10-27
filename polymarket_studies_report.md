# Études Polymarket/Kalshi — rapport du 2026-10-27

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 2318244 ticks lus, 696 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 482 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
450 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.001 | Polymarket devant
    -55min |       +0.001 | Polymarket devant
    -50min |       -0.004 | Polymarket devant
    -45min |       +0.001 | Polymarket devant
    -40min |       -0.004 | Polymarket devant
    -35min |       -0.007 | Polymarket devant
    -30min |       -0.005 | Polymarket devant
    -25min |       -0.007 | Polymarket devant
    -20min |       +0.003 | Polymarket devant
    -15min |       -0.009 | Polymarket devant
    -10min |       -0.004 | Polymarket devant
     -5min |       +0.010 | Polymarket devant
     +0min |       +0.173 | simultané  <<<
     +5min |       +0.084 | Pinnacle devant
    +10min |       +0.018 | Pinnacle devant
    +15min |       +0.013 | Pinnacle devant
    +20min |       +0.014 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.004 | Pinnacle devant
    +35min |       +0.003 | Pinnacle devant
    +40min |       -0.003 | Pinnacle devant
    +45min |       +0.001 | Pinnacle devant
    +50min |       +0.003 | Pinnacle devant
    +55min |       -0.007 | Pinnacle devant
    +60min |       -0.000 | Pinnacle devant

Maximum à +0 min (corrélation +0.173)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.046
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  2318244 ticks lus · 696 match(s) exploitables (fourchette max 10 pts)
Books      : 483 match(s), dont 482 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 461 matchs (74068 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.05 ; +0.06]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                461       +0.01  [-0.05 ; +0.06]
  proportionnel       461       -0.11  [-0.20 ; -0.01]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.11 pt)

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   182 |       -0.04 | [ -0.15 ;  +0.07]
           60-70% |   188 |       -0.08 | [ -0.36 ;  +0.21]
           70-80% |   116 |       +0.13 | [ -0.10 ;  +0.35]
           80-90% |    61 |       +0.06 | [ -0.28 ;  +0.39]
             90%+ |    25 |       +0.15 | [ -0.38 ;  +0.68]

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
      confirme |        17 |       +5.8% |      +6.9% | [  +3.2 ;  +10.6]
       infirme |         0 | trop peu
          muet |        95 |      +12.1% |     +16.5% | [ +13.3 ;  +19.7]

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

  HORS ÉCHANTILLON (décisif) — 68 observation(s)
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

  HORS ÉCHANTILLON (décisif) — 228 observation(s)
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
4528 match(s) en contexte · 4517 avec courbe pinnacle
polymarket : 5,544,783 ticks lus · 430 observation(s)
kalshi : 2,318,244 ticks lus · 946 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1376 observation(s)
==========================================================================
  avec résultat connu     : 296
  postérieures au gel     : 296
  avec prix pinnacle    : 1370

  par marché (avec résultat) : kalshi 228 · polymarket 68

  par niveau (avec résultat) : challenger 160 · atp 92 · wta 44

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            11              11
  15 – 30 %           35              35
  30 – 45 %           75              75
  45 – 55 %           54              54
  55 – 70 %           75              75
  70 – 85 %           35              35
  85 – 100 %          11              11

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1209 observation(s) construite(s) · 666 nouvelle(s) · 20083 au journal kalshi_lead_obs.jsonl

```
