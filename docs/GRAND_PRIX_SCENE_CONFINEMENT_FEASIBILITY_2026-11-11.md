# Grand Prix — confinement physique : étude d'arrêt (Webots R2025a)

**Statut : IMPASSE pour le prototype minimal demandé, sans transfert d'autorité produit.**
**Nature : analyse de sources + réutilisation de preuves natives antérieures, PAS un prototype de protection natif.**
**Base reconstruite :** `main@2f1c9398cf1f4cf1f6a08ceebdd303af5201fcc8` (2026-11-11).
**Moteur étudié :** source Webots R2025a épinglé `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.
**Périmètre :** un parcours variable Grand Prix; aucun changement de produit, pilote, évaluateur, monde ou moteur.

## Question réfutable

Peut-on charger et attester une fois les colliders, puis garantir leur
immutabilité pendant toute la tentative sans rescanner la géométrie toutes
les 8 ms, tout en autorisant le drone, ses moteurs, capteurs et contacts,
STOP/RESET/LAND et les protocoles READY/ALIVE ?

**Conclusion bornée : non avec les mécanismes de permission de R2025a
et l'interface Webots actuelle.** Ce n'est pas une impossibilité absolue
pour un moteur modifié ni pour un produit à vue 3D réellement déportée.
Les solutions envisageables dépassent ici le seuil de simplicité et de
preuve exigé pour le prototype minimal.

## 1. Contrats effectivement reconstruits

- `AGENTS.md`, `docs/PRODUCT_VISION.md`, `docs/ROADMAP.md`,
  `docs/GRAND_PRIX_ROUTE_CONTRACT.md` et `docs/GRAND_PRIX_SIMULATION_CONTRACT.md`.
- Monde actif : `tools/grand_prix/course_active_world_v2.py` :
  le Crazyflie et `GP_ROUTE_EVALUATOR` portent **tous deux** `supervisor TRUE`.
  `tools/grand_prix/evaluator_scene_identity_v2.py` **exige** explicitement
  la capacité Supervisor sur les deux; la retirer sans refonte est une
  régression de l'admission existante.
- Pilote : `controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp`
  (inclus par `grand_prix_route_flight`) lit/écrit via Supervisor
  `customData`, `model` et le champ `description` de l'évaluateur;
  ce n'est donc pas un simple utilisateur d'API moteurs/capteurs.
- Évaluateur : `tools/grand_prix/evaluator_publisher_v2.py`
  atteste via `evaluator_scene_identity_v2.py`,
  `native_collider_contract_v2.py` et `native_scene_snapshot_v2.py`,
  et publie le protocole sur des champs de nœuds. Il garde la vérité de
  la mission, les 500 ms de sol vérifié, l'ALIVE frais, l'échéance à 210000 ms
  et la fermeture irréversible d'une tentative compromise.
- #922 (observation native), #923 (révision partielle), #946 (acquisition
  compacte Windows), #966 (optimisation historique visuelle) sont des
  Drafts non décisionnaires. #912, #913, #914 et #911 maintiennent la
  séparation des preuves et la qualification Windows.

La documentation R2025a de Supervisor indique que `supervisor TRUE`
donne des pouvoirs généraux de modification de la scène et de contrôle
du monde ; aucune liste d'autorisations natives par champ, par nœud et
par opération n'est identifiée dans la version étudiée.
Les `getBaseNodeField` des PROTO sont documentés en lecture seule côté
API, mais cela ne protège ni les paramètres exposés et régénérations
PROTO, ni l'interface Webots, ni les autres chemins de modification.

## 2. Frontières réellement proposées puis écartées

**F0 — restriction Blockly/WWI.** Elle peut refuser l'instruction élève
avant le pilote, mais une mutation depuis un Supervisor privilégié, l'éditeur
Webots ou un redémarrage de monde ne franchit pas ce filtre. Non suffisante.

**F1 — fichiers de monde et PROTO en lecture seule + environnement OS
isolé.** Cela limite le remplacement de ressources persistantes, sans
immobiliser le graphe/ODE déjà chargé en mémoire. Même avec un contrôleur
protégé sur disque, `supervisor TRUE` conserve ses opérations de mutation.
Le lancement, le changement de monde et l'éditeur Webots restent
surfaces privilégiées. Non suffisante lorsque l'éditeur doit être testé
comme adversaire.

**F2 — pilote sans Supervisor + évaluateur de confiance seul Supervisor.**
Nécessiterait de modifier les échanges actuels, dont les écritures du
pilote dans le DEF évaluateur, et de prouver une nouvelle provenance de
READY/ALIVE/RESET. Un évaluateur Supervisor reste mutable et l'éditeur
Webots n'est pas supprimé par ce déplacement. Ce n'est pas un changement
minimal ni une preuve d'immutabilité.

**F3 — Webots inaccessible à l'élève + vue passive par IPC.**
Une séparation complète des processus et une API qui ne transmet que des
mouvements moteurs/commandes élève peuvent réduire fortement la surface
d'attaque **sous hypothèses de confiance explicites**. Mais il faut
remplacer l'accès direct à la GUI Webots, gérer rendu/latence, redémarrage
et cycle de vie du moteur. Ce n'est plus le prototype minimal demandé ;
sans cette frontière OS/GUI, la seule « fenêtre non éditable » est cosmétique.

**F4 — barrière native Webots avant chaque effet.**
Seule voie permettant de garder l'interface Webots existante et d'espérer
une interdiction effective des mutations, mais le patch #923 montre
déjà des points d'effet non convergents : écritures de champs différées,
MF insert/remove, création/suppression de nœud, poses de Solid, joint,
reset physique global et par nœud, forces/couples ODE, roues 3D,
redémarrage contrôleur et reset du monde. La régénération PROTO, les
mutations GUI restantes, `WorldInfo`, save/reload/revert et les
mutations de physique globale ne sont pas exhaustivement couverts.
Une barrière après effet ou un simple compteur ne suffit pas.
Il faudrait identifier, intercepter **avant** chaque effet et classifier
sa provenance, traiter les opérations autorisées (dont la physique
naturelle et le RESET drone), et démontrer les absences de chemins
de contournement. Une collection croissante de hooks constitue
précisément le critère d'arrêt demandé.

## 3. Matrice des attaques : ATTENTION, blocage avant effet non testé

La colonne « expérimentation existante » désigne des **essais hérités**,
non des essais de cette branche. Un incrément de révision et un refus de
jeton *après* mutation ne sont PAS une interdiction de mutation.

| Tentative / chemin d'effet | Résultat antérieur effectivement attesté | Barrière AVANT l'effet dans R2025a produit | Couverture de confinement |
|---|---|---|---|
| Déplacer/restaurer Solid par API Supervisor, même temps simulé | #923 `results-composed-linux.json` : x 0→0,1→0, rev. 3→4→5, ancien effet refusé | Aucune | NON |
| Modifier `Box.size` / `boundingObject` d'obstacle | Source du setter et de la reconstruction étudiée, pas de refus pré-effet natif exhaustif | Aucune | NON DÉMONTRÉ |
| Modifier Floor / `Floor.size` | #911/#946 : crash natif dans le scénario Floor, cause/retour non qualifiés | Aucune | NON DÉMONTRÉ |
| Régénérer ou substituer un PROTO | Sources et risques identifiés, pas de contre-épreuve complète | Aucune | NON DÉMONTRÉ |
| Insérer puis supprimer un Solid | #923 `results-linux.json` : cardinalité restaurée, rev. 7→8→9; effet permis puis jeton périmé refusé | Aucune | NON |
| Insérer/supprimer une primitive MF du collider | #923 `results-composed-linux.json` : rev. 9→10→11, ancien effet refusé | Aucune | NON |
| Changer une pose via GUI Webots (Shift+molette) | #923 `results-wheel-linux.json` : z 0,12→0,22→0,12, rev. 1→2→3 sur moteur corrigé | Aucune | NON |
| Autres actions GUI (arbre, import, édition champs) | Non exécutées avec barrière pré-effet | Aucune | NON DÉMONTRÉ |
| Remplacement/réouverture/revert du monde | Incarnation native étudiée ; aucun refus pré-reload démontré | Aucune | NON DÉMONTRÉ |
| `WorldInfo` / paramètres physiques globaux | Surface identifiée ; contre-épreuve spécifique absente | Aucune | NON DÉMONTRÉ |
| Reset physique global par Supervisor | #923 `results-composed-linux.json` : reset réel, rev. 12→13, ancien effet refusé | Aucune | NON |
| Force/couple ODE via Supervisor | #923 `results-composed-linux.json` : trois effets et révisions 17→20; jeton périmé refusé | Aucune | NON |
| Repositionner un joint/collider | #923 : rev. 15→16→17, retour aux coordonnées initiales; jeton refusé | Aucune | NON |
| Redémarrer le contrôleur | #923 : rev. 13→14, ancien effet refusé ; redémarrage n'est pas empêché | Aucune | NON |
| RESET légitime du drone, STOP, LAND | #922 route-5 shadow observe le cycle existant ; aucun prototype de gel de parcours ajouté | Sans objet (doit rester permis) | COMPATIBILITÉ NON TESTÉE sous gel |
| Remplacement d'un binaire privilégié | Un environnement OS séparé pourrait le restreindre ; aucun test natif de confinement | Aucune démontrée | NON DÉMONTRÉ |

**La contre-épreuve de modification puis restauration est particulièrement
réfutante pour l'idée « une attestation + pas de relecture » :** les tests
natifs #923 établissent que ces mutations peuvent réellement être produites
sans avancer le temps simulé. Le fait qu'un patch compteur remarque
ensuite la révision ne crée pas de protection pré-effet.

Le run #922 `route-5-revision-linux.json` observe 2128 trames comparables
sans divergence, mais il préserve l'évaluateur historique et ne prouve
ni la couverture mutation, ni le confinement. Les échecs/problèmes
d'ordonnancement et de handles natifs de #946 interdisent d'assimiler
sa capture compacte à une attestation immuable.

## 4. Invariant de sécurité qui resterait à prouver

Un véritable résultat devrait assurer, sous un modèle de menace explicite :

- Pendant une tentative `A`, toute opération `op` modifiant colliders,
  topologie, Floor, PROTO ou paramètres physiques doit être **refusée
  avant application**, à moins d'être explicitement une évolution
  physique normale du Crazyflie ou une transition de sécurité autorisée.
- Même une opération `move;restore` à temps simulé identique échoue dès
  `move`. Si un effet non autorisé était néanmoins commis, `A`
  perd définitivement READY/ALIVE; une restauration n'autorise rien.
- `RESET` légitime réinitialise drone et autorité de tentative, sans
  régénérer les colliders. `activity switch` est la seule transition
  autorisant une **nouvelle** incarnation de parcours, qui doit être
  entièrement réattestée avant une tentative suivante.
- Perte d'évaluateur, protocole ambigu, perte de provenance, débordement,
  contrôle non couvert : fail-closed et LAND préservé.
- Le pilote conserve exactement PID, capteurs, contacts, 8 ms, 210000 ms,
  STOP/RESET/LAND, AST et Runtime.

**Aucun candidat vérifié ne satisfait actuellement l'invariant pré-effet.**
L'API Supervisor n'offre pas la granularité nécessaire ; une politique
au niveau GUI n'intercepte pas les commandes Supervisor ; la mutation
des objets et du moteur traverse plusieurs méthodes natives disjointes.

## 5. Décision, preuves et coût

**Verdict : IMPASSE — prototype minimal arrêté avant codage.**
Il serait incorrect de fabriquer une « réussite » sur une enveloppe
Python, un verrouillage de l'éditeur ou quelques setters Supervisor et
de l'appeler confinement Webots. Aucun build Webots ni nouvelle injection
native n'a été exécuté pour cette branche ; les valeurs et contre-exemples
ci-dessus sont des preuves existantes de #923/#922/#946, avec leur portée
historique exacte.

Coût de généralisation actuellement **élevé et non borné** : maintenir
la couverture de tous les mutateurs Qt/GUI, Supervisor, ODE, PROTO,
world-load/revert, distinguer les écritures légitimes et valider chaque
nouveau chemin natif sur Linux et Windows. La complexité et la
surface de preuve sont supérieures au prototype minimal demandé,
sans garantie d'être inférieures au maintien du vérificateur historique.

**Aucun transfert d'autorité, aucune baisse de fréquence de contrôle,
aucun retrait de vérifications géométriques, aucun nouveau
`TEST_REQUIRED`, aucun READY ni GO.** Ce rapport est une preuve
d'arrêt, non une nouvelle autorité du Grand Prix.

Références durables : #911 (couverture et atomicité), #910/#922,
#923, #946, #966, #912, #913, #914 ; documentation Webots Supervisor,
Controller programming et interface 3D de la version R2025a.
