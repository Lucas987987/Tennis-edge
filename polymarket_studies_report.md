# Études Polymarket/Kalshi — rapport du 2026-10-25

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1978892 ticks lus, 604 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 437 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
405 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.007 | Polymarket devant
    -55min |       +0.003 | Polymarket devant
    -50min |       -0.009 | Polymarket devant
    -45min |       -0.003 | Polymarket devant
    -40min |       -0.001 | Polymarket devant
    -35min |       -0.000 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       -0.003 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       +0.006 | Polymarket devant
     +0min |       +0.164 | simultané  <<<
     +5min |       +0.082 | Pinnacle devant
    +10min |       +0.012 | Pinnacle devant
    +15min |       +0.008 | Pinnacle devant
    +20min |       +0.015 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       -0.006 | Pinnacle devant
    +35min |       +0.011 | Pinnacle devant
    +40min |       +0.000 | Pinnacle devant
    +45min |       -0.003 | Pinnacle devant
    +50min |       +0.003 | Pinnacle devant
    +55min |       -0.007 | Pinnacle devant
    +60min |       +0.005 | Pinnacle devant

Maximum à +0 min (corrélation +0.164)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.043
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1978892 ticks lus · 600 match(s) exploitables (fourchette max 10 pts)
Books      : 439 match(s), dont 437 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 417 matchs (70670 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.05 ; +0.07]
  écart médian par match : -0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                417       +0.01  [-0.05 ; +0.07]
  proportionnel       417       -0.09  [-0.18 ; +0.00]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.09 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   165 |       -0.04 | [ -0.15 ;  +0.07]
           60-70% |   162 |       -0.07 | [ -0.40 ;  +0.25]
           70-80% |   103 |       +0.10 | [ -0.13 ;  +0.33]
           80-90% |    57 |       +0.00 | [ -0.37 ;  +0.38]
             90%+ |    22 |       +0.12 | [ -0.35 ;  +0.59]

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
      confirme |        12 |       +1.4% |      +1.9% | [  -1.7 ;   +5.5]
       infirme |         2 | trop peu
          muet |        81 |      +13.6% |     +16.2% | [ +13.4 ;  +18.9]

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

  HORS ÉCHANTILLON (décisif) — 96 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        21     37.9%     42.9%    +5.0  [ -13.4 ;  +25.6]
                        il faudrait ~366 obs pour trancher à cet écart (345 manquantes)
  55 – 70 %        20     61.7%     60.0%    -1.7  [ -23.1 ;  +16.4]
                        il faudrait ~3051 obs pour trancher à cet écart (3031 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 256 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        58     37.4%     41.4%    +4.0  [  -7.8 ;  +16.8]
                        il faudrait ~570 obs pour trancher à cet écart (512 manquantes)
  55 – 70 %        57     62.5%     59.6%    -2.8  [ -15.8 ;   +8.9]
                        il faudrait ~1115 obs pour trancher à cet écart (1058 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4385 match(s) en contexte · 4374 avec courbe pinnacle
polymarket : 5,772,285 ticks lus · 406 observation(s)
kalshi : 1,978,892 ticks lus · 854 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1260 observation(s)
==========================================================================
  avec résultat connu     : 352
  postérieures au gel     : 352
  avec prix pinnacle    : 1254

  par marché (avec résultat) : kalshi 256 · polymarket 96

  par niveau (avec résultat) : challenger 180 · atp 100 · wta 72

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            18              18
  15 – 30 %           44              44
  30 – 45 %           79              79
  45 – 55 %           70              70
  55 – 70 %           77              77
  70 – 85 %           46              46
  85 – 100 %          18              18

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  889 observation(s) construite(s) · 409 nouvelle(s) · 18921 au journal kalshi_lead_obs.jsonl

```
