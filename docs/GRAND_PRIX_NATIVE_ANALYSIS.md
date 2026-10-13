# Grand Prix : analyse indépendante des traces natives

Ce composant lit des CSV position/vitesse/attitude, les événements WWI et les
journaux de commandes du prototype #591. Il n'importe ni oracle, ni solution,
ni backend, ni contrôleur de vol. Il ne transmet aucune donnée au programme.
Il exige des instants natifs milliseconde contigus à 32 ms, identités de
commandes et terminaisons appariées, valeurs finies et compte de mesures exact.
Les contrôles sont inclus dans le test de temps de simulation déjà appelé par
le harness Runtime intégré ; aucun workflow ou sélecteur CI n'est modifié.

La convention de diagnostic de freinage est explicite : étendue restante après
le **dernier échantillon à au moins 90 % de la vitesse maximale de chaque MOVE**.
Ce n'est pas une borne d'arrêt d'urgence, une preuve universelle de décélération,
ni un dégagement de trajectoire future. Les mouvements observés incluent le PID
et sa stabilisation normale jusqu'à ACK. Les TURN rapportent aussi leur dérive
horizontale ; les H et obstacles bas leurs marges ; LAND la distance à la paroi.
Les marges utilisent une sphère de 0,09 m et les boîtes du monde expérimenté.
La comparaison des capteurs projette le Multi-ranger à (0,0,0,01 m) dans la
matrice d'attitude native, applique les orientations R2025a 0/3,14/±1,57 rad,
la portée 2 m et les boîtes/sol. Elle est un diagnostic, pas un certificat
d'ouverture ni une information mise à disposition de Blockly.

## Premier domaine réellement observé

Source candidat #591 **60efa676e4f1e17ffd0d4098406e597210aad6f2**, run
**38363324274**, tentative 1, artefact **11796149632**,
SHA-256 ZIP **67e80f7aba0b0d2254d304c3ac1504fddec6864a0a144c1c93df2aeef31855ce**.
Image cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099,
assets c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b, mode realtime.
Le run **échoue** sur gp-v4-0 ; seuls les deux succès ci-dessous sont analysés
par la commande qui exige un résultat achieved. Ce composant ne réhabilite pas
le candidat, ne produit aucun GO et ne change jamais le score.

| Mesure native | gp-v4-4 | gp-v4-1 |
| --- | ---: | ---: |
| Durée Webots / T=180 s | 280,288 s | 314,752 s |
| Passages / points expérimentaux | 5 / −76 | 6 / −105 |
| Dégagement minimal de l'enveloppe | 0,070286 m | 0,055335 m |
| Marge latérale minimale aux H | 0,143177 m | 0,135351 m |
| Marge haute minimale aux H | 0,112482 m | 0,080181 m |
| Dégagement paroi fermée après ACK LAND | 0,545142 m | 0,578889 m |
| Vitesse horizontale maximale | 0,260822 m/s | 0,260822 m/s |
| Inclinaison maximale | 4,590598° | 4,590630° |
| Extent après dernier 90 % du pic, max MOVE | 0,277035 m | 0,277036 m |
| Dérive horizontale maximale TURN | 0,003042 m | 0,002992 m |
| Retours saturés / retour fini maximal | 14 / 1,946056 m | 21 / 1,945894 m |

Les écarts rayons/retours natifs restent <5e-10 m, cohérents avec la sérialisation
à neuf décimales et le modèle sans bruit. Ni bruit, disponibilité physique,
équité CPU/WWI, répétabilité ni batterie ne sont prouvés. Ce diagnostic porte
sur les échantillons enregistrés, sans interpolation certifiée entre pas.

## Reproduction

Télécharger l'artefact, recalculer le digest, extraire un dossier de succès.
Depuis un checkout du SHA source, produire son layout.json avec :

```sh
python3 -c 'import dataclasses,json;from tools.grand_prix.layout import generate;print(json.dumps(dataclasses.asdict(generate(4,"gp-v4"))))' > layout.json
```

Depuis le checkout de cette proposition, utiliser les fichiers de ce même
essai ; changer 4 en 1 pour l'autre configuration :

```sh
python3 -m tools.grand_prix.kinematics --layout layout.json   --trace gp-v4-4-1-efficient/native_trace.csv   --log gp-v4-4-1-efficient/webots.log   --events gp-v4-4-1-efficient/events.jsonl   --result gp-v4-4-1-efficient/result.json --output kinematics.json
python3 tools/ci/test_grand_prix_simulation_time.py
```

Le JSON conserve chaque intervalle de commande et mesure projetée. Les tests
synthétiques restent explicitement non natifs ; ils réfutent trous, doublons,
identités erronées, ACK manquants, non-finis, mauvaise pose capteur et nombre de
mesures incohérent. Aucun vol, appareil ou fichier de #157/#586 n'est concerné.
