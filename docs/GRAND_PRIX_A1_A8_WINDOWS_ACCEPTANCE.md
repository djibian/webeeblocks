# Acceptation Windows réelle — progression Grand Prix A1–A8

**Statut : NON TESTÉ / NON PUBLIABLE.** Ce guide concerne uniquement l'archive unifiée de 35 mondes et huit starters, issue du SHA exact intégré et qualifié. Webots officiel R2025a, pas physique 8 ms, rendu natif, limite 210 s simulées, oracles et LAND indépendants. Les preuves automatiques, la préparation PowerShell et le smoke headless ne constituent pas le PASS enseignant.

## 1 — Identifier et vérifier le paquet

Sur le PC personnel Windows, consigner le système/build, CPU/GPU/RAM, navigateur et profil, version Webots, SHA Git exact, ID du run, de l'artefact et SHA-256 annoncé. Ne pas utiliser un ZIP historique, un ZIP A8 seul ni un autre HEAD. En PowerShell 5.1 :

```powershell
Get-FileHash -LiteralPath '.\WebeeBlocks-Progression-A1-A8-Windows-R2025a.zip' -Algorithm SHA256
```

Comparer les 64 chiffres au digest publié ; en cas d'absence ou différence, BLOQUÉ. Extraire dans un répertoire local neuf (sans droits administrateur), ouvrir PowerShell à sa racine. Vérifier le SHA Git contre le SHA annoncé, pas simplement son format.

```powershell
$ErrorActionPreference = 'Stop'
$env:WEBOTS_HOME = 'C:\Program Files\Webots'
if ((Get-Content -LiteralPath (Join-Path $env:WEBOTS_HOME 'resources\version.txt') -Raw).Trim() -cne 'R2025a') { throw 'Webots R2025a obligatoire' }
$sha = (Get-Content -LiteralPath '.\SOURCE_SHA' -Raw).Trim()
if ($sha -cnotmatch '^[0-9a-f]{40}$') { throw 'Source SHA invalide' }
Write-Host "Comparer ce SHA au candidat exact : $sha"
$counts = @(1,1,1,3,5,5,7,12)
$c = Get-Content -LiteralPath '.\COURSES.json' -Raw | ConvertFrom-Json
if ($c.profile -cne 'progression-grand-prix-a1-a8-v1' -or
    $c.physics_step_ms -ne 8 -or $c.fps_default -ne 20 -or
    $c.course_ids.Count -ne 35 -or (@($c.course_ids | Sort-Object -Unique)).Count -ne 35 -or
    ($c.variant_counts -join ',') -cne ($counts -join ',')) { throw 'Inventaire invalide' }
$seen = @{}
foreach ($line in Get-Content -LiteralPath '.\MANIFEST.sha256' -Encoding UTF8) {
  if ($line -cnotmatch '^([0-9a-f]{64})  (.+)$') { throw 'Ligne manifeste invalide' }
  $expected = $Matches[1]; $relative = $Matches[2]
  if ($relative.StartsWith('/') -or $relative.Contains('\') -or $relative.Contains(':') -or
      ($relative.Split('/') -contains '..') -or $seen.ContainsKey($relative)) { throw "Chemin invalide ou dupliqué : $relative" }
  $file = Join-Path (Get-Location).Path ($relative.Replace('/', '\'))
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Fichier absent : $relative" }
  if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) { throw "Fichier altéré : $relative" }
  $seen[$relative] = $true
}
$root = (Get-Location).Path
$actual = @(Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
  $_.FullName.Substring($root.Length + 1).Replace('\','/')
} | Where-Object { $_ -cne 'MANIFEST.sha256' })
if ($actual.Count -ne $seen.Count -or @($actual | Where-Object { -not $seen.ContainsKey($_) }).Count -ne 0) { throw 'Inventaire manifeste incomplet' }
if (@(Get-ChildItem -LiteralPath '.\worlds' -Filter '*.wbt' -File).Count -ne 35 -or
    @(Get-ChildItem -LiteralPath '.\Activites' -Filter '*.wbb' -File).Count -ne 8) { throw '35 mondes et 8 starters exigés' }
Write-Host "Intégrité : $($seen.Count) fichiers ; 35 mondes, 8 starters."
```

Puis lancer les 35 préflights, sans vol :

```powershell
$counts = @(1,1,1,3,5,5,7,12)
for ($a = 1; $a -le 8; $a++) {
  for ($v = 1; $v -le $counts[$a-1]; $v++) {
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File '.\Lancer-Progression.ps1' -Activite $a -Variante $v -WebotsHome $env:WEBOTS_HOME -ValidateOnly
    if ($LASTEXITCODE -ne 0) { throw "PREFLIGHT ÉCHOUÉ A$a/V$v" }
  }
}
```

Vérifier également le refus A1/V2, A8/V13 et l'association activité/indice incohérente. Aucun préflight n'est une mission réussie.

## 2 — Interface, fichiers et sécurité

Ouvrir `Lancer-Progression.cmd`, choisir explicitement une activité et une variante, obtenir la vraie scène et PRÊT. Tester Démarrer une activité : starter vierge, sans cible de sauvegarde. Construire un programme, provoquer une erreur intelligible puis corriger. Tester Enregistrer sous, Enregistrer, fermeture et réouverture du même fichier, dialogues natifs Windows et annulation sans mutation. Tester si possible Chrome/Firefox et le transport réellement utilisé ; noter cache, droits et profil réseau. Un simple chargement n'est pas un PASS.

**Portabilité** : ouvrir un programme A7/A8 depuis A1 : conserver les blocs, les valeurs (notamment 0,25 m/s), les variables et la scène A1, refuser les blocs non admis au lancement avant tout décollage. Sauvegarder et rouvrir sans perte ; si le profil courant ne valide pas le programme, conserver le profil source seulement s'il reste valide. Un import invalide ne doit changer ni fichier cible ni workspace. Puis ouvrir un programme simple compatible dans une activité ultérieure et vérifier la réutilisation. Ne jamais confondre ouverture et sélection de scène.

**Récupération** : A2 collision réelle, LAND indépendant, STOP/RESET et nouvelle admission sans état périmé. A7 : variable non initialisée avant vol, puis distance calculée négative après TAKEOFF, aucun MOVE invalide, STOP unique, attendre ACK avant RESET ; réinitialiser sans perte de programme et relancer. STOP manuel pendant une action, verrou si résultat STOP inconnu (ne pas provoquer artificiellement une panne non contrôlée sur le poste). Rebond A7 et recul conditionnel restent des preuves natives séparées. Ne jamais assimiler un statut affiché à une pose ou un RESET réussi.

## 3 — Campagne pédagogique et physique (35 variantes)

| Activité | Parcours | Observation nominale | Contre-épreuve |
| --- | --- | --- | --- |
| A1 | V1 | 1,4/1,8/1,6 m, virages G/D | Limite rouge, collision H fermé |
| A2 | V1 | H ouvert à 0,8 m, descente puis montée | Altitude constante, collision, RESET |
| A3 | V1 | Trois côtés de 2,50 m jusqu'au centre du damier, trois H ouverts | H manqué, altitude, mauvais virage |
| A4 | V1–V3 | Capteur frontal moins marge, pose à gauche | Valeur fixe, pose erronée |
| A5 | V1–V5 | Mémoire du sens, choix opposé | Mauvais damier autorise la descente mais refuse la mission |
| A6 | V1–V5 | Trois H ouverts/deux sans H, V2/V4 et V3/V5 indiscernables de face initialement | Capteur unique, collision, LAND indépendant |
| A7 | V1–V7 | 0/1 H sur un segment ou l'autre, procédures/boucles possibles | Erreur de calcul, STOP/RESET, 210 s |
| A8 | V1–V12 | Trois segments, deux virages, 1–3 H et cible selon le nombre | Mauvais damier, vol bas interdit, collision, STOP/RESET, 210 s |

Contrôler les centres de damiers à 0,30 m du H fermé (A1–A5) ou 0,50 m (A6–A8). A3 : H fermé à 2,80 m sur la troisième ligne. Bandes jaunes ±0,45 m autour des H ouverts ; rayon conservateur de 9 cm pour la sécurité du franchissement. Descente terminale seulement au-dessus d'un support vert de 28 cm ; cible correcte et centre à ±7 cm par axe, vrai contact Floor et 500 ms de stabilité dans la fenêtre native de 1500 ms. La descente sur un autre support n'est pas un succès. Aucun élargissement de bande ou déplacement du H pour réussir.

Pour chaque activité, construire un fichier de référence, en noter le SHA-256, puis ouvrir **le même fichier, sans modification**, sur toutes ses variantes. Vérifier après chaque vol son empreinte, verdict natif, temps simulé, pose, LAND. Toute erreur exige un résultat négatif explicite ; ne pas compter une mission interrompue comme réussite. Conserver les huit fichiers, captures, journaux, temps, mesures de fluidité/temps réel et les difficultés d'usage. Un plafond FPS n'est pas une mesure de performance graphique.

## 4 — Verdict

Rapporter pour chaque (A,V) : SHA source, SHA ZIP, SHA .wbb, Webots, PRÊT, verdict et cause, temps simulé, contact/stabilité, STOP/RESET/LAND, contre-épreuve, capture et observations pédagogiques. Statuts : PASS_ENSEIGNANT, FAIL, NON_TESTÉ, BLOQUÉ. Les 35 variantes, huit fichiers et négatifs doivent être conformes pour une acceptation globale. Seul le propriétaire donne le PASS enseignant sur le candidat essayé. Aucun vol réel Crazyflie, publication ou distribution n'est autorisé par ce protocole. Demander TEST_REQUIRED uniquement via le mécanisme V5 existant après intégration et qualification du SHA exact et préparation vérifiable du paquet.
