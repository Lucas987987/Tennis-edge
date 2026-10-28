# Études Polymarket/Kalshi — rapport du 2026-10-28

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 2205448 ticks lus, 656 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 433 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
400 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.003 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       -0.006 | Polymarket devant
    -45min |       +0.000 | Polymarket devant
    -40min |       -0.000 | Polymarket devant
    -35min |       -0.005 | Polymarket devant
    -30min |       -0.006 | Polymarket devant
    -25min |       -0.010 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       -0.010 | Polymarket devant
    -10min |       -0.004 | Polymarket devant
     -5min |       +0.006 | Polymarket devant
     +0min |       +0.184 | simultané  <<<
     +5min |       +0.083 | Pinnacle devant
    +10min |       +0.021 | Pinnacle devant
    +15min |       +0.003 | Pinnacle devant
    +20min |       +0.019 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.005 | Pinnacle devant
    +35min |       +0.001 | Pinnacle devant
    +40min |       -0.005 | Pinnacle devant
    +45min |       +0.002 | Pinnacle devant
    +50min |       +0.004 | Pinnacle devant
    +55min |       -0.010 | Pinnacle devant
    +60min |       +0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.184)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.046
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  2205448 ticks lus · 655 match(s) exploitables (fourchette max 10 pts)
Books      : 435 match(s), dont 433 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 410 matchs (64797 instants, grille 5 min)
  écart moyen Shin - marché      : +0.00 pts  IC95 [-0.06 ; +0.06]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                410       +0.00  [-0.06 ; +0.06]
  proportionnel       410       -0.08  [-0.17 ; +0.02]
  → plus proche de Polymarket : Shin (écart 0.00 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   160 |       -0.01 | [ -0.10 ;  +0.08]
           60-70% |   162 |       -0.07 | [ -0.36 ;  +0.21]
           70-80% |    94 |       +0.13 | [ -0.15 ;  +0.40]
           80-90% |    59 |       -0.09 | [ -0.33 ;  +0.15]
             90%+ |    25 |       +0.21 | [ -0.28 ;  +0.69]

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
      confirme |        15 |       +6.7% |      +8.3% | [  +4.8 ;  +11.8]
       infirme |         0 | trop peu
          muet |        85 |      +10.4% |     +15.2% | [ +11.9 ;  +18.5]

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

  HORS ÉCHANTILLON (décisif) — 64 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        18     37.9%     38.9%    +0.9  [ -17.6 ;  +23.4]
                        il faudrait ~10142 obs pour trancher à cet écart (10124 manquantes)
  55 – 70 %        18     62.1%     61.1%    -0.9  [ -23.4 ;  +17.6]
                        il faudrait ~10142 obs pour trancher à cet écart (10124 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 212 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        53     37.5%     41.5%    +4.0  [  -8.2 ;  +17.4]
                        il faudrait ~553 obs pour trancher à cet écart (500 manquantes)
  55 – 70 %        53     62.5%     58.5%    -4.1  [ -17.5 ;   +8.2]
                        il faudrait ~547 obs pour trancher à cet écart (494 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4561 match(s) en contexte · 4550 avec courbe pinnacle
polymarket : 5,183,918 ticks lus · 388 observation(s)
kalshi : 2,205,448 ticks lus · 854 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1242 observation(s)
==========================================================================
  avec résultat connu     : 276
  postérieures au gel     : 276
  avec prix pinnacle    : 1236

  par marché (avec résultat) : kalshi 212 · polymarket 64

  par niveau (avec résultat) : challenger 142 · atp 90 · wta 44

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             8               8
  15 – 30 %           33              33
  30 – 45 %           71              71
  45 – 55 %           52              52
  55 – 70 %           71              71
  70 – 85 %           33              33
  85 – 100 %           8               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1124 observation(s) construite(s) · 597 nouvelle(s) · 20680 au journal kalshi_lead_obs.jsonl

```
