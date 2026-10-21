# SIGSEGV avant READY — #646 / #655, 21 octobre 2026

**Cause native : UNPROVEN. Aucune nouvelle simulation lancée.** L'acquisition
causale est interdite sur l'hôte examiné : le debugger ne peut pas tracer son
propre fils (`ptrace: Operation not permitted`). Les preuves nouvelles portent
sur les octets historiques et la qualification hors simulation de la capture.
Ce dossier ne modifie aucun lanceur partagé, caméra, contrôleur, PID de vol,
LAND, RESET, Blockly, cible, tolérance ou condition READY.

## Sujets et autorité

- Main lu intégralement : `b478f9dd1854d83345abe13ed20fcf7baeffaca5`.
  AGENTS / PRODUCT_VISION / ROADMAP : blobs `c1b0078103507e7b0132af948b34a5cbd7b5950a` /
  `df0b3b8591562f13f879db5c3f5ab78286b84cde` / `e8c4e246df15f223728f94743c958374176fccac`.
- #646 : Draft `b3cf056b8ecea916c970fba20bbb339375c53321`, base main.
  Ancien NO_GO [5573333140](https://github.com/djibian/webeeblocks/pull/646#pullrequestreview-5573333140)
  sur `c3326e0dd26a0b11be601348e668a8d2a35414b0` **non levé**.
  Revue [5599820400](https://github.com/djibian/webeeblocks/pull/646#pullrequestreview-5599820400) :
  UNPROVEN, conservée. Ce travail ne répète pas cette revue ni le contraste à
  quatre succès pour prétendre résoudre l'intermittence.
- #655 : Draft `6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7`, base #647
  `4e0e6b21e43c68c19049430b46751c41ccf6ce28`, elle-même sur #641.
  RESULTS.md, README, runners et commentaire de qualification
  [6316113276](https://github.com/djibian/webeeblocks/pull/655#issuecomment-6316113276)
  examinés. Aucun workflow retourné pour ce HEAD à la reconstruction ; aucune
  preuve CI Gate Ready n'en résulte.
- Run historique #646 [39266948873](https://github.com/djibian/webeeblocks/actions/runs/39266948873) :
  `pull_request`, `.github/workflows/ci.yml`, tentative 1, HEAD `c3326e0…`,
  failure ; job natif `118109077574` failure.
- Run [39275776688](https://github.com/djibian/webeeblocks/actions/runs/39275776688) :
  HEAD `3d6ecd6…`, tentative 1, success **Draft**.
  Run [39564769939](https://github.com/djibian/webeeblocks/actions/runs/39564769939) :
  HEAD `b3cf056…`, tentative 1, success **Draft**, job final `CI Gate (Draft)`
  `119108309187`. Aucun n'est un CI Gate décisionnel du HEAD Ready courant.

Le tronc reste non restauré selon les preuves applicables. La suspension V5
des fusions ordinaires est préservée ; aucun travail sur #637 ou #638,
aucun TEST_REQUIRED ni vol réel. Ce support nouveau demeure expérimental :
aucun GO auteur et aucune intégration ne sont revendiqués.

**Publication bornée : branche de diagnostic, sans ouverture de PR.** Sur ce
main, `.github/workflows/ci.yml` lance inconditionnellement le prototype
Grand Prix pour toute PR Draft interne ciblant main dès que son runner existe
(étape `Falsify simulation-only Grand Prix Draft prototype`). Ouvrir une PR
déclencherait donc des simulations supplémentaires sans ce tracing qualifié,
contrairement au présent mandat. Le workflow n'est pas modifié, aucune CI
n'est sautée ni revendiquée verte. La branche et les références depuis les
PR existantes conservent les preuves. Une PR de support restera Draft lors
de son ouverture ultérieure, seulement lorsque cet effet natif sera admissible.

## Octets effectivement extraits et comparés

Les trois ZIP GitHub ont été téléchargés et entièrement ouverts. Leurs
SHA-256 recalculés sont conformes aux références historiques :

| Artefact | ZIP SHA-256 | Mondes / manifestes examinés |
|---|---|---:|
|12193597782|`f017e3d1f7c84e420177100986de9e21a013c0e6c364eb8634ccbd1627e28b86`|11|
|12197204926|`c781622fe2fc68831114d0594ea792d38b51febd23b2c98d6a13fe21387feb74`|18|
|12329503523|`a08591122f676fa76d64b9cbb32ddc898867ec99a03513fc9e6d902e38fb6ccf`|20|

Zéro membre réclamé manquant et zéro divergence de ces 49 manifestes.
Le même monde seed 1 `7e2ee944f301483b0c86a83fefba02ec1fe67f856ae62fa36dcd35b6acff6edf`
a crashé dans `s1-witness-6d0b79629b` et réussi dans
`s1-witness-260af4b71f` : **comparaison des octets**, pas seulement des digests.
Il a aussi atteint READY dans `s1-wrong-landing-d0244322a5` du **même run
historique** que le crash. Ni seed ni sérialisation ne suffisent donc à
déterminer l'échec. Cela n'innocente pas le suivi comme facteur intermittent.

Les 12 tar.xz de #655 ont été ouvertes ; leurs tailles et SHA correspondent
à l'index publié. Les 11 mondes présents correspondent **octet par octet**
au générateur exact #655, avec les seules transformations TCP/assets du runner.
Le snapshot tardif s14 ne contient pas de monde ; il n'est pas inventé.
Les divergences historiques s14/node.log et s5/flight.log restent conservées.
Ce snapshot tardif ne contient que trois logs et un manifeste hérité : huit
membres réclamés sont absents et ses trois logs divergent. Il ne forme donc
pas une archive complète du scénario ; le contrôle strict le documente
séparément des 11 archives contenant un monde.

| Cas avant admission #655 | Monde SHA-256 | Résultat de l'extraction |
|---|---|---|
|s1|`50f0c8657be237d6f7b3e590a8ff1861607902148d39296e7daa694a5a06fcf6`|17 799 octets ; SIGSEGV shell-reporté du fils 47|
|s17|`dbe25c32c79256bff7332c0f5f99f7784ed071a73df344370e47782cc970394e`|16 601 octets ; SIGSEGV shell-reporté du fils 115|

Les deux mondes sont différents entre eux, mais ont chacun exactement :

```text
Viewpoint { orientation -0.45 0.47 0.76 1.05 position -5 -5 7 }
```

**Aucun `follow`, `followType` ou `followSmoothness`.** Leur absence est vérifiée
dans les mondes archivés, et non déduite du seul générateur. Les trois mondes
s3 historique/positif/deadline de #655 sont byte-identiques ; aucune analyse
du comportement de LAND n'est menée ici.

`evidence/archive-audit.json` conserve inventaires, mondes, champs, digests,
anomalies et comparaisons. Pour refaire cette inspection sans simulation :

```sh
python3 experiments/native-startup-capture/audit_archives.py \
  --candidate655 /chemin/checkout-exact-655 \
  --artifact-dir /chemin/zip \
  --output /tmp/archive-audit.json
```

Les ZIP doivent être nommés `artifact-<id>.zip`. Le script refuse un autre
HEAD #655, des modifications suivies, un mauvais digest ou une comparaison
de monde contradictoire. Les anciens fichiers ne sont jamais modifiés.

## Classification causale et limites historiques

| Couche / phase | Preuve | Conclusion permise |
|---|---|---|
|Webots natif #646|shell officiel : `webots-bin`, fils 581, SIGSEGV après warnings Mesa/PointLight ; aucun démarrage de contrôleur ni READY journalisé|échec avant READY ; fonction fautive inconnue|
|Webots natif #655 s1/s17|shell officiel ligne 105 : `webots-bin` SIGSEGV ; aucun journal de contrôleur ni admission|échec de préparation, pas une réfutation du programme Blockly|
|Wrapper / affichage|#646 suit le Popen de `xvfb-run` ; #655 utilise un affichage X TCP indépendant|vie du wrapper insuffisante ; aucun SIGSEGV Xvfb démontré|
|Contrôleurs / capture #655|s14/s5 ont un résultat natif puis un log divergent|défaut de conservation distinct, pas un crash de démarrage démontré|
|Mesa / Qt / Wren / chargeur / finalisation PROTO|warnings, mais aucune pile, registres ou identité des objets chargés au signal|couches candidates, aucune attribution causale démontrée|
|OOM|pas de compteur ou événement kernel attribuable archivé|inconnu ; un SIGSEGV ne démontre pas un OOM kill|

Les PID 581/47/115 sont des **nombres rapportés par le shell**, sans heure de
création ni identité de namespace conservée. Ils ne permettent pas de
retrouver rétroactivement un processus. `core dumped` n'est pas un fichier
core récupéré. Aucun core/backtrace exploitable n'est présent dans les
archives réexaminées. Les avertissements communs ne constituent pas une pile.

#646 utilise l'image
`cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099`,
`xvfb-run` et les contrôleurs lancés par Webots. #655 rapporte le tar officiel
R2025a `c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`,
X TCP froid indépendant, Xvfb `2:21.1.12-1ubuntu1` et contrôleurs TCP externes.
Les assets déclarés sont `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.
Ces provenances déclarées ne remplacent pas les empreintes du binaire et des
bibliothèques **effectivement chargés** au crash, absentes historiquement.
Une cause commune n'est pas établie. Le suivi n'est pas nécessaire aux crashs
#655 ; cela ne réfute pas une cause propre au suivi pour le crash #646.

Le rapport historique `docs/GRAND_PRIX_U_PROTOTYPE.md` mentionne également
un SIGSEGV en affichage TCP partagé, puis l'usage d'affichages froids. Ses
observations et le README des preuves du 13 octobre ont été lus ; ils
n'apportent pas de pile. Le ZIP historique de 36 essais, annoncé comme remis
au propriétaire, n'est pas présent dans le dépôt : ses octets ne sont pas
revendiqués inspectés dans cette exécution.

## Qualification hors simulation effectuée

`qualify.py` compile `fixture.c` avec symboles et utilise `support.py`.
L'archive nouvelle `evidence/host-qualification.zip`, SHA-256
`3d4c2c4f4e93eadaf47409b5d7c33b1fff4aa96b449b89adff52d6963a343337`,
contient 63 membres, tous manifestés sauf le manifeste lui-même, et a été
relue avant publication atomique sans écrasement. Elle conserve notamment :

- sortie normale 42 ; SIGSEGV direct (`Popen.returncode=-11`) ;
- fils SIGSEGV et lanceur encore vivant, puis sortie **0 du lanceur** ;
  `waitpid` contrôlé : `raw_status=11`, signal 11, `core_bit=0` ;
- arbre des descendants, PID procfs + `NSpid`, espace de PID, start ticks,
  boot ID, horloges UTC/monotone, fichiers exe/maps/status/limits/cgroup ;
- snapshot d'un vrai binaire de fixture **arrêté par SIGSTOP** : empreintes
  et Build IDs du binaire, libc et chargeur ; refus d'une fausse naissance ;
- variables graphiques autorisées, versions de paquets, mémoire et compteurs
  cgroup avant/après ; aucun événement OOM observé dans ces fixtures ;
- GDB Ubuntu 15.0.50.20240403, binaire SHA-256
  `f0068d3b418ae039c309574b33901b82404025eb46c2e983246b9c3976ba7e83`,
  extrait en scratch de paquets Ubuntu hachés, sans mise à jour de la libc
  système. Provenance dans `evidence/debugger-provenance.json`.

**Refus expérimental décisif :** `PTRACE_TRACEME=-1`, errno 1 ; GDB reproduit
`Could not trace the inferior process / ptrace: Operation not permitted /
During startup program exited with code 127`. Ce code 127 appartient au
démarrage refusé sous debugger, pas à Webots. GDB ne dispose d'aucun inférieur,
registre, bibliothèque ou pile. Le prérequis `gdb_real_sigsegv_stack` vaut
false ; le qualificateur sort **77**, `acquisition_allowed=false`.
GDB lui-même sort **0** dans cette commande batch malgré le démarrage refusé
de l'inférieur : son code de sortie seul aurait également produit une fausse
garantie. Le qualificateur exige le signal et la vraie frame de la fixture.

Le noyau ne présente pas `/proc/sys/kernel/core_pattern` et la limite core
initiale est 0. Aucun sink core fonctionnel n'a été établi. Aucun essai natif
ne serait ici autorisé par une simple augmentation de cette limite.

Autre constat propre à cet hôte : `getpid()` et `/proc` n'utilisent pas le
même espace. Exemple arrêté : `NSpid = 13782 17`. Le support lit les identités
procfs depuis `/proc/self`, traverse les PPid vérifiés et garde les deux
numérotations. Il ne lit pas aveuglément `/proc/<Popen.pid>`.

#656, Draft observée à `ff0d91b29f80ee320ddf3a6bbe47ceb6033410b0`, travaille
séparément la clôture des écrivains #655. Aucun de ses fichiers n'est modifié.
Une contre-épreuve synthétique en lecture seule montre que son
`_group_members(Popen.pid)` ne peut pas servir de garantie native dans cet
hôte sans qualification du mapping : le fils contrôlé local 7 est
`procfs PID/PGID 13903`, tandis que le scan retourne `[7]`, qui ne désigne
pas ce fils dans procfs. Transcript conservé. Il s'agit d'une limite de
namespace du contrôle de groupe, pas d'une cause historique de SIGSEGV ni
d'une revue complète de #656.

Les trois tests d'archive vérifient la relecture/inventaire, les écritures
tardives de contenu ou de nouveau fichier, les symlinks et le refus
d'écrasement. Ils passent ; ils ne qualifient aucun moteur natif.

```sh
python3 -m unittest discover -s experiments/native-startup-capture -p 'test_*.py' -v
python3 experiments/native-startup-capture/qualify.py --output /tmp/qualification-neuve
```

Le sampler est **explicitement insuffisant** pour les execs brefs, tous les
exit codes de descendants et un inventaire complet des bibliothèques.
`snapshot.py` complète les objets mappés d'un processus identifié et arrêté ;
il ne produit pas de backtrace. Un compte OOM cgroup peut concerner d'autres
processus : son delta seul n'attribue pas la terminaison.

## Acquisition causale préparée, non engagée

Le protocole exécutable à qualifier, les identités et conditions d'arrêt sont
dans [CAPTURE_PROTOCOL.md](CAPTURE_PROTOCOL.md). La chaîne de capture du
vrai lancement fork/exec reste **non qualifiée**. Aucun relâchement de
permissions de cet hôte n'est demandé ; utiliser ultérieurement un environnement
de diagnostic qui fournit déjà le tracing ou un core exploitable.

Avant READY/GO #646 restent indispensables : une acquisition interprétable
et un traitement causal explicite de la réfutation, la revalidation native
du candidat exact, des captures avec **rendu activé** et des observations
des manœuvres, puis Ready stable + CI Gate canonique exacte + revue
indépendante résolvant le NO_GO, dans un tronc restauré. L'acceptation
pédagogique personnelle reste séparée. `--no-rendering` ne qualifie ni
fluidité ni lisibilité ; aucun PASS visuel humain n'est revendiqué.
