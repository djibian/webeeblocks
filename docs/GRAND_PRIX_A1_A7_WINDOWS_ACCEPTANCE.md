# Acceptation Windows réelle — progression Grand Prix A1–A7

**Statut : NON TESTÉ / NON PUBLIABLE.** Ce protocole s'applique exclusivement
au futur ZIP qualifié de la nouvelle progression A1–A7 ; la PR #1100 prépare
sa livraison, **sans réutiliser le ZIP ni la pile native de #1075**. Le code intégré admet maintenant 23 variantes, mais ni cette admission,
ni un ZIP assemblé n'établissent la provenance, les vols natifs sur le SHA,
les dialogues graphiques ou le PASS enseignant. Le protocole de
préqualification graphique Linux/Windows est conservé dans
le dépôt, sans être requis hors ligne pour ce paquet Windows autonome.
Les préflights et CI automatiques ne constituent **jamais** un `PASS_ENSEIGNANT`. Autorité pédagogique : #587 et #1053 ;
contrat natif : `docs/GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md`.
A8 et tout vol Crazyflie physique sont hors de cette acceptation.

## 0 — Sélectionner le bon candidat (obligatoire)

Utiliser **uniquement** l'archive `WebeeBlocks-Progression-A1-A7-Windows-R2025a.zip`
provenant d'un run GitHub du **SHA exact** de la nouvelle implémentation,
avec `completed/success`, artefact identifié et SHA-256 publié.
Ne jamais substituer le ZIP du checkpoint historique #1063, un ZIP A8
ou un paquet issu d'un autre HEAD. La présence d'un ZIP sur une PR Draft
n'autorise pas sa distribution en classe.

Sur le **PC personnel Windows** choisi pour l'essai (pas le réseau administré
du lycée), noter : Windows/build, processeur/RAM/GPU/pilote, navigateur,
profil navigateur local ou réseau, version de Webots, connexion réseau,
SHA du commit, run, ID d'artefact et SHA-256 du ZIP. Un ancien profil
Chrome stocké sur un lecteur réseau peut empêcher « Enregistrer sous »
si ce lecteur est inaccessible : consigner le cas, ne pas le masquer.

Depuis le répertoire contenant le ZIP, ouvrir **Windows PowerShell 5.1** :

```powershell
Get-FileHash -LiteralPath '.\WebeeBlocks-Progression-A1-A7-Windows-R2025a.zip' -Algorithm SHA256
```

Comparer les **64 chiffres hexadécimaux** au digest publié pour **ce run**.
Si différents ou inconnus : **BLOQUÉ**, ne pas lancer.
Extraire le ZIP dans un dossier local ordinaire, sans privilège administrateur,
par exemple `C:\WebeeBlocks Essai\`. Ouvrir PowerShell dans le dossier
contenant `Lancer-Progression.cmd`, `SOURCE_SHA`, `COURSES.json` et
`MANIFEST.sha256`.

## 1 — Contrôles locaux reproductibles, avant tout vol

```powershell
$ErrorActionPreference = 'Stop'
$homeWebots = 'C:\Program Files\Webots'  # Adapter au chemin réel
$env:WEBOTS_HOME = $homeWebots
$version = (Get-Content -LiteralPath (Join-Path $homeWebots 'resources\version.txt') -Raw).Trim()
if ($version -cne 'R2025a') { throw "Webots incorrect : $version" }
$source = (Get-Content -LiteralPath '.\SOURCE_SHA' -Raw).Trim()
if ($source -notmatch '^[0-9a-f]{40}$') { throw 'SOURCE_SHA incorrect' }
Write-Host "Source réelle du paquet : $source"
$course = Get-Content -LiteralPath '.\COURSES.json' -Raw | ConvertFrom-Json
$counts = @(1,1,1,3,5,5,7)
if (($course.physics_step_ms -ne 8) -or ($course.course_ids.Count -ne 23) -or
    (($course.variant_counts -join ',') -cne ($counts -join ','))) {
  throw 'Identité native / inventaire A1–A7 invalide'
}
$verified = 0
foreach ($line in Get-Content -LiteralPath '.\MANIFEST.sha256' -Encoding UTF8) {
  if ($line -cnotmatch '^([0-9a-f]{64})  (.+)$') { throw "Ligne manifeste invalide : $line" }
  $expected = $Matches[1]
  $relative = $Matches[2]
  if ($relative.StartsWith('/') -or $relative.Contains('\') -or
      ($relative.Split('/') -contains '..')) { throw "Chemin invalide : $relative" }
  $file = Join-Path (Get-Location).Path ($relative.Replace('/', '\'))
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Fichier absent : $relative" }
  $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -cne $expected) { throw "Fichier altéré : $relative" }
  $verified++
}
if ($verified -lt 46) { throw 'Manifeste incomplet' }
Write-Host "Intégrité vérifiée : $verified fichiers ; A1–A7 = 23 variantes."
```

**Tout échec est BLOQUÉ**, pas un signal pour modifier le monde, ignorer
le manifeste ou désactiver l'oracle. Comparer `SOURCE_SHA` au commit exact
du run enregistré, et non au numéro d'une PR historique.

### Préflights réels du lanceur Windows, sans vol

Sur l'installation extraite, la commande suivante valide la préparation
**PowerShell 5.1 de chacune des 23 variantes**, le chargement de session,
l'identité activité/indice et les ressources locales, sans ouvrir le simulateur
graphique ni produire un PASS de vol. Elle peut prendre du temps sur un vieux PC ;
ne pas modifier le paquet pendant l'opération.

```powershell
$counts = @(1,1,1,3,5,5,7)
for ($a = 1; $a -le 7; $a++) {
  for ($v = 1; $v -le $counts[$a-1]; $v++) {
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File '.\Lancer-Progression.ps1' -Activite $a -Variante $v -WebotsHome $env:WEBOTS_HOME -ValidateOnly
    if ($LASTEXITCODE -ne 0) { throw "PREFLIGHT ÉCHOUÉ A$a/V$v" }
    Write-Host "PRÉFLIGHT SEUL OK : A$a/V$v"
  }
}
```

Ces 23 préflights ne testent **ni** les boîtes de dialogue du navigateur,
**ni** les 23 réussites physiques. Refuser aussi explicitement une variante
hors catalogue (par exemple `-Activite 1 -Variante 2 -ValidateOnly`) :
la commande doit sortir en erreur **avant** la création d'une session.

## 2 — Essai graphique et fichier élève, par activité

1. Double-cliquer sur `Lancer-Progression.cmd`, choisir A1 puis la variante
   proposée. Exiger Webots **R2025a**, une scène native visible, Robot Window
   Blockly, passage à **PRÊT** et commandes répondantes. Refaire pour A2…A7.
   Si un sélecteur, écran, dialogue ou PID se fige : **FAIL** avec captures et
   heure, ne pas compter le simple chargement comme réussite.
2. Pour chaque activité, ouvrir **Démarrer une activité** et partir du
   **starter réellement vierge**. Construire soi-même une stratégie, provoquer
   au moins un échec réel, constater la cause affichée par l'oracle, corriger
   dans Blockly et relancer. Les témoins automatisés privés ne remplacent
   pas une construction enseignante/élève.
3. Vérifier réellement **STOP** pendant une action, **RESET** (nouvelle
   tentative sans héritage d'état) et **LAND indépendant**. Un STOP inopérant,
   un RESET qui recycle un résultat, ou un LAND forcé qui finit par
   `UNSAFE_OR_TIMEOUT` constituent un **FAIL**, jamais un PASS par omission.
   Conserver la trace complète et la configuration du cas négatif.
4. **Enregistrer sous** dans un dossier local → fermer totalement Webots
   → relancer **la même activité**, même ou autre variante → **Ouvrir**
   le **même fichier `.wbb`** → vérifier ses blocs éditables et son comportement.
   Tester le vrai dialogue Windows et non un transport simulé.
5. Quand le programme corrigé fonctionne sur la première variante, enregistrer
   une seule version de référence, noter son SHA-256, puis enchaîner **toutes**
   les variantes de l'activité **sans réécrire ni modifier** ce `.wbb`.
   Sur chaque variante, rouvrir le fichier et observer une vraie mission
   jusqu'à son verdict natif, contacts, pose entière et retour LAND. Reprendre
   `Get-FileHash -LiteralPath 'C:\chemin\programme-eleve.wbb' -Algorithm SHA256`
   pour attester que les octets n'ont pas changé. Un changement de contenu
   invalide la preuve « même `.wbb` ».
6. Relancer une variante déjà essayée après RESET et contrôler l'absence
   d'ancien état ou résultat affiché. Recueillir le ressenti (fluidité Blockly,
   temps réel effectif, délai des commandes, capacité à comprendre/corriger).
   Mesurer les performances réellement observées ; une cible FPS affichée
   ou un test natif headless ne prouve pas la vitesse graphique.

## 3 — Campagne de 23 variantes et contre-épreuves

| Activité | Parcours | Fonction à observer | Négatif indispensable |
| --- | --- | --- | --- |
| A1 | V1 | Séquence, 3 segments 1,4/1,8/1,6 m, 2 virages, pose | Limite rouge, altitude et H fermé final |
| A2 | V1 | Monter puis descendre pour H ouvert à 0,8 m, remonter | Hauteur constante, passage hors bande jaune |
| A3 | V1 | 3 virages gauche, trois H ouverts et pose | H manqué, collision et altitude incorrecte |
| A4 | V1–V3 | Même `.wbb`, longueurs variables, pose gauche 0,5 m | Mouvement fixe aveugle, pose latérale erronée |
| A5 | V1–V5 | Même `.wbb`, sens mémorisé, pose opposée | Mauvaise pose et fausse relecture du premier virage |
| A6 | V1–V5 | 3 H ouverts / 2 sans H, deux latéraux, H fermé | Capteur unique, front seul, collision, LAND de récupération |
| A7 | V1–V7 | Même `.wbb`, 2 segments, 0/1 H, gauche/droite | Changement de H/segment, TIMEOUT 210 s, STOP/RESET |

Pour A6, contrôler explicitement V1–V3 avec H et V4–V5 sans H, les
ambiguïtés frontales V2/V4 et V3/V5, la pose à 0,70 m du H final, et les
deux collisions négatives avec récupération LAND signalées dans #1080.
Rejouer ces contre-épreuves sur le SHA du livrable : les résultats
antérieurs sont des preuves historiques, pas un PASS transférable.
Aucune variante ne peut être écartée afin d'obtenir 23 PASS.

Pour chaque couple `(A,V)`, reporter : SHA exact, version de Webots, SHA-256
du `.wbb`, commande d'ouverture, READY, décollage, temps simulé final,
verdict natif et cause, collision éventuelle, pose entière/Floor, STOP, RESET,
LAND, test négatif et capture/trace. Distinguer résultat automatique, vol
Webots observé et compréhension pédagogique ; ne jamais déduire l'un des autres.

## 4 — Verdict et intégration

Par activité : `PASS_ENSEIGNANT`, `FAIL` (reproduction exacte),
`NON_TESTÉ` ou `BLOQUÉ`. La progression globale ne peut être acceptée
que si les **23 variantes** et les négatifs requis sont qualifiés sur **les
sept fichiers `.wbb` de référence**, avec sauvegarde/réouverture réelle,
STOP/RESET/LAND et examen du passage A7 → A8. Le PASS pédagogique est
une **décision humaine explicite du propriétaire**, attachée au candidat
effectivement essayé ; l'automatisation ne le publie pas à sa place.

Avant de demander le seul checkpoint V5 `TEST_REQUIRED`, il faut une
version native intégrée et qualifiée, un ZIP issu du SHA exact de `main`,
`CI Gate` canonique verte sur le HEAD Ready, revue indépendante
applicable et absence de réfutation pertinente non résolue. Ne pas créer
de second checkpoint tant qu'un autre est ouvert. L'essai n'autorise
aucun vol Crazyflie physique et ne modifie jamais le contrat A8.
