# Grand Prix — enveloppe balayée des couloirs variables (#811)

Ce module expérimental purement géométrique calcule la **frontière exacte de l'union des trois rectangles de couloir** de `route_v2` (largeur 0,60 m), puis la distance minimale continue entre un déplacement horizontal et chaque segment de cette frontière. Un déplacement est rejeté lorsque le disque du drone de **rayon fixe 0,09 m** atteint la frontière, même si ses deux positions d'échantillonnage sont intérieures. Le contrôle ne se contente donc pas d'échantillonner des points du segment.

Exécution des tests : `python3 -m unittest tools.ci.test_grand_prix_corridor_sweep_v2`. Les tests couvrent les 108 parcours de longueurs et virages, les deux virages de chaque route, le refus d'un raccourci à travers l'intérieur d'un U, la tangence et les valeurs non finies.

**Frontière de preuve :** aucune qualification native R2025a ni simulation d'un vol. Le module ne gère ni l'aire terminale élargie, ni l'orientation/progrès séquentiel, ni les H, ni les collisions physiques, ni les poses, ni RESET/LAND ni la deadline de 210000 ms. Une absence de collision dans la géométrie plane n'est pas une réussite de mission. Aucune fonction de ce module n'est appelée par le contrôleur, l'AST ou l'oracle U actuellement actifs. Les validations finales de #811 et #808 restent nécessaires.
