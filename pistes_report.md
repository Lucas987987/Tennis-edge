# Pistes exploratoires — rapport du 2026-08-30

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  377 moves appariés | témoin population appariée : 74.5% de CLV>0
  terciles de limite : basse <= 196 < moyenne <= 812 < haute
    limite basse    n=126 | CLV>0 : 73% (IC95 65-80%) | CLV méd +5.8%
    limite moyenne  n=126 | CLV>0 : 82% (IC95 74-88%) | CLV méd +5.1%
    limite haute    n=125 | CLV>0 : 69% (IC95 60-76%) | CLV méd +3.4%
  H1b (descriptif) : limite closing / limite move — médiane x6.35 sur n=377

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 72.8% de CLV>0 (n=975)
    ATP         n= 380 | CLV>0 : 75% (IC95 70-79%) | CLV méd +4.9%
    WTA         n= 377 | CLV>0 : 70% (IC95 65-74%) | CLV méd +4.6%
    Challenger  n=  41 | CLV>0 : 61% (IC95 46-74%) | CLV méd +2.9%
    autre       n= 177 | CLV>0 : 77% (IC95 71-83%) | CLV méd +6.4%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 27.2% (IC95 24.5-30.1%, n=975)
  — par ampleur du move —
    2-3%     n= 225 | retournés 45% (IC 39-51%)  <-- hors IC global
    3-6%     n= 232 | retournés 35% (IC 29-41%)
    6-12%    n= 301 | retournés 15% (IC 11-19%)  <-- hors IC global
    >12%     n= 207 | retournés 16% (IC 12-22%)  <-- hors IC global
  — par avance sur le match —
    <1h      n=  41 | retournés 71% (IC 56-82%)  <-- hors IC global
    1-6h     n= 127 | retournés 37% (IC 29-46%)
    6-24h    n= 568 | retournés 25% (IC 21-29%)
    >24h     n= 239 | retournés 20% (IC 15-26%)
  — par circuit —
    WTA         n= 377 | retournés 30% (IC 26-35%)
    ATP         n= 380 | retournés 25% (IC 21-30%)
    Challenger  n=  41 | retournés 39% (IC 26-54%)
    autre       n= 177 | retournés 23% (IC 17-29%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  181 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 19% positifs | n=2582
    T+ 2min : CLV atteignable médian +0.0% | 19% positifs | n=2582
    T+10min : CLV atteignable médian +0.0% | 17% positifs | n=2586
    T+30min : CLV atteignable médian +0.0% | 12% positifs | n=2590
    T+60min : CLV atteignable médian +0.0% | 7% positifs | n=2590
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    coolbet            17 min (n=29)
    888sport           21 min (n=12)
    winamax.fr         21 min (n=38)
    1xbet              21 min (n=44)
    unibet.fr          22 min (n=32)
    tipico             26 min (n=31)
    betway             26 min (n=30)
    22bet              28 min (n=44)
    bet365             31 min (n=18)
    netbet             31 min (n=39)
    bwin               31 min (n=14)
    betsson            33 min (n=57)
    bet365.fr          36 min (n=11)
    unibet             53 min (n=21)
    pmu                61 min (n=39)
    leovegas           61 min (n=41)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  2154 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 363/2154 = 17% (IC95 15-18%)
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
  267 marchés Polymarket avec ticks (fenêtre récente)
  59 matchs appariés avec corrélation exploitable (|r|>0,15)
  décalage médian du pic de corrélation : +3 min
  (négatif = Polymarket PRÉCÈDE Pinnacle = signal en amont du steam)

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  19 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  4 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  1 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n=  3 — sous 30, suivi sans verdict
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
