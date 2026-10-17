# Présentation initiale de Webots

## Panneaux de développement

La perspective `worlds/.crazyflie_runtime_v2.wbproj` masque **Text Editor**
et replie **Scene Tree**, tout en laissant la vue 3D et la console accessibles.
Les panneaux peuvent être rouverts avec les commandes Webots habituelles.
Le lanceur Windows copie cette perspective dans chaque session et en retire
uniquement l'ouverture automatique de la Robot Window ; Chrome reste ouvert
par le chemin local existant. Le paquet Grand Prix copie aussi cette perspective
dans chacun de ses trois mondes.

Le format est celui du [monde Crazyflie officiel R2025a](https://github.com/cyberbotics/webots/blob/R2025a/projects/robots/bitcraze/crazyflie/worlds/.crazyflie.wbproj)
(blob `07b836554e8cf3869ba2aa4c4200709ce6c2abeb`). Dans l'état Qt des docks,
seul l'octet de visibilité suivant le nom UTF-16 `TextEditor` passe de 1 à 0.
Dans l'état du splitter, les largeurs 272/2002 deviennent 0/2274 : l'arbre est
replié et la vue 3D conserve l'espace disponible. Aucun verrou d'interaction,
fichier texte ouvert ou état de périphérique n'est ajouté.

Sources de lecture/restauration : [WbPerspective](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/app/WbPerspective.cpp),
[WbMainWindow](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/gui/WbMainWindow.cpp)
et [WbSimulationView](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/gui/WbSimulationView.cpp).
La restauration de ces octets a été exécutée avec les vrais `QMainWindow`,
`QDockWidget` et `QSplitter` de Qt 6.7.3 sous Linux, après un état initial où
les panneaux sont visibles, aux largeurs 800 et 1800 px : éditeur caché,
console visible, largeur d'arbre nulle, vue 3D positive ; réouverture des deux
panneaux possible. Cela vérifie le format Qt, pas le rendu réel Windows/R2025a.

## Frontières encore ouvertes de #621

Les changements #622 (perspective) et #623 (vrai monde d'accueil neutre)
sont désormais intégrés. Le paquet Windows utilise ce monde au démarrage ;
les anciennes scènes ne sont chargées qu'après la sélection explicite de
l'activité. La CI de #623 a vérifié le changement de scènes, le refus d'un
TAKEOFF sans SCENE et la fermeture du paquet, mais **pas** le rendu graphique
sur le poste Windows de référence. La disparition du rectangle noir et le
parcours complet de démarrage restent donc à observer dans #621 ; aucune
acceptation humaine du nouveau paquet n'est encore établie.
Le Runtime n'active pas la caméra 324 × 324 du PROTO Crazyflie. Le code R2025a
de `WbWrenTextureOverlay` alloue une image noire sans données mais **masque
initialement** l'overlay. L'hypothèse d'un aperçu caméra restauré doit donc
être vérifiée sur la fenêtre observée ; la présence de la caméra seule ne
prouve pas l'origine du rectangle. Ne pas supprimer le capteur ou modifier le
rendu global pour masquer une cause non établie.

Le PASS humain #619 accepte l'activité 1 au SHA
`a38839628c99bf38278ca950ed8e68f363d1b5b3`. Il ne constitue pas un test de
cette nouvelle perspective ni une acceptation du Grand Prix ou d'un vol réel.
