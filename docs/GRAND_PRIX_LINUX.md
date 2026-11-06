# Grand Prix sur Linux — U historique actif et bac à sable variable limité

**Statut : incrément expérimental non accepté.** Le lancement **actif** ci-dessous
réutilise le Grand Prix **U de référence** (`gp-u-v1`, trois côtés de 2 m et
virages gauche, **sans cornières en L**). Il ne lance pas la nouvelle mission
variable décidée le 3 novembre 2026. Les 12 parcours variables et leurs
variantes personnalisées sont disponibles en **inspection statique inerte** ;
un bac à sable Blockly expérimental permet aussi l'édition, **sans READY ni
mission de vol qualifiée**. Voir
[#808](https://github.com/djibian/webeeblocks/issues/808) et
[#809](https://github.com/djibian/webeeblocks/issues/809).

L'objectif limité de cet incrément est de fournir une entrée directe **sans
Docker** qui assemble les composants existants du simulateur sur un poste
Linux disposant de Webots R2025a. Le vrai cycle graphique/Blockly et les
dialogues du système d'exploitation doivent encore être constatés sur un
poste adéquat ; la présence du script et ses tests statiques **ne valent pas**
`PRÊT POUR EMMANUEL`.

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

## Préparer et lancer

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
(0 à 65535). **Ce ne sont pas des configurations de la future course variable.**
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
`.wbb` sans modification sur une autre graine U, puis, quand #808/#811 auront
livré leurs mondes et oracles, sur une **vraie configuration variable**.
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
des dialogues OS. Le futur livrable #809 doit ajouter les configurations
de #808, l'oracle généralisé #811, les vrais essais natifs R2025a et le
cycle enseignant observé. Aucun vol physique, aucune acceptation pédagogique,
aucune modification du catalogue officiel des activités 2–7/8.
