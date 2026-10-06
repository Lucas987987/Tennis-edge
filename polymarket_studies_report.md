# Études Polymarket/Kalshi — rapport du 2026-10-06

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1902525 ticks lus, 617 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 318 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
290 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.004 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.009 | Polymarket devant
    -40min |       -0.006 | Polymarket devant
    -35min |       +0.003 | Polymarket devant
    -30min |       -0.001 | Polymarket devant
    -25min |       -0.005 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.001 | Polymarket devant
    -10min |       -0.001 | Polymarket devant
     -5min |       -0.012 | Polymarket devant
     +0min |       +0.118 | simultané  <<<
     +5min |       +0.045 | Pinnacle devant
    +10min |       +0.014 | Pinnacle devant
    +15min |       +0.016 | Pinnacle devant
    +20min |       +0.018 | Pinnacle devant
    +25min |       +0.010 | Pinnacle devant
    +30min |       +0.013 | Pinnacle devant
    +35min |       +0.010 | Pinnacle devant
    +40min |       -0.012 | Pinnacle devant
    +45min |       +0.013 | Pinnacle devant
    +50min |       +0.000 | Pinnacle devant
    +55min |       +0.011 | Pinnacle devant
    +60min |       +0.012 | Pinnacle devant

Maximum à +0 min (corrélation +0.118)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.046
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1902525 ticks lus · 615 match(s) exploitables (fourchette max 10 pts)
Books      : 320 match(s), dont 318 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 297 matchs (52065 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.05 ; +0.09]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                297       +0.02  [-0.05 ; +0.09]
  proportionnel       297       -0.06  [-0.19 ; +0.07]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.06 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   108 |       +0.13 | [ -0.01 ;  +0.26]
           60-70% |   117 |       -0.00 | [ -0.17 ;  +0.16]
           70-80% |    85 |       +0.10 | [ -0.08 ;  +0.28]
           80-90% |    45 |       -0.13 | [ -0.40 ;  +0.14]
             90%+ |    16 |       +0.25 | [ -0.20 ;  +0.70]

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
      confirme |        11 |       +7.5% |      +9.3% | [  +5.3 ;  +13.3]
       infirme |         2 | trop peu
          muet |       128 |      +10.9% |     +12.6% | [ +10.6 ;  +14.7]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  2 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3137 résultats · 3065 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 114 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        23     37.9%     47.8%    +9.9  [  -8.7 ;  +29.1]
                        il faudrait ~93 obs pour trancher à cet écart (70 manquantes)
  55 – 70 %        23     61.4%     47.8%   -13.6  [ -32.2 ;   +5.6]
                        il faudrait ~50 obs pour trancher à cet écart (27 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 556 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       126     38.2%     43.7%    +5.5  [  -2.9 ;  +14.2]
                        il faudrait ~301 obs pour trancher à cet écart (175 manquantes)
  55 – 70 %       130     62.0%     54.6%    -7.4  [ -16.0 ;   +0.9]
                        il faudrait ~166 obs pour trancher à cet écart (36 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3137 résultats · 3065 paires · fenêtre ±5 j
2937 match(s) en contexte · 2926 avec courbe pinnacle
polymarket : 2,273,113 ticks lus · 124 observation(s)
kalshi : 1,902,525 ticks lus · 618 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 742 observation(s)
==========================================================================
  avec résultat connu     : 670
  postérieures au gel     : 670
  avec prix pinnacle    : 734

  par marché (avec résultat) : kalshi 556 · polymarket 114

  par niveau (avec résultat) : challenger 428 · atp 142 · wta 100

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            38              38
  15 – 30 %          109             109
  30 – 45 %          149             149
  45 – 55 %           75              75
  55 – 70 %          153             153
  70 – 85 %          107             107
  85 – 100 %          39              39

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1833 observation(s) construite(s) · 752 nouvelle(s) · 12269 au journal kalshi_lead_obs.jsonl

```
