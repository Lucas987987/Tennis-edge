# Pistes exploratoires — rapport du 2026-11-01

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  2075 moves appariés | témoin population appariée : 64.5% de CLV>0
  terciles de limite : basse <= 137 < moyenne <= 525 < haute
    limite basse    n=702 | CLV>0 : 64% (IC95 60-67%) | CLV méd +4.8%
    limite moyenne  n=686 | CLV>0 : 66% (IC95 63-70%) | CLV méd +4.2%
    limite haute    n=687 | CLV>0 : 63% (IC95 60-67%) | CLV méd +3.1%
  H1b (descriptif) : limite closing / limite move — médiane x6.58 sur n=2075

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 65.0% de CLV>0 (n=2895)
    ATP         n= 671 | CLV>0 : 69% (IC95 65-72%) | CLV méd +4.5%
    WTA         n= 689 | CLV>0 : 64% (IC95 61-68%) | CLV méd +3.9%
    Challenger  n=1094 | CLV>0 : 61% (IC95 58-64%) | CLV méd +3.8%
    autre       n= 441 | CLV>0 : 70% (IC95 66-74%) | CLV méd +4.8%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 35.0% (IC95 33.3-36.8%, n=2895)
  — par ampleur du move —
    2-3%     n= 198 | retournés 52% (IC 45-58%)  <-- hors IC global
    3-6%     n=1425 | retournés 35% (IC 32-37%)
    6-12%    n=1033 | retournés 33% (IC 30-36%)
    >12%     n= 239 | retournés 30% (IC 25-36%)
  — par avance sur le match —
    <1h      n=  92 | retournés 71% (IC 61-79%)  <-- hors IC global
    1-6h     n= 356 | retournés 47% (IC 42-52%)  <-- hors IC global
    6-24h    n=1773 | retournés 33% (IC 31-35%)
    >24h     n= 674 | retournés 30% (IC 26-33%)
  — par circuit —
    WTA         n= 689 | retournés 36% (IC 32-39%)
    ATP         n= 671 | retournés 31% (IC 28-35%)
    Challenger  n=1094 | retournés 39% (IC 36-42%)
    autre       n= 441 | retournés 30% (IC 26-34%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  262 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 19% positifs | n=1181
    T+ 2min : CLV atteignable médian +0.0% | 19% positifs | n=1181
    T+10min : CLV atteignable médian +0.0% | 17% positifs | n=1183
    T+30min : CLV atteignable médian +0.0% | 12% positifs | n=1193
    T+60min : CLV atteignable médian +0.0% | 7% positifs | n=1201
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    unibet.fr          25 min (n=17)
    1xbet              26 min (n=61)
    winamax.fr         34 min (n=26)
    22bet              35 min (n=47)
    bet365             38 min (n=21)
    pmu                39 min (n=27)
    unibet             40 min (n=23)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  1554 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 341/1554 = 22% (IC95 20-24%)
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
  219 marchés Polymarket avec ticks (fenêtre récente)
  36 matchs appariés avec corrélation exploitable (|r|>0,15)
  décalage médian du pic de corrélation : +9 min
  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  100 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  71 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  9 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 62 | CLV médian  +12.1% | refermeture 87% (IC95 77-93%)
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
