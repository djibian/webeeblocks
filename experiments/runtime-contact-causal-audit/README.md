# #637 — expertise indépendante : géométrie du premier contact et réponse PID

## Verdict borné

**La cause complète de RESET/LAND reste UNPROVEN. Aucun correctif produit,
aucune restauration de main, aucun GO intégrateur.** Cette étude explique
quantitativement une partie auparavant seulement corrélée du contraste LAND :
les poses enregistrées et le détecteur cylindre–plan R2025a suffisent à retrouver
le contact unique excentré du FAIL et les quatre contacts du PASS. Le PID
de production compilé retrouve ensuite les fortes consignes de tangage.
La contribution de ces mécanismes à la trajectoire complète reste à tester
par intervention native. Le résultat ne s'étend pas automatiquement au RESET.

Base lue : `main@f5435a8d28b7a2dfae2f50f896aa40a246a4858b`.
Contrat V5 / vision / roadmap : blobs `c00e855a431b1b83382ba333b0db490a8c330e53`,
`121409284eba687941c9f1f195077007c3352855`,
`e150cf29129304e54ce3a2eb7cd8208dbf648876`.
Les sources produit, monde, oracles, sécurité et CI ne sont pas modifiés.
Cette branche d'évidence n'est pas un candidat d'intégration et ne lance rien.

## Entrées vérifiées et reproduction

Les quatre ZIP Actions ont été téléchargés, leur SHA256 recalculé et tous leurs
membres contrôlés par CRC. Les manifestes original/instrumented ont été
recalculés pour le premier couple. `RESULTS.json` conserve les mesures et
résultats numériques, pas une nouvelle acquisition Webots.
Les quatre ZIP originaux complets sont conservés sous `evidence/` ; le script
les utilise par défaut, sans dépendre de la durée de rétention Actions.

| Rôle | Run / artefact | SHA256 ZIP |
|---|---|---|
| LAND PASS #680 | 40181415364 / 12593429251 | `fda4b50ef668c9295b15e7cb3c916dcf29a55c2e52c8d405edb813e9097dcc47` |
| LAND FAIL ancien #686 | 40181830007 / 12594851352 | `c86dc896ffa8c605568b5dfac7ad86f070d4a49f44f08eef64160f93024b5178` |
| #698 ancien HEAD PASS | 40235655559 / 12615475360 | `3b9ea3bc867a1c226f80e02f4403674f391cb22ea51408c02398d4a7fd91c250` |
| #698 Ready FAIL | 40238386434 / 12615774377 | `6e71e2b711c03a1f6f2851a5683c4d8ca9f8303f618869bd00b05c76d4889eb0` |

```sh
python3 experiments/runtime-contact-causal-audit/analyze.py
# Ou, pour vérifier des copies téléchargées indépendamment :
python3 experiments/runtime-contact-causal-audit/analyze.py \
  --pass-zip /absolute/path/12593429251.zip \
  --fail-zip /absolute/path/12594851352.zip \
  --environment-pass-zip /absolute/path/12615475360.zip \
  --environment-fail-zip /absolute/path/12615774377.zip
```

Python 3 et gcc suffisent. Le script compile dans un répertoire temporaire le
vrai `controllers/crazyflie_square/pid_controller.c` blob
`2803b7d2f5a1189717712bf7c826b45cc171d201`. Ce blob a été relu identique
sur les HEADs #686 `14c45d0...`, #698 `895e75d...` et son ancien `2b4415e...`.
Les deux premiers ZIP contiennent le même C runtime original
`a3c35b...` et instrumenté `e6c3ce...`.
Le rejeu utilise les échantillons consécutifs pour reconstruire les erreurs
précédentes, puis appelle les fonctions C horizontale et d'attitude. Il teste
la composante de mixage tangage, qui élimine le terme commun d'altitude.
Il ne prétend pas reconstituer l'intégrateur vertical ou les vitesses internes
des rotors. Dans cette fenêtre, Y/roulis/lacet sont nuls à la précision des
traces ; les commandes sont positives avant application des signes et ne
saturent pas. Le résidu maximal sur dix points est inférieur à `9.2e-8`.

Sources Webots primaires lues à la révision R2025a exacte
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b` :

- [Crazyflie.proto](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto) : cylindre de collision rayon 0,05 m, hauteur 0,03 m, masse 0,05 kg ; les hélices et le deck visuel ne sont pas des pieds de collision distincts dans ce modèle.
- [Floor.proto](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/projects/objects/floors/protos/Floor.proto) : `boundingObject Plane`.
- [collision_cylinder_plane.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/ode/ode/src/collision_cylinder_plane.cpp) : branche quasi parallèle `sin²(angle)<0.001`, quatre points cardinaux de chaque disque, point retenu seulement si sa profondeur est strictement positive.
- [WbMotor.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbMotor.cpp) et [WbPropeller.cpp](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbPropeller.cpp) : consigne, vitesse interne et poussée sont des grandeurs différentes.

Ce sont les sources épinglées, pas une attestation rétrospective de tous les
octets chargés par chaque processus. L'accord géométrique est testé contre les
points natifs ; le script Python spécialise l'algorithme, il ne compile pas ODE.

## 1. La géométrie explique le changement de nombre de contacts

Pour le disque inférieur incliné de tangage theta, son centre est
`(x - h sin(theta), y, z - h cos(theta))`, avec `h=0.015`.
Les quatre hauteurs testées sont `q-r sin(theta)`, `q+r sin(theta)`, `q`, `q`,
où `q=z-h cos(theta)` et `r=0.05`. Chaque hauteur négative donne un contact.
La comparaison s'effectue dans la fenêtre de roulis/lacet nuls des traces.

| Même temps simulé 12,448 s | PASS #680 | FAIL #686 |
|---|---:|---:|
| Centre Z (m) | 0,015205993 | 0,015019625 |
| Tangage (rad) | -0,000503304 | -0,000503311 |
| Hauteur du point le plus bas | +180,829 µm | **-5,539 µm** |
| Contacts prédits / observés | 0 / 0 | **1 / 1** |

Le contact unique prédit du FAIL est `(0.125383193, 0, -0.000005539)` m,
exactement celui archivé à l'arrondi près. Son bras horizontal par rapport au
centre est environ -50 mm. Le nombre de contacts n'est donc pas ici une preuve
que le solveur aurait choisi aléatoirement des contacts pour une pose identique :
les poses sont différentes et l'algorithme déterministe les distingue.

Au pas suivant, le PASS arrive plus profondément : centre Z=-4,202 mm,
quatre points entre -19,227 et -19,178 mm. Les coordonnées des huit états
quasi parallèles des deux archives sont retrouvées à moins de `5.7e-10 m`.
Le même calcul retrouve également les premiers contacts des deux archives
#698 (quatre au PASS, un au FAIL), sans nouveau réglage de géométrie.

**Intervention réellement calculée, au seul niveau du détecteur :** à pose FAIL
12,448 s, toutes autres coordonnées fixées, `delta Z=+186.368 µm` donne zéro
contact, `delta Z=-46 µm` donne quatre contacts. La bande de q permettant un
unique contact n'a ici qu'environ **25,166 µm** de largeur. Ces décalages sont
des contre-factuels hors ligne ; ils ne sont ni une modification du monde, ni
une preuve que les trajectoires modifiées réussiraient.

À 0,62 m/s, un pas de 32 ms représente près de 20 mm de descente. Cela motive
une hypothèse de sensibilité à la phase d'impact et à la discrétisation.
Cela ne prouve ni un défaut ODE, ni que réduire le pas corrigerait le produit.
Le PASS pénètre davantage avant la résolution observée : « plus de pénétration
implique nécessairement ce FAIL » est déjà une explication insuffisante.

## 2. Le PID réagit très fortement ; sa responsabilité dynamique reste ouverte

Avec désir de vitesse nul et dt=0,032 s, la consigne de tangage horizontale vaut
`-2 constrain(vx,-1,1) - 0.5*(vx-vx_precedent)/dt`.
Le contrôleur d'attitude dérive ensuite son erreur de tangage. La cascade
contient donc une seconde différence de vitesse, avec coefficient local
`kd_att_rp*kd_vel_xy/dt² = 48.828125`, avant les saturations pertinentes.
Ce coefficient est une sensibilité du calcul, pas une borne de stabilité
de l'ensemble robot/contact/moteurs.

| FAIL #686 | 12,448 s | 12,480 s | 12,512 s |
|---|---:|---:|---:|
| vx (m/s) | +0,002012 | +0,200691 | -0,073807 |
| tangage observé (rad) | -0,000503 | +0,420593 | +0,209272 |
| tangage désiré rejoué (rad) | -0,001469 | **-3,505740** | **+4,436647** |
| mixage tangage rejoué | -0,000879 | **+12,766771** | **-25,980337** |

Ce rejeu explique arithmétiquement les écarts de commandes moteur déjà archivés
25,533543 et 51,960674. Les désirs extrêmes ne sont pas des attitudes atteintes.
La grosse consigne est calculée après lecture de l'état déjà perturbé ; elle
ne peut expliquer rétroactivement cet état. Une amplification ultérieure est
plausible, mais nécessite l'évolution réelle des forces et une intervention.

R2025a limite ici la variation de vitesse interne à 30 rad/s², soit **0,96 rad/s
par pas de 32 ms**, sous les paramètres du PROTO. L'écart entre vitesses de
deux rotors peut changer d'au plus 1,92 rad/s en un tel pas, pas instantanément
de 25 ou 52 comme les consignes. Cette borne de variation ne donne pas leurs
vitesses absolues, leurs forces ni leur asymétrie avant l'impact.
Leur état interne manque dans ces archives LAND : assimiler directement
commandes et poussées amplifierait artificiellement l'explication PID.

## 3. Confrontation des hypothèses

| Hypothèse | Conclusion appuyée / falsificateur manquant |
|---|---|
| Contact sol | Le cylindre sur plan explique quantitativement la topologie 0/1/4. Un contact excentré et la rotation suivante sont compatibles avec une impulsion de contact ; l'impulsion n'a pas été mesurée. Tester le premier pas avec forces moteurs fixées. |
| Commandes moteurs | Elles ne divergent fortement qu'après le premier contact. Courants internes inconnus : exclure seulement leur variation *nouvellement commandée* comme cause rétroactive ; conserver l'hypothèse d'un état moteur antérieur. |
| PID | Réponse calculatoire démontrée ; amplification de trajectoire non démontrée. Comparer retour PID actif et commandes gelées à état moteur initial identique. |
| Initialisation / phase | Des écarts submillimétriques modifient les contacts. La cause amont de l'écart Z (timing, intégrateur vertical, historique moteur, initialisation) reste inconnue ; ne pas appeler ces états identiques. |
| Environnement | Les manifestes PASS/FAIL #698 identiques, déjà documentés sur #637, réduisent l'explication par leurs valeurs mesurées. Versions effectives ODE/Qt, PROTO résolus et états internes ne sont pas attestés ; aucune attribution au noyau/Chrome. |
| Non-déterminisme | Aucune comparaison à état natif complet identique n'existe. La sensibilité déterministe du détecteur est une explication plus précise du nombre de contacts ; elle ne démontre pas la source des variations amont. |

Le manifeste #698 reste une observation de paquets : `libode8`/`libqt6core6`
UNPROVEN ne signifie ni absence de solveur ni différence entre les deux runs.
Les bibliothèques de Webots peuvent être embarquées ; `dpkg-query` n'atteste
pas les objets réellement chargés. Ne pas dupliquer cette collecte ; réutiliser
#698 et qualifier les identités chargées seulement si l'expérience en dépend.

## 4. RESET : une autre obligation, pas une conclusion transférée depuis LAND

Le ZIP FAIL #671 `12496178609` a également été vérifié : SHA256
`a1892f8bafda36d1ceb556a7b164e041ababa30a6189fc2ce34f90b39e4b7436`,
21 membres CRC valides, manifeste autonome 15/15.
Le septième RESET remet bien le corps à l'identité, Z=0,015 m et vitesse native
6D nulle à 497,344 s. À 497,376 s, norme de vitesse angulaire ~39,65 rad/s,
deux contacts profonds : la défaillance est réellement physique, pas uniquement
une différence finie GPS. Les données sont post-pas et ne datent pas l'impulsion.
`CMD_RESET` arrête les consignes et contourne le calcul PID à chaque pas :
**une réaction PID active n'est pas une cause commune démontrable de ces deux
fenêtres RESET et LAND**. Les rotors peuvent cependant conserver leur vitesse
interne après le body reset, mécanisme déjà démontré ailleurs sous #637.
Leurs états dans CE FAIL restent inconnus. Les corps remis à zéro ne constituent
pas un état moteur/solveur complet identique. Aucun ajout de délai, changement
d'oracle ou `loadState` moteur n'est justifié comme correction historique.

## 5. Expérience minimale suivante, arrêt et verdicts explicites

Ne pas répéter une cohorte entière pour obtenir un vert. Le premier test utile
est un **micro-essai causal natif de 32 ms**, hors produit, dans le moteur
R2025a exact : cylindre/masse/inertie et plan réels, état entrant mesuré du FAIL
12,448 s, mêmes vitesses 6D et orientation, matériaux/ERP/CFM/pas retenus.
Trois cas prédéfinis changent uniquement Z : `0`, `+186.368 µm`, `-46 µm`.
Utiliser des forces externes identiques et explicitement fixées, sans retour PID
ni état caché de moteur ; c'est une fixture de suffisance mécanique,
**pas une reproduction intégrale du vol historique**. Archiver pose/vitesse
avant/après, points/normales/profondeurs et impulsions par joint si accessibles.
Vérifier le vrai tenseur d'inertie du corps ; ne pas lui substituer un moteur
ou une géométrie différents sans le déclarer.

- Si le cas à un point développe une impulsion angulaire forte alors que les
  cas 0/4 points ne la développent pas, la topologie/phase est causalement
  discriminée dans cette fixture sans PID. Cela ne prouve pas encore l'effet
  dans le robot motorisé historique.
- Si le résultat diffère, conserver la réfutation : état de contraintes,
  rotor/force, configuration ou géométrie effective manquent au modèle réduit.
  Ne pas remplacer la fixture ou ses seuils après avoir vu le résultat.
- Ensuite seulement, pour mesurer l'amplification, opposer deux continuations
  motorisées explicitement préparées à mêmes vitesses internes et même état
  entrant, l'une avec PID inchangé, l'autre avec commandes gelées avant contact.
  Geler une consigne ne gèle pas automatiquement une vitesse réelle : enregistrer
  `currentVelocity/currentThrust/currentTorque` ou les forces réellement imposées.
  Réutiliser le support natif d'actionneurs déjà conservé dans #637.

Le passage à un pas physique plus court, si ce premier test le justifie, exige
de garder séparément la période du contrôleur à 32 ms ; la réduire aussi
modifierait simultanément contact, PID et communication et ne départagerait
pas les causes. Aucun changement de pas produit n'est proposé ici.

Cette exécution a réalisé les relectures, calculs et compilation/rejeu C décrits.
Elle n'a exécuté aucun Webots : Webots et Docker ne sont pas disponibles dans
son environnement. La fixture native et les continuations sont **non exécutées**.
Si un correctif devient démontrable, il faudra un petit candidat V5 Ready,
CI canonique exacte et validation indépendante conservant tous les positifs,
négatifs, fraîcheur RESET 250 ms / 5 s, LAND et règle 210 s.
Les CI rouges actuelles #686/#698 et leurs NO_GO restent applicables.
