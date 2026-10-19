# Études Polymarket/Kalshi — rapport du 2026-10-19

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1485707 ticks lus, 646 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 118 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
111 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.023 | Polymarket devant
    -55min |       +0.010 | Polymarket devant
    -50min |       -0.002 | Polymarket devant
    -45min |       +0.003 | Polymarket devant
    -40min |       +0.010 | Polymarket devant
    -35min |       +0.013 | Polymarket devant
    -30min |       -0.029 | Polymarket devant
    -25min |       -0.000 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.003 | Polymarket devant
    -10min |       -0.018 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.140 | simultané  <<<
     +5min |       +0.096 | Pinnacle devant
    +10min |       +0.030 | Pinnacle devant
    +15min |       +0.039 | Pinnacle devant
    +20min |       +0.049 | Pinnacle devant
    +25min |       +0.022 | Pinnacle devant
    +30min |       +0.015 | Pinnacle devant
    +35min |       +0.016 | Pinnacle devant
    +40min |       -0.007 | Pinnacle devant
    +45min |       -0.002 | Pinnacle devant
    +50min |       -0.004 | Pinnacle devant
    +55min |       +0.004 | Pinnacle devant
    +60min |       -0.009 | Pinnacle devant

Maximum à +0 min (corrélation +0.140)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.070
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1485707 ticks lus · 637 match(s) exploitables (fourchette max 10 pts)
Books      : 120 match(s), dont 118 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 113 matchs (14234 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.14 ; +0.10]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                113       -0.02  [-0.14 ; +0.10]
  proportionnel       113       -0.15  [-0.38 ; +0.09]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.15 pt)

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    39 |       -0.05 | [ -0.26 ;  +0.15]
           60-70% |    42 |       -0.24 | [ -0.52 ;  +0.03]
           70-80% |    39 |       +0.00 | [ -0.29 ;  +0.29]
           80-90% |    17 |       +0.25 | [ -0.06 ;  +0.55]
             90%+ |     9 |       -0.08 | [ -0.40 ;  +0.23]

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
      confirme |         3 | trop peu
       infirme |        10 |      +13.0% |     +14.6% | [ +10.9 ;  +18.4]
          muet |        48 |      +11.1% |      +8.6% | [  +4.3 ;  +12.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3547 résultats · 3453 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 34 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         6   trop peu
  55 – 70 %         5   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 210 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        38     37.9%     36.8%    -1.1  [ -14.5 ;  +14.8]
                        il faudrait ~8160 obs pour trancher à cet écart (8122 manquantes)
  55 – 70 %        38     61.8%     65.8%    +4.0  [ -11.9 ;  +17.0]
                        il faudrait ~564 obs pour trancher à cet écart (526 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3547 résultats · 3453 paires · fenêtre ±5 j
3518 match(s) en contexte · 3507 avec courbe pinnacle
polymarket : 3,954,338 ticks lus · 46 observation(s)
kalshi : 1,485,707 ticks lus · 236 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 282 observation(s)
==========================================================================
  avec résultat connu     : 244
  postérieures au gel     : 244
  avec prix pinnacle    : 278

  par marché (avec résultat) : kalshi 210 · polymarket 34

  par niveau (avec résultat) : challenger 210 · wta 22 · atp 12

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            15              15
  15 – 30 %           44              44
  30 – 45 %           44              44
  45 – 55 %           37              37
  55 – 70 %           43              43
  70 – 85 %           46              46
  85 – 100 %          15              15

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  868 observation(s) construite(s) · 475 nouvelle(s) · 16310 au journal kalshi_lead_obs.jsonl

```
