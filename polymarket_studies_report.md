# Études Polymarket/Kalshi — rapport du 2026-10-04

```
--- polymarket_leadlag ---
Polymarket : 6 partition(s), 1383441 ticks lus, 400 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 199 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
190 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.006 | Polymarket devant
    -55min |       -0.002 | Polymarket devant
    -50min |       +0.003 | Polymarket devant
    -45min |       -0.003 | Polymarket devant
    -40min |       -0.011 | Polymarket devant
    -35min |       +0.004 | Polymarket devant
    -30min |       -0.003 | Polymarket devant
    -25min |       -0.003 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       -0.004 | Polymarket devant
    -10min |       -0.005 | Polymarket devant
     -5min |       -0.014 | Polymarket devant
     +0min |       +0.120 | simultané  <<<
     +5min |       +0.044 | Pinnacle devant
    +10min |       +0.015 | Pinnacle devant
    +15min |       +0.016 | Pinnacle devant
    +20min |       +0.022 | Pinnacle devant
    +25min |       +0.006 | Pinnacle devant
    +30min |       +0.016 | Pinnacle devant
    +35min |       +0.017 | Pinnacle devant
    +40min |       -0.005 | Pinnacle devant
    +45min |       +0.006 | Pinnacle devant
    +50min |       -0.004 | Pinnacle devant
    +55min |       +0.015 | Pinnacle devant
    +60min |       +0.012 | Pinnacle devant

Maximum à +0 min (corrélation +0.120)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.043
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (6 partition(s))
  1383441 ticks lus · 398 match(s) exploitables (fourchette max 10 pts)
Books      : 200 match(s), dont 199 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 192 matchs (33479 instants, grille 5 min)
  écart moyen Shin - marché      : +0.05 pts  IC95 [-0.04 ; +0.13]
  écart médian par match : +0.05 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                192       +0.05  [-0.04 ; +0.13]
  proportionnel       192       +0.06  [-0.09 ; +0.21]
  → plus proche de Polymarket : Shin (écart 0.05 contre 0.06 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    77 |       +0.24 | [ +0.10 ;  +0.39]
           60-70% |    81 |       +0.00 | [ -0.18 ;  +0.19]
           70-80% |    62 |       +0.12 | [ -0.10 ;  +0.35]
           80-90% |    22 |       +0.00 | [ -0.38 ;  +0.38]

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
      confirme |        11 |       +7.5% |      +9.3% | [  +5.3 ;  +13.3]
       infirme |         2 | trop peu
          muet |       103 |      +11.8% |     +14.2% | [ +11.8 ;  +16.6]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3054 résultats · 2983 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 42 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        11   trop peu
  55 – 70 %        11   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 352 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        87     38.4%     46.0%    +7.6  [  -2.5 ;  +18.0]
                        il faudrait ~158 obs pour trancher à cet écart (71 manquantes)
  55 – 70 %        87     61.7%     54.0%    -7.7  [ -18.1 ;   +2.4]
                        il faudrait ~153 obs pour trancher à cet écart (66 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3054 résultats · 2983 paires · fenêtre ±5 j
2817 match(s) en contexte · 2806 avec courbe pinnacle
polymarket : 1,427,078 ticks lus · 46 observation(s)
kalshi : 1,383,441 ticks lus · 398 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 444 observation(s)
==========================================================================
  avec résultat connu     : 394
  postérieures au gel     : 394
  avec prix pinnacle    : 440

  par marché (avec résultat) : kalshi 352 · polymarket 42

  par niveau (avec résultat) : challenger 252 · atp 78 · wta 64

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             9               9
  15 – 30 %           66              66
  30 – 45 %           98              98
  45 – 55 %           48              48
  55 – 70 %           98              98
  70 – 85 %           66              66
  85 – 100 %           9               9

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  547 observation(s) construite(s) · 238 nouvelle(s) · 10933 au journal kalshi_lead_obs.jsonl

```
