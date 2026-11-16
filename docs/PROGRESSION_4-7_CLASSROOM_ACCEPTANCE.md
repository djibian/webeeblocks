# Activités 4–7 — protocole d'acceptation pédagogique en classe (4e/3e agricoles)

**Statut : protocole proposé, aucun essai élève ni PASS revendiqué.** Complément du [protocole des activités 1–3](PROGRESSION_1-3_CLASSROOM_ACCEPTANCE.md), selon la [matrice 1–8 approuvée](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md) dans [#587](https://github.com/djibian/webeeblocks/issues/587#issuecomment-6826109034). Il sert à **réfuter** une activité pédagogique inadaptée, pas à remplacer une qualification Webots, une revue V5 ou une décision de l'enseignant.

**État du produit à ne pas confondre avec cette proposition :** l'activation publique de 4 est en PR [#1010](https://github.com/djibian/webeeblocks/pull/1010) ; les travaux de 5, 6 et 7 sont respectivement en PR [#980](https://github.com/djibian/webeeblocks/pull/980), [#981](https://github.com/djibian/webeeblocks/pull/981) et [#983](https://github.com/djibian/webeeblocks/pull/983). Ces PR sont des candidats de développement ; ne pas présenter leurs sondes privées ou leurs programmes de démonstration comme des exercices publiés ou déjà acceptés. Une validation est à refaire sur le **HEAD produit intégré exact**.

## Règles communes de l'observation

L'enseignant remet une **mission observable**, sans fournir le programme solution, des tests d'AST, un seuil télémétrique à recopier, la réponse attendue à une mesure ou une stratégie unique. L'élève regarde le monde, prévoit, construit son programme, exécute, constate une réussite ou une raison d'échec, explique puis corrige. L'aide apportée est consignée afin de distinguer autonomie et réussite guidée.

Pour chaque activité, comparer une première variante et une variante nouvelle **avec les octets du même projet .wbb**, sans adapter le programme aux obstacles rencontrés. La sélection du monde relève de l'interface et de l'enseignant ; elle ne doit pas injecter le nombre de portes, la variante, le résultat d'oracle ou une « réponse » dans Blockly. Une variation de blocs ou du fichier entre les essais annule la preuve de généralisation, mais pas les observations d'apprentissage intermédiaires.

Tester séparément : démarrer une activité depuis le sélecteur ; créer et modifier un programme ; lire les mesures visibles ; observer l'exécution et le pas à pas lorsqu'il est permis ; STOP et RESET avec identité de tentative fraîche ; **Enregistrer sous** dans le navigateur/OS réel ; fermer/rouvrir le même .wbb et vérifier qu'il reste éditable. Un aller-retour en mémoire ou un navigateur simulé ne remplace pas le dialogue de fichier scolaire. Noter l'OS, le navigateur, Webots R2025a, le SHA et la variante réellement lancés.

## Missions et contre-épreuves pédagogiques

| Activité | Consigne élève (sans algorithme) | Apprentissage à observer | Réfutations à provoquer |
| --- | --- | --- | --- |
| **4 — Observer pour décider** | « Deux parcours ont des passages différents. Avec **un seul programme**, observe ton environnement pour traverser sans toucher l'obstacle puis pose entièrement le drone sur le damier. » | L'élève explique ce qu'une **mesure** lui apprend et pourquoi une **comparaison** peut changer sa décision. Il réemploie les déplacements et les rotations. | Même stratégie aveugle sur les deux mondes ; mesure absente/non disponible ; confusion entre distance mesurée et déplacement ; franchissement incomplet ; collision ; pose hors cible. Tester les variantes au même point de décision, sans exiger un bloc particulier dans l'AST. |
| **5 — Explorer et garder le fil** | « Le trajet forme des cornières variables. Repère leurs changements et rejoins la destination avec le même programme, même si le parcours diffère. » | Répéter réellement **observer → décider → avancer** quand de nouvelles informations apparaissent, puis **conserver une information d'étape** lorsque la mesure initiale n'est plus utilisable directement. | Programme à deux lectures fixes, décision toujours prise avant le changement d'étape, trajet aveugle, boucle sans nouvelle observation, variable enregistrée puis lue immédiatement à partir d'un capteur encore disponible. Le succès technique de ces cas ne prouve pas l'apprentissage de mémoire. |
| **6 — Compter pour choisir** | « Sur la ligne droite, franchis les portiques ouverts dans l'ordre. À l'arrivée, utilise le nombre de portiques réellement franchis pour choisir la bonne zone parmi trois et pose entièrement le drone. » | L'élève distingue **détection** et **franchissement confirmé**, conserve un compte 1/2/3, puis le réemploie alors que le nombre ne se déduit plus des capteurs à l'arrivée. | Double comptage au voisinage d'un H ; retour arrière ; compte calculé d'après le seul décor final ; cible figée ; réussite d'une seule variante ; pose partielle ou en sustentation. Observer les trois configurations avec un seul .wbb. |
| **7 — Mini Grand Prix** | « Construis un programme autonome pour franchir un H ouvert, tourner, reconnaître le H final fermé et te poser sur la zone prévue. Réussis les deux parcours sans modifier ton projet. » | L'élève **transfère** séquences, hauteur, rotation, capteurs, conditions, boucles et observations dans une mission nouvelle, puis sait expliquer et corriger un échec. | Programme spécialisé à un parcours, absence de virage réel, non-franchissement complet du H, collision avec le fermé, pose partielle, sauvegarde réouverte différente, programme retouché entre L/R. Cette mission ne démontre **pas** le comptage 1/2/3 de l'activité 6 ou 8. |

### Trois tests discriminants indispensables

**4 → 5 : information à nouveau acquérir.** À l'activité 4, une mesure ponctuelle puis un SI/SINON peuvent suffire. À l'activité 5, vérifier sur les mondes physiques que **le changement suivant ne peut pas être correctement décidé avec la seule mesure initiale** : un programme aveugle ou figé doit échouer pour une raison physique. Aucun succès ne doit dépendre d'une vérification syntaxique de présence de boucle.

**5 → 6 : information à mémoriser.** L'activité 5 doit aller plus loin qu'un simple stockage immédiatement consommé : provoquer une étape entre la mesure et sa réutilisation, où la mesure ne suffit plus. L'activité 6 consolide cet acquis avec un véritable nombre de franchissements achevés. Une lecture directe du capteur juste avant le choix final, ou l'observation magique du nombre de H par l'oracle, ne doit pas tenir lieu de mémoire. Ne pas imposer une forme de variables, de procédures ou un nombre de blocs précis pour juger le résultat.

**6 → 7 : synthèse accessible.** Le Mini Grand Prix introduit **une nouvelle combinaison**, pas une nouvelle notion ni une copie raccourcie de l'activité 8. Vérifier la capacité de l'élève à expliquer ses choix plutôt qu'à reconstruire un programme expert caché. La complexité d'un témoin privé (par exemple un grand nombre de blocs) prouve au mieux une faisabilité technique ; elle ne constitue ni objectif de reproduction ni mesure d'accessibilité aux 4e/3e.

### Reconnaissance du H final : distinguer réussite et apprentissage

La réussite technique des variantes L/R **ne démontre pas à elle seule** que l'élève a reconnu le H fermé terminal en cours de vol. Le témoin privé d'intégration de l'activité 7 peut mesurer une distance **une seule fois au départ**, choisir ensuite un trajet de longueurs prédéfinies et terminer correctement avant le H fermé. Ce résultat valide l'oracle physique sur les deux mondes, **pas** la nécessité pédagogique d'une observation au voisinage du dernier obstacle. Il ne faut ni montrer ce programme témoin aux élèves ni retirer son GO technique sur cette seule base.

**Observation en classe, sans dévoiler de stratégie :** demander à l'élève de prévoir ce qui lui indique où terminer, de justifier la décision prise à l'approche du H fermé, puis d'expliquer ce qu'il changerait si le dernier obstacle était plus proche ou plus éloigné. Recueillir les mesures réellement disponibles au moment du choix et confronter la réponse de l'élève à l'exécution. **Ne jamais imposer** une seconde lecture de télémètre, une boucle ou une forme d'AST comme condition de réussite.

**Contre-épreuve de généralisation à concevoir, non encore qualifiée :** si l'on veut spécifiquement établir la reconnaissance sensorielle du H final plutôt que le seul transfert des notions précédentes, proposer après décision pédagogique une variation de son approche qui ne soit pas prédictible depuis l'indice initial. Le même fichier `.wbb` devra réussir les variantes physiques tandis qu'une stratégie entièrement prédéfinie devra échouer dans au moins l'une d'elles ; les télémètres utiles devront être mesurables et les verdicts natifs conserver franchissement, collision, virage, pose entière et RESET. Cette extension éventuelle réclame sa propre PR, ses contre-épreuves R2025a et un accord enseignant sur la difficulté. **Elle n'ajoute pas une troisième variante obligatoire à la matrice approuvée**, ne remet pas en cause le Mini Grand Prix L/R intégré et ne modifie aucune propriété de l'activité 8.

## Fiche d'observation minimale

| Champ | Observation à conserver |
| --- | --- |
| Provenance | SHA exact, activité, version Webots, OS, navigateur, scène, variante et projet .wbb initial |
| Autonomie | Mission reformulée, prédiction, stratégie initiale, type et nombre d'aides, blocage sur le vocabulaire ou les repères |
| Capteurs et choix | Mesure effectivement observée, moment où elle est utile, explication par l'élève, gestion d'une valeur indisponible |
| Essais | Résultat et motif d'échec réellement affichés ; collision, franchissement, stabilité de pose, RESET/STOP et tentative nouvelle |
| Généralisation | Deux ou trois variantes selon l'activité, même projet .wbb vérifié, aucune modification entre les variantes |
| Révision | Diagnostic formulé avant aide, correction choisie par l'élève, raison observable de l'amélioration ou de l'échec persistant |
| Fichiers et interface | Démarrer/Ouvrir distincts, Enregistrer sous et réouverture du vrai fichier sur la plateforme scolaire, consignes et ergonomie |
| Décision | **PASS / FAIL / À REVOIR** par l'enseignant, pour ce profil/monde/version, avec limite et correction demandée |

Les observations nominatives et les projets personnels restent dans les ressources scolaires prévues. Sur GitHub, conserver seulement des descriptions anonymisées et des reproductions techniques exemptes de données personnelles. **Aucun** classement, notation automatisée, déverrouillage d'activité ni historique de tentatives n'est créé.

## Frontières de décision

- **Qualification automatisée et native R2025a :** oracle indépendant, obstacles collisionnables, capteurs vrais, mêmes octets .wbb entre variantes, résultats positifs et négatifs, attestation de scène, RUN/STOP/RESET, refus des scènes mélangées, faux atterrissages, cadence et échec irréversible. La CI Draft et un témoin de pilote ne sont pas une CI Ready ni un PASS humain.
- **Observation pédagogique :** un élève découvre le parcours et construit une solution sans recevoir le programme témoin ; son raisonnement et ses corrections sont observables. Une réussite native ne suffit jamais à cette validation.
- **Intégration V5 :** HEAD Ready exact, vrai CI Gate réussi, contre-expertise indépendante, absence de réfutation non résolue, base actuelle et intégration conditionnelle. Une PR documentaire n'active aucun cours.
- **Frontière physique :** aucune scène ou réussite de simulation n'autorise le vol réel Crazyflie sans #157/#72 et accord explicite de l'enseignant. Les mondes, programmes, limites, oracles et règles de **l'activité 8** ne sont pas modifiés par ce protocole, pas plus que le chantier performance.
