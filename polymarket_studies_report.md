# Études Polymarket/Kalshi — rapport du 2026-09-09

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1043982 ticks lus, 396 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 231 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
194 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.000 | Polymarket devant
    -55min |       -0.002 | Polymarket devant
    -50min |       +0.004 | Polymarket devant
    -45min |       -0.005 | Polymarket devant
    -40min |       -0.001 | Polymarket devant
    -35min |       +0.006 | Polymarket devant
    -30min |       -0.006 | Polymarket devant
    -25min |       -0.015 | Polymarket devant
    -20min |       -0.000 | Polymarket devant
    -15min |       +0.002 | Polymarket devant
    -10min |       -0.010 | Polymarket devant
     -5min |       +0.003 | Polymarket devant
     +0min |       +0.046 | simultané  <<<
     +5min |       +0.046 | Pinnacle devant
    +10min |       +0.037 | Pinnacle devant
    +15min |       +0.014 | Pinnacle devant
    +20min |       +0.000 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.009 | Pinnacle devant
    +35min |       +0.012 | Pinnacle devant
    +40min |       +0.012 | Pinnacle devant
    +45min |       -0.000 | Pinnacle devant
    +50min |       +0.008 | Pinnacle devant
    +55min |       +0.003 | Pinnacle devant
    +60min |       +0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.046)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.062
→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent
  des paires de matchs sans rapport. Aucun lead/lag démontré.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1043982 ticks lus · 391 match(s) exploitables (fourchette max 10 pts)
Books      : 232 match(s), dont 231 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 206 matchs (35826 instants, grille 5 min)
  écart moyen Shin - marché      : -0.00 pts  IC95 [-0.08 ; +0.08]
  écart médian par match : -0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                206       -0.00  [-0.08 ; +0.08]
  proportionnel       206       -0.05  [-0.19 ; +0.08]
  → plus proche de Polymarket : Shin (écart 0.00 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    66 |       -0.24 | [ -0.80 ;  +0.31]
           60-70% |    64 |       +0.03 | [ -0.12 ;  +0.19]
           70-80% |    62 |       -0.13 | [ -0.44 ;  +0.18]
           80-90% |    43 |       -0.01 | [ -0.19 ;  +0.17]
             90%+ |    13 |       +0.15 | [ -0.35 ;  +0.65]

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
      confirme |         0 | trop peu
       infirme |         0 | trop peu
          muet |       175 |      +16.7% |     +20.9% | [ +16.1 ;  +25.7]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1982 résultats · 1954 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 124 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        27     37.3%     37.0%    -0.3  [ -15.8 ;  +18.4]
                        il faudrait ~102375 obs pour trancher à cet écart (102348 manquantes)
  55 – 70 %        26     62.4%     61.5%    -0.8  [ -19.9 ;  +15.2]
                        il faudrait ~12591 obs pour trancher à cet écart (12565 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 402 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        81     37.9%     38.3%    +0.4  [  -9.5 ;  +11.2]
                        il faudrait ~70547 obs pour trancher à cet écart (70466 manquantes)
  55 – 70 %        78     61.9%     61.5%    -0.4  [ -11.5 ;   +9.6]
                        il faudrait ~57338 obs pour trancher à cet écart (57260 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1982 résultats · 1954 paires · fenêtre ±5 j
2166 match(s) en contexte · 2166 avec courbe pinnacle
polymarket : 1,626,703 ticks lus · 140 observation(s)
kalshi : 1,043,982 ticks lus · 440 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 580 observation(s)
==========================================================================
  avec résultat connu     : 526
  postérieures au gel     : 526
  avec prix pinnacle    : 578

  par marché (avec résultat) : kalshi 402 · polymarket 124

  par niveau (avec résultat) : challenger 334 · grand_chelem 192

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            29              29
  15 – 30 %           95              95
  30 – 45 %          108             108
  45 – 55 %           62              62
  55 – 70 %          104             104
  70 – 85 %           99              99
  85 – 100 %          29              29

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  645 observation(s) construite(s) · 267 nouvelle(s) · 1880 au journal kalshi_lead_obs.jsonl

```
