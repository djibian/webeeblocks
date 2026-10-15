# Grand Prix U : composition expérimentale Draft #591

## Candidat recomposé après #602 et #608 — 15 octobre 2026

Le candidat reprend intégralement les huit fichiers en conflit depuis main
`53ace39403970d4fe85f36bdefbbc8b0acaa60be` : autorité, hooks, composition,
oracle et tests. Les corrections des mesures/angles, de la confirmation de
pose et du RESET, de l'échec irréversible et du fournisseur fichier bloquant
restent celles de #602 intégré. Aucun ancien GO ou essai ne qualifie cette
nouvelle composition. Les sources physiques et le verrou natif partagé restent
identiques à main ; aucune activité intermédiaire n'est refondue.

La dimension courante du lancement et de la campagne revient à **2,00 m**,
constante pour les sept configurations. Ce choix privilégie la marge de temps
et les preuves historiques à 2 m plutôt que la taille 3,6 m qui ne laissait
que 4,432 s dans le cas à trois H. La nouvelle campagne doit démontrer la marge
réelle du HEAD courant, les sept réussites du même Blockly/.wbb/AST, les négatifs
et deux tentatives après RESET ; rien n'est réputé acquis par ce choix.

L'échec Draft `38473674859` est conservé : Docker a échoué pendant la campagne,
puis l'upload a échoué sur un répertoire Qt/XDG privé root mode 0700 situé dans
les preuves. L'artefact manquant ne permet pas d'attribuer la première erreur
native. Désormais les caches/configurations temporaires vivent hors du dossier
d'artefacts et sont nettoyés après arrêt des processus. Le journal Docker reste
retenu et sa fin est aussi imprimée en cas d'échec. Aucun délai, oracle ou cas
de test n'est supprimé. La CI doit établir la correction et diagnostiquer toute
réfutation native restante ; aucune reprise aveugle n'est autorisée.

Les sections suivantes et les preuves de 2026-10-13 sont historiques. Une
acceptation pédagogique personnelle de chaque borne reste nécessaire selon
#587/#608, indépendamment des futurs CI Gate et GO techniques.

---

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

Premier candidat historique à 2 m pour toutes les graines : 1–3 H, un maximum/côté ; aucun
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


## Réparations natives du 13 octobre, seconde campagne

La composition conserve les sources partagées, colliders, rayon 0,09 m,
bandes ±0,55 m, seuil 0,60 m et oracles. Le témoin seul est corrigé :
une somme latérale saturée au second coin n'est pas une aire terminale ;
l'arrivée exige une largeur observée entre 1,65 et 1,90 m. La pose règle
ensuite range(front) entre 0,63 et 0,73 m **avant** le déplacement latéral.
Une avance fixe a été réfutée en graine 3 (x≈0,474 m au lieu de 0,70 m) ;
un décalage latéral trop tôt a été réfuté en graine 14 au bord de l'élargissement.
Ces échecs restent des réfutations, jamais des succès reclassés.

Le témoin est construit avec les vraies définitions Blockly 13.2.1 et les
vrais blocs variables/conditions/boucles ; préflight du profil U, compilation
AST, sérialisation .wbb, réouverture et préflight/AST exact sont vérifiés.
Le helper `tools/grand_prix/witness_workspace_u.js` ne transmet ni graine,
position, quantité de H ni oracle au programme. Il est réservé à la preuve ;
le starter élève reste vide. Le programme natif provient de cet AST compilé.
L'omission canonique des branches else vides n'altère pas le comportement.
Le budget maximal est **18225/20000** ; la boucle de côté est bornée à 35
itérations, la correction finale à 6. Aucun budget du Runtime n'est augmenté.

La CI Draft précédente e27ae679/38462841000 est négative : démarrage réparé,
six négatifs natifs acquis, puis ancien probe inverse qui ne dégagait pas
complètement le H avant de reculer. Le nouveau négatif impose un dégagement
complet, puis exige `reverse-crossing` avec exactement un passage déjà compté.
Le succès d'une mauvaise pose, du vol bas hors bande ou d'une collision
reste impossible à accepter dans le runner.

Les traces conservent aussi une mesure indisponible injectée **après une vraie
lecture native**, refusée par l'interpréteur avant poursuite ; ce n'est pas
une qualification de panne du capteur réel. Les probes d'échéance vérifient
les requêtes COMPLETE/FAILURE/RESET/MOVE/STOP tardives, l'interruption et LAND
à 210000 ms. Deux missions réussies après RESET natif ont des tentatives
1 et 2 et le même AST ; aucune durée ou réussite de la première n'est réutilisée.
Un fichier de diagnostic conserve la pose/vitesse/route/stabilité au verdict.

Les démarrages locaux AF_UNIX refusés utilisent explicitement le transport
TCP officiel ; toute autre erreur native reste négative. Les profils/cache
Qt et runtime XDG sont isolés par essai et Mesa utilise un seul thread.
Le rendu 3D est désactivé dans ce harness de preuve de trajectoire, les forces
Webots et capteurs de distance restent natifs ; cela n'est pas une acceptation
visuelle de la Robot Window. Le temps CPU n'est jamais une durée de mission.

La synthèse JSON versionnée des essais et le paquet des traces complètes
portent les sujets exacts et les digests. Les témoins antérieurs restent
historiques. Une taille réussie pour une graine n'établit ni un maximum global,
ni la qualification de toutes les graines ni une marge physique. Les activités
intermédiaires et #157 ne changent pas. #602 isole l'autorité native ; aucun
GO auteur ou fusion n'est délivré. La composition est offerte Ready après stabilisation du code et des preuves
locales ; une nouvelle CI canonique Ready et la revue d’une autre exécution
sont exigées avant intégration.

Le manifest SHA-256 est désormais établi après arrêt des processus natifs et
fermeture des journaux, y compris en échec : les lignes de déconnexion ne
peuvent plus modifier les logs après leur hash. Les anciens manifests de
runner, produits trop tôt, restent distincts du manifest complet du paquet.


### Dimension du candidat composé

Les sept combinaisons de côtés 0/1/3/4/14/15/17 réussissent à **3,60 m**
avec le même AST `a13e7a58525bd9cc6605b364d596052543ab40e281bb45531ae9837cf798074d`.
Les durées observées s'étendent de 171,328 à 205,568 s. Cette taille devient
le défaut des mondes U composés et de la campagne `--suite all` ; le générateur
et les fixtures 2 m de #599 restent conservés. La graine 4 à 3,70 m échoue
à 210,000 s avec interruption et LAND ; 4/5/6 m échouent aussi au plafond
sur le témoin ayant corrigé la confusion du coin. 3,60 m est la plus grande
**taille ayant réussi ici les sept dispositions**, pas une preuve d'impossibilité
pour chaque millimètre supérieur ni pour une autre stratégie. La réserve minimale
observée de 4,432 s n'est pas une autonomie batterie.

À 3,60 m, les gaps d'enveloppe sphérique **échantillonnés** dans les traces
positives sont au moins 0,044 m pour les essais examinés ; le résultat natif
inclut déjà le contrôle balayé des collisions. La marge échantillonnée ne
constitue ni une borne d'attitude/bruit physique ni une preuve universelle.
Les négatifs, RESET et échéances doivent encore être refaits dans la CI exacte
sur cette nouvelle composition. La CI Ready exacte et une revue indépendante sont exigées avant intégration.

La campagne TCP locale dans un même affichage a reproduit un crash natif
de démarrage (SIGSEGV, aucune tentative admise). Ces essais restent négatifs.
Les preuves locales agrégées utilisent des affichages froids distincts ;
la voie CI normale lance désormais chaque monde avec son propre xvfb-run,
puis retire son groupe de processus. Elle ne relance ni ne tolère un crash.
La CI Docker doit encore établir ce nouveau lancement exact.
