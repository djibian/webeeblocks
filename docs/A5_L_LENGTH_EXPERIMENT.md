# A5 — Cornières L à longueur et sens variables (expérience native isolée)

**NON QUALIFIÉ POUR LES ÉLÈVES.** Ce document spécifie un test de faisabilité
de capteurs Webots R2025a, non un programme élève, un oracle de mission,
une preuve de vol motorisé, une qualification matérielle ni un PASS enseignant.

## Réfutation préalable et question expérimentale

Le `.wbb` privé à boucle `while range(front) > 0,75` et le `.wbb`
concurrent à répétition fixe `12 × [avancer 0,10 m, avancer 0,10 m]`
réussissent **tous les deux** le banc natif H proche/loin × G
gauche/droite : [run 44248718995](https://github.com/djibian/webeeblocks/actions/runs/44248718995),
HEAD `f030bf1f0b0f5283072568417c1b455cdad6ce58`, 3/3 jobs natifs.
Le concurrent obtient zéro lecture `front` et les mêmes quatre poses
physiques. Cette preuve **réfute l'utilité causale de la boucle dans ces
quatre mondes seulement**. Elle ne réfute pas l'utilité pédagogique
d'observer à nouveau dans les véritables L variables.

La prochaine hypothèse expérimentale est celle-ci : si la position
et **la longueur de la cornière physique** changent, un départ commun
ne permet plus de prévoir la bonne position du virage par un nombre de
pas figé. Il faut déterminer si le vrai Multi-ranger distingue
le changement *en vol*, puis seulement qualifier deux trajectoires
réelles concurrentes sans assouplir l'oracle.

## Quatre mondes sources, deux facteurs indépendants

La scène H initiale, le véritable Crazyflie, son Flow Deck et son
Multi-ranger sont strictement inchangés. Les quatre fichiers WBO
strictement privés varient :

| Facteur | Court | Long |
|---|---:|---:|
| Mur G, x (m) | 2,900 | 3,300 |
| Début du bras L, x (m) | 1,350 | 1,350 |
| Centre du bras L, x (m) | 1,975 | 2,175 |
| **Longueur solide du bras L, x (m)** | **1,250** | **1,650** |
| Marqueur d'approche, x (m) | 2,300 | 2,700 |
| Damiers, x (m) | 3,950 | 4,350 |

La deuxième dimension est l'ouverture **gauche / droite**, réalisée
par les mêmes boîtes G lower/upper et le bras latéral placé de l'autre
côté. Chaque WBO contient exactement sept `Solid` avec
`boundingObject Box` : deux solides H inchangés et cinq solides
physiques G, plus quatre `Pose` visuelles. Il n'ajoute aucun
Supervisor, agent, renseignement de parcours Blockly ni marqueur
d'autorité matérielle.

Le test `tools/ci/test_progression_a5_length_sources.py`
reconstruit les quatre textes à partir des WBO d'origine et refuse
toute divergence hors des transformations autorisées. Le nouveau
contrôleur **C natif isolé** atteste aussi séparément les boîtes et
positions physiques au démarrage ; un contrôle textuel ne suffit pas.

## Premier test natif : observer et réfuter, sans moteurs

Le nouveau banc `run_classroom_reactive_L_length_probe.py`
échantillonne directement les distances `range_front`,
`range_left`, `range_right` **du Crazyflie original** dans cinq
poses Supervisor *privées* : départ (0,0), enquête (1,8;0),
décision (2,25;0), ouverture gauche et ouverture droite au x du
mur −0,60 m.

Les critères sont bornés et antérieurs à la mesure :

- Départ **indiscernable** entre les quatre mondes :
  écart maximal des trois rayons ≤ 0,035 m.
- H initial observable à gauche (0,45–0,70 m) et mur G invisible
  par le rayon avant (portée à saturation proche de 2 m).
- La distance avant à l'enquête sépare les L courts et longs de
  **plus de 0,25 m** à sens G identique.
- La distance gauche au point de décision sépare ouvertures gauche
  et droite de **plus de 0,35 m**, sans fuite de longueur dans
  ce choix latéral (≤ 0,035 m).
- Sur les deux côtés de l'ouverture, le capteur avant distingue le
  passage physiquement ouvert du mur de plus de 0,35 m.

Toute mesure absente, pose inexacte, composant non identifié, fuite
initiale ou contraste insuffisant échoue et conserve les journaux.
Ces seuils ne sont pas des limites de mission : ils servent
uniquement à **réfuter la lisibilité de ces mondes pour un élève**.

Même si ce nouveau job devient vert, il ne prouvera **aucun vol** :
les poses sont téléportées par un Supervisor CI, les moteurs ne sont
pas commandés et aucun `.wbb` n'est soumis au monde. Le PASS natif
des capteurs ne doit jamais être transféré à une activité scolaire.

## Prochaine décision technique

Après observation des vrais rayons, créer et attester un oracle
**motorisé et indépendant** adapté aux quatre géométries, sans
affaiblir les contacts, les intersections swept, les limites de
temps ni les critères de pose. Vérifier ensuite le même véritable
`.wbb` réactif sur les quatre L et tenter le `.wbb` fixe
adversaire : **il doit échouer physiquement sur au moins un L**
pour rendre la réobservation fonctionnellement utile.

Enfin, réintroduire l'indice H proche/loin pour tester l'utilité
distincte d'une **variable simple** et les stratégies sans mémoire
avec des détours. Cela ne saurait être imposé par l'inspection
syntaxique de l'AST. Les véritables boutons et dialogues Save/Open,
les limites d'une salle Windows ancienne et le PASS personnel du
professeur restent des étapes séparées.

## Second private experiment — real two-WBB motorized short/long L (UNPROVEN)

The separate Draft-only CI job **a5-length-real-blockly-motor-draft-only**
must reopen the **two existing genuine Blockly 13.2.1 .wbb projects** from
the successful H×G experiment and fly them in the **four new** L worlds.

C++ admission checks the genuine Crazyflie, 32-ms step, unique scene,
11 children, visual pads and all **seven exact native collision boxes**.
A separate C physics monitor inspects obstacle/craft contact streams and
conservative swept intersections on every 32-ms step. The physical Floor
target is x=3.95 m for short, x=4.35 m for long, y=+0.62 m for both,
with the same ±0.10 m and z≤0.025 m acceptance as the earlier experiment.
The product PID, original sensors and original Webots flight runtime stay
unchanged.

Two independent native outcomes are required:

- The same reactive WBB SHA in all four worlds, fresh front readings,
  two genuine left readings, successful physical Floor on the appropriate
  pad and full seven-Solid swept coverage.
- The same fixed-repeat WBB SHA in all four worlds, **zero** native front
  readings, genuine H/G left observations, an attempted LAND and a **real
  wrong-X Floor contact** attested by the independent C code, with native
  FATAL premature_floor_contact and no native positive Floor marker.

The browser's LAND ACK cannot create mission success. Timeouts, spurious
collisions, a missing robot window or runtime failures do not count as a
confirmed fixed-repeat physical counterexample.

**No new native motor result is claimed by the source itself.** The Draft
CI must pass on the exact commit before drawing conclusions. Even a later
success would not qualify the full owner-approved L-corner pedagogy, the
necessity of any particular AST variable syntax, Windows pupil Save/Open,
human classroom acceptance or physical flight authorization.

## Résultats réellement observés — 18 novembre 2026

La preuve ci-dessous **supplante les états « UNPROVEN » des sections
préparatoires ci-dessus**, sans qualifier pour autant l'activité élève.
HEAD expérimental `05cf8409dd0f6075cb18155a35b898b1866c53af` :
[run #44265683691](https://github.com/djibian/webeeblocks/actions/runs/44265683691),
[job moteur #134669496728](https://github.com/djibian/webeeblocks/actions/runs/44265683691/job/134669496728)
`completed/success`.

Trois **véritables projets Blockly .wbb privés**, chaque fois identiques
entre A/B/C/D et soumis au même PID Webots R2025a, aux sept solides
collisionnables, aux contrôles swept à 32 ms et à une véritable pose Floor :

- **Réactif** : 4/4 poses autorisées, 23/23/27/27 lectures frontales ;
  mesure réévaluée en boucle.
- **Aveugle fixe** : 4/4 rejets physiques à une pose X intermédiaire ;
  zéro lecture frontale.
- **Un relevé ponctuel** : 4/4 poses autorisées, **une seule** lecture
  frontale à x≈1,80 m, puis `SI/SINON` et 4/8 avances complémentaires.
  Empreinte du même .wbb :
  `2326fb5a5edfca58581c764715c595c49d1a5bbd92095319c32642ca88707245`.

**Réfutation pédagogique** : ces quatre mondes statiques n'établissent
**pas** l'utilité fonctionnelle spécifique d'une **boucle de réobservation**
au-delà du relevé ponctuel déjà maîtrisé en A4. La variable
`destination` ne varie pas non plus : l'indice initial H est toujours
« proche », et la destination reste toujours à gauche. Exiger la syntaxe
`WHILE` ou `variables_set` serait artificiel. Il faut éprouver de
nouvelles informations découvertes pendant le déplacement **et**
une destination dépendant d'un indice initial réellement variable,
puis des adversaires sans mémoire et à lecture unique. Sur un ensemble
fini de mondes, on ne peut pas prouver l'impossibilité logique de toutes
les stratégies à nombre fini de tests ; la qualification doit aussi
mesurer la valeur cognitive en classe de la stratégie enseignée.

**Autre échec distinct dans le même run** :
[job H×G #134669497020](https://github.com/djibian/webeeblocks/actions/runs/44265683691/job/134669497020)
`completed/failure`. Le moniteur C a correctement mesuré une vraie
pose au mauvais damier `C blind_h` à
`x=4.091320447, y=0.598925165, z=0.012652966, t=90.816`,
puis `FATAL premature_floor_contact`. La trace native confirme
`LAND_TOUCHDOWN`, `LAND stop=1` et `RESPONSE 14 OK`.
Le navigateur a été interrompu **avant** ses événements `LAND_ACK`
et `TEST_COMPLETE`, exigés à tort par le test négatif. Un nouveau
test peut accepter ce cas **uniquement** si le mauvais contact Floor,
le fatal natif, la réponse native LAND et leurs temps sont attestés,
avec absence de succès élève ; aucune preuve ne doit être synthétisée.
L'ancien run **reste rouge** et la réparation n'est pas qualifiée tant
qu'un nouveau HEAD n'a pas été éprouvé.

**Statut de livraison : NO_GO pédagogique A5**, bien que les expériences
natives soient utiles. Aucun projet solution n'est publié dans le
catalogue, aucun PASS enseignant, aucune modification de l'activité 8,
des PID de vol, de l'oracle Grand Prix ou de la sécurité matérielle.
