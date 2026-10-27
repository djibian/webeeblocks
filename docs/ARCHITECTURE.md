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

Le profil configure les blocs, bornes, capacités et évaluateurs. La fenêtre
prépare la scène via WWI **avant** de muter le projet ; le Runtime natif
sélectionne les sous-scènes et exécute les évaluateurs. L'implémentation
distingue aujourd'hui `sequence-v1` et `legacy-v1` : elle ne constitue
pas encore un mécanisme complètement déclaratif d'activités arbitraires.
Voir [ACTIVITY_SCENES.md](ACTIVITY_SCENES.md). Les activités historiques 2–7
restent un acquis technique, pas une acceptation pédagogique.

### Projet élève → navigateur / Qt

Le fichier `.wbb` est enregistré **explicitement**, sans autosave.
`project_files.js` maintient le contrat du projet ; l'interface conserve
la cible courante et affiche les erreurs. Chrome utilise File System Access,
Firefox le broker fichiers/dialogues Qt via WWI. Les deux chemins ont des
consommateurs et tests spécifiques. Ne pas confondre une sauvegarde réussie
avec un résultat pédagogique. L'atomicité des écritures Chrome est suivie
dans [#708](https://github.com/djibian/webeeblocks/pull/708) et doit être
prouvée sur le HEAD intégré avant d'être déclarée acquise.

### Runtime C / WWI / Qt / Webots

Le contrôleur natif compose encore contrôle de vol, gestion des scènes,
évaluateurs et gestion des dialogues de fichiers Qt. Le broker, les
interceptions WWI et les dépendances partagées rendent possibles des
interférences entre responsabilités. Ne pas réécrire le contrôleur C sur
la seule base de cette carte : établir d'abord la causalité des défauts
RESET [#637](https://github.com/djibian/webeeblocks/issues/637) et
démarrage natif [#665](https://github.com/djibian/webeeblocks/issues/665),
puis qualifier toute séparation.

### Simulation / matériel

Le chemin matériel réutilise le **même interpréteur JavaScript** via un
travailleur Node contrôlé par l'hôte Python, mais l'autorité de commande,
la fraîcheur de session, le watchdog, le préflight et le contrôle enseignant
restent dans la frontière matérielle. Les preuves logicielles ne qualifient
ni le premier vol réel [#157](https://github.com/djibian/webeeblocks/issues/157),
ni l'activité physique finale [#72](https://github.com/djibian/webeeblocks/issues/72).
Aucun vol, flash ou TEST_REQUIRED automatique.

### Code fournisseur, validation historique, archive

- **Produit actif :** `blockly_v2/`, modules `blockly/webeeblocks/`,
  `crazyflie_runtime_v2/`, mondes et scènes actuellement sélectionnés,
  et backend physique soumis à son autorité distincte.
- **Frontière fournisseur imparfaite :** Blockly 13.2.1 est servi sous
  `blockly_v2/vendor/`, mais la définition de blocs **spécifique au produit**
  `crazyflie_v2.js` reste sous le répertoire historique
  `blockly/google-blockly-31ee4ea/blocks/` et est chargée directement par
  `blockly_v2.html`. Déplacer ce code exige de vérifier tous les chargeurs.
- **Témoins historiques :** anciens contrôleurs, mondes, oracles et ressources
  Blockly peuvent rester nécessaires à des tests. Leur âge ne démontre pas
  qu'ils sont inutilisés.
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
