# Activités 1–3 — protocole d'observation en classe (4e/3e agricoles)

**Statut : protocole de qualification pédagogique proposé, non résultat d'essai.** Ce document applique la [matrice révisée approuvée dans #587](https://github.com/djibian/webeeblocks/issues/587#issuecomment-6826109034) et le contrat de [progression 1–8](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md). Il ne modifie aucun profil, scène, bloc, oracle, programme ou critère de sécurité. Il n'accorde aucun PASS pédagogique, aucune qualification d'un scénario Webots ni aucune autorisation de vol physique.

## Ce qui doit être observé

L'objectif n'est **pas** qu'un témoin technique termine la mission, mais qu'un élève puisse :

1. comprendre l'objectif concret en regardant la scène ;
2. concevoir **son propre** programme Blockly, sans recevoir un algorithme complet ;
3. prévoir ce qui va se passer, exécuter, puis confronter sa prévision aux observations ;
4. expliquer un échec et **modifier une décision** avant de relancer ;
5. enregistrer le projet avec **Enregistrer sous**, le rouvrir via **Ouvrir**, et retrouver un projet modifiable.

À chaque séance, conserver la même version de référence (commit exact, Webots R2025a et plateforme), une scène initiale réinitialisée, les mêmes consignes orales et la même politique d'aide. Les projets de départ sont des **modèles**, non des programmes solutions. Le lancement par « Démarrer une activité » et l'ouverture d'un `.wbb` sauvegardé doivent être testés séparément. Aucune tentative n'autorise une commande sur un Crazyflie réel.

Le protocole n'impose ni durée de réussite, ni nombre de blocs, ni forme d'AST. Les tests natifs de monde, d'obstacle et de pose restent **distincts** de l'observation des élèves.

## Activités et réfutations attendues

| Activité | Mission remise à l'élève, sans méthode | Apprentissages à rendre observables | Erreurs et contre-épreuves utiles |
| --- | --- | --- | --- |
| **1 — Prendre son envol en 3D** (`progression-sequence-v1`, scène `sequence-v1`) | « Depuis le départ bleu, pose le drone **entièrement**, immobile, sur le damier vert décalé. » | Repérer avant et gauche dans la scène ; choisir et ajuster deux distances horizontales et une hauteur de décollage ; expliquer une séquence. **Aucune** condition ni boucle. | Départ haut ou bas mais dans les bornes, distance insuffisante, axe confondu, arrivée partielle, mouvement résiduel. L'élève sait-il prédire la correction avant de modifier ? |
| **2 — Maîtriser l'altitude** (`progression-altitude-v1`, scène `altitude-v1`) | « Quitte le départ sous l'auvent, passe l'obstacle sans toucher le toit ni les parois et pose-toi sur le damier. » | Distinguer la hauteur **choisie au décollage** de la **montée relative en vol** ; coordonner translation et hauteur ; observer la nécessité de changer d'altitude au bon moment. Pas de capteur. | Départ directement trop haut sous l'auvent ; trajet rectiligne à faible hauteur ; montée trop tôt/trop tard ; contournement latéral ; contact ; pose partielle. L'échec doit résulter de la **géométrie physique observée**, jamais de l'absence d'un bloc vertical dans l'AST. |
| **3 — S'orienter et organiser son trajet** (`progression-orientation-3d-v1`, scène `orientation-v1`) | « Parcours les balises A, B et C dans l'ordre, en respectant les flèches et les hauteurs indiquées, puis pose-toi sur le damier. » | Distinguer *tourner de 90°* de *se déplacer latéralement* ; raisonner dans le repère local du drone ; réutiliser les changements d'altitude ; reconnaître un motif récurrent. | Pas de rotation réelle, mauvais sens de rotation, hauteur unique sur A/B/C, ordre erroné, pose hors cible. Une répétition bornée peut être utilisée mais sa présence dans l'AST n'est **pas** un critère de succès. |

### Question discriminante entre 1 et 2

Un élève peut réussir la première mission avec la seule hauteur initiale et des déplacements horizontaux. Dans la deuxième, le **toit bas au départ** et l'**obstacle plus haut que la trajectoire nominale** doivent lui faire comprendre pourquoi cette méthode ne suffit plus. L'élève doit pouvoir **expliquer les deux contraintes**, sans que la consigne lui donne l'ordre ou la valeur des blocs. Si un programme peut contourner trivialement l'obstacle, ou si le toit ne contraint pas réellement le décollage, ouvrir une correction du monde et refaire les épreuves natives ; ne pas « réussir » en imposant une syntaxe.

### Question discriminante entre 2 et 3

Les déplacements verticaux déjà rencontrés sont réemployés, mais l'activité 3 exige maintenant une **orientation réelle** aux balises : une translation vers la droite ou la gauche sans changement de cap ne doit pas suffire. Vérifier les flèches visibles et le cap physique réellement observé ; une simple succession de coordonnées visitées ne prouve pas la nouvelle compétence.

### Vérifier l'intérêt réel de la répétition dans l'activité 3

La géométrie comporte un motif de trajet réutilisable à deux endroits. Avant de programmer, demander à l'élève d'identifier **ce qui se répète dans l'espace**, puis de prévoir ce que le drone devra refaire après une première étape. Pendant les essais, distinguer une répétition d'actions correspondant à ce motif d'une boucle purement cosmétique (par exemple, découper un seul déplacement en deux). L'élève doit pouvoir expliquer ce qu'une modification du motif change aux deux endroits, **sans recevoir un programme solution**.

**Contre-épreuve pédagogique :** vérifier que le motif est réellement visible et compréhensible dans Webots, et que sa répétition aide à concevoir, expliquer ou corriger le trajet. Une réussite native avec `repeat(2)` ne démontre pas à elle seule cet intérêt pour les 4e/3e ; inversement, un algorithme équivalent sans boucle reste recevable par l'oracle. Consigner l'argumentation de l'élève et les aides nécessaires, non un nombre de blocs ni une forme d'AST imposée.

## Fiche d'observation minimale — une ligne par activité/élève

| Champ | Consigner, sans notation automatique |
| --- | --- |
| Référence | SHA, OS, navigateur, version Webots, profil et scène réellement chargés |
| Départ | Élève capable ou non de reformuler sa mission, avec aides indiquées |
| Première stratégie | Prédiction verbale, décisions qu'il a prises, difficultés de lecture de la scène/Blockly |
| Premier essai | Comportement réellement observé, éventuel échec et raison visible ; ne pas confondre verdict natif et compréhension |
| Révision | Diagnostic formulé par l'élève, modification effectuée, nombre et nature des aides, résultat du nouvel essai |
| Fichier | Enregistrer sous, emplacement choisi par l'élève, fermeture/ouverture et édition du **même** `.wbb` |
| Ergonomie | Lisibilité caméra/obstacles, repères, accessibilité des blocs, manipulation, stabilité RESET/STOP, message d'échec |
| Décision humaine | **PASS / FAIL / À REVOIR** de l'enseignant pour ce scénario exact, motifs et correction éventuelle |

Employer des identifiants anonymisés dans les retours publiés sur GitHub ; les fichiers `.wbb` personnels et les observations nominatives restent dans les ressources scolaires prévues, pas dans le dépôt.

## Séparation des validations

- **Technique automatisée :** scènes importables et isolées, profil/boîte à outils, oracles positifs et négatifs, refus de collisions/poses incorrectes, identité de tentative, RESET, absence de dégradation des contrats et CI exacte. Une réussite du script de test ne prouve **pas** l'autonomie d'un collégien.
- **Utilisabilité réelle :** réaliser le cycle complet dans Webots/Blockly sur la plateforme représentative, jusqu'à Save/Open/RESET et aux raisons d'échec. Les observations ne doivent pas commencer à partir d'un `.wbb` expert déjà résolu.
- **Acceptation personnelle :** l'enseignant décide sur des traces reproductibles ; une PR Ready, un GO V5 indépendant ou un `CI Gate` vert ne valent pas PASS pédagogique.

Ne pas ouvrir d'historique de tentatives, de notation ou de suivi automatisé de l'élève pour ce protocole. Les activités 4–7 feront l'objet de leur propre qualification. **L'activité 8, ses mondes, programmes, règles et oracles restent intacts.** Aucune qualification de vol réel n'en découle.
