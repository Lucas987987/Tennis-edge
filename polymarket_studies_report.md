# Études Polymarket/Kalshi — rapport du 2026-10-29

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 2047678 ticks lus, 584 match(s) avec série 'match'
  book_curves_live.jsonl: 5346 courbes reconstruites | 798235 points | 4 partitions
Pinnacle   : 522 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
478 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.009 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       +0.003 | Polymarket devant
    -40min |       +0.002 | Polymarket devant
    -35min |       -0.003 | Polymarket devant
    -30min |       -0.003 | Polymarket devant
    -25min |       -0.000 | Polymarket devant
    -20min |       +0.006 | Polymarket devant
    -15min |       +0.009 | Polymarket devant
    -10min |       +0.021 | Polymarket devant
     -5min |       +0.031 | Polymarket devant
     +0min |       +0.102 | simultané  <<<
     +5min |       +0.040 | Pinnacle devant
    +10min |       +0.014 | Pinnacle devant
    +15min |       +0.010 | Pinnacle devant
    +20min |       +0.004 | Pinnacle devant
    +25min |       +0.013 | Pinnacle devant
    +30min |       +0.014 | Pinnacle devant
    +35min |       -0.002 | Pinnacle devant
    +40min |       -0.006 | Pinnacle devant
    +45min |       +0.008 | Pinnacle devant
    +50min |       +0.001 | Pinnacle devant
    +55min |       -0.011 | Pinnacle devant
    +60min |       -0.008 | Pinnacle devant

Maximum à +0 min (corrélation +0.102)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.044
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  2047678 ticks lus · 581 match(s) exploitables (fourchette max 10 pts)
Books      : 541 match(s), dont 522 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 503 matchs (74277 instants, grille 5 min)
  écart moyen Shin - marché      : -0.01 pts  IC95 [-0.06 ; +0.05]
  écart médian par match : -0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                503       -0.01  [-0.06 ; +0.05]
  proportionnel       503       -0.06  [-0.14 ; +0.03]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.06 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   176 |       +0.04 | [ -0.07 ;  +0.14]
           60-70% |   205 |       -0.10 | [ -0.33 ;  +0.12]
           70-80% |   106 |       +0.11 | [ -0.12 ;  +0.34]
           80-90% |    71 |       -0.08 | [ -0.27 ;  +0.11]
             90%+ |    28 |       +0.24 | [ -0.19 ;  +0.67]

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
      confirme |        17 |      +10.7% |      +8.7% | [  +6.0 ;  +11.3]
       infirme |         0 | trop peu
          muet |        64 |      +11.2% |     +16.8% | [ +11.7 ;  +21.9]

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

  HORS ÉCHANTILLON (décisif) — 36 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         9   trop peu
  55 – 70 %         9   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 86 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        23     37.0%     30.4%    -6.5  [ -21.4 ;  +13.9]
                        il faudrait ~210 obs pour trancher à cet écart (187 manquantes)
  55 – 70 %        23     63.0%     69.6%    +6.5  [ -13.9 ;  +21.4]
                        il faudrait ~211 obs pour trancher à cet écart (188 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4784 match(s) en contexte · 4733 avec courbe pinnacle
polymarket : 4,801,655 ticks lus · 436 observation(s)
kalshi : 2,047,678 ticks lus · 1056 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1492 observation(s)
==========================================================================
  avec résultat connu     : 122
  postérieures au gel     : 122
  avec prix pinnacle    : 1414

  par marché (avec résultat) : kalshi 86 · polymarket 36

  par niveau (avec résultat) : challenger 46 · atp 46 · wta 30

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             4               4
  15 – 30 %           11              11
  30 – 45 %           32              32
  45 – 55 %           28              28
  55 – 70 %           32              32
  70 – 85 %           11              11
  85 – 100 %           4               4

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  921 observation(s) construite(s) · 401 nouvelle(s) · 21081 au journal kalshi_lead_obs.jsonl

```
