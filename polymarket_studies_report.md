# Études Polymarket/Kalshi — rapport du 2026-09-03

```
--- polymarket_flow ---
❌ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 7 partition(s), 1852562 ticks lus, 411 match(s) avec série 'match'
Pinnacle   : 176 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
155 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.014 | Polymarket devant
    -55min |       -0.014 | Polymarket devant
    -50min |       +0.011 | Polymarket devant
    -45min |       -0.017 | Polymarket devant
    -40min |       +0.002 | Polymarket devant
    -35min |       +0.010 | Polymarket devant
    -30min |       -0.020 | Polymarket devant
    -25min |       -0.005 | Polymarket devant
    -20min |       +0.012 | Polymarket devant
    -15min |       +0.015 | Polymarket devant
    -10min |       +0.001 | Polymarket devant
     -5min |       -0.006 | Polymarket devant
     +0min |       +0.102 | simultané  <<<
     +5min |       +0.077 | Pinnacle devant
    +10min |       +0.032 | Pinnacle devant
    +15min |       -0.003 | Pinnacle devant
    +20min |       +0.021 | Pinnacle devant
    +25min |       +0.008 | Pinnacle devant
    +30min |       +0.008 | Pinnacle devant
    +35min |       +0.006 | Pinnacle devant
    +40min |       -0.013 | Pinnacle devant
    +45min |       +0.013 | Pinnacle devant
    +50min |       -0.003 | Pinnacle devant
    +55min |       +0.002 | Pinnacle devant
    +60min |       -0.002 | Pinnacle devant

Maximum à +0 min (corrélation +0.102)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.044
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (7 partition(s))
  1852562 ticks lus · 405 match(s) exploitables (fourchette max 10 pts)
Books      : 176 match(s), dont 176 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 155 matchs (20468 instants, grille 5 min)
  écart moyen Shin - marché      : +0.02 pts  IC95 [-0.08 ; +0.12]
  écart médian par match : -0.02 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                155       +0.02  [-0.08 ; +0.12]
  proportionnel       155       -0.04  [-0.20 ; +0.11]
  → plus proche de Polymarket : Shin (écart 0.02 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    76 |       +0.02 | [ -0.21 ;  +0.25]
           60-70% |    78 |       -0.02 | [ -0.26 ;  +0.22]
           70-80% |    38 |       -0.16 | [ -0.73 ;  +0.40]
           80-90% |    12 |       -0.11 | [ -0.67 ;  +0.46]

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
      confirme |        23 |       +9.6% |     +10.8% | [  +8.8 ;  +12.8]
       infirme |         5 |       +9.8% |      +8.5% | [  +3.6 ;  +13.3]
          muet |        79 |      +10.5% |     +13.5% | [ +11.3 ;  +15.6]

  différentiel confirme - infirme : +2.3 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 200 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        67     38.3%     43.3%    +5.0  [  -6.2 ;  +16.9]
                        il faudrait ~368 obs pour trancher à cet écart (301 manquantes)
  55 – 70 %        67     61.7%     56.7%    -5.0  [ -16.9 ;   +6.2]
                        il faudrait ~368 obs pour trancher à cet écart (301 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 298 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        91     37.8%     38.5%    +0.7  [  -8.6 ;  +11.0]
                        il faudrait ~19143 obs pour trancher à cet écart (19052 manquantes)
  55 – 70 %        93     62.1%     60.2%    -1.8  [ -12.0 ;   +7.5]
                        il faudrait ~2660 obs pour trancher à cet écart (2567 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j
1886 match(s) en contexte · 1886 avec courbe pinnacle
polymarket : 2,571,665 ticks lus · 214 observation(s)
kalshi : 1,852,562 ticks lus · 314 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 528 observation(s)
==========================================================================
  avec résultat connu     : 498
  postérieures au gel     : 498
  avec prix pinnacle    : 522

  par marché (avec résultat) : kalshi 298 · polymarket 200

  par niveau (avec résultat) : grand_chelem 322 · challenger 100 · atp 42 · wta 34

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             4               4
  15 – 30 %           48              48
  30 – 45 %          158             158
  45 – 55 %           75              75
  55 – 70 %          160             160
  70 – 85 %           47              47
  85 – 100 %           6               6

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
