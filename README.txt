Correctif V3 : installer ce ZIP avec « Appliquer un paquet », puis lancer le workflow
« Correctif V3 - ancrage distribution exacte » et ensuite « Pronostics du jour ».
Cause : le moteur borne p_victoire à 0.005–0.995, le contrôle comparait à p_home brut.
Le workflow vérifie la présence de la borne dans le moteur, modifie uniquement
simulateur/pronostics_du_jour.py et pousse un commit si nécessaire.
Si la branche est protégée, le push échouera et nécessitera une PR.
