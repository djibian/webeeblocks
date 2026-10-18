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

## Qualification Windows de l'accueil — #621 clôturée

Les corrections #622 (panneaux), #623 (monde d'accueil neutre) et #630
(perspective de l'overlay Camera Webots 324 × 324, sans suppression du capteur)
sont intégrées. Leur résultat réel a été **accepté par le propriétaire** au
[checkpoint #632](https://github.com/djibian/webeeblocks/issues/632#issuecomment-6247199523),
sur le SHA exact `39b0841c52f9db91ddbc3f80ba3bc1588fab9489`,
l'artefact Windows `WebeeBlocks-Windows-R2025a` ID `12127577400`
et Webots R2025a + Chrome. L'issue #621 est clôturée.

Le PASS observé couvre l'accueil neutre et `PRÊT`, l'absence du rectangle noir
bordé de magenta, les panneaux initialement masqués puis réouvrables, la caméra,
les cas nominal et négatif de l'activité 1, RESET, le parcours 2 → 1,
Enregistrer sous / Enregistrer / Ouvrir `.wbb`, la restauration de scène
et le pas-à-pas. La correspondance de l'ancien rectangle avec l'overlay motive
#630 ; le PASS constate sa disparition dans cet environnement, sans prouver
une absence universelle de défaut sur toute plateforme.

Le [FAIL #629](https://github.com/djibian/webeeblocks/issues/629) sur son
ancien SHA et le [PASS pédagogique #619](https://github.com/djibian/webeeblocks/issues/619)
sur `a38839628c99bf38278ca950ed8e68f363d1b5b3` gardent chacun leur sujet.
#632 n'accepte ni le Grand Prix, ni les activités 2–7, ni le vol réel.
