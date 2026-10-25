# Pistes exploratoires — rapport du 2026-10-25

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  1830 moves appariés | témoin population appariée : 62.3% de CLV>0
  terciles de limite : basse <= 140 < moyenne <= 541 < haute
    limite basse    n=611 | CLV>0 : 60% (IC95 56-64%) | CLV méd +4.2%
    limite moyenne  n=610 | CLV>0 : 66% (IC95 62-69%) | CLV méd +4.0%
    limite haute    n=609 | CLV>0 : 61% (IC95 57-65%) | CLV méd +2.9%
  H1b (descriptif) : limite closing / limite move — médiane x6.45 sur n=1830

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 63.4% de CLV>0 (n=2614)
    ATP         n= 616 | CLV>0 : 68% (IC95 64-72%) | CLV méd +4.2%
    WTA         n= 616 | CLV>0 : 63% (IC95 59-67%) | CLV méd +3.6%
    Challenger  n= 944 | CLV>0 : 58% (IC95 54-61%) | CLV méd +3.0%
    autre       n= 438 | CLV>0 : 70% (IC95 65-74%) | CLV méd +4.5%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 36.6% (IC95 34.8-38.5%, n=2614)
  — par ampleur du move —
    2-3%     n= 183 | retournés 54% (IC 46-61%)  <-- hors IC global
    3-6%     n=1286 | retournés 36% (IC 34-39%)
    6-12%    n= 928 | retournés 35% (IC 32-38%)
    >12%     n= 217 | retournés 31% (IC 25-37%)
  — par avance sur le match —
    <1h      n=  79 | retournés 77% (IC 67-85%)  <-- hors IC global
    1-6h     n= 326 | retournés 48% (IC 43-54%)  <-- hors IC global
    6-24h    n=1583 | retournés 35% (IC 33-38%)
    >24h     n= 626 | retournés 29% (IC 26-33%)  <-- hors IC global
  — par circuit —
    WTA         n= 616 | retournés 37% (IC 33-41%)
    ATP         n= 616 | retournés 32% (IC 28-36%)
    Challenger  n= 944 | retournés 42% (IC 39-46%)  <-- hors IC global
    autre       n= 438 | retournés 30% (IC 26-35%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  357 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 17% positifs | n=1759
    T+ 2min : CLV atteignable médian +0.0% | 16% positifs | n=1760
    T+10min : CLV atteignable médian +0.0% | 13% positifs | n=1760
    T+30min : CLV atteignable médian +0.0% | 8% positifs | n=1760
    T+60min : CLV atteignable médian +0.0% | 4% positifs | n=1765
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    22bet              12 min (n=68)
    unibet.fr          15 min (n=30)
    1xbet              16 min (n=83)
    bet365             30 min (n=26)
    winamax.fr         30 min (n=41)
    pmu                31 min (n=20)
    unibet             37 min (n=37)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  2283 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 483/2283 = 21% (IC95 20-23%)
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
  298 marchés Polymarket avec ticks (fenêtre récente)
  48 matchs appariés avec corrélation exploitable (|r|>0,15)
  décalage médian du pic de corrélation : +0 min
  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  88 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  66 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  8 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 58 | CLV médian  +12.4% | refermeture 88% (IC95 77-94%)
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
