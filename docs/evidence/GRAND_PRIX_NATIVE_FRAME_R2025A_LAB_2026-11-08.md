> **Provenance et portée (archive historique).** Rapport expérimental communiqué au projet le 8 novembre 2026, concernant le binaire Linux Webots R2025a et l'adaptateur de laboratoire spécifique à un ELF. Ces mesures ne constituent **ni un patch source Webots reproductible Windows/Linux, ni une qualification de sécurité des mutations, ni une acceptation d'usage GUI/Windows**. Les hooks et binaires expérimentaux ne sont pas inclus dans cette archive documentaire. La reprise dans le produit exige les preuves et revues distinctes définies dans [#910](https://github.com/djibian/webeeblocks/issues/910), [#911](https://github.com/djibian/webeeblocks/issues/911), [#913](https://github.com/djibian/webeeblocks/issues/913) et [#914](https://github.com/djibian/webeeblocks/issues/914). La référence #906 reste autoritaire jusqu'à ces validations. Les chiffres et limites ci-dessous sont reproduits comme **preuve rapportée**, non comme reproduction machine indépendante.

---

# Trame native du Grand Prix · preuve expérimentale R2025a

## Résultat

Le moteur Webots expérimental fournit pose, orientation, vitesses, contacts et révision du monde à chaque pas physique. Sur le même parcours et le même hôte, la supervision expérimentale utilise **3 requêtes synchrones par pas en vol**, contre **139** avec #906. Le débit en mode rapide sans rendu passe de **1,08–1,11× à 7,85–8,76×**. Le p99 de la chaîne native, de la capture dans Webots à la validation dans l’évaluateur, est de **0,15–0,21 ms**. L’expérience démontre que le travail de scène peut sortir du chemin critique en régime stable.

Le moteur a également enregistré les deux déplacements d’une cornière à **3080 ms**, alors que l’état final du monde est identique à l’état initial. Le mode expérimental révoque READY et maintient la révocation. La couverture des mutateurs et la validation de la révision au moment de l’action restent à établir avant toute utilisation comme autorité du produit.

## Référence et modification du moteur

- WebeeBlocks `main` au SHA `2e84c333a7bd71e2836b7fbb49a595978062fbc1`, intégrant #906. Parcours GD index 5, `gp-route-v2-L2000-2500-3000-TGD-s105-H2`. [Intégration de #906](https://github.com/djibian/webeeblocks/commit/2e84c333a7bd71e2836b7fbb49a595978062fbc1)
- Webots R2025a Linux x86-64, binaire officiel SHA-256 `c12c65e8680b579d0f33c34be452f100a302bdecc6d9344becf356db4a675a1a`, sources et en-têtes au SHA `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. L’extension C++ est compilée à part, chargée dans le processus moteur et s’abonne à `physicsStepEnded`, après le post-traitement ODE. Elle instrumente en mémoire deux entrées natives, après vérification de leurs prologues, pour identifier l’origine des mises à jour physiques et des hélices. [Source du pas physique](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/engine/WbSimulationWorld.cpp#L247)
- A et B chargent le même monde et le même module. En A, l’instrumentation moteur et la publication de trame sont désactivées et l’évaluateur exécute #906. En B, le monde est attesté une fois par tentative. L’adaptateur de laboratoire remplace la relecture de la scène et des observations physiques par la lecture de la révision et de la trame. Il réutilise le pilote et les règles de l’évaluateur. Le mode parallèle conserve toutes les lectures et l’autorité de #906.

### Trame et état du monde

Chaque trame comprend une séquence, l’heure simulée, les identifiants natifs du drone et de l’évaluateur, la révision à la capture, la position, neuf composantes d’orientation, six vitesses et les contacts avec leur identifiant de solide. Webots lit les contacts descendants avec le même code natif que Supervisor. Le transfert par mémoire partagée ne bloque pas la physique. Le lecteur vérifie l’identité, le temps du pas, la séquence, la finitude, l’orientation et la cohérence de la publication. La charge utile est de **216 octets hors contacts**, plus **32 octets par contact**. Les capteurs de distance restent mesurés par le pilote et transmis par le canal existant. [Lecture de contacts et de pose R2025a](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/utils/WbSupervisorUtilities.cpp#L1989)

La révision courante est publiée séparément, y compris entre deux pas. Un changement après la capture se voit donc sans attendre la trame suivante. En mode expérimental, la vérification de scène compare cette révision à celle de la trame et à la dernière attestation complète de la tentative. Une trame incohérente ou périmée entraîne un refus. Une nouvelle tentative passe de nouveau par le mécanisme de RESET et une attestation complète.

## A/B · trois paires alternées sur le même hôte

Debian 13, AMD EPYC 9V74, deux contrôleurs synchrones externes TCP en boucle locale. Ordre A1, B1, B2, A2, A3, B3. Même monde, même scénario natif et même fenêtre de **3104 à 8096 ms simulées**, soit 624 intervalles de 8 ms par exécution. Les valeurs sont les plages des trois exécutions de chaque bras.

| En vol, mode rapide, rendu coupé | A · #906 | B · trame native |
|---|---:|---:|
| Vitesse simulée / murale | 1,075–1,107× | 7,847–8,758× |
| Pas mural moyen | 7,23–7,44 ms | 0,91–1,02 ms |
| Pas mural p95 | 9,46–9,86 ms | 1,32–1,35 ms |
| Pas mural p99 | 11,34–12,60 ms | 1,54–2,38 ms |
| Pas mural maximum | 14,31–19,91 ms | 4,19–4,99 ms |
| Temps mural dans `step(8)`, moyenne | 0,14–0,16 ms | 0,11–0,12 ms |
| Temps mural de l’évaluateur par pas | 6,99–7,18 ms | 0,70–0,78 ms |
| Temps CPU de l’évaluateur par pas | 3,46–3,57 ms | 0,64–0,72 ms |
| Requêtes synchrones dans l’évaluateur | 139 | 3 |

La réduction est **98 % en nombre de requêtes** et **environ 89 % en temps mural de l’évaluateur**. Le gain de débit apparié va de **7,1× à 8,1×**. `step(8)` et le pas mural sont mesurés indépendamment. Le premier comprend les attentes de synchronisation et la régulation du temps réel lorsque celle-ci est active.

| Chronométrage de la trame B | Moyenne | p95 | p99 | Plus grand maximum |
|---|---:|---:|---:|---:|
| Capture moteur + copie et validation côté lecteur | 0,025–0,028 ms | 0,031–0,041 ms | 0,062–0,093 ms | 0,287 ms |
| De la capture dans Webots à la fin de la validation, attente comprise | 0,073–0,077 ms | 0,113–0,123 ms | 0,150–0,208 ms | 1,841 ms |

Le budget de 1 ms est respecté au p99 dans ces trois exécutions. Un événement d’ordonnancement le dépasse ponctuellement. Le CPU moteur moyen de capture est de 0,0015–0,0017 ms par pas et le CPU de copie et validation côté lecteur de 0,024–0,028 ms. Le coût de préparation moteur est mesuré juste avant la publication. La seconde ligne couvre aussi le transfert et la mise à disposition après `step(8)`.

### Temps réel et Robot Window Blockly

En temps réel sans rendu, une paire distincte donne **0,917× en A et 0,937× en B**. L’attente moyenne dans `step(8)` augmente de 0,55 à 7,31 ms en B, tandis que le travail mural de l’évaluateur tombe de 8,06 à 1,05 ms. La régulation de Webots absorbe une partie de la marge obtenue.

Une paire supplémentaire utilise la vraie Robot Window Blockly 13.2.1 dans Chromium Headless Shell, Mesa logiciel sous Xvfb et un plafond d’affichage de 25 FPS. Le même AST lance TAKEOFF 0,4 m puis LAND. Le vol actif dure 8,768 s simulées dans les deux bras. Les ACK et le verdict négatif attendu sont vérifiés.

| Temps réel avec Blockly et rendu logiciel | A | B |
|---|---:|---:|
| Attente active avant lancement | 0,45× | 0,88× |
| Vol | 0,36× | 0,71× |
| Tentative terminée | 0,85× | 0,90× |
| Après RESET | 0,47× | 0,91× |
| Pas mural p99 en vol | 90,9 ms | 96,6 ms |
| CPU moyen Webots / évaluateur en vol, équivalents cœur | 1,51 / 0,19 | 1,22 / 0,08 |

La marge côté supervision améliore le débit sans suffire à lisser les pointes de rendu de ce banc logiciel. La paire graphique est une mesure Linux de laboratoire avec un navigateur headless par essai.

## Preuves fonctionnelles

- **Observation en parallèle.** Le moteur et Supervisor concordent sur **1504 observations** utilisées par l’évaluateur pendant le témoin vol–perte de service–RESET. L’écart maximal des composantes de pose, d’orientation et de vitesse est **zéro**. Les contacts descendants concordent en coordonnées, en nombre et en identifiant. L’autorité de ce témoin est celle de #906.
- **READY, ALIVE et RESET.** Les six exécutions A/B produisent le même manifeste natif. READY à 3072 ms, ACK TAKEOFF à 8096 ms, perte du service et LAND indépendant avec ACK à 10368 ms, ACK RESET à 10944 ms, READY frais à 12000 ms, puis second ACK TAKEOFF à 17024 ms. Le pilote et l’évaluateur franchissent une nouvelle époque. La révision reste constante pendant le vol nominal. Les seules attestations complètes utilisées par B dans les deux tentatives tombent à 2088 ms et 11016 ms, hors fenêtre A/B.
- **Déplacement et restauration au même instant.** À 3080 ms, les lectures Webots prouvent x = 2,10 m puis x = 2,00 m. La révision passe **2 → 3 → 4**. En parallèle, #906 conserve READY. Avec l’adaptateur expérimental, READY est révoqué dans ce même pas et reste révoqué 32 ms plus tard.
- **Ajout et suppression transitoires.** Un solide doté d’une boîte de collision est inséré puis retiré au même instant simulé. Le nombre de nœuds revient à 36. Les événements de champs et de topologie font passer la révision **0 → 2 → 4**. Le prototype révoque READY dans le pas courant. La révision est un témoin monotone d’événements, le même geste pouvant produire plusieurs notifications moteur.
- **Contacts avec les cornières.** Sur les parcours 0, 5 et 11, le banc excite physiquement les quatre bras par un chevauchement initial de 15 mm. Il obtient des points natifs réciproques sur **12 bras**, concordants entre la trame et Supervisor. Ce témoin sans décollage vérifie les contacts sur des obstacles, en plus des contacts au sol du témoin de vol.
- **LAND à l’échéance.** Admission à 3104 ms, ordre natif indépendant à **213104 ms** et ACK LAND à **215568 ms**. Le délai est exactement 210000 ms. Le témoin utilise le même pilote et le même oracle, avec une commande de décollage à 0,65 m pour pouvoir maintenir le vol. À 0,4 m, l’oracle avait déclenché une protection anticipée de vol bas. À 0,8 m, il avait refusé une excursion d’altitude. Les seuils restent les mêmes dans les trois essais.

## Périmètre des mutateurs et intégration éventuelle

**Limite reproduite sur une régénération PROTO.** La modification de `Floor.size` a émis des événements natifs de champs, de régénération et de remplacement de la racine. Webots s’est ensuite arrêté par erreur de segmentation, avant qu’une nouvelle trame puisse être comparée. Le crash a aussi été reproduit avec le module désactivé dans le même monde. Le cas est conservé comme diagnostic. Il ne valide pas une régénération complète, sa restauration ni la continuité de la simulation lors de cette édition.

Le module observe les signaux natifs des champs et paramètres du graphe, les modifications DEF/USE, les notifications d’ajout/suppression, la régénération PROTO et le reset du monde. Une reconstruction après changement de monde exige une nouvelle session. Les deux entrées natives instrumentées distinguent l’appel d’ODE qui met à jour les vitesses et l’animation des seules hélices visuelles du modèle épinglé. Les canaux textuels du pilote et de l’évaluateur ont une responsabilité distincte. [Restauration d’état](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/utils/WbSupervisorUtilities.cpp#L608) · [Pose et vitesse ODE](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbSolid.cpp#L1890)

La couverture démontrée concerne les chemins exercés dans les mondes de laboratoire. Les écritures natives qui bloquent les signaux, les interventions arbitraires sur ODE et toutes les intercalations de mutation avant action demandent une preuve séparée. L’adaptateur expérimental compare la révision au point de lecture de l’évaluateur. Une version produit doit aussi l’attacher au reçu utilisé par le pilote, à l’instant où l’effet est autorisé. Le laboratoire borne le vecteur à 128 contacts et refuse tout dépassement. Une qualification complète doit définir et éprouver ce plafond. Les binaires et hooks du laboratoire sont spécifiques à cet ELF Linux. Aucun résultat Windows ni GPU matériel ne se déduit du banc.

**Conclusion falsifiable.** Rejouer les deux bras sur les SHA fournis. Une révision constante sous vol nominal, deux augmentations à 3080 ms lors du déplacement/restauration, la concordance avec les observations Supervisor, les mêmes ACK et un p99 de transport/validation sous 1 ms sont des critères vérifiables dans les traces. La réduction de 139 à 3 requêtes par pas est la preuve que la nouvelle frontière supprime le travail de relecture sur ce parcours. La révision doit être rattachée à un point de validation atomique avant tout changement d’autorité. Un A/B sur un poste Windows modeste, avec les fenêtres Webots et Blockly visibles, reste le test de fluidité du produit.