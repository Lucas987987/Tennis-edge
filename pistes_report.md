# Pistes exploratoires — rapport du 2026-09-06

```
==============================================================
PISTE 1 — LIMITES PINNACLE AU MOMENT DU MOVE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  477 moves appariés | témoin population appariée : 75.7% de CLV>0
  terciles de limite : basse <= 200 < moyenne <= 883 < haute
    limite basse    n=161 | CLV>0 : 75% (IC95 67-81%) | CLV méd +5.5%
    limite moyenne  n=158 | CLV>0 : 85% (IC95 78-90%) | CLV méd +5.1%
    limite haute    n=158 | CLV>0 : 68% (IC95 60-75%) | CLV méd +3.2%
  H1b (descriptif) : limite closing / limite move — médiane x6.12 sur n=477

==============================================================
PISTE 7 — SEGMENTATION PAR CIRCUIT
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  témoin global : 73.7% de CLV>0 (n=1085)
    ATP         n= 380 | CLV>0 : 75% (IC95 70-79%) | CLV méd +4.9%
    WTA         n= 377 | CLV>0 : 70% (IC95 65-74%) | CLV méd +4.6%
    Challenger  n=  73 | CLV>0 : 73% (IC95 61-82%) | CLV méd +3.8%
    autre       n= 255 | CLV>0 : 78% (IC95 73-83%) | CLV méd +5.8%
  Lecture : un segment ne devient hypothèse gelée que si son IC95
  se sépare du témoin global avec n>=30.

==============================================================
PISTE 5 — PRÉDIRE LES RETOURNEMENTS (CLV<=0)
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  taux global de retournement : 26.3% (IC95 23.7-29.0%, n=1085)
  — par ampleur du move —
    2-3%     n= 248 | retournés 45% (IC 39-51%)  <-- hors IC global
    3-6%     n= 264 | retournés 33% (IC 28-39%)
    6-12%    n= 338 | retournés 14% (IC 11-18%)  <-- hors IC global
    >12%     n= 222 | retournés 15% (IC 11-20%)  <-- hors IC global
  — par avance sur le match —
    <1h      n=  47 | retournés 70% (IC 56-81%)  <-- hors IC global
    1-6h     n= 144 | retournés 36% (IC 29-44%)
    6-24h    n= 609 | retournés 24% (IC 21-28%)
    >24h     n= 285 | retournés 19% (IC 15-24%)  <-- hors IC global
  — par circuit —
    WTA         n= 377 | retournés 30% (IC 26-35%)
    ATP         n= 380 | retournés 25% (IC 21-30%)
    Challenger  n=  73 | retournés 27% (IC 18-39%)
    autre       n= 255 | retournés 22% (IC 17-27%)

==============================================================
PISTE 3 — DÉCROISSANCE DU PRIX APRÈS ALERTE
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  263 alertes appariées à au moins un book soft
  — alertes à >6h du coup d'envoi —
  — alertes à 1-6h du coup d'envoi —
  — alertes à <1h du coup d'envoi —
    T+ 0min : CLV atteignable médian +0.0% | 24% positifs | n=3430
    T+ 2min : CLV atteignable médian +0.0% | 23% positifs | n=3431
    T+10min : CLV atteignable médian +0.0% | 21% positifs | n=3437
    T+30min : CLV atteignable médian +0.0% | 15% positifs | n=3449
    T+60min : CLV atteignable médian +0.0% | 9% positifs | n=3452
  Lecture : la différence T+0 vs T+30 est le prix de la lenteur —
  c'est la fenêtre à annoncer aux abonnés et la décote du ROI papier.

==============================================================
PISTE 4 — LA CASCADE DES BOOKS
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  délai médian pour parcourir 50 % du move (n>=10 alertes) :
    winamax.fr         21 min (n=43)
    1xbet              21 min (n=81)
    unibet.fr          23 min (n=40)
    marathonbet        23 min (n=10)
    22bet              25 min (n=75)
    888sport           25 min (n=25)
    betway             26 min (n=43)
    tipico             26 min (n=43)
    coolbet            27 min (n=60)
    netbet             30 min (n=50)
    betsson            34 min (n=86)
    bet365             38 min (n=26)
    bet365.fr          39 min (n=17)
    bwin               52 min (n=43)
    unibet             55 min (n=38)
    leovegas           61 min (n=71)
    pmu                61 min (n=62)
  Lecture : le bas du classement = les books où le CLV vit le plus
  longtemps. Stabilité à vérifier avant tout gel en hypothèse.

==============================================================
PISTE 6 — PROPAGATION ML -> MARCHÉ SET1
(exploratoire, protocole gelé le 2026-08-25 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  2887 paires (fenêtre alerte / fenêtre témoin même match, set1)
  fenêtre alerte plus baissière que sa fenêtre témoin : 570/2887 = 20% (IC95 18-21%)
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
  83 marchés Polymarket avec ticks (fenêtre récente)
  14 matchs appariés avec corrélation exploitable (|r|>0,15)
  TROP TÔT : verdict à n>=30 matchs — le protocole est gelé,
  la donnée s'accumule toute seule. Relance hebdomadaire.

==============================================================
CONFIRMATION PINNACLE — hypothèse ouverture précoce
(exploratoire, protocole gelé le 2026-08-26 — voir frozen_pistes.json ;
 n<30 = suivi sans conclusion ; témoin = population concernée)
==============================================================
  23 signaux POSTÉRIEURS au gel (les 62 signaux du 13-26/08 ayant servi à formuler le protocole sont exclus).
  6 signaux appariés (Pinnacle + book, fenêtre 60min)
    Pinnacle CONFIRME (>= 0.5pt en 60min)      n=  1 — sous 30, suivi sans verdict
    Pinnacle ne confirme pas                   n=  5 — sous 30, suivi sans verdict
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
