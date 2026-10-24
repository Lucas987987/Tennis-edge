# Études Polymarket/Kalshi — rapport du 2026-10-24

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1867294 ticks lus, 542 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 422 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
399 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.007 | Polymarket devant
    -55min |       +0.001 | Polymarket devant
    -50min |       -0.005 | Polymarket devant
    -45min |       -0.004 | Polymarket devant
    -40min |       +0.000 | Polymarket devant
    -35min |       -0.004 | Polymarket devant
    -30min |       +0.002 | Polymarket devant
    -25min |       -0.006 | Polymarket devant
    -20min |       -0.000 | Polymarket devant
    -15min |       -0.005 | Polymarket devant
    -10min |       -0.001 | Polymarket devant
     -5min |       +0.005 | Polymarket devant
     +0min |       +0.152 | simultané  <<<
     +5min |       +0.084 | Pinnacle devant
    +10min |       +0.013 | Pinnacle devant
    +15min |       +0.004 | Pinnacle devant
    +20min |       +0.019 | Pinnacle devant
    +25min |       +0.011 | Pinnacle devant
    +30min |       -0.006 | Pinnacle devant
    +35min |       +0.011 | Pinnacle devant
    +40min |       -0.004 | Pinnacle devant
    +45min |       -0.002 | Pinnacle devant
    +50min |       +0.003 | Pinnacle devant
    +55min |       -0.008 | Pinnacle devant
    +60min |       +0.008 | Pinnacle devant

Maximum à +0 min (corrélation +0.152)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.042
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1867294 ticks lus · 535 match(s) exploitables (fourchette max 10 pts)
Books      : 423 match(s), dont 422 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 404 matchs (72054 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.05 ; +0.06]
  écart médian par match : -0.00 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                404       +0.01  [-0.05 ; +0.06]
  proportionnel       404       -0.08  [-0.17 ; +0.01]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   160 |       -0.04 | [ -0.15 ;  +0.07]
           60-70% |   160 |       -0.06 | [ -0.39 ;  +0.26]
           70-80% |   105 |       +0.10 | [ -0.13 ;  +0.33]
           80-90% |    52 |       +0.02 | [ -0.38 ;  +0.41]
             90%+ |    18 |       +0.00 | [ -0.47 ;  +0.47]

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
          muet |        78 |      +14.1% |     +16.5% | [ +13.7 ;  +19.3]

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

  HORS ÉCHANTILLON (décisif) — 124 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        24     37.5%     41.7%    +4.1  [ -13.1 ;  +23.6]
                        il faudrait ~530 obs pour trancher à cet écart (506 manquantes)
  55 – 70 %        23     62.1%     60.9%    -1.3  [ -21.3 ;  +15.7]
                        il faudrait ~5686 obs pour trancher à cet écart (5663 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 306 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        67     37.4%     38.8%    +1.4  [  -9.3 ;  +13.4]
                        il faudrait ~4335 obs pour trancher à cet écart (4268 manquantes)
  55 – 70 %        66     62.6%     62.1%    -0.4  [ -12.5 ;  +10.3]
                        il faudrait ~48259 obs pour trancher à cet écart (48193 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4338 match(s) en contexte · 4327 avec courbe pinnacle
polymarket : 4,871,419 ticks lus · 376 observation(s)
kalshi : 1,867,294 ticks lus · 826 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1202 observation(s)
==========================================================================
  avec résultat connu     : 430
  postérieures au gel     : 430
  avec prix pinnacle    : 1200

  par marché (avec résultat) : kalshi 306 · polymarket 124

  par niveau (avec résultat) : challenger 242 · atp 104 · wta 84

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            18              18
  15 – 30 %           58              58
  30 – 45 %           91              91
  45 – 55 %           96              96
  55 – 70 %           89              89
  70 – 85 %           60              60
  85 – 100 %          18              18

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  782 observation(s) construite(s) · 323 nouvelle(s) · 18512 au journal kalshi_lead_obs.jsonl

```
