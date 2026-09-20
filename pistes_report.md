# Pistes exploratoires — rapport du 2026-09-20

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  871 moves appariés | témoin population appariée : 66.4% de CLV>0
  terciles de limite : basse <= 153 < moyenne <= 550 < haute
    limite basse    n=291 | CLV>0 : 64% (IC95 59-70%) | CLV méd +5.0%
    limite moyenne  n=290 | CLV>0 : 67% (IC95 61-72%) | CLV méd +4.7%
    limite haute    n=290 | CLV>0 : 68% (IC95 62-73%) | CLV méd +3.3%
  H1b (descriptif) : limite closing / limite move — médiane x6.80 sur n=871

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 66.3% de CLV>0 (n=1553)
    ATP         n= 399 | CLV>0 : 70% (IC95 65-74%) | CLV méd +4.7%
    WTA         n= 464 | CLV>0 : 66% (IC95 61-70%) | CLV méd +4.2%
    Challenger  n= 390 | CLV>0 : 60% (IC95 55-65%) | CLV méd +3.8%
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
  taux global de retournement : 33.7% (IC95 31.4-36.1%, n=1553)
  — par ampleur du move —
    2-3%     n= 113 | retournés 51% (IC 42-60%)  <-- hors IC global
    3-6%     n= 751 | retournés 32% (IC 29-35%)
    6-12%    n= 557 | retournés 34% (IC 30-38%)
    >12%     n= 132 | retournés 29% (IC 22-37%)
  — par avance sur le match —
    <1h      n=  47 | retournés 68% (IC 54-80%)  <-- hors IC global
    1-6h     n= 190 | retournés 45% (IC 38-52%)  <-- hors IC global
    6-24h    n= 930 | retournés 33% (IC 30-36%)
    >24h     n= 386 | retournés 25% (IC 21-30%)  <-- hors IC global
  — par circuit —
    WTA         n= 464 | retournés 34% (IC 30-39%)
    Challenger  n= 390 | retournés 40% (IC 35-45%)
    Grand Chelem n= 272 | retournés 29% (IC 24-35%)
    ATP         n= 399 | retournés 30% (IC 26-35%)
    autre       n=  28 | retournés 29% (IC 15-47%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  325 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 22% positifs | n=4179
    T+ 2min : CLV atteignable médian +0.0% | 21% positifs | n=4183
    T+10min : CLV atteignable médian +0.0% | 18% positifs | n=4195
    T+30min : CLV atteignable médian +0.0% | 11% positifs | n=4224
    T+60min : CLV atteignable médian +0.0% | 5% positifs | n=4230
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    888sport            8 min (n=34)
    1xbet              14 min (n=102)
    22bet              16 min (n=95)
    betway             18 min (n=59)
    unibet.fr          18 min (n=16)
    winamax.fr         19 min (n=25)
    marathonbet        20 min (n=110)
    tipico             21 min (n=43)
    betsson            22 min (n=63)
    coolbet            24 min (n=40)
    netbet             26 min (n=68)
    bet365             34 min (n=41)
    bwin               35 min (n=51)
    bet365.fr          36 min (n=41)
    leovegas           41 min (n=65)
    unibet             48 min (n=49)
    pmu                58 min (n=16)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  3696 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 792/3696 = 21% (IC95 20-23%)
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
  291 marchés Polymarket avec ticks (fenêtre récente)
  49 matchs appariés avec corrélation exploitable (|r|>0,15)
  décalage médian du pic de corrélation : -6 min
  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  82 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  48 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n= 11 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n= 37 | CLV médian  +15.5% | refermeture 95% (IC95 82-99%)
  Verdict : IC95 disjoints ET n>=30 des deux côtés -> promouvoir en
  hypothèse gelée de la famille Holm avec sa propre FREEZE_DATE.

==============================================================
SIZING OMBRE — la note de fiabilité mérite-t-elle une mise ?
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  24 paris dénoués avec note de fiabilité (score journalisé depuis le 2026-08-26).
  TROP TÔT (<30) — aucun verdict. La note continue de se journaliser à chaque pari sans rien piloter.

```
