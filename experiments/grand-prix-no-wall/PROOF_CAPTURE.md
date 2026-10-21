# #655 — clôture et conservation des preuves, sans Webots

## Portée et données historiques

Ce composant concerne **uniquement** les runners locaux de
`experiments/grand-prix-no-wall`, sur Linux avec `/proc` accessible.
Il ne modifie ni programme/AST, ni simulation, ni oracle, ni verdict natif,
ni séquences LAND/RESET, ni limite à 210 secondes.

La preuve historique #655 reste **partiellement qualifiée** : s14 `node.log`
(hachage déclaré différent du membre archivé), s5 `flight.log` (même défaut).
Les tarballs, manifestes et rapports antérieurs sont conservés à l'identique.
Le résultat natif `achieved` ne transforme aucun de ces deux cas en PASS.
La copie tardive s14 suggère que les octets observables peuvent varier dans
le temps ; elle ne permet pas d'attribuer la divergence à un processus précis.

## Enchaînement pour un *nouvel* essai seulement

1. `run_native.py` ou `run_negative.py` produit le résultat natif et ses
   témoins. Dans son `finally`, `close_capture` envoie SIGTERM à **tous les
   groupes de processus connus** (créés par `start_new_session=True`), attend
   la disparition des membres actifs, escalade SIGKILL si nécessaire, puis
   récolte les processus directs. Les zombies sont sans capacité d'écriture.
2. Les flux ouverts par le runner sont fermés. Une inspection `/proc/*/fd`
   refuse toute écriture encore ouverte sur le dossier par un processus du
   même UID, y compris hors groupe connu. Tout échec interdit la clôture.
3. En cas de clôture saine, le runner crée `capture-seal.json`, puis **un seul
   inventaire** `sha256.json` listant strictement les fichiers réguliers du
   dossier, sans lui-même. Aucune preuve de mission n'est modifiée.
4. **Un appel indépendant après sortie du runner** construit une nouvelle
   archive depuis ce dossier, exclusivement après présence du seal et
   validation d'un manifeste couvrant exactement l'ensemble des fichiers :

   ```sh
   python3 experiments/grand-prix-no-wall/evidence_capture.py \
     ci-artifacts/grand-prix-no-wall/<nouveau-dossier-essai> \
     <archive-nouvelle-et-unique>.tar.xz
   ```

5. Cette commande re-hache les fichiers sources, écrit une archive temporaire
   dans le dossier de destination, réouvre celle-ci, vérifie la présence
   **exacte et unique de tous les membres** et compare leur SHA-256 aux
   fichiers sources et au manifeste. Elle vérifie de nouveau la source et
   relit l'archive temporaire. Après synchronisation disque, elle crée le nom
   définitif par **lien atomique sans remplacement** (`os.link`), synchronise
   le répertoire et retire le nom temporaire. Deux processus concurrents ne
   peuvent pas remplacer une archive déjà publiée. Le fichier est en mode
   `0444` à sa publication ; sa taille et son SHA-256 sont retournés.

En cas d'échec de clôture, d'inventaire, de compression, de relecture,
d'incohérence, d'interruption ou de conflit de destination, **aucune nouvelle
archive n'est publiée**. La capture brute reste disponible pour diagnostic,
sans modification du résultat natif `achieved` / `not-achieved` / indéterminé.

## Validation sans simulation

```sh
cd experiments/grand-prix-no-wall
python3 -m unittest -v test_evidence_capture.py
```

Les tests adversariaux couvrent les écrivains tardifs, le descendant dont le
leader est mort, l'écrivain détaché avec FD ouvert, fichier manquant/modifié,
manifeste incomplet, interruption/corruption de l'archive temporaire,
publication concurrente et lecture d'une archive réussie non écrasable.
Cette qualification ne prouve ni la qualité des traces Webots ni une réparation
rétrospective des s14/s5. L'oracle/`verify_native.py` doit qualifier le
**contenu** d'un nouvel essai indépendamment des contrôles d'intégrité.

## Limite précise

L'inspection des groupes connus et des FDs ouverts **ne garantit pas** l'absence
d'un processus inconnu actuellement sans FD qui ouvrirait un fichier plus tard,
ni un descendant qui change d'UID/session et échappe à la visibilité de
`/proc`, ni l'absence d'un acteur privilégié capable de modifier
l'archive publiée. Le protocole suppose un dossier d'essai unique, privé des
autres producteurs, sans nouvelles écritures après la sortie du runner. Une
écriture concurrente détectée entre hachage et publication échoue fermement,
mais une mutation ultérieure de la source ne peut pas être exclue par hachage
seul. Aucun mécanisme SHA-256 n'est un verrou permanent sur la source.

**Prochaine contre-épreuve éventuelle :** un seul nouveau s5, exclusivement
après tests locaux et évaluation indépendante du support, avec un nom et un
manifeste nouveaux, et arrêt immédiat au premier refus de préparation,
capture ou mission. Le s5 historique reste intact, et une nouvelle réussite
ne répare pas ses octets antérieurs. Pas de nouveau s14 ni des cinq réussites
déjà complètes. Aucun vol réel ni PASS pédagogique implicite.
