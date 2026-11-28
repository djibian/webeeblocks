# WebeeBlocks — Vision produit

## Finalité

Former au raisonnement algorithmique par la robotique, en particulier en 4e/3e de l'enseignement agricole. Blockly est un moyen : décomposer, programmer, observer, expliquer et corriger sont les apprentissages. L'élève n'a pas à écrire de code textuel.

Le produit de référence est la **progression Grand Prix A1–A8**, disponible depuis [v0.1.0](https://github.com/djibian/webeeblocks/releases/tag/v0.1.0). La [matrice officielle](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md) porte seule les géométries, variantes, règles de mission et nouveaux blocs de chaque activité. Les scénarios de livraison, le U fixe et les anciens prérequis de développement des activités sont historiques.

## Expérience élève

Choisir une activité et son parcours → comprendre la mission → construire → exécuter → observer → corriger → réinitialiser et recommencer → enregistrer.

- Des missions concrètes, des mondes lisibles et distincts, un générateur Grand Prix commun. Un même fichier élève par activité doit réussir toutes ses variantes, sans connaissance cachée du monde ni syntaxe imposée.
- Une boîte à outils cumulative, des primitives génériques et composables. Pas de bloc révélant une solution, une porte ou la cible. Chaque option proposée doit fonctionner. Une nouvelle primitive nécessite un besoin pédagogique démontré, un intérêt dans une autre situation et une observation en pas à pas. Le propriétaire conçoit lui-même sa stratégie avant toute extension de vocabulaire ; `guarded_move` (#659) demeure rejeté.
- Blockly **13.2.1 / Zelos**, interface française, claire et accessible : actions, valeurs, unités, conditions, navigation, commandes d'édition et d'exécution distinctes. Le choix de renderer est acquis.
- Exécution et pas à pas simulés : bloc courant, mesures des capteurs en mètres, variables, Continuer. Pas de guidage de stratégie, de tutorat automatique ni de débogueur professionnel.
- Retour lisible : programme à corriger, mission non réussie, interruption, incident technique, réussite. Expliquer les contraintes et les erreurs établies, sans inventer une cause ou donner le corrigé. STOP et RESET ne doivent jamais autoriser une reprise lorsque l'état natif reste incertain.
- Démarrer une activité crée un projet à partir d'une amorce, sans cible d'enregistrement ; Ouvrir reprend un .wbb sans sélectionner sa scène. Préserver les programmes incomplets et les blocs importés, même incompatibles avec l'activité courante ; le préflight refuse leur exécution, pas leur édition. Enregistrer sous puis Enregistrer sur le même fichier, sans autosave permanent.

L'enseignant organise la progression et l'évaluation. Moodle et le dossier personnel peuvent distribuer et recevoir les .wbb. Pas de compte, classement, note, historique d'essais, suivi de maîtrise, déblocage automatique ou atelier de création d'activités complexe.

**Hors ligne** signifie sans Internet ni service externe pendant le parcours normal, une fois la session scolaire disponible. La perte du LAN nécessaire à la connexion et aux fichiers réseau est hors de ce périmètre (#476/#525). La simulation locale avec Webots reste le produit ; pas de promesse de navigateur distant autonome.

## Architecture et sûreté

`activité/profil → Blockly → AST neutre → préflight → interpréteur partagé → backend`

Webots **R2025a**, physique native à **8 ms**, capteurs frais, contacts et oracles comportementaux indépendants, admission/identité/horloge/liveness, STOP/RESET/LAND et échec irréversible avec LAND indépendant à **210 s**. Aucune amélioration de performance ou de simplicité n'autorise un affaiblissement de ces garanties.

[Décision #914 du 12 novembre](https://github.com/djibian/webeeblocks/issues/914) : le monde canonique scolaire est attesté intégralement avant READY, puis réputé statique durant son incarnation. Un changement/rechargement de monde exige une nouvelle incarnation et attestation ; RESET normal garde la géométrie inchangée. Les modifications directes GUI/Supervisor en vol sont hors périmètre et invalident la valeur de l'essai ; aucune promesse anti-triche. Le vérificateur continu historique reste un témoin d'ingénierie. La scène statique est intégrée par #970 ; ce résultat ne vaut pas acceptation graphique.

**Rendu natif à pleine résolution**, plafond par défaut **20 FPS**, sélecteur conservé conformément à la [décision du 27 novembre](https://github.com/djibian/webeeblocks/issues/914#issuecomment-7225500889). Ne pas relancer la recherche d'un autre réglage, WebGL/IPC séparé, WREN réduit ou trames compactes. Les mesures de performance restent distinctes de ce choix et ne changent ni la physique ni les exigences fonctionnelles.

## Livraison et pédagogie

La réussite native d'un témoin expert ne prouve pas que l'élève sait le construire. Évaluer la construction à partir d'un projet initial sans solution complète, l'explication, le diagnostic, la correction, l'autonomie et la manipulation du même fichier. Les nombres de blocs, variables, procédures et imbrications sont des descriptions, jamais des seuils automatiques ni une note pédagogique. Une réussite CI ou GO V5 n'est pas un PASS enseignant.

L'[exception propriétaire de première publication #1132](https://github.com/djibian/webeeblocks/issues/1132#issuecomment-7245759591) autorise v0.1.0 sans nouveau test enseignant. Elle ne modifie aucune règle V5 permanente et ne transfère aucun PASS historique. Le [FAIL #1114](https://github.com/djibian/webeeblocks/issues/1114#issuecomment-7223603624) demeure attaché à son candidat. Voir la [roadmap](ROADMAP.md) pour les objectifs qui restent à atteindre.

## Matériel réel : finalité distincte, conditionnelle

La référence matérielle est Crazyflie 2.1 + Flow Deck V2 + Multi-ranger + Color LED Deck inférieur. Couvrir les capacités pédagogiquement utiles avec un petit vocabulaire générique ; pas de nouveaux blocs spéculatifs. Simuler l'effet visible de la LED plutôt que son électronique.

La première preuve matérielle (#157) doit porter sur **un programme simple inchangé** entre Webots et le drone (`tools/physical/hover_range_comparison.wbb` : décoller à 0,50 m, attendre 1 s, mesurer devant, atterrir sur sol uniforme). Ce témoin n'autorise pas de vol. L'hôte de confiance, la session radio, les capacités requises, la fraîcheur, les effets bornés, le watchdog, les accusés et la récupération gardent leurs autorités propres ; une capacité manquante ou une issue inconnue interdit l'effet ou sa répétition aveugle.

Une activité finale réelle (#72) ne peut être proposée qu'après preuves physiques distinctes sur le domaine retenu : préflight, marges mesurées, capteurs sous poussée, excursions, énergie, arrêt/récupération, autorisation explicite de l'enseignant. Pas à pas et modification en vol sont interdits sur le drone réel. Les 210 s simulées ne constituent pas une autonomie matérielle. Le Grand Prix simulé ne dépend pas de cette finalité ; #70 reste une recherche optionnelle Lab sur l'altitude monde lors de changements de surface, non un préalable sur sol uniforme.

Les décisions et preuves anciennes restent consultables dans l'[historique](HISTORIQUE.md). Toute intégration respecte [AGENTS.md](../AGENTS.md).
