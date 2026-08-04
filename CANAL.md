# Canal public « Évolution des Cotes Tennis » — kit de lancement

## 1. Nom et description du canal (à copier dans Telegram)

**Nom suggéré** : Évolution Cotes Tennis 📊

**Description (bio du canal)** :
> Observation des mouvements de cotes tennis en avant-match : prix de référence
> (Pinnacle), juste prix estimé (dévig Shin), retards d'ajustement des opérateurs.
> Données horodatées, méthode publique, récap hebdo vérifiable. Aucun pronostic,
> aucune promesse. 18+ · joueurs-info-service.fr

## 2. Message épinglé (le manifeste)

> 📊 **Bienvenue — lisez ceci une fois.**
>
> Ce canal observe une chose précise : **comment les cotes de tennis évoluent
> avant les matchs**, et à quelle vitesse les différents opérateurs s'ajustent
> quand le prix de référence du marché (Pinnacle) bouge.
>
> **Ce que vous recevrez** :
> • 📊 des alertes d'évolution : quel joueur voit sa cote se raccourcir, de
>   combien, et quels opérateurs n'ont pas encore ajusté leur prix par rapport
>   au juste prix estimé (calculé par dévig Shin, méthode publique) ;
> • 📈 un récap hebdomadaire **vérifiable** : chaque chiffre du récap correspond
>   à des messages horodatés publiés ici en amont — y compris quand le marché
>   ne fait pas ce qu'on attendait.
>
> **Ce que vous ne verrez jamais ici** :
> • aucun pronostic, aucune promesse de gain, aucun « taux de réussite » ;
> • aucune incitation à jouer — ce canal est un outil d'observation des
>   marchés, pas un service de conseils.
>
> **Pourquoi cette transparence ?** Parce que ce secteur est saturé de comptes
> qui affichent des résultats invérifiables. Ici, tout est daté, public et
> rejouable. Jugez la qualité de l'information sur la durée, pas sur une
> semaine.
>
> 18+ · Le jeu comporte des risques (endettement, isolement, dépendance).
> joueurs-info-service.fr · 09 74 75 13 13

## 3. Anatomie d'un message d'évolution (généré par canal_public.py)

```
📊 ÉVOLUTION DE COTE · Iga Swiatek vs Aryna Sabalenka (WTA Cincinnati)
📉 Iga Swiatek : 2.30 → 1.85 chez Pinnacle (10 pts de probabilité en sa faveur)
⚖️ Juste prix estimé (dévig Shin) : 1.90
🕐 Départ dans 4h59
🏪 Ajustement des autres opérateurs : unibet 2.20 (+16% vs juste prix)
Le marché a revu Iga Swiatek à la hausse face à Aryna Sabalenka.
Historiquement, ce type d'écart se referme avant le début du match.
—
ℹ️ Information sur l'évolution des marchés de cotes. Ceci n'est pas un conseil.
Aucun résultat n'est garanti.
18+ | Le jeu comporte des risques : joueurs-info-service.fr · 09 74 75 13 13
```

Règles de langage (imposées par le code, à respecter aussi dans vos posts
manuels) : jamais « miser », « parier », « jouer », « pari sûr », « gagner » ;
toujours « évolution », « ajustement », « juste prix », « retard de prix ».

## 4. Mise en place technique (10 minutes)

1. Créer le canal Telegram public → récupérer son @handle.
2. Ajouter votre bot existant comme **administrateur** du canal.
3. Récupérer le chat_id du canal (poster un message puis
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, ou utiliser @userinfobot).
4. Ajouter le secret GitHub `TELEGRAM_PUBLIC_CHAT_ID`.
5. Déployer `scripts/canal_public.py`, `scripts/canal_recap.py` et les deux
   workflows mis à jour. C'est tout : les évolutions partent à chaque cycle de
   capture, le récap chaque dimanche soir. 0 requête API supplémentaire.

## 5. Trajectoire (rappel stratégique)

- **Phase 1 (maintenant)** : canal public gratuit → preuve + audience.
  L'horloge du track record tourne à chaque message horodaté.
- **Phase 2 (~3 mois, si l'audience prend)** : canal premium (mêmes alertes en
  instantané, le public passe en différé 60 min) à petit prix. Le différé se
  règle en une variable dans canal_public.
- **Phase 3 (6-12 mois)** : produits complémentaires (méthode/formation), selon
  la validation forward.
- Positionnement permanent : **outil d'information transparent** — jamais un
  service de pronostics. C'est à la fois l'angle différenciant du marché FR et
  le bon côté de la ligne réglementaire (ANJ/DGCCRF).
