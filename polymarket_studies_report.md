# Études Polymarket/Kalshi — rapport du 2026-11-26

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1079382 ticks lus, 418 match(s) avec série 'match'
  book_curves_live.jsonl: 3645 courbes reconstruites | 389967 points | 4 partitions
Pinnacle   : 365 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
329 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.011 | Polymarket devant
    -55min |       -0.009 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.001 | Polymarket devant
    -40min |       -0.004 | Polymarket devant
    -35min |       -0.008 | Polymarket devant
    -30min |       -0.017 | Polymarket devant
    -25min |       +0.002 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.007 | Polymarket devant
    -10min |       +0.014 | Polymarket devant
     -5min |       +0.052 | Polymarket devant
     +0min |       +0.094 | simultané  <<<
     +5min |       +0.055 | Pinnacle devant
    +10min |       +0.025 | Pinnacle devant
    +15min |       +0.027 | Pinnacle devant
    +20min |       +0.008 | Pinnacle devant
    +25min |       -0.017 | Pinnacle devant
    +30min |       -0.011 | Pinnacle devant
    +35min |       +0.012 | Pinnacle devant
    +40min |       +0.006 | Pinnacle devant
    +45min |       +0.011 | Pinnacle devant
    +50min |       -0.006 | Pinnacle devant
    +55min |       +0.006 | Pinnacle devant
    +60min |       -0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.094)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.082
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1079382 ticks lus · 418 match(s) exploitables (fourchette max 10 pts)
Books      : 388 match(s), dont 365 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 349 matchs (32812 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.10 ; +0.06]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                349       -0.02  [-0.10 ; +0.06]
  proportionnel       349       -0.02  [-0.15 ; +0.12]
  → plus proche de Polymarket : proportionnel (écart 0.02 contre 0.02 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    98 |       +0.08 | [ -0.07 ;  +0.23]
           60-70% |   108 |       -0.19 | [ -0.51 ;  +0.14]
           70-80% |    96 |       +0.00 | [ -0.31 ;  +0.31]
           80-90% |    77 |       -0.04 | [ -0.20 ;  +0.12]
             90%+ |    34 |       -0.05 | [ -0.35 ;  +0.25]

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
      confirme |        35 |      +14.2% |     +14.0% | [ +10.6 ;  +17.4]
       infirme |         0 | trop peu
          muet |        18 |       +9.8% |     +15.6% | [  +5.1 ;  +26.1]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3924 résultats · 3821 paires · fenêtre ±5 j

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
  30 – 45 %         7   trop peu
  55 – 70 %         7   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 62 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        15     38.5%     46.7%    +8.2  [ -13.7 ;  +31.4]
                        il faudrait ~136 obs pour trancher à cet écart (121 manquantes)
  55 – 70 %        14   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3924 résultats · 3821 paires · fenêtre ±5 j
6065 match(s) en contexte · 5977 avec courbe pinnacle
polymarket : 3,033,332 ticks lus · 316 observation(s)
kalshi : 1,079,382 ticks lus · 760 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1076 observation(s)
==========================================================================
  avec résultat connu     : 94
  postérieures au gel     : 94
  avec prix pinnacle    : 996

  par marché (avec résultat) : kalshi 62 · polymarket 32

  par niveau (avec résultat) : challenger 90 · atp 4

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             5               5
  15 – 30 %           10              10
  30 – 45 %           25              25
  45 – 55 %           15              15
  55 – 70 %           23              23
  70 – 85 %           11              11
  85 – 100 %           5               5

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  808 observation(s) construite(s) · 363 nouvelle(s) · 35237 au journal kalshi_lead_obs.jsonl

```
