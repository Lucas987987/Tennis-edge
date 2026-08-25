# Tennis-edge — Ce que nos données disent
### État complet des analyses au 25 août 2026 (854 moves, 1 025 matchs calibration, 11 hypothèses gelées)

---

## 1. Le socle : ce qui est solidement établi

**Le steam est de l'information, pas du bruit.** Sur les 854 mouvements
significatifs détectés sur la référence sharp depuis le début de la collecte,
**72,5 % (619/854) se retrouvent amplifiés dans le prix de clôture** des
opérateurs grand public. CLV médian de la population : **+4,7 %**, moyenne
+6,6 %. Une large part de cet écart n'est pas du « momentum » mais du **retard
de propagation** : Pinnacle bouge en premier, les books lents encaissent
l'information avec délai — le prix capturé à la détection est en partie un
prix périmé. C'est la prémisse mesurée du projet entier, et c'est désormais
aussi **l'étalon (p0 témoin) contre lequel toute hypothèse doit se battre**.

**Le filtre d'alerte ajoute de la valeur au-dessus du témoin.** Le test de
contrôle décisif (août) : **+11,2 points de CLV** pour les mouvements alertés
vs non alertés, intervalles de confiance disjoints, robuste au test de
permutation. C'est le **critère primaire** du dispositif — pré-spécifié, jugé
seul à α=0,05, hors famille Holm, gelé (rétroactivement, et marqué comme tel)
au 25/08/2026.

**Le dévig de Shin est validé** (biais non matériel vs proportionnel) et sert
de convention unique partout : calibration, attendus, hypothèses.

---

## 2. La calibration des bookmakers (étude sur 1 025 matchs dénoués)

Probabilités dévigées (Shin), closing strictement pré-match, deux entrées par
match (une par côté) :

| Annoncé | Observé | Écart | n |
|---|---:|---:|---:|
| 0–15 % | 5,9 % | **−4,4 pts** | 68 |
| 15–30 % | 23,4 % | −0,2 | 269 |
| 30–45 % | 41,7 % | +3,8 | 528 |
| 45–55 % | 50,0 % | **±0,0** | 320 |
| 55–70 % | 58,3 % | −3,8 | 528 |
| 70–85 % | 76,6 % | +0,2 | 269 |
| 85–100 % | 94,1 % | **+4,4 pts** | 68 |

Lecture : **le marché est remarquablement calibré au centre** (45-55 % : pile
50,0 %). Aux extrêmes, la signature favori-outsider classique : les très gros
outsiders gagnent *moins* que leur probabilité dévigée (−4,4 pts), les très
gros favoris *plus* (+4,4 pts) — même après retrait de la marge.

**Aucun opérateur ne prédit mieux que les autres.** Scores de Brier sur
échantillon commun : 13 opérateurs dans une fourchette de **~0,002** (bwin
0,2150 en tête, Pinnacle 0,2162 — un écart qui est du bruit). Conclusion
opérationnelle : la différence entre books n'est pas la qualité de la
prédiction, c'est la marge et la vitesse de réaction.

---

## 3. Le journal forward (paper trading — critère primaire en construction)

Surface « match » : **31 paris dénoués**, 4 ouverts. CLV vs clôture :
médiane **+6,9 %**, moyenne +9,4 %, **74 % positifs** (IC95 : 57–86 %).

Lecture honnête, dans les deux sens :
- le CLV réalisé du journal est solidement positif et cohérent avec le test
  de contrôle ;
- **mais 74 % ≈ le taux de base témoin de 72,5 %**. Le seuil « >50 % » que le
  rapport affiche en vert est l'ancien étalon ; la vraie question — le journal
  bat-il *le témoin* ? — demande plus de n (le différentiel de +11,2 pts du
  test de contrôle porte sur un échantillon plus large que les 31 dénoués).
  Extension prévue : appliquer le p0 témoin au verdict du journal aussi.
- **À annoter au bilan de dimanche** : les entrées du 25/08 entre 09:01 et
  ~11:00 UTC ont été produites sous seuils par défaut (régression sparse,
  corrigée le jour même).

Sets 1 et 2 : volumes encore faibles, pas de conclusion.

---

## 4. Les 11 hypothèses gelées — état au filtre complet
*(binomial exact contre p0 témoin 72,5 % ou attendu Shin, plancher n≥30 en
amont, correction de Holm sur la famille, α global 5 %)*

**Famille : 3 testables sur 11, 0 rejet.** Aucune hypothèse secondaire n'est
confirmée à ce stade — et c'est le dispositif qui fonctionne, pas qui échoue.

| Hypothèse (gel) | État | Détail |
|---|---|---|
| Calibration 2,20-3,50 (04/08) | **Morte** | 95/263 = 36,1 % vs attendu Shin 36,3 %. Le résidu in-sample de +5,8 pts est retombé à zéro out-of-sample : c'était un été à surprises, pas un edge. |
| Heure du match (04/08) | Ne rejette pas | 132/242 sur le groupe « tard », p=0,09. Le différentiel tard/tôt in-sample ne se confirme pas encore. |
| Variation de marge (09/08) | **Prometteuse, hors famille** | 13/13 refermés sur « marge élargie ». Parfait mais n<30 : suivi, aucune conclusion avant le seuil maison. |
| Round (10/08) | **Prometteuse, hors famille** | 22/23 sur « premiers tours ». Même statut : à confirmer à n≥30. |
| Gros move (10/08) | Trop tôt | Pas assez de prix mous loggés pour mesurer le CLV OOS. |
| Ouverture précoce (13/08) | Trop tôt | n insuffisant. |
| Renforcement outsider (14/08) | **Hors périmètre binomial** | Mesure une dérive de marché, pas un CLV — test de gradient dédié à définir avant réintégration. Dernier état : 17/34 (50 %), gradient in-sample (49→65 % par écart) non répliqué pour l'instant. |
| Book réactif (14/08) | Trop tôt | n insuffisant sur le groupe « rapide ». |
| Seuil adaptatif (04/08) | **⚠️ Sous le témoin — enquête ouverte** | 1231/2042 = 60,3 % vs témoin 72,5 %. Voir §6. |
| Confirmation Betfair (16/08) | Trop tôt | n insuffisant. |
| Âge du mouvement (16/08) | Trop tôt | Le bucket <5min (in-sample : 92-96 % refermés) attend son n OOS. |

---

## 5. Les hypothèses déjà enterrées (avant ce cycle)

- **Fatigue / forme des joueurs** : étude conclue — le marché price déjà ces
  facteurs. Aucun résidu exploitable.
- **Elo (Tennis Abstract)** : ~58 % de précision après correction du
  look-ahead — honnête, mais le marché est mieux informé que l'Elo. Utile
  comme référence pédagogique, pas comme signal.
- **G2 (écart ≥3 %) à ROI +25,9 %** : chiffre non fiable — divergence CLV/ROI
  et biais de sélection (prendre le meilleur prix parmi beaucoup de books
  gonfle mécaniquement le ROI). Jamais publié comme claim, à raison.
- **Résidu de calibration 2,20-3,50** : voir tableau — mort proprement,
  out-of-sample, au filtre.

---

## 6. Les deux alertes ouvertes

**Le seuil adaptatif referme moins que le move moyen (60,3 % vs 72,5 %).**
Deux lectures possibles, à départager : soit les seuils gelés par book
sélectionnent réellement des mouvements de moindre qualité que le tout-venant
(ce qui serait un problème sérieux de la sélection), soit les deux populations
ne sont pas comparables — les CLV du suivi adaptatif viennent du détecteur par
book soft, le témoin vient des moves référencés Pinnacle. **Enquête prioritaire**
avant toute conclusion : recalculer le taux de base sur la population du
détecteur par book lui-même.

**Le libellé du flag ⚠️ est imprécis pour la calibration** : le rapport
affiche « sous le taux de base témoin » alors que son p0 est l'attendu Shin
(36,1 % vs 36,3 % = résidu nul, pas une sous-performance). Cosmétique, à
corriger au prochain passage.

---

## 7. Les leçons de méthode (payées, encaissées, encodées)

1. **Le look-ahead est partout** : cinq instances corrigées (Elo, courbe
   Pinnacle, valeur d'ouverture, calcul ROI, tri des flux Polymarket) — plus
   une sixième attrapée le jour même en réécrivant l'étude de calibration
   (dernier point de courbe = in-play → « calibration » miraculeuse à 98 %).
   Vérification premier réflexe sur toute nouvelle analyse.
2. **Le biais de sélection gonfle les ROI** : max-price multi-books = chiffre
   invendable. Le CLV reste le juge unique.
3. **Tester contre 50 % quand on possède un témoin est une faute** : le taux
   de base réel (72,5 %) a transformé « 3 rejets » en « 0 rejet » — dans le
   bon sens : celui de la vérité.
4. **Les tests multiples se comptent et se corrigent** : 11 hypothèses, Holm,
   plancher n≥30 pré-enregistré appliqué en amont, primaire isolé et daté.
5. **La lecture vide silencieuse est le pire mode de panne** : trois
   occurrences (15/08, 25/08 matin, troncature d'archivage) — désormais
   entourées de garde-fous bruyants.

---

## 8. Ce que ça implique

**Pour le canal** : le contenu le plus solide et le plus différenciant est
prêt — calibration des books, Brier par opérateur, pédagogie du steam et du
retard de propagation, et l'honnêteté méthodologique elle-même (« 0 hypothèse
confirmée » est un post, pas une honte).

**Pour la monétisation** : la porte reste fermée, et c'est le dispositif qui
la tient. Le critère primaire est positif ; aucune hypothèse secondaire n'a
gagné le droit d'exister ; le journal forward n'a pas encore le n pour battre
le témoin. Le seuil (~500-1 000 abonnés + track record publié) est inchangé.

**Prochaines échéances des données** : marge et round atteindront n≥30 dans
les semaines qui viennent (verdict automatique au filtre) ; l'enquête seuil
adaptatif ; l'extension du p0 témoin au verdict du journal ; et le test à
deux échantillons alerté-vs-témoin en continu, comme forme définitive du
critère primaire.

---

*Document généré le 25/08/2026 sur les données du dépôt (854 moves,
1 025 matchs de calibration, 31 paris forward dénoués). Chiffres régénérables :
`validation_report.py`, `calibration_books.py`, `moves_detail_hist.csv`.*
