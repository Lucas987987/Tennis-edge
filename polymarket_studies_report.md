# Études Polymarket/Kalshi — rapport du 2026-10-11

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1344235 ticks lus, 607 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 320 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
298 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.001 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       +0.006 | Polymarket devant
    -40min |       +0.001 | Polymarket devant
    -35min |       -0.002 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.012 | Polymarket devant
    -20min |       -0.002 | Polymarket devant
    -15min |       +0.004 | Polymarket devant
    -10min |       +0.005 | Polymarket devant
     -5min |       -0.002 | Polymarket devant
     +0min |       +0.091 | simultané  <<<
     +5min |       +0.048 | Pinnacle devant
    +10min |       +0.049 | Pinnacle devant
    +15min |       +0.032 | Pinnacle devant
    +20min |       +0.015 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       +0.013 | Pinnacle devant
    +35min |       +0.007 | Pinnacle devant
    +40min |       -0.002 | Pinnacle devant
    +45min |       +0.004 | Pinnacle devant
    +50min |       +0.012 | Pinnacle devant
    +55min |       +0.005 | Pinnacle devant
    +60min |       +0.002 | Pinnacle devant

Maximum à +0 min (corrélation +0.091)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.053
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1344235 ticks lus · 593 match(s) exploitables (fourchette max 10 pts)
Books      : 321 match(s), dont 320 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 303 matchs (54677 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.05 ; +0.09]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                303       +0.02  [-0.05 ; +0.09]
  proportionnel       303       -0.06  [-0.18 ; +0.07]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.06 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   103 |       -0.02 | [ -0.14 ;  +0.11]
           60-70% |   112 |       -0.04 | [ -0.24 ;  +0.17]
           70-80% |    75 |       +0.11 | [ -0.10 ;  +0.31]
           80-90% |    43 |       -0.02 | [ -0.24 ;  +0.21]
             90%+ |    18 |       +0.25 | [ -0.23 ;  +0.74]

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
      confirme |        10 |       +8.5% |     +16.2% | [  +3.5 ;  +28.8]
       infirme |         1 | trop peu
          muet |        83 |      +10.2% |     +10.1% | [  +8.5 ;  +11.6]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  1 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3367 résultats · 3278 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 212 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        44     37.7%     40.9%    +3.2  [ -10.1 ;  +17.9]
                        il faudrait ~898 obs pour trancher à cet écart (854 manquantes)
  55 – 70 %        44     61.9%     56.8%    -5.1  [ -19.7 ;   +8.4]
                        il faudrait ~348 obs pour trancher à cet écart (304 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 570 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       131     37.9%     36.6%    -1.2  [  -9.0 ;   +7.3]
                        il faudrait ~5804 obs pour trancher à cet écart (5673 manquantes)
  55 – 70 %       136     62.0%     59.6%    -2.5  [ -10.9 ;   +5.4]
                        il faudrait ~1474 obs pour trancher à cet écart (1338 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3367 résultats · 3278 paires · fenêtre ±5 j
3137 match(s) en contexte · 3126 avec courbe pinnacle
polymarket : 2,630,534 ticks lus · 224 observation(s)
kalshi : 1,344,235 ticks lus · 622 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 846 observation(s)
==========================================================================
  avec résultat connu     : 782
  postérieures au gel     : 782
  avec prix pinnacle    : 842

  par marché (avec résultat) : kalshi 570 · polymarket 212

  par niveau (avec résultat) : challenger 470 · atp 220 · wta 92

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            43              43
  15 – 30 %          112             112
  30 – 45 %          175             175
  45 – 55 %          117             117
  55 – 70 %          180             180
  70 – 85 %          111             111
  85 – 100 %          44              44

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  580 observation(s) construite(s) · 239 nouvelle(s) · 12984 au journal kalshi_lead_obs.jsonl

```
