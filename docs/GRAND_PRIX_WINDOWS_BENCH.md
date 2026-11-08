# Grand Prix — inventaire du portable Windows et protocole A/B (#914)

Ce premier outil documente **la machine réelle** du banc cible. Il ne lance
pas Webots et ne mesure **aucune** fluidité. Il reste indépendant de la future
bascule native #910/#911/#913, du rendu #912 et de la validation pédagogique.

## Inventaire hors ligne et sans droits administrateur

Sur le **portable Windows personnel**, depuis un dossier source préparé et
épinglé (pas les PC ni le réseau du lycée), ouvrir PowerShell et exécuter :

```powershell
$root = (Get-Location).Path
$sha = if (Test-Path -LiteralPath '.\TARGET_SHA.txt') { (Get-Content -LiteralPath '.\TARGET_SHA.txt' -Raw).Trim() } else { $null }
& "$root\tools\grand_prix\windows_host_inventory.ps1" `
  -WebotsHome 'C:\Webots-R2025a' `
  -BrowserExe 'C:\Program Files\Mozilla Firefox\firefox.exe' `
  -SourceSha $sha `
  -OutputPath "$root\host-reference.json"
```

Les chemins sont **des exemples à adapter**. Si aucun SHA de sources exact n'est
disponible, omettre `-SourceSha` ; la valeur JSON `null` interdit d'utiliser
ce relevé comme provenance du candidat. De même, `-BrowserExe` est facultatif
mais indispensable pour documenter le navigateur réellement choisi. Le dossier
de sortie doit exister ; un fichier déjà présent n'est jamais écrasé.
Pour comparer deux Webots, refaire l'inventaire avec des fichiers distincts
(`host-reference.json`, `host-native.json`) sur **la même machine**.

Le test d'inventaire exécutable localement sur Windows, sans Webots installé et sans réseau, est :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\ci\test_grand_prix_windows_host_inventory.ps1
```

Ce test vérifie le schéma et plusieurs refus, mais le résultat réel Windows/GL
et l'acceptation du Grand Prix restent distincts.

L'outil lit CIM/WMI et les exécutables locaux ; il écrit un JSON UTF-8 portant
Windows, CPU, RAM, GPU/pilote, version et SHA-256 de Webots R2025a, navigateur
optionnel et SHA exact fourni. **Pas de hostname, compte, numéro de série, MAC
ou chemin personnel dans le JSON.** Le GPU déclaré par Windows ne prouve pas
le moteur OpenGL réellement utilisé. Le champ `actual_opengl_renderer` reste
délibérément `null` : collecter séparément les sorties `webots.exe --sysinfo`
et les informations du contexte OpenGL **de la session GUI active**, les
vérifier et les joindre au relevé. Ne pas remplir ce champ par déduction.

## Protocole de performance à instrumenter séparément

1. Préparer des artefacts **exactement identifiés** de la référence #906 et
   des candidats ; vérifier hashes, Webots, monde, Blockly et même `.wbb`.
   Une archive Windows compilée et ses dépendances restent à fournir avant
   toute acceptation. Ne pas transférer un résultat Linux comme PASS Windows.
2. Dans une même session machine stable, garder viewport, résolution,
   programme, configuration, fréquence **physique 8 ms** et processus identiques.
   Répéter **au moins trois fois** et alterner l'ordre A/B (par exemple AB,
   BA, AB). Mesurer séparément lancement/attente, vol, fin de tentative,
   RESET + second décollage et parcours jusqu'à 210 s simulées.
3. Exécuter le parcours **5**, puis **0** et **11** ; la matrice **0..11**
   vérifie les obligations natives, sans substituer les moyennes de parcours
   aux tests de sécurité. Relever les profils visibles 60/30/25 FPS et le
   mode sans rendu **uniquement comme contrôle diagnostic**.
4. Pour chaque répétition, conserver le temps simulé/temps mur, les pas 8 ms
   horodatés (p50/p95/p99/max), la charge CPU/RAM par processus, images
   effectivement visibles/s, GPU/pilote, latences de Blockly et la provenance
   des compteurs. **Un FPS affiché n'est pas une preuve de vitesse physique**.
   Sans télémétrie réelle des pas et des images, déclarer les métriques
   `UNMEASURED`, jamais `0` ni `PASS`.
5. Exercices GUI obligatoires sur le *même* artefact : Pas à pas/Continuer
   (conserver comme réfutation le FAIL #905), capteurs, STOP/RESET,
   deuxième vol, Save As → modifier → Save → Open du **même** `.wbb`,
   réouverture après changement de parcours et absence de fallback U.
   Arrêter et documenter la première défaillance sans neutraliser une garde.

**Objectifs, non garanties :** vitesse simulée/murale ≥0,95× dans toutes les
phases stabilisées, p99 ≤25 ms et maximum cible ≤80 ms hors chargement
explicite, vue utilisable ~25–30 FPS. Le test portable réel et le verdict
pédagogique suivent exclusivement le checkpoint GitHub V5 autorisé,
après artefact complet et preuves natives. Cet inventaire, même conforme,
n'autorise ni publication ni vol réel.
