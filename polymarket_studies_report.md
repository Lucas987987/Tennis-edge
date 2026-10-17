# Études Polymarket/Kalshi — rapport du 2026-10-17

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1116997 ticks lus, 529 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 196 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
187 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.019 | Polymarket devant
    -55min |       +0.011 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       +0.004 | Polymarket devant
    -40min |       +0.006 | Polymarket devant
    -35min |       +0.011 | Polymarket devant
    -30min |       -0.017 | Polymarket devant
    -25min |       -0.001 | Polymarket devant
    -20min |       +0.001 | Polymarket devant
    -15min |       +0.004 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       -0.009 | Polymarket devant
     +0min |       +0.112 | simultané  <<<
     +5min |       +0.076 | Pinnacle devant
    +10min |       +0.050 | Pinnacle devant
    +15min |       +0.028 | Pinnacle devant
    +20min |       +0.036 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.011 | Pinnacle devant
    +35min |       +0.020 | Pinnacle devant
    +40min |       +0.005 | Pinnacle devant
    +45min |       +0.008 | Pinnacle devant
    +50min |       +0.010 | Pinnacle devant
    +55min |       -0.001 | Pinnacle devant
    +60min |       -0.016 | Pinnacle devant

Maximum à +0 min (corrélation +0.112)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.063
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1116997 ticks lus · 522 match(s) exploitables (fourchette max 10 pts)
Books      : 198 match(s), dont 196 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 189 matchs (26645 instants, grille 5 min)
  écart moyen Shin - marché      : +0.03 pts  IC95 [-0.05 ; +0.12]
  écart médian par match : +0.06 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                189       +0.03  [-0.05 ; +0.12]
  proportionnel       189       -0.05  [-0.21 ; +0.12]
  → plus proche de Polymarket : Shin (écart 0.03 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    67 |       +0.06 | [ -0.10 ;  +0.21]
           60-70% |    72 |       -0.15 | [ -0.33 ;  +0.04]
           70-80% |    55 |       +0.05 | [ -0.18 ;  +0.29]
           80-90% |    25 |       +0.29 | [ +0.05 ;  +0.53]
             90%+ |    12 |       -0.08 | [ -0.35 ;  +0.19]

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
          muet |        66 |      +10.4% |      +8.9% | [  +5.7 ;  +12.1]

  différentiel confirme - infirme : +5.6 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3572 résultats · 3477 paires · fenêtre ±5 j

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
  30 – 45 %        27     37.4%     33.3%    -4.1  [ -18.8 ;  +14.7]
                        il faudrait ~538 obs pour trancher à cet écart (511 manquantes)
  55 – 70 %        26     62.3%     65.4%    +3.1  [ -16.1 ;  +18.3]
                        il faudrait ~942 obs pour trancher à cet écart (916 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 356 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        78     38.0%     38.5%    +0.4  [  -9.6 ;  +11.5]
                        il faudrait ~46273 obs pour trancher à cet écart (46195 manquantes)
  55 – 70 %        78     61.8%     62.8%    +1.0  [ -10.1 ;  +10.9]
                        il faudrait ~9425 obs pour trancher à cet écart (9347 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3572 résultats · 3477 paires · fenêtre ±5 j
3418 match(s) en contexte · 3407 avec courbe pinnacle
polymarket : 3,019,591 ticks lus · 138 observation(s)
kalshi : 1,116,997 ticks lus · 392 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 530 observation(s)
==========================================================================
  avec résultat connu     : 476
  postérieures au gel     : 476
  avec prix pinnacle    : 526

  par marché (avec résultat) : kalshi 356 · polymarket 120

  par niveau (avec résultat) : challenger 296 · atp 104 · wta 76

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            24              24
  15 – 30 %           70              70
  30 – 45 %          105             105
  45 – 55 %           77              77
  55 – 70 %          104             104
  70 – 85 %           72              72
  85 – 100 %          24              24

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  1280 observation(s) construite(s) · 445 nouvelle(s) · 15555 au journal kalshi_lead_obs.jsonl

```
