# B4 — Étude de faisabilité : frontières C / Qt / WWI

**Référence d'analyse :** audit architectural du 27 octobre 2026 (état historique
`main@9ed7b1088b54e641bde421477d72c95d609bbd7b`, ``2.4` et ``8.1–8.2, chantier C`).
**Code vérifié :** `main@2a0ef1a99fc6ee1583bdc02aedcafdbbaa9f94b1`,
28 octobre 2026 ; `AGENTS.md` V5, `PRODUCT_VISION.md` et `ROADMAP.md`
de cette référence. Les PR et défauts GitHub évoluent indépendamment.

## 1. Verdict

**FAISABLE PAR ÉTAPES**, mais il y a deux objectifs non interchangeables :

1. **Modularité et isolation des tests sans modifier le processus** :
   faisabilité **élevée**, risque **moyen** si les interfaces et oracles existants
   restent identiques. Le code possède déjà des coutures vérifiables.
2. **Absence de Qt dans le processus natif de vol** :
   faisabilité **plausible mais non démontrée sur le produit déployé** ;
   risque **élevé** et bénéfice sur #665/#637 **non prouvé**.
   Un simple déplacement de fichiers C++ n'enlève **aucune** dépendance dynamique
   Qt de l'exécutable actuel.

**Recommandation :** documenter et éprouver d'abord la frontière native
WWI/état de tentative/broker, puis réaliser seulement les petites extractions
qui démontrent une baisse de couplage. Ne pas lancer maintenant une réécriture du
contrôleur C, une seconde application autonome, un nouveau protocole ou un
processus Qt séparé. La clôture causale de #637 et #665 reste prioritaire et
leurs refutations ne sont pas annulées par une réorganisation.

Cette étude est **une analyse statique de faisabilité** appuyée sur le code, les
tests existants et les documents de qualification : ni prototype compilé
spécifiquement pour B4, ni test natif Linux/Windows du refactoring proposé,
ni preuve de causalité des incidents ouverts.

## 2. Chemin actuel et dépendances réelles

```text
Robot Window HTML/JS
    |
    | WWI REQUEST / RESPONSE (Webots, même robot)
    v
crazyflie_runtime_v2.c (C, boucle pas Webots / commandes de vol)
    | -include file_broker_interpose.h : substitution de trois symboles C
    v
file_broker_runtime.cpp (C++, même processus)
    |-- reçoit WWI; HELLO / READY
    |-- COMPLETE / FAILURE / OUTCOME, champ Supervisor customData
    |-- observe RESET émis/répondu et fait tourner l'identité de tentative
    |-- route le reste des commandes au contrôleur C
    |
    +-- FILE_BROKER_V1 (création paresseuse au premier message fichier)
           -> file_broker.cpp (parseur/validateur, C++ sans Qt)
           -> FileDialogProvider / file_broker_c.h (interfaces)
           -> qt_file_dialog_provider.cpp (Qt / IFileDialog Win32)
              -> Open / Save As / Save sur le même fichier / Release
```

**Contrôle C.** `crazyflie_runtime_v2.c` (~1023 lignes) commande le drone,
consomme des commandes WWI et protège TAKEOFF, MOVE, STOP, RESET et LAND ;
les fonctions Webots `wb_robot_step`, moteurs, capteurs, Supervisor restent
attachées à ce processus. `runtime_entry.c` choisit le vol ou l'un des
évaluateurs de progression **par `controllerArgs`**, dans **le même binaire**
du Runtime : les évaluateurs sont des exécutions distinctes, pas des
bibliothèques indépendantes du binaire commun.

**Interposition.** `file_broker_interpose.h` remplace au préprocesseur C
`wb_robot_wwi_receive_text`, `wb_robot_wwi_send` et `wb_robot_cleanup`.
`file_broker_runtime.cpp` (334 lignes) réalise simultanément le routage WWI,
la sonde de présence HELLO, les événements de mission, l'autorité des tentatives
et la création/destruction de la passerelle fichiers Qt.
Le détail crucial est l'observation **des deux faces** d'un RESET : requête
exacte avant contrôleur C puis réponse terminale **du même ID** avant rotation
de l'identité de tentative (pas de rotation après erreur, BUSY ou réponse
d'une autre requête). `customData` est la frontière d'évidence avec les
évaluateurs natifs.

**Fichiers.** `file_broker.cpp` (~221 lignes) définit le protocole fichiers
et valide noms, références opaques et taille <= 4 Mio, sans inclure Qt.
`file_broker.hpp` injecte déjà `FileDialogProvider` et permet un faux provider.
`qt_file_dialog_provider.cpp` (~484 lignes) possède les dialogues, les
références chemin/jeton, `QSaveFile` transactionnel, et sur Windows une
réalisation `IFileDialog`/COM avec contrôle spécifique de fenêtre propriétaire.
Les références opaques ne doivent jamais devenir des chemins fournis par JS.
Les contrats Chromium File System Access et Firefox Qt/WWI sont deux voies
volontairement distinctes vers les mêmes opérations .wbb.

**Binaire et distribution.** Le `Makefile` du Runtime lie explicitement
`Qt6Core`, `Qt6Gui` et `Qt6Widgets` sur **Linux et Windows**, avec
`qt_file_dialog_provider.cpp` dans `CXX_SOURCES`. La création de provider est
paresseuse, **pas le chargement de ses bibliothèques liées** : ne pas présenter
la création tardive comme une isolation d'adresse, de chargeur ou d'ABI.
Sur Windows, cela touche aussi la fermeture PE/DLL, le plugin `qwindows` et les
runtimes C++ ; sur Linux, Qt/XCB et le chemin des plugins du Webots R2025a
exact sont pertinents.

**Consommateurs indirects.** Les `Makefile` de
`controllers/grand_prix_flight/` et `controllers/grand_prix_u_flight/`
réemploient le broker et son provider Qt. Plus important :
`tools/grand_prix/prepare_u_runtime.py` copie **textuellement**
`file_broker_runtime.cpp` puis injecte `gp_u_filter_raw(message)` juste
après la ligne exacte `while ((message = wb_robot_wwi_receive_text()) != nullptr) {`,
sous contrôle d'un ancrage unique ; le filtre s'exécute **avant** la
comptabilité RESET du broker. Toute extraction/renommage change cette
composition, même si le dossier Grand Prix n'est pas modifié directement.
Les modifications pédagogiques/fonctionnelles du Grand Prix restent suspendues,
mais les négatifs et les oracles existants sont obligatoires.

**Dépendance Webots.** WWI est l'interface documentée entre une fenêtre de
robot et **son contrôleur** ; `wb_robot_step` synchronise le contrôleur
avec la simulation. Un nouveau service natif ne recevra pas magiquement
les messages WWI sans relais explicite : la frontière Webots existante doit
rester une autorité unique (référence : documentation Cyberbotics Robot et
Robot Window Plugin, version R2025a pour toute validation concrète).

## 3. Coutures disponibles et preuves déjà présentes

| Couture | Évidence existante | Ce qui n'est PAS prouvé |
| --- | --- | --- |
| FileBroker sans Qt | `tools/ci/test_firefox_file_broker.cpp` et faux `FileDialogProvider` (opérations, erreurs, références, annulation, refus chemins) | Démarrage du vrai Runtime sans Qt |
| Broker natif sans provider réel | `tools/ci/test_runtime_mission_broker.py` compile le vrai `file_broker_runtime.cpp` avec Webots et provider factices : HELLO, tentatives, RESET, erreur, stale, oracle croisé | Ordonnancement du vrai moteur et Qt |
| Frontière UI/WWI | `tools/ci/test_runtime_v2_project_files.js` ; `test_runtime_activity_outcome.js` ; `test_runtime_v2_reset.js` | Absence générale de courses sous tous ordonnancements natifs |
| Linux Firefox réel | `tools/ci/run_runtime_v2_firefox_project_files.py` et driver X11/Firefox avec dialogue Qt réel | Acceptation Windows réelle ni suppression du chargement Qt |
| Dépendances Webots/Windows | CI Webots/Runtime, packaging et qualifications liées à #665/#701 | Garantie de stabilité de l'ABI ou guérison des crashes de démarrage |

Le code contient donc déjà un **parseur fichiers injectable** et un
**adaptateur de transport natif testable**. Il serait injustifié de réécrire
le broker ou de dupliquer le protocole pour obtenir une séparation seulement
cosmétique.

## 4. Scénarios de séparation

| Option | Coût relatif | Risque | Effet réel | Décision proposée |
| --- | --- | --- | --- | --- |
| **S0 — conserver tel quel, améliorer contrats/tests** | Faible | Faible | Meilleure preuve, couplage binaire inchangé | Oui, maintenant si manque démontré |
| **S1 — extraire routeur WWI / canal de tentative en unités C++ testables, même exécutable** | Moyen | Moyen à élevé | Réduction du couplage source et meilleures localisations de défauts ; Qt toujours chargé | **Piste préférée sous conditions** |
| **S2 — charger le provider Qt par module dynamique seulement à l'usage** | Élevé | Élevé | Peut ôter les importations Qt du *binaire de vol* ; Qt partage toujours son processus, son éventuel blocage et l'environnement du chargeur | Étude/prototype seulement sur cause identifiée |
| **S3 — helper Qt natif dans un processus séparé + IPC local** | Très élevé | Très élevé | Isolation de crash/chargeur et de boucle modale **si le relais est réellement non bloquant** ; nouveau protocole, lifecycle, packaging, auth et timeouts | **Ne pas engager sans preuve causale et bénéfice mesuré** |
| **S4 — binaires vol/évaluateurs distincts** | Élevé | Élevé | Allègement potentiel des exécutables et dépendances selon linkage ; perturbe controllerArgs, packaging, identités et mondes | Chantier distinct, non préalable à B4 |

Un autre contrôle navigateur ne remplace pas Firefox : la parité native
Open/Save As/Save/Release et la conservation des cibles sont une exigence
du produit (#87). Inversement, retirer Qt du *contrôleur* ne retire pas Qt
du *moteur Webots* et ne corrige pas automatiquement le crash #665,
dont la causalité doit rester attribuée avec ses propres preuves.

## 5. Conception cible **minimale** (S1, seulement si justifiée)

Conserver **à l'identique** la surface protocolaire externe WWI :
`WEBEEBLOCKS_RUNTIME_V2`, `WEBEEBLOCKS_FILE_BROKER_V1`,
`WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1`, `COMPLETION`, `FAILURE_PROBE` et
`OUTCOME` ; mêmes ID/ordre/erreurs, mêmes refus et absence d'action réémise.

Une séparation interne possible :

1. **Transport WWI exclusif :** un seul lecteur et un seul écrivain
   Webots dans le thread du contrôleur, avec adaptateur et trace des
   envois/réceptions. Ne pas introduire de second lecteur concurrent.
2. **Canal de preuve/tentative :** analyse des commandes COMPLETE/FAILURE/
   OUTCOME et suivi RESET A/B ; dépendance Supervisor explicite et injectée.
   Publier l'identité de tentative seulement après le RESET OK exact.
3. **Broker fichier :** `FileBroker` et le provider injecté existants ;
   la politique de nom, taille, opaque reference, sauvegarde atomique et
   erreurs demeure indépendante des événements de vol.
4. **Adapter Qt :** propriétaire du provider et de son cycle de vie ;
   conserver les règles réelles de présentation du dialogue sur Linux et
   Windows. Ne pas changer la composition Qt/COM lors d'un premier extrait.

Les frontières 1–2 doivent respecter **l'ordre de filtrage**
`gp_u_filter_raw` *avant* l'enregistrement de RESET pour le Grand Prix U
historique ; traiter `prepare_u_runtime.py` et les deux autres consommateurs
Grand Prix comme des propriétaires de contrat, pas des fichiers ignorables.

**Risque structurel à reproduire avant tout changement de comportement :**
`wb_file_broker_handle_message` peut aboutir à `QFileDialog::exec()` ou
`IFileDialog::Show()` dans l'appel synchrone de réception WWI du contrôleur.
Cela peut retarder son prochain `wb_robot_step`. L'UI actuelle verrouille
normalement les fichiers en vol, mais ce garde-fou UI n'est pas une preuve de
refus natif pour tout message inattendu ou différé. **Ne pas conclure sans
essai natif** qu'un dialogue fige effectivement un vol, qu'il provoquerait
un crash ou que le déplacement vers un thread est sûr. Tester d'abord :
message fichier retardé pendant commande active ; annulation/erreur ; pas de
modification des oracles/RESET ; effet horloge physique et simulée observé.

## 6. Petits incréments qualifiables (sans chantier « big bang »)

**I0 — gel des interfaces observées / contre-exemples.**
Capturer les contrats historiques sur un HEAD de référence : traces exactes
HELLO/READY, refus malformed, COMPLETE/FAILURE/OUTCOME, RESET A/B et
reconnexion Robot Window, Open/Save As/same-file Save/Release/annulation ;
les symboles/interpositions réels Linux/Windows, Qt DLL/ELF et héritage Grand Prix.
Tester des ordres adversariaux : réponse ancienne, ID erroné, fermeture provider,
réattachement, fichier invalide et broker indisponible. Aucun changement
de protocole ni d'oracle.

**I1 — extraction pure du suivi de tentative, pas des API Webots.**
Déplacer la logique dans une unité qui accepte callbacks/fonctions de lecture/
écriture du champ Supervisor et un émetteur de réponse injectés.
Le chemin production garde la même suite exacte d'appels ; le test
`test_runtime_mission_broker.py` reste un témoin d'identité de commande, de
freshness et d'erreurs. **Ne pas déplacer/retarder la rotation RESET**.
Candidat complet séparé ; aucun changement Qt/Makefile dans le même incrément.

**I2 — dispatcher C++ mince, conservation du broker et filtre GP U.**
Extraire le routage des namespaces vers des fonctions testables sans changer
l'API C d'interposition ni l'ordre natif de consommation/réponses. Requalifier
`prepare_u_runtime.py`, qui injecte dans le source texte exact ; si cet ancrage
doit changer, adapter explicitement son test de composition et conserver la
priorité de `gp_u_filter_raw`, sans modification fonctionnelle des mondes GP.

**I3 — seulement sur résultat causal positif : mesurer S2 ou S3.**
Avant d'envisager le découplage de processus : contre-exemple lié à Qt *dans
le contrôleur*, comparaison à charge identique avec Qt hors binaire, preuve
des DLL/ELF *effectivement chargés* et qualification UI Firefox + moteur.
Pour S3, exiger absence de réseau, IPC local authentifié par session et
borné, limite 4 Mio, secrets/chemins jamais exposés au JS, références opaques
et révoquées à la fermeture, annulation exacte, durée/teardown limités,
crash du helper sans perte de projet, non-blocage démontré des pas Webots,
lifecycle d'un seul helper par session, installations Linux et Windows sans SDK.
Une preuve purement simulée n'est pas l'acceptation d'un dialogue réel.

Ces incréments sont des **options à sélectionner selon défauts et preuves**,
pas des dépendances administratives ni une reprise du Grand Prix.

## 7. Matrice minimale d'acceptation

| Obligation préservée | Preuve requise si touchée |
| --- | --- |
| Syntaxe/autorité WWI, HELLO et reconnexion | Tests broker avec stubs + tests frontend/broker de production ; aucun ancien READY falsifié |
| RESET exact et identité de tentative | Négatifs RESET A/B, OK/ERR/timeout, stale/cross-oracle, résultat de tentative fraîche ; campagne R2025a existante |
| Missions et sécurité de vol | Semantics Runtime/PID, fail-safe, négatifs, LAND **exactement 210000 ms**, sélections scènes, aucun affaiblissement |
| Flux fichiers .wbb | Fake provider + vrai Firefox Linux/Qt/WWI, Chrome unchanged, annulation, ouverture invalide sans mutation, Save même cible et release, 4 Mio |
| Consommateurs GP historiques | Composition `prepare_u_runtime.py`, filtres avant bookkeeping, règles de preuve du Grand Prix conservées malgré suspension fonctionnelle |
| Webots Linux/Windows / identité chargée | Builds et linkage, chargeur Linux ELF (`readelf/ldd` + /proc si disponible), Windows PE/DLL **et processus réel**, Qt plugins, distribution hors SDK |
| Cycle des processus | Repeated open/cancel/close/reset, échec et nettoyage, startup/shutdown ; absence de thread/sock concurrent non qualifié |
| Gouvernance d'intégration | Dernier CI canonique `.github/workflows/ci.yml` sur le HEAD Ready exact, vrai `CI Gate` success, GO **indépendant**, base actuelle, squash conditionnel (`expected_head_sha`) et preuve post-fusion |

Les tests hôtes permettent de **refuser des erreurs**, pas de déclarer une
qualité native Windows acquise. #637 (RESET/collision) et #665 (démarrage
Webots/Qt) restent des réfutations pertinentes selon les chemins touchés.
La PR expérimentale #701 sur Webots Qt est Draft : ne pas confondre sa
qualification partielle Linux/Windows et une correction intégrée sur main.

## 8. Décision à réévaluer avant d'implémenter

- **GO pour l'étude et l'ajout de tests/contrats sans changement de comportement.**
- **GO conditionnel pour S1** uniquement lorsqu'une frontière précise peut
  être isolée et ses négatifs reproduits, et si cela ne gêne pas les réparations
  causales #637/#665.
- **NO-GO de principe pour S2/S3 tant qu'un gain de robustesse propre au
  découplage n'est pas démontré** ; ce n'est pas un NO_GO V5 sur une PR
  existante ni une interdiction définitive.
- **Non-objectifs :** supprimer le chemin Firefox, utiliser des chemins
  de fichiers envoyés par JS, rejouer des commandes, déplacer les commandes
  Webots vers un thread non qualifié, créer un serveur réseau ou une
  seconde autorité de simulation, changer le langage élève, la sûreté du
  Crazyflie physique, les oracles Grand Prix ou 210000 ms.

**Critère de décision en fin de phase :** le découplage source est
objectivement meilleur (interfaces, tests et responsabilités identifiés)
**sans perte** de garanties, et toute prétention à une réduction du couplage
natif est vérifiée par la présence/absence des bibliothèques **réellement
chargées** chez les consommateurs Linux et Windows. Aucune acceptation
pédagogique ou autorisation de vol physique n'en découle.

## Sources vérifiables

- Audit du 27 octobre 2026 fourni par le propriétaire, `2.4, `8.1 et chantier C
  (diagnostic historique non modifié par cette étude).
- Code actuel : [Makefile Runtime](../controllers/crazyflie_runtime_v2/Makefile),
  [C flight](../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c),
  [C entry](../controllers/crazyflie_runtime_v2/runtime_entry.c),
  [interposition](../controllers/crazyflie_runtime_v2/file_broker_interpose.h),
  [bridge](../controllers/crazyflie_runtime_v2/file_broker_runtime.cpp),
  [FileBroker](../controllers/crazyflie_runtime_v2/file_broker.cpp),
  [provider](../controllers/crazyflie_runtime_v2/qt_file_dialog_provider.cpp),
  [GP U source transform](../tools/grand_prix/prepare_u_runtime.py).
- Tests : [fake provider](../tools/ci/test_firefox_file_broker.cpp),
  [stubs broker](../tools/ci/test_runtime_mission_broker.py),
  [Firefox réel](../tools/ci/run_runtime_v2_firefox_project_files.py),
  [projets .wbb](../tools/ci/test_runtime_v2_project_files.js).
- Décisions / états : [#87](https://github.com/djibian/webeeblocks/issues/87),
  [#637](https://github.com/djibian/webeeblocks/issues/637),
  [#665](https://github.com/djibian/webeeblocks/issues/665),
  [#701](https://github.com/djibian/webeeblocks/pull/701),
  [#587](https://github.com/djibian/webeeblocks/issues/587).
- Documentation externe : [Webots Robot](https://cyberbotics.com/doc/reference/robot?version=R2025a),
  [Robot Window Plugin](https://www.cyberbotics.com/doc/reference/robot-window-plugin?version=R2025a),
  [Controller Programming](https://www.cyberbotics.com/doc/guide/controller-programming?version=R2025a).
