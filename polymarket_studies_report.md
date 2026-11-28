# Études Polymarket/Kalshi — rapport du 2026-11-28

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1005918 ticks lus, 382 match(s) avec série 'match'
  book_curves_live.jsonl: 1685 courbes reconstruites | 169396 points | 4 partitions
Pinnacle   : 325 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
293 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.006 | Polymarket devant
    -55min |       -0.010 | Polymarket devant
    -50min |       +0.003 | Polymarket devant
    -45min |       -0.007 | Polymarket devant
    -40min |       -0.007 | Polymarket devant
    -35min |       -0.008 | Polymarket devant
    -30min |       -0.011 | Polymarket devant
    -25min |       +0.001 | Polymarket devant
    -20min |       +0.003 | Polymarket devant
    -15min |       -0.012 | Polymarket devant
    -10min |       +0.017 | Polymarket devant
     -5min |       +0.036 | Polymarket devant
     +0min |       +0.154 | simultané  <<<
     +5min |       +0.070 | Pinnacle devant
    +10min |       +0.024 | Pinnacle devant
    +15min |       +0.007 | Pinnacle devant
    +20min |       +0.019 | Pinnacle devant
    +25min |       -0.004 | Pinnacle devant
    +30min |       +0.006 | Pinnacle devant
    +35min |       +0.017 | Pinnacle devant
    +40min |       -0.000 | Pinnacle devant
    +45min |       -0.001 | Pinnacle devant
    +50min |       -0.004 | Pinnacle devant
    +55min |       -0.003 | Pinnacle devant
    +60min |       -0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.154)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.073
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1005918 ticks lus · 382 match(s) exploitables (fourchette max 10 pts)
Books      : 336 match(s), dont 325 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 313 matchs (31617 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.11 ; +0.07]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                313       -0.02  [-0.11 ; +0.07]
  proportionnel       313       -0.05  [-0.19 ; +0.10]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    98 |       +0.13 | [ -0.05 ;  +0.30]
           60-70% |   103 |       -0.03 | [ -0.39 ;  +0.32]
           70-80% |    80 |       +0.00 | [ -0.37 ;  +0.37]
           80-90% |    67 |       -0.11 | [ -0.30 ;  +0.09]
             90%+ |    36 |       +0.04 | [ -0.30 ;  +0.37]

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
      confirme |        27 |       +9.6% |     +14.8% | [  +6.4 ;  +23.2]
       infirme |         0 | trop peu
          muet |        38 |       +7.5% |     +15.3% | [  +9.2 ;  +21.3]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3936 résultats · 3833 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 52 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        13   trop peu
  55 – 70 %        13   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 80 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        20     38.1%     40.0%    +1.9  [ -16.2 ;  +23.2]
                        il faudrait ~2578 obs pour trancher à cet écart (2558 manquantes)
  55 – 70 %        20     61.9%     55.0%    -6.9  [ -27.6 ;  +12.3]
                        il faudrait ~194 obs pour trancher à cet écart (174 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3936 résultats · 3833 paires · fenêtre ±5 j
6038 match(s) en contexte · 6004 avec courbe pinnacle
polymarket : 2,725,162 ticks lus · 334 observation(s)
kalshi : 1,005,918 ticks lus · 668 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1002 observation(s)
==========================================================================
  avec résultat connu     : 132
  postérieures au gel     : 132
  avec prix pinnacle    : 964

  par marché (avec résultat) : kalshi 80 · polymarket 52

  par niveau (avec résultat) : challenger 132

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             6               6
  15 – 30 %           14              14
  30 – 45 %           32              32
  45 – 55 %           28              28
  55 – 70 %           32              32
  70 – 85 %           14              14
  85 – 100 %           6               6

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1221 observation(s) construite(s) · 212 nouvelle(s) · 35781 au journal kalshi_lead_obs.jsonl

```
