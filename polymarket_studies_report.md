# Études Polymarket/Kalshi — rapport du 2026-09-06

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1664329 ticks lus, 405 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 199 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
181 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.006 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       +0.006 | Polymarket devant
    -45min |       -0.003 | Polymarket devant
    -40min |       +0.005 | Polymarket devant
    -35min |       +0.014 | Polymarket devant
    -30min |       -0.014 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       -0.007 | Polymarket devant
    -10min |       -0.005 | Polymarket devant
     -5min |       +0.003 | Polymarket devant
     +0min |       +0.064 | simultané  <<<
     +5min |       +0.052 | Pinnacle devant
    +10min |       +0.023 | Pinnacle devant
    +15min |       +0.009 | Pinnacle devant
    +20min |       +0.006 | Pinnacle devant
    +25min |       +0.004 | Pinnacle devant
    +30min |       +0.007 | Pinnacle devant
    +35min |       +0.001 | Pinnacle devant
    +40min |       +0.013 | Pinnacle devant
    +45min |       +0.004 | Pinnacle devant
    +50min |       +0.008 | Pinnacle devant
    +55min |       +0.007 | Pinnacle devant
    +60min |       +0.007 | Pinnacle devant

Maximum à +0 min (corrélation +0.064)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.048
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1664329 ticks lus · 398 match(s) exploitables (fourchette max 10 pts)
Books      : 199 match(s), dont 199 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 186 matchs (50943 instants, grille 5 min)
  écart moyen Shin - marché      : +0.10 pts  IC95 [+0.01 ; +0.18]
  écart médian par match : +0.08 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                186       +0.10  [+0.01 ; +0.18]
  proportionnel       186       +0.08  [-0.06 ; +0.22]
  → plus proche de Polymarket : proportionnel (écart 0.08 contre 0.10 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    59 |       +0.18 | [ -0.02 ;  +0.39]
           60-70% |    60 |       +0.20 | [ +0.02 ;  +0.39]
           70-80% |    50 |       -0.04 | [ -0.45 ;  +0.37]
           80-90% |    38 |       -0.01 | [ -0.22 ;  +0.19]
             90%+ |    13 |       -0.05 | [ -0.38 ;  +0.27]

  → biais détectable (+0.10 pts) mais SOUS le seuil de matérialité
    de 0.5 pt. Statistiquement réel, pratiquement sans effet :
    aucune décision du projet ne change pour un tel décalage.
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
      confirme |         0 | trop peu
       infirme |         0 | trop peu
          muet |        92 |       +9.1% |     +13.5% | [  +9.8 ;  +17.2]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1763 résultats · 1737 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 130 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        33     38.6%     42.4%    +3.8  [ -11.3 ;  +20.6]
                        il faudrait ~615 obs pour trancher à cet écart (582 manquantes)
  55 – 70 %        33     61.4%     57.6%    -3.8  [ -20.6 ;  +11.3]
                        il faudrait ~615 obs pour trancher à cet écart (582 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 346 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        71     38.5%     39.4%    +0.9  [  -9.6 ;  +12.5]
                        il faudrait ~11025 obs pour trancher à cet écart (10954 manquantes)
  55 – 70 %        74     61.4%     60.8%    -0.6  [ -12.0 ;   +9.7]
                        il faudrait ~22561 obs pour trancher à cet écart (22487 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1763 résultats · 1737 paires · fenêtre ±5 j
2046 match(s) en contexte · 2046 avec courbe pinnacle
polymarket : 1,212,626 ticks lus · 146 observation(s)
kalshi : 1,664,329 ticks lus · 386 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 532 observation(s)
==========================================================================
  avec résultat connu     : 476
  postérieures au gel     : 476
  avec prix pinnacle    : 532

  par marché (avec résultat) : kalshi 346 · polymarket 130

  par niveau (avec résultat) : grand_chelem 294 · challenger 156 · wta 14 · atp 12

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            29              29
  15 – 30 %           75              75
  30 – 45 %          104             104
  45 – 55 %           57              57
  55 – 70 %          107             107
  70 – 85 %           74              74
  85 – 100 %          30              30

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  391 observation(s) construite(s) · 391 nouvelle(s) · 391 au journal kalshi_lead_obs.jsonl

```
