# Études Polymarket/Kalshi — rapport du 2026-10-08

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1888770 ticks lus, 620 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 349 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
317 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.007 | Polymarket devant
    -55min |       -0.000 | Polymarket devant
    -50min |       +0.009 | Polymarket devant
    -45min |       -0.005 | Polymarket devant
    -40min |       -0.002 | Polymarket devant
    -35min |       -0.003 | Polymarket devant
    -30min |       -0.007 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       -0.003 | Polymarket devant
    -15min |       -0.003 | Polymarket devant
    -10min |       +0.002 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.108 | simultané  <<<
     +5min |       +0.059 | Pinnacle devant
    +10min |       +0.028 | Pinnacle devant
    +15min |       +0.017 | Pinnacle devant
    +20min |       +0.025 | Pinnacle devant
    +25min |       +0.011 | Pinnacle devant
    +30min |       +0.014 | Pinnacle devant
    +35min |       +0.005 | Pinnacle devant
    +40min |       +0.002 | Pinnacle devant
    +45min |       +0.009 | Pinnacle devant
    +50min |       +0.008 | Pinnacle devant
    +55min |       +0.015 | Pinnacle devant
    +60min |       -0.000 | Pinnacle devant

Maximum à +0 min (corrélation +0.108)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.056
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1888770 ticks lus · 620 match(s) exploitables (fourchette max 10 pts)
Books      : 350 match(s), dont 349 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 328 matchs (54190 instants, grille 5 min)
  écart moyen Shin - marché      : +0.03 pts  IC95 [-0.04 ; +0.10]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                328       +0.03  [-0.04 ; +0.10]
  proportionnel       328       -0.06  [-0.18 ; +0.06]
  → plus proche de Polymarket : Shin (écart 0.03 contre 0.06 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   117 |       +0.04 | [ -0.08 ;  +0.16]
           60-70% |   124 |       -0.00 | [ -0.20 ;  +0.19]
           70-80% |    91 |       +0.12 | [ -0.07 ;  +0.31]
           80-90% |    51 |       -0.09 | [ -0.33 ;  +0.14]
             90%+ |    18 |       +0.25 | [ -0.23 ;  +0.73]

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
      confirme |         8 |      +12.7% |     +10.1% | [  +4.5 ;  +15.6]
       infirme |         1 | trop peu
          muet |       118 |       +9.1% |     +10.0% | [  +8.3 ;  +11.7]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  2 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3231 résultats · 3158 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 140 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        27     38.2%     44.4%    +6.2  [ -10.7 ;  +24.4]
                        il faudrait ~236 obs pour trancher à cet écart (209 manquantes)
  55 – 70 %        27     61.2%     51.9%    -9.4  [ -27.2 ;   +8.1]
                        il faudrait ~105 obs pour trancher à cet écart (78 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 622 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       145     38.2%     40.7%    +2.4  [  -5.2 ;  +10.6]
                        il faudrait ~1518 obs pour trancher à cet écart (1373 manquantes)
  55 – 70 %       150     61.8%     57.3%    -4.5  [ -12.5 ;   +3.1]
                        il faudrait ~446 obs pour trancher à cet écart (296 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3231 résultats · 3158 paires · fenêtre ±5 j
3017 match(s) en contexte · 3006 avec courbe pinnacle
polymarket : 2,463,134 ticks lus · 150 observation(s)
kalshi : 1,888,770 ticks lus · 676 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 826 observation(s)
==========================================================================
  avec résultat connu     : 762
  postérieures au gel     : 762
  avec prix pinnacle    : 820

  par marché (avec résultat) : kalshi 622 · polymarket 140

  par niveau (avec résultat) : challenger 472 · atp 180 · wta 110

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            45              45
  15 – 30 %          115             115
  30 – 45 %          172             172
  45 – 55 %           94              94
  55 – 70 %          177             177
  70 – 85 %          113             113
  85 – 100 %          46              46

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  519 observation(s) construite(s) · 113 nouvelle(s) · 12382 au journal kalshi_lead_obs.jsonl

```
