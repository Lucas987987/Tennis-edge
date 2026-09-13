# Pistes exploratoires — rapport du 2026-09-13

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  692 moves appariés | témoin population appariée : 67.1% de CLV>0
  terciles de limite : basse <= 176 < moyenne <= 650 < haute
    limite basse    n=232 | CLV>0 : 61% (IC95 55-67%) | CLV méd +4.0%
    limite moyenne  n=231 | CLV>0 : 71% (IC95 65-76%) | CLV méd +4.8%
    limite haute    n=229 | CLV>0 : 69% (IC95 63-75%) | CLV méd +3.3%
  H1b (descriptif) : limite closing / limite move — médiane x6.48 sur n=692

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 66.7% de CLV>0 (n=1348)
    ATP         n= 399 | CLV>0 : 70% (IC95 65-74%) | CLV méd +4.7%
    WTA         n= 409 | CLV>0 : 66% (IC95 61-70%) | CLV méd +4.2%
    Challenger  n= 240 | CLV>0 : 58% (IC95 52-64%) | CLV méd +2.7%
    Grand Chelem n= 272 | CLV>0 : 71% (IC95 65-76%) | CLV méd +4.6%
    autre       n=  28 | CLV>0 : 71% (IC95 53-85%) | CLV méd +4.8% [n<30 : suivi]
  Contenu de "autre" (28 moves, 1 libellé(s)) :
       28 | Berlin
    -> si un libellé ci-dessus désigne un circuit connu, l'ajouter à segment_circuit().
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 33.3% (IC95 30.8-35.9%, n=1348)
  — par ampleur du move —
    2-3%     n= 101 | retournés 53% (IC 44-63%)  <-- hors IC global
    3-6%     n= 660 | retournés 31% (IC 27-34%)
    6-12%    n= 478 | retournés 33% (IC 29-37%)
    >12%     n= 109 | retournés 33% (IC 25-42%)
  — par avance sur le match —
    <1h      n=  42 | retournés 69% (IC 54-81%)  <-- hors IC global
    1-6h     n= 163 | retournés 44% (IC 37-52%)  <-- hors IC global
    6-24h    n= 784 | retournés 33% (IC 30-36%)
    >24h     n= 359 | retournés 25% (IC 21-30%)  <-- hors IC global
  — par circuit —
    WTA         n= 409 | retournés 34% (IC 30-39%)
    Challenger  n= 240 | retournés 42% (IC 36-48%)  <-- hors IC global
    Grand Chelem n= 272 | retournés 29% (IC 24-35%)
    ATP         n= 399 | retournés 30% (IC 26-35%)
    autre       n=  28 | retournés 29% (IC 15-47%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  336 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 24% positifs | n=4129
    T+ 2min : CLV atteignable médian +0.0% | 24% positifs | n=4132
    T+10min : CLV atteignable médian +0.0% | 21% positifs | n=4139
    T+30min : CLV atteignable médian +0.0% | 15% positifs | n=4158
    T+60min : CLV atteignable médian +0.0% | 9% positifs | n=4162
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    888sport           16 min (n=36)
    1xbet              17 min (n=116)
    tipico             18 min (n=49)
    22bet              20 min (n=112)
    winamax.fr         20 min (n=26)
    marathonbet        21 min (n=85)
    betway             22 min (n=38)
    netbet             33 min (n=60)
    betsson            34 min (n=108)
    coolbet            34 min (n=68)
    unibet             43 min (n=47)
    unibet.fr          44 min (n=11)
    bet365             45 min (n=37)
    bet365.fr          48 min (n=21)
    leovegas           50 min (n=70)
    bwin               53 min (n=63)
    pmu                55 min (n=38)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  3494 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 718/3494 = 21% (IC95 19-22%)
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
  266 marchés Polymarket avec ticks (fenêtre récente)
  28 matchs appariés avec corrélation exploitable (|r|>0,15)
  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,
  la donnée s'accumule toute seule. Relance hebdomadaire.

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  49 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  23 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  5 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 18 — sous 30, suivi sans verdict
  Verdict : IC95 disjoints ET n>=30 des deux côtés -> promouvoir en
  hypothèse gelée de la famille Holm avec sa propre FREEZE_DATE.

==============================================================
SIZING OMBRE — la note de fiabilité mérite-t-elle une mise ?
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  0 paris dénoués avec note de fiabilité (score journalisé depuis le 2026-08-26).
  TROP TÔT (<30) — aucun verdict. La note continue de se journaliser à chaque pari sans rien piloter.

```
