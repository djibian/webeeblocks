# Procédures Blockly sans paramètres — premier incrément

Le besoin est de rendre possible une procédure **construite par l'élève**, dont
les blocs restent visibles, modifiables et exécutables pas à pas. Aucun traitement
de H n'est fourni. Les activités officielles 2–7 restent inchangées.

## Définition, compilation et limites

- Réutilisation des blocs Blockly 13.2.1 `procedures_defnoreturn` et
  `procedures_callnoreturn`, du renommage et de la sérialisation natifs.
  Le mutateur de paramètres est retiré de l'interface. Une signature importée
  avec paramètres reste refusée par le compilateur, sans coercition silencieuse.
- Catégorie française « Procédures », exposée uniquement dans le prototype Grand
  Prix. Le flyout présente une définition et les appels des procédures présentes,
  sans fonctions à résultat ni retour anticipé. La définition forme une pile
  distincte du programme principal dans le même espace de travail et le même `.wbb`.
- Un unique programme principal commence par TAKEOFF et finit par LAND.
  Les définitions sont des piles séparées autorisées ; les autres blocs détachés
  restent refusés. Aucun TAKEOFF/LAND n'est autorisé dans une procédure, même
  inutilisée, ni dans ses appels transitifs.
- Noms non vides, 80 caractères maximum, résolution sans distinction de casse ;
  doublons, appels absents, paramètres et cycles directs/indirects refusés.
  Toutes les définitions sont compilées pour vérifier leur syntaxe et leurs
  cycles ; l'affectation préalable des variables se vérifie aux sites d'appel.
- Expansion bornée à 2 000 instructions compilées au total (vérification des
  définitions comprise), profondeur de séquences à 20, et limite historique
  de 200 instructions par séquence. Ces limites protègent aussi d'un graphe
  acyclique dont l'expansion serait exponentielle. Le budget statique de
  l'interpréteur reste distinct et contrôle toutes les branches avant TAKEOFF.

Un appel devient un nœud explicite :

```json
{"kind":"call","name":"observer","body":["instructions compilées de la procédure"]}
```

Le corps est développé au site d'appel ; l'AST n'a ni table globale de symboles,
ni lookup dynamique, ni pile de récursion. Le champ `name` est une étiquette
vérifiée, pas une autorité : la sémantique exécutée est exactement `body`.
Les anciens projets produisent les mêmes formes AST qu'avant. Le format `.wbb`
et l'enveloppe AST v1 sont conservés ; un ancien interpréteur refuse le nouveau
kind plutôt que de l'exécuter partiellement.

Un appel coûte un pas plus le coût conservateur de son corps. Il partage les
variables du programme principal. Les profils, directions de capteur, bornes de
mouvement, capacités et lectures initialisées sont contrôlés dans les corps.
L'interpréteur exige `capabilities.procedures === true` avant tout effet. Seul le
backend WWI de simulation annonce cette capacité. Le préflight physique conserve
son refus de `call` : aucun élargissement de son domaine n'est effectué.

Les chemins AST `.../body/...` sont reliés aux **vrais IDs** des blocs de la
procédure, à chaque appel. Le pas de l'appel puis les pas internes restent
observables. Les exceptions, interruptions et refus de capteur se propagent ;
aucune capture ne convertit une interruption en fin normale ou en LAND réussi.

## Arrivée terminale et futur contrôle de sortie

Un retour de procédure ne quitte pas les répétitions appelantes et ne résout
pas la sortie du troisième côté. Une instruction « terminer » qui saute le LAND
final serait incorrecte. Ce premier incrément n'introduit ni retour anticipé,
ni état caché d'arrivée, ni troisième variable élève.

La plus petite piste retenue pour un incrément ultérieur est une **région de
recherche quittable explicitement**, avec sortie depuis les appels autorisés :

```text
DÉCOLLER
nombre_H = 0
DANS LA RECHERCHE :
    RÉPÉTER 3 FOIS :
        position = 0
        ... progression et procédure élève ...
        ... la procédure QUITTE LA RECHERCHE si le fermé est confirmé ...
        ... virage tant que la recherche continue ...
    ÉCHEC  // épuisement sans arrivée confirmée
... placement et choix d'atterrissage par l'élève ...
ATTERRIR
```

Une telle sortie saute les répétitions restantes et le troisième virage, puis
rejoint la suite explicite du programme. L'épuisement normal de la recherche
échoue. Ce schéma évite un booléen mémorisé supplémentaire, mais n'est **pas
implémenté ni qualifié**. Il faudra lier statiquement les cibles de sortie aux
sites d'appel, refuser les sorties sans région compatible et revalider tous les
chemins vers LAND, le budget, les interruptions et l'observation. Le `call` actuel
n'absorbe aucun signal de contrôle futur et n'engage pas une sémantique de retour.
La reconnaissance du fermé reste entièrement dans la procédure Blockly élève.

## Déplacement surveillé : frontière à résoudre ensuite

Le backend JavaScript `move()` attend un acquittement `OK` sans valeur de
position ni déplacement mesuré. Dans le Runtime C, la cible XY est calculée
à partir de la pose courante ; `OK` suit les tolérances de position/vitesse/yaw/
altitude et la fenêtre stable existantes. `TRACE MOVE distance=...` conserve
**la consigne** `active_value`, pas le déplacement effectivement mesuré.

Une somme de ces consignes acquittées peut constituer une progression nominale,
mais n'est ni une odométrie, ni une borne de l'erreur XY accumulée. Aucun
accumulateur de mètres mesurés n'est ajouté ici. Le démonstrateur compte seulement
les appels dont le mouvement a été acquitté.

Avant une primitive de progression mesurée, établir un résultat de déplacement
corrélé à chaque commande et à sa complétion, avec unités, fraîcheur, projection,
incertitudes et absence de double comptage. Les résultats ambigus ne permettent
ni incrément ni renvoi automatique. Le backend physique reste refusé tant que
son propre contrat de mesure/autorité n'est pas qualifié.

Une première avance surveillée pourra échantillonner les capteurs entre des
mouvements bornés. Le minimum actuel de MOVE est 0,10 m : ce n'est pas une
surveillance continue, et l'acquittement ne fournit aucune borne générale de
freinage. Les seuils, marges, lectures invalides/saturées et la distinction entre
« plus d'obstacle observé » et « H entièrement franchi » demandent des preuves
spécifiques. Aucun accès à la scène cachée ou à l'oracle n'est justifié.

## Démonstrateur et vérification

`tools/blockly/procedure_steps_demo.wbb` est issu de vrais blocs Blockly :
11 blocs au total, dont **7 dans le principal**, une procédure, une variable
`pas`, `répéter 3 fois`. Profondeur structurelle Blockly : **1** (on compte les
entrées de corps DO/STACK, pas les connexions séquentielles). Profondeur des
conteneurs dans l'AST développé : **2** (repeat puis call).

Il décolle à 0,80 m, appelle trois fois la procédure élève « avancer_un_pas »
(avance de 0,10 m puis incrément de `pas`), puis atterrit. Ce n'est pas un programme
Grand Prix : aucun H n'est reconnu ou compté, aucune réussite de mission native
n'est revendiquée. Dans le probe d'interface, l'issue injectée est délibérément
`not-achieved` et s'affiche « MISSION NON RÉUSSIE ».

Ouvrir le monde prototype `worlds/grand_prix_u_seed4.wbt` depuis ce candidat,
ouvrir sa Robot Window puis **Ouvrir** le `.wbb`. Les procédures apparaissent
à droite du principal ; **Pas à pas** permet d'observer l'appel et son corps.
Cela ne dispense jamais de la sécurité ou du préflight, et n'autorise aucun vol.

Tests ciblés :

```sh
node tools/ci/test_runtime_v2_procedures.js
node tools/ci/test_runtime_v2_variables.js
node tools/ci/test_runtime_v2_while.js
node tools/ci/test_runtime_v2_project_files.js
node tools/ci/test_runtime_v2_observability.js
node tools/ci/test_runtime_v2_preflight.js
node tools/ci/test_grand_prix_u_profile.js
node tools/ci/test_physical_capability_contract.js
```

Le test procédures est appelé par `test_runtime_v2_variables.js`, déjà exécuté
par le harnais core canonique. Il vérifie aussi la composition UNTIL + procédures.
La branche procédures dépend donc du correctif de #657 ; ce petit empilement
permet d'éprouver leur composition avant toute intégration.

Le probe optionnel de la vraie page HTML/Blockly/Zelos requiert Playwright,
un Chromium et les assets vendorizés ; il ne lance pas Webots :

```sh
node plugins/robot_windows/blockly_v2/prepare_blockly_vendor.js
CHROME_BIN=/chemin/vers/chromium \
WEBEEBLOCKS_PLAYWRIGHT_MODULE=/chemin/vers/playwright/index.mjs \
node tools/ci/probe_blockly_procedures_ui.mjs
```

Observation locale : Chromium 153.0.8010.0, page Grand Prix réelle, définition et
appel dans le flyout, mutateur absent, Save As/Open, **25 pas**, 11 blocs restaurés,
`pas = 3`, aucune erreur JavaScript. Le transport de commandes et les sélecteurs
de fichiers sont injectés ; ni le dialogue natif du système, ni la physique,
ni l'oracle Webots, ni Windows/Firefox ne sont qualifiés par cette observation.

Erreurs conservées : téléchargement Playwright tronqué (ZIP invalide), extraction
initiale du navigateur refusée sur chown, premier serveur isolé inaccessible ;
préparation corrigée avec le binaire npm décompressé sans reprise d'ownership et
serveur dans le processus de test. Le premier test d'hygiène a refusé un checkout
sale ; cela ne constitue pas un défaut X3 ou une preuve verte. Le premier test
variables a détecté l'hypothèse incorrecte `Blockly.Blocks` toujours présent dans
un environnement de test : garde ajoutée, puis test réexécuté. Les assertions du
probe ont été corrigées pour admettre l'icône commentaire native et le libellé
existant « MISSION NON RÉUSSIE », sans changer le produit.

La qualification native R2025a du programme élève, ses deux variables métier,
le franchissement du H isolé, les configurations cachées et la validation
pédagogique restent à réaliser. Aucun résultat de ce fichier ne constitue GO,
CI Gate, acceptation pédagogique ou autorisation de fusion.
