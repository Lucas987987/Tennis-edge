# Études Polymarket/Kalshi — rapport du 2026-11-25

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1133270 ticks lus, 443 match(s) avec série 'match'
  book_curves_live.jsonl: 4655 courbes reconstruites | 496502 points | 4 partitions
Pinnacle   : 286 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
261 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.002 | Polymarket devant
    -55min |       -0.016 | Polymarket devant
    -50min |       +0.006 | Polymarket devant
    -45min |       +0.002 | Polymarket devant
    -40min |       +0.007 | Polymarket devant
    -35min |       +0.005 | Polymarket devant
    -30min |       -0.019 | Polymarket devant
    -25min |       -0.004 | Polymarket devant
    -20min |       -0.001 | Polymarket devant
    -15min |       +0.002 | Polymarket devant
    -10min |       +0.017 | Polymarket devant
     -5min |       +0.088 | Polymarket devant  <<<
     +0min |       +0.083 | simultané
     +5min |       +0.028 | Pinnacle devant
    +10min |       +0.030 | Pinnacle devant
    +15min |       -0.001 | Pinnacle devant
    +20min |       +0.007 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       -0.002 | Pinnacle devant
    +35min |       +0.004 | Pinnacle devant
    +40min |       -0.005 | Pinnacle devant
    +45min |       -0.009 | Pinnacle devant
    +50min |       -0.010 | Pinnacle devant
    +55min |       -0.000 | Pinnacle devant
    +60min |       +0.000 | Pinnacle devant

Maximum à -5 min (corrélation +0.088)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.076
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1133270 ticks lus · 443 match(s) exploitables (fourchette max 10 pts)
Books      : 328 match(s), dont 286 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 278 matchs (25681 instants, grille 5 min)
  écart moyen Shin - marché      : -0.04 pts  IC95 [-0.12 ; +0.04]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                278       -0.04  [-0.12 ; +0.04]
  proportionnel       278       -0.09  [-0.25 ; +0.07]
  → plus proche de Polymarket : Shin (écart 0.04 contre 0.09 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    66 |       +0.18 | [ +0.01 ;  +0.34]
           60-70% |    79 |       -0.08 | [ -0.25 ;  +0.09]
           70-80% |    76 |       -0.13 | [ -0.30 ;  +0.04]
           80-90% |    60 |       -0.09 | [ -0.26 ;  +0.09]
             90%+ |    39 |       -0.04 | [ -0.30 ;  +0.22]

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
      confirme |        35 |      +14.3% |     +14.9% | [ +11.8 ;  +18.0]
       infirme |         0 | trop peu
          muet |        32 |       +9.7% |     +12.2% | [  +7.5 ;  +16.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3891 résultats · 3788 paires · fenêtre ±5 j

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
  30 – 45 %         1   trop peu
  55 – 70 %         1   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 6 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         3   trop peu
  55 – 70 %         3   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3891 résultats · 3788 paires · fenêtre ±5 j
6008 match(s) en contexte · 5854 avec courbe pinnacle
polymarket : 3,198,032 ticks lus · 252 observation(s)
kalshi : 1,133,270 ticks lus · 632 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 884 observation(s)
==========================================================================
  avec résultat connu     : 8
  postérieures au gel     : 8
  avec prix pinnacle    : 764

  par marché (avec résultat) : kalshi 6 · polymarket 2

  par niveau (avec résultat) : challenger 8

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             0               0
  15 – 30 %            0               0
  30 – 45 %            4               4
  45 – 55 %            0               0
  55 – 70 %            4               4
  70 – 85 %            0               0
  85 – 100 %           0               0

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  882 observation(s) construite(s) · 475 nouvelle(s) · 34874 au journal kalshi_lead_obs.jsonl

```
