# Grand Prix variable R2025a — qualification expérimentale Windows

Extraire les deux ZIP du **même SHA d’assemblage** dans deux dossiers voisins
nommés `Webots-R2025a-experimental` (moteur) et
`WebeeBlocks-Grand-Prix-Windows` (projet). Utiliser un dossier local court et
accessible en écriture. Fermer les autres instances de Webots. Aucun Python,
Node ou Webots global n’est requis. Utiliser un navigateur local configuré
pour ouvrir la fenêtre Blockly de Webots. Si besoin, ouvrir « Fenêtre du robot »
depuis Webots. Attendre PRÊT avant de soumettre le programme Blockly.

Dans le dossier du projet, depuis PowerShell :

```powershell
.\Lancer-Grand-Prix.cmd --course 5 --fps 60 --arm A
.\Lancer-Grand-Prix.cmd --course 5 --fps 60 --arm B
```

A dessine à 100 %, B à 50 % de la largeur et hauteur de la cible 3D.
`--arm budget` ajoute un budget de dessin expérimental à B, à mesurer
séparément. `--fps` fixe le plafond d’affichage (25, 30 ou 60).
La physique conserve 8 ms dans chaque bras. Le lanceur vérifie le manifeste du moteur et ses empreintes, ainsi que les
empreintes des mondes et composants de code immuables du ZIP projet avant
exécution. Ce contrôle détecte les altérations après extraction ; il ne remplace
pas la vérification indépendante du SHA-256 de l'archive ni un test GUI. Les contrôleurs natifs du
parcours variable conservent l’autorité de READY, LAND et RESET.

Pour isoler l’effet de l’échelle, effectuer trois paires en ordre A/B, B/A,
A/B sur le même PC et le même pilote graphique. Garder le même fichier
`.wbb` (noter son SHA-256), parcours, plafond, taille de fenêtre et régime
secteur, avec Webots et Blockly visibles. Remettre le parcours à zéro
en fermant et relançant Webots entre les bras. Mesurer le même segment
d’au moins 30 secondes simulées consécutives en vol si le programme le
permet. Un arrêt de sécurité écourte l’essai et doit rester dans les
résultats. Pour établir la fluidité du Grand Prix complet, conserver
aussi un parcours terminé, l’issue native et les actions READY, RESET
et LAND. Relever vitesse, p99 natif, FPS observés et pauses visibles.

Garder les dossiers `traces` bruts (SHA, bras, commande, journal Webots
avec traces du moteur et du pas évaluateur, et fichier Webots
`--log-performance`). Les compteurs de swaps du moteur ne suffisent
pas à prouver un FPS visible. Ce test compare deux réglages du même
moteur. La comparaison officiel/candidat, qui exige deux moteurs
distincts, utilise le protocole
[GRAND_PRIX_WINDOWS_NATIVE_AB](https://github.com/djibian/webeeblocks/blob/main/docs/GRAND_PRIX_WINDOWS_NATIVE_AB.md).

## Inventaire et collecte CPU/RAM (uniquement lors d’un test V5 autorisé)

Les deux scripts PowerShell passifs sont inclus dans cette archive ; aucun
checkout Git ou téléchargement complémentaire n’est nécessaire pour eux.
Ils ne commandent pas le simulateur, ne valident pas la GUI ni les FPS visibles.
Depuis le répertoire du projet dans PowerShell :

```powershell
$sha = (Get-Content '.\TARGET_SHA.txt' -Raw).Trim()
$home = (Resolve-Path '..\Webots-R2025a-experimental').Path
& .\tools\grand_prix\windows_host_inventory.ps1 `
  -WebotsHome $home -SourceSha $sha -OutputPath '.\host-native.json'
Get-Process -Name webots-bin -ErrorAction SilentlyContinue |
  Select-Object Id, ProcessName, Path, StartTime
# Après vérification visuelle du PID exact du moteur dans $home :
$webotsPid = 12345  # à remplacer, ne jamais sélectionner arbitrairement
& .\tools\grand_prix\capture_windows_host.ps1 `
  -SourceSha $sha -CourseId 'route-5' -Variant candidate `
  -WebotsProcessId $webotsPid -WebotsHome $home `
  -OutputDirectory '.\cpu-A1' -DurationSeconds 90 -SamplePeriodMs 500
```

Créer un fichier d’inventaire et un dossier de capture nouveaux par essai.
Le script refuse un PID provenant d’une autre installation et un écrasement
silencieux. Le CPU/RAM d’un seul processus ne suffit pas pour conclure
sur la vitesse simulée/murale, le rendu visible ou la sécurité : conserver
aussi les traces natives et les observations de Blockly. Les fichiers de
journaux sont à examiner avant tout partage (chemins locaux possibles).
Aucune exécution humaine ni notification hors `TEST_REQUIRED` n’est autorisée
par ce simple conditionnement.
