# LAND forcé #655 — refus localisé, cause physique non démontrée

21 octobre 2026. **Échec natif de LAND confirmé ; sous-prédicat exact du refus
UNPROVEN ; garde d'attitude fortement étayée ; aucune réparation produit justifiée.**

Cette analyse réutilise les octets existants, sans acquisition native, sans
changer #655 ou #638. Elle ne revendique aucune trajectoire corrigée, CI Gate,
revue indépendante de son propre ajout, restauration de main ou acceptation
pédagogique. Aucun vol réel.

## Provenance et vérification exécutée

Référence #655 ouverte Draft : `6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7`.
Archive `experiments/grand-prix-no-wall/evidence/negative-deadline.tar.xz`,
8 562 316 octets, SHA-256
`9be0c27869d1d3ce637f06373969ef86c7f316f53a41979c71113cae493e661c`.
Les **dix membres du manifeste original ont été vérifiés**, sans divergence.
Le CSV complet contient 139 755 observations, jusqu'à 1118,040 s ; son empreinte
et sa taille sont dans `sources.json`. Cette vérification ne répare ni ne
transfère les autres archives partielles de #655.

`data/` conserve les dix petits fichiers originaux, le manifeste original,
le transcript du runner et un **extrait contigu**, avec en-tête, de
`native_trace.csv` entre 225 et 230 s. Les offsets d'octets exacts et le dernier
échantillon du fichier complet sont dans `sources.json` ; `sha256.json` couvre
les fichiers retenus. Le manifeste original concerne le CSV complet, pas cet
extrait. L'archive originale reste référencée au HEAD exact ci-dessus.

```sh
python3 experiments/grand-prix-forced-land-audit/verify.py
python3 experiments/grand-prix-forced-land-audit/verify.py --archive /chemin/negative-deadline.tar.xz
```

Les deux modes ont été exécutés ; le second recoupe tous les membres et
l'extrait au niveau des octets. `analysis.json` conserve son résultat.
Les calculs portent sur la matrice Supervisor :
`pitch=asin(clamp(-r6,-1,1))`, `roll=atan2(r7,r8)`.
**Ce ne sont pas des mesures IMU archivées.** Les 626 observations de l'extrait
sont finies et espacées de 8 ms ; cela ne prouve pas la validité de tous les
échantillons consommés par le contrôleur.

Le générateur a été exécuté dans un worktree détaché de #655 : son Runtime
composé SHA-256 `c6b47c499dfe482f438432e9ed9a36d58611080f644644cd2ad42c18b00a3a99`
et le Runtime partagé `8cf1a492e9f3417c5a8ad90005ddd35e373d1af8a3fd18f7699799c3e16d76d9`
correspondent **exactement aux empreintes du runner.log original**. C'est un
recoupement de sources générées ; aucun binaire original n'est présent dans
cette archive et aucune attestation rétroactive de ses octets n'est inventée.

## Condition exacte de refus et limites

Le message d'erreur générique ne distingue pas tous les chemins. Dans le
**Runtime composé réellement référencé par #655**, la garde fatale est :

```c
command != CMD_RESET &&
((!gp_control_sample && (airborne || command != CMD_IDLE)) ||
 (command != CMD_IDLE &&
  (fabs(actual.roll) > 1.2 || fabs(actual.pitch) > 1.2 ||
   now - action_start > ACTION_TIMEOUT)))
```

Il existe donc une **troisième possibilité**, omise par une lecture du seul
Runtime partagé : échantillon de contrôle invalide. `gp_control_sample`
exige finitude de temps, dt, GPS, vitesses, attitude et trois axes gyro,
avec `dt <= 0.032001`. L'adaptateur remplace une attitude invalide par des NaN.
Un tel refus imprime aussi « unsafe attitude or action timeout » ; le libellé
ne suffit pas à exclure une perte de mesure.

Il existe également un refus de requête entrante pour échantillon invalide,
mais l'ID indépendant `2147483646` est assigné par la composition, et le
`FATAL` consécutif identifie ici la garde fatale de commande active. Il n'y a
aucune requête Node avec cet ID dans les événements conservés.

À l'échéance, le code fait explicitement `action_start=now` avec
`command=CMD_LAND`. Le délai de l'ancien MOVE n'est donc pas hérité.
`ACTION_TIMEOUT` vaut 25 s et la comparaison est **strictement >** : le
timeout du LAND ne devient éligible qu'après 251,288 s absolues, pas à 210 s
de mission ni à 227,624 s. Si le contrôleur consomme normalement l'attitude
physique observée, il doit rencontrer sa garde d'attitude bien avant ce délai.

**Conclusion : garde d'attitude très cohérente avec la trace, timeout seul
non soutenu. Sous-prédicat effectivement déclenché et instant exact encore
inconnus.** Ni le défaut de finitude/échantillonnage ni un horodatage tardif
du refus ne peuvent être éliminés avec un log non horodaté et sans entrées
effectivement consommées. Ne pas transformer cette inférence en mesure.

Le PROTO officiel Crazyflie et `WbInertialUnit.cpp` ont été consultés au SHA
assets `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b` : l'IMU est attachée au corps,
le calcul part de sa matrice, puis transmet un quaternion lors du refresh.
Cela rend la reconstruction physiquement pertinente, mais ne fournit ni le
quaternion effectivement reçu, ni sa phase de rafraîchissement, ni les RPY
consommés par cette exécution. L'activation des capteurs est à 32 ms ; le
Supervisor observe à 8 ms. Aucun temps exact de garde n'est déduit en arrondissant
simplement 227,624 s à un multiple de 32 ms.

## Chronologie physique et Runtime

Tous les temps du tableau sont **absolus Webots**. La mission commence à
16,288 s. Le négatif distinct décolle à 0,40 m, monte de 0,40 m puis oscille
avec des MOVE avant/arrière ; il n'est pas le témoin positif expert de 389 blocs.

| Temps | Observation conservée | Portée |
| --- | --- | --- |
| 226,288 s | interruption du MOVE 59 par TIME_LIMIT ; LAND indépendant, ID 2147483646 ; x=0,110812 m, z=0,777601 m, VX=+0,225575 m/s | exactement 210 000 ms de mission ; LAND commence en mouvement, à altitude haute |
| 226,800 s | z=0,620823 m, VX=+0,492779 m/s, VZ=−0,782180 m/s | augmentation du mouvement horizontal pendant la descente, bien avant le rebond près du sol |
| 227,032 s | z=0,403184 m, pitch reconstruit=−0,229213 rad | oscillation d'assiette déjà présente en altitude ; aucun dépassement de 1,2 rad à ce stade |
| 227,368 s | premier z<0,04 m ; VZ=−1,048018 m/s | approche du sol nettement plus rapide que les ~−0,45 m/s de #638 |
| 227,384 s | x=0,387913 m, z=0,019227 m, VZ=−1,037470 m/s | déplacement XY de 0,277102 m depuis l'ordre ; pas de temps de premier contact archivé |
| 227,392 s | z=0,014510 m, VX=−0,152030 m/s, pitch=−0,085743 rad | discontinuité de mouvement près du sol, compatible avec un impact |
| 227,400 s | VZ=+0,293968 m/s, z=0,016862 m | inversion verticale/rebond ; ne mesure pas une force de contact |
| 227,616 → 227,624 s | pitch=1,196904 → 1,229044 rad | premier dépassement reconstruit de 1,2 rad, 1,336 s après LAND ; VX=1,344281 m/s |
| 228,000 s | roll≈pi, x=1,008278 m | le corps s'est retourné ; les angles Euler changent de branche |
| 1118,040 s | x≈1,029045 m ; matrice≈diag(−1,1,−1), vitesses≈0 | état final retourné, aucune pose droite contrôlée |

Le log de vol place après l'ordre `RESPONSE 2147483646 ERR UNSAFE_OR_TIMEOUT`,
puis `FATAL unsafe attitude or action timeout`. Il ne les horodate pas.
Il ne contient ni `TRACE LAND stop=1`, ni `GP_U_LAND_CONTROL`.
Les requêtes tardives COMPLETE/FAILURE/MOVE/STOP sont refusées TIME_LIMIT ;
OUTCOME reste not-achieved ; **aucun RESET n'a été envoyé**.

## Consignes, actionneurs, contact : ce qui est prouvé

Le protocole indépendant remplace la commande active, révoque l'horloge du
programme, fixe target_z à origin_z et remet sa fenêtre de stabilité à zéro.
Il initialise aussi target_x/y/yaw à l'état courant. Cependant la branche
LAND ordinaire n'utilise pas leur maintien de position : elle fixe l'altitude
au sol et conserve les consignes horizontales et de lacet initialisées à zéro
pour ce pas. Le vrai PID de vitesse reste ensuite appelé. Une vitesse désirée
nulle n'est pas une assiette désirée nulle : le PID génère cette dernière.

La consigne verticale est un **échelon vers origin_z**, pas une rampe de
descente. L'historique PID n'est pas réinitialisé à l'entrée du LAND, forcé ou
ordinaire. Au passage à la deadline, `gp_u_next_step` peut raccourcir le pas
pour respecter exactement la limite ; 210 000 ms n'est pas divisible par
32 ms. Cette transition d'échantillonnage et la transition MOVE→LAND méritent
une mesure, mais ne constituent pas une cause démontrée de l'incident.

Le zéro moteur est appelé **après** l'émission de l'erreur et du FATAL dans
la garde ; celle-ci verrouille ensuite le failsafe, révoque l'horloge et
met la commande IDLE/airborne=0. Ces affectations sont administratives :
elles ne signifient pas que le drone est physiquement posé. L'autorité GP
conserve justement une confirmation de pose indépendante et fail-closed.
Les appels moteur ne sont pas horodatés dans l'archive. Impossible de mesurer
leur arrêt, les cibles intermédiaires, la vitesse effective des rotors, la
poussée ou l'effet du zéro sur le retournement. Un ordre zéro n'est pas une
extinction instantanée prouvée. Ne pas reconstruire une force depuis des
consignes, ni depuis le seul slowHelix.

Les points/identités/forces de contact sont absents du CSV #655. Le rebond et
les changements de vitesse à ~227,392–227,400 s sont compatibles avec un impact
au sol ; ils ne prouvent ni l'instant du premier toucher ni la topologie ou
l'impulsion initiale. Le mouvement horizontal a déjà augmenté en altitude,
ce qui interdit d'attribuer toute l'excursion au seul contact terminal.

## Comparaison séparée avec #638

Les treize commentaires #638, les reviews, le rapport de rejeu
`a7653962129d64234e1ecb7ad55467fa97d5dede` et le rapport d'arrêt
`554202bded6950af4ac2886bc0d778b29932821d` ont été lus.
Le ZIP historique seed 14 (artefact 12212133156) a été téléchargé : SHA-256
`71a4430fb849d06774521ee602126292741d91f5706d79db2c1092a2c48d36ae`, CRC
et ses huit membres manifestés du scénario s14 vérifiés. Le vérificateur
du vrai PID a également été exécuté sur les extraits retenus du commit a765396 :
285 pas, erreur maximale ~2,17e−7. Cette exécution ne prétend pas avoir
revérifié les ZIP complets des trois réussites ni relancé leurs simulations.

| Cas | Signature | Conclusion préservée |
| --- | --- | --- |
| wrong-landing seed 3 historique | arrivée près de la cible, dérive près du sol, erreur finale ~18,27 cm ; pas de trace moteur ancienne | échec réel ; completion_ms est un marqueur observé, pas un temps d'ACK mesuré |
| envelope-contact seed 14 | approche ~0,39 m, XY quasi nulle, VZ≈−0,453 m/s ; contacts 1 puis 3 ; impulsion et roulis ; excursion vers +y ; stop/OK après refus de l'oracle | défaut réel de LAND au contact, sans cause physique suffisante établie |
| rejeu PID seed 14 | +37° puis −90° demandés après impact ; commandes/mixage reproduits par le vrai C | lien mesures→commandes établi ; amplification physique par dérivée non démontrée |
| réussites natives #638 | quatre contacts d'emblée, VZ comparable, faible mouvement horizontal ; présence ou absence de tuiles | un rebond et −0,45 m/s ne suffisent pas à prédire l'échec ; damier pas systématiquement fautif |
| A1/B1/B2/A2 arrêté | seul A1 exécuté et réussi ; NotADirectoryError ; 2,008 s post-stop au lieu de 3 s ; slowHelix seul invalide à la transition 50 rad/s | aucun B, aucun correctif ni répétition autorisés par ces données ; campagne définitivement arrêtée |
| LAND forcé #655 | début à ~0,78 m et VX~0,226 m/s ; augmentation de VX/oscillation avant rebond ; VZ~−1,04 m/s près du sol ; tangage, puis retournement et refus sans ACK | autre état d'entrée et autre signature ; aucune attribution automatique au mécanisme de dérivée #638 |

Le PID C est identique entre main et #655. Le Runtime partagé diffère de main
par des diagnostics RESET ; aucune équivalence globale des builds n'est
prétendue. La composition #655 n'embarque pas les diagnostics LAND ajoutés
dans #638. Le lien physique commun reste **inconnu**.

## A / B / C / D et correction

- **A — failsafe :** son refus est compatible avec une situation réellement
  dangereuse, positivement observée par le Supervisor. Aucun faux positif de
  la garde, bug de seuil ou besoin de l'affaiblir n'est démontré. Le sous-prédicat
  consommé reste à mesurer. Le failsafe ne promet pas de redresser un véhicule.
- **B — comportement LAND :** le témoin montre un échec effectif d'atterrissage
  contrôlé, pas une simple réponse mal nommée. Sa cause peut impliquer la
  transition de consigne, le freinage, la descente, le contact et les actionneurs.
  Aucune de ces causes n'est isolée en boucle fermée.
- **C — protocole indépendant :** échéance, interruption, nouvel action_start,
  branche LAND et verrouillage tardif sont conformes aux observations/source.
  L'efficacité physique de MOVE→LAND dans cet état n'est pas qualifiée. Aucun
  défaut de chronologie/protocole n'est démontré ou exclu par principe.
- **D — support :** le runner refuse correctement la fin LAND absente.
  L'archive de ce cas est intègre ; une modification de manifeste ou d'oracle
  ne le réparerait pas. Le manque de télémétrie de garde/IMU/actionneurs est une
  limite de preuve, distincte des anomalies de capture des autres cas.

**Aucune correction produit n'est proposée.** Pas de retouche de gain, seuil,
timeout RESET, 210 s, critère de pose, cible, oracle ou programme Blockly.
Une correction minimale à ce stade serait un diagnostic expérimental
horodatant les conditions réellement évaluées, sans changer leur expression
ni la réaction fail-closed. **Ce diagnostic est préparé par `instrument.py`** :
il refuse une source composée autre que celle exacte de #655, écrit un nouveau
fichier sans écraser un existant et ne lance aucun processus natif. Il ajoute
les sous-prédicats et données de garde, les valeurs invalides avant normalisation,
les entrées/historiques PID, les sorties/consignes signées après clamps, et le
temps des appels de mise à zéro. L'entrée/sortie PID couvre LAND et la dernière
seconde pré-deadline via la seule lecture de l'horloge du programme. Les étiquettes
LAND_INPUT/OUTPUT incluent `command` pour distinguer cette phase d'approche.

La source instrumentée obtenue a SHA-256
`24de42df52a769df7239ea5350e9f4a8618bc9663182e5af0053fef9775d2d33`.
`verify_instrumentation.py` compile le **vrai Runtime composé**, broker/hook et
fixture de contrôle de #655, avec/sans instrumentation. **Neuf comparaisons
exécutées** conservent exactement stdout (dont chaque appel moteur capturé),
réponses/événements, code de sortie et stderr hors nouvelles traces :
nominal, LAND réussi, attitude au deadline/en amont, timeout de commande et
LAND, mesure invalide permanente/transitoire, et garde de tangage distincte.
Le PID de cette fixture est un substitut déterministe : des puissances non
nulles injectées `[-2,1000,37,42]` exercent les clamps et signes
`[-0,600,-37,42]`. Il ne simule pas la dynamique du vrai PID ou du drone.
Les traces différencient effectivement attitude, mesure invalide et timeout ;
les valeurs brutes `inf` ne sont pas perdues derrière la normalisation NaN.
Le CLI refuse également une source altérée et l'écrasement d'un fichier.
Résultats conservés dans `instrumentation-validation.log`.

```sh
python3 experiments/grand-prix-forced-land-audit/verify_instrumentation.py /chemin/checkout-exact-655
python3 experiments/grand-prix-forced-land-audit/instrument.py /chemin/runtime_u.c /nouveau/chemin/runtime_observed.c
```

Ces vérifications sont **hors Webots**, sans preuve native de coût temporel,
contacts, mouvement corrigé ou exactitude des mesures effectives. Le journal
stderr n'est pas encore un journal indépendant à clôture attestée, et le
diagnostic de contact/actionneurs reste à composer. Le support d'archivage
#656 est actuellement Draft `ff0d91b29f80ee320ddf3a6bbe47ceb6033410b0`, sans
revue indépendante recensée : sa simple existence ne satisfait pas les gates
du protocole. Aucun lancement n'est donc justifié par ces seuls tests.
Le protocole suivant est dans `PROTOCOL.md` ; il ne reprend pas l'ancien A/B.

## Conditions restantes pour le négatif de deadline

1. Attribuer le refus sur des entrées réellement consommées avec une capture
   fiable ; distinguer transition en vol, impact et réponse des actionneurs.
2. Si une cause produit est isolée, opposer une intervention minimale à une
   référence exerçant la panne. Un contrôle sans incident rend une comparaison
   non concluante sur la correction ; ne pas multiplier les succès.
3. Démontrer ordre à exactement 210 s, refus tardifs et échec irréversible,
   **plus** descente/pose droite stable et fin LAND native, sans chute dangereuse.
   La disparition de l'erreur seule ne suffit pas. Conserver les négatifs.
4. Revalider le monde final convergé sur un nouveau candidat exact, y compris
   le domaine de LAND à toute position et les autres négatifs #655 non exécutés.
   Pas de transfert automatique des réussites isolées ou d'un monde antérieur.
5. Santé de main restaurée avant intégration ordinaire ; candidat produit
   isolé, Ready stable, CI Gate canonique exacte et revue indépendante résolvant
   les réfutations applicables. Le checkpoint pédagogique reste séparé.

## État GitHub

Main observé `b478f9dd1854d83345abe13ed20fcf7baeffaca5`, contrat V5/vision/roadmap
chargés, blobs `c1b0078103507e7b0132af948b34a5cbd7b5950a`,
`df0b3b8591562f13f879db5c3f5ab78286b84cde`,
`e8c4e246df15f223728f94743c958374176fccac`.
#638 ouverte Draft à `149c0b61b48f335eb4cb925113ccc03afce80cca` : succès Draft
39311714756, NO_GO historique 5574571532 non résolu. #655 ouverte Draft à
`6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7`, aucun workflow PR de ce HEAD et
aucune revue recensés lors de la reconstruction. #655 reste empilée sur
#647 `4e0e6b21e43c68c19049430b46751c41ccf6ce28` puis #641
`c965bdc1cb39b6ede1f603a875a51a0b5d9cf05e`.

#637 reste ouvert et main non restauré : aucune intégration ordinaire.
Les candidats existants sont préservés. Cette branche conserve une analyse,
pas un correctif intégrable ou une nouvelle autorité. Aucune activité 2–7,
notification, TEST_REQUIRED, acceptation pédagogique ou action matérielle.
