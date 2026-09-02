# Études Polymarket/Kalshi — rapport du 2026-09-02

```
--- polymarket_flow ---
❌ polymarket_flow.py EN ÉCHEC (code 124)

--- polymarket_leadlag ---
Polymarket : 11 partition(s), 2408930 ticks lus, 535 match(s) avec série 'match'
Pinnacle   : 213 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
194 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       +0.009 | Polymarket devant
    -55min |       -0.012 | Polymarket devant
    -50min |       +0.010 | Polymarket devant
    -45min |       -0.018 | Polymarket devant
    -40min |       +0.002 | Polymarket devant
    -35min |       +0.012 | Polymarket devant
    -30min |       -0.020 | Polymarket devant
    -25min |       -0.003 | Polymarket devant
    -20min |       +0.012 | Polymarket devant
    -15min |       +0.013 | Polymarket devant
    -10min |       -0.002 | Polymarket devant
     -5min |       -0.012 | Polymarket devant
     +0min |       +0.114 | simultané  <<<
     +5min |       +0.084 | Pinnacle devant
    +10min |       +0.022 | Pinnacle devant
    +15min |       +0.002 | Pinnacle devant
    +20min |       +0.026 | Pinnacle devant
    +25min |       +0.009 | Pinnacle devant
    +30min |       +0.009 | Pinnacle devant
    +35min |       +0.003 | Pinnacle devant
    +40min |       -0.008 | Pinnacle devant
    +45min |       +0.013 | Pinnacle devant
    +50min |       -0.004 | Pinnacle devant
    +55min |       +0.003 | Pinnacle devant
    +60min |       -0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.114)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.042
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (11 partition(s))
  2408930 ticks lus · 529 match(s) exploitables (fourchette max 10 pts)
Books      : 213 match(s), dont 213 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 194 matchs (31349 instants, grille 5 min)
  écart moyen Shin - marché      : +0.00 pts  IC95 [-0.08 ; +0.09]
  écart médian par match : -0.03 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                194       +0.00  [-0.08 ; +0.09]
  proportionnel       194       -0.05  [-0.19 ; +0.09]
  → plus proche de Polymarket : Shin (écart 0.00 contre 0.05 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    91 |       +0.05 | [ -0.15 ;  +0.25]
           60-70% |    92 |       -0.05 | [ -0.26 ;  +0.15]
           70-80% |    50 |       -0.23 | [ -0.67 ;  +0.21]
           80-90% |    19 |       -0.19 | [ -0.58 ;  +0.21]

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
      confirme |        25 |       +9.6% |     +11.8% | [  +9.5 ;  +14.0]
       infirme |         5 |       +9.8% |      +8.5% | [  +3.6 ;  +13.3]
          muet |       140 |      +10.6% |     +17.3% | [ +14.7 ;  +19.9]

  différentiel confirme - infirme : +3.3 pts de CLV
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

  HORS ÉCHANTILLON (décisif) — 214 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        71     38.1%     43.7%    +5.5  [  -5.4 ;  +17.1]
                        il faudrait ~296 obs pour trancher à cet écart (225 manquantes)
  55 – 70 %        71     61.9%     56.3%    -5.5  [ -17.1 ;   +5.4]
                        il faudrait ~296 obs pour trancher à cet écart (225 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 374 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       107     37.7%     42.1%    +4.3  [  -4.6 ;  +13.8]
                        il faudrait ~484 obs pour trancher à cet écart (377 manquantes)
  55 – 70 %       109     62.1%     56.9%    -5.3  [ -14.6 ;   +3.7]
                        il faudrait ~328 obs pour trancher à cet écart (219 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 1582 résultats · 1558 paires · fenêtre ±5 j
1886 match(s) en contexte · 1886 avec courbe pinnacle
polymarket : 3,135,037 ticks lus · 228 observation(s)
kalshi : 2,408,930 ticks lus · 392 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 620 observation(s)
==========================================================================
  avec résultat connu     : 588
  postérieures au gel     : 588
  avec prix pinnacle    : 614

  par marché (avec résultat) : kalshi 374 · polymarket 214

  par niveau (avec résultat) : grand_chelem 364 · challenger 108 · atp 66 · wta 50

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %             6               6
  15 – 30 %           63              63
  30 – 45 %          178             178
  45 – 55 %           91              91
  55 – 70 %          180             180
  70 – 85 %           62              62
  85 – 100 %           8               8

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

```
