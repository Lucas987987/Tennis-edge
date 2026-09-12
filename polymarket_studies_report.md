# Études Polymarket/Kalshi — rapport du 2026-09-12

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1239838 ticks lus, 432 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 309 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
274 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.002 | Polymarket devant
    -55min |       -0.004 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       -0.009 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       -0.002 | Polymarket devant
    -30min |       -0.001 | Polymarket devant
    -25min |       -0.010 | Polymarket devant
    -20min |       -0.000 | Polymarket devant
    -15min |       +0.014 | Polymarket devant
    -10min |       -0.003 | Polymarket devant
     -5min |       +0.008 | Polymarket devant
     +0min |       +0.041 | simultané
     +5min |       +0.045 | Pinnacle devant  <<<
    +10min |       +0.041 | Pinnacle devant
    +15min |       +0.017 | Pinnacle devant
    +20min |       +0.011 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.001 | Pinnacle devant
    +35min |       +0.007 | Pinnacle devant
    +40min |       +0.007 | Pinnacle devant
    +45min |       +0.000 | Pinnacle devant
    +50min |       +0.007 | Pinnacle devant
    +55min |       +0.008 | Pinnacle devant
    +60min |       +0.001 | Pinnacle devant

Maximum à +5 min (corrélation +0.045)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.060
→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent
  des paires de matchs sans rapport. Aucun lead/lag démontré.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1239838 ticks lus · 427 match(s) exploitables (fourchette max 10 pts)
Books      : 310 match(s), dont 308 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 282 matchs (47326 instants, grille 5 min)
  écart moyen Shin - marché      : -0.04 pts  IC95 [-0.11 ; +0.04]
  écart médian par match : -0.02 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                282       -0.04  [-0.11 ; +0.04]
  proportionnel       282       -0.01  [-0.13 ; +0.12]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    90 |       -0.23 | [ -0.63 ;  +0.18]
           60-70% |    98 |       +0.11 | [ -0.10 ;  +0.33]
           70-80% |    90 |       -0.13 | [ -0.37 ;  +0.10]
           80-90% |    52 |       -0.12 | [ -0.56 ;  +0.31]
             90%+ |    18 |       +0.05 | [ -0.41 ;  +0.51]

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
       infirme |         0 | trop peu
          muet |       236 |      +16.9% |     +25.4% | [ +20.8 ;  +29.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2036 résultats · 1997 paires · fenêtre ±5 j

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
  30 – 45 %        29     37.9%     41.4%    +3.5  [ -12.4 ;  +21.3]
                        il faudrait ~753 obs pour trancher à cet écart (724 manquantes)
  55 – 70 %        28     61.8%     57.1%    -4.7  [ -22.7 ;  +11.7]
                        il faudrait ~418 obs pour trancher à cet écart (390 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 420 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        88     37.2%     35.2%    -1.9  [ -11.1 ;   +8.5]
                        il faudrait ~2363 obs pour trancher à cet écart (2275 manquantes)
  55 – 70 %        84     62.6%     64.3%    +1.6  [  -9.0 ;  +11.1]
                        il faudrait ~3331 obs pour trancher à cet écart (3247 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2036 résultats · 1997 paires · fenêtre ±5 j
2286 match(s) en contexte · 2286 avec courbe pinnacle
polymarket : 1,745,679 ticks lus · 188 observation(s)
kalshi : 1,239,838 ticks lus · 588 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 776 observation(s)
==========================================================================
  avec résultat connu     : 540
  postérieures au gel     : 540
  avec prix pinnacle    : 772

  par marché (avec résultat) : kalshi 420 · polymarket 120

  par niveau (avec résultat) : challenger 458 · grand_chelem 82

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            29              29
  15 – 30 %           95              95
  30 – 45 %          117             117
  45 – 55 %           58              58
  55 – 70 %          112             112
  70 – 85 %          100             100
  85 – 100 %          29              29

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  683 observation(s) construite(s) · 222 nouvelle(s) · 2398 au journal kalshi_lead_obs.jsonl

```
