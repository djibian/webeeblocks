# Grand Prix sur Linux — première entrée interactive, U historique uniquement

**Statut : incrément expérimental non accepté.** Cette commande réutilise le
Grand Prix **U de référence** (`gp-u-v1`, trois côtés de 2 m et virages gauche,
**sans cornières en L**). Elle ne réalise pas le nouveau parcours décidé le
3 novembre 2026. En particulier, elle ne livre **ni** les longueurs de segments
indépendantes 2/2,5/3 m, **ni** les virages GG/GD/DG/DD, **ni** les 12 parcours
variables demandés par [#808](https://github.com/djibian/webeeblocks/issues/808)
et [#809](https://github.com/djibian/webeeblocks/issues/809).

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
