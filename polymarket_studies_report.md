# Études Polymarket/Kalshi — rapport du 2026-10-01

```
--- polymarket_leadlag ---
Polymarket : 3 partition(s), 798115 ticks lus, 291 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 119 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
110 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.005 | Polymarket devant
    -55min |       -0.000 | Polymarket devant
    -50min |       -0.001 | Polymarket devant
    -45min |       +0.007 | Polymarket devant
    -40min |       -0.011 | Polymarket devant
    -35min |       +0.018 | Polymarket devant
    -30min |       -0.004 | Polymarket devant
    -25min |       +0.001 | Polymarket devant
    -20min |       +0.006 | Polymarket devant
    -15min |       -0.011 | Polymarket devant
    -10min |       -0.005 | Polymarket devant
     -5min |       +0.002 | Polymarket devant
     +0min |       +0.130 | simultané  <<<
     +5min |       +0.043 | Pinnacle devant
    +10min |       +0.012 | Pinnacle devant
    +15min |       +0.019 | Pinnacle devant
    +20min |       +0.024 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.013 | Pinnacle devant
    +35min |       +0.020 | Pinnacle devant
    +40min |       -0.018 | Pinnacle devant
    +45min |       +0.002 | Pinnacle devant
    +50min |       -0.021 | Pinnacle devant
    +55min |       +0.018 | Pinnacle devant
    +60min |       +0.029 | Pinnacle devant

Maximum à +0 min (corrélation +0.130)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.050
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (3 partition(s))
  798115 ticks lus · 289 match(s) exploitables (fourchette max 10 pts)
Books      : 120 match(s), dont 119 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 112 matchs (15311 instants, grille 5 min)
  écart moyen Shin - marché      : +0.04 pts  IC95 [-0.09 ; +0.16]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                112       +0.04  [-0.09 ; +0.16]
  proportionnel       112       +0.08  [-0.14 ; +0.29]
  → plus proche de Polymarket : Shin (écart 0.04 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    34 |       +0.29 | [ +0.08 ;  +0.50]
           60-70% |    50 |       -0.08 | [ -0.30 ;  +0.15]
           70-80% |    40 |       -0.07 | [ -0.26 ;  +0.13]
           80-90% |    15 |       +0.16 | [ -0.36 ;  +0.68]

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
      confirme |        10 |       +9.1% |     +10.2% | [  +6.3 ;  +14.1]
       infirme |         2 | trop peu
          muet |        74 |      +12.5% |     +15.0% | [ +12.3 ;  +17.7]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2921 résultats · 2850 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 18 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         4   trop peu
  55 – 70 %         4   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 212 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        47     37.4%     42.6%    +5.2  [  -7.8 ;  +19.4]
                        il faudrait ~333 obs pour trancher à cet écart (286 manquantes)
  55 – 70 %        47     62.8%     57.4%    -5.3  [ -19.5 ;   +7.7]
                        il faudrait ~317 obs pour trancher à cet écart (270 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2921 résultats · 2850 paires · fenêtre ±5 j
1148 match(s) en contexte · 1137 avec courbe pinnacle
polymarket : 485,207 ticks lus · 18 observation(s)
kalshi : 798,115 ticks lus · 238 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 256 observation(s)
==========================================================================
  avec résultat connu     : 230
  postérieures au gel     : 230
  avec prix pinnacle    : 254

  par marché (avec résultat) : kalshi 212 · polymarket 18

  par niveau (avec résultat) : challenger 162 · atp 38 · wta 30

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             5               5
  15 – 30 %           47              47
  30 – 45 %           51              51
  45 – 55 %           24              24
  55 – 70 %           51              51
  70 – 85 %           47              47
  85 – 100 %           5               5

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  589 observation(s) construite(s) · 497 nouvelle(s) · 9368 au journal kalshi_lead_obs.jsonl

```
