# Études Polymarket/Kalshi — rapport du 2026-09-01

```
--- polymarket_flow ---
❌ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 15 partition(s), 3000602 ticks lus, 654 match(s) avec série 'match'
Pinnacle   : 240 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
233 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.007 | Polymarket devant
    -55min |       -0.007 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.011 | Polymarket devant
    -40min |       +0.008 | Polymarket devant
    -35min |       +0.006 | Polymarket devant
    -30min |       -0.012 | Polymarket devant
    -25min |       +0.000 | Polymarket devant
    -20min |       +0.014 | Polymarket devant
    -15min |       +0.009 | Polymarket devant
    -10min |       +0.003 | Polymarket devant
     -5min |       -0.004 | Polymarket devant
     +0min |       +0.113 | simultané  <<<
     +5min |       +0.085 | Pinnacle devant
    +10min |       +0.031 | Pinnacle devant
    +15min |       +0.013 | Pinnacle devant
    +20min |       +0.026 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       +0.011 | Pinnacle devant
    +35min |       +0.005 | Pinnacle devant
    +40min |       -0.001 | Pinnacle devant
    +45min |       +0.010 | Pinnacle devant
    +50min |       +0.002 | Pinnacle devant
    +55min |       -0.006 | Pinnacle devant
    +60min |       -0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.113)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.041
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (15 partition(s))
  3000602 ticks lus · 648 match(s) exploitables (fourchette max 10 pts)
Books      : 240 match(s), dont 240 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 233 matchs (38782 instants, grille 5 min)
  écart moyen Shin - marché      : -0.00 pts  IC95 [-0.08 ; +0.08]
  écart médian par match : -0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                233       -0.00  [-0.08 ; +0.08]
  proportionnel       233       -0.04  [-0.17 ; +0.08]
  → plus proche de Polymarket : Shin (écart 0.00 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   111 |       +0.05 | [ -0.13 ;  +0.22]
           60-70% |   112 |       -0.10 | [ -0.30 ;  +0.11]
           70-80% |    60 |       -0.10 | [ -0.48 ;  +0.28]
           80-90% |    28 |       +0.01 | [ -0.40 ;  +0.42]

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
          muet |       173 |      +10.7% |     +17.0% | [ +14.3 ;  +19.7]

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

  origine (pour mémoire) — 64 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        20     39.0%     35.0%    -4.0  [ -20.8 ;  +17.8]
  55 – 70 %        20     61.1%     65.0%    +3.9  [ -17.8 ;  +20.8]

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

  origine (pour mémoire) — 72 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        20     38.2%     35.0%    -3.2  [ -20.1 ;  +18.5]
  55 – 70 %        20     61.9%     65.0%    +3.1  [ -18.6 ;  +20.0]

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j
1886 match(s) en contexte · 1886 avec courbe pinnacle
polymarket : 5,445,603 ticks lus · 298 observation(s)
kalshi : 3,000,602 ticks lus · 470 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 768 observation(s)
==========================================================================
  avec résultat connu     : 724
  postérieures au gel     : 588
  avec prix pinnacle    : 762

  par marché (avec résultat) : kalshi 446 · polymarket 278

  par niveau (avec résultat) : grand_chelem 452 · challenger 118 · atp 92 · wta 62

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             9               6
  15 – 30 %           79              63
  30 – 45 %          218             178
  45 – 55 %          109              91
  55 – 70 %          220             180
  70 – 85 %           78              62
  85 – 100 %          11               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
