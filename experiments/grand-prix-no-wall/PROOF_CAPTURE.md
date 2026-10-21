# #655 — clôture et conservation des preuves, sans Webots

## Portée et histoire préservée

Support expérimental des deux runners de `experiments/grand-prix-no-wall`,
uniquement sur Linux avec procfs **qualifié dans le namespace PID appelant**.
Aucun changement du programme Blockly/AST, monde, oracle, LAND, RESET ou seuil
210 s. Aucun fichier de #655, manifeste ou archive historique n'est réécrit.

Les divergences historiques s14/`node.log` et s5/`flight.log` restent des défauts
de preuve. Leur cause précise n'est pas établie. Une réussite nouvelle ne les
répare pas ; `achieved` seul ne vaut ni capture complète ni archive validée.

## Défauts réfutés et domaine du correctif

1. L'ancien scan comparait directement PGID syscall et `/proc/*/stat`, sans
   qualifier leur namespace. Le contre-exemple réel syscall PID/PGID 7 contre
   procfs PID/PGID 13903, `NSpid: 13903 7`, pouvait manquer le véritable fils et
   retourner un autre PID 7. **Aucune traduction de PID n'est désormais tentée.**
2. Les `poll()`/`wait()` des runners pouvaient récolter un leader avant le dernier
   signal au groupe. Le simple numéro `Popen.pid` ne réservait alors plus
   l'identité du groupe. Un PID récolté n'autorise plus scan/signal/attestation.
3. Les `finally` imbriqués pouvaient remplacer la cause native par un échec de
   clôture/nettoyage ; un `GP_U_NATIVE` était imprimé avant la clôture effective.
4. L'ancien texte « aucune archive publiée en cas d'échec » était faux après
   création du lien si la synchronisation du répertoire échouait.

La qualification exige :

- PID, PGID et SID de `self` égaux aux appels système ; `NSpid` singleton ;
  namespace PID de `self`, PID 1 et `pid_for_children` identiques ;
- montage procfs complet, racine `/`, sans `hidepid` non nul ; erreurs de lecture,
  permissions insuffisantes, structure inattendue ou ambiguïté = refus ;
- runner à un seul thread avec SIGCHLD par défaut, UID réel/effectif/sauvé/fs
  uniforme. Aucun autre récolteur, ptracer, changement concurrent de credentials,
  namespace ou montage ; les producteurs sont les programmes de confiance du
  protocole. Les tests injectés ne qualifient pas ces hypothèses sur un hôte réel.

Avant tout producteur, `spawn_writer` impose ce domaine et
`start_new_session=True`. Le leader direct est enregistré avec PID, parent,
PGID=SID=PID, naissance procfs, namespace et UID. Un échec d'enregistrement est
conservé dans le handle ; il interdit le signal et est levé à l'observation.
Le caller conserve immédiatement le handle, même en cas d'échec d'inscription.
Les contrôleurs TCP sont aussi revalidés par la clôture ; aucun échec
d'inscription ne peut obtenir de seal.

`observe_exit`/`wait_writer` utilisent `waitid(WEXITED|WNOHANG|WNOWAIT)` ; ils ne
font pas de `Popen.poll`, `Popen.wait`, `communicate`, ni de récolte implicite.
Le statut observé ne modifie pas `Popen.returncode`. Après sortie, le zombie
retenu conserve son PID. Les liens namespace d'un zombie peuvent disparaître :
son appartenance reste bornée par l'enfant direct non récolté et son NSpid
singleton dans le procfs qualifié. Les liens sont vérifiés pour un leader vivant.

`WNOWAIT` n'est pas à lui seul une protection universelle. Le mécanisme dépend
également du contexte sans autre récolteur, de l'identité enregistrée et du fait
que le fils est leader de session. Une autre session ne peut pas rejoindre ce
groupe. Un fils arbitraire, une naissance modifiée, ECHILD, un statut déjà
récolté ou une incertitude d'identité sont refusés **avant tout signal**.
Le namespace et l'identité sont revalidés après le scan, immédiatement avant
chaque `killpg`. Aucun signal ne suit la récolte des leaders.

## Enchaînement pour un nouvel essai

1. Qualifier l'hôte sans lancer de producteur :

   ```sh
   python3 experiments/grand-prix-no-wall/evidence_capture.py --qualify
   ```

   Refus = JSON `capture_host: REFUSED` et code 77. Les deux runners appliquent
   eux-mêmes cette garde avant leur préparation et avant `trial`.
2. Pendant l'essai, tous les leaders restent non récoltés. `close_capture`
   signale les groupes qualifiés (TERM puis KILL si nécessaire), attend leur
   absence de membres vivants, puis seulement récolte les enfants directs.
   Un échec ne récolte pas aveuglément les leaders dans un `finally` et n'autorise
   aucun signal fondé sur une identité devenue incertaine.
3. Tous les flux du parent, y compris `webots.log`, sont tentés à la fermeture.
   Le scan des FD same-UID refuse un écrivain détaché ouvert dans le dossier.
   Des erreurs multiples restent des objets accessibles par
   `capture_cleanup_errors`, avec notes sur Python >=3.11 et `capture_notes`
   et copie stderr sur 3.10. La cause native et son traceback restent primaires ; chaque autre
   nettoyage est tenté. Un échec de groupe ou de flux interdit le seal.
4. Une clôture réussie crée `capture-seal.json` **schema 2**, avec domaine procfs
   et identités des leaders, puis un inventaire strict `sha256.json`.
   Les anciens seals schema 1 sont refusés pour un nouvel archivage, sans les
   modifier. `result.json` garde le résultat natif même si la clôture échoue.
   `GP_U_NATIVE` et `GP_U_CAPTURE_CLOSED` ne sont imprimés qu'après clôture et
   nettoyages réussis ; aucun de ces messages ne valide une archive externe.
5. Après sortie du runner, appel externe distinct :

   ```sh
   python3 experiments/grand-prix-no-wall/evidence_capture.py \
     ci-artifacts/grand-prix-no-wall/<nouvel-essai> \
     <archive-nouvelle-et-unique>.tar.xz
   ```

   Source et manifeste sont vérifiés, archive temporaire écrite, membres exacts
   et SHA-256 relus, source recontrôlée, archive relue, mode 0444 + fsync,
   puis lien atomique sans remplacement et fsync du répertoire. La réponse
   d'archivage réussie est distincte des deux messages du runner.

Avant la tentative de lien, un échec ne publie pas de destination. Après la
tentative de lien, une interruption ou un échec peut laisser la destination
présente : l'exception porte `publication_uncertain=True`, `archive_destination`
et une note. **Inspecter la destination, sa provenance, ses membres et ses
hachages avant toute décision ; aucun retry aveugle ni suppression de la
destination.** Un conflit atomique FileExistsError connu ne crée pas de lien
par cet appel. Les erreurs de nettoyage du temporaire ou de fermeture du FD
répertoire ne remplacent pas l'erreur initiale. SIGKILL/panne machine ne peut
exécuter aucun handler : une absence de réponse après publication impose aussi
une reconstruction, même sans exception Python conservée.

## Tests et qualification restant ouverte

```sh
cd experiments/grand-prix-no-wall
python3 -m unittest -v test_evidence_capture.py test_capture_identity.py
GP_CAPTURE_REQUIRE_HOST=1 python3 test_evidence_capture.py
```

Le second appel exige réellement le domaine hôte : il retourne 77 si celui-ci
est indisponible, au lieu de revendiquer les douze tests historiques réussis.

Résultat local de cette réparation, Python 3.12.14 / Linux : **40 tests
recensés, 38 réussis, 2 tests réels non exécutables** (descendant après mort du
leader et FD détaché). Les douze méthodes historiques sont conservées : dix
réussissent, deux attendent un hôte qualifié. Les fixtures d'archivage injectent
explicitement un seal synthétique ; elles ne prouvent pas la clôture réelle.
Le mode strict et `--qualify` refusent cet hôte avec code 77 : procfs/syscall
divergent. Une création de namespace avec procfs propre est également interdite
par les permissions disponibles ; aucun contournement ni acquisition native.

Les modèles adversariaux couvrent namespace cohérent/divergent, 13903/7,
faux PID étranger, zombie retenu avec descendant vivant, escalade, PID récolté,
ECHILD/réutilisation, naissance/namespace/UID modifiés, revalidation après scan,
visibilité insuffisante, SIGCHLD/threads, FD détaché, erreurs natives et multiples
nettoyages, messages des deux runners, corruption/interruptions d'archive,
concurrence, fsync après lien et conservation de l'incertitude. Les modèles
mockent les signaux ; le seul test noyau additionnel crée et récolte son propre
fils pour démontrer WNOWAIT. Aucun signal modèle vers un processus extérieur.

**Non qualifié** ici : chemin positif complet sur Linux/procfs cohérent et
Python 3.10 de l'environnement R2025a visé. Le code évite les API d'exception
3.11 obligatoires ; cela ne constitue pas une exécution sous Python 3.10.
Exiger sur l'hôte réel, hors Webots : `--qualify` réussi, les douze historiques
réellement exécutés sans skip, et la suite additionnelle. Ne pas transformer
38 tests réussis en qualification complète.

## Limites et gates avant une acquisition native

L'attestation porte seulement sur les groupes connus et les FD same-UID
visibles, pas sur tous les écrivains possibles. Un descendant peut changer de
session/UID ; un écrivain inconnu sans FD peut rouvrir plus tard. Il faut un
dossier d'essai unique privé des autres producteurs, des programmes de confiance
sans changement d'identité et aucune nouvelle écriture après sortie. Les
vérifications de hachage ne sont pas un verrou permanent ; aucun acteur
privilégié hostile ni panne matérielle n'est couvert. Un refus ne garantit pas
le nettoyage complet : des processus restent éventuellement vivants, sans
nouveau signal tant que leur identité est incertaine.

Avant toute nouvelle acquisition : qualification hôte complète ci-dessus,
revue indépendante du correctif sur son HEAD exact (y compris les réfutations
13903/7 et réutilisation), état Draft/Ready et preuves CI applicables reconstruits,
puis protocole scientifique exact qualifié. Le diagnostic de crash pré-READY
#646/#655 a ses propres préconditions de tracing et le diagnostic LAND #638 ses
mesures de contact ; ce correctif ne les satisfait pas. Un seul nouveau s5
éventuellement discriminant exige nom et manifeste nouveaux et arrêt au premier
refus. Pas de rejeu des cinq positifs historiques, réparation de s14/s5 ou
campagne automatique.

#656 reste une pile expérimentale sur #655 : aucun CI Gate canonique observé
sur cette base non-main, aucun GO auteur et aucune autorisation de fusion de
la pile. La santé de main (#637) reste non restaurée. Pas de PASS pédagogique,
checkpoint matériel ou vol réel implicite.
