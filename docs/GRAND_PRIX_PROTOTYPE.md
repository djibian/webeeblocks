# Grand Prix — prototype de faisabilité #587

Ce candidat est une **simulation expérimentale**, pas une validation pédagogique
ni une qualification réelle. #588 fixe le contrat falsifiable ; #589 isole
l'activité 1 ; #590 propose séparément la boucle générique WHILE/UNTIL. Les
activités 2–8 et le backend physique sont inchangés. Aucun matériel, vol,
checkpoint ou reprise de #70 n'est autorisé.

## Géométrie et observations

`python3 tools/grand_prix/layout.py --seed 4 --output worlds/grand_prix_v2_seed4.wbt`
recrée exactement une configuration versionnée `gp-v2-4`. Les graines admises
sont les entiers 0–65535. Deux mondes représentatifs sont versionnés : 1 et 4 (quatre puis deux H, arrivée longue puis courte).
Ils utilisent le même Crazyflie, les mêmes vrais devices et le contrôleur de vol
Runtime v2 partagé, compilé sous un nom propre au prototype.

La boucle fait 1,4 m de côté, 0,8 m de largeur, avec quatre coins gauches
ordinaires et une jonction vers la ligne finale. Elle comporte 2–4 portiques.
Les H ont une ouverture de 0,56 m et une traverse pleine au-dessus de 0,62 m.
Leurs panneaux latéraux s'étendent 0,24 m de part et d'autre de la traverse.
Un segment sans H comporte à sa place un obstacle bas de 0,50 m, sur toute
la largeur de la piste. La ligne finale contient zéro ou un H ouvert puis un H
fermé à 0,80 m ou 1,10 m de la jonction. La zone d’arrivée suit cette fermeture
et les deux zones possibles ne se recouvrent pas. Le gabarit conservateur de l'oracle est une sphère de rayon 0,09 m,
uniquement pour le modèle de simulation représenté.

Le programme ne reçoit ni graine, ni position, ni identité, ni nombre de portes,
ni tour de l'évaluateur. Seuls les capteurs ordinaires, les variables et les
commandes de l'AST sont employés. La caméra et l'identifiant affiché restent
réservés à l'humain.

Les contre-exemples ont déjà contraint le générateur :

- H mince : rayons latéraux aveugles avant la traverse ; les plaques doivent
  précéder celle-ci.
- Quatrième côté + ligne trop longue : retour bas saturé ; la position du H du
  quatrième côté est fixée et la fermeture terminale rapprochée.
- Mur attendu à la jonction : aucun mur n'arrête la sortie ; il faut observer
  l'ouverture latérale, après avoir confirmé la paroi du segment.
- H du segment suivant : il peut masquer l'ouverture du coin à la mesure
  latérale ; les positions admissibles et le seuil de cette observation sont
  donc bornés ensemble.
- Plaques terminales trop courtes : détection tardive et gabarit déjà trop près
  de la fermeture ; le H final conserve de longues plaques.
- Deux H trop rapprochés : pas de dégagement observable ; le générateur garde
  un intervalle de réarmement avant le H fermé.

L'analyse de rayons idéale teste 100 graines. Le **même AST** témoin passe
les 92 géométries distinctes produites par toutes les graines 0–65535 dans ce modèle, découvre le compte au premier tour et le
réutilise par décrémentation aux tours suivants. Le témoin confirme la paroi
avant un coin, engage une porte une seule fois, descend et exige une mesure
avant basse finie <1,99 m, puis remonte après dégagement et vérifie la traverse
à l'arrière. Une saturation n'est jamais son certificat d'ouverture.

Une réfutation plus forte a invalidé la géométrie gp-v1 : un AST aveugle
(takeoff, descente unique puis déplacements/tours constants) réussit ses deux
configurations sans capteur ni variable. Le cas positif original est conservé
avec ses deux géométries dans
`tools/ci/fixtures/grand_prix_v1_blind_counterexample.json`. En gp-v2, le même
slot exige une hauteur basse pour un H et haute pour un obstacle bas dans une
autre configuration ; l’arrivée varie aussi. Le programme aveugle est désormais
réfuté dans la matrice, tandis que le témoin sensoriel reste accepté. Aucune
inspection des blocs ni donnée cachée ne produit cette différence.

La nécessité pédagogique du compte mémorisé est également réfutée dans cette
topologie : remettre toutes les écritures des variables « portes » et
« restantes » à zéro laisse le même parcours sensoriel réussir gp-v2-4. Les
quatre coins ordinaires suffisent à la fin des trois tours. Le test conserve
cette réussite légitime ; l'oracle ne la rejette pas pour sa forme AST. Le
témoin original découvre et réutilise un compte, mais le monde ne rend pas
encore cette mémoire **nécessaire**. Ce critère de #587 exige un autre design
pédagogique ou une clarification du résultat attendu ; aucun compteur caché
ni obligation artificielle de blocs n'est ajouté.

Un autre contre-exemple borne l'identification finale : fermer inopinément le
premier H ouvert de la ligne finale donne les mêmes mesures hautes/basses
qu'un H terminal fermé. Le témoin sensoriel déclare alors sa fin trop tôt ;
l'oracle de trajectoire refuse la réussite et le chrono, car un passage et la
vraie zone d'arrivée manquent. Le test conserve cette réfutation. Aucune suite
finie de mesures de distance ne peut donner l'identité sémantique de deux
géométries identiques. Le prototype assume donc exclusivement les configurations
immuables du générateur ; la reconnaissance robuste d'une fermeture imprévue
reste **non démontrée**. Le contrat #587 ne peut pas être déclaré intégralement
satisfait sur ce point par les seules configurations positives.

Cette preuve idéale ne valide pas l'inclinaison, les marges de freinage, les
signaux réels ou le programme dans Webots. Elle est un contrôle falsificateur,
pas un substitut à la nouvelle CI Webots.

## Oracle et temps

`grand_prix_evaluator` juge la trajectoire : coins et passages orientés dans
l'ordre pendant trois tours, ouvertures avec gabarit entier, piste, contacts,
altitude, ligne finale complète et atterrissage terminal immobile. Il n'inspecte
ni Blockly, ni l'AST, ni les variables du programme. Un contre-exemple a supprimé
la contrainte injustifiée d'un passage à 12 cm du centre de chaque coin : un
virage arrondi dégagé, dans la largeur de la piste, doit être accepté. Les
zones de coin restent séparées des H, ordonnées et soumises au même contrôle
de gabarit/piste ; des lectures répétées dans une zone ne font pas un tour. Les répétitions sur place,
le recul, les raccourcis et une sortie prématurée ne donnent pas de nouveaux
tours/portes. Un échec est terminal pour cette tentative.

Le contrôleur dédié observe et borne uniquement le transport de simulation
Webots existant. Il retient le temps de réception du takeoff, dans le même pas de
simulation que son admission, et exige son ACK réel. Une erreur ou un STOP
révoque définitivement cette mesure ; un ACK tardif ne l'efface pas. Reset
consomme l'acquittement natif puis prend la nouvelle identité du broker existant.
Il n'émet aucun mouvement de navigation ni effet physique. Une limite de
600 secondes Webots engage une seule fois le STOP natif de simulation, même
si le programme ou le navigateur est en attente ; le contrôleur conserve son
fail-safe jusqu'au Reset. La borne reste active tant que le résultat n'est pas
une réussite certifiée du même oracle et de la même tentative, avec takeoff
acquitté ; une telle réussite au sol est terminale jusqu'au Reset. Un résultat
ancien ou une simple complétion ne désarme pas la borne. Les commandes verticales conservent aussi une hauteur
nominale admise de 0,30 à 1,10 m, vérifiée avant leur effet et mise à jour
uniquement sur ACK. Cette borne publique empêche un survol des panneaux sans
changer les commandes partagées ni lire la position oracle.

Le résultat chronométré apparaît dans Webots avec l'identifiant de configuration.
Il utilise exclusivement `Supervisor.getTime()` / `wb_robot_get_time()`, s'arrête
après complétion du même oracle et stabilité au sol, et est absent pour tout
échec, collision, interruption, observation invalide ou mode pas-à-pas. Il ne
persiste aucune tentative. L'AST ne lit pas le chrono.

**Limite non résolue :** une durée Webots sur une trajectoire donnée est
indépendante de l'horloge murale, mais cela ne prouve pas qu'un même AST piloté
par un navigateur produise exactement la même trajectoire/attente sur deux CPU
ou à deux vitesses de simulation. Les latences WWI et des hooks peuvent ajouter
du temps simulé. La répétabilité à un pas et la comparaison compétitive restent
à démontrer ; ce prototype ne doit pas être annoncé comme un chrono compétitif
validé. Aucune soustraction d'attentes cachées n'est introduite.

## Usage et preuves manquantes

Après préparation des assets Blockly et compilation du contrôleur
`controllers/grand_prix_flight` dans R2025a, les mondes du prototype ouvrent une
Robot Window française utilisant le même Blockly/AST/interpréteur et le même
format `.wbb`. Ils ont leur propre profil, avec un budget de 20 000 pas borné.
La scène courante reste attachée au monde ; le projet ne mémorise pas une graine.

Le programme témoin est **un outil de preuve machine**, pas une solution livrée
au workspace élève. Il utilise provisoirement les répétitions bornées avec
conditions déjà intégrées. La fenêtre expose la boucle WHILE/UNTIL lorsque son entrée générique est
intégrée par #590 ; avant cette intégration elle reste absente du profil. Elle n'est pas dissimulée dans
un bloc spécial ou une boucle native propre à la mission.

Le brouillon exécute un probe Webots non décisionnel dans `Select suites` et
conserve ses observations ; il ne publie jamais `CI Gate`. Le candidat Ready
exécute ce probe dans le job Runtime obligatoire `grand-prix-prototype`, qui exige les tests idéaux puis une
exécution dans le vrai R2025a des configurations 1 et 4 avec le même AST et les
mesures réelles. Un échec reste rouge, sans adaptation du compte attendu. Ces
résultats, la reprise fraîche, deux stratégies différentes, les essais négatifs
réels, l'intégration au changement automatique de sous-scène #589, les fichiers
représentatifs et la répétabilité CPU/chrono sont encore des critères d'acceptation.
Le prototype doit rester Draft tant que ces frontières importantes ne sont pas
résolues ou réduites explicitement par une revue du résultat borné.


Le probe Webots du HEAD `fbaeb657eb6232a5c675c7f6215deb9a7ad8b69e`
(run 38231836526, artefact 11739876500) n’a pas exécuté le Crazyflie : le chemin
`webots://projects/...` visait des PROTO absents de l’image officielle, puis
l’évaluateur a échoué sans véhicule. C’est un échec de préparation, aucune
preuve de vol simulé ou de détectabilité. Le runner fournit désormais les
assets depuis le commit R2025a exact, montés en lecture seule, refuse un
fallback/Traceback sans attendre la fenêtre complète, et écrit la perspective
Robot Window sous son vrai nom Webots. La répétition est justifiée par cette
correction causale ; le résultat futur reste à obtenir.

Le HEAD `e60f88daf724c40dc1f42dfeb0ac39469935993b` (run 38236332327,
artefact 11741301017) charge la géométrie et ouvre la fenêtre, mais son contrôleur
ne démarre pas : `libQt6Core.so.6` est introuvable. La fenêtre expire sur READY ;
aucune mesure capteur ni trajectoire n'a été obtenue. Le contrôleur reçoit désormais
le même `runtime.ini` Qt/Webots que le Runtime partagé. Les textures par défaut
du commit épinglé sont ajoutées au montage. La nouvelle paire 1/4 couvre aussi
deux comptes de H distincts ; 1/3 avait quatre H dans les deux mondes.

Le premier probe dynamique fonctionnel, HEAD
`3db9611cf2bf07bf50a96bf2335812a37c0a4f57`, run 38238140957, artefact
11742870803 (SHA-256 3ce4818d81139fdecdf24fd5e7c6555d6850211d379761edb2f421ad34fc4f33),
est **rouge** sur gp-v2-1. Il relève 432 vraies mesures ; les variables du témoin
rapportent trois tours et quatre H, mais l'oracle invalide dès l'ascension,
avant l'ACK de takeoff. Ces variables ne prouvent donc aucun parcours valide.
Le second monde n'a pas été exécuté. Un diagnostic de rejet avec temps,
position, vitesse et invariant est ajouté exclusivement au journal superviseur,
jamais au programme ; les seuils restent identiques. Le runner termine au
rejet pour conserver la cause initiale sans attendre une fausse complétion.
Le candidat ne peut être déclaré faisable dans le vrai Webots sur cette preuve.

Le diagnostic du HEAD `b7f1493f7ce8054f95c15068d6b5020c8bcd693c`
(run 38239852904, artefact 11741872557, SHA-256
0fd465e6b525989fdd80d2795ee41c8d62092e5a6309c3a66d9a657bfc74f932)
identifie précisément la cause : à 5,216 s Webots, la hauteur est
1,174482845 m et la vitesse verticale 1,001077986 m/s. Le décollage nominal
à 0,90 m dépasse le plafond relatif de 1,15 m ; l'oracle reste terminal,
non chronométré. Cette mesure réelle devient une régression négative. Le témoin
employait alors les mêmes commandes génériques avec un décollage à 0,50 m,
puis une montée de 0,40 m avant navigation. La durée inclut ces deux commandes.
Le contrôleur partagé, les seuils de l'oracle et les règles de collision restent
identiques ; la nouvelle réussite dynamique reste à obtenir.

Le HEAD `1986d330a8a74b9631fb507af6595fd98e8bbc40` (run 38240569802,
artefact 11742728400, SHA-256
222dd93c1ea288fa2eb62a80bd67453fe5ebde947d4c5c2222fa7f96290ebe8b)
franchit le décollage progressif et le premier H, mais sa remontée de 0,50 m
dépasse à son tour le plafond : z=1,170211127 m à t=38,112 s, curseur oracle 2.
Ce second échec réel devient aussi une régression négative. Les hauteurs
nominales du témoin sont désormais 0,80 m / 0,40 m, avec transitions de 0,40 m ;
la mise en altitude initiale utilise 0,50 m puis +0,30 m. Tous les seuils et
le contrôleur partagé sont conservés. La nouvelle preuve dynamique reste
indispensable ; ces adaptations de programme ne prouvent aucune marge réelle.
