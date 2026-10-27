# Variante expérimentale — trois procédures et verrou « H passé » par côté

**Base technique :** `main@17671d18723c858ea873311a545d8c65b97b877e`, projet 222 `5db5128896bfcb1986b1ca830adae79418ae929f`. Le monde #647, les colliders, les oracles, les huit négatifs, RESET, la limite LAND 210000 ms, la CI canonique et les profils restent identiques à main.

**Réfutation du raccourci 218/222 :** [run différentiel 40397383095](https://github.com/djibian/webeeblocks/actions/runs/40397383095), vraiment compilé et interprété depuis les WBB 232/222, mêmes lectures synthétiques d'un H répétées. Avant le premier virage, source originale 232 compte **1** H, 222 en compte **3**. Ce n'est pas un vol Webots, mais cela réfute la garantie algorithmique de non-double comptage pour 222 dans le modèle testé.

**Correction explicite, dans les blocs élève :**
- `H passé` commence à 0 sur chaque côté ;
- après confirmation par le capteur arrière dans l'intervalle 0.30–0.65, le programme effectue `portes += 1` puis `H passé = 1` ;
- un nouvel écho H ouvert sur ce même côté **n'entraîne plus** un nouveau passage ; au troisième côté, si la mesure haute/basse prétend néanmoins montrer un H ouvert après un H déjà compté, la branche `état = 2` signale l'incohérence ;
- la discrimination `H ouvert / H fermé avec concordance ±0.08 m / mesure ambiguë` reste explicite ;
- `distance += 8` regroupe deux mises à jour de décimètres de **commandes acquittées**, après les consignes de passage ; les commandes MOVE restent 0.2,0.4,0.2 m, inchangées et conformes.

Les blocs sont tous des primitives Blockly ordinaires : **232 blocs / 10 variables / 3 procédures / 17 IF / 34 comparaisons**. La suppression de deux modifications intermédiaires de `distance` est légitime seulement sur le chemin fautif terminal où la boucle n'utilise plus la distance. La capacité de débogage est meilleure par modules, **mais le total et la complexité des décisions restent importants** ; aucun progrès massif de charge cognitive n'est présumé.

**Test requis :** même WBB fichier exact, vrai Blockly 13.2.1/compiler/observer/projet, différentiel redétection, puis 7 positifs + 8 négatifs + RESET frais + LAND forcé exact 210000 ms sur l'exécutable Webots R2025a du nouveau main. Archiver premier échec et preuves. Aucun PASS élève, GO auteur, Ready, merge ni TEST_REQUIRED.
