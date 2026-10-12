# Études Polymarket/Kalshi — rapport du 2026-10-12

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1393124 ticks lus, 646 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 333 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
307 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.003 | Polymarket devant
    -55min |       +0.009 | Polymarket devant
    -50min |       -0.002 | Polymarket devant
    -45min |       +0.005 | Polymarket devant
    -40min |       -0.003 | Polymarket devant
    -35min |       -0.000 | Polymarket devant
    -30min |       -0.001 | Polymarket devant
    -25min |       -0.010 | Polymarket devant
    -20min |       +0.001 | Polymarket devant
    -15min |       +0.005 | Polymarket devant
    -10min |       -0.003 | Polymarket devant
     -5min |       -0.006 | Polymarket devant
     +0min |       +0.085 | simultané  <<<
     +5min |       +0.058 | Pinnacle devant
    +10min |       +0.049 | Pinnacle devant
    +15min |       +0.036 | Pinnacle devant
    +20min |       +0.013 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.014 | Pinnacle devant
    +35min |       +0.016 | Pinnacle devant
    +40min |       +0.002 | Pinnacle devant
    +45min |       -0.003 | Pinnacle devant
    +50min |       +0.015 | Pinnacle devant
    +55min |       +0.001 | Pinnacle devant
    +60min |       +0.006 | Pinnacle devant

Maximum à +0 min (corrélation +0.085)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.051
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1393124 ticks lus · 640 match(s) exploitables (fourchette max 10 pts)
Books      : 336 match(s), dont 333 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 314 matchs (50812 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.05 ; +0.09]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                314       +0.02  [-0.05 ; +0.09]
  proportionnel       314       -0.02  [-0.15 ; +0.11]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.02 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   106 |       +0.02 | [ -0.11 ;  +0.14]
           60-70% |   113 |       -0.16 | [ -0.36 ;  +0.03]
           70-80% |    79 |       +0.13 | [ -0.08 ;  +0.33]
           80-90% |    41 |       +0.03 | [ -0.19 ;  +0.25]
             90%+ |    20 |       +0.21 | [ -0.21 ;  +0.63]

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
      confirme |        10 |       +8.5% |     +16.2% | [  +3.5 ;  +28.8]
       infirme |         1 | trop peu
          muet |        82 |      +10.1% |     +10.1% | [  +8.5 ;  +11.6]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3440 résultats · 3350 paires · fenêtre ±5 j

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
  30 – 45 %        39     38.2%     43.6%    +5.3  [  -8.9 ;  +20.8]
                        il faudrait ~318 obs pour trancher à cet écart (279 manquantes)
  55 – 70 %        40     61.6%     55.0%    -6.6  [ -21.8 ;   +7.7]
                        il faudrait ~210 obs pour trancher à cet écart (170 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 554 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       128     38.0%     36.7%    -1.3  [  -9.1 ;   +7.4]
                        il faudrait ~5650 obs pour trancher à cet écart (5522 manquantes)
  55 – 70 %       133     61.8%     60.2%    -1.7  [ -10.2 ;   +6.3]
                        il faudrait ~3270 obs pour trancher à cet écart (3137 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3440 résultats · 3350 paires · fenêtre ±5 j
3177 match(s) en contexte · 3166 avec courbe pinnacle
polymarket : 2,716,668 ticks lus · 216 observation(s)
kalshi : 1,393,124 ticks lus · 652 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 868 observation(s)
==========================================================================
  avec résultat connu     : 726
  postérieures au gel     : 726
  avec prix pinnacle    : 860

  par marché (avec résultat) : kalshi 554 · polymarket 172

  par niveau (avec résultat) : challenger 462 · atp 188 · wta 76

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            40              40
  15 – 30 %           95              95
  30 – 45 %          167             167
  45 – 55 %          116             116
  55 – 70 %          173             173
  70 – 85 %           94              94
  85 – 100 %          41              41

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  930 observation(s) construite(s) · 622 nouvelle(s) · 13606 au journal kalshi_lead_obs.jsonl

```
