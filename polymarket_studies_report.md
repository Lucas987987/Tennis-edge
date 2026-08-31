# Études Polymarket/Kalshi — rapport du 2026-08-31

```
--- polymarket_flow ---
❌ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 16 partition(s), 3175182 ticks lus, 726 match(s) avec série 'match'
Pinnacle   : 276 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
262 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.008 | Polymarket devant
    -55min |       -0.007 | Polymarket devant
    -50min |       +0.009 | Polymarket devant
    -45min |       -0.011 | Polymarket devant
    -40min |       +0.009 | Polymarket devant
    -35min |       +0.001 | Polymarket devant
    -30min |       -0.010 | Polymarket devant
    -25min |       -0.004 | Polymarket devant
    -20min |       +0.013 | Polymarket devant
    -15min |       +0.006 | Polymarket devant
    -10min |       +0.008 | Polymarket devant
     -5min |       -0.007 | Polymarket devant
     +0min |       +0.118 | simultané  <<<
     +5min |       +0.085 | Pinnacle devant
    +10min |       +0.038 | Pinnacle devant
    +15min |       +0.018 | Pinnacle devant
    +20min |       +0.024 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.010 | Pinnacle devant
    +35min |       +0.002 | Pinnacle devant
    +40min |       +0.002 | Pinnacle devant
    +45min |       +0.009 | Pinnacle devant
    +50min |       +0.002 | Pinnacle devant
    +55min |       -0.006 | Pinnacle devant
    +60min |       +0.001 | Pinnacle devant

Maximum à +0 min (corrélation +0.118)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.041
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (16 partition(s))
  3175182 ticks lus · 720 match(s) exploitables (fourchette max 10 pts)
Books      : 281 match(s), dont 276 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 267 matchs (41363 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.07 ; +0.09]
  écart médian par match : -0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                267       +0.01  [-0.07 ; +0.09]
  proportionnel       267       -0.04  [-0.17 ; +0.09]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   122 |       +0.04 | [ -0.12 ;  +0.20]
           60-70% |   124 |       -0.09 | [ -0.28 ;  +0.10]
           70-80% |    66 |       -0.13 | [ -0.50 ;  +0.25]
           80-90% |    35 |       -0.05 | [ -0.43 ;  +0.32]

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
      confirme |        61 |      +10.0% |     +12.5% | [ +10.5 ;  +14.5]
       infirme |         9 |       +2.8% |      +4.1% | [  -1.8 ;  +10.0]
          muet |       174 |      +10.7% |     +17.0% | [ +14.3 ;  +19.6]

  différentiel confirme - infirme : +8.4 pts de CLV
  → intervalles disjoints. Piste à geler et valider hors échantillon.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 214 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        71     38.1%     43.7%    +5.5  [  -5.4 ;  +17.1]
                        il faudrait ~296 obs pour trancher à cet écart (225 manquantes)
  55 – 70 %        71     61.9%     56.3%    -5.5  [ -17.1 ;   +5.4]
                        il faudrait ~296 obs pour trancher à cet écart (225 manquantes)

  origine (pour mémoire) — 118 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        35     38.2%     37.1%    -1.1  [ -15.1 ;  +15.4]
  55 – 70 %        36     61.6%     63.9%    +2.3  [ -14.0 ;  +16.0]

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 374 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       107     37.7%     42.1%    +4.3  [  -4.6 ;  +13.8]
                        il faudrait ~484 obs pour trancher à cet écart (377 manquantes)
  55 – 70 %       109     62.1%     56.9%    -5.3  [ -14.6 ;   +3.7]
                        il faudrait ~328 obs pour trancher à cet écart (219 manquantes)

  origine (pour mémoire) — 144 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        38     37.7%     39.5%    +1.8  [ -12.1 ;  +17.6]
  55 – 70 %        38     62.5%     60.5%    -2.0  [ -17.8 ;  +11.9]

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j
1886 match(s) en contexte · 1886 avec courbe pinnacle
polymarket : 6,364,236 ticks lus · 358 observation(s)
kalshi : 3,175,182 ticks lus · 548 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 906 observation(s)
==========================================================================
  avec résultat connu     : 850
  postérieures au gel     : 588
  avec prix pinnacle    : 900

  par marché (avec résultat) : kalshi 518 · polymarket 332

  par niveau (avec résultat) : grand_chelem 452 · challenger 186 · atp 130 · wta 82

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            16               6
  15 – 30 %           94              63
  30 – 45 %          251             178
  45 – 55 %          124              91
  55 – 70 %          254             180
  70 – 85 %           94              62
  85 – 100 %          17               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
