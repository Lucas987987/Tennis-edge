# Études Polymarket/Kalshi — rapport du 2026-08-30

```
--- polymarket_flow ---
❌ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 16 partition(s), 3001648 ticks lus, 757 match(s) avec série 'match'
Pinnacle   : 305 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
290 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.006 | Polymarket devant
    -55min |       -0.007 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.009 | Polymarket devant
    -40min |       +0.006 | Polymarket devant
    -35min |       +0.002 | Polymarket devant
    -30min |       -0.007 | Polymarket devant
    -25min |       +0.001 | Polymarket devant
    -20min |       +0.013 | Polymarket devant
    -15min |       +0.006 | Polymarket devant
    -10min |       +0.006 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.127 | simultané  <<<
     +5min |       +0.076 | Pinnacle devant
    +10min |       +0.037 | Pinnacle devant
    +15min |       +0.021 | Pinnacle devant
    +20min |       +0.023 | Pinnacle devant
    +25min |       +0.009 | Pinnacle devant
    +30min |       +0.008 | Pinnacle devant
    +35min |       +0.006 | Pinnacle devant
    +40min |       +0.003 | Pinnacle devant
    +45min |       +0.008 | Pinnacle devant
    +50min |       +0.003 | Pinnacle devant
    +55min |       -0.006 | Pinnacle devant
    +60min |       +0.002 | Pinnacle devant

Maximum à +0 min (corrélation +0.127)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.046
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (16 partition(s))
  3001648 ticks lus · 751 match(s) exploitables (fourchette max 10 pts)
Books      : 310 match(s), dont 305 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 295 matchs (44756 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.07 ; +0.09]
  écart médian par match : -0.05 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                295       +0.01  [-0.07 ; +0.09]
  proportionnel       295       -0.03  [-0.16 ; +0.09]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.03 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   130 |       +0.01 | [ -0.15 ;  +0.16]
           60-70% |   137 |       -0.08 | [ -0.26 ;  +0.10]
           70-80% |    77 |       -0.08 | [ -0.44 ;  +0.28]
           80-90% |    38 |       -0.04 | [ -0.39 ;  +0.30]
             90%+ |     8 |       -0.54 | [ -1.55 ;  +0.47]

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
      confirme |        65 |      +10.4% |     +12.5% | [ +10.6 ;  +14.3]
       infirme |         9 |       +2.8% |      +4.1% | [  -1.8 ;  +10.0]
          muet |       197 |      +10.7% |     +16.1% | [ +13.7 ;  +18.5]

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

  origine (pour mémoire) — 166 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        47     37.8%     36.2%    -1.6  [ -13.8 ;  +12.7]
  55 – 70 %        49     61.9%     65.3%    +3.4  [ -10.6 ;  +15.1]

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

  origine (pour mémoire) — 200 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        53     37.2%     37.7%    +0.5  [ -11.3 ;  +14.0]
  55 – 70 %        52     62.8%     63.5%    +0.7  [ -12.9 ;  +12.4]

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j
1886 match(s) en contexte · 1886 avec courbe pinnacle
polymarket : 7,065,169 ticks lus · 406 observation(s)
kalshi : 3,001,648 ticks lus · 604 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1010 observation(s)
==========================================================================
  avec résultat connu     : 954
  postérieures au gel     : 588
  avec prix pinnacle    : 1004

  par marché (avec résultat) : kalshi 574 · polymarket 380

  par niveau (avec résultat) : grand_chelem 452 · challenger 218 · atp 166 · wta 118

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            24               6
  15 – 30 %          105              63
  30 – 45 %          278             178
  45 – 55 %          135              91
  55 – 70 %          281             180
  70 – 85 %          106              62
  85 – 100 %          25               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
