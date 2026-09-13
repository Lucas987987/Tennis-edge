# Études Polymarket/Kalshi — rapport du 2026-09-13

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1250936 ticks lus, 499 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 306 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
276 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.009 | Polymarket devant
    -55min |       -0.004 | Polymarket devant
    -50min |       -0.002 | Polymarket devant
    -45min |       -0.007 | Polymarket devant
    -40min |       +0.000 | Polymarket devant
    -35min |       -0.005 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       +0.001 | Polymarket devant
    -15min |       +0.011 | Polymarket devant
    -10min |       -0.011 | Polymarket devant
     -5min |       +0.005 | Polymarket devant
     +0min |       +0.048 | simultané  <<<
     +5min |       +0.037 | Pinnacle devant
    +10min |       +0.036 | Pinnacle devant
    +15min |       +0.019 | Pinnacle devant
    +20min |       +0.006 | Pinnacle devant
    +25min |       +0.018 | Pinnacle devant
    +30min |       +0.002 | Pinnacle devant
    +35min |       +0.008 | Pinnacle devant
    +40min |       +0.006 | Pinnacle devant
    +45min |       +0.002 | Pinnacle devant
    +50min |       +0.005 | Pinnacle devant
    +55min |       +0.006 | Pinnacle devant
    +60min |       +0.006 | Pinnacle devant

Maximum à +0 min (corrélation +0.048)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.058
→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent
  des paires de matchs sans rapport. Aucun lead/lag démontré.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1250936 ticks lus · 493 match(s) exploitables (fourchette max 10 pts)
Books      : 307 match(s), dont 305 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 285 matchs (43627 instants, grille 5 min)
  écart moyen Shin - marché      : -0.08 pts  IC95 [-0.16 ; -0.00]
  écart médian par match : -0.09 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                285       -0.08  [-0.16 ; -0.00]
  proportionnel       285       -0.07  [-0.20 ; +0.06]
  → plus proche de Polymarket : proportionnel (écart 0.07 contre 0.08 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    91 |       -0.39 | [ -0.79 ;  +0.01]
           60-70% |    99 |       +0.06 | [ -0.16 ;  +0.27]
           70-80% |    85 |       -0.11 | [ -0.37 ;  +0.14]
           80-90% |    51 |       -0.13 | [ -0.61 ;  +0.35]
             90%+ |    21 |       +0.05 | [ -0.40 ;  +0.50]

  → biais détectable (-0.08 pts) mais SOUS le seuil de matérialité
    de 0.5 pt. Statistiquement réel, pratiquement sans effet :
    aucune décision du projet ne change pour un tel décalage.
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
      confirme |         2 | trop peu
       infirme |         0 | trop peu
          muet |       213 |      +17.1% |     +26.2% | [ +21.3 ;  +31.0]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  1 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 2118 résultats · 2075 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 152 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        38     37.6%     34.2%    -3.4  [ -16.4 ;  +12.5]
                        il faudrait ~801 obs pour trancher à cet écart (763 manquantes)
  55 – 70 %        37     62.2%     64.9%    +2.6  [ -13.5 ;  +15.9]
                        il faudrait ~1301 obs pour trancher à cet écart (1264 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 500 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       112     37.1%     34.8%    -2.3  [ -10.5 ;   +6.9]
                        il faudrait ~1717 obs pour trancher à cet écart (1605 manquantes)
  55 – 70 %       107     62.7%     64.5%    +1.7  [  -7.7 ;  +10.2]
                        il faudrait ~2956 obs pour trancher à cet écart (2849 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 2118 résultats · 2075 paires · fenêtre ±5 j
2326 match(s) en contexte · 2326 avec courbe pinnacle
polymarket : 1,950,150 ticks lus · 196 observation(s)
kalshi : 1,250,936 ticks lus · 594 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 790 observation(s)
==========================================================================
  avec résultat connu     : 652
  postérieures au gel     : 652
  avec prix pinnacle    : 786

  par marché (avec résultat) : kalshi 500 · polymarket 152

  par niveau (avec résultat) : challenger 568 · grand_chelem 42 · wta 42

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            32              32
  15 – 30 %          100             100
  30 – 45 %          150             150
  45 – 55 %           88              88
  55 – 70 %          144             144
  70 – 85 %          106             106
  85 – 100 %          32              32

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  718 observation(s) construite(s) · 278 nouvelle(s) · 2676 au journal kalshi_lead_obs.jsonl

```
