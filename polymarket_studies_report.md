# Études Polymarket/Kalshi — rapport du 2026-10-14

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1247533 ticks lus, 617 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 322 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
310 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.014 | Polymarket devant
    -55min |       +0.004 | Polymarket devant
    -50min |       -0.002 | Polymarket devant
    -45min |       +0.008 | Polymarket devant
    -40min |       +0.001 | Polymarket devant
    -35min |       +0.004 | Polymarket devant
    -30min |       -0.010 | Polymarket devant
    -25min |       -0.007 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       +0.004 | Polymarket devant
    -10min |       -0.008 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.105 | simultané  <<<
     +5min |       +0.067 | Pinnacle devant
    +10min |       +0.051 | Pinnacle devant
    +15min |       +0.043 | Pinnacle devant
    +20min |       +0.031 | Pinnacle devant
    +25min |       +0.020 | Pinnacle devant
    +30min |       +0.010 | Pinnacle devant
    +35min |       +0.015 | Pinnacle devant
    +40min |       +0.005 | Pinnacle devant
    +45min |       -0.008 | Pinnacle devant
    +50min |       +0.014 | Pinnacle devant
    +55min |       +0.005 | Pinnacle devant
    +60min |       -0.009 | Pinnacle devant

Maximum à +0 min (corrélation +0.105)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.049
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1247533 ticks lus · 611 match(s) exploitables (fourchette max 10 pts)
Books      : 324 match(s), dont 322 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 312 matchs (53854 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.05 ; +0.09]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                312       +0.02  [-0.05 ; +0.09]
  proportionnel       312       -0.01  [-0.14 ; +0.12]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.02 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   112 |       -0.08 | [ -0.29 ;  +0.12]
           60-70% |   118 |       -0.10 | [ -0.27 ;  +0.08]
           70-80% |    90 |       +0.13 | [ -0.08 ;  +0.34]
           80-90% |    40 |       +0.18 | [ -0.03 ;  +0.39]
             90%+ |    16 |       -0.00 | [ -0.51 ;  +0.51]

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
      confirme |        13 |      +15.4% |     +18.8% | [  +8.6 ;  +29.1]
       infirme |        11 |      +10.9% |      +7.5% | [  -6.8 ;  +21.8]
          muet |       107 |      +11.1% |     +10.4% | [  +8.3 ;  +12.6]

  différentiel confirme - infirme : +11.3 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3603 résultats · 3508 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 172 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        39     37.6%     38.5%    +0.8  [ -12.7 ;  +16.5]
                        il faudrait ~12591 obs pour trancher à cet écart (12552 manquantes)
  55 – 70 %        38     62.2%     60.5%    -1.7  [ -17.5 ;  +12.2]
                        il faudrait ~3287 obs pour trancher à cet écart (3249 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 520 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       115     37.8%     38.3%    +0.5  [  -7.9 ;   +9.6]
                        il faudrait ~43341 obs pour trancher à cet écart (43226 manquantes)
  55 – 70 %       116     61.9%     60.3%    -1.6  [ -10.7 ;   +6.9]
                        il faudrait ~3742 obs pour trancher à cet écart (3626 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3603 résultats · 3508 paires · fenêtre ±5 j
3257 match(s) en contexte · 3246 avec courbe pinnacle
polymarket : 2,475,143 ticks lus · 196 observation(s)
kalshi : 1,247,533 ticks lus · 644 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 840 observation(s)
==========================================================================
  avec résultat connu     : 692
  postérieures au gel     : 692
  avec prix pinnacle    : 836

  par marché (avec résultat) : kalshi 520 · polymarket 172

  par niveau (avec résultat) : challenger 438 · atp 170 · wta 84

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            31              31
  15 – 30 %          102             102
  30 – 45 %          154             154
  45 – 55 %          115             115
  55 – 70 %          154             154
  70 – 85 %          105             105
  85 – 100 %          31              31

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  569 observation(s) construite(s) · 291 nouvelle(s) · 14480 au journal kalshi_lead_obs.jsonl

```
