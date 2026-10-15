# Études Polymarket/Kalshi — rapport du 2026-10-15

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1120810 ticks lus, 557 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 278 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
268 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.011 | Polymarket devant
    -55min |       +0.005 | Polymarket devant
    -50min |       -0.001 | Polymarket devant
    -45min |       +0.003 | Polymarket devant
    -40min |       +0.006 | Polymarket devant
    -35min |       +0.001 | Polymarket devant
    -30min |       -0.011 | Polymarket devant
    -25min |       -0.002 | Polymarket devant
    -20min |       +0.004 | Polymarket devant
    -15min |       +0.001 | Polymarket devant
    -10min |       -0.007 | Polymarket devant
     -5min |       -0.008 | Polymarket devant
     +0min |       +0.104 | simultané  <<<
     +5min |       +0.065 | Pinnacle devant
    +10min |       +0.047 | Pinnacle devant
    +15min |       +0.035 | Pinnacle devant
    +20min |       +0.025 | Pinnacle devant
    +25min |       +0.017 | Pinnacle devant
    +30min |       +0.019 | Pinnacle devant
    +35min |       +0.017 | Pinnacle devant
    +40min |       +0.006 | Pinnacle devant
    +45min |       -0.006 | Pinnacle devant
    +50min |       +0.008 | Pinnacle devant
    +55min |       +0.000 | Pinnacle devant
    +60min |       -0.009 | Pinnacle devant

Maximum à +0 min (corrélation +0.104)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.051
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1120810 ticks lus · 552 match(s) exploitables (fourchette max 10 pts)
Books      : 280 match(s), dont 278 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 271 matchs (45777 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.06 ; +0.08]
  écart médian par match : +0.01 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                271       +0.01  [-0.06 ; +0.08]
  proportionnel       271       -0.03  [-0.16 ; +0.11]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.03 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |    98 |       +0.01 | [ -0.12 ;  +0.14]
           60-70% |   110 |       -0.06 | [ -0.22 ;  +0.11]
           70-80% |    77 |       +0.07 | [ -0.14 ;  +0.29]
           80-90% |    29 |       +0.21 | [ -0.05 ;  +0.47]
             90%+ |    12 |       -0.08 | [ -0.35 ;  +0.18]

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
          muet |        84 |      +11.1% |      +9.4% | [  +6.8 ;  +12.0]

  différentiel confirme - infirme : +5.6 pts de CLV
  → les intervalles se CHEVAUCHENT : aucun apport démontré.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  0 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3586 résultats · 3492 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 164 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        39     37.6%     38.5%    +0.8  [ -12.7 ;  +16.5]
                        il faudrait ~12591 obs pour trancher à cet écart (12552 manquantes)
  55 – 70 %        38     62.2%     60.5%    -1.7  [ -17.5 ;  +12.2]
                        il faudrait ~3287 obs pour trancher à cet écart (3249 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 482 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       111     37.8%     37.8%    +0.0  [  -8.4 ;   +9.3]
                        il faudrait ~5495448 obs pour trancher à cet écart (5495337 manquantes)
  55 – 70 %       111     62.0%     61.3%    -0.7  [ -10.0 ;   +7.9]
                        il faudrait ~19065 obs pour trancher à cet écart (18954 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3586 résultats · 3492 paires · fenêtre ±5 j
3257 match(s) en contexte · 3246 avec courbe pinnacle
polymarket : 2,478,916 ticks lus · 182 observation(s)
kalshi : 1,120,810 ticks lus · 556 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 738 observation(s)
==========================================================================
  avec résultat connu     : 646
  postérieures au gel     : 646
  avec prix pinnacle    : 734

  par marché (avec résultat) : kalshi 482 · polymarket 164

  par niveau (avec résultat) : challenger 394 · atp 168 · wta 84

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            25              25
  15 – 30 %           91              91
  30 – 45 %          150             150
  45 – 55 %          112             112
  55 – 70 %          149             149
  70 – 85 %           94              94
  85 – 100 %          25              25

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  553 observation(s) construite(s) · 269 nouvelle(s) · 14749 au journal kalshi_lead_obs.jsonl

```
