# Pistes exploratoires — rapport du 2026-10-04

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  968 moves appariés | témoin population appariée : 65.2% de CLV>0
  terciles de limite : basse <= 150 < moyenne <= 525 < haute
    limite basse    n=326 | CLV>0 : 62% (IC95 57-67%) | CLV méd +4.3%
    limite moyenne  n=325 | CLV>0 : 66% (IC95 61-71%) | CLV méd +3.1%
    limite haute    n=317 | CLV>0 : 67% (IC95 62-72%) | CLV méd +2.9%
  H1b (descriptif) : limite closing / limite move — médiane x6.69 sur n=968

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 65.4% de CLV>0 (n=1671)
    ATP         n= 442 | CLV>0 : 69% (IC95 65-73%) | CLV méd +4.0%
    WTA         n= 479 | CLV>0 : 62% (IC95 57-66%) | CLV méd +3.2%
    Challenger  n= 457 | CLV>0 : 62% (IC95 58-66%) | CLV méd +3.4%
    autre       n= 293 | CLV>0 : 71% (IC95 66-76%) | CLV méd +3.4%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 34.6% (IC95 32.4-37.0%, n=1671)
  — par ampleur du move —
    2-3%     n= 118 | retournés 55% (IC 46-64%)  <-- hors IC global
    3-6%     n= 811 | retournés 33% (IC 30-36%)
    6-12%    n= 600 | retournés 35% (IC 31-39%)
    >12%     n= 142 | retournés 27% (IC 21-35%)
  — par avance sur le match —
    <1h      n=  49 | retournés 69% (IC 55-80%)  <-- hors IC global
    1-6h     n= 207 | retournés 41% (IC 35-48%)
    6-24h    n= 999 | retournés 34% (IC 31-37%)
    >24h     n= 416 | retournés 29% (IC 24-33%)
  — par circuit —
    WTA         n= 479 | retournés 38% (IC 34-43%)
    Challenger  n= 457 | retournés 38% (IC 34-42%)
    ATP         n= 442 | retournés 31% (IC 27-35%)
    autre       n= 293 | retournés 29% (IC 24-34%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  205 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 23% positifs | n=2790
    T+ 2min : CLV atteignable médian +0.0% | 22% positifs | n=2790
    T+10min : CLV atteignable médian +0.0% | 19% positifs | n=2801
    T+30min : CLV atteignable médian +0.0% | 11% positifs | n=2823
    T+60min : CLV atteignable médian +0.0% | 5% positifs | n=2838
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    unibet.fr          11 min (n=18)
    betway             12 min (n=48)
    marathonbet        15 min (n=58)
    coolbet            17 min (n=40)
    tipico             19 min (n=33)
    22bet              20 min (n=30)
    888sport           20 min (n=44)
    1xbet              21 min (n=43)
    netbet             21 min (n=50)
    bwin               24 min (n=28)
    betsson            25 min (n=79)
    winamax.fr         29 min (n=14)
    unibet             32 min (n=24)
    leovegas           38 min (n=37)
    bet365.fr          38 min (n=48)
    pmu                38 min (n=18)
    bet365             42 min (n=23)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  3830 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 856/3830 = 22% (IC95 21-24%)
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
  140 marchés Polymarket avec ticks (fenêtre récente)
  9 matchs appariés avec corrélation exploitable (|r|>0,15)
  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,
  la donnée s'accumule toute seule. Relance hebdomadaire.

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  52 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  17 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  3 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 14 — sous 30, suivi sans verdict
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
