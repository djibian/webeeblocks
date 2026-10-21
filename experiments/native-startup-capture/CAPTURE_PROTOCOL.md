# Protocole d'acquisition native — préparé, non exécuté

## Gate préalable

La qualification de cet hôte a échoué ; **aucune commande Webots de ce
document n'a été exécutée**. Il n'existe pas encore de backend de tracing
fork/exec validé ici. Les commandes GDB ci-dessous sont une procédure à
qualifier, pas une déclaration de support déjà fonctionnel.

Dans l'environnement final exact, exécuter `qualify.py` avant toute simulation.
Exiger la vraie pile de `intentional_fixture_segv`, les identités/mappings,
la distinction code 42 / signal 11 / wrapper 0 et l'archive vérifiée. Un code
77, une erreur de capture ou un prérequis inconnu interdit la simulation.
Le succès de ce prérequis n'autorise pas encore la chaîne fork/exec.

Ensuite, hors Webots, utiliser le mode `wrapper` de la fixture pour qualifier
la procédure GDB multi-inférieurs : identifier son `exec` enfant, conserver
le parent, observer le SIGSEGV du fils, sa pile, puis son véritable événement
de terminaison et le code 0 du parent. Vérifier aussi le cas normal `exit42`.
Pas de passage à Webots tant que cette chaîne et la clôture de tous ses
écrivains ne sont pas établies. Si la pile existe mais que l'identité ou les
sorties des descendants restent inconnues, conserver le refus de qualification.

## Garantie du processus natif

Les sources officielles du
[lanceur R2025a](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/launcher/webots-linux.sh)
ont été lues à `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b` : le shell prépare
LD_LIBRARY_PATH, QT_QPA_PLATFORM, chemins temporaires et DPI, lance
`bin/webots-bin` **en enfant**, puis attend ce PID. Il ne l'`exec` pas.
Suivre seulement le parent GDB, ou seulement le Popen de `xvfb-run`, ne suffit
donc pas. `follow-fork-mode child` seul peut aussi suivre un utilitaire de
préparation et abandonner le vrai lanceur.

Procédure à qualifier : conserver tous les inférieurs fork/vfork/exec depuis
le shell officiel, en gardant le Xvfb externe identifié séparément. Sur un
hôte approprié, le point d'entrée diagnostic est de la forme :

```text
xvfb-run -a gdb --nx --nh --args /bin/bash /usr/local/webots/webots <arguments originaux du cas>
```

Ne pas remplacer silencieusement l'environnement du shell par une invocation
directe de webots-bin. GDB et ses dépendances doivent être isolés : installer
un debugger ne doit pas mettre à jour Mesa, Qt ou libc de la cible. Si GDB
est extrait avec son propre LD_LIBRARY_PATH, restaurer explicitement dans
l'**environnement de l'inférieur** les valeurs natives figées, avant le run ;
vérifier les valeurs réellement obtenues au stop d'exec du binaire.

Réglages GDB de départ à valider sur la fixture :

```gdb
set pagination off
set confirm off
set debuginfod enabled off
set disable-randomization off
set detach-on-fork off
set follow-fork-mode parent
set schedule-multiple on
catch fork
catch vfork
catch exec
handle SIGSEGV stop print pass
handle SIGBUS stop print pass
handle SIGABRT stop print pass
run
```

Chaque événement est enregistré avant `continue`. Ne pas installer de
commande `continue` inconditionnelle qui ferait perdre le premier signal.
La conduite automatique éventuelle doit être validée sur les fixtures ; les
catchpoints imposent ici des stops volontaires qui ne sont pas des crashs.
Le debugger perturbe l'ordonnancement : un succès instrumenté ne réfute pas
un défaut intermittent ni ne prouve l'équivalence temporelle au lancement CI.

Au stop d'exec du vrai binaire, établir un enregistrement unique : numéro
d'inférieur, PID syscall, PID procfs, chaîne `NSpid`, namespace PID, boot ID,
start ticks, temps UTC/monotone de l'observation, PPid, groupe/session,
commande, chemin réel, inode/device, taille/SHA-256/Build ID. Même contrôle
pour Xvfb, shell, contrôleurs et leurs descendants ; l'arbre doit conserver
les relations antérieures lorsqu'un parent disparaît. Résoudre le PID procfs
dans l'arbre possédé, avec namespace correspondant, jamais par nom ou en
supposant `/proc/<Popen.pid>` correct.

À partir de cette identité vérifiée et du stop effectif, `snapshot.py`
conserve `/proc` et les objets mappés :

```text
python3 snapshot.py --proc-pid <PID-procfs> --start-ticks <naissance> \
  --boot-id <boot> --exe-sha256 <SHA-binaire> --output <dossier-neuf>
```

Les bibliothèques sans identité inode/device concordante restent inconnues,
avec raison conservée ; ne pas convertir l'erreur en empreinte valide.
Répéter le snapshot au signal et au READY observé si le même natif existe
encore. Les maps initiales seules omettent les chargements tardifs de plugins
Qt/Mesa/DRI. Conserver les objets nécessaires à l'analyse du core ou leurs
paquets exacts et un moyen vérifié de les récupérer.

Au premier signal inattendu, avant toute reprise de la cible :

```gdb
info inferiors
info threads
info registers
info sharedlibrary
info proc mappings
thread apply all bt full
generate-core-file /chemin/preuve/webots.core
```

Sélectionner et étiqueter explicitement l'inférieur fautif. Sauvegarder la
pile de chaque thread utile de cet inférieur ; les piles d'un shell ou de
Xvfb ne sont pas celles de Webots. Conserver signal, `siginfo` si accessible,
PC/SP, registres, mappings, offset dans module, symboles/Build IDs et erreurs
de génération du core. Une pile utilisable peut suffire si le core est
impossible ; un simple texte `Segmentation fault` ne suffit pas.

Après sauvegarde, distinguer **signal arrêté** de **terminaison par signal**.
Laisser le debugger observer la livraison et l'événement final de l'inférieur,
avec son identité. Conserver séparément exit code normal, signal final,
code du shell, code xvfb-run, code GDB et toute terminaison imposée par le
collecteur. Ne pas déduire `SIGSEGV` d'un seul code 139 ni transformer un
timeout/kill du collecteur en crash spontané. Si le signal est intercepté par
la cible, le noter : la seule réception n'atteste pas sa mort.

## Environnement et preuves à figer avant le premier cas

- Exact HEAD #646, contenu/empreintes du runner et de ses sources composées,
  monde seed 1 archivé, layout, contrôleurs et assets R2025a récursivement
  manifestés. Comparer aux octets témoins, sans régénération implicite sous
  une autre branche. `world.wbt` tracking attendu : `7e2ee944…` ; statique
  attendu : `cbd1b953…`, seuls trois champs retirés.
- Même image Docker par digest `f0023e30…`, mêmes assets `c6793d8f…`, même
  renderer, topologie de contrôleurs, variables graphiques, XDG isolés et
  affichage froid par cas. Enregistrer image inspectée et binaires effectifs,
  version.txt et `webots-bin` SHA/Build ID. Ne pas utiliser l'environnement
  tar/TCP de #655 comme contre-épreuve prétendument identique.
- Xvfb et Mesa : paquets exacts, binaires/libs/plugins effectifs, arguments
  de l'affichage, DISPLAY, GL vendor/renderer/version observables, stderr X,
  QT_QPA_PLATFORM, LIBGL/MESA/GALLIUM/LP et LD_LIBRARY_PATH/LD_PRELOAD.
  Préserver les différences ou indisponibilités ; ne pas exposer les autres
  variables d'environnement (identifiants/secrets inutiles).
- Mémoire : limites processus/cgroup et membership réel, mémoire disponible,
  pression, pics et memory.events avant/au signal/après, événement OOM kernel
  et PID s'il existe. Si `/sys/fs/cgroup` ne correspond pas au membership,
  résoudre le chemin dans mountinfo ; ne pas attribuer les compteurs racine
  à Webots par défaut. Conserver les refus d'accès.
- Vérifier espace disque, sink core ou génération GDB, disponibilité exacte
  des symboles/objets pour l'autopsie et fermeture des écrivains. Le booléen
  WCOREDUMP ne remplace pas une archive core réellement relue.

## Petite expérience discriminante conditionnelle

**H1 :** le défaut se manifeste dans le chargement natif/graphique partagé,
sans nécessiter le suivi. **H2 :** l'initialisation du suivi est un déclencheur
propre au cas #646. **H3 :** le processus fautif est un auxiliaire plutôt que
webots-bin. Le PC/pile + arbre doivent d'abord départager la couche fautive ;
une pile dans Mesa peut encore résulter d'une corruption amorcée ailleurs.

Après les gates seulement : **maximum deux démarrages**, seed 1, ordre
tracking puis statique, une seule fois chaque variante. Ce n'est pas un
nouveau crossover à quatre démarrages ; l'information nouvelle visée est la
capture complète d'un signal et des identités, indisponible précédemment.
Le contraste porte exclusivement sur les trois champs de Viewpoint du même
monde et sur le même environnement figé.

Chaque cas est borné à 45 s murales de fonctionnement natif, avec retrait
contrôlé après vrai READY et 2 s d'observation de l'identité native. Ce délai
est un budget **diagnostic externe** ; il ne remplace aucun timeout ni oracle
du runner de production. Les arrêts volontaires GDB et l'autopsie sont
horodatés séparément. Aucun programme de vol ou requête MOVE/LAND/RESET n'est
ajouté pour ce probe de préparation.

**Arrêt de la campagne au premier signal, refus READY, défaut de capture,
timeout, changement d'environnement ou sortie inattendue.** Au premier échec
avec pile, autopsie et conservation immédiate avant toute nouvelle exécution.
Même un SIGSEGV sans pile arrête la campagne : c'est un refus de capture,
pas une justification pour recommencer jusqu'à obtenir une preuve.

Un crash statique réfute la nécessité du suivi pour **ce crash**. Un crash
tracking avec pile dans le suivi justifie l'examen de cette branche, sans
prouver seul la cause racine. Un auxiliaire fautif identifie un autre périmètre.
Deux succès laissent H1/H2 UNPROVEN et terminent ce protocole ; aucun
allongement de série n'est prévu. Aucun résultat de ce protocole n'existe ici.

Après chaque cas : fermer/récolter les vrais processus identifiés, conserver
les sorties naturelles/interventions, arrêter les écrivains, produire un
inventaire unique, vérifier tous les digests source → archive → réouverture,
puis publier sans écrasement. Les anciennes archives restent intactes.
La clôture doit être qualifiée dans le même domaine de namespaces ; le scan
de groupe #656 ne doit pas être présumé transférable sans cette vérification.

## Après identification éventuelle et qualification visuelle

Corriger seulement la couche démontrée : moteur/dépendance native, lanceur,
affichage ou capture selon les faits. Aucun changement caméra ou renderer
n'est justifié par le seul warning Mesa. Aucun changement de contrôle de vol,
LAND, RESET, Blockly, seuil, oracle ou READY ne fait partie de ce protocole.
Préserver le cas fautif pour une contre-épreuve du correctif, sans compter
des démarrages verts comme preuve universelle de disparition du défaut.

La validation du rendu est une phase distincte, après qualification suffisante
du démarrage : **retirer `--no-rendering` pour une acquisition dédiée**, même
Viewpoint R2025a conforme, cible nommée et smoothing 0.20. Capturer images ou
vidéo horodatées en approche, descente, passage sous H, sortie/remontée,
deux virages et pose centre/gauche/droite. Relier chaque image au monde,
temps simulé, position caméra/cible et résultat natif exact ; mesurer cadrage,
occlusions et cadence. Conserver les échecs de rendu sans les remplacer.

Un rendu logiciel avec Xvfb peut fournir des images natives, pas un PASS
humain ni la fluidité de Windows. La plateforme classe de référence et le
workflow élève doivent recevoir leur qualification propre ; la demande
humaine éventuelle ne passe que par le mécanisme V5 lorsque l'artefact exact
est prêt. Aucun TEST_REQUIRED n'est requis pour le blocage machine actuel.
