# Pistes exploratoires — rapport du 2026-10-11

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  1165 moves appariés | témoin population appariée : 65.7% de CLV>0
  terciles de limite : basse <= 150 < moyenne <= 595 < haute
    limite basse    n=394 | CLV>0 : 66% (IC95 62-71%) | CLV méd +5.3%
    limite moyenne  n=383 | CLV>0 : 65% (IC95 60-70%) | CLV méd +3.9%
    limite haute    n=388 | CLV>0 : 65% (IC95 61-70%) | CLV méd +3.1%
  H1b (descriptif) : limite closing / limite move — médiane x6.39 sur n=1165

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 65.8% de CLV>0 (n=1892)
    ATP         n= 506 | CLV>0 : 69% (IC95 64-72%) | CLV méd +4.2%
    WTA         n= 505 | CLV>0 : 64% (IC95 60-68%) | CLV méd +3.8%
    Challenger  n= 586 | CLV>0 : 62% (IC95 58-66%) | CLV méd +3.9%
    autre       n= 295 | CLV>0 : 71% (IC95 65-76%) | CLV méd +4.5%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 34.2% (IC95 32.1-36.4%, n=1892)
  — par ampleur du move —
    2-3%     n= 140 | retournés 52% (IC 44-60%)  <-- hors IC global
    3-6%     n= 919 | retournés 32% (IC 29-36%)
    6-12%    n= 668 | retournés 34% (IC 31-38%)
    >12%     n= 165 | retournés 30% (IC 23-37%)
  — par avance sur le match —
    <1h      n=  57 | retournés 72% (IC 59-82%)  <-- hors IC global
    1-6h     n= 241 | retournés 44% (IC 37-50%)  <-- hors IC global
    6-24h    n=1133 | retournés 32% (IC 30-35%)
    >24h     n= 461 | retournés 29% (IC 25-33%)
  — par circuit —
    WTA         n= 505 | retournés 36% (IC 32-40%)
    Challenger  n= 586 | retournés 38% (IC 34-42%)
    ATP         n= 506 | retournés 31% (IC 28-36%)
    autre       n= 295 | retournés 29% (IC 24-35%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  287 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 21% positifs | n=4066
    T+ 2min : CLV atteignable médian +0.0% | 20% positifs | n=4068
    T+10min : CLV atteignable médian +0.0% | 18% positifs | n=4073
    T+30min : CLV atteignable médian +0.0% | 13% positifs | n=4081
    T+60min : CLV atteignable médian +0.0% | 8% positifs | n=4086
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    22bet              16 min (n=35)
    betway             17 min (n=46)
    1xbet              20 min (n=30)
    marathonbet        24 min (n=91)
    coolbet            25 min (n=43)
    tipico             25 min (n=36)
    netbet             27 min (n=48)
    888sport           29 min (n=58)
    betsson            31 min (n=135)
    winamax.fr         33 min (n=33)
    bwin               33 min (n=36)
    pmu                36 min (n=11)
    williamhill        37 min (n=27)
    bet365             39 min (n=32)
    unibet.fr          40 min (n=17)
    bet365.fr          44 min (n=86)
    unibet             48 min (n=23)
    leovegas           58 min (n=51)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  4272 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 817/4272 = 19% (IC95 18-20%)
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
  283 marchés Polymarket avec ticks (fenêtre récente)
  41 matchs appariés avec corrélation exploitable (|r|>0,15)
  décalage médian du pic de corrélation : +0 min
  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  63 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  26 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  4 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 22 — sous 30, suivi sans verdict
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
