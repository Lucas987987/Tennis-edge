# Pistes exploratoires — rapport du 2026-10-18

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  1419 moves appariés | témoin population appariée : 63.8% de CLV>0
  terciles de limite : basse <= 147 < moyenne <= 558 < haute
    limite basse    n=475 | CLV>0 : 63% (IC95 59-67%) | CLV méd +4.8%
    limite moyenne  n=472 | CLV>0 : 65% (IC95 61-69%) | CLV méd +3.9%
    limite haute    n=472 | CLV>0 : 63% (IC95 59-68%) | CLV méd +3.0%
  H1b (descriptif) : limite closing / limite move — médiane x6.39 sur n=1419

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 64.6% de CLV>0 (n=2171)
    ATP         n= 518 | CLV>0 : 69% (IC95 64-72%) | CLV méd +4.3%
    WTA         n= 521 | CLV>0 : 64% (IC95 60-68%) | CLV méd +3.8%
    Challenger  n= 706 | CLV>0 : 60% (IC95 56-63%) | CLV méd +3.7%
    autre       n= 426 | CLV>0 : 68% (IC95 64-72%) | CLV méd +3.9%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 35.4% (IC95 33.4-37.4%, n=2171)
  — par ampleur du move —
    2-3%     n= 156 | retournés 54% (IC 46-61%)  <-- hors IC global
    3-6%     n=1055 | retournés 34% (IC 31-37%)
    6-12%    n= 768 | retournés 35% (IC 31-38%)
    >12%     n= 192 | retournés 30% (IC 24-36%)
  — par avance sur le match —
    <1h      n=  66 | retournés 76% (IC 64-84%)  <-- hors IC global
    1-6h     n= 282 | retournés 47% (IC 41-53%)  <-- hors IC global
    6-24h    n=1286 | retournés 33% (IC 31-36%)
    >24h     n= 537 | retournés 29% (IC 26-33%)
  — par circuit —
    WTA         n= 521 | retournés 36% (IC 32-40%)
    Challenger  n= 706 | retournés 40% (IC 37-44%)
    ATP         n= 518 | retournés 31% (IC 28-36%)
    autre       n= 426 | retournés 32% (IC 28-36%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  112 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 21% positifs | n=1487
    T+ 2min : CLV atteignable médian +0.0% | 20% positifs | n=1488
    T+10min : CLV atteignable médian +0.0% | 16% positifs | n=1488
    T+30min : CLV atteignable médian +0.0% | 12% positifs | n=1489
    T+60min : CLV atteignable médian +0.0% | 8% positifs | n=1491
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    netbet             11 min (n=21)
    coolbet            11 min (n=14)
    1xbet              13 min (n=20)
    betway             14 min (n=27)
    tipico             18 min (n=14)
    bwin               20 min (n=13)
    williamhill        22 min (n=13)
    bet365.fr          27 min (n=15)
    marathonbet        36 min (n=38)
    888sport           36 min (n=17)
    betsson            51 min (n=49)
    unibet             52 min (n=16)
    leovegas           54 min (n=23)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  1501 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 296/1501 = 20% (IC95 18-22%)
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
  328 marchés Polymarket avec ticks (fenêtre récente)
  4 matchs appariés avec corrélation exploitable (|r|>0,15)
  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,
  la donnée s'accumule toute seule. Relance hebdomadaire.

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  76 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  40 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  5 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 35 | CLV médian  +11.8% | refermeture 86% (IC95 71-94%)
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
