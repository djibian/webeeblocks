# Grand Prix — premier lanceur Linux, parcours U historique (#809)

**Périmètre limité :** ce lanceur ouvre Webots R2025a en mode graphique
avec le vrai contrôleur Grand Prix U, l'évaluateur indépendant et la Robot
Window Blockly du dépôt. Il utilise uniquement l'ancienne géométrie
gp-u-v1 à trois côtés de 2 m et deux virages à gauche. Ce n'est PAS encore
le livrable variable de #808/#809 (quatre orientations, longueurs mixtes,
cornières L, douze configurations). Ne pas confondre préparation machine,
succès CI et acceptation effective de l'interface par l'enseignant.

Sur Ubuntu, disposer d'un checkout WebeeBlocks accessible en écriture,
Webots R2025a installé avec ses ressources/headers, Python 3, make, g++,
une session graphique et un navigateur compatible. Définir WEBOTS_HOME
avec le dossier de Webots si celui-ci n'est pas détecté dans PATH.

Depuis la racine du dépôt, exécuter :

    ./tools/grand_prix/launch_linux.sh --check-only
    ./tools/grand_prix/launch_linux.sh --seed 4

Le premier appel vérifie les prérequis sans compiler, lancer ou réclamer
un test humain. Le second compile le contrôleur, génère un monde stable
(worlds/grand_prix_u_teacher_seed4.wbt) et lance la véritable GUI Webots.
Il ne lance pas Docker ni un vol réel. Les graines 0 et 1 sont également
essayables via --seed 0 et --seed 1 ; toute graine entière 0..65535 reste
dans le même U historique. Les mondes générés ne sont jamais écrasés
lorsqu'ils ont été modifiés ; la perspective Webots est conservée.

Sur le poste Linux, il reste INDISPENSABLE de vérifier l'affichage de la
Robot Window, Démarrer une activité, programmation Blockly libre, Play,
pas à pas/Continuer, capteurs/variables, Stop/Reset, Enregistrer sous,
Enregistrer, Ouvrir le même vrai fichier .wbb, puis essai sur une autre
graine. Aucun de ces gestes n'est déclaré passé par ce lanceur.

En cas d'échec, conserver la commande, la version R2025a, la sortie
complète et le monde exact. L'adaptation de ce lanceur aux vrais parcours
variables nécessite ensuite le générateur #808 et l'oracle orienté #811.
Aucun nouveau bloc, programme solution, PASS pédagogique ou vol physique
n'est créé.
