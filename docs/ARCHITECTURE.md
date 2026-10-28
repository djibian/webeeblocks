# WebeeBlocks — architecture maintenue

Cette carte aide à **localiser une responsabilité, suivre ses dépendances et
identifier ses tests**. Elle décrit le code maintenu, sans remplacer la
[vision produit](PRODUCT_VISION.md), la [roadmap](ROADMAP.md), le
[contrat V5](../AGENTS.md) ou les oracles. Les décisions en cours restent sur GitHub.

## Chemin d'exécution d'un projet élève

```text
activité / profil → éditeur Blockly (.wbb) → AST neutre v1
                                  ↓
                     préflight du profil / AST
                                  ↓
                      interpréteur partagé JS
                          ↙             ↘
           backend WWI/Webots        hôte Python + Node
                    ↓                       ↓
          Runtime C / scènes       sûreté / autorité propre
                    ↓                       ↓
         évaluateurs du monde       Crazyflie réel (non qualifié)
```

L'activité définit **le problème**, pas l'algorithme solution. L'AST, le
préflight et l'interpréteur séparent la sémantique des plateformes. Les
évaluateurs décident sur l'état observable du monde, sans rechercher un
agencement Blockly. Les résultats de simulation ne valent pas autorisation
matérielle.

## Responsabilités et points d'entrée

| Responsabilité | Où lire/modifier |
| --- | --- |
| Fenêtre de programmation et cycle exécuter/arrêter/RESET | [`blockly_v2/`](../plugins/robot_windows/blockly_v2/), principalement `main.js` |
| Catalogues et profils | [`activities.js`](../plugins/robot_windows/blockly/webeeblocks/activities.js) et [`activity_profiles.js`](../plugins/robot_windows/blockly/webeeblocks/activity_profiles.js) |
| Contrat d'activité et préflight | [`activity_contract.js`](../plugins/robot_windows/blockly/webeeblocks/activity_contract.js) |
| Compilation Blockly vers AST | [`semantic_ast.js`](../plugins/robot_windows/blockly/webeeblocks/semantic_ast.js) |
| Sémantique d'exécution partagée | [`interpreter.js`](../plugins/robot_windows/blockly/webeeblocks/interpreter.js) |
| Backend de simulation et protocole WWI | [`wwi_backend.js`](../plugins/robot_windows/blockly/webeeblocks/wwi_backend.js) |
| Runtime natif, scènes et oracles de mission | [`crazyflie_runtime_v2/`](../controllers/crazyflie_runtime_v2/) : `crazyflie_runtime_v2.c`, `activity_scene.cpp`, `progression_*_evaluator.c` |
| Observabilité élève | [`execution_observer.js`](../plugins/robot_windows/blockly/webeeblocks/execution_observer.js), `blockly_v2/led_observability.js` |
| Fichiers et interface Save/Open | [`project_files.js`](../plugins/robot_windows/blockly/webeeblocks/project_files.js), `blockly_v2/project_ui.js` |
| Backend physique et sûreté | [`tools/physical/`](../tools/physical/) : `shared_interpreter_host.py`, `shared_interpreter_worker.js`, `serve_physical_host.py` |
| CI, préparation, sélection et oracles | [`tools/ci/`](../tools/ci/) et [`ci.yml`](../.github/workflows/ci.yml) |

**Attention :** le tableau fournit des entrées, pas des frontières déjà
parfaitement étanches. Un changement doit examiner les consommateurs directs
et indirects, y compris les tests qui vivent dans un autre répertoire.

## Frontières à préserver et limites actuelles

### Activité → scène → évaluateur

Le profil configure les blocs, bornes, capacités, évaluateurs et, depuis
[#723](https://github.com/djibian/webeeblocks/pull/723), la scène native
`runtime.scene` : `sequence-v1` pour l'activité 1, `legacy-v1` pour les
neuf autres. La fenêtre prépare la scène via WWI **avant** de muter le projet.
`wwi_backend.js` refuse les scènes absentes ou inconnues **avant tout envoi
natif**, sans déduire un défaut de l'identifiant pédagogique ; les profils
des mondes dédiés peuvent omettre ce champ lorsqu'ils n'utilisent pas SCENE.
Le Runtime natif conserve sa liste fermée de deux scènes et ses validations.
Il ne s'agit **pas** d'un mécanisme déclaratif d'activités arbitraires.
Voir [ACTIVITY_SCENES.md](ACTIVITY_SCENES.md). Les activités historiques 2–7
restent un acquis technique, pas une acceptation pédagogique.

### Projet élève → navigateur / Qt

Le fichier `.wbb` est enregistré **explicitement**, sans autosave.
`project_files.js` maintient le contrat du projet ; l'interface conserve
la cible courante et affiche les erreurs. Chrome utilise File System Access,
Firefox le broker fichiers/dialogues Qt via WWI. Les deux chemins ont des
consommateurs et tests spécifiques. Le correctif
[#708](https://github.com/djibian/webeeblocks/pull/708), intégré et qualifié
par CI, abandonne le flux Chrome après échec de `write()` ou `close()`,
sans refermer un fichier partiellement écrit après l'échec de `write()`.
Ses tests transactionnels vérifient la conservation du contenu précédent
et de l'erreur primaire. Ils ne prouvent pas la durabilité universelle
d'une fermeture déjà engagée en cas de panne du navigateur ou du système
de fichiers. Ne pas confondre une sauvegarde réussie avec un résultat pédagogique.

### Runtime C / WWI / Qt / Webots

Le contrôleur natif compose encore contrôle de vol, gestion des scènes,
évaluateurs et gestion des dialogues de fichiers Qt. Le broker, les
interceptions WWI et les dépendances partagées rendent possibles des
interférences entre responsabilités. Ne pas réécrire le contrôleur C sur
la seule base de cette carte : établir d'abord la causalité des défauts
RESET [#637](https://github.com/djibian/webeeblocks/issues/637) et
démarrage natif [#665](https://github.com/djibian/webeeblocks/issues/665),
puis qualifier toute séparation.

Pour la **preuve native**, le collecteur CI
[`grand_prix_u_log_capture.py`](../tools/ci/grand_prix_u_log_capture.py)
reçoit stdout/stderr dans un pipe et écrit seul `webots.log`.
Le scellement attend la fin des détenteurs du pipe et refuse les crashes
tardifs, après [#715](https://github.com/djibian/webeeblocks/pull/715).
Le retrait des ressources du harnais [#719](https://github.com/djibian/webeeblocks/pull/719)
essaie aussi les autres fermetures après un premier échec, conserve l'erreur
primaire et **refuse de sceller** les traces lorsque le teardown échoue.
Un manifeste de traces intègres ne prouve jamais qu'une mission a réussi.
Cette garantie ne démontre ni la fin de tous les processus Webots, ni
l'intégrité universelle des autres captures, ni la résolution des
défauts natifs #637/#665.

### Simulation / matériel

Le chemin matériel réutilise le **même interpréteur JavaScript** via un
travailleur Node contrôlé par l'hôte Python, mais l'autorité de commande,
la fraîcheur de session, le watchdog, le préflight et le contrôle enseignant
restent dans la frontière matérielle. Le test
[`test_physical_shared_interpreter.py`](../tools/ci/test_physical_shared_interpreter.py)
exécute maintenant hors matériel l'AST compagnon exact du
`hover_range_comparison.wbb` avec un backend factice ([#712](https://github.com/djibian/webeeblocks/pull/712)).
Il ne prouve pas une exécution Webots de ce même programme. Le vérificateur
de paquet hors ligne [#722](https://github.com/djibian/webeeblocks/pull/722)
refuse les liens symboliques hors manifeste (y compris les liens vers
répertoires ou cibles absentes), sans prouver l'absence de mutation concurrente
lors du contrôle. Les preuves logicielles ne qualifient ni le premier vol réel
[#157](https://github.com/djibian/webeeblocks/issues/157),
ni l'activité physique finale [#72](https://github.com/djibian/webeeblocks/issues/72).
Aucun vol, flash ou TEST_REQUIRED automatique.

### Code fournisseur, validation historique, archive

- **Produit actif :** `blockly_v2/`, modules `blockly/webeeblocks/`,
  `crazyflie_runtime_v2/`, mondes et scènes actuellement sélectionnés,
  et backend physique soumis à son autorité distincte.
- **Frontière fournisseur clarifiée :** Blockly 13.2.1 est servi depuis
  `blockly_v2/vendor/` ; la définition de blocs `crazyflie_v2.js`, propre
  à WebeeBlocks, vit dans `blockly/webeeblocks/` et est chargée par les
  fenêtres V2, les témoins et les distributions Windows / physique.
  Les fichiers de l'ancien Blockly requis par les tests historiques restent
  conservés ; leur existence ne justifie pas d'y ajouter du code produit.
- **Témoins historiques :** anciens contrôleurs, mondes, oracles et ressources
  Blockly peuvent rester nécessaires à des tests. Leur âge ne démontre pas
  qu'ils sont inutilisés.
- **Sorties et amorces du sidecar Blockly historique :** deux fichiers
  repérés par l'audit du 27 octobre **ne sont pas du code mort** :
  - [`controllers/my_controller/my_controller.py`](../controllers/my_controller/my_controller.py)
    est initialement vide dans Git : le serveur historique
    [`blocklyServer.cpp`](../controllers/supervisor/blocklyServer/blocklyServer.cpp)
    l'écrit lors de `SEND_CODE`, et le superviseur historique l'écrit
    aussi. La CI [`run_blockly_ui_sidecar_test.py`](../tools/ci/run_blockly_ui_sidecar_test.py)
    préserve puis restaure ses octets ; le job Webots
    `encoders-historical` y exporte un programme et vérifie son exécution.
    Supprimer le fichier sans refaire ces contrats casserait des consommateurs.
  - [`controllers/Blockly_Programs/.tmp.txt`](../controllers/Blockly_Programs/.tmp.txt)
    contient le nom de projet initial `myFile` (sans extension).
    Le serveur le consulte pour `RESTORE_LAST_NAME` et `RESTORE_LAST`,
    ce dernier ouvrant `myFile.xml`. Le test navigateur historique
    préserve cette amorce, installe une valeur de test, puis restaure l'état
    initial après avoir exercé Save/Submit/Restore. Ce nom est un état du
    **sidecar XML historique**, pas une persistance automatique de projets
    élèves `.wbb` de l'interface V2.
  - **Statut : validation historique active**, et non artefacts à effacer.
    Toute rationalisation future doit d'abord prouver le remplacement des
    consommateurs et conserver leurs oracles de régression.
- **Recherche/archives :** `experiments/` conserve données et hypothèses ;
  les variantes Grand Prix sont des témoins techniques et non une acceptation
  pédagogique. Les travaux fonctionnels du Grand Prix restent suspendus,
  conformément aux décisions du propriétaire.

## Trouver les validations pertinentes

[`select_ci.py`](../tools/ci/select_ci.py) choisit les suites Runtime/Webots
selon les fichiers modifiés ; [`ci.yml`](../.github/workflows/ci.yml)
oriente vers les workflows spécialisés et le `CI Gate`. Les exceptions
historiques du sélecteur montrent qu'un chemin ne désigne pas à lui seul
**l'oracle propriétaire** ; une cartographie complète composants/tests reste
à consolider. Toute modification inconnue doit rester conservatrice.

Quelques tests d'entrée : [projets .wbb](../tools/ci/test_runtime_v2_project_files.js),
[collecte WWI](../tools/ci/test_runtime_v2_wwi_event_server.py),
[interpréteur physique partagé](../tools/ci/test_physical_shared_interpreter.py).
Ils n'épuisent pas les obligations. Préserver les négatifs, RESET, et LAND
**exactement à 210000 ms** ; exiger toujours la CI canonique exacte et la
contre-revue indépendante V5 avant intégration.

**Entretien :** mettre à jour la section touchée de cette carte avec toute
future modification effective de frontière, sans enregistrer ici l'état des
contrôleurs, PR, CI, checkpoints ou expérimentations.
