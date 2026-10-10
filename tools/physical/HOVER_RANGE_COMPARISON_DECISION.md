# #157 — décision avant comparaison Multi-ranger sol / vol

**Statut : proposition scientifique préparée, essai non autorisé et checkpoint
non prêt.** Ce dossier ne demande aucun `TEST_REQUIRED`. Il ne prescrit aucune
manipulation maintenant. Les procédures ci-dessous sont conditionnelles à une
décision explicite ultérieure du propriétaire et au mécanisme de checkpoint.
#70 reste suspendue ; aucune recherche, configuration ou preuve X3 n'est requise.

## État et décision recommandée

Base examinée : `main@049ab4c8d4a1c563d6727df424324edaeecc2e2a`, contrat V5,
vision et roadmap sur ces octets. #583 est intégrée : candidat indépendamment
revu `257876977ec89e0fbc403785a4d64286e8656fec`, squash ci-dessus, arbres identiques.
Les trois réfutations initiales sont résolues pour l'admission au décollage ; ce
dossier ne réouvre pas cette revue. Le GO était logiciel, pas physique.

La comparaison est **scientifiquement utile**, mais **il est prématuré d'autoriser
son exécution**. Deux compléments logiciels sont proposés dans cette PR : preuves
brutes du retour en vol et réutilisation en vol de la fermeture LOG confirmée
déjà revue pour l'admission. Leur auteur ne peut pas fournir le GO indépendant.
L'environnement réel, le volume de récupération et l'arrêt opérateur décrit
ci-dessous ne sont pas encore qualifiés. Leurs inconnues interdisent un effet
physique ; une CI verte ne les résout pas.

| Question | Preuve disponible | Limite pour la décision |
| --- | --- | --- |
| Disponibilité au sol | #572 : 200 valeurs finies, archive #580 intégrale revérifiée | FAIL procédural ; aucune disponibilité continue, ni autorisation transférable |
| Indisponibilité en vol | #566 : premier `range.front=32766`, récupération contrôlée attestée dans ce run | Géométrie et statut VL53L1 absents ; cause inconnue |
| Admission avant poussée | #583 : premier retour, PARAM causal, même epoch, suppression LOG confirmée, autorité réaffirmée | Publication LOG, pas âge de production ni marge obstacle |
| Retour fini en vol sur la base | `readRange` rend les mètres à l'interpréteur sans journal brut positif | Impossible de comparer précisément valeurs, timestamps et contexte après un succès |
| Fermeture LOG en vol sur la base | `FreshRangeObserver.close()` appelle stop/delete asynchrones | Retour local sans preuve de réponse ; #583 ne remplace que l'observateur d'admission |
| Suivi / descente réels | Nominal 0,50 m ; commande 9/10 à 0,50 m/s ; supervisor et ACK | Aucun maximum mesuré X/Y/Z, attitude, latence ou distance de récupération |
| Arrêt opérateur | CLI : PREPARE, APPROVE/DENY, puis exécution bloquante | Aucune commande d'abandon en vol proposée/qualifiée par ce lanceur ; Ctrl-C/kill/reset ne sont pas un atterrissage garanti |

Le programme historique #554/#566 ne convient pas à un **essai minimal** : à
1 m de la cible, `front > 0.8` sélectionne une avance de 0,20 m, puis viennent
une rotation de 45° et une montée/descente de 0,20 m. Ces effets ajoutent du risque
sans informer davantage sur le premier retour sous poussée. Leur suppression est
un **nouveau programme explicite**, à valider inchangé en simulation, jamais une
adaptation cachée du programme historique après son autorisation.

## Hypothèse, pouvoir discriminant et limites

Question bornée : dans UNE scène fixe et témoin conservé, une observation avant
décollage utilisable est-elle suivie d'une observation utilisable en stationnaire
nominal à 0,50 m ? L'essai peut réfuter la continuité ponctuelle dans cette scène.
Il n'est pas une campagne de fiabilité, un contrôle anticollision ou une mission #72.

La hauteur, l'attitude, la poussée, les vibrations, l'alimentation et certains
angles optiques changent ensemble. Même avec une cible suffisamment large, un
échec ne prouve pas que les moteurs ont causé la panne. Une mesure finie à chaque
instant ne prouve pas que le producteur ne s'est pas figé entre les deux : le
timestamp LOG date la copie/publication des valeurs stockées. Ni une cible fixe
ni une différence de timestamp ne fournissent un âge de production. Ne pas ajouter
une cible mobile, de filtre alternatif ou de firmware expérimental pour combler
cette limite dans ce premier essai.

Deux observations positives qualifient uniquement **la comparaison ponctuelle
de ce run**, si toute la procédure est conforme. Elles ne qualifient pas toutes
les directions, les obstacles, le comportement Color LED, la récupération lors
d'une rupture radio, la reproductibilité ou l'exploitation pédagogique générale.

## Programme exact proposé et support futur

Ouvrir `tools/physical/hover_range_comparison.wbb`, profil existant
`reactive-obstacle-v2`. Ce fichier n'est pas ajouté au catalogue des élèves.

1. Décoller à 0,50 m.
2. Attendre 1,00 s après la complétion causale du décollage.
3. Affecter `distance` à UNE expression `range(front)`.
4. Atterrir immédiatement, sans utiliser la valeur pour choisir un mouvement.

Le fichier canonique compagnon est `hover_range_comparison_ast.json`.
Digest SHA-256 de la liaison AST **sans le saut de ligne du fichier** :
`97bc1460a74f331804e3ea288ee452d52e7a5573920a1bbcc4e225bf941c4aa5`.
Le compiler Blockly/profil natif et l'interpréteur partagé sont exercés par les
tests de cette PR. Cela ne remplace pas le témoin de validation réel Webots du
programme sélectionné avant toute exécution physique. Aucun debug en vol.

L'artefact nécessaire est un **nouveau** `WebeeBlocks-Physical-Qualification`
du futur SHA exact intégré et indépendamment revu. Le packager copie tout
`tools/physical` : projet, AST, ce dossier et modifications y seront couverts par
le manifeste. Le futur profil de checkpoint reste
`physical-capabilities-representative`, purpose `checkpoint`, déjà implémenté.
Ne pas changer les mécanismes de gouvernance. Les artefacts de #583/#572 et leurs
digests sont des preuves historiques, pas le support autorisé du futur essai.

Conserver `SOURCE_SHA`, `PROVENANCE.json`, `SHA256SUMS.json`, ID d'artefact,
workflow/run/attempt et SHA-256 du ZIP préparé par le checkpoint. Ces identités
ne peuvent pas encore être renseignées pour une PR non intégrée. Ne pas fabriquer
un ZIP « exact » depuis un checkout modifié ou reprendre le package antérieur.
La qualification complète du paquet extrait CPython 3.10/R2025a appartient à la
CI canonique puis à la préparation déterministe du checkpoint.

## Préconditions physiques encore ouvertes

### Volume et cible

Un emplacement de départ marqué au **sol**, uniforme, plat, mat, texturé et
éclairé doit couvrir décollage, dérive et récupération. Aucun départ sur table,
support surélevé, tapis avec marche, ombre mobile ou surface brillante. Aucun
obstacle dans le volume de vol/descente. Ne pas poser de capteurs supplémentaires
ou utiliser la recherche #70 pour justifier le Z.

Cible candidate : panneau fixe, mat, opaque, vertical, à distance horizontale
nominale **1,00 m depuis le capteur avant**, mesurée indépendamment avant le run.
La mesure inclut son incertitude ; le retour ToF n'est jamais le réglet. Ses
dimensions, sa fixation et la lumière doivent être décrites. Il doit couvrir le
cône optique au sol et à 0,50 m, avec les excursions admises de position/attitude.
Le sol peut contribuer au retour bas ; si le témoin ne permet pas d'écarter une
occlusion ou une cible différente, ne pas attribuer une différence au vol.

**1,00 m est un candidat de géométrie, pas une distance de sécurité validée.**
Le panneau et ses supports doivent être hors du volume de récupération. Pour
une limite horizontale de run `R`, une enveloppe rotor `r`, une incertitude de
géométrie `u` et une excursion additionnelle avant fin d'arrêt `d_abort`, il faut
au minimum `D > R + r + u + d_abort` dans la direction de la cible. La couverture
optique doit tenir jusqu'à ces limites. Les valeurs `R`/`d_abort`, la latence
opérateur et les excursions Z/attitude ne sont pas établies par les archives.
Une ligne au sol, un ACK ou « pas de mouvement commandé » ne les bornent pas.

Il faut donc, avant une demande motorisée, documenter une maîtrise indépendante
des conséquences de sortie du volume (protection/confinement adapté, sans
obstruction du Flow ni intrusion dans l'enveloppe rotor), ou apporter des marges
physiques indépendamment justifiées. Aucune dimension de confinement ni borne
de suivi n'est déclarée acquise ici. Personnes, animaux et biens sensibles doivent
rester hors du volume accessible en cas de perte d'estimation ou de liaison.
Une enceinte peut modifier pression, lumière et retours optiques : sa présence
fait partie de la scène qualifiée. Aucune manipulation pour installer cette scène
n'est autorisée par le présent dossier.

### Arrêt opérateur et récupération

Le run normal finit par l'atterrissage intégré. Sur mesure indisponible ou faute
après un décollage causalement établi, l'autorité ordinaire est révoquée et le host
peut tenter **une seule** descente contrôlée de récupération, si ses conditions
indépendantes restent satisfaites. #566 prouve un cas, pas un majorant de durée
ou d'excursion. Une perte d'epoch, un état d'effet ambigu, un watchdog perdu ou un
atterrissage déjà tenté peuvent rendre cette récupération bloquée. Un reset STM,
un arrêt immédiat ou la fin du watchdog peuvent couper les moteurs ; à 0,50 m
une chute/impact reste possible. Ne pas les présenter comme une descente douce.

Il manque une **procédure opérateur d'abandon en vol éprouvée pour ce lanceur**,
accessible sans debug, retry, deuxième client radio ni nouvelles commandes élève.
Une éventuelle correction doit réutiliser la révocation et la récupération
host, conserver le watchdog pendant l'arrêt, préciser latence et état ambigu et
passer une revue indépendante. Ce dossier ne prétend pas que Ctrl-C, QUIT,
fermer Webots, tuer le host ou débrancher la radio sont ce mécanisme.
Le canal d'urgence ultime et ses conséquences doivent être nommés et qualifiés
dans le futur protocole, avec protection du volume de chute ; ils restent ouverts.

## Déroulement conditionnel du futur checkpoint

**Ne rien exécuter maintenant.** La décision propriétaire doit nommer le but,
le nouveau programme, le domaine expérimental et les risques résiduels. Après
revue/CI/intégration des corrections indispensables et résolution des préconditions
ci-dessus, reconstruire main, dépendances, demandes ouvertes et profil. Observer
l'absence de tout autre `TEST_REQUIRED` avant de publier une demande exacte. La
consultation actuelle des issues ouvertes ne trouve que #70/#72/#157 ; elle n'a
pas de valeur permanente pour un futur checkpoint. Aucun essai en attente n'est créé.

Le futur document exécutable devra prescrire cet ordre et arrêter au premier défaut :

1. Enregistrer la sortie terminal complète dès le téléchargement/extraction,
   vérifier le nouvel artefact sur Ubuntu 22.04 x86-64/Python 3.10/Webots R2025a.
   Échec de vérification : FAIL, arrêt sans environnement de remplacement ni retry.
2. Exécuter une fois la préparation officielle emballée, avec quatre hélices
   retirées, URI exacte et dossier de sortie neuf hors artefact. Conserver
   `preparation-start.json`, `preparation.json` PREPARED et readbacks typés.
   Firmware cf2 2026.08/binaire `9b745fe76da30e071ba8e04e6a8535d1dbd747d7ce6ca72d2d3ccf8c18978298`,
   EKF=2, PID=1. Pas d'écriture de tuning, UKF/S3 ou récupération X3.
3. Conserver le relevé de scène/zone, incertitudes et témoins indépendants réels.
   Vérifier matériel après les impacts historiques : hélices/moteurs/montage,
   orientation et dégagement Flow/Multi-ranger/batterie, selon le contrôle
   constructeur et le futur protocole autorisé. Défaut/doute : arrêt.
4. Valider le projet exact inchangé dans Webots ; garder fichier, AST, digest,
   résultat et témoin. Ne pas substituer l'AST historique plus long.
5. Seulement lorsque la procédure l'autorise et tous les contrôles de site passent,
   réinstaller les hélices ; démarrer un témoin externe continu véhicule/cible/
   repères et la transcription terminal. Restaurer le départ marqué, orientation
   avant connue, cible inchangée. Ne plus toucher le véhicule entre PREPARE et
   fin de récupération. Une préparation devenue invalide ne permet pas un retry.
6. Le runner emballé normal reçoit URI et nouveau `--preparation-record` ; ouvrir
   le `.wbb` emballé, PREPARE une fois. Au résumé post-reset, comparer profil,
   AST digest et programme exact. DENY si une précondition manque. APPROVE une fois
   seulement avec décision/checkpoint applicables et volume dégagé.
7. Le host observe au sol puis commande une seule montée. Après complétion et
   attente, une seule mesure avant ; atterrissage normal ou récupération éligible.
   Ne pas bouger la cible, aider le drone à la main, modifier le programme ni
   reconnecter. Vérifier physiquement le posé et conserver les traces de fin avant
   toute intervention matérielle autorisée par le futur protocole.

Il ne faut pas ajouter une boucle « jusqu'à mesure finie ». Une observation
indisponible au sol interdit le décollage ; elle est discriminante pour
l'admission mais ne donne aucune comparaison en vol. Son échec termine ce sujet.

## Critères d'arrêt et résultats

| Déclencheur | Conséquence requise dans le futur protocole |
| --- | --- |
| Erreur de package/runtime/préparation, témoin manquant, mauvaise liaison AST/configuration ou défaut matériel | Pas d'APPROVE ; conserver erreur, FAIL de procédure, aucune continuation |
| Première observation au sol indisponible, PARAM non causal, epoch changé ou suppression LOG non confirmée | Veto automatique de command 9 ; aucun retry |
| Mesure en vol indisponible/malformée, délai dépassé, identité perdue ou suppression LOG incertaine | Arrêt du programme ; une récupération contrôlée seulement si éligible ; conserver premier brut et causes |
| Départ de l'enveloppe déclarée, inclinaison/dérive inhabituelle, cible hors champ, obstacle/personne entrant, vibration/contact ou capteur masqué | Abandon opérateur via la procédure encore à qualifier ; aucun seuil numérique arbitraire n'est autorisé ici |
| ACK/complétion/descente inconnus, crash ou défaut de récupération | État ambigu ; pas de commande renvoyée, reset/reconnexion opportunistes ou approche d'un véhicule encore actif |
| Données/témoin perdus, terminal non conservé ou commande répétée | Comparaison incomplète/FAIL procédural ; pas de vol supplémentaire pour « réparer » les preuves |

PASS de ce futur sujet exigerait : programme et préparation exacts, procédure
entière conforme, disponibilité ponctuelle sol ET vol, deux bruts/timestamps de
même epoch liés au digest, géométrie effective et témoin continu conservés,
aucune sortie de domaine/contact et descente normale/posé effectivement vérifiés.
Un retour indisponible en vol avec descente réussie serait un **échec de
disponibilité**, même si la récupération fournit une preuve positive séparée.
Un veto au sol n'est pas un succès de comparaison. Séparer intégrité procédurale,
retours capteur, trajectoire et récupération ; garder les observations défavorables.
Aucune tolérance d'exactitude du ToF n'est qualifiée par ce protocole : comparer
les erreurs à la géométrie et son incertitude, sans inventer un oracle PASS après coup.

## Preuves à conserver intégralement

- Identités SHA/run/attempt/artefact/ZIP/manifeste et sorties de chaque vérification.
- Préparation complète, readbacks, URI, configuration réelle et identité du matériel.
- Projet `.wbb`, liaison AST canonique et digest présenté avant APPROVE, preuve
  de validation en simulation ; décision explicite applicable.
- Distance indépendante, incertitude, capteur de référence, dimensions/fixation
  cible, sol/lumière, volume autorisé/protection et méthode d'arrêt ; photos réelles
  face/profil et vidéo continue. Une déclaration JSON n'est pas un témoin.
- Transcript complet et `physical-qualification-*.log`, incluant
  `HOST_RANGE_READINESS`, `HOST_INFLIGHT_RANGE`, `HOST_DIAGNOSTIC`,
  `HOST_RECOVERY`, `HOST_TEARDOWN` présents, ou leur absence explicite.
  `backendReadAccepted=false` signifie brut conservé mais rejeté par le backend ;
  `true` signifie contrôles backend satisfaits, sans preuve de livraison RPC à
  l'interpréteur ni de succès du run ;
  `hostReportMonotonicNs` date le rapport, pas la production ni la réception.
  Le premier callback demandé garde une copie diagnostique de son epoch/tick/brut,
  même si une erreur LOG, un callback malformé ou une perte d'epoch ultérieure
  interdit sa consommation. Cette copie ne valide jamais une mesure rejetée.
  L'entrée et la capture locale du callback sont sérialisées avec la clôture de
  sa demande, indépendamment de l'acceptation : une déconnexion pendant son
  traitement ne peut effacer un brut déjà entré et correctement encadré. Le
  callback garde sa génération d'entrée même si son traitement finit après une
  nouvelle demande ; aucun callback antérieur n'acquiert de fraîcheur ainsi.
  La sortie en vol utilise une file bornée de 64 rapports et un worker daemon,
  sans écriture, flush, drain ou join dans le chemin de commande/récupération.
  Un stockage/terminal bloqué, une file pleine, une erreur d'écriture ou la fin
  du processus peuvent perdre un rapport : absence/ligne partielle = INCOMPLET.
  Le timestamp date la construction du rapport, pas son écriture différée.
- Toutes les traces partielles, exceptions et données négatives, observation
  réelle de la descente/posé/impact et éventuelle absence de récupération.

Relier la vidéo aux événements de terminal par un témoin d'horloge/écran conservé
avec son incertitude. Ne pas aligner directement des ticks firmware et une vidéo
parce que leurs nombres semblent proches. L'absence de trace donne INCOMPLET pour
l'analyse scientifique et interdit de déduire une observation favorable.

## Sources et corrections bornées

- [Intégration/revue #583](https://github.com/djibian/webeeblocks/pull/583),
  [état physique #157](https://github.com/djibian/webeeblocks/issues/157#issuecomment-6098096705),
  [archive #572/#580](../../docs/evidence/checkpoint-572/README.md),
  [audit #554](../../docs/PHYSICAL_FAIL_554_AUDIT.md).
- Source de base : `dynamic_physical_backend.py:readRange/_default_range_observer`,
  `range_observer.py:_cleanup`, `launch_physical_qualification.py:main`,
  `production_takeoff_run.py:_recover`, AST historique `tools/ci/fixtures/physical_fail_554_ast.json`.
- [Bitcraze : Multi-ranger, aucune réaction obstacle automatique](https://www.bitcraze.io/products/multi-ranger-deck/).
- [Bitcraze : contraintes Flow/sol/texture/éclairage](https://www.bitcraze.io/2023/11/go-with-the-flow-relative-positioning-with-the-flow-deck/),
  [tutoriel Flow](https://www.bitcraze.io/documentation/tutorials/getting-started-with-flow-deck/).
- [Supervisor/watchdog : emergency stop](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/functional-areas/supervisor/).
- Firmware, cflib et limites de publication restent ceux de
  [PHYSICAL_FLIGHT_BASELINE.md](PHYSICAL_FLIGHT_BASELINE.md), sans nouvelle enquête
  sur les défauts déjà éliminés ni tuning.

Cette PR ne fournit que la trace scientifique, le programme minimal et la
fermeture LOG confirmée en vol avec leurs contrôles déterministes. L'arrêt
opérateur/site reste un blocage conservé, pas une garantie livrée. Aucun paquet
physique de cette PR, même vert et intégré, ne déclenche de checkpoint sans une
nouvelle décision propriétaire satisfaisant ces préconditions.
