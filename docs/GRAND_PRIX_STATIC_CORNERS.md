# Grand Prix — deux cornières L physiques, scène statique (#808)

Ce module consomme le modèle `route_v2` déjà intégré. Il produit **quatre bras Solid** (deux L, branches de 0,60 m, hauteur 1,30 m, boundingObject physique, locked TRUE), sur le bord extérieur du couloir virtuel de largeur 0,60 m dans les 108 variantes géométriques. Les guides blancs et bords rouges sont seulement des Pose **sans collision**.

Pour inspecter un texte de scène : `python3 -c "from tools.grand_prix.route_solid_v2 import example; print(example())"` ; pour les assertions : `python3 -m unittest tools.ci.test_grand_prix_route_solid_v2`.

**Limite impérative :** le monde statique place un robot **sans contrôleur actif**, ni fenêtre Blockly, ni évaluateur ; il ne comporte pas encore les H, la zone d'arrivée, le nouvel oracle #811, ni une preuve native des capteurs/collisions. Il ne peut pas être distribué comme activité, ni réclamer un test humain. Il prépare seulement un monde Webots à intégrer et falsifier nativement. Les exigences RESET, deadline 210000 ms et LAND restent inchangées.
