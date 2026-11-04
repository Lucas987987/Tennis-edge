# Études Polymarket/Kalshi — rapport du 2026-11-04

```
--- polymarket_leadlag ---
Polymarket : 10 partition(s), 2719753 ticks lus, 803 match(s) avec série 'match'
  book_curves_live.jsonl: 6902 courbes reconstruites | 863445 points | 4 partitions
Pinnacle   : 601 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
581 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.001 | Polymarket devant
    -55min |       -0.003 | Polymarket devant
    -50min |       -0.009 | Polymarket devant
    -45min |       +0.008 | Polymarket devant
    -40min |       +0.003 | Polymarket devant
    -35min |       -0.002 | Polymarket devant
    -30min |       -0.007 | Polymarket devant
    -25min |       +0.007 | Polymarket devant
    -20min |       -0.001 | Polymarket devant
    -15min |       +0.007 | Polymarket devant
    -10min |       +0.028 | Polymarket devant
     -5min |       +0.058 | Polymarket devant
     +0min |       +0.094 | simultané  <<<
     +5min |       +0.035 | Pinnacle devant
    +10min |       +0.013 | Pinnacle devant
    +15min |       +0.004 | Pinnacle devant
    +20min |       -0.001 | Pinnacle devant
    +25min |       +0.004 | Pinnacle devant
    +30min |       +0.006 | Pinnacle devant
    +35min |       +0.005 | Pinnacle devant
    +40min |       +0.005 | Pinnacle devant
    +45min |       +0.001 | Pinnacle devant
    +50min |       -0.005 | Pinnacle devant
    +55min |       +0.004 | Pinnacle devant
    +60min |       -0.006 | Pinnacle devant

Maximum à +0 min (corrélation +0.094)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.038
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (10 partition(s))
  2719753 ticks lus · 799 match(s) exploitables (fourchette max 10 pts)
Books      : 638 match(s), dont 601 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 591 matchs (96546 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.03 ; +0.07]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                591       +0.02  [-0.03 ; +0.07]
  proportionnel       591       -0.05  [-0.13 ; +0.04]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   181 |       +0.24 | [ -0.07 ;  +0.55]
           60-70% |   229 |       +0.00 | [ -0.11 ;  +0.12]
           70-80% |   155 |       +0.04 | [ -0.15 ;  +0.23]
           80-90% |    97 |       -0.07 | [ -0.29 ;  +0.14]
             90%+ |    36 |       +0.03 | [ -0.39 ;  +0.45]

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
      confirme |        86 |       +7.0% |     +12.9% | [  +6.9 ;  +19.0]
       infirme |         2 | trop peu
          muet |        65 |       +9.5% |     +15.4% | [ +11.1 ;  +19.6]

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
ResultIndex : 3806 résultats · 3704 paires · fenêtre ±5 j
5181 match(s) en contexte · 5059 avec courbe pinnacle
polymarket : 5,210,740 ticks lus · 352 observation(s)
kalshi : 2,719,753 ticks lus · 1271 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 1623 observation(s)
==========================================================================
  avec résultat connu     : 0
  postérieures au gel     : 0
  avec prix pinnacle    : 1504

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
  1250 observation(s) construite(s) · 569 nouvelle(s) · 25306 au journal kalshi_lead_obs.jsonl

```
