# Grand Prix sur Linux — parcours variables expérimentaux

Le lanceur assemble le CoursePlan canonique, les L/H réels, le pilote natif,
l'évaluateur et la Robot Window Blockly existants. Le publisher natif de
l'évaluateur (#886) et le lancement actif (#890) sont intégrés. Un script absent,
arrêté ou incapable de prouver READY n'autorise jamais TAKEOFF. Le lanceur ne remplace aucune garde native et ne fournit aucun programme.

Les tests du lanceur qualifient sa composition et ses refus, **pas** le vrai
cycle graphique Linux, les dialogues OS, un parcours réussi, les 12 missions
ou l'acceptation pédagogique. Ce document ne déclare pas `PRÊT POUR EMMANUEL`.
Le bac à sable sans évaluateur et l'inspection inerte restent des modes distincts.

## Prérequis

- Linux avec une session graphique et **Webots R2025a** installé localement,
  pas une autre version. Connaître son dossier, par exemple
  `/usr/local/webots` (variable `WEBOTS_HOME` ou `--webots-home`).
- Sources de `djibian/webeeblocks` dans un dossier personnel **accessible en
  écriture**. Pour reproduire un résultat, relever le SHA exact avec
  `git rev-parse HEAD`. Ne pas travailler directement depuis une archive
  système en lecture seule.
- `python3`, `make`, compilateur C/C++ (pour le contrôleur natif), Bash.
  **Node.js 22 ou plus et npm** sont nécessaires à la préparation initiale des
  ressources Blockly ; celle-ci peut nécessiter Internet. Aucun accès root
  n'est demandé par le lanceur. La préparation garde la version Blockly
  contractuelle 13.2.1.

## Essai Linux au moyen d'un TEST_REQUIRED de confiance

**Ne pas lancer de test sur simple fusion ou CI verte.** Le profil
`grand-prix-linux-r2025a` (checkpoint uniquement) prépare dans le workflow
GitHub de confiance `human-checkpoint.yml` l'artefact
`WebeeBlocks-Grand-Prix-Linux-R2025a` associé à **un SHA de commit exact**.
Sa publication est interdite si les suites complètes Runtime/Webots ou la
préparation du paquet échouent, si l'archive/digest manque, ou si un autre
`TEST_REQUIRED` est ouvert. Le paquet **ne démontre pas** que la GUI a été
utilisée : c'est précisément l'observation demandée à l'enseignant.

Uniquement après création d'une issue `[TEST_REQUIRED] grand-prix-linux-r2025a`
par le mécanisme de confiance :

1. Télécharger **l'artefact du run indiqué dans l'issue**, extraire son ZIP
   dans un dossier personnel, ouvrir un terminal dans le dossier extrait.
2. Vérifier les fichiers avant extraction des sources :
   `sha256sum -c SHA256SUMS`, puis relever `cat TARGET_SHA.txt`. L'issue
   doit désigner **ce même SHA** et l'artefact doit porter son digest GitHub.
   Ne rien exécuter si cette vérification échoue.
3. Extraire `tar -xzf webeeblocks-source.tar.gz` ; se placer dans
   `webeeblocks/`. Il s'agit d'une archive de sources figées, **sans .git** :
   utiliser le SHA du `TARGET_SHA.txt` vérifié, pas `git rev-parse HEAD`.
4. Avec Webots R2025a, Python 3, Make/C++, Node.js ≥ 22 et npm disponibles,
   définir `WEBOTS_HOME` pour le répertoire d'installation de Webots.
   Exécuter successivement :

   ```bash
   python3 tools/grand_prix/launch_linux.py --index 5 --preflight-only
   python3 tools/grand_prix/launch_linux.py --index 5
   ```

5. Dans Webots, démarrer la simulation puis Blockly, créer un petit programme
   libre, observer les distances des capteurs et essayer Lecture, Pas à pas,
   Continuer, STOP et RESET. Un programme incomplet ou un échec de mission
   sont des résultats d'essai valables. Faire Enregistrer sous → modifier →
   Enregistrer → Ouvrir le **même .wbb**. Fermer Webots, relancer avec
   `--index 6`, rouvrir le **même .wbb** sans modification et vérifier le
   rétablissement du programme, les capteurs et une tentative fraîche.
6. Reporter **PASS** uniquement si l'ensemble du parcours d'interface
   demandé fonctionne ; sinon **FAIL**, avec la première action défaillante,
   sorties de terminal, version Linux et Webots, navigateur/Robot Window
   utilisé et observations factuelles. La réussite du Grand Prix ne fait
   **pas** partie de cette acceptation Linux initiale.

Le profil prépare une archive de sources complète à partir du commit exact,
la procédure française et un manifeste `SHA256SUMS`. Les dépendances
Blockly épinglées sont préparées par le lanceur au premier usage et peuvent
nécessiter un accès au registre npm ; les ressources officielles Webots
R2025a doivent déjà être installées sur le poste. Le checkpoint n'impose
aucune installation root ni vol physique.

## Lancer un parcours variable

Sur un checkout exact intégrant l'évaluateur qualifié, relever `git rev-parse HEAD`,
puis exécuter depuis le dépôt dans une session graphique :

```bash
export WEBOTS_HOME=/usr/local/webots   # adapter au poste
python3 tools/grand_prix/launch_linux.py --list-configurations
python3 tools/grand_prix/launch_linux.py --index 5 --preflight-only
python3 tools/grand_prix/launch_linux.py --index 5
```

L'indice **5** désigne le premier GD à longueurs mixtes 2 / 2,5 / 3 m.
Les indices 0 à 11 sélectionnent les douze références reproductibles ; cette
sélection n'établit pas leur qualification de vol complète. Pour reproduire une
variante canonique personnalisée, utiliser son identifiant hôte exact :

```bash
python3 tools/grand_prix/launch_linux.py --course-id gp-route-v2-L2000-2500-3000-TGD-s17-H2
```

`--index`, `--course-id` et `--legacy-u` sont exclusifs. `--seed` reste réservé
à l'ancien U. Aucun repli vers cet ancien monde n'est effectué en cas d'erreur.
Le préflight vérifie les ressources officielles épinglées, prépare Blockly
13.2.1, compose le Runtime route partagé et compile **le pilote de production**,
jamais une sonde. `--preflight-only` n'ouvre pas Webots et n'atteste aucun READY.

Le monde temporaire garde `grand_prix_route_flight`, `grand_prix_route_evaluator`
et `grand_prix_route_v2`. Les paramètres du CoursePlan restent natifs ; le
`.wbb` conserve son profil et son monde logique stables. Fermer Webots avant de
relancer une autre configuration : le nouvel évaluateur et le pilote repartent
dans un nouveau monde, sans hériter d'un ancien résultat.

Pour éprouver le premier cycle réel, sans chercher une solution gagnante :

1. Webots s'ouvre en pause. Démarrer sa simulation avec son bouton Lecture,
   puis attendre la connexion de la Robot Window. Le premier TAKEOFF Blockly
   attend également l'admission native, distincte du simple signal de connexion.
2. Construire librement le programme avec les blocs existants. Exécuter,
   observer les portées, utiliser Step/Continue, Stop puis Réinitialiser.
   Un essai incomplet ou incorrect ne constitue pas une réussite de mission.
3. Enregistrer par **Save As**, modifier puis **Save** : vérifier que le même
   fichier local est réécrit, sans copie numérotée. Éprouver aussi l'annulation
   d'Open/Save As, qui doit laisser le projet et sa cible inchangés.
4. Fermer Webots, relancer avec `--index 6`, puis ouvrir **le même .wbb**.
   Sans modifier le programme, vérifier l'espace de travail restauré et une
   tentative fraîche ; relever l'empreinte `sha256sum mon-programme.wbb` avant
   et après Open/Save sans édition. Ne pas convertir le projet vers le profil U.

Conserver le SHA du checkout, la commande et l'identifiant affiché, les versions,
la sortie du terminal et le fichier réellement utilisé. Ces observations ne
sont pas encore réalisées par les tests automatisés du lanceur. Aucun test
humain supplémentaire n'est demandé en dehors du mécanisme V5 existant.

## Préparer et lancer le U historique

Depuis la racine du dépôt, terminal ouvert dans la **session graphique** :

```bash
export WEBOTS_HOME=/usr/local/webots   # adapter au poste
python3 -m unittest tools.grand_prix.test_launch_linux
python3 tools/grand_prix/launch_linux.py --legacy-u --preflight-only
python3 tools/grand_prix/launch_linux.py --legacy-u --seed 4
```

Le préflight prépare les ressources Blockly, compose le contrôleur U depuis
le Runtime partagé avec vérification stricte des ancres, puis le compile avec
le SDK du Webots installé. **Il ne lance aucune simulation** et ne teste pas
le navigateur. Le lancement réel produit un monde temporaire dans
`worlds/`, lié au contrôleur natif, à l'évaluateur indépendant et à la
**Robot Window** `grand_prix_u`. Webots s'ouvre en mode graphique normal,
sans `--batch`, `--minimize`, Docker ni navigateur externe imposé.
L'évaluateur, la piste et l'échéance de 210000 ms proviennent du code U
existant ; aucun oracle n'est affaibli.

Choisir une autre graine historique avec `--seed 0`, `--seed 1`, etc.
(0 à 65535). **Ce ne sont pas des configurations des parcours variables.**
Fermer Webots avant de relancer un autre monde, afin de ne pas mélanger
deux évaluateurs ou tentatives. Le monde temporaire et son projet Webots
temporaire sont nettoyés après le retour du processus de lancement. Les
fichiers personnels `.wbb` enregistrés ailleurs ne sont pas effacés.

## Voir les 12 parcours variables, sans activer la mission

Le dépôt possède aussi une **inspection graphique statique** de la nouvelle
géométrie (longueurs indépendantes, virages GG/GD/DG/DD, cornières en L,
H ouverts et terminal). Elle est utile pour examiner les tracés sur le
poste Linux **avant** la qualification du vrai lanceur variable. Depuis la
racine du même checkout, avec `WEBOTS_HOME` et une session graphique :

```bash
python3 tools/grand_prix/launch_linux.py --list-configurations
python3 tools/grand_prix/inspect_static_linux.py --index 5
python3 tools/grand_prix/inspect_static_linux.py --course-id gp-route-v2-L2000-2500-3000-TGD-s17-H2
```

La première commande affiche les **12 indices (00 à 11)** et leur identifiant
`CoursePlan` reproductible, sans exiger Webots ni démarrer de simulateur.
La seconde vérifie les ressources officielles locales de **Webots R2025a**,
génère le monde temporaire correspondant puis l'ouvre graphiquement
**en pause**. Remplacer `5` par un indice de `0` à `11` pour visualiser
une autre variante ; fermer la simulation précédente avant d'en changer.
La troisième commande accepte **tout identifiant CoursePlan canonique** :
`L2000-2500-3000` code les trois longueurs en millimètres,
`TGD` les deux virages gauche/droite, `s17` la graine reproductible,
`H2` le nombre de H ouverts. Les domaines autorisés sont
`2000/2500/3000`, `GG/GD/DG/DD`, graine `0..65535` et `H1/H2/H3`.
Copier exactement l'identifiant imprimé pour rejouer la même scène.
`--index` et `--course-id` sont mutuellement exclus. Les identifiants
inconnus ou non canoniques échouent avant tout lancement Webots.
Aucun téléchargement réseau ni accès administrateur n'est effectué par
cet inspecteur.

**Frontière de sécurité :** cet aperçu affiche le Robot **sans contrôleur
actif ni Robot Window Blockly** et **sans évaluateur**. Il ne mesure ni
les capteurs ni les contacts, n'admet aucune tentative, ne permet ni
exécution du programme ni cycle `.wbb`, et ne démontre pas un rendu
visuel effectivement observé sur le poste tant qu'il n'a pas été ouvert.
Le véritable environnement enseignant (#809/#826), l'admission native
(#824) et les qualifications perception/contact (#825) restent à livrer.
Ne pas confondre cet aperçu avec le lancement historique `--legacy-u`.

## Bac à sable Blockly sur un parcours variable (sans autorisation de vol)

Un deuxième point d'entrée permet de **voir la Robot Window Blockly** du
monde variable complet et de préparer des essais manuels du cycle
`.wbb` sans attendre l'autorisation native de vol. C'est un **bac à sable
d'édition**, pas un simulateur de mission prêt à l'emploi. La piste et les
cornières L/H restent celles du `CoursePlan` canonique, le contrôleur natif
de vol est compilé depuis le Runtime partagé, mais le **contrôleur de
l'évaluateur est forcé à `"<none>"` dans ce monde temporaire**. Il ne peut
donc émettre ni READY ni ALIVE, même si une version ultérieure apporte un
publisher natif : TAKEOFF doit être refusé par le pilote.

```bash
python3 tools/grand_prix/launch_variable_editor_linux.py --index 5 --preflight-only
python3 tools/grand_prix/launch_variable_editor_linux.py --index 5 --editor-sandbox
python3 tools/grand_prix/launch_variable_editor_linux.py \
  --course-id gp-route-v2-L2000-2500-3000-TGD-s17-H2 --editor-sandbox
```

La première commande vérifie les ressources Webots R2025a et Blockly, puis
compose et compile le vrai pilote natif **sans démarrer Webots**. Les suivantes
ouvrent le monde généré en mode **pause** ; fermer Webots avant de sélectionner
une autre configuration. Il n'y a ni solution experte, ni programme imposé,
ni réécriture du fichier `.wbb` par la configuration hôte. Le monde
temporaire et **son seul** fichier de projet Webots sont retirés à la
fermeture ; les programmes `.wbb` enregistrés dans le dossier utilisateur
restent intacts.

Le lancement exige `--editor-sandbox` explicitement, vérifie la présence
d'une session graphique et refuse tout identifiant non canonique avant le
préflight. Les tests hôtes attestent l'identité du monde, l'impossibilité de
produire READY, le contrôle d'entrées et le nettoyage ciblé. **Ils ne prouvent
pas que l'éditeur ou les dialogues du système fonctionnent réellement** :
le cycle graphique Ouvrir / Enregistrer / Enregistrer sous sur Linux, les
capteurs en cours de mission, les 12 configurations actives et la réussite
pédagogique restent à qualifier. Ne pas utiliser ce bac à sable pour tester
une mission de vol. Son existence ne change pas le statut de livraison #809.

## Parcours utilisateur à vérifier (pas encore qualifié par ce script)

Dans la fenêtre Blockly dédiée : démarrer un projet **sans corrigé**, choisir
les blocs, observer les capteurs, lancer le vol, utiliser le pas-à-pas et
Continuer, arrêter/réinitialiser, modifier, **Enregistrer sous** dans le dossier
personnel, fermer puis **Ouvrir** ce même fichier `.wbb`. Relancer le même
`.wbb` sans modification sur une autre configuration variable, avec nouvel
évaluateur et résultat non hérité ; le U historique reste une expérience séparée.
Ne pas déduire de la réussite d'un simple décollage une réussite de la mission
ni une qualification de l'altitude 0,8 m du prototype #805.

Pour diagnostiquer : relever `git rev-parse HEAD`, `$WEBOTS_HOME/resources/version.txt`,
la graine, la commande exacte, les sorties du terminal et les étapes qui
échouent. Un défaut de préparation entraîne un **échec explicite** ;
l'absence d'interface, une erreur de dialogue de fichier ou un processus
Webots qui s'arrête ne doivent jamais être rebaptisés PASS.

## Frontière technique

Le test `python3 -m unittest tools.grand_prix.test_launch_linux`
falsifie uniquement l'identité des contrôleurs et de la fenêtre générée,
la reproductibilité, la version stricte et le refus du lancement graphique
sans affichage. Il **n'exécute pas Webots** et ne peut garantir l'ouverture
des dialogues OS. La livraison #809 exige encore les vrais essais natifs
R2025a applicables aux configurations choisies et le cycle enseignant observé.
La composition existante consomme déjà les modèles de #808 et l'oracle de #811 ;
leur présence seule ne qualifie pas une mission. Aucun vol physique, aucune acceptation pédagogique,
aucune modification du catalogue officiel des activités 2–7/8.
