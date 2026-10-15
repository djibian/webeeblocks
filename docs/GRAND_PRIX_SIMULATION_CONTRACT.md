# Grand Prix autonome — contrat applicable de simulation (#587)

**Décision produit du propriétaire, 13 octobre 2026.** Les anciens cahiers des charges à trois tours, tours libres, bonus de portiques, pénalité temporelle et ligne droite finale sont **supplantés**. Les versions et preuves gp-v2/v3/v4 de #591 restent historiques, jamais des PASS du nouveau parcours. Ce texte est un contrat falsifiable, **pas une qualification physique**.

## Mission élève et comportement attendu

Le Crazyflie parcourt **une seule fois trois côtés consécutifs d'un carré**, avec exactement **deux virages**, sans quatrième côté ni ligne finale distincte. Sur l'ensemble des trois côtés : **1 à 3 portiques H ouverts**, au plus un par côté, nombre et positions variables selon une graine reproductible. **Aucun obstacle bas**, même sur un côté sans H : le sol est uniformément dégagé. Un H **fermé** termine le troisième côté et ne doit jamais être franchi.

Le programme doit reconnaître les H et mémoriser les **franchissements complets** pour choisir, avant le H fermé, parmi trois positions d'atterrissage :
- **1 franchissement** : centre ;
- **2 franchissements** : **50 cm à gauche** ;
- **3 franchissements** : **50 cm à droite**.

Gauche/droite sont définies dans le sens d'arrivée à la fin du troisième côté. Les zones ont une aire et des tolérances observables ; un atterrissage dans une mauvaise zone **échoue**, même sans collision. L'oracle ne regarde jamais la structure du Blockly/AST et ne transmet au programme aucune graine, nombre de H, zone correcte, identité de H fermé ou donnée cachée. La variable compteur est une solution naturelle, pas une contrainte syntaxique.

Un H est compté exclusivement après **engagement, passage complet dans le sens prescrit et dégagement**. Oscillation, recul, observation multiple, passage partiel, porte contournée ou porte traversée à l'envers ne sont pas des franchissements valides. Le H final est découvert par perception ordinaire et observation active, non par signal secret.

## Géométrie fixe et validation

- **2,00 m par côté** de trajectoire centrale : **première hypothèse**, non acceptée ; déterminer par essais natifs R2025a une **dimension fixe** commune à toutes les configurations, y compris la plus lente, offrant des dégagements dynamiques et une **marge temporelle confortable et reproductible avant 210 s**, sans rechercher systématiquement la taille maximale. Couloir environ **1,00 m** à éprouver.
- H avec ouverture nominale **0,56 m**, panneaux latéraux, traverse supérieure ; préserver le rayon de gabarit témoin **0,09 m**, collisions et limites de perception. Les H sont placés uniquement dans les portions offrant assez de place pour détecter, descendre, passer, remonter et tourner.
- Aire d'arrivée élargie **environ 1,70–1,80 m** (hypothèse à tester), réellement dégagée et avant le fermé ; trois cibles latéralement espacées de 0,50 m. Le H fermé ne doit pas être contournable depuis cette aire.
- **Toutes les configurations partagent exactement les mêmes dimensions** de piste, de zone finale et les mêmes règles ; seule la disposition/nombre des H ouverts varie. Les mondes restent versionnés et reproductibles.
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

Essais positifs **natifs Webots R2025a** avec 1, 2 et 3 H, positions sur chacun des trois côtés, même AST apprenant le nombre et choisissant les trois destinations ; comparer deux mondes à **fin sensorielle identique** mais destinations correctes distinctes. Mesurer pires temps, écarts au plafond 210 s, dégagements, vitesses, altitude et collisions pour **valider une seule dimension fixe, sûre et reproductible** sur les configurations retenues, sans conditionner la livraison à l'augmentation du côté au-delà de 2,00 m.

Cas négatifs à conserver/créer : mauvaise zone, collision sur H ouvert/fermé, H fermé contourné, raccourci, H absent raté, demi-franchissement, oscillation et décompte double, mémoire erronée, saturation de capteurs, faux fermé, bandes avant/après franchies en altitude basse **d'un seul pas**, vol bas entre H, sur côté sans H et hors aire finale, limites juste avant/à/après **210,000 s** (pas Webots 32 ms), LAND imposé au timeout **dans un H**, ACK/réponse/RESET tardif, essais successifs et course CPU/horloge. Refuser un PASS si les oracles, traces ou preuves du véritable R2025a sont insuffisants.

Exiger source/artefacts versionnés avec poses/altitudes et temps Webots, reproduction plusieurs graines, mêmes programmes AST, contre-exemples falsificateurs et limites scientifiques explicites. **Les anciens tests de points, de ligne finale et de plusieurs tours sont à conserver comme histoire du prototype, pas comme critères actifs.**

## Frontières de développement

**#588** porte cette révision documentaire ; la PR doit avoir son propre HEAD Ready, sa nouvelle CI et une **revue indépendante d'une autre exécution**. **#591 reste Draft** : réorienter par petites PR révisables le générateur de parcours en U, la signalisation au sol, l'oracle de basse altitude et d'atterrissage, l'échéance LAND souveraine et le programme témoin. Conserver les preuves des anciennes versions. **#589 activité 1** reste indépendant ; **aucune activité intermédiaire n'est modifiée**. Préserver le pipeline générique **activité → Blockly → AST → préflight → interpréteur partagé → backend**, le français, les contrats d'autorité et de sécurité physique. Aucun GO par l'auteur de ses propres changements.
