# Études Polymarket/Kalshi — rapport du 2026-08-29

```
--- polymarket_flow ---
⚠️ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 16 partition(s), 2577167 ticks lus, 767 match(s) avec série 'match'
Pinnacle   : 275 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
261 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.001 | Polymarket devant
    -55min |       -0.009 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.009 | Polymarket devant
    -40min |       +0.008 | Polymarket devant
    -35min |       +0.002 | Polymarket devant
    -30min |       -0.008 | Polymarket devant
    -25min |       -0.002 | Polymarket devant
    -20min |       +0.013 | Polymarket devant
    -15min |       +0.006 | Polymarket devant
    -10min |       +0.008 | Polymarket devant
     -5min |       -0.007 | Polymarket devant
     +0min |       +0.122 | simultané  <<<
     +5min |       +0.071 | Pinnacle devant
    +10min |       +0.043 | Pinnacle devant
    +15min |       +0.024 | Pinnacle devant
    +20min |       +0.026 | Pinnacle devant
    +25min |       +0.011 | Pinnacle devant
    +30min |       +0.012 | Pinnacle devant
    +35min |       +0.005 | Pinnacle devant
    +40min |       +0.002 | Pinnacle devant
    +45min |       +0.008 | Pinnacle devant
    +50min |       +0.005 | Pinnacle devant
    +55min |       -0.007 | Pinnacle devant
    +60min |       -0.002 | Pinnacle devant

Maximum à +0 min (corrélation +0.122)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.051
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (16 partition(s))
  2577167 ticks lus · 761 match(s) exploitables (fourchette max 10 pts)
Books      : 280 match(s), dont 275 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 269 matchs (39168 instants, grille 5 min)
  écart moyen Shin - marché      : +0.04 pts  IC95 [-0.04 ; +0.12]
  écart médian par match : -0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                269       +0.04  [-0.04 ; +0.12]
  proportionnel       269       -0.01  [-0.14 ; +0.12]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   117 |       +0.01 | [ -0.16 ;  +0.19]
           60-70% |   129 |       -0.02 | [ -0.20 ;  +0.17]
           70-80% |    70 |       -0.10 | [ -0.49 ;  +0.29]
           80-90% |    33 |       +0.04 | [ -0.33 ;  +0.40]
             90%+ |     8 |       -0.54 | [ -1.55 ;  +0.47]

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
      confirme |        65 |      +10.4% |     +12.5% | [ +10.6 ;  +14.3]
       infirme |         9 |       +2.8% |      +4.1% | [  -1.8 ;  +10.0]
          muet |       197 |      +10.7% |     +16.1% | [ +13.7 ;  +18.5]

  différentiel confirme - infirme : +8.4 pts de CLV
  → intervalles disjoints. Piste à geler et valider hors échantillon.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1537 résultats · 1513 paires · fenêtre ±3 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 142 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        48     37.8%     39.6%    +1.8  [ -10.7 ;  +15.9]
                        il faudrait ~2717 obs pour trancher à cet écart (2669 manquantes)
  55 – 70 %        48     62.2%     60.4%    -1.8  [ -15.9 ;  +10.7]
                        il faudrait ~2717 obs pour trancher à cet écart (2669 manquantes)

  origine (pour mémoire) — 146 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        42     37.7%     38.1%    +0.4  [ -12.7 ;  +15.5]
  55 – 70 %        44     62.0%     63.6%    +1.7  [ -13.1 ;  +14.3]

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 212 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        63     37.2%     39.7%    +2.5  [  -8.7 ;  +14.8]
                        il faudrait ~1445 obs pour trancher à cet écart (1382 manquantes)
  55 – 70 %        63     62.6%     58.7%    -3.9  [ -16.2 ;   +7.4]
                        il faudrait ~598 obs pour trancher à cet écart (535 manquantes)

  origine (pour mémoire) — 182 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        48     37.0%     41.7%    +4.7  [  -8.1 ;  +18.8]
  55 – 70 %        48     63.0%     60.4%    -2.6  [ -16.7 ;  +10.0]

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1537 résultats · 1513 paires · fenêtre ±3 j
1846 match(s) en contexte · 1846 avec courbe pinnacle
polymarket : 7,094,772 ticks lus · 408 observation(s)
kalshi : 2,577,167 ticks lus · 554 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 962 observation(s)
==========================================================================
  avec résultat connu     : 682
  postérieures au gel     : 354
  avec prix pinnacle    : 956

  par marché (avec résultat) : kalshi 394 · polymarket 288

  par niveau (avec résultat) : challenger 214 · grand_chelem 200 · atp 160 · wta 108

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            18               3
  15 – 30 %           70              35
  30 – 45 %          201             111
  45 – 55 %          100              55
  55 – 70 %          203             111
  70 – 85 %           73              36
  85 – 100 %          17               3

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
