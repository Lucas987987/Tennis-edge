# Études Polymarket/Kalshi — rapport du 2026-10-09

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1662477 ticks lus, 588 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 323 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
302 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.003 | Polymarket devant
    -55min |       -0.001 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.006 | Polymarket devant
    -40min |       -0.006 | Polymarket devant
    -35min |       +0.001 | Polymarket devant
    -30min |       +0.004 | Polymarket devant
    -25min |       -0.009 | Polymarket devant
    -20min |       -0.004 | Polymarket devant
    -15min |       +0.002 | Polymarket devant
    -10min |       +0.005 | Polymarket devant
     -5min |       -0.013 | Polymarket devant
     +0min |       +0.109 | simultané  <<<
     +5min |       +0.054 | Pinnacle devant
    +10min |       +0.039 | Pinnacle devant
    +15min |       +0.031 | Pinnacle devant
    +20min |       +0.010 | Pinnacle devant
    +25min |       +0.014 | Pinnacle devant
    +30min |       +0.011 | Pinnacle devant
    +35min |       +0.006 | Pinnacle devant
    +40min |       -0.002 | Pinnacle devant
    +45min |       +0.005 | Pinnacle devant
    +50min |       +0.012 | Pinnacle devant
    +55min |       +0.011 | Pinnacle devant
    +60min |       -0.005 | Pinnacle devant

Maximum à +0 min (corrélation +0.109)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.052
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1662477 ticks lus · 588 match(s) exploitables (fourchette max 10 pts)
Books      : 324 match(s), dont 323 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 307 matchs (52799 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.05 ; +0.08]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                307       +0.01  [-0.05 ; +0.08]
  proportionnel       307       -0.07  [-0.19 ; +0.06]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   118 |       +0.01 | [ -0.12 ;  +0.13]
           60-70% |   110 |       +0.04 | [ -0.17 ;  +0.25]
           70-80% |    78 |       +0.09 | [ -0.11 ;  +0.28]
           80-90% |    44 |       -0.22 | [ -0.45 ;  +0.01]
             90%+ |    18 |       +0.26 | [ -0.22 ;  +0.74]

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
       infirme |         1 | trop peu
          muet |       100 |      +10.5% |     +11.0% | [  +9.1 ;  +12.8]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  2 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3248 résultats · 3175 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 150 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        30     38.1%     50.0%   +11.9  [  -4.9 ;  +28.7]
                        il faudrait ~64 obs pour trancher à cet écart (34 manquantes)
  55 – 70 %        30     61.4%     46.7%   -14.7  [ -31.2 ;   +2.5]
                        il faudrait ~42 obs pour trancher à cet écart (12 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 586 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       135     38.3%     41.5%    +3.2  [  -4.8 ;  +11.6]
                        il faudrait ~906 obs pour trancher à cet écart (771 manquantes)
  55 – 70 %       140     61.6%     55.0%    -6.6  [ -14.9 ;   +1.4]
                        il faudrait ~206 obs pour trancher à cet écart (66 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3248 résultats · 3175 paires · fenêtre ±5 j
3057 match(s) en contexte · 3046 avec courbe pinnacle
polymarket : 2,501,844 ticks lus · 160 observation(s)
kalshi : 1,662,477 ticks lus · 628 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 788 observation(s)
==========================================================================
  avec résultat connu     : 736
  postérieures au gel     : 736
  avec prix pinnacle    : 782

  par marché (avec résultat) : kalshi 586 · polymarket 150

  par niveau (avec résultat) : challenger 472 · atp 180 · wta 84

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            40              40
  15 – 30 %          108             108
  30 – 45 %          165             165
  45 – 55 %          105             105
  55 – 70 %          170             170
  70 – 85 %          107             107
  85 – 100 %          41              41

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  761 observation(s) construite(s) · 327 nouvelle(s) · 12709 au journal kalshi_lead_obs.jsonl

```
