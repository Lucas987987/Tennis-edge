# Études Polymarket/Kalshi — rapport du 2026-09-10

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1157928 ticks lus, 428 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 269 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
232 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.000 | Polymarket devant
    -55min |       -0.002 | Polymarket devant
    -50min |       +0.004 | Polymarket devant
    -45min |       -0.010 | Polymarket devant
    -40min |       -0.004 | Polymarket devant
    -35min |       +0.000 | Polymarket devant
    -30min |       -0.005 | Polymarket devant
    -25min |       -0.015 | Polymarket devant
    -20min |       -0.000 | Polymarket devant
    -15min |       +0.003 | Polymarket devant
    -10min |       -0.006 | Polymarket devant
     -5min |       +0.004 | Polymarket devant
     +0min |       +0.057 | simultané  <<<
     +5min |       +0.044 | Pinnacle devant
    +10min |       +0.041 | Pinnacle devant
    +15min |       +0.013 | Pinnacle devant
    +20min |       +0.001 | Pinnacle devant
    +25min |       +0.012 | Pinnacle devant
    +30min |       +0.007 | Pinnacle devant
    +35min |       +0.009 | Pinnacle devant
    +40min |       +0.010 | Pinnacle devant
    +45min |       -0.003 | Pinnacle devant
    +50min |       +0.006 | Pinnacle devant
    +55min |       +0.001 | Pinnacle devant
    +60min |       +0.002 | Pinnacle devant

Maximum à +0 min (corrélation +0.057)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.060
→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent
  des paires de matchs sans rapport. Aucun lead/lag démontré.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1157928 ticks lus · 423 match(s) exploitables (fourchette max 10 pts)
Books      : 270 match(s), dont 269 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 244 matchs (41818 instants, grille 5 min)
  écart moyen Shin - marché      : -0.02 pts  IC95 [-0.10 ; +0.05]
  écart médian par match : -0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                244       -0.02  [-0.10 ; +0.05]
  proportionnel       244       -0.02  [-0.15 ; +0.11]
  → plus proche de Polymarket : proportionnel (écart 0.02 contre 0.02 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    74 |       -0.24 | [ -0.74 ;  +0.26]
           60-70% |    79 |       +0.07 | [ -0.14 ;  +0.29]
           70-80% |    77 |       -0.11 | [ -0.38 ;  +0.15]
           80-90% |    53 |       +0.04 | [ -0.23 ;  +0.30]
             90%+ |    16 |       -0.02 | [ -0.50 ;  +0.46]

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
          muet |       205 |      +17.9% |     +22.7% | [ +18.4 ;  +27.0]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2034 résultats · 2004 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 162 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        37     37.7%     35.1%    -2.5  [ -15.9 ;  +13.6]
                        il faudrait ~1398 obs pour trancher à cet écart (1361 manquantes)
  55 – 70 %        36     62.1%     63.9%    +1.8  [ -14.5 ;  +15.4]
                        il faudrait ~2861 obs pour trancher à cet écart (2825 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 478 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        98     37.8%     36.7%    -1.0  [  -9.9 ;   +8.8]
                        il faudrait ~8501 obs pour trancher à cet écart (8403 manquantes)
  55 – 70 %        95     62.1%     63.2%    +1.0  [  -9.0 ;  +10.1]
                        il faudrait ~8242 obs pour trancher à cet écart (8147 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2034 résultats · 2004 paires · fenêtre ±5 j
2206 match(s) en contexte · 2206 avec courbe pinnacle
polymarket : 1,757,882 ticks lus · 180 observation(s)
kalshi : 1,157,928 ticks lus · 516 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 696 observation(s)
==========================================================================
  avec résultat connu     : 640
  postérieures au gel     : 640
  avec prix pinnacle    : 694

  par marché (avec résultat) : kalshi 478 · polymarket 162

  par niveau (avec résultat) : challenger 436 · grand_chelem 204

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            35              35
  15 – 30 %          117             117
  30 – 45 %          135             135
  45 – 55 %           66              66
  55 – 70 %          131             131
  70 – 85 %          121             121
  85 – 100 %          35              35

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  675 observation(s) construite(s) · 218 nouvelle(s) · 2098 au journal kalshi_lead_obs.jsonl

```
