# Études Polymarket/Kalshi — rapport du 2026-11-21

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1166958 ticks lus, 411 match(s) avec série 'match'
  book_curves_live.jsonl: 2201 courbes reconstruites | 222679 points | 4 partitions
Pinnacle   : 125 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
108 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.006 | Polymarket devant
    -55min |       -0.014 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       -0.002 | Polymarket devant
    -40min |       +0.000 | Polymarket devant
    -35min |       -0.012 | Polymarket devant
    -30min |       -0.001 | Polymarket devant
    -25min |       -0.011 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.008 | Polymarket devant
    -10min |       +0.008 | Polymarket devant
     -5min |       +0.037 | Polymarket devant
     +0min |       +0.033 | simultané
     +5min |       +0.077 | Pinnacle devant  <<<
    +10min |       +0.025 | Pinnacle devant
    +15min |       -0.006 | Pinnacle devant
    +20min |       +0.017 | Pinnacle devant
    +25min |       +0.017 | Pinnacle devant
    +30min |       -0.008 | Pinnacle devant
    +35min |       -0.010 | Pinnacle devant
    +40min |       -0.002 | Pinnacle devant
    +45min |       -0.006 | Pinnacle devant
    +50min |       -0.000 | Pinnacle devant
    +55min |       -0.013 | Pinnacle devant
    +60min |       +0.014 | Pinnacle devant

Maximum à +5 min (corrélation +0.077)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.074
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1166958 ticks lus · 410 match(s) exploitables (fourchette max 10 pts)
Books      : 135 match(s), dont 125 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 116 matchs (11637 instants, grille 5 min)
  écart moyen Shin - marché      : -0.01 pts  IC95 [-0.13 ; +0.11]
  écart médian par match : +0.06 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                116       -0.01  [-0.13 ; +0.11]
  proportionnel       116       +0.01  [-0.18 ; +0.19]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.01 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    35 |       -0.00 | [ -0.27 ;  +0.27]
           60-70% |    48 |       -0.07 | [ -0.25 ;  +0.11]
           70-80% |    30 |       -0.11 | [ -0.36 ;  +0.13]
           80-90% |    17 |       +0.39 | [ +0.09 ;  +0.68]

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
      confirme |         7 |      +11.9% |     +15.8% | [  +5.4 ;  +26.1]
       infirme |         0 | trop peu
          muet |         6 |      +13.0% |     +15.8% | [  +6.2 ;  +25.4]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3856 résultats · 3753 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 0 observation(s)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 0 observation(s)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3856 résultats · 3753 paires · fenêtre ±5 j
4976 match(s) en contexte · 4949 avec courbe pinnacle
polymarket : 2,880,968 ticks lus · 112 observation(s)
kalshi : 1,166,958 ticks lus · 264 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 376 observation(s)
==========================================================================
  avec résultat connu     : 0
  postérieures au gel     : 0
  avec prix pinnacle    : 354

  par marché (avec résultat) : 

  par niveau (avec résultat) : 

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             0               0
  15 – 30 %            0               0
  30 – 45 %            0               0
  45 – 55 %            0               0
  55 – 70 %            0               0
  70 – 85 %            0               0
  85 – 100 %           0               0

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1035 observation(s) construite(s) · 533 nouvelle(s) · 31830 au journal kalshi_lead_obs.jsonl

```
