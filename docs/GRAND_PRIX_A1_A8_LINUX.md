# Grand Prix sur Linux — prévisualisation depuis les sources

La version publiée [v0.1.0](https://github.com/djibian/webeeblocks/releases/tag/v0.1.0) est destinée à Windows. Linux dispose d'un lanceur enseignant A1–A8 depuis les sources ; ce chemin n'est pas une distribution Linux qualifiée pour les élèves.

## Préparer

Utiliser un checkout du dépôt dans un dossier accessible en écriture, avec une session graphique, Webots officiel R2025a, Python 3, Make, compilateurs C/C++, Node.js ≥ 22 et npm pour la préparation Blockly 13.2.1. Le menu graphique nécessite tkinter (python3-tk). La préparation peut nécessiter Internet. Relever le SHA avec `git rev-parse HEAD`.

Depuis la racine :

```bash
export WEBOTS_HOME=/usr/local/webots # adapter
python3 tools/grand_prix/launch_progression_linux.py --activity 1 --variant 1 --preflight-only
python3 tools/grand_prix/launch_progression_linux.py --menu
```

Pour choisir directement, par exemple :

```bash
python3 tools/grand_prix/launch_progression_linux.py --activity 8 --variant 1
```

Les variantes admises sont contrôlées par le lanceur natif ; A8/V1 à V12 correspondent aux indices de référence 0 à 11. Un préflight prépare les composants sans ouvrir le simulateur et ne prouve ni READY ni réussite de vol.

## Utiliser

Suivre le [guide utilisateur](GUIDE_UTILISATEUR.md) pour programmer, observer, arrêter, réinitialiser et enregistrer. Fermer Webots avant de relancer une autre variante et rouvrir le même .wbb. La sélection hôte ne doit pas changer le fichier ni divulguer une variante à son AST. Conserver SHA, commande, parcours et diagnostics en cas de problème.

La qualification graphique Linux réelle reste distincte des tests du lanceur et des preuves Windows. Les règles natives, la physique 8 ms, STOP/RESET/LAND et la limite 210 s sont inchangées.

## Historique et qualification

Le [guide Linux du checkpoint historique](GRAND_PRIX_LINUX.md) conserve les procédures exactes du prototype U, du lanceur variable A8, des aperçus inertes, du bac à sable et du checkpoint `grand-prix-linux-r2025a`. Ne pas utiliser ces chemins comme procédure de livraison A1–A8 ni modifier les protocoles de qualification. Seul le mécanisme V5 existant peut demander un TEST_REQUIRED.
