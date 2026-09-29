# Études Polymarket/Kalshi — rapport du 2026-09-07

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1076627 ticks lus, 405 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 202 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
160 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.007 | Polymarket devant
    -55min |       +0.004 | Polymarket devant
    -50min |       +0.008 | Polymarket devant
    -45min |       -0.006 | Polymarket devant
    -40min |       +0.002 | Polymarket devant
    -35min |       +0.007 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.001 | Polymarket devant
    -20min |       +0.002 | Polymarket devant
    -15min |       -0.002 | Polymarket devant
    -10min |       -0.003 | Polymarket devant
     -5min |       +0.005 | Polymarket devant
     +0min |       +0.064 | simultané  <<<
     +5min |       +0.048 | Pinnacle devant
    +10min |       +0.028 | Pinnacle devant
    +15min |       +0.016 | Pinnacle devant
    +20min |       +0.004 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       +0.006 | Pinnacle devant
    +35min |       +0.011 | Pinnacle devant
    +40min |       +0.011 | Pinnacle devant
    +45min |       +0.004 | Pinnacle devant
    +50min |       +0.014 | Pinnacle devant
    +55min |       +0.009 | Pinnacle devant
    +60min |       +0.009 | Pinnacle devant

Maximum à +0 min (corrélation +0.064)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.062
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1076627 ticks lus · 401 match(s) exploitables (fourchette max 10 pts)
Books      : 202 match(s), dont 202 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 170 matchs (38658 instants, grille 5 min)
  écart moyen Shin - marché      : +0.08 pts  IC95 [-0.01 ; +0.17]
  écart médian par match : +0.04 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                170       +0.08  [-0.01 ; +0.17]
  proportionnel       170       -0.01  [-0.18 ; +0.15]
  → plus proche de Polymarket : proportionnel (écart 0.01 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    40 |       +0.21 | [ -0.04 ;  +0.46]
           60-70% |    46 |       +0.19 | [ -0.01 ;  +0.39]
           70-80% |    58 |       -0.05 | [ -0.40 ;  +0.30]
           80-90% |    41 |       -0.02 | [ -0.21 ;  +0.16]
             90%+ |    16 |       +0.11 | [ -0.31 ;  +0.53]

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
          muet |       121 |      +13.0% |     +16.7% | [ +13.5 ;  +19.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1814 résultats · 1788 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 98 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        19     37.4%     31.6%    -5.8  [ -22.0 ;  +16.6]
                        il faudrait ~269 obs pour trancher à cet écart (250 manquantes)
  55 – 70 %        18     62.2%     66.7%    +4.4  [ -18.5 ;  +21.5]
                        il faudrait ~458 obs pour trancher à cet écart (440 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 342 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        55     38.0%     34.5%    -3.4  [ -14.6 ;   +9.8]
                        il faudrait ~767 obs pour trancher à cet écart (712 manquantes)
  55 – 70 %        57     61.9%     66.7%    +4.7  [  -8.2 ;  +15.6]
                        il faudrait ~403 obs pour trancher à cet écart (346 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1814 résultats · 1788 paires · fenêtre ±5 j
2086 match(s) en contexte · 2086 avec courbe pinnacle
polymarket : 1,050,612 ticks lus · 112 observation(s)
kalshi : 1,076,627 ticks lus · 378 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 490 observation(s)
==========================================================================
  avec résultat connu     : 440
  postérieures au gel     : 440
  avec prix pinnacle    : 490

  par marché (avec résultat) : kalshi 342 · polymarket 98

  par niveau (avec résultat) : grand_chelem 260 · challenger 180

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            33              33
  15 – 30 %           90              90
  30 – 45 %           74              74
  45 – 55 %           44              44
  55 – 70 %           75              75
  70 – 85 %           91              91
  85 – 100 %          33              33

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  908 observation(s) construite(s) · 693 nouvelle(s) · 1084 au journal kalshi_lead_obs.jsonl

```
