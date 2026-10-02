# Études Polymarket/Kalshi — rapport du 2026-10-02

```
--- polymarket_leadlag ---
Polymarket : 4 partition(s), 1064025 ticks lus, 342 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 159 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
150 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.000 | Polymarket devant
    -55min |       +0.001 | Polymarket devant
    -50min |       -0.003 | Polymarket devant
    -45min |       +0.004 | Polymarket devant
    -40min |       -0.010 | Polymarket devant
    -35min |       +0.004 | Polymarket devant
    -30min |       -0.006 | Polymarket devant
    -25min |       -0.007 | Polymarket devant
    -20min |       +0.005 | Polymarket devant
    -15min |       -0.007 | Polymarket devant
    -10min |       -0.006 | Polymarket devant
     -5min |       -0.005 | Polymarket devant
     +0min |       +0.103 | simultané  <<<
     +5min |       +0.038 | Pinnacle devant
    +10min |       +0.015 | Pinnacle devant
    +15min |       +0.013 | Pinnacle devant
    +20min |       +0.018 | Pinnacle devant
    +25min |       +0.022 | Pinnacle devant
    +30min |       +0.014 | Pinnacle devant
    +35min |       +0.025 | Pinnacle devant
    +40min |       -0.007 | Pinnacle devant
    +45min |       +0.005 | Pinnacle devant
    +50min |       -0.013 | Pinnacle devant
    +55min |       +0.015 | Pinnacle devant
    +60min |       +0.027 | Pinnacle devant

Maximum à +0 min (corrélation +0.103)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.043
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (4 partition(s))
  1064025 ticks lus · 340 match(s) exploitables (fourchette max 10 pts)
Books      : 160 match(s), dont 159 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 152 matchs (25622 instants, grille 5 min)
  écart moyen Shin - marché      : +0.04 pts  IC95 [-0.06 ; +0.14]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                152       +0.04  [-0.06 ; +0.14]
  proportionnel       152       +0.07  [-0.11 ; +0.24]
  → plus proche de Polymarket : Shin (écart 0.04 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    56 |       +0.23 | [ +0.04 ;  +0.42]
           60-70% |    69 |       +0.00 | [ -0.21 ;  +0.21]
           70-80% |    50 |       +0.16 | [ -0.11 ;  +0.42]
           80-90% |    18 |       +0.09 | [ -0.36 ;  +0.55]

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
      confirme |        10 |       +9.1% |     +10.2% | [  +6.3 ;  +14.1]
       infirme |         2 | trop peu
          muet |        96 |      +11.9% |     +14.4% | [ +11.8 ;  +16.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2974 résultats · 2903 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 26 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %         8   trop peu
  55 – 70 %         8   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 282 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        70     38.1%     45.7%    +7.6  [  -3.6 ;  +19.2]
                        il faudrait ~159 obs pour trancher à cet écart (89 manquantes)
  55 – 70 %        70     62.0%     54.3%    -7.7  [ -19.3 ;   +3.5]
                        il faudrait ~154 obs pour trancher à cet écart (84 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2974 résultats · 2903 paires · fenêtre ±5 j
1188 match(s) en contexte · 1177 avec courbe pinnacle
polymarket : 805,428 ticks lus · 28 observation(s)
kalshi : 1,064,025 ticks lus · 318 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 346 observation(s)
==========================================================================
  avec résultat connu     : 308
  postérieures au gel     : 308
  avec prix pinnacle    : 344

  par marché (avec résultat) : kalshi 282 · polymarket 26

  par niveau (avec résultat) : challenger 208 · atp 58 · wta 42

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             8               8
  15 – 30 %           54              54
  30 – 45 %           78              78
  45 – 55 %           28              28
  55 – 70 %           78              78
  70 – 85 %           54              54
  85 – 100 %           8               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1537 observation(s) construite(s) · 959 nouvelle(s) · 10327 au journal kalshi_lead_obs.jsonl

```
