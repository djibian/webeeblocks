# Qualification Windows R3 — laboratoire exact #778 (non publication)

**Produit :** `f243b2b597a2a6bd6af38e895787d9dd4bdfef5e`.
**Source Windows :** paquet #783, run `41285363676`, artefact `13075341081`.
**SHA-256 de l'archive GitHub contenant le ZIP :**
`07c5a175f80d1481794f4a064a3229984a4f008c5b457899de5c670f37a36f2b`.
**SHA-256 de l'exécutable C Windows dans le ZIP :**
`2c8f8e5da9370f4242e860e26952f2838c5cec7ffc5bd327161f1be49434c74a`.

## Préparation unique

1. Sur un poste **Windows interactif** avec **Webots R2025a** et **Google Chrome**, télécharger l'artefact `experiment-r3-windows-classroom-zip` depuis [le run #41285363676](https://github.com/djibian/webeeblocks/actions/runs/41285363676) (ne **pas** le décompresser).
2. Mettre cette archive ZIP GitHub et `Qualify-R3-Windows.ps1` dans un dossier accessible, sans autres fichiers personnels.
3. Ouvrir PowerShell dans ce dossier puis exécuter :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Qualify-R3-Windows.ps1 -ArtifactZip ".\experiment-r3-windows-classroom-zip.zip" -AutoCollisionReconstruction
```

Le paramètre `-AutoCollisionReconstruction` utilise **uniquement** le programme Blockly fictif des essais de collision : il provoque de vraies commandes Webots et vraie reconstruction, mais **bascule l'interface en mode Reconstruire dans la sonde** après deux collisions. Ce n'est **pas** la reproduction historique d'un `RESET_TIMEOUT` et ne doit jamais être présentée comme telle.

**Interaction humaine prévue :** fermer Webots normalement une fois lorsque le script l'indique, puis valider par Entrée. Dans le mode automatique, les blocs, lancement, remise à zéro, reconstruction et essais de refus sont pilotés via le véritable navigateur Chrome local sans remplacer la physique ni fabriquer d'ACK.

Le script crée sous `%LOCALAPPDATA%` un dossier privé de qualification, un profil Chrome **neuf**, un répertoire d'état natif dédié et un rapport `R3-rapport-expurge.json`. Il vérifie l'archive et chaque ligne du manifeste. **Aucun Python, Git, Node.js ou compilateur requis.**

## Limites et interprétation

- Le lanceur crée **un nouveau monde de session** à chaque double-clic : le second démarrage valide le **parcours scolaire normal**, pas la réadmission sur un **même chemin**. Cette dernière propriété reste `UNPROVEN` jusqu'à un test explicite à monde stable.
- La reconstruction interne conserve en revanche la **même** session de monde, le profil Chrome et son contexte ; la sonde exige un nouveau document et les mêmes empreintes SHA-256 Blockly et AST. `PRÊT` et `LIGHT` sont observés avec une vraie connexion WWI, sans inventer d'ACK.
- L'état `window.name` est observé **après** consommation, sans récupérer ni enregistrer la clé. Cela ne prouve pas à lui seul toutes les propriétés du handoff transitoire.
- `RESET ×2 / SCENE ×2 / CLEAR unique` restent `UNPROVEN` au niveau d'une **trace WWI C indépendante** si le rapport ne contient que les résultats de l'interface. Le code produit les impose, mais une affirmation de preuve native demande des captures distinctes.
- Ancien bearer et anciens ACK WWI ne sont jamais exportés ; la survie d'un ancien document reste `UNPROVEN` en l'absence d'un banc explicite.

**À transmettre :** seulement `R3-rapport-expurge.json`. Le dossier `PRIVATE`, les profils Chrome, fichiers natifs `OWNED`, `PENDING`, `.state.lock`, `.next` et checkpoints ne doivent **jamais** être partagés ni effacés automatiquement.

**Conditions avant GO d'intégration :** vérité de toutes les postconditions Windows avec observation native indépendante ; qualification de l'ancienne autorité ; revue indépendante du HEAD exact ; CI Gate complète + LAND/Grand Prix ; décision explicite du propriétaire. Aucun `TEST_REQUIRED` envoyé par cette expérimentation.
