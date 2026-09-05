# WebeeBlocks — classe Windows

Cette archive est prête à l’emploi après installation de Webots R2025a. Elle
contient le contrôleur Windows compilé, Blockly 13.2.1, le pont Robot Window et
les actifs Crazyflie nécessaires au fonctionnement hors ligne.

## Périmètre de la release

- cible de compatibilité : Windows 10 ou 11 64 bits ;
- Webots R2025a installé dans `C:\Program Files\Webots` (ou
  `WEBOTS_HOME` défini) ;
- **Google Chrome**, navigateur de référence actuellement validé.

La cible de compatibilité inclut Windows 10 et 11, mais les preuves réelles W1/W2
actuelles portent exclusivement sur Windows 11. Edge n’appartient pas au
périmètre Windows actuellement validé. Firefox peut
faire fonctionner une partie de l’interface, mais la parité des fichiers projet
n’est pas supportée à ce stade et reste suivie séparément par #87. Cette archive
ne revendique donc aucun faux parcours de secours équivalent à
`Ouvrir / Enregistrer sous / Enregistrer` dans ces navigateurs.

Ni Git, ni Node.js, ni npm, ni compilateur ne sont requis sur le poste élève.

## Installation et lancement

1. décompresser l’archive dans un dossier accessible en écriture, y compris un
   chemin contenant des espaces ;
2. utiliser Google Chrome comme navigateur de la Robot Window ;
3. double-cliquer sur `Launch-WebeeBlocks.cmd` ;
4. attendre l’état `PRÊT` dans la fenêtre Blockly ;
5. utiliser **Lancer le vol** ou les contrôles pas-à-pas de WebeeBlocks.

Le lanceur démarre Webots directement en mode temps réel : le parcours validé
ne demande pas de cliquer manuellement sur ▶ dans Webots.

Après préparation de Webots et extraction de cette archive, couper le réseau ne
doit pas empêcher le lancement, Blockly, l’exécution, le pas à pas, la remise à
zéro ou les fichiers `.wbb`.

En cas d’échec, vérifier que
`C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe` existe. Le fichier
`MANIFEST.sha256` permet de contrôler l’intégrité de chaque fichier livré.

## Validation réelle

Le parcours Chrome a passé sur le poste Windows faible de référence les gates
W1 fonctionnel et W2 stabilité hors ligne de 30 minutes consignés dans l’issue
#81. Cette preuve ne s’étend ni à Edge/Firefox, ni automatiquement à une future
release matériellement différente.

`WINDOWS-ACCEPTANCE.md` reste fourni comme modèle de revalidation lorsqu’une
future évolution rend un nouveau test réel nécessaire.
