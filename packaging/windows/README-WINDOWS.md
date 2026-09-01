# WebeeBlocks — classe Windows

Cette archive est prête à l’emploi après installation de Webots R2025a. Elle
contient le contrôleur Windows compilé, Blockly 13.2.1, le pont Robot Window et
les actifs Crazyflie nécessaires au fonctionnement hors ligne.

## Prérequis enseignant

- Windows 10 ou 11 64 bits ;
- Webots R2025a installé dans `C:\Program Files\Webots` (ou `WEBOTS_HOME`
  défini) ;
- Microsoft Edge ou Google Chrome recommandé. Firefox utilise le parcours de
  sauvegarde de secours et peut créer une nouvelle copie à chaque sauvegarde.

Ni Git, ni Node.js, ni npm, ni compilateur ne sont requis sur le poste élève.

## Installation et lancement

1. décompresser l’archive dans un dossier accessible en écriture, y compris un
   chemin contenant des espaces ;
2. double-cliquer sur `Launch-WebeeBlocks.cmd` ;
3. attendre l’état `PRÊT` dans la fenêtre Blockly ;
4. démarrer la simulation avec les contrôles Webots puis utiliser **Lancer le
   vol**.

Après préparation de Webots et extraction de cette archive, couper le réseau ne
doit pas empêcher le lancement, Blockly, l’exécution, le pas à pas, la remise à
zéro ou les fichiers `.wbb`.

En cas d’échec, vérifier que
`C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe` existe. Le fichier
`MANIFEST.sha256` permet de contrôler l’intégrité de chaque fichier livré.

Le support Windows reste **à valider humainement** tant que la fiche
`WINDOWS-ACCEPTANCE.md` n’a pas été remplie sur le poste de classe le moins
puissant.
