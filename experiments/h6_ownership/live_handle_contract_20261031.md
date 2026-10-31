# H6 — frontière de propriété et identité temporelle des contacts ODE/Webots

**Recherche indépendante, analyse de code uniquement — NE PAS FUSIONNER.** 2026-10-31.

Source examinée : [Webots pinned](https://github.com/cyberbotics/webots/tree/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b), commit `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. Références historiques inchangées : [#766](https://github.com/djibian/webeeblocks/pull/766) `8d8d644b2bc6d5821572d87d474e59f533ec3260`, [#771](https://github.com/djibian/webeeblocks/pull/771) `01b16a707248e77eeea6a80519a7775f81311`, [#773](https://github.com/djibian/webeeblocks/pull/773) `83673148d7076b764282ed4e0618ff5a86aa5cbf`, [#774](https://github.com/djibian/webeeblocks/pull/774) `e3cec6c402f088e87600ca50bc37338baf8c8a77`. Main observé au démarrage : `c0cb8c1873d48b26a0f67976c65fa92ca5d54f52`. Issue #637 OPEN ; causalité historique RESET_TIMEOUT → H6 UNPROVEN.

## 1. Définition exacte des garanties

ODE épinglé : [common.h:184](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/include/ode/ode/common.h#L184) définit `typedef struct dxJoint *dJointID`. [objects.h:1647–1655](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/include/ode/ode/objects.h#L1647-L1655) : détruire un joint le retire du monde, mais `dJointDestroy` est sans effet pour un joint appartenant à un groupe. [ode.cpp:1252–1258](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/ode.cpp#L1252-L1258) : `j->flags` est lu immédiatement, puis `delete j` à travers `FinalizeAndDestroyJointInstance` (1236–1250). Une fois l'objet détruit, la valeur d'adresse résiduelle **n'est plus un identifiant valide pour accéder à ce joint** selon la durée de vie C/C++ ; il n'y a ni table de handles ni compteur de génération dans l'API. C'est H0 comme domaine technique des appels valides, non une phrase explicite de la documentation Cyberbotics promettant une politique applicative. Les plugins doivent s'abstenir d'utiliser un ID après destruction effective, de conserver un ID de Webots après la fin de sa validité, ou de déclencher des destructions concurrentes non synchronisées sans prolongation de durée de vie.

**H0 :** les opérations ODE visant un joint sont garanties seulement tant que ce joint est vivant et pendant une exclusion mutuelle appropriée avec sa destruction. Le simple fait d'avoir commencé un appel ou de posséder la même valeur de pointeur n'est pas une référence gardant l'objet vivant. Un second destructeur attendant le mutex après le free du premier ne devient pas licite par magie.

**H1 :** l'ancienne valeur doit être sans effet sur un nouvel objet même après réallocation de l'adresse. Aucune preuve de cette promesse dans l'API Webots/ODE épinglée. Nécessité pour la compatibilité avec des plugins particuliers **UNPROVEN** ; ne pas déduire la non-nécessité du seul silence documentaire. Sous H1 absolu et appels publics ne transmettant que le pointeur, démonstration d'impossibilité par indiscernabilité : deux appels `dJointDestroy(p)` ont exactement le même argument et l'état mémoire courant (nouveau joint d'adresse p) ; un registre ne peut distinguer « ancien p » de « p courant ». Exiger l'un sans effet et l'autre effectif est contradictoire sans identité temporelle externe ou interdiction de réemploi pendant toute la durée du handle. Les deux refutations natives de #774 (tombstone retenue / effacée, 20/20) sont compatibles avec cette preuve générale, mais ne prouvent pas l'impossibilité de générations ou d'une mémoire non réutilisée.

Options H1 et coûts : (a) représentation `(slot,generation)` transportée par TOUTES les API concernées, changement ABI/type et migration des plugins ; (b) handles indirects permanents non réutilisés avec quarantaine/epochs et preuve de fin de possession, coût mémoire et parfois impossibilité de borner la quarantaine ; (c) non-réutilisation des adresses sur toute la durée de détention possible, coût mémoire non borné et conflit avec I3/I7. Ajouter un numéro de génération uniquement dans un QHash **ne suffit pas** puisque le plugin transmet toujours p. Ne pas ressortir les tombstones d'adresse.

## 2. Contrats P0/P1 et machines minimales

**Identité du sujet** : joint ODE vivant + appartenance à la catégorie **contact automatiquement créé par Webots**, enregistrée lors de la création avant exposition. **Autorité du demandeur** : chemin d'appel explicite « destruction interne de contact Webots » distinct de l'entrée publique `dJointDestroy` ; ne jamais classer par ID de thread, TLS « thread du moteur », ou possession implicite du QMutex. `odeNearCallback` invoque un plugin sur un thread du moteur ([cluster:505–519](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/engine/WbSimulationCluster.cpp#L505-L519)).

Machine unique sous un arbitre exclusif pour une *incarnation vivante* :

- `LIVE` : enregistré dans exactement un des deux registres de Webots et présent physiquement ; un joint plugin inconnu du registre suit la sémantique native ODE.
- `DESTROYING` : état transitoire dans la section atomique, interdiction de nouvelle destruction de cette incarnation ; retirer immédiatement toutes les références moteur/des deux tampons **avant** la destruction physique.
- `FREED` : transition terminale, **pas** de tombstone indexée par l'adresse conservée comme identité du joint. Le registre ne contient que du vivant.

P0 : un appel **public plugin** sur contact Webots `LIVE→LIVE` (no-op conforme au groupe historique). La destruction **interne explicitement autorisée** effectue `LIVE→DESTROYING→FREED`. P1 : un appel public plugin **ou** une destruction interne admise effectue `LIVE→DESTROYING→FREED` avec désinscription avant free. Aucun état supplémentaire n'est nécessaire sous H0 **si** la durée de vie et l'exclusion avec le solveur sont déjà garanties par le contexte. Sur joint propre au plugin : `dJointDestroy` standalone reste effectif ; sur joint group-owned plugin : no-op natif, `dJointGroupEmpty` inchangé. La sélection P0/P1 est une *politique*, pas une information déductible de l'identité du thread.

Limite capitale : ces machines ne garantissent pas un second `dJointDestroy(p)` qui arrive **après** la libération du premier ou attend sur mutex sans avoir acquis une protection de durée de vie avant le free. Deux appels concurrents sans mécanisme externe de « pin » ou exclusivité d'appel restent hors de H0 ; les accepter tous deux comme valides et exiger une destruction unique demande une admission de durée de vie au niveau de l'appelant ou une identité générationnelle. La section critique règle la cohérence registre/free, pas la validité des paramètres introduits depuis l'extérieur. Ne pas confondre « aucune double destruction interne à Webots » avec « tout appel double arbitraire sur pointeur C est sûr ».

## 3. Graphe du scheduler et chemins exacts

1. [WbSimulationCluster::step :109–129](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/engine/WbSimulationCluster.cpp#L109-L129) appelle `dWorldStepAndSpaceCollide` puis `swapBuffer`, puis détruit le groupe des contacts plugin et retire l'ancien tampon des contacts moteur. Le *code original* ne prend pas `cJointCreationMutex` au retrait dans `step`, malgré le commentaire de `WbOdeContext`; le patch expérimental [patch_standalone.py:147–155](https://github.com/djibian/webeeblocks/blob/8d8d644b2bc6d5821572d87d474e59f533ec3260/experiments/h6_standalone/patch_standalone.py#L147-L155) ajoute ce verrou. Ne pas transposer la remarque de la version originale au patch, ni croire que ce mutex protège le solveur.
2. [odeNearCallback :878–889](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/engine/WbSimulationCluster.cpp#L878-L889) tient le QMutex sur création/attachement ; #766 crée désormais des joints standalone et les inscrit sous le même verrou. Le callback plugin est appelé plus tôt, aux lignes 513–519.
3. [WbSolidMerger::~WbSolidMerger:42–45](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/utils/WbSolidMerger.cpp#L42-L45) retire les contacts avant `dBodyDestroy`. Le candidat D1 corrige le suivi des deux corps réellement attachés (même si l'owner est un corps endormi) mais le protocole de destruction arbitré n'y est pas intégré.
4. [WbSolid::reset(id):2123–2153](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbSolid.cpp#L2123-L2153) copie les joints du corps puis les détache/détruit ; #766 D3 centralise les contacts suivis. [resetPhysics:2260–2268](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbSolid.cpp#L2260-L2268) et `resetSingleSolidPhysics` sont distincts de `resumePhysics` ; ne pas rétablir G inconditionnel.
5. [WbOdeContext::~WbOdeContext:42–63](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/ode/WbOdeContext.cpp#L42-L63) détruit les groupes (moteur puis plugin), puis l'espace et le monde. Dans le candidat standalone, les contacts Webots restants sont détruits individuellement avant `dWorldDestroy` ; ce chemin DOIT être arbitré et doit prouver les registres vides à la fin.
6. [ode.cpp:1274–1315](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/ode.cpp#L1274-L1315) : `dJointGroupEmpty` détruit directement par `FinalizeAndDestroyJointInstance`, **sans** appeler `dJointDestroy`. [ode.cpp:1539–1584](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/ode.cpp#L1539-L1584) : `dWorldDestroy_ST` détruit les standalone en direct (`~dxJoint` puis `dFree`), **sans** appeler `dJointDestroy`. Une interception de `dJointDestroy` seule n'est donc pas une couverture universelle : le registre doit être vide avant destruction du monde ; aucun contact moteur standalone ne doit entrer dans un groupe ODE.
7. [WbPhysicsPlugin.cpp:130–133,214–223](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/plugins/WbPhysicsPlugin.cpp#L130-L133) : destruction du plugin invoque `cleanup()` ; callbacks `collide` et `step` passent dans le plugin natif. La documentation [callbacks](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/docs/reference/callback-functions.md#L7-L12) reconnaît explicitement l'appel multithread et demande au plugin de mutex-protéger les modifications du monde.
8. [ode_MT.cpp:262–296](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/ode_MT/ode_MT.cpp#L262-L296) : `threadManager->simLoop()` entre collision/solveur et retour de `dWorldStepAndSpaceCollide`; [threadManagerPthread.cpp:75–121](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/ode_MT/threading/threadManagerPthread.cpp#L75-L121) : les workers participent aux barrières 1/2. Barrière 2 démontre la fin du travail **de cette phase** avant le retour du step, pas la quiescence de threads propres aux plugins ni l'impossibilité d'un callback externe simultané hors phase. Le démontage sans barrier spécifique reste UNPROVEN.

## 4. Verrouillage proposé, sans réentrance automatique

**Invariants préalables** : `Φ`, une porte d'exclusion/quiescence de phase physique couvrant TOUS les utilisateurs de joint (workers du solveur ET appels externes admis) ; `M`, un seul verrou de propriété protégeant ensemble les deux registres et la décision de free ; `C`, code de callback. Ordre voulu **Φ avant M**, sans aucun trajet `M → attente de fin des workers`, et **pas d'appel arbitraire de plugin sous M**. La preuve que Φ peut exister dans Webots sans bloquer un worker intervenant en callback n'est PAS fournie. Si le plugin peut appeler `dJointDestroy` pendant `odeNearCallback`, attendre une barrière de phase depuis ce worker créerait un auto-deadlock : ce cas demande classification par phase et voie locale sûre ou refus/différé, sans feindre une garantie de destruction immédiate.

Pour le seul domaine H0 et quand Φ est acquis :
- création moteur : `M.lock ; ODE create + attach ; register(one buffer) ; M.unlock`, aucune exposition partielle ;
- entrée **publique** `dJointDestroy(p)` : **avant `p->flags`**, `M.lock ; lookup live ; (P0 : return/no-op ; P1 : unregister both maps puis destruction native) ; sinon destruction ODE ordinaire ; M.unlock` ; vérification effective de `p->flags` uniquement si p est valide selon H0 ;
- entrée **interne** `destroyOwnedContactLocked(p)` : précondition `M` déjà tenu, supprimer référence(s), destruction native directe **sans repasser par l'entrée publique ni acquérir M** ; interdit aux callbacks de plugin par construction de l'appel, pas par identité de thread ;
- retrait de tampon, RESET, D1, teardown : tenir `M` une fois par lot, utiliser exclusivement `destroyOwnedContactLocked` ; le chemin interne ne doit ni rappeler le QMutex ni invoquer le callback qui reprend M ;
- désenregistrement du mécanisme ODE : après arrêt et retour de **tous** les workers pertinents et callbacks, sous M et hors callbacks ; nettoyer toutes les entrées et vérifier registre vide ; désenregistrer le callback avant destruction de M et de WbOdeContext.

**Pas d'équivalence démontrée** entre le `std::recursive_mutex` jetable de #774 et `QMutex` non récursif. Sur le chemin source `WbSolidMerger → removeBodyContactJointGroup`, M est pris ; un hook ODE qui prend M à nouveau provoquerait un deadlock. La réentrance d'un callback d'origine plugin durant les opérations de suppression reste une obligation ciblée. Les mutex privés des plugins constituent un autre ordre de verrous non contrôlé par Webots : aucune hypothèse de hiérarchie globale n'est acquise.

**Point dur** : même ce verrou unique ne protège pas les accès du solveur tant que Φ n'est pas assuré. P0 (no-op public pour contacts moteur) réduit les destructions externes, P1 requiert une preuve supplémentaire d'exclusion physique à chaque destruction effective provenant du plugin. Le simple mutex du registre n'est PAS cette preuve.

## 5. Minimalité, composants requis, ABI

Sous H0 et avec l'hypothèse de quiescence Φ, la borne inférieure de complexité comprend :
1. une identité d'**appartenance courante** du joint moteur (les deux QHash live existants de #766 peuvent l'assurer sans génération persistante) ;
2. un seul point d'admission **avant** première déréférence sur le chemin public ODE et une route interne explicitement autorisée ;
3. une transaction atomique `unregister → free` avec un **seul** verrou non-récursif commun (sous discipline `locked` / `unlocked` non ambiguë) ;
4. une barrière de durée de vie/quiescence avec les users ODE **indépendante** du verrou de registre ;
5. l'ordre de teardown callback → objets → désenregistrement → destruction des registres établi explicitement.

Aucune tombstone, table de générations, nouveau handle ou `std::recursive_mutex` n'est requis **pour H0 correctement borné**. `DESTROYING` est une étape transactionnelle sous M, pas obligatoirement un champ persistant par joint ; `FREED` est l'absence dans la table live. La minimalité de cette décomposition **conditionnelle** est fondée sur les obligations, pas encore sur des mesures ni une implémentation Webots testée. Sous H1 le coût de l'identité temporelle doit être ajouté et la représentation brute devient insuffisante.

Pour éviter de casser le C ABI des plugins, conserver `dJointID`, la signature et le comportement de `dJointDestroy` pour leurs propres joints, `dJointGroupEmpty` des groupes plugins et `dWebotsGetContactJointGroup`. Le mécanisme d'admission exigerait une modification d'implémentation de la libode chargée par Webots et probablement une **entrée privée interne** Webots/ODE (éventuellement symboles ajoutés, non réclamés par les plugins). Ajouter des symboles C n'est pas automatiquement une qualification ABI : exports Windows, import library, anciens plugins précompilés, ordre de chargement, interposition de libode, unload du plugin et mondes multiples, tous **UNQUALIFIED**. Une politique coopérative n'isole pas un plugin malveillant natif dans le même processus.

Le contact group-owned originel existe et bénéficie d'un no-op ODE documenté ; **P0 minimise la divergence observable** pour les plugins découvrant un contact moteur via `dBodyGetJoint`. **P1** peut être une API utilisable seulement si Cyberbotics accepte explicitement la destruction externe effective et si la barrière solveur est prouvée. La documentation ne suffit pas pour décider cette convention Webots.

Coûts : reprendre uniquement #773, 217 processus comparatifs déjà terminés, rapports à 1024 contacts : singleton ≈34,6× la mémoire active vs standalone notifié. Pas de nouveau benchmark. Le coût additionnel de la porte Φ, de l'admission publique et des deux QHash Webots réels reste à mesurer **après** faisabilité.

## 6. Obligations et verdict de faisabilité

| Obligation | Résultat actuel | Démonstration encore nécessaire |
|---|---|---|
| Sous H0, ABA après free | Hors domaine garanti | **Ne jamais** enregistrer un ID libéré ; aucune prétention de validation de vie par adresse seule |
| Sous H1, ancien ID inoffensif arbitraire | **IMPOSSIBLE AVEC ID BRUT RÉUTILISABLE** | Si exigée, choisir nouvelle représentation ou non-réemploi complet |
| Double destruction interne du même vivant | **CONCEPTION VIABLE CONDITIONNELLE** | Atomisation toutes voies et preuve de durée de vie à l'entrée |
| Deux `dJointDestroy(p)` concurrents sans pin de vie | **NON GARANTI PAR H0** | Restriction de contrat ou admission de références avant le premier free |
| P0 plugin → contact moteur vivant | **POSSIBLE EN PRINCIPE** | Admettre avant flags, vérifier no-op sans reprendre M |
| P1 plugin → contact moteur vivant | **POSSIBLE SEULEMENT HORS ACCÈS SOLVEUR** | Porte de phase ; cas callback worker sans deadlock ni perte de contacts |
| Joint standalone appartenant au plugin | **RESTER ODE ORIGINAL** | Test ABI natif ; aucune tombstone de contact moteur ne peut l'intercepter |
| Groupe plugin / world destroy | Sources confirment bypass de dJointDestroy | Tester registre vide avant teardown, arrêter callback/workers |
| QMutex non récursif | **UNPROVEN** | Vérifier graphe de prises sur Webots compilé et interleavings ciblés |
| Workers / destruction | **UNPROVEN** | Source + test ciblé worker callback / retrait / teardown |
| H6 I1/I2/I3 | Historique #766 limité | Ne pas répéter G, RESET, D1/D3 ; conserver la sémantique sélective |

**Pas de nouveau run** : les 217 benchmarks, SIGSEGV et 20 reproductions ABA ne sont pas réexécutés ; les sources suffisent pour les limites d'identité et le constat des bypass ; le point incertain restant est une vraie synchronisation source-pinnée Webots, non un nouveau stress d'allocateur.

### Prochaine action technique unique

**Une contre-épreuve de faisabilité du *chemin de destruction interne sous QMutex* avec plugin callback ODE pendant des workers actifs** : instrumenter le Webots épinglé dans un banc indépendant pour produire une trace totale `phase / worker / M acquis-libéré / callback / registre / destruction`, avec 1 et 2 workers, qui teste uniquement (a) absence d'acquisition récursive de M, (b) aucune attente de barrière depuis un worker participant, (c) nettoyage du registre avant libération et (d) absence de destruction en présence d'un utilisateur solveur. Si la scène n'exerce pas la contention attendue, conclure UNPROVEN, jamais PASS implicite. Commencer par P0, puisque P1 ajoute une obligation d'exclusion externe plus forte. Ne pas implémenter un correctif natif complet avant ce test et la politique Cyberbotics.

### Question Cyberbotics — préparée, NON envoyée

> Dans Webots R2025a, un plugin physique peut-il appeler `dJointDestroy` sur un contact créé automatiquement par Webots, découvert via `dBodyGetJoint` ? Le no-op historique des joints appartenant aux groupes doit-il être conservé (P0) ou une destruction effective est-elle permise (P1) ? Webots garantit-il qu'un ancien `dJointID` ne puisse affecter un nouveau joint après destruction et réutilisation de son adresse, ou l'ID devient-il invalide à cette destruction ?

## 7. Verdict contraignant

- **H0 : ESTABLISHED** (domaine de validité des objets C/ODE épinglés ; garantie Cyberbotics explicite de compatibilité plugin non obtenue).
- **H1 : UNPROVEN** (nécessité contractuelle Webots non démontrée).
- **P0 sous H0 : UNPROVEN** (possible conditionnellement ; phase/Qt/ABI non qualifiés).
- **P1 sous H0 : UNPROVEN** (possible sous admission et quiescence ; callback worker bloquant).
- **Protection sous H1 : NON_VIABLE_WITH_RAW_ID** (adresse réutilisable, sans identité temporelle transportée).
- **Sûreté des verrous Qt : UNPROVEN**.
- **Sûreté des workers : UNPROVEN**.
- **Compatibilité ABI : UNQUALIFIED**.
- **Protocole minimal identifié : CONDITIONAL**.
- **Implémentation native complète : NOT_READY**.
- **PR #766 : NO_GO tant que le défaut #771 n'est pas corrigé**.
- **Cyberbotics : NOT_READY**.

Aucune modification à main, #756/#760/#765/#766/#771/#773/#774, aux branches D1 ingénieur 3, au Runtime/LAND/RESET ou à des oracles.
