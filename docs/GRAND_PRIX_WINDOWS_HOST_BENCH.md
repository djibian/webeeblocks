# Grand Prix — collecte passive Windows (préparation du banc #914)

Ce premier outil de métrologie **ne lance ni ne pilote Webots** : il relève
les caractéristiques CPU/GPU/OS et mesure, à intervalle régulier,
l'utilisation CPU, la mémoire et les threads du **seul processus Webots**
sélectionné par PID. Il est destiné au **portable Windows personnel**,
sans compte cloud, réseau scolaire ni droits administrateur après préparation.
C'est une première brique de l'A/B, **pas encore un banc complet**.

## Conditions préalables

- Windows avec Windows PowerShell 5.1, Webots **R2025a** installé.
- WebeeBlocks à un SHA exact connu, même programme Blockly et même parcours
  pour A/B ; consigner séparément le SHA/empreinte de l'éventuel moteur Webots
  patché (le champ SourceSha désigne le code WebeeBlocks mesuré).
- Faire tourner **visiblement** le vrai profil Blockly ; régler taille de
  fenêtre, écran, rendu et alimentation de façon identique.
- Les expériences en mode sans rendu servent uniquement de contrôle négatif.
  Elles ne prouvent pas l'usage graphique acceptable.
- Ce script ne contourne pas le checkpoint humain V5.

## Usage (une mesure de 30 s)

Dans une console Windows PowerShell ouverte à la racine du checkout,
identifier le **PID Webots qui affiche la scène** :

~~~powershell
Get-Process | Where-Object { $_.ProcessName -match 'webots' } | Select-Object Id, ProcessName, CPU, WorkingSet64
~~~

Démarrer le parcours souhaité et stabiliser l'état observé.
Remplacer les valeurs entre chevrons ; cette commande est sur une ligne :

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\grand_prix\capture_windows_host.ps1 -SourceSha "<SHA complet de WebeeBlocks>" -CourseId "gp-route-v2-L2000-2500-3000-TGD-s105-H2" -Variant reference -WebotsProcessId <PID> -WebotsHome "C:\Program Files\Webots" -OutputDirectory ".\preuves-gp-reference-01" -DurationSeconds 30 -SamplePeriodMs 500
~~~

La sortie doit être un dossier **nouveau pour chaque essai**, contenant
metadata.json et samples.csv. Le script refuse de réutiliser un dossier,
un PID non Webots, un processus portant le même nom mais exécuté depuis
une autre installation, un remplacement de PID ou une version autre que
R2025a. Il n'écrit pas le nom de l'utilisateur, de la machine ni de série.

**Variables enregistrées :** SHA WebeeBlocks, empreinte SHA-256 de
l’exécutable Webots réellement sélectionné, route, variante, date UTC,
version et PID Webots, OS/build, CPU, RAM, modèle et pilote des cartes graphiques,
temps monotone, durée réellement échantillonnée, CPU cumulé et delta CPU
(100 % = un cœur logique), mémoire résidente/privée et threads.
La fréquence demandée et l'intervalle réel sont tous deux conservés.
Si Webots quitte durant la collecte, l'essai est invalide.

## Comparaisons à poursuivre après qualification de l'instrumentation

Sur la **même machine**, même programme .wbb, même parcours et même vue,
répéter au moins trois fois chaque variante en alternant référence/candidat.
Comparer séparément les phases d'attente active, vol stabilisé, fin de
tentative, RESET et réadmission. Documenter le vrai renderer OpenGL,
les paramètres de rendu (60/30/25 FPS), les ressources du pilote et de
l'évaluateur, et le comportement de la Robot Window.

**Limites explicites :** ce script ne mesure ni temps simulé, ni facteur
simulé/mural, ni durées de step(8) et leurs p50/p95/p99/max, ni FPS
réellement affichés, charge GPU, processus enfants ou latences Blockly.
Le modèle/driver GPU Windows n'atteste pas l'accélération OpenGL.
Ces preuves nécessitent une instrumentation native/évaluateur et une
observation GUI complémentaires, sans changer RESET, STOP, LAND,
capteurs, sécurité ou fichiers .wbb.

**Aucun seuil de performance n'est déclaré atteint** : la cible de #914
(au moins 0,95×, p99 du pas au plus 25 ms, vue lisible 25–30 FPS)
reste à établir séparément sur SHA et matériel exacts.
Aucun TEST_REQUIRED n'est demandé par cet outil.

## Contre-test Windows sans moteur Webots

La suite CI complète inclut le test natif `tools/ci/test_grand_prix_windows_host_capture.ps1` : un exécutable Windows local renommé `webots.exe` joue un processus mesurable et un second exécutable homonyme dans un autre répertoire est explicitement refusé. Les horodatages/échantillons et l'empreinte binaire sont vérifiés. Ce témoin **ne simule pas la physique**, ne qualifie pas l'interface réelle ni le matériel Windows personnel ; aucun PASS ne lui est attribué en dehors du contrat de capture hôte.
