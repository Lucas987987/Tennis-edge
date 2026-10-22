# Études Polymarket/Kalshi — rapport du 2026-10-22

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1837674 ticks lus, 554 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 283 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
260 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.001 | Polymarket devant
    -55min |       -0.013 | Polymarket devant
    -50min |       -0.010 | Polymarket devant
    -45min |       -0.003 | Polymarket devant
    -40min |       +0.009 | Polymarket devant
    -35min |       -0.012 | Polymarket devant
    -30min |       +0.010 | Polymarket devant
    -25min |       +0.000 | Polymarket devant
    -20min |       -0.005 | Polymarket devant
    -15min |       -0.015 | Polymarket devant
    -10min |       -0.003 | Polymarket devant
     -5min |       -0.004 | Polymarket devant
     +0min |       +0.122 | simultané  <<<
     +5min |       +0.058 | Pinnacle devant
    +10min |       +0.004 | Pinnacle devant
    +15min |       +0.022 | Pinnacle devant
    +20min |       +0.024 | Pinnacle devant
    +25min |       +0.013 | Pinnacle devant
    +30min |       -0.005 | Pinnacle devant
    +35min |       +0.013 | Pinnacle devant
    +40min |       -0.008 | Pinnacle devant
    +45min |       +0.002 | Pinnacle devant
    +50min |       +0.007 | Pinnacle devant
    +55min |       -0.005 | Pinnacle devant
    +60min |       +0.014 | Pinnacle devant

Maximum à +0 min (corrélation +0.122)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.061
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1837674 ticks lus · 550 match(s) exploitables (fourchette max 10 pts)
Books      : 284 match(s), dont 283 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 268 matchs (35237 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.09 ; +0.05]
  écart médian par match : -0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                268       -0.02  [-0.09 ; +0.05]
  proportionnel       268       -0.13  [-0.24 ; -0.02]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.13 pt)

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   106 |       +0.05 | [ -0.11 ;  +0.20]
           60-70% |   101 |       -0.18 | [ -0.49 ;  +0.14]
           70-80% |    71 |       -0.02 | [ -0.16 ;  +0.11]
           80-90% |    26 |       -0.08 | [ -0.42 ;  +0.26]
             90%+ |    10 |       +0.12 | [ -0.52 ;  +0.76]

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
      confirme |         2 | trop peu
       infirme |         2 | trop peu
          muet |        24 |      +12.4% |     +15.8% | [ +10.2 ;  +21.4]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3695 résultats · 3596 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 76 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        13   trop peu
  55 – 70 %        12   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 160 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        35     36.5%     34.3%    -2.2  [ -15.6 ;  +14.4]
                        il faudrait ~1888 obs pour trancher à cet écart (1853 manquantes)
  55 – 70 %        33     63.3%     66.7%    +3.3  [ -13.7 ;  +16.9]
                        il faudrait ~811 obs pour trancher à cet écart (778 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3695 résultats · 3596 paires · fenêtre ±5 j
4105 match(s) en contexte · 4094 avec courbe pinnacle
polymarket : 4,498,942 ticks lus · 294 observation(s)
kalshi : 1,837,674 ticks lus · 546 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 840 observation(s)
==========================================================================
  avec résultat connu     : 236
  postérieures au gel     : 236
  avec prix pinnacle    : 840

  par marché (avec résultat) : kalshi 160 · polymarket 76

  par niveau (avec résultat) : challenger 162 · wta 58 · atp 16

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            11              11
  15 – 30 %           33              33
  30 – 45 %           48              48
  45 – 55 %           52              52
  55 – 70 %           45              45
  70 – 85 %           36              36
  85 – 100 %          11              11

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  853 observation(s) construite(s) · 371 nouvelle(s) · 17715 au journal kalshi_lead_obs.jsonl

```
