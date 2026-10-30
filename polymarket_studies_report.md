# Études Polymarket/Kalshi — rapport du 2026-10-30

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1974104 ticks lus, 567 match(s) avec série 'match'
  book_curves_live.jsonl: 4141 courbes reconstruites | 556408 points | 4 partitions
Pinnacle   : 482 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
455 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.000 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       +0.003 | Polymarket devant
    -45min |       +0.001 | Polymarket devant
    -40min |       +0.007 | Polymarket devant
    -35min |       -0.006 | Polymarket devant
    -30min |       -0.006 | Polymarket devant
    -25min |       -0.004 | Polymarket devant
    -20min |       +0.008 | Polymarket devant
    -15min |       -0.004 | Polymarket devant
    -10min |       +0.020 | Polymarket devant
     -5min |       +0.031 | Polymarket devant
     +0min |       +0.109 | simultané  <<<
     +5min |       +0.049 | Pinnacle devant
    +10min |       +0.013 | Pinnacle devant
    +15min |       +0.012 | Pinnacle devant
    +20min |       +0.010 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.016 | Pinnacle devant
    +35min |       -0.004 | Pinnacle devant
    +40min |       -0.000 | Pinnacle devant
    +45min |       +0.009 | Pinnacle devant
    +50min |       +0.004 | Pinnacle devant
    +55min |       -0.009 | Pinnacle devant
    +60min |       -0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.109)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.055
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1974104 ticks lus · 565 match(s) exploitables (fourchette max 10 pts)
Books      : 495 match(s), dont 482 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 467 matchs (63706 instants, grille 5 min)
  écart moyen Shin - marché      : -0.03 pts  IC95 [-0.08 ; +0.03]
  écart médian par match : -0.05 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                467       -0.03  [-0.08 ; +0.03]
  proportionnel       467       -0.08  [-0.17 ; +0.00]
  → plus proche de Polymarket : Shin (écart 0.03 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   162 |       +0.02 | [ -0.09 ;  +0.12]
           60-70% |   182 |       -0.26 | [ -0.43 ;  -0.09]
           70-80% |   107 |       +0.11 | [ -0.12 ;  +0.34]
           80-90% |    69 |       +0.00 | [ -0.17 ;  +0.17]
             90%+ |    25 |       +0.27 | [ -0.21 ;  +0.74]

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
      confirme |        18 |       +8.6% |     +11.0% | [  +7.2 ;  +14.9]
       infirme |         0 | trop peu
          muet |        62 |       +8.8% |     +12.9% | [  +9.9 ;  +15.9]

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

  HORS ÉCHANTILLON (décisif) — 2 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         1   trop peu
  55 – 70 %         1   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 8 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         2   trop peu
  55 – 70 %         2   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4764 match(s) en contexte · 4732 avec courbe pinnacle
polymarket : 4,709,804 ticks lus · 422 observation(s)
kalshi : 1,974,104 ticks lus · 978 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1400 observation(s)
==========================================================================
  avec résultat connu     : 10
  postérieures au gel     : 10
  avec prix pinnacle    : 1356

  par marché (avec résultat) : kalshi 8 · polymarket 2

  par niveau (avec résultat) : wta 8 · atp 2

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             0               0
  15 – 30 %            0               0
  30 – 45 %            3               3
  45 – 55 %            4               4
  55 – 70 %            3               3
  70 – 85 %            0               0
  85 – 100 %           0               0

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  924 observation(s) construite(s) · 400 nouvelle(s) · 21481 au journal kalshi_lead_obs.jsonl

```
