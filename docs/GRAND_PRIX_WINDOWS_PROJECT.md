# Grand Prix autonome — projet Windows isolé

Ce paquet de simulation réunit le contrôleur U natif, son évaluateur Python
embarqué, trois mondes R2025a et la fenêtre Blockly dédiée. Webots R2025a et
Chrome restent requis ; aucune installation Python élève ni connexion Internet
n'est nécessaire. Aucun accès au drone réel n'est fourni.

Extraire dans un nouveau dossier accessible en écriture. Fermer Webots avant
chaque lancement. Ouvrir `Launch-WebeeBlocks.cmd` (configuration 5 par défaut),
ou `Lancer-Grand-Prix-1.cmd`, `Lancer-Grand-Prix-2.cmd`,
`Lancer-Grand-Prix-5.cmd` pour choisir une configuration reproductible.
Attendre PRÊT puis utiliser « Démarrer une activité » pour le Grand Prix.
Les fichiers `.wbb` restent ordinaires : Enregistrer sous au premier
enregistrement, Enregistrer pour le même fichier, Ouvrir pour reprendre.
Un même programme enregistré peut être essayé dans les trois configurations.
Les commandes pas à pas restent exclusivement simulées ; le temps Webots
continue d'appartenir à la mission et son plafond de 210 s reste inchangé.

Le paquet scolaire ordinaire et son catalogue ne sont pas modifiés. Cette
composition prépare la livraison du Grand Prix ; elle ne remplace pas encore
l'ancienne activité 8 dans ce catalogue. Les activités 2–7 restent des prototypes
historiques. Ne pas mélanger les fichiers des différents paquets.

`SOURCE_SHA`, `COMPOSITION.json` et `MANIFEST.sha256` identifient les sources,
les trois supports d'entrée et tous les fichiers distribués. La CI vérifie
l'assemblage extrait et le lanceur pour chaque configuration. Les preuves
distinctes de chargement natif Windows ne valent pas un parcours élève complet
ni l'acceptation pédagogique personnelle. Le lancement réel et le parcours
Démarrer/simuler/observer/pas à pas/Enregistrer/Ouvrir restent à accepter sur
le poste de référence via le mécanisme de checkpoint du projet.

La CI exécute aussi l'archive extraite dans le vrai Webots Windows R2025a,
avec les contrôleurs et l'interpréteur embarqué du paquet, sur les trois
configurations 1/2/5. Le même témoin Blockly compilé et prévalidé doit réussir
avec les trois atterrissages, sans modifier géométrie, autorité ni oracle.
Les traces natives, résultats, diagnostics et empreinte de l'AST sont retenus
dans `grand-prix-u-windows-native`, y compris en cas d'échec. Ce contrôle
par WWI est une preuve d'exécution technique de l'assemblage, pas une preuve
du lanceur GUI, de manipulation des fichiers ou d'acceptation personnelle.

Sur le runner Windows automatisé, cette campagne utilise Mesa logiciel
24.2.1 release-mingw, comme la [CI Windows officielle de Webots R2025a](https://github.com/cyberbotics/webots/blob/R2025a/.github/workflows/test_suite_windows.yml).
L'archive est vérifiée par SHA-256 avant installation sur ce seul hôte jetable,
après construction des paquets ; elle n'est pas distribuée aux élèves.
`--sysinfo`, la commande et les codes de sortie du moteur sont retenus avec
les traces. Cette preuve ne qualifie pas les performances graphiques d'un PC
de classe ni la lisibilité de sa fenêtre ; ces observations restent humaines.

Le moteur R2025a est capturé par deux pipes drainés simultanément : son
`gui/main.cpp` conserve les handles redirigés seulement pour `FILE_TYPE_PIPE`
et rouvre sinon `CONOUT$`. Des fichiers directs perdaient donc les journaux
sur Windows. Le banc conserve le même READY et les mêmes résultats natifs ;
il ne remplace pas ces preuves par la seule présence d'une trajectoire.
