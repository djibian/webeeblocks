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
