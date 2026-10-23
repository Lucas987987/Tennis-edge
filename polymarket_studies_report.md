# Études Polymarket/Kalshi — rapport du 2026-10-23

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1873062 ticks lus, 534 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 420 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
397 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.004 | Polymarket devant
    -55min |       -0.003 | Polymarket devant
    -50min |       -0.006 | Polymarket devant
    -45min |       -0.003 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       -0.002 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.005 | Polymarket devant
    -20min |       -0.002 | Polymarket devant
    -15min |       -0.007 | Polymarket devant
    -10min |       -0.005 | Polymarket devant
     -5min |       +0.004 | Polymarket devant
     +0min |       +0.147 | simultané  <<<
     +5min |       +0.076 | Pinnacle devant
    +10min |       +0.011 | Pinnacle devant
    +15min |       +0.002 | Pinnacle devant
    +20min |       +0.012 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       -0.007 | Pinnacle devant
    +35min |       +0.013 | Pinnacle devant
    +40min |       -0.001 | Pinnacle devant
    +45min |       +0.000 | Pinnacle devant
    +50min |       +0.004 | Pinnacle devant
    +55min |       -0.006 | Pinnacle devant
    +60min |       +0.006 | Pinnacle devant

Maximum à +0 min (corrélation +0.147)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.042
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1873062 ticks lus · 530 match(s) exploitables (fourchette max 10 pts)
Books      : 421 match(s), dont 420 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 402 matchs (69192 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.05 ; +0.07]
  écart médian par match : +0.00 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                402       +0.01  [-0.05 ; +0.07]
  proportionnel       402       -0.09  [-0.18 ; +0.01]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.09 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   159 |       -0.05 | [ -0.16 ;  +0.07]
           60-70% |   155 |       +0.03 | [ -0.28 ;  +0.35]
           70-80% |   104 |       +0.01 | [ -0.11 ;  +0.13]
           80-90% |    46 |       +0.04 | [ -0.39 ;  +0.47]
             90%+ |    20 |       -0.01 | [ -0.44 ;  +0.41]

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
          muet |        73 |      +13.6% |     +16.0% | [ +13.1 ;  +18.9]

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

  HORS ÉCHANTILLON (décisif) — 134 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        28     36.9%     35.7%    -1.2  [ -16.2 ;  +17.2]
                        il faudrait ~6069 obs pour trancher à cet écart (6041 manquantes)
  55 – 70 %        27     62.8%     66.7%    +3.9  [ -15.0 ;  +18.5]
                        il faudrait ~605 obs pour trancher à cet écart (578 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 336 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        78     37.1%     38.5%    +1.4  [  -8.6 ;  +12.5]
                        il faudrait ~4675 obs pour trancher à cet écart (4597 manquantes)
  55 – 70 %        77     62.9%     62.3%    -0.5  [ -11.7 ;   +9.5]
                        il faudrait ~31630 obs pour trancher à cet écart (31553 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
4299 match(s) en contexte · 4288 avec courbe pinnacle
polymarket : 4,408,183 ticks lus · 360 observation(s)
kalshi : 1,873,062 ticks lus · 822 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1182 observation(s)
==========================================================================
  avec résultat connu     : 470
  postérieures au gel     : 470
  avec prix pinnacle    : 1180

  par marché (avec résultat) : kalshi 336 · polymarket 134

  par niveau (avec résultat) : challenger 274 · atp 104 · wta 92

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            21              21
  15 – 30 %           59              59
  30 – 45 %          106             106
  45 – 55 %           98              98
  55 – 70 %          104             104
  70 – 85 %           61              61
  85 – 100 %          21              21

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  947 observation(s) construite(s) · 474 nouvelle(s) · 18189 au journal kalshi_lead_obs.jsonl

```
