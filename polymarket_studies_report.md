# Études Polymarket/Kalshi — rapport du 2026-09-30

```
--- polymarket_leadlag ---
Polymarket : 2 partition(s), 477532 ticks lus, 219 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 39 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
37 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.004 | Polymarket devant
    -55min |       -0.002 | Polymarket devant
    -50min |       -0.040 | Polymarket devant
    -45min |       +0.028 | Polymarket devant
    -40min |       -0.016 | Polymarket devant
    -35min |       +0.050 | Polymarket devant
    -30min |       -0.021 | Polymarket devant
    -25min |       -0.011 | Polymarket devant
    -20min |       +0.013 | Polymarket devant
    -15min |       -0.004 | Polymarket devant
    -10min |       +0.002 | Polymarket devant
     -5min |       +0.010 | Polymarket devant
     +0min |       +0.180 | simultané  <<<
     +5min |       +0.016 | Pinnacle devant
    +10min |       +0.012 | Pinnacle devant
    +15min |       +0.029 | Pinnacle devant
    +20min |       +0.023 | Pinnacle devant
    +25min |       -0.003 | Pinnacle devant
    +30min |       -0.005 | Pinnacle devant
    +35min |       +0.002 | Pinnacle devant
    +40min |       -0.019 | Pinnacle devant
    +45min |       -0.010 | Pinnacle devant
    +50min |       -0.027 | Pinnacle devant
    +55min |       +0.043 | Pinnacle devant
    +60min |       +0.100 | Pinnacle devant

Maximum à +0 min (corrélation +0.180)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.087
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (2 partition(s))
  477532 ticks lus · 217 match(s) exploitables (fourchette max 10 pts)
Books      : 40 match(s), dont 39 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 37 matchs (3198 instants, grille 5 min)
  écart moyen Shin - marché      : -0.04 pts  IC95 [-0.30 ; +0.21]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                 37       -0.04  [-0.30 ; +0.21]
  proportionnel        37       -0.07  [-0.50 ; +0.36]
  → plus proche de Polymarket : Shin (écart 0.04 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    15 |       +0.37 | [ +0.06 ;  +0.68]
           60-70% |    14 |       -0.22 | [ -0.77 ;  +0.34]
           70-80% |    12 |       -0.06 | [ -0.50 ;  +0.39]

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
      confirme |         0 | trop peu
       infirme |         2 | trop peu
          muet |        37 |      +16.1% |     +22.0% | [ +18.0 ;  +25.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2872 résultats · 2801 paires · fenêtre ±5 j

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
  30 – 45 %         0   trop peu
  55 – 70 %         0   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 60 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        13   trop peu
  55 – 70 %        13   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2872 résultats · 2801 paires · fenêtre ±5 j
1068 match(s) en contexte · 1057 avec courbe pinnacle
polymarket : 269,866 ticks lus · 2 observation(s)
kalshi : 477,532 ticks lus · 78 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 80 observation(s)
==========================================================================
  avec résultat connu     : 62
  postérieures au gel     : 62
  avec prix pinnacle    : 78

  par marché (avec résultat) : kalshi 60 · polymarket 2

  par niveau (avec résultat) : challenger 60 · atp 2

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             1               1
  15 – 30 %           15              15
  30 – 45 %           13              13
  45 – 55 %            4               4
  55 – 70 %           13              13
  70 – 85 %           15              15
  85 – 100 %           1               1

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  640 observation(s) construite(s) · 640 nouvelle(s) · 8871 au journal kalshi_lead_obs.jsonl

```
