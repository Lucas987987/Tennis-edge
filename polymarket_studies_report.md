# Études Polymarket/Kalshi — rapport du 2026-09-08

```
--- polymarket_leadlag ---
Polymarket : 8 partition(s), 1017769 ticks lus, 427 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 238 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
192 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.004 | Polymarket devant
    -55min |       +0.005 | Polymarket devant
    -50min |       +0.001 | Polymarket devant
    -45min |       -0.005 | Polymarket devant
    -40min |       +0.002 | Polymarket devant
    -35min |       +0.004 | Polymarket devant
    -30min |       -0.011 | Polymarket devant
    -25min |       -0.004 | Polymarket devant
    -20min |       -0.003 | Polymarket devant
    -15min |       +0.002 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       +0.004 | Polymarket devant
     +0min |       +0.062 | simultané  <<<
     +5min |       +0.045 | Pinnacle devant
    +10min |       +0.033 | Pinnacle devant
    +15min |       +0.017 | Pinnacle devant
    +20min |       -0.000 | Pinnacle devant
    +25min |       +0.015 | Pinnacle devant
    +30min |       -0.003 | Pinnacle devant
    +35min |       +0.009 | Pinnacle devant
    +40min |       +0.009 | Pinnacle devant
    +45min |       +0.002 | Pinnacle devant
    +50min |       +0.011 | Pinnacle devant
    +55min |       +0.008 | Pinnacle devant
    +60min |       +0.003 | Pinnacle devant

Maximum à +0 min (corrélation +0.062)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.063
→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent
  des paires de matchs sans rapport. Aucun lead/lag démontré.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (8 partition(s))
  1017769 ticks lus · 422 match(s) exploitables (fourchette max 10 pts)
Books      : 238 match(s), dont 238 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 201 matchs (35706 instants, grille 5 min)
  écart moyen Shin - marché      : +0.04 pts  IC95 [-0.04 ; +0.12]
  écart médian par match : +0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                201       +0.04  [-0.04 ; +0.12]
  proportionnel       201       -0.03  [-0.18 ; +0.12]
  → plus proche de Polymarket : proportionnel (écart 0.03 contre 0.04 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    55 |       -0.17 | [ -0.84 ;  +0.49]
           60-70% |    60 |       +0.10 | [ -0.07 ;  +0.27]
           70-80% |    65 |       -0.06 | [ -0.36 ;  +0.25]
           80-90% |    47 |       -0.01 | [ -0.19 ;  +0.17]
             90%+ |    16 |       +0.13 | [ -0.31 ;  +0.56]

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
          muet |       181 |      +16.9% |     +21.3% | [ +16.7 ;  +25.9]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 1884 résultats · 1858 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 110 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        24     37.3%     37.5%    +0.2  [ -16.1 ;  +20.0]
                        il faudrait ~206982 obs pour trancher à cet écart (206958 manquantes)
  55 – 70 %        23     62.4%     60.9%    -1.5  [ -21.6 ;  +15.5]
                        il faudrait ~3893 obs pour trancher à cet écart (3870 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 416 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        75     37.8%     37.3%    -0.4  [ -10.5 ;  +10.9]
                        il faudrait ~46642 obs pour trancher à cet écart (46567 manquantes)
  55 – 70 %        76     62.1%     64.5%    +2.4  [  -8.8 ;  +12.2]
                        il faudrait ~1577 obs pour trancher à cet écart (1501 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1884 résultats · 1858 paires · fenêtre ±5 j
2126 match(s) en contexte · 2126 avec courbe pinnacle
polymarket : 1,311,074 ticks lus · 126 observation(s)
kalshi : 1,017,769 ticks lus · 454 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 580 observation(s)
==========================================================================
  avec résultat connu     : 526
  postérieures au gel     : 526
  avec prix pinnacle    : 580

  par marché (avec résultat) : kalshi 416 · polymarket 110

  par niveau (avec résultat) : grand_chelem 280 · challenger 246

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            36              36
  15 – 30 %          100             100
  30 – 45 %           99              99
  45 – 55 %           54              54
  55 – 70 %           99              99
  70 – 85 %          102             102
  85 – 100 %          36              36

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  819 observation(s) construite(s) · 529 nouvelle(s) · 1613 au journal kalshi_lead_obs.jsonl

```
