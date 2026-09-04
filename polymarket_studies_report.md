# Études Polymarket/Kalshi — rapport du 2026-09-04

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1672567 ticks lus, 407 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 166 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
144 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.006 | Polymarket devant
    -55min |       -0.009 | Polymarket devant
    -50min |       +0.014 | Polymarket devant
    -45min |       -0.006 | Polymarket devant
    -40min |       +0.005 | Polymarket devant
    -35min |       +0.022 | Polymarket devant
    -30min |       -0.018 | Polymarket devant
    -25min |       -0.015 | Polymarket devant
    -20min |       +0.015 | Polymarket devant
    -15min |       -0.006 | Polymarket devant
    -10min |       -0.000 | Polymarket devant
     -5min |       +0.000 | Polymarket devant
     +0min |       +0.041 | simultané
     +5min |       +0.054 | Pinnacle devant  <<<
    +10min |       +0.006 | Pinnacle devant
    +15min |       +0.013 | Pinnacle devant
    +20min |       +0.021 | Pinnacle devant
    +25min |       +0.011 | Pinnacle devant
    +30min |       +0.020 | Pinnacle devant
    +35min |       +0.008 | Pinnacle devant
    +40min |       +0.010 | Pinnacle devant
    +45min |       +0.011 | Pinnacle devant
    +50min |       -0.005 | Pinnacle devant
    +55min |       +0.009 | Pinnacle devant
    +60min |       -0.004 | Pinnacle devant

Maximum à +5 min (corrélation +0.054)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.054
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1672567 ticks lus · 401 match(s) exploitables (fourchette max 10 pts)
Books      : 166 match(s), dont 166 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 145 matchs (34126 instants, grille 5 min)
  écart moyen Shin - marché      : +0.13 pts  IC95 [+0.03 ; +0.23]
  écart médian par match : +0.14 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                145       +0.13  [+0.03 ; +0.23]
  proportionnel       145       +0.11  [-0.06 ; +0.28]
  → plus proche de Polymarket : proportionnel (écart 0.11 contre 0.13 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    49 |       +0.21 | [ -0.01 ;  +0.42]
           60-70% |    52 |       +0.20 | [ -0.04 ;  +0.44]
           70-80% |    34 |       +0.06 | [ -0.57 ;  +0.68]
           80-90% |    27 |       -0.03 | [ -0.23 ;  +0.18]
             90%+ |     9 |       +0.07 | [ -0.32 ;  +0.46]

  → biais détectable (+0.13 pts) mais SOUS le seuil de matérialité
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
      confirme |         5 |       +9.6% |      +9.7% | [  +8.8 ;  +10.6]
       infirme |         0 | trop peu
          muet |       108 |       +9.8% |     +12.4% | [ +10.7 ;  +14.1]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1687 résultats · 1661 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 120 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        37     38.6%     48.6%   +10.0  [  -5.2 ;  +25.5]
                        il faudrait ~91 obs pour trancher à cet écart (54 manquantes)
  55 – 70 %        37     61.4%     51.4%   -10.0  [ -25.5 ;   +5.2]
                        il faudrait ~91 obs pour trancher à cet écart (54 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 270 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        62     38.2%     43.5%    +5.3  [  -6.3 ;  +17.7]
                        il faudrait ~321 obs pour trancher à cet écart (259 manquantes)
  55 – 70 %        65     61.5%     56.9%    -4.6  [ -16.7 ;   +6.7]
                        il faudrait ~430 obs pour trancher à cet écart (365 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1687 résultats · 1661 paires · fenêtre ±5 j
1966 match(s) en contexte · 1966 avec courbe pinnacle
polymarket : 1,887,686 ticks lus · 134 observation(s)
kalshi : 1,672,567 ticks lus · 300 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 434 observation(s)
==========================================================================
  avec résultat connu     : 390
  postérieures au gel     : 390
  avec prix pinnacle    : 434

  par marché (avec résultat) : kalshi 270 · polymarket 120

  par niveau (avec résultat) : grand_chelem 256 · challenger 92 · wta 26 · atp 16

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            19              19
  15 – 30 %           50              50
  30 – 45 %           99              99
  45 – 55 %           51              51
  55 – 70 %          102             102
  70 – 85 %           48              48
  85 – 100 %          21              21

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
