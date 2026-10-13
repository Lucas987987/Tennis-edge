# Études Polymarket/Kalshi — rapport du 2026-10-13

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1416112 ticks lus, 673 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 321 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
312 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.011 | Polymarket devant
    -55min |       +0.006 | Polymarket devant
    -50min |       -0.002 | Polymarket devant
    -45min |       +0.007 | Polymarket devant
    -40min |       -0.002 | Polymarket devant
    -35min |       +0.003 | Polymarket devant
    -30min |       -0.008 | Polymarket devant
    -25min |       -0.006 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       +0.005 | Polymarket devant
    -10min |       +0.003 | Polymarket devant
     -5min |       -0.004 | Polymarket devant
     +0min |       +0.106 | simultané  <<<
     +5min |       +0.063 | Pinnacle devant
    +10min |       +0.058 | Pinnacle devant
    +15min |       +0.042 | Pinnacle devant
    +20min |       +0.014 | Pinnacle devant
    +25min |       +0.020 | Pinnacle devant
    +30min |       +0.020 | Pinnacle devant
    +35min |       +0.009 | Pinnacle devant
    +40min |       +0.004 | Pinnacle devant
    +45min |       -0.003 | Pinnacle devant
    +50min |       +0.016 | Pinnacle devant
    +55min |       +0.003 | Pinnacle devant
    +60min |       -0.005 | Pinnacle devant

Maximum à +0 min (corrélation +0.106)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.048
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1416112 ticks lus · 668 match(s) exploitables (fourchette max 10 pts)
Books      : 323 match(s), dont 321 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 315 matchs (54484 instants, grille 5 min)
  écart moyen Shin - marché      : -0.01 pts  IC95 [-0.08 ; +0.06]
  écart médian par match : +0.00 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                315       -0.01  [-0.08 ; +0.06]
  proportionnel       315       -0.08  [-0.21 ; +0.05]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   106 |       -0.00 | [ -0.12 ;  +0.11]
           60-70% |   116 |       -0.12 | [ -0.31 ;  +0.07]
           70-80% |    86 |       +0.05 | [ -0.15 ;  +0.24]
           80-90% |    44 |       +0.08 | [ -0.14 ;  +0.31]
             90%+ |    18 |       +0.06 | [ -0.36 ;  +0.48]

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
       infirme |         1 | trop peu
          muet |        99 |      +10.4% |      +9.3% | [  +7.0 ;  +11.6]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3525 résultats · 3432 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 170 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        38     37.9%     39.5%    +1.6  [ -12.3 ;  +17.4]
                        il faudrait ~3689 obs pour trancher à cet écart (3651 manquantes)
  55 – 70 %        37     61.9%     59.5%    -2.4  [ -18.4 ;  +11.8]
                        il faudrait ~1549 obs pour trancher à cet écart (1512 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 536 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       114     38.0%     35.1%    -2.9  [ -11.1 ;   +6.2]
                        il faudrait ~1058 obs pour trancher à cet écart (944 manquantes)
  55 – 70 %       116     61.8%     62.9%    +1.2  [  -7.9 ;   +9.4]
                        il faudrait ~6798 obs pour trancher à cet écart (6682 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3525 résultats · 3432 paires · fenêtre ±5 j
3217 match(s) en contexte · 3206 avec courbe pinnacle
polymarket : 2,573,338 ticks lus · 198 observation(s)
kalshi : 1,416,112 ticks lus · 642 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 840 observation(s)
==========================================================================
  avec résultat connu     : 706
  postérieures au gel     : 706
  avec prix pinnacle    : 836

  par marché (avec résultat) : kalshi 536 · polymarket 170

  par niveau (avec résultat) : challenger 434 · atp 190 · wta 82

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            33              33
  15 – 30 %          108             108
  30 – 45 %          152             152
  45 – 55 %          117             117
  55 – 70 %          153             153
  70 – 85 %          110             110
  85 – 100 %          33              33

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  902 observation(s) construite(s) · 583 nouvelle(s) · 14189 au journal kalshi_lead_obs.jsonl

```
