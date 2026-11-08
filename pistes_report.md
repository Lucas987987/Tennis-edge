# Pistes exploratoires — rapport du 2026-11-08

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  2120 moves appariés | témoin population appariée : 63.8% de CLV>0
  terciles de limite : basse <= 137 < moyenne <= 525 < haute
    limite basse    n=721 | CLV>0 : 63% (IC95 60-67%) | CLV méd +4.8%
    limite moyenne  n=698 | CLV>0 : 66% (IC95 62-69%) | CLV méd +4.2%
    limite haute    n=701 | CLV>0 : 62% (IC95 59-66%) | CLV méd +2.9%
  H1b (descriptif) : limite closing / limite move — médiane x6.58 sur n=2120

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 64.5% de CLV>0 (n=2944)
    ATP         n= 688 | CLV>0 : 68% (IC95 64-71%) | CLV méd +4.5%
    WTA         n= 697 | CLV>0 : 64% (IC95 61-68%) | CLV méd +3.9%
    Challenger  n=1118 | CLV>0 : 61% (IC95 58-63%) | CLV méd +3.6%
    autre       n= 441 | CLV>0 : 70% (IC95 66-74%) | CLV méd +4.8%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 35.5% (IC95 33.8-37.2%, n=2944)
  — par ampleur du move —
    2-3%     n= 206 | retournés 53% (IC 47-60%)  <-- hors IC global
    3-6%     n=1451 | retournés 35% (IC 33-38%)
    6-12%    n=1045 | retournés 33% (IC 31-36%)
    >12%     n= 242 | retournés 31% (IC 25-37%)
  — par avance sur le match —
    <1h      n=  94 | retournés 71% (IC 61-79%)  <-- hors IC global
    1-6h     n= 377 | retournés 49% (IC 44-54%)  <-- hors IC global
    6-24h    n=1792 | retournés 33% (IC 31-35%)
    >24h     n= 681 | retournés 30% (IC 26-33%)  <-- hors IC global
  — par circuit —
    WTA         n= 697 | retournés 36% (IC 32-39%)
    ATP         n= 688 | retournés 32% (IC 29-36%)
    Challenger  n=1118 | retournés 39% (IC 37-42%)
    autre       n= 441 | retournés 30% (IC 26-34%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  23 alertes appariées à au moins un book soft
  trop tôt (<30 alertes appariées).

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  trop tôt : aucun book avec >=10 alertes mesurables.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  123 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 33/123 = 27% (IC95 20-35%)
  IC95 entièrement > 50 % ET n>=30 -> propagation confirmée, à
  geler alors en hypothèse de la famille principale.
  ⚠️ RÉSULTAT INVERSE — lire avec le CONFONDEUR en tête : la
  fenêtre témoin est plus loin du coup d'envoi que la fenêtre
  alerte, or dérive et volatilité varient avec l'approche du
  match. Avant toute conclusion, protocole v2 : témoin apparié
  à la MÊME distance du match, sur des matchs SANS alerte.

==============================================================
PISTE 2 — LEAD-LAG POLYMARKET vs PINNACLE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  28 marchés Polymarket avec ticks (fenêtre récente)
  0 matchs appariés avec corrélation exploitable (|r|>0,15)
  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,
  la donnée s'accumule toute seule. Relance hebdomadaire.

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  114 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  72 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  9 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 63 | CLV médian  +12.3% | refermeture 87% (IC95 77-93%)
  Verdict : IC95 disjoints ET n>=30 des deux côtés -> promouvoir en
  hypothèse gelée de la famille Holm avec sa propre FREEZE_DATE.

==============================================================
SIZING OMBRE — la note de fiabilité mérite-t-elle une mise ?
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  74 paris dénoués avec note de fiabilité (score journalisé depuis le 2026-08-26).
  Mise plate (référence) : ROI +4.6% [IC95 -25.4, +34.7]
  Mise variable (note)   : ROI +4.6% [IC95 -25.4, +34.7]
  Détail par note :
    score +0 : n=  3 | ROI  +80.7%
    score +1 : n= 71 | ROI   +1.4%
  IC95 recouvrants -> pas encore de différence démontrée. La mise plate reste la référence.

```
