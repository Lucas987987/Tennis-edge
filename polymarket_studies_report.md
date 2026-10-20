# Études Polymarket/Kalshi — rapport du 2026-10-20

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1689829 ticks lus, 627 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 79 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
76 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.011 | Polymarket devant
    -55min |       -0.004 | Polymarket devant
    -50min |       -0.010 | Polymarket devant
    -45min |       -0.002 | Polymarket devant
    -40min |       +0.014 | Polymarket devant
    -35min |       +0.008 | Polymarket devant
    -30min |       -0.023 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       -0.009 | Polymarket devant
    -15min |       -0.003 | Polymarket devant
    -10min |       -0.018 | Polymarket devant
     -5min |       -0.000 | Polymarket devant
     +0min |       +0.166 | simultané  <<<
     +5min |       +0.102 | Pinnacle devant
    +10min |       +0.029 | Pinnacle devant
    +15min |       +0.047 | Pinnacle devant
    +20min |       +0.066 | Pinnacle devant
    +25min |       +0.033 | Pinnacle devant
    +30min |       -0.003 | Pinnacle devant
    +35min |       +0.009 | Pinnacle devant
    +40min |       -0.000 | Pinnacle devant
    +45min |       +0.001 | Pinnacle devant
    +50min |       -0.008 | Pinnacle devant
    +55min |       +0.008 | Pinnacle devant
    +60min |       -0.014 | Pinnacle devant

Maximum à +0 min (corrélation +0.166)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.059
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1689829 ticks lus · 622 match(s) exploitables (fourchette max 10 pts)
Books      : 79 match(s), dont 79 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 76 matchs (10748 instants, grille 5 min)
  écart moyen Shin - marché      : -0.05 pts  IC95 [-0.19 ; +0.09]
  écart médian par match : +0.07 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                 76       -0.05  [-0.19 ; +0.09]
  proportionnel        76       -0.26  [-0.52 ; -0.00]
  → plus proche de Polymarket : Shin (écart 0.05 contre 0.26 pt)

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    30 |       -0.08 | [ -0.33 ;  +0.16]
           60-70% |    29 |       -0.13 | [ -0.48 ;  +0.22]
           70-80% |    30 |       -0.22 | [ -0.57 ;  +0.14]
           80-90% |    14 |       +0.23 | [ -0.12 ;  +0.58]

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
      confirme |         3 | trop peu
       infirme |        10 |      +13.0% |     +14.6% | [ +10.9 ;  +18.4]
          muet |        48 |      +11.1% |      +8.6% | [  +4.3 ;  +12.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3506 résultats · 3412 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 24 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         4   trop peu
  55 – 70 %         3   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 136 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        26     37.8%     38.5%    +0.7  [ -15.4 ;  +19.7]
                        il faudrait ~21129 obs pour trancher à cet écart (21103 manquantes)
  55 – 70 %        25     61.9%     64.0%    +2.1  [ -17.4 ;  +17.8]
                        il faudrait ~2135 obs pour trancher à cet écart (2110 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3506 résultats · 3412 paires · fenêtre ±5 j
3518 match(s) en contexte · 3507 avec courbe pinnacle
polymarket : 4,228,028 ticks lus · 28 observation(s)
kalshi : 1,689,829 ticks lus · 154 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 182 observation(s)
==========================================================================
  avec résultat connu     : 160
  postérieures au gel     : 160
  avec prix pinnacle    : 182

  par marché (avec résultat) : kalshi 136 · polymarket 24

  par niveau (avec résultat) : challenger 136 · wta 16 · atp 8

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             3               3
  15 – 30 %           35              35
  30 – 45 %           30              30
  45 – 55 %           24              24
  55 – 70 %           28              28
  70 – 85 %           37              37
  85 – 100 %           3               3

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1075 observation(s) construite(s) · 652 nouvelle(s) · 16962 au journal kalshi_lead_obs.jsonl

```
