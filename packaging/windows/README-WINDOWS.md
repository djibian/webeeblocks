# WebeeBlocks — classe Windows

Cette archive est prête à l’emploi après installation de Webots R2025a. Elle
contient le contrôleur Windows compilé, Blockly 13.2.1, le pont Robot Window et
les actifs Crazyflie nécessaires au fonctionnement hors ligne.

## Périmètre de la release

- cible de compatibilité : Windows 10 ou 11 64 bits ;
- Webots R2025a installé dans `C:\Program Files\Webots` (ou
  `WEBOTS_HOME` défini) ;
- **Google Chrome**, navigateur de référence pour la baseline faible W1/W2 ;
- Firefox, qualifié séparément sur Windows 11 + Webots R2025a pour les fichiers
  projet directs `.wbb` et la présentation des boîtes natives.

La cible de compatibilité inclut Windows 10 et 11, mais les preuves réelles W1/W2
actuelles portent exclusivement sur Windows 11. Edge n’appartient pas au
périmètre Windows actuellement validé. Firefox dispose désormais d’une preuve
réelle indépendante : le checkpoint #481 a validé `Ouvrir`, `Enregistrer sous`,
`Enregistrer` sur le même fichier, les annulations neutres, l’absence de copies
numérotées et l’apparition spontanée au premier plan des boîtes de dialogue
natives. #87 est clos sur cette preuve. Cette qualification Firefox ne remplace
pas la baseline Chrome W1/W2 ni ses mesures du poste faible.

Ni Git, ni Node.js, ni npm, ni compilateur ne sont requis sur le poste élève.

## Installation et lancement

1. décompresser l’archive dans un dossier accessible en écriture, y compris un
   chemin contenant des espaces ;
2. utiliser Google Chrome comme navigateur de référence de la Robot Window, ou
   Firefox pour le parcours direct `.wbb` qualifié ;
3. double-cliquer sur `Launch-WebeeBlocks.cmd` ;
4. attendre l’état `PRÊT` dans la fenêtre Blockly ;
5. utiliser **Lancer le vol** ou les contrôles pas-à-pas de WebeeBlocks.

Le lanceur démarre Webots directement en mode temps réel : le parcours validé
ne demande pas de cliquer manuellement sur ▶ dans Webots.

Après préparation de Webots et extraction de cette archive, couper le réseau ne
doit pas empêcher le lancement, Blockly, l’exécution, le pas à pas, la remise à
zéro ou les fichiers `.wbb`. Pour Chrome, le cas où le profil/data-directory
Windows ou un contexte associé devient indisponible hors réseau reste isolé et
suivi par #476 ; ne l’interprétez pas comme une régression du broker Firefox.

## Démarrer une activité de la progression

L’archive contient le dossier `Activites` avec les huit fichiers `.wbb` de la
progression pédagogique, numérotés dans l’ordre. L’enseignant peut distribuer
l’ensemble du dossier ou seulement les activités qu’il souhaite rendre
disponibles.

Dans WebeeBlocks, cliquer **Démarrer une activité**, puis choisir le fichier
`.wbb` voulu dans `Activites`. Le titre, l’objectif, la boîte à outils et les
contraintes de cette activité sont alors appliqués par le même profil déclaratif
que dans le produit. Le fichier fourni est utilisé comme **modèle** : il ne
devient pas la cible d’enregistrement de l’élève. Pour conserver son travail,
l’élève choisit **Enregistrer sous** et crée son propre fichier ; ensuite
**Enregistrer** réécrit uniquement ce fichier choisi.

Le bouton **Ouvrir** conserve son sens habituel : il ouvre un projet de travail
existant et en fait la cible courante d’**Enregistrer**. Il ne remplace donc pas
**Démarrer une activité**.

En cas d’échec, vérifier que
`C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe` existe. Le fichier
`MANIFEST.sha256` permet de contrôler l’intégrité de chaque fichier livré.

## Validation réelle

Le parcours Chrome a passé sur le poste Windows faible de référence les gates
W1 fonctionnel et W2 stabilité hors ligne de 30 minutes consignés dans l’issue
#81. La qualification Windows Firefox directe `.wbb` est établie séparément par
le PASS #481/#87. Ces preuves ne s’étendent pas à Edge, à Windows 10, ni
automatiquement à une future release matériellement différente.

`WINDOWS-ACCEPTANCE.md` reste fourni comme modèle de revalidation lorsqu’une
future évolution rend un nouveau test réel nécessaire.
