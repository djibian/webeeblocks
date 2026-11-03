# Grand Prix autonome — contrat applicable de simulation (#587)

**Décisions produit du propriétaire : 13 octobre, puis 3 novembre 2026.**
La [décision du 3 novembre sur #587](https://github.com/djibian/webeeblocks/issues/587#issuecomment-6598600569)
**supplante uniquement** le U carré à côtés fixes et ses deux virages toujours
à gauche : géométrie et H désormais variables, cornières physiques aux coins,
premier livrable **Linux** permettant la conception Blockly autonome de
l'enseignant, sans nouvelles primitives présumées. Toutes les exigences
de sécurité et de comportement ci-dessous demeurent obligatoires. Les anciens
cahiers des charges à tours multiples, bonus, pénalités et ligne finale sont
historiques, de même que les résultats `gp-v2/v3/v4` et `gp-u-v1`
sur leurs mondes exacts : **aucune ancienne preuve native ne qualifie les
nouveaux circuits**. Le contrat est une cible à implémenter/tester, **pas une
déclaration de livraison opérationnelle ni une qualification physique**.

## Mission élève et comportement attendu

Le Crazyflie parcourt **une seule fois trois segments consécutifs** de longueur
individuellement choisie parmi **2,00 / 2,50 / 3,00 m**, avec exactement
**deux virages à 90°**, chacun indépendamment à **gauche ou droite**
(GG, GD, DG, DD), sans quatrième segment ni ligne finale distincte.
Sur l'ensemble du circuit : **1 à 3 portiques H ouverts**, au maximum un
par segment, nombre et positions variables selon une configuration reproductible.
**Aucun obstacle BAS** au sol, y compris sur les segments sans H. Deux
**cornières HAUTES en L**, chacune dotée de deux branches de **0,60 m**
(largeur du couloir), matérialisent les coins et sont détectables par les
télémètres horizontaux : elles ne sont ni un portique ni une zone de vol bas.
Un H **fermé** termine le troisième segment et ne doit jamais être franchi.

Le programme doit reconnaître les H et mémoriser les **franchissements complets** pour choisir, avant le H fermé, parmi trois positions d'atterrissage :
- **1 franchissement** : centre ;
- **2 franchissements** : **50 cm à gauche** ;
- **3 franchissements** : **50 cm à droite**.

Gauche/droite sont définies dans le sens d'arrivée à la fin du troisième côté. Les zones ont une aire et des tolérances observables ; un atterrissage dans une mauvaise zone **échoue**, même sans collision. L'oracle ne regarde jamais la structure du Blockly/AST et ne transmet au programme aucune graine, nombre de H, zone correcte, identité de H fermé ou donnée cachée. La variable compteur est une solution naturelle, pas une contrainte syntaxique.

Un H est compté exclusivement après **engagement, passage complet dans le sens prescrit et dégagement**. Oscillation, recul, observation multiple, passage partiel, porte contournée ou porte traversée à l'envers ne sont pas des franchissements valides. Le H final est découvert par perception ordinaire et observation active, non par signal secret.

## Géométrie variable, cornières physiques et validation

- **Trois segments de 2 / 2,5 / 3 m**, chacun variable indépendamment ; deux
  virages orientés indépendamment gauche/droite. **Couloir virtuel de 0,60 m**
  de large, délimité par le ruban **rouge pointillé** au sol. La **ligne blanche
  centrale n'est qu'un guide visuel** (option A), **sans télémétrie de ligne**
  ni état caché transmis au programme. Aucun raccourci ou chevauchement de
  couloirs ne doit permettre d'éluder un H, un virage ou l'oracle. La combinaison
  de trois segments et du terminal doit être réalisable sans croisement illégitime,
  et suffisamment sûre/dégagée pour les transitions de vol haut, détection et
  décision sur capteurs.
- **Deux obstacles physiques en L**, aux **deux coins extérieurs** (un par virage),
  chacun fait de **deux branches de 0,60 m de long**, alignées sur les deux
  limites rouges pointillées extérieures convergentes. Elles doivent être
  **assez hautes pour les télémètres horizontaux à l'altitude normale**, visibles
  dans Webots, dotées de **colliders Solid**, et ne pas boucher le couloir de
  sortie. En arrivant sur le segment, un capteur frontal doit pouvoir constater
  l'approche de l'extrémité et le côté de l'obstacle doit indiquer par observation
  latérale l'unique direction praticable (obstacle à droite → gauche,
  obstacle à gauche → droite). Cette hypothèse exige des essais natifs de
  distances, orientation, freinage, précision et collisions. Les cornières ne
  constituent pas des capteurs magiques ni des repères programmatiques.
- H avec ouverture nominale **0,56 m**, panneaux latéraux, traverse supérieure ; préserver le rayon de gabarit témoin **0,09 m**, collisions et limites de perception. Les H sont placés uniquement dans les portions offrant assez de place pour détecter, descendre, passer, remonter et tourner.
- Aire d'arrivée élargie **environ 1,70–1,80 m** (hypothèse à tester), réellement dégagée et avant le fermé ; trois cibles latéralement espacées de 0,50 m. Le H fermé ne doit pas être contournable depuis cette aire.
- **Toutes les configurations partagent les mêmes règles de mission et de
  sécurité**, mais varient en **longueurs indépendantes, directions de virages,
  nombre et positions des H**. Le H terminal, les trois zones de pose et leurs
  éventuels élargissements sont **orientés relativement au dernier segment**,
  sans supposer une direction finale fixe. Les mondes sont versionnés et
  reproductibles ; le **même `.wbb` / AST** est utilisé sans paramètre caché.
  Prévoir un ensemble aisément sélectionnable sous Linux (au moins douze
  configurations pédagogiquement distinctes et une génération reproductible).
  Toute dimension longue qui ne respecte pas les 210 s ou les dégagements
  reste **non qualifiée** ; ne jamais corriger l'échec en assouplissant l'oracle.
- Le modèle Crazyflie Webots R2025a observe horizontalement jusqu'à **2 m** et le Runtime v2 limite la translation à **0,35 m/s** et le lacet à **0,7 rad/s** ; les acquittements et les modèles géométriques parfaits ne prouvent ni freinage ni robustesse au bruit/dérive.

## Zones de basse altitude et bandes au sol

Le drone vole **à altitude normale en dehors du franchissement des H ouverts**. Pour chaque H ouvert, définir un **seuil de basse altitude** et une zone longitudinale délimitée par une **distance maximale avant** et une **distance maximale après** le plan du portique. Les deux limites sont visibles **au sol dans Webots**, correspondant au **ruban adhésif au sol du futur parcours réel**.

L'oracle vérifie à chaque pas les **poses et altitudes réelles**, pas simplement la texture du sol ni la présence d'un bloc de programmation. **Tout vol bas hors de la zone autorisée échoue**. En particulier, être bas entre deux H, sur un côté sans H ou juste hors d'une bande est invalide. Ne pas augmenter arbitrairement la bande pour supprimer des échecs : elle doit suffire aux transitions verticales prouvées de descente avant H et de remontée après H.

Trois **exceptions bornées et testées** : phase de décollage à la plate-forme de départ ; reconnaissance/descente et pose dans l'aire terminale ; **descente forcée à l'échéance de 210 s, déjà classée échec**. Le H fermé ne crée pas une zone basse autorisée sur tout le dernier côté.

**Restent expérimentalement à fixer** : distances avant/après, limites haute/basse, tolérances d'échantillonnage, encombrement des bandes, dimensions de l'aire, règles exactes d'engagement/dégagement. Calibrer d'après les tracés natifs R2025a, perception, arrêt, virage, attitude, latéralité et pose ; ne pas affaiblir les protections.

## Temps, résultats, échéance

Aucun **point**, **bonus de porte**, **pénalité de temps**, barème ou **classement logiciel**. En simulation, le résultat de la tentative courante affiche en français : **réussie/échouée**, **durée Webots**, **motif d'échec**, éventuellement passages validés comme diagnostic non scoré. Aucune base de classe, historique ni classement entre élèves.

**Le classement chronométrique ne concerne que le défi final réel organisé hors WebeeBlocks**, où tous les programmes sont évalués sur **le même parcours physique**. On ne compare que les temps des missions réussies.

**210,000 secondes** depuis l'admission effective du TAKEOFF est le **plafond arbitraire de conception** voulu par le propriétaire. Une mission réussit seulement après **traversée du parcours complet, respect des zones, reconnaissance du H fermé et pose stable dans la bonne zone AVANT le plafond**.

Dès le premier pas du simulateur à **210,000 s**, un mécanisme **indépendant du Blockly/AST** doit (1) marquer la tentative **ÉCHOUÉE / temps écoulé**, irrévocablement, (2) **interrompre l'autorité et les commandes du programme élève**, (3) **commander immédiatement l'atterrissage** quel que soit le lieu, même dans un portique. L'éventuel choc de la descente en simulation ne modifie ni cet ordre ni l'échec : **aucune attente de zone dégagée**. Un LAND tardif, un ACK tardif, un STOP ou un RESET ne réhabilite pas la mission. L'instant de **commande** n'est pas l'instant de fin d'atterrissage. La simulation ne doit pas prétendre que la limite établit une autonomie batterie.

Pour le **Crazyflie réel**, l'objectif de surveillance indépendante à 210 s et commande de pose immédiate reste à **qualifier séparément** : aucune autonomie avec Flow deck/Multi-ranger, maîtrise de l'autorité de contrôle, récupération, réserve ou sécurité matérielle n'est prouvée par cette décision. Aucun essai physique ni autorisation de vol avant les gates **#157/#72**.

## Preuves et falsification

Essais **natifs Webots R2025a** avec 1, 2 et 3 H ; positions sur chacun
des trois segments ; **les quatre combinaisons de virages**, longueurs homogènes
2/2,5/3 m et mixtes, mesure réelle des cornières avant/pendant chaque virage,
même AST élève apprenant le nombre et choisissant les trois destinations ;
comparer deux mondes à **fin sensorielle identique** mais destinations correctes
distinctes. Mesurer pires temps, écarts au plafond **210 s**, dégagements,
vitesses, altitude et collisions, y compris sur les segments de 3 m. La
livraison de l'environnement Linux d'**expérimentation** ne présume ni une
solution Blockly gagnante ni un PASS automatique de toutes les variantes ;
les parcours présentés comme qualifiés devront satisfaire toutes les
obligations natives avec le programme inchangé.

Cas négatifs à conserver/créer : mauvaise zone (sur chaque orientation finale),
collision sur H ouvert/fermé **ou cornière en L**, H fermé contourné, raccourci
et **sortie de couloir par un coin**, virage du mauvais côté, H absent raté,
demi-franchissement, franchissement inversé après virage, oscillation et
décompte double, mémoire erronée, saturation de capteurs, faux fermé, bandes
avant/après franchies en altitude basse **d'un seul pas**, vol bas entre H,
sur segment sans H et hors aire finale, limites juste avant/à/après
**210,000 s** (pas Webots 8 ms), LAND imposé au timeout **dans un H**,
ACK/réponse/RESET tardif, essais successifs et course CPU/horloge. Refuser un PASS si les oracles, traces ou preuves du véritable R2025a sont insuffisants.

Exiger source/artefacts versionnés avec poses/altitudes et temps Webots, reproduction plusieurs graines, mêmes programmes AST, contre-exemples falsificateurs et limites scientifiques explicites. **Les anciens tests de points, de ligne finale et de plusieurs tours sont à conserver comme histoire du prototype, pas comme critères actifs.**

## Frontières de développement et premier livrable Linux

[#808](https://github.com/djibian/webeeblocks/issues/808) porte les mondes
paramétrables et leurs **cornières en L réellement physiques**,
[#809](https://github.com/djibian/webeeblocks/issues/809) le **cycle utilisateur
Linux réellement testable** : lancer un parcours reproductible, manipuler
Blockly, faire voler et observer le drone en simulation, pas-à-pas,
corriger, enregistrer/réouvrir un vrai projet `.wbb`, relancer le même
programme sur d'autres mondes. L'enseignant **développe lui-même sa stratégie** ;
ne pas proposer/implémenter de nouveaux blocs avant les difficultés réellement
observées. Le bloc expérimental `guarded_move` de #659 est **rejeté**, PR close
non fusionnée.

La première livraison n'attend pas une preuve que l'enseignant a déjà
résolu les douze mondes ; **elle doit permettre de chercher librement cette
solution**, sans qualifier prématurément les parcours ou relâcher une règle.
Conserver les anciens tests natifs comme témoins bornés à leurs mondes exacts.
Tous les changements passent par **petites PR, CI Gate exacte et contre-revue
indépendante V5**. Maintenir le pipeline
**activité → Blockly → AST → préflight → interpréteur partagé → backend**.
Les activités officielles 2–7, le vol réel #157/#72 et les autorisations
humaines ne sont pas modifiés par cette décision.
