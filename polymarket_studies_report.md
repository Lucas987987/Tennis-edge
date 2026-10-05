# Études Polymarket/Kalshi — rapport du 2026-10-05

```
--- polymarket_leadlag ---
Polymarket : 7 partition(s), 1601555 ticks lus, 525 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 278 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
251 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.006 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       +0.006 | Polymarket devant
    -45min |       -0.007 | Polymarket devant
    -40min |       -0.007 | Polymarket devant
    -35min |       +0.003 | Polymarket devant
    -30min |       -0.000 | Polymarket devant
    -25min |       -0.005 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       -0.003 | Polymarket devant
    -10min |       -0.003 | Polymarket devant
     -5min |       -0.015 | Polymarket devant
     +0min |       +0.120 | simultané  <<<
     +5min |       +0.041 | Pinnacle devant
    +10min |       +0.015 | Pinnacle devant
    +15min |       +0.012 | Pinnacle devant
    +20min |       +0.022 | Pinnacle devant
    +25min |       +0.008 | Pinnacle devant
    +30min |       +0.012 | Pinnacle devant
    +35min |       +0.011 | Pinnacle devant
    +40min |       -0.010 | Pinnacle devant
    +45min |       +0.013 | Pinnacle devant
    +50min |       -0.004 | Pinnacle devant
    +55min |       +0.013 | Pinnacle devant
    +60min |       +0.014 | Pinnacle devant

Maximum à +0 min (corrélation +0.120)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.046
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (7 partition(s))
  1601555 ticks lus · 523 match(s) exploitables (fourchette max 10 pts)
Books      : 280 match(s), dont 278 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 257 matchs (46754 instants, grille 5 min)
  écart moyen Shin - marché      : +0.05 pts  IC95 [-0.03 ; +0.13]
  écart médian par match : +0.05 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                257       +0.05  [-0.03 ; +0.13]
  proportionnel       257       +0.01  [-0.12 ; +0.15]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    94 |       +0.18 | [ +0.04 ;  +0.33]
           60-70% |   102 |       +0.03 | [ -0.14 ;  +0.21]
           70-80% |    80 |       +0.12 | [ -0.07 ;  +0.31]
           80-90% |    36 |       -0.12 | [ -0.42 ;  +0.18]
             90%+ |    14 |       +0.17 | [ -0.33 ;  +0.67]

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
      confirme |        11 |       +7.5% |      +9.3% | [  +5.3 ;  +13.3]
       infirme |         2 | trop peu
          muet |       114 |      +11.1% |     +13.5% | [ +11.3 ;  +15.7]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  2 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3076 résultats · 3005 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 100 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        21     38.3%     52.4%   +14.0  [  -6.0 ;  +33.3]
                        il faudrait ~47 obs pour trancher à cet écart (26 manquantes)
  55 – 70 %        20     61.3%     45.0%   -16.3  [ -35.4 ;   +4.5]
                        il faudrait ~35 obs pour trancher à cet écart (15 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 482 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       111     38.3%     44.1%    +5.9  [  -3.0 ;  +15.2]
                        il faudrait ~262 obs pour trancher à cet écart (151 manquantes)
  55 – 70 %       112     62.0%     55.4%    -6.6  [ -15.8 ;   +2.3]
                        il faudrait ~209 obs pour trancher à cet écart (97 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3076 résultats · 3005 paires · fenêtre ±5 j
2897 match(s) en contexte · 2886 avec courbe pinnacle
polymarket : 1,814,386 ticks lus · 110 observation(s)
kalshi : 1,601,555 ticks lus · 538 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 648 observation(s)
==========================================================================
  avec résultat connu     : 582
  postérieures au gel     : 582
  avec prix pinnacle    : 640

  par marché (avec résultat) : kalshi 482 · polymarket 100

  par niveau (avec résultat) : challenger 368 · atp 120 · wta 94

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            32              32
  15 – 30 %           96              96
  30 – 45 %          132             132
  45 – 55 %           62              62
  55 – 70 %          132             132
  70 – 85 %           96              96
  85 – 100 %          32              32

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1127 observation(s) construite(s) · 584 nouvelle(s) · 11517 au journal kalshi_lead_obs.jsonl

```
