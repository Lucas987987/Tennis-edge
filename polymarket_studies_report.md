# Études Polymarket/Kalshi — rapport du 2026-10-18

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1226179 ticks lus, 574 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 158 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
151 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.023 | Polymarket devant
    -55min |       +0.016 | Polymarket devant
    -50min |       +0.009 | Polymarket devant
    -45min |       -0.014 | Polymarket devant
    -40min |       +0.012 | Polymarket devant
    -35min |       +0.013 | Polymarket devant
    -30min |       -0.028 | Polymarket devant
    -25min |       -0.013 | Polymarket devant
    -20min |       +0.003 | Polymarket devant
    -15min |       +0.004 | Polymarket devant
    -10min |       -0.009 | Polymarket devant
     -5min |       -0.000 | Polymarket devant
     +0min |       +0.134 | simultané  <<<
     +5min |       +0.078 | Pinnacle devant
    +10min |       +0.050 | Pinnacle devant
    +15min |       +0.033 | Pinnacle devant
    +20min |       +0.040 | Pinnacle devant
    +25min |       +0.014 | Pinnacle devant
    +30min |       +0.014 | Pinnacle devant
    +35min |       +0.020 | Pinnacle devant
    +40min |       -0.005 | Pinnacle devant
    +45min |       -0.003 | Pinnacle devant
    +50min |       +0.014 | Pinnacle devant
    +55min |       -0.002 | Pinnacle devant
    +60min |       -0.015 | Pinnacle devant

Maximum à +0 min (corrélation +0.134)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.074
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1226179 ticks lus · 569 match(s) exploitables (fourchette max 10 pts)
Books      : 160 match(s), dont 158 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 153 matchs (17937 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.08 ; +0.11]
  écart médian par match : +0.06 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                153       +0.01  [-0.08 ; +0.11]
  proportionnel       153       -0.08  [-0.27 ; +0.10]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    55 |       -0.01 | [ -0.18 ;  +0.17]
           60-70% |    56 |       -0.17 | [ -0.38 ;  +0.05]
           70-80% |    48 |       +0.04 | [ -0.22 ;  +0.30]
           80-90% |    21 |       +0.28 | [ +0.00 ;  +0.56]
             90%+ |    11 |       -0.04 | [ -0.31 ;  +0.24]

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
      confirme |        12 |      +15.9% |     +20.2% | [  +9.4 ;  +30.9]
       infirme |        10 |      +13.0% |     +14.6% | [ +10.9 ;  +18.4]
          muet |        61 |      +10.4% |      +8.6% | [  +5.1 ;  +12.0]

  différentiel confirme - infirme : +5.6 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3563 résultats · 3468 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 68 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        12   trop peu
  55 – 70 %        11   trop peu

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 282 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        54     38.0%     38.9%    +0.9  [ -11.0 ;  +14.2]
                        il faudrait ~11950 obs pour trancher à cet écart (11896 manquantes)
  55 – 70 %        54     61.7%     63.0%    +1.2  [ -12.1 ;  +12.9]
                        il faudrait ~5896 obs pour trancher à cet écart (5842 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3563 résultats · 3468 paires · fenêtre ±5 j
3518 match(s) en contexte · 3507 avec courbe pinnacle
polymarket : 3,725,639 ticks lus · 84 observation(s)
kalshi : 1,226,179 ticks lus · 316 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 400 observation(s)
==========================================================================
  avec résultat connu     : 350
  postérieures au gel     : 350
  avec prix pinnacle    : 396

  par marché (avec résultat) : kalshi 282 · polymarket 68

  par niveau (avec résultat) : challenger 234 · wta 72 · atp 44

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            20              20
  15 – 30 %           57              57
  30 – 45 %           66              66
  45 – 55 %           63              63
  55 – 70 %           65              65
  70 – 85 %           59              59
  85 – 100 %          20              20

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  625 observation(s) construite(s) · 280 nouvelle(s) · 15835 au journal kalshi_lead_obs.jsonl

```
