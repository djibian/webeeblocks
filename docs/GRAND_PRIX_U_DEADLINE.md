# Autorité d'échéance U : composant borné (#587)

Correction du NO_GO `0a64e7aea8170efe11fd40deb72fb79866126dc1` :
le runtime partagé peut terminer `UNSAFE_OR_TIMEOUT` en `IDLE/airborne=0`
à 0,80 m du sol. Cet état administratif ne prouve aucune pose. La composition
exige maintenant 0,5 s d'observations natives continues : altitude à moins de
5 cm du niveau initial (des deux côtés), vitesse horizontale < 0,12 m/s,
verticale < 0,15 m/s, roll/pitch à moins de 2° de la pose initiale et chaque
axe gyro < 0,10 rad/s. Temps, GPS, attitude, gyro et vitesses doivent tous être
finis ; une perte ou un intervalle > 32 ms annule la fenêtre. Ces critères
reprennent les tolérances du runtime ; ce sont des critères de simulation sur
sol uniforme, jamais des marges qualifiées pour le réel.

La preuve n'est disponible qu'en IDLE sans vol administratif, après la fenêtre
observée. Elle est réévaluée avant chaque lecture du broker et révoquée au
TAKEOFF, au RESET et à toute observation invalide. RESET est refusé également
après une terminaison anormale avant 210 s, avant tout bookkeeping de tentative.
Une pose effectivement observée peut permettre la récupération après erreur ;
le simple arrêt des moteurs ne la permet jamais. La branche d'erreur d'attitude,
l'échec irréversible et le déclencheur LAND unique à 210000 ms sont conservés.

`test_grand_prix_u_pose.py` compile le C complet généré, le broker complet et
le hook, avec wrappers aux seules frontières Webots. Les 14 cas couvrent
erreur à l'échéance, erreur/timeout avant échéance, timeout du LAND, RESET
en file, commandes/résultat tardifs, GPS/IMU/gyro non finis, rebond, mouvement,
pose sous le sol, perte de confirmation puis récupération et poses positives.
Les mêmes cas sont exécutés dans R2025a par le probe composé : temps et capteurs
natifs, poses/attitudes imposées par Supervisor, pertes de mesures injectées
aux getters, vrais PID et broker de simulation sans dialogue Qt.
Le monde de probe a une gravité nulle pour isoler cette provenance de pose.
La pose native initiale correspond à la pose de démarrage imposée. Après
RESET, le Supervisor maintient la pose réellement demandée par le runtime
pendant les observations de stabilité ; aucune dérive dynamique n'est testée.
Les wrappers enregistrent uniquement les téléportations demandées par RESET.
Ce test prouve le filtrage de la composition, pas une descente dynamique.
Un enregistrement frais n'est écrit qu'après toutes les assertions.

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
