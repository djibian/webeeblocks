# WebeeBlocks — protocole minimal d’essai humain

Ce document prépare le premier essai avec un élève sans modifier l’expérience produit. Il ne constitue ni un tutoriel élève ni une procédure de formation.

## But

Observer si un collégien travaillant seul peut accomplir la boucle suivante sans médiation technique :

`comprendre le défi → programmer → lancer → interpréter → corriger → optimiser`

La seule consigne à donner à l’élève est :

> Fais réussir le parcours, puis essaie d’améliorer ton temps.

Ne donner aucune solution de trajectoire, aucune valeur de distance/angle et aucune explication technique sur Webots, Blockly ou le contrôleur.

## Préparation technique — enseignant uniquement

Pré-requis :
- dépôt `djibian/webeeblocks` sur la branche `webots-ci` ;
- Webots R2025a ;
- variable `WEBOTS_HOME` pointant vers l’installation R2025a ;
- compilateur C compatible avec les Makefiles Webots ;
- connexion réseau fonctionnelle, ou ressources Webots/Robot Window déjà présentes en cache, car le monde et la Robot Window chargent encore des ressources externes.

Depuis la racine du dépôt :

```bash
make -C controllers/crazyflie_l_course
make -C controllers/crazyflie_collision_observer
webots worlds/crazyflie_runtime_obstacle.wbt
```

Le fichier `worlds/.crazyflie_runtime_obstacle.wbproj` demande l’ouverture de la Robot Window pour `Crazyflie Runtime`. Avant l’arrivée de l’élève, vérifier seulement que :
- le monde est chargé ;
- la fenêtre WebeeBlocks/Blockly est visible ;
- l’état élève est `PRÊT` ;
- le bouton `Lancer le vol` est effectivement activé et cliquable, ce qui confirme que le transport Robot Window est initialisé ;
- le drone est à sa position initiale ;
- aucune mission de démonstration n’est préchargée donnant implicitement la solution.

Si cette préparation échoue, interrompre l’essai : il s’agit d’un défaut technique, pas d’une observation pédagogique.

## Observation

Ne guider l’élève qu’en cas de blocage durable. Noter le premier point où il ne peut plus progresser seul.

Observer au minimum :
1. comprend-il l’obstacle, G1, G2 et la condition de réussite ?
2. identifie-t-il les blocs utiles ?
3. découvre-t-il seul comment lancer le vol ?
4. comprend-il `RÉUSSI`, `COLLISION`, `PASSAGE MANQUÉ` et le chrono ?
5. modifie-t-il son programme puis relance-t-il sans aide technique ?
6. tente-t-il une optimisation et peut-il expliquer simplement ce qu’il a changé ?

Pour chaque friction, consigner :
- moment précis ;
- comportement observable ;
- aide minimale éventuellement nécessaire ;
- résultat après cette aide.

## Classification des problèmes

- **Défaut technique** : l’interface, le simulateur ou le vol empêche une action qui devrait fonctionner.
- **Friction UX** : l’action existe mais l’élève ne la trouve pas ou interprète mal le retour de l’interface.
- **Difficulté pédagogique normale** : l’élève comprend l’outil mais doit raisonner pour construire ou améliorer sa stratégie.

Ne proposer aucun changement produit pendant l’essai. Identifier d’abord le premier obstacle réellement bloquant ou reproductible.

## Fin de l’essai

L’essai peut être considéré exploitable dès que l’on dispose soit :
- d’une boucle complète réussie et d’au moins une tentative d’optimisation ;
- soit d’un blocage clair empêchant l’élève de poursuivre seul.

Reporter ensuite dans GitHub le premier blocage observable avec sa classification et les faits, sans prescrire d’emblée la solution. Le prochain incrément produit devra être le plus petit correctif réversible répondant à ce blocage.
