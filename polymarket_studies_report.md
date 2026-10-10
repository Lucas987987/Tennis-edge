# Études Polymarket/Kalshi — rapport du 2026-10-10

```
--- polymarket_leadlag ---
Polymarket : 9 partition(s), 1460305 ticks lus, 544 match(s) avec série 'match'
  book_curves_live.jsonl: 0 courbes reconstruites | 0 points | 0 partitions
Pinnacle   : 320 match(s) avec courbe exploitable

========================================================================
LEAD/LAG POLYMARKET vs PINNACLE — marché 'match'
299 match(s) · grille 5 min · variations, pas niveaux
========================================================================
  décalage |  corrélation | qui mène
------------------------------------------------------------------------
    -60min |       -0.003 | Polymarket devant
    -55min |       +0.002 | Polymarket devant
    -50min |       +0.003 | Polymarket devant
    -45min |       -0.002 | Polymarket devant
    -40min |       -0.004 | Polymarket devant
    -35min |       +0.002 | Polymarket devant
    -30min |       +0.001 | Polymarket devant
    -25min |       -0.008 | Polymarket devant
    -20min |       -0.002 | Polymarket devant
    -15min |       +0.003 | Polymarket devant
    -10min |       -0.000 | Polymarket devant
     -5min |       +0.003 | Polymarket devant
     +0min |       +0.093 | simultané  <<<
     +5min |       +0.055 | Pinnacle devant
    +10min |       +0.045 | Pinnacle devant
    +15min |       +0.032 | Pinnacle devant
    +20min |       +0.017 | Pinnacle devant
    +25min |       +0.016 | Pinnacle devant
    +30min |       +0.009 | Pinnacle devant
    +35min |       +0.004 | Pinnacle devant
    +40min |       -0.006 | Pinnacle devant
    +45min |       +0.004 | Pinnacle devant
    +50min |       +0.014 | Pinnacle devant
    +55min |       +0.005 | Pinnacle devant
    +60min |       +0.004 | Pinnacle devant

Maximum à +0 min (corrélation +0.093)
Seuil de bruit (95e centile sur 200 appariements factices) : +0.052
→ Le maximum dépasse la distribution nulle. Signal à confirmer
  sur davantage de matchs avant toute conclusion.
⚠️ |décalage| <= 5 min = pas de la grille. Les courbes pinnacle sont échantillonnées toutes les 5-10 min : un décalage
  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.

Rapport écrit dans polymarket_leadlag_report.json

--- polymarket_studies ---
Source(s) : kalshi (9 partition(s))
  1460305 ticks lus · 544 match(s) exploitables (fourchette max 10 pts)
Books      : 321 match(s), dont 320 avec pinnacle

==========================================================================
1. VALIDATION DU DÉVIGAGE — Shin(Pinnacle) vs marché de prédiction
==========================================================================
  n = 304 matchs (52792 instants, grille 5 min)
  écart moyen Shin - marché      : +0.01 pts  IC95 [-0.06 ; +0.08]
  écart médian par match : +0.02 pts

  méthode          matchs  écart moyen                IC95
  --------------------------------------------------------
  Shin                304       +0.01  [-0.06 ; +0.08]
  proportionnel       304       -0.07  [-0.19 ; +0.06]
  → plus proche de Polymarket : Shin (écart 0.01 contre 0.07 pt)
    mais la différence entre les deux est elle-même négligeable :
    sur cet échantillon, le choix de méthode ne change rien.

   tranche favori | matchs |  écart moyen |               IC95
  ------------------------------------------------------------
           50-60% |   110 |       -0.01 | [ -0.13 ;  +0.11]
           60-70% |   109 |       -0.01 | [ -0.22 ;  +0.20]
           70-80% |    76 |       +0.07 | [ -0.12 ;  +0.27]
           80-90% |    45 |       -0.16 | [ -0.40 ;  +0.08]
             90%+ |    16 |       +0.31 | [ -0.23 ;  +0.85]

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
      confirme |         1 | trop peu
       infirme |         1 | trop peu
          muet |        81 |      +10.2% |     +10.0% | [  +8.4 ;  +11.6]

  → pas encore assez d'écarts dans les deux groupes pour comparer.

==========================================================================
3. DIVERGENCE ≥ 5 PTS — qui a raison, le marché ou pinnacle ?
==========================================================================
  2 match(s) divergent(s) avec résultat connu — trop peu.
  Il en faut plusieurs centaines : compter quelques semaines.

Rapport écrit dans polymarket_studies_report.json

--- pm_calibration_track ---
ResultIndex : 3287 résultats · 3207 paires · fenêtre ±5 j

==============================================================================
HYPOTHÈSE GELÉE N°12 — calibration des marchés de prédiction
Gelée le 2026-08-24 · tranches et sens FIXÉS, non modifiables
==============================================================================
  30 – 45 % : sous-évaluée attendue   (+5,2 PM / +7,2 KX à la mesure)
  55 – 70 % : sur-évaluée attendue    (−2,8 PM / −4,7 KX)

==============================================================================
POLYMARKET
==============================================================================

  HORS ÉCHANTILLON (décisif) — 196 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %        43     37.3%     44.2%    +6.9  [  -6.9 ;  +21.6]
                        il faudrait ~190 obs pour trancher à cet écart (147 manquantes)
  55 – 70 %        43     62.3%     53.5%    -8.9  [ -23.4 ;   +5.1]
                        il faudrait ~115 obs pour trancher à cet écart (72 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
KALSHI
==============================================================================

  HORS ÉCHANTILLON (décisif) — 590 observation(s)
  tranche           n   annoncé   observé    écart          IC95 écart
  --------------------------------------------------------------------
  30 – 45 %       137     38.0%     38.0%    -0.1  [  -7.7 ;   +8.3]
                        il faudrait ~3020331 obs pour trancher à cet écart (3020194 manquantes)
  55 – 70 %       142     61.9%     58.5%    -3.5  [ -11.7 ;   +4.3]
                        il faudrait ~741 obs pour trancher à cet écart (599 manquantes)

  origine (pour mémoire) — 0 observation(s)

==============================================================================
→ rien de concluant hors échantillon. Laisser l'échantillon grossir.
==============================================================================

Rapport écrit dans pm_calibration_track.json

--- pm_observations ---
ResultIndex : 3287 résultats · 3207 paires · fenêtre ±5 j
3097 match(s) en contexte · 3086 avec courbe pinnacle
polymarket : 2,652,029 ticks lus · 206 observation(s)
kalshi : 1,460,305 ticks lus · 622 observation(s)

==========================================================================
TABLE CONSOLIDÉE — 828 observation(s)
==========================================================================
  avec résultat connu     : 786
  postérieures au gel     : 786
  avec prix pinnacle    : 824

  par marché (avec résultat) : kalshi 590 · polymarket 196

  par niveau (avec résultat) : challenger 490 · atp 218 · wta 78

  tranche de prix      n  dont après gel
  ----------------------------------------
  0 – 15 %            42              42
  15 – 30 %          113             113
  30 – 45 %          180             180
  45 – 55 %          111             111
  55 – 70 %          185             185
  70 – 85 %          112             112
  85 – 100 %          43              43

pm_observations.jsonl
  Les études lisent désormais ce fichier au lieu de reparcourir
  3,4 millions de ticks à chaque exécution.

--- kalshi_lead_track ---
HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel 2026-09-05)
  horizon 45 min · seuil signal 1.0 pt · fourchette <= 2 pts
  400 observation(s) construite(s) · 36 nouvelle(s) · 12745 au journal kalshi_lead_obs.jsonl

```
