# Études Polymarket/Kalshi — rapport du 2026-10-16

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1104379 ticks lus, 540 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 238 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
231 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.013 | Polymarket devant
    -55min |       +0.004 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       +0.007 | Polymarket devant
    -40min |       +0.005 | Polymarket devant
    -35min |       +0.003 | Polymarket devant
    -30min |       -0.004 | Polymarket devant
    -25min |       -0.004 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       +0.005 | Polymarket devant
    -10min |       -0.011 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.100 | simultané  <<<
     +5min |       +0.065 | Pinnacle devant
    +10min |       +0.048 | Pinnacle devant
    +15min |       +0.032 | Pinnacle devant
    +20min |       +0.036 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.013 | Pinnacle devant
    +35min |       +0.019 | Pinnacle devant
    +40min |       -0.002 | Pinnacle devant
    +45min |       -0.002 | Pinnacle devant
    +50min |       +0.013 | Pinnacle devant
    +55min |       +0.002 | Pinnacle devant
    +60min |       -0.007 | Pinnacle devant

Maximum à +0 min (corrélation +0.100)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.056
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1104379 ticks lus · 535 match(s) exploitables (fourchette max 10 pts)
Books      : 240 match(s), dont 238 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 233 matchs (36796 instants, grille 5 min)
  écart moyen Shin - marché      : +0.04 pts  IC95 [-0.04 ; +0.12]
  écart médian par match : +0.08 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                233       +0.04  [-0.04 ; +0.12]
  proportionnel       233       -0.01  [-0.15 ; +0.14]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    85 |       +0.04 | [ -0.10 ;  +0.19]
           60-70% |    93 |       -0.07 | [ -0.25 ;  +0.11]
           70-80% |    66 |       +0.09 | [ -0.13 ;  +0.31]
           80-90% |    28 |       +0.28 | [ +0.05 ;  +0.52]
             90%+ |    12 |       -0.08 | [ -0.35 ;  +0.18]

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
      confirme |        12 |      +15.9% |     +20.2% | [  +9.4 ;  +30.9]
       infirme |        10 |      +13.0% |     +14.6% | [ +10.9 ;  +18.4]
          muet |        70 |      +10.5% |      +8.9% | [  +5.9 ;  +12.0]

  différentiel confirme - infirme : +5.6 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3571 résultats · 3476 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 142 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        34     37.4%     41.2%    +3.8  [ -11.0 ;  +20.4]
                        il faudrait ~635 obs pour trancher à cet écart (601 manquantes)
  55 – 70 %        33     62.4%     57.6%    -4.8  [ -21.6 ;  +10.4]
                        il faudrait ~394 obs pour trancher à cet écart (361 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 438 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        97     37.7%     38.1%    +0.4  [  -8.6 ;  +10.4]
                        il faudrait ~53078 obs pour trancher à cet écart (52981 manquantes)
  55 – 70 %        97     62.0%     60.8%    -1.1  [ -11.1 ;   +8.0]
                        il faudrait ~7041 obs pour trancher à cet écart (6944 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3571 résultats · 3476 paires · fenêtre ±5 j
3257 match(s) en contexte · 3246 avec courbe pinnacle
polymarket : 2,595,476 ticks lus · 160 observation(s)
kalshi : 1,104,379 ticks lus · 476 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 636 observation(s)
==========================================================================
  avec résultat connu     : 580
  postérieures au gel     : 580
  avec prix pinnacle    : 632

  par marché (avec résultat) : kalshi 438 · polymarket 142

  par niveau (avec résultat) : challenger 366 · atp 132 · wta 82

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            24              24
  15 – 30 %           85              85
  30 – 45 %          131             131
  45 – 55 %           98              98
  55 – 70 %          130             130
  70 – 85 %           88              88
  85 – 100 %          24              24

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  874 observation(s) construite(s) · 361 nouvelle(s) · 15110 au journal kalshi_lead_obs.jsonl

```
