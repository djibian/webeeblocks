# Grand Prix #587 — décomposition en procédures du témoin sans murs (expérience, NON QUALIFIÉE)

**But :** tester une amélioration de la construction, de la lecture et de la correction par un collégien, **sans prétendre que renommer ou masquer 389 blocs rend l'algorithme accessible**. Cette expérience n'est ni le starter élève ni le témoin officiel. Aucun changement de moteur, de monde, de règles, de matériel, de workflow CI, d'oracle, de RESET, de LAND ou de limite 210 s. Le seul fichier partagé modifié ajoute l'appel au vérificateur dans les tests core Blockly existants ; aucune sélection/condition de succès n'est affaiblie.

## Provenance et domaine

- Contrat au départ : `main@aa8e1556cff45bfd5bde1b29593afabe5522e486`, AGENTS V5 `c00e855a431b1b83382ba333b0db490a8c330e53`, vision `121409284eba687941c9f1f195077007c3352855`, roadmap `e150cf29129304e54ce3a2eb7cd8208dbf648876`.
- Point de départ immuable : témoin #655 `6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7`, `experiments/grand-prix-no-wall/Grand-Prix-sans-murs-experimental.wbb`, blob Git `947c9f67074a4530083426f0dc467fab3b90cce4`. Il ne qualifie que le monde expérimental #647 : **cinq réussites natives complètement archivées**, deux archives partielles, deux échecs Webots pré-READY et plusieurs négatifs encore absents ; voir son rapport originel.
- Les deux fichiers `.wbb` sont conservés localement dans ce dossier, avec la même activité `progression-grand-prix-u-v1`. Les numéros de configuration et la géométrie du monde ne sont pas entrés dans le programme.
- C'est un **contrôle expérimental de décomposition**, pas une tentative de redéployer/combiner #647/#655/#659/#660 ni une qualification du monde final #635 (notamment H terminal composite #644). Les corrections natives LAND #637/#700 et Qt #665/#701 restent indépendantes.

## Programme réellement éditable

Le projet `Grand-Prix-procedures-sans-murs.wbb` emploie uniquement les blocs ordinaires déjà disponibles sur main : variables, conditions, `répéter`, `jusqu'à`, déplacements, capteurs et procédures sans paramètres (#658). Aucun nouveau bloc `détecter H`, `faire un côté`, `arriver`, aucune donnée du monde/oracle n'est injectée.

La **chaîne principale** est désormais : décoller → monter → **initialiser la mémoire** → répéter trois fois **explorer un côté** → atterrir. Les trois définitions ouvrables/modifiables sont : **initialiser la mémoire** (11 initialisations), **explorer un côté** (recherche, décision de virage, mémoire du côté), **observer et décider** (observations frontales/latérales, passage, confirmation, comptage, fermeture, pose). Les noms sont des étiquettes visibles ; chaque action reste construite par l'élève et peut être examinée bloc par bloc. Les variables sont partagées, sans argument magique.

| Mesure de structure du vrai .wbb | Source #655 | Variante |
|---|---:|---:|
| Nombre total de blocs expressions comprises | 389 | 395 |
| Variables déclarées / utilisées | 12 / 11 | 11 / 11 |
| Procédures définies | 0 | 3 |
| Longueur de chaîne principale | 15 | 5 |
| Appels de procédures dans l'espace de travail | 0 | 3 |

**Le nombre total de blocs augmente.** La profondeur interne de `observer et décider`, le nombre de décisions et les constantes de seuil restent substantiels. La variante n'est donc **pas encore un programme authentiquement accessible à une classe**, et aucune optimisation cognitive chiffrée n'est revendiquée en l'absence d'essai utilisateur.

## Test discriminant

`node experiments/grand-prix-pupil-procedures/verify.js --structural-only` vérifie sans dépendances la présence/identité des blocs, variables et définitions ; développe les appels et établit une égalité exacte avec l'arbre des instructions Blockly de #655, après exclusion des seuls IDs et coordonnées d'éditeur. `node experiments/grand-prix-pupil-procedures/verify.js`, dans un checkout préparé avec Blockly 13.2.1, ajoute : chargement et réouverture, préflight Grand Prix, compilation AST et égalité stricte des instructions de l'AST après expansion des appels.

Le test core partagé `tools/ci/test_runtime_v2_variables.js` invoque désormais le vérificateur complet sur le HEAD du candidat. Observer son résultat CI réel avant toute affirmation de chargement/préflight réussi ; ne pas convertir une CI Draft en GO.

Cette équivalence est **statique**, pas un verdict de vol : chaque appel est un pas d'interpréteur et le temps réel/les effets des capteurs/déplacements restent à contrôler. Les procédures ne transforment pas les retours de MOVE en odométrie et ne résolvent pas la non-observabilité latérale hors des montants. Aucun replay natif de cette variante n'est revendiqué.

Le prochain test natif doit comparer la même variante dans le monde **final sans murs et H fermé composite**, sur toutes les configurations requises 1/2/3 H, incluant côtés sans H, virages, pose, marges au gabarit 9 cm, saturations des capteurs, comportements négatifs, RESET et LAND commandé **à exactement 210 s** (avec complétion). Refuser les crashs pré-READY sans les transformer en échec élève et archiver RUN/SHA/monde/binaire/AST/manifestes. Aucun oracle ou délai ne doit être relâché.

## Test pédagogique à mener séparément

Comparer A (389 blocs linéaires) et B (395 en trois procédures), à contraintes et consignes identiques : retrouver l'endroit où un H est compté, expliquer ce qu'est une distance *commandée*, prédire un côté sans H, localiser une erreur volontaire de seuil, corriger en pas-à-pas, enregistrer et réouvrir le même `.wbb`. Chronométrer la recherche du bon bloc, le nombre de panneaux et de défilements, les erreurs de modification, la restitution sans aide et la réussite/échec observée. Décider ensuite sur ces **mesures**, non sur « trois procédures = accessible ».

**Décision provisoire :** le refactoring conserve strictement la logique du témoin expert, mais **ne réduit pas son coût conceptuel** ; l'objectif #587 reste OPEN. Rechercher ensuite une simplification algorithmique avec capteurs génériques, et la qualifier nativement sans murs avant tout PASS pédagogique. Pas de refonte officielle des activités 2–7, pas de TEST_REQUIRED ni de vol réel.
