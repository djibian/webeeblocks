# Monde d'accueil scolaire neutre

Le paquet Windows scolaire ouvre `crazyflie_classroom_start.wbt`, distribué
sous le nom de lancement historique `worlds/crazyflie_runtime_v2.wbt`.
Avant toute sélection, il contient le sol, l'éclairage, la caméra, le drone et
l'évaluateur technique de l'activité 1 ; aucune géométrie d'exercice ni aucun
évaluateur des anciens scénarios n'est instancié. La connexion peut devenir
`PRÊT`. Le chemin existant **Démarrer une activité / Ouvrir / exécuter** prépare
ensuite le profil par `prepareActivity` avant le programme élève.

Le monde historique reste intact dans le dépôt. Ses groupes complets de
32 enfants de scène et 6 évaluateurs sont conservés à l'identique dans
`worlds/scenes/legacy-scene-v1.wbo` et `legacy-evaluators-v1.wbo`.
Le test de scène compare ces ressources et le monde d'accueil à l'extraction
exacte de ce monde historique pour empêcher leur divergence silencieuse.

Seul un `WorldInfo` explicitement nommé `WEBEEBLOCKS_CLASSROOM_START_WORLD`,
sans groupe de scène partiel ou déjà sélectionné, autorise la lecture de ces
ressources à la place d'un export initial. Un fichier manquant, vide ou trop
grand refuse avant modification ; un import incomplet conserve le refus du
décollage. Les contrôles de type, du nombre attendu et de chaque enfant restent
identiques. Les anciens mondes dédiés et le refus après perte des snapshots
d'une scène déjà sélectionnée conservent leur contrat.

Les transitions activité 1 ↔ activités historiques gardent le même contrôleur,
les mêmes évaluateurs et la même caméra de restauration. RESET et l'ouverture
`.wbb` ne créent pas de second état pédagogique ni d'historique élève.
L'activité 1 reste le même scénario accepté par le propriétaire dans #619 ;
aucun seuil, objectif, résultat ou preuve historique n'est affaibli.

La CI conserve la campagne activité 1/2 sur l'ancien monde, puis la répète sur
le monde d'accueil avec **les mêmes contrôles et cas négatifs**. Le second
artefact `progression-neutral-start` exige en outre l'absence native des trois
groupes avant READY. Les preuves historiques restent dans
`progression-sequence-mission` ; les deux sont retenues par la CI existante.
Les tests C++ injectés couvrent aussi le démarrage neutre, les ressources
absentes/vides/surdimensionnées, un mauvais type de WorldInfo, les groupes
partiels existants, l'import partiel et les allers-retours de scène.

Ce résultat traite le monde de départ de #621. La perspective des panneaux
est proposée séparément dans #622 ; le rectangle noir demande encore un
diagnostic causal et l'expérience complète doit être observée sur Windows
R2025a. Aucun PASS de nouvelle archive, acceptation du Grand Prix ou vol réel
n'est déduit de ces changements.
