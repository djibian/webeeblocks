# Sous-scènes de simulation — prototype #587

Le monde de lancement reste `worlds/crazyflie_runtime_v2.wbt`. Le bouton
« Démarrer une activité » et l'ouverture d'un projet sélectionnent la scène avant
de remplacer le workspace. L'activité 1 charge `worlds/scenes/sequence-v1.wbo` ;
les autres profils conservent le monde hérité. La sélection ne déduit plus
la scène de l'identifiant de l'activité : chaque profil déclare
`runtime.scene`, avec `sequence-v1` pour l'activité 1 et `legacy-v1`
pour les neuf autres. Une déclaration absente ou inconnue est refusée avant
l'envoi de SCENE ; le contrôleur natif conserve sa propre liste fermée de
ces deux scènes, ses validations et ses refus. Les programmes `.wbb`, les
AST, les missions, les bornes et les oracles de livraison ne changent pas.

La sélection native est limitée à `sequence-v1` / `legacy-v1`, à l'état posé,
immobile, hors effet, sans fail-safe et près de l'origine réinitialisée. Elle
retire les objets et contrôleurs hors activité avant l'import. Les nœuds importés
au démarrage par les évaluateurs 7/8 sont retirés aussi ; leur restauration passe
par le redémarrage des évaluateurs, qui reconstruisent leurs propres objets.
Une importation incomplète ne permet aucun décollage. Le sol, le drone, le WWI
et l'oracle de séquence restent en place ; il n'y a aucun chargement de `.wbt`,
transfert de fichier élève, changement de sauvegarde ou donnée de navigation.

Le damier est un décor plat sans `Solid` ni `boundingObject`, en bord de zone
verte ; il ne crée pas un obstacle horizontal aux hauteurs de vol. Le sol Webots
existant demeure la seule surface physique et texturée sous le drone. Le pad
garde les dimensions utilisées par l'oracle original.

## Vérification falsificatrice

La chaîne `run_progression_sequence_mission.py` vérifie dans Webots R2025a la
sélection, l'absence de l'ancien obstacle dans la mesure avant en vol, le refus
du changement en vol, réussite/reprise/échec de livraison, puis le retour au
monde hérité et tous les cas de précision/collision d'origine. Les tests projet
exigent un ACK avant mutation et conservent le workspace si la préparation échoue.
Les tests des autres activités restent obligatoires et inchangés.

Les actions de fichiers attendent aussi le transport Robot Window et son READY,
y compris avec le sélecteur natif Chrome. Une sélection de scène en cours refuse
une seconde sélection ; seul son ACK OK exact peut confirmer l'identité, et un
ACK retardé après RESET ne la rétablit pas. Si l'application du workspace échoue
après une préparation confirmée, la restauration comprend la scène du profil
précédent. Une erreur de restauration reste attachée à l'erreur causale ; l'UI
conserve alors le veto terminal. Aucun import ambigu n'est automatiquement rejoué.

Un nouveau backend Robot Window considère toujours la scène native inconnue,
même après READY : ce message prouve uniquement la disponibilité du contrôleur.
La première préparation envoie donc SCENE et attend son ACK OK corrélé avant
d'appliquer le projet, y compris pour les activités 2–8 utilisant legacy.
Les tests projet couvrent Démarrer/Ouvrir pour ces sept profils après
réattachement, le trajet inverse et les réponses retardées/erronées ; le probe
R2025a remplace aussi le backend tout en gardant le même contrôleur natif.

Un redémarrage du seul contrôleur natif est distinct d'un réattachement de
fenêtre : ses variables de processus ne prouvent pas le monde conservé.
Le module observe les groupes vivants avant toute autorité et revalide leur
structure sur le chemin d'identité déjà sélectionnée et avant TAKEOFF. Les
cardinalités attendues sont fixées par le monde de lancement versionné :
**32 enfants directs de scène et 6 évaluateurs**, indépendamment d'un état
vivant potentiellement incomplet lors du démarrage. Une seconde instance
native aux statiques fraîches doit donc refuser une racine partiellement
amputée, même lorsque les références restantes sont valides.
Si sequence-v1 survit sans les snapshots legacy perdus avec le processus,
SCENE et TAKEOFF restent refusés ; il faut recharger le monde Webots pour
reconstruire les scènes et évaluateurs. Aucun faux ACK legacy ne remplace
cette récupération explicite. L'absence totale des trois groupes reste elle
aussi refusée, y compris après redémarrage : elle ne prouve pas un monde dédié.
Les mondes dédiés déclarent positivement
`DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo` et ne contiennent aucun
groupe géré. Ce marqueur typé est vérifié avant chaque autorité TAKEOFF ;
absent, de mauvais type ou supprimé, il ne peut autoriser le monde.
Il identifie le mode de scène, sans qualifier la géométrie ou l'oracle du monde.
Le monde sonde outcome et les générateurs/sondes U déclarent ce mode ;
le monde pédagogique Runtime v2 conserve obligatoirement ses groupes.

Tout READY reçu invalide la connaissance de scène JS et l'epoch des réponses ;
les requêtes encore en attente d'un contrôleur précédent sont annulées.
Un ACK déjà reçu dont le callback attend ne peut pas confirmer la scène après
ce READY. Le test C++ charge deux instances isolées du module de production
sur les mêmes nœuds pour reproduire les statiques fraîches d'un redémarrage ;
ce test hôte n'est pas présenté comme un redémarrage réel R2025a exécuté.

Les identifiants numériques repartent à 1 dans une nouvelle fenêtre : ils ne
suffisent donc pas à corréler un ACK retardé d'une autre connexion. Chaque
préparation ajoute désormais un jeton aléatoire de 256 bits, généré par
`crypto.getRandomValues`, à SCENE. Le contrôleur le renvoie dans SCENE_OK
seulement après sélection native réussie ; le backend exige ID ET jeton exacts
avant confirmation. L'unicité pratique repose sur la source aléatoire système ;
son absence refuse la préparation. Ni un ancien OK simple ni le jeton d'une
autre préparation ne consomme la requête courante. Les erreurs restent
refusantes. Les requêtes SCENE historiques sans jeton restent compatibles avec
les probes natifs, mais leur OK simple ne confirme jamais une préparation du
nouveau frontend. Les tests routent explicitement l'ancien ACK au nouveau
récepteur avec le même ID, avant de livrer le seul bon ACK.

Le signal spontané `READY` indique un démarrage du contrôleur : il invalide
toujours scène, requêtes et horloge antérieures. La réponse de disponibilité à
`HELLO` est distincte : `READY HELLO`. Elle libère seulement une attente de
disponibilité en cours et n'invalide pas une scène ou une commande. En effet,
le `READY` spontané puis la réponse tardive à `HELLO` peuvent entourer une
requête SCENE et son accusé dans une même connexion normale. Les confondre
annulait cette préparation avec `RESET_CANCELLED` (CI Ready 38788423410).
Les tests couvrent les deux ordres autour de SCENE_OK, y compris avant son
callback, une commande ordinaire en attente, le vrai redémarrage et RESET.

Le lancement dans un autre monde sans les groupes identifiés peut refuser la
scène épurée : seule la scène de lancement Runtime v2 est couverte. La lisibilité
visuelle, les save/open/reset représentatifs et le comportement réel du modèle
incliné restent à valider ; un test de syntaxe ou une scène transparente ne les
prouve pas. Aucun essai matériel ni vol physique n'est autorisé.

La compilation modifie les entrées générées épinglées de la qualification : la
CI doit préparer le nouveau cache exact en brouillon, observer le digest réel,
puis vérifier ce digest. Un échec de cache n'est ni un échec de mission ni une
autorisation de contourner la vérification. Le dossier physique #157 conserve
ses blocages et ses anciennes preuves ; #70 demeure suspendue.

L'import vérifie aussi les enfants directs : les 18 éléments de la scène de
livraison, puis les cardinalités et références des deux Group historiques
capturées avant leur retrait. Une racine présente avec des enfants manquants,
y compris le Group d'évaluateurs lors de la restauration, garde `ready=false`.
Le test natif injecte ces deux cas, puis vérifie la récupération vers legacy.
Ce contrôle ne constitue pas une validation de fichiers de scène arbitraires :
seuls l'asset versionné et les exports Webots capturés sont pris en charge.
