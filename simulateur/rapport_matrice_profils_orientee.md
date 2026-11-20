# Matrice orientée exhaustive des profils

Cinq profils réels, vingt directions par branche. Diagnostic historique réutilisé ; aucune activation.

## Synthèse des corrections complètes

| Branche | n | Gain log loss | Gain Brier | IC95 log loss | Exactitude contrôle → challenger |
|---|---:|---:|---:|---:|---:|
| atp | 405 | -0.017539 | -0.008133 | [-0.034906 ; -0.000277] | 68.89 % → 67.16 % |
| wta | 414 | -0.017564 | -0.007305 | [-0.031281 ; -0.002890] | 64.25 % → 64.01 % |
| challenger | 5028 | -0.008208 | -0.003500 | [-0.011725 ; -0.004607] | 68.28 % → 67.64 % |

## Cellules directionnelles du diagnostic

Le résiduel est celui du premier profil après Elo, service–retour et bilan global. Les métriques de la case inverse portent sur les mêmes matchs.

| Branche | Direction | n | Résiduel (points) | IC95 résiduel | Gain log loss | Gain Brier | Exactitude C → M |
|---|---|---:|---:|---:|---:|---:|---:|
| atp | contreur_contre_equilibre | 47 | +2.505 | [-10.706 ; +15.428] | -0.032164 | -0.013523 | 65.96 % → 63.83 % |
| atp | contreur_contre_grand_serveur | 45 | -6.170 | [-22.528 ; +10.388] | -0.045795 | -0.021724 | 66.67 % → 53.33 % |
| atp | contreur_contre_retourneur_pressant | 27 | -1.860 | [-19.273 ; +17.742] | -0.017626 | -0.010342 | 77.78 % → 62.96 % |
| atp | contreur_contre_serveur_attaquant | 11 | -9.429 | [-29.571 ; +15.050] | -0.074126 | -0.034591 | 72.73 % → 72.73 % |
| atp | equilibre_contre_contreur | 47 | -2.505 | [-15.428 ; +10.706] | -0.032164 | -0.013523 | 65.96 % → 63.83 % |
| atp | equilibre_contre_grand_serveur | 52 | -6.415 | [-15.750 ; +2.953] | -0.007835 | -0.003316 | 78.85 % → 82.69 % |
| atp | equilibre_contre_retourneur_pressant | 53 | +7.098 | [-4.466 ; +18.168] | +0.005144 | +0.002210 | 62.26 % → 60.38 % |
| atp | equilibre_contre_serveur_attaquant | 18 | -8.254 | [-25.316 ; +11.025] | -0.082246 | -0.037930 | 72.22 % → 72.22 % |
| atp | grand_serveur_contre_contreur | 45 | +6.170 | [-10.388 ; +22.528] | -0.045795 | -0.021724 | 66.67 % → 53.33 % |
| atp | grand_serveur_contre_equilibre | 52 | +6.415 | [-2.953 ; +15.750] | -0.007835 | -0.003316 | 78.85 % → 82.69 % |
| atp | grand_serveur_contre_retourneur_pressant | 30 | +1.139 | [-16.669 ; +18.588] | -0.019512 | -0.008998 | 56.67 % → 63.33 % |
| atp | grand_serveur_contre_serveur_attaquant | 16 | -7.792 | [-23.020 ; +9.582] | +0.019861 | +0.004719 | 87.5 % → 81.25 % |
| atp | retourneur_pressant_contre_contreur | 27 | +1.860 | [-17.742 ; +19.273] | -0.017626 | -0.010342 | 77.78 % → 62.96 % |
| atp | retourneur_pressant_contre_equilibre | 53 | -7.098 | [-18.168 ; +4.466] | +0.005144 | +0.002210 | 62.26 % → 60.38 % |
| atp | retourneur_pressant_contre_grand_serveur | 30 | -1.139 | [-18.588 ; +16.669] | -0.019512 | -0.008998 | 56.67 % → 63.33 % |
| atp | retourneur_pressant_contre_serveur_attaquant | 13 | +11.432 | [-9.451 ; +35.627] | +0.029996 | +0.015597 | 69.23 % → 84.62 % |
| atp | serveur_attaquant_contre_contreur | 11 | +9.429 | [-15.050 ; +29.571] | -0.074126 | -0.034591 | 72.73 % → 72.73 % |
| atp | serveur_attaquant_contre_equilibre | 18 | +8.254 | [-11.025 ; +25.316] | -0.082246 | -0.037930 | 72.22 % → 72.22 % |
| atp | serveur_attaquant_contre_grand_serveur | 16 | +7.792 | [-9.582 ; +23.020] | +0.019861 | +0.004719 | 87.5 % → 81.25 % |
| atp | serveur_attaquant_contre_retourneur_pressant | 13 | -11.432 | [-35.627 ; +9.451] | +0.029996 | +0.015597 | 69.23 % → 84.62 % |
| wta | contreur_contre_equilibre | 53 | -0.472 | [-10.641 ; +10.480] | -0.014099 | -0.006057 | 56.6 % → 52.83 % |
| wta | contreur_contre_grand_serveur | 31 | +8.295 | [-6.098 ; +22.894] | -0.140874 | -0.053627 | 61.29 % → 58.06 % |
| wta | contreur_contre_retourneur_pressant | 20 | -11.162 | [-30.761 ; +12.389] | +0.006328 | +0.002397 | 70.0 % → 65.0 % |
| wta | contreur_contre_serveur_attaquant | 24 | -10.736 | [-21.834 ; +1.601] | -0.002819 | -0.001969 | 87.5 % → 87.5 % |
| wta | equilibre_contre_contreur | 53 | +0.472 | [-10.480 ; +10.641] | -0.014099 | -0.006057 | 56.6 % → 52.83 % |
| wta | equilibre_contre_grand_serveur | 40 | +0.289 | [-11.057 ; +12.021] | -0.003712 | -0.002700 | 75.0 % → 72.5 % |
| wta | equilibre_contre_retourneur_pressant | 32 | +9.506 | [-6.604 ; +26.744] | +0.005536 | +0.005590 | 46.88 % → 65.62 % |
| wta | equilibre_contre_serveur_attaquant | 37 | -2.074 | [-17.857 ; +14.628] | +0.004967 | +0.001314 | 64.86 % → 64.86 % |
| wta | grand_serveur_contre_contreur | 31 | -8.295 | [-22.894 ; +6.098] | -0.140874 | -0.053627 | 61.29 % → 58.06 % |
| wta | grand_serveur_contre_equilibre | 40 | -0.289 | [-12.021 ; +11.057] | -0.003712 | -0.002700 | 75.0 % → 72.5 % |
| wta | grand_serveur_contre_retourneur_pressant | 30 | -0.783 | [-18.797 ; +15.420] | -0.020706 | -0.009101 | 53.33 % → 50.0 % |
| wta | grand_serveur_contre_serveur_attaquant | 25 | -7.566 | [-19.817 ; +7.657] | -0.021291 | -0.012117 | 80.0 % → 76.0 % |
| wta | retourneur_pressant_contre_contreur | 20 | +11.162 | [-12.389 ; +30.761] | +0.006328 | +0.002397 | 70.0 % → 65.0 % |
| wta | retourneur_pressant_contre_equilibre | 32 | -9.506 | [-26.744 ; +6.604] | +0.005536 | +0.005590 | 46.88 % → 65.62 % |
| wta | retourneur_pressant_contre_grand_serveur | 30 | +0.783 | [-15.420 ; +18.797] | -0.020706 | -0.009101 | 53.33 % → 50.0 % |
| wta | retourneur_pressant_contre_serveur_attaquant | 15 | +15.575 | [-11.859 ; +39.588] | -0.062789 | -0.030506 | 53.33 % → 46.67 % |
| wta | serveur_attaquant_contre_contreur | 24 | +10.736 | [-1.601 ; +21.834] | -0.002819 | -0.001969 | 87.5 % → 87.5 % |
| wta | serveur_attaquant_contre_equilibre | 37 | +2.074 | [-14.628 ; +17.857] | +0.004967 | +0.001314 | 64.86 % → 64.86 % |
| wta | serveur_attaquant_contre_grand_serveur | 25 | +7.566 | [-7.657 ; +19.817] | -0.021291 | -0.012117 | 80.0 % → 76.0 % |
| wta | serveur_attaquant_contre_retourneur_pressant | 15 | -15.575 | [-39.588 ; +11.859] | -0.062789 | -0.030506 | 53.33 % → 46.67 % |
| challenger | contreur_contre_equilibre | 422 | -2.691 | [-6.717 ; +1.208] | +0.002969 | +0.001320 | 65.17 % → 66.35 % |
| challenger | contreur_contre_grand_serveur | 102 | +6.107 | [-3.173 ; +14.645] | +0.002570 | +0.001095 | 65.69 % → 64.71 % |
| challenger | contreur_contre_retourneur_pressant | 125 | -0.110 | [-7.537 ; +7.587] | -0.056935 | -0.027321 | 61.6 % → 56.0 % |
| challenger | contreur_contre_serveur_attaquant | 94 | +2.912 | [-7.405 ; +12.713] | -0.118832 | -0.048371 | 56.38 % → 50.0 % |
| challenger | equilibre_contre_contreur | 422 | +2.691 | [-1.208 ; +6.717] | +0.002969 | +0.001320 | 65.17 % → 66.35 % |
| challenger | equilibre_contre_grand_serveur | 511 | +3.228 | [-0.286 ; +6.928] | -0.005632 | -0.002075 | 63.6 % → 63.6 % |
| challenger | equilibre_contre_retourneur_pressant | 368 | +3.054 | [-1.255 ; +7.500] | -0.003170 | -0.001524 | 67.12 % → 66.58 % |
| challenger | equilibre_contre_serveur_attaquant | 307 | +4.850 | [+0.616 ; +9.127] | -0.011992 | -0.005191 | 67.1 % → 65.15 % |
| challenger | grand_serveur_contre_contreur | 102 | -6.107 | [-14.645 ; +3.173] | +0.002570 | +0.001095 | 65.69 % → 64.71 % |
| challenger | grand_serveur_contre_equilibre | 511 | -3.228 | [-6.928 ; +0.286] | -0.005632 | -0.002075 | 63.6 % → 63.6 % |
| challenger | grand_serveur_contre_retourneur_pressant | 115 | +1.632 | [-5.870 ; +9.339] | -0.023806 | -0.009563 | 64.35 % → 60.87 % |
| challenger | grand_serveur_contre_serveur_attaquant | 109 | -1.295 | [-9.681 ; +6.688] | -0.007524 | -0.002930 | 56.88 % → 60.55 % |
| challenger | retourneur_pressant_contre_contreur | 125 | +0.110 | [-7.587 ; +7.537] | -0.056935 | -0.027321 | 61.6 % → 56.0 % |
| challenger | retourneur_pressant_contre_equilibre | 368 | -3.054 | [-7.500 ; +1.255] | -0.003170 | -0.001524 | 67.12 % → 66.58 % |
| challenger | retourneur_pressant_contre_grand_serveur | 115 | -1.632 | [-9.339 ; +5.870] | -0.023806 | -0.009563 | 64.35 % → 60.87 % |
| challenger | retourneur_pressant_contre_serveur_attaquant | 95 | +0.485 | [-7.469 ; +9.150] | -0.130989 | -0.054307 | 66.32 % → 54.74 % |
| challenger | serveur_attaquant_contre_contreur | 94 | -2.912 | [-12.713 ; +7.405] | -0.118832 | -0.048371 | 56.38 % → 50.0 % |
| challenger | serveur_attaquant_contre_equilibre | 307 | -4.850 | [-9.127 ; -0.616] | -0.011992 | -0.005191 | 67.1 % → 65.15 % |
| challenger | serveur_attaquant_contre_grand_serveur | 109 | +1.295 | [-6.688 ; +9.681] | -0.007524 | -0.002930 | 56.88 % → 60.55 % |
| challenger | serveur_attaquant_contre_retourneur_pressant | 95 | -0.485 | [-9.150 ; +7.469] | -0.130989 | -0.054307 | 66.32 % → 54.74 % |
