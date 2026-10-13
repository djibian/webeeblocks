# Grand Prix U : composition expérimentale Draft #591

Décision applicable : tête de #587, contrat #588 intégré sur main
874318b5bb34644cf07d873eff8ba367777374ab. Cette version remplace la cible
produit à tours/points ; gp-v2/v3/v4, leurs sources, mondes, traces référencées
et contre-exemples restent des archives, jamais des PASS du parcours U.

## Composants indépendamment révisables

- #599 : géométrie gp-u-v1 et perception statique R2025a, Ready.
- #600 : oracle pur des trois côtés, franchissements, altitude et pose, Ready.
- #591 : composition Draft de ces candidats avec autorité native d'échéance,
  témoin sensoriel et fenêtre française. Cette composition ne remplace pas
  leurs revues ; elle doit être recomposée/requalifiée après leurs intégrations.
  Aucun GO de cette exécution auteure.

Géométrie à 2 m pour toutes les graines : 1–3 H, un maximum/côté ; aucun
obstacle bas, fermeture pleine largeur et arrivée 1,80 m ; bandes candidates
±0,55 m, seuil 0,60 m, rayon 0,09 m. Seules disposition et quantité de H
changent. Pose centre / gauche sud / droite nord pour 1/2/3 passages, sans
score ni classement. L'oracle refuse les passages incomplets/doublons,
raccourcis, contacts, altitude hors zone et mauvais lieu de pose.

## Temps et autorité native

210 000 ms n'est pas divisible par 32 ms. Le monde utilise 8 ms, mais le
contrôle et les capteurs conservent **32 ms** ; seul le dernier pas avant
l'échéance est raccourci (16 ms depuis une admission sur la grille 32 ms).
Ainsi, aucune tolérance temporelle ni soustraction de latence ne remplace
l'instant prescrit. Les anciennes limites PID, translation, lacet, attitude
et timeout d'action sont reprises du source partagé courant.

Une composition de compilation injecte des hooks bornés dans les sources de vol et de broker
**courant** du contrôleur partagé, sans modifier ce fichier, son binaire
produit verrouillé ou le backend physique. Chaque ancre doit apparaître une
fois ; un changement du source impose revalidation. Les SHA-256 du source
partagé et des fichiers générés sont imprimés. Pas de copie permanente du
Runtime ni de second interpréteur.

À l'admission TAKEOFF seulement, l'autorité lie tentative et horloge.
À 210 s, avant de lire les commandes du programme : état exact de tentative
échouée, révocation d'horloge, interruption du pending ID, état natif LAND
sur place, cible verticale d'origine. Les commandes tardives (dont STOP)
sont rejetées ; RESET ne peut être admis après expiration qu'après fin
native de pose. Un reset crée une nouvelle tentative, il n'efface pas le
résultat de la précédente. LAND commandé et LAND achevé restent distincts.

La nouvelle mise en échec écrit également le canal de résultat du drone
avant d'attendre l'évaluateur. Une admission sans identité valide/évaluateur
refuse TAKEOFF. Le filtrage des messages expirés intervient avant le bookkeeping du broker : un RESET refusé ne peut réserver le même ID que le LAND interne et incrémenter une tentative lors d’un ACK de LAND. COMPLETE/FAILURE tardifs sont refusés, OUTCOME reste lisible. Ce durcissement doit recevoir ses contre-exemples indépendants.

Les améliorations postérieures au dernier essai local sont
**non qualifiées** jusqu'à la CI du nouveau HEAD ; aucune ancienne observation
n'est transférée.

## Témoin et réfutations obtenues

Témoin composé de range/variables/if/repeat/while/move/vertical/turn/land
ordinaires, budget calculé 16620 ≤ 20000. Il ne reçoit ni graine, position,
quantité future, oracle ou score. Descente et observation frontale, retour
oblique fini si saturation, dégagement puis mesure arrière ; deux virages
reconnus par les distances, pose choisie par le compte appris.

Le H du troisième côté peut masquer l'ouverture latérale du second coin :
une reconnaissance du coin par seule hausse de range(left) a été réfutée.
Au premier contre-exemple natif à trois H, gabarit en contact à 91,000 s,
deux passages déjà validés, centre vers (1,67035 ; 2,36030 ; 0,79013) ;
gap à la boîte latérale ≈0,08989 m < rayon 0,09 m. Sa correction change le
témoin (observation proche des panneaux, mesure de la paroi extérieure après
virage, recentrage), jamais les murs ou la marge.

Un TAKEOFF direct 0,80 m a dépassé le plafond d'altitude dans deux cadences
testées ; son origine n'est pas attribuée au seul pas de 8 ms. Le témoin
utilise 0,40 m puis montée de 0,40 m, comme la stratégie historique.
Aucun retuning PID ou relèvement du plafond.

Observations locales **avant les dernières mutations** du candidat :

|Cas|Résultat observé|Durée Webots|
|---|---|---:|
|2 m, graine 4, trois H, pose droite|réussie, 3 passages|145,472 s|
|2 m, graine 0, un H, pose centre|réussie, 1 passage|123,328 s|
|attente volontaire au départ|échec, LAND natif, STOP tardif rejeté|210,000 s|
|vol court et pose au départ|échec, mauvaise pose|14,216 s|

Même AST des deux succès : SHA-256
38948a96f7a971e8dff2d920e07b8626a81b057311058fbcd937d4c2bc9190d2.
Source partagé alors composé :
0067b7167288141a9cb38e5732311ecbb75c0de4d7ba7475d1ead807ccafc3c0.
Ces résultats sont des observations d'auteur, pas des GO du présent HEAD.
Les traces locales n'ont pas pu être archivées intégralement sur GitHub après
la déconnexion de l'exécuteur : ne pas prétendre à une archive native complète.

Le probe TIMEOUT initial utilisant repeat(100) a été refusé par le vrai
préflight avant TAKEOFF ; cela ne prouvait aucun watchdog. Il est corrigé
en repeats ordinaires bornés 10×10. Les premiers probes réutilisant un port
et un fichier ont aussi exposé des survivants du lanceur ; les essais utilisent
maintenant un port et des fichiers frais, et retirent les groupes des processus
créés, y compris quand leur wrapper a déjà quitté.

## Reproduction et nouvelle CI

Dans un environnement disposant de Docker et Node 22+ :

```bash
python3 tools/ci/run_grand_prix_u_prototype.py
python3 tools/ci/run_grand_prix_u_prototype.py --suite sizes
```

Image R2025a et assets épinglés, aucun vol matériel. Le premier scénario
exige 1/2/3 H avec le même AST, mauvaises pose/altitude, plafond en attente
et dans un H. Le second observe 2/3/4/5/6 m avec le même AST ; un échec de
taille est une réfutation conservée, pas une réussite. Ce balayage est un
début de recherche, **pas la détermination de la taille maximale** ni une
qualification de toutes les dispositions.

Pour préparer le monde interactif sans utiliser les mondes historiques :
```bash
python3 tools/grand_prix/prepare_u_runtime.py
make -C controllers/grand_prix_u_flight
# ouvrir worlds/grand_prix_u_seed4.wbt dans Webots R2025a
```

Le préparateur génère les mondes U 0/1/4. La fenêtre dédiée expose le même
Blockly/AST/préflight/interpréteur que le produit ; le starter vide est
activities/grand-prix/02-grand-prix-u.wbb. Les tests Node de profil/témoin
ne remplacent pas une acceptation de la vraie fenêtre Blockly.

Les runs Draft restent non décisionnels et ne publient pas CI Gate.
Ready devra fournir la CI canonique exacte et la revue d'une autre exécution.

## Frontières encore ouvertes

- Après déconnexion locale durant le probe LAND dans un H : résultat UNKNOWN,
  aucun PASS revendiqué, aucune relance aveugle du même processus.
- Le cas natif à 2 H/pose gauche, les nouveaux négatifs, la composition exacte
  après modifications, les courses ACK/RESET et deux tentatives successives
  restent à établir par la nouvelle campagne.
- Fenêtre Blockly/.wbb réelle et réversibilité des contrôles à vérifier.
- Géométrie 2 m encore candidate ; transitions et marges mesurées sur toutes
  dispositions, recherche/bisection d'un maximum, stabilité CPU/WWI,
  saturations adversariales et bruit restent ouverts.
- #597 conserve une analyse utile, mais son pas fixe 32 ms ne peut analyser
  sans adaptation les traces U à 8 ms.
- Aucun backend physique, activité intermédiaire, #157/#72, vol réel ou
  checkpoint n'est modifié. Le plafond 210 s ne démontre aucune autonomie
  batterie ni récupération physique.
