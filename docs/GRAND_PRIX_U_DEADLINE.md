# Autorité d'échéance U : composant borné (#587)

Le hook natif indépendant lie le temps Webots à l'admission TAKEOFF et à
l'identité de tentative. Le monde doit avoir un pas de base de 8 ms ; le
contrôle partagé reste à 32 ms, avec un dernier pas de 16 ms pour atteindre
exactement 210000 ms. À l'échéance, la composition révoque l'horloge du
programme, répond TIME_LIMIT à sa commande en attente, écrit l'échec et
active CMD_LAND sur place. Aucun code partagé, backend physique ou activité
intermédiaire n'est modifié. Les ancres de compilation refusent si les
sources partagées changent.

Le filtrage précède le bookkeeping du broker : MOVE, LAND, STOP, COMPLETE,
FAILURE et RESET tardifs sont refusés avant la pose native. OUTCOME reste
lisible ; RESET devient admissible après pose et prépare une nouvelle
identité. Un ancien résultat réussi d'une autre tentative ne peut désarmer
l'échéance. La réussite déjà observée avant échéance reste terminale.

Claim de cet incrément : code d'autorité/composition et entrelacements de
ses canaux contrôlés, pas une activité ni une qualification de trajectoire.
Le préparateur s'exécute aussi sans générateur U ; les mondes et l'oracle
restent dans les incréments géométrie #599, oracle #600 et composition #591.

`python3 tools/ci/test_grand_prix_simulation_time.py` conserve les cinq tests
historiques et compile le vrai hook C++ contre des canaux Webots contrôlés :
209999/210000 ms, réduction du dernier pas, émission unique du déclencheur,
commandes tardives, RESET avant/après pose, nouvelle tentative, succès ancien
et absence d'évaluateur. Ce test ne simule pas les forces du drone. Le test
fait partie du harness Runtime existant, sans nouvelle exemption ou workflow.

Les probes natifs dans #591 produisent séparément interruption/LAND à
210,000 s au départ et dans un H ; ils ne transfèrent aucun GO au présent
composant. La campagne et ses traces exactes doivent être examinées sur le
HEAD concerné. Cette exécution auteure ne donne aucun GO et ne fusionne pas.
Aucun vol réel ou checkpoint matériel n'est proposé.

Réparation du NO_GO `770356638d808b1d6df0aea90bcbe1fdd9507da7` :
le test entier `elapsed_ms >= 210000` précède l'acquisition d'un nouveau
succès. Seul un succès déjà observé avant la limite avec pose native confirmée
reste terminal. Le canal OUTCOME actuel ne prouve aucun instant antérieur de
validation : une première observation à/après expiration est refusée même si
l'évaluateur a écrit entre deux ticks. Aucun horodatage fourni par le programme
ne peut antidater la réussite. Cette règle conservatrice reste explicite ;
une future amélioration de livraison demanderait une preuve causale distincte.

Autre contre-exemple recherché : un producteur écrivant `achieved` après le
timeout. L'autorité réaffirme l'échec à chaque tick expiré et avant le traitement
OUTCOME du broker, tout en ne déclenchant LAND qu'une fois. Les tests compilés
conservent les anciennes assertions et ajoutent première observation à
209999/210000/210001 ms, livraison entre ticks, succès non posé, succès déjà
confirmé, écrasement tardif et 10000 origines d'horloge à pas natif 8 ms.

Le job R2025a existant conserve toutes ses assertions de géométrie et exécute
en plus `run_grand_prix_u_deadline_native.py`. Il compile la composition de vol
courante et le vrai hook, puis éprouve cinq cas dans le vrai moteur : succès
observé à 209984 ms ; premier succès à 210000 ms ; résultat livré à 210008 ms ;
écriture à 209992 ms observée à 210000 ms ; absence de succès avec pose non
confirmée. Les canaux Supervisor, le temps Webots, le dernier pas de 16 ms,
le déclencheur unique à 210000 ms, le filtrage tardif et RESET sont contrôlés.
Les logs `deadline-*.log` et `deadline-build.log` rejoignent l'artefact existant
et son manifeste SHA-256. Une preuve manquante fait échouer le job.

Cette preuve native porte sur le temps et les champs, avec pose/outcome
contrôlés. Elle ne démontre pas une trajectoire ni une descente dynamique ;
les essais de mouvement/LAND dans des portiques appartiennent à la future
recomposition #591. Aucun fichier de #591 ni oracle #600 n'est modifié ici.

Le résultat natif du probe est écrit et fermé dans `deadline-*-native.txt`
**après toutes les assertions et avant** la demande de fermeture Webots.
Le runner exige le fichier frais exact ; les éventuels marqueurs stdout
doivent être cohérents. Les premiers probes ont exposé une perte de la fin
de stdout au shutdown (dernier tick visible 210016 ms, suivant et marqueur
final non drainés). Comme pour les preuves géométriques natives existantes,
stdout seul ne sert donc pas d'accusé de réception. Une assertion échouée
écrit un enregistrement d'échec et aucun fichier absent/ancien/erroné ne
peut être converti en PASS. Les diagnostics des deux runs défectueux sont
conservés dans leurs artefacts CI.
