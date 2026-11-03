# Grand Prix U — premier travail d'observation, sans solution

**Statut : proposition expérimentale à éprouver avec des collégiens.** Le monde
est celui du Grand Prix U sans murs latéraux du `main` de référence. Ce
dossier n'est ni un nouveau profil, ni une activité 2–7, ni un témoignage de
réussite native. Il ne fournit **aucun programme complet**.

## Départ élève

Ouvrir `Grand-Prix-U-demarrage-incomplet.wbb` dans la fenêtre dédiée Grand
Prix U, avec le bon monde déjà lancé. Le fichier comprend uniquement le bloc
ordinaire de décollage à 0,8 m, altitude de travail à discuter ; il ne comporte
ni détection, ni mouvement, ni test, ni procédure, ni variable, ni atterrissage.
Il est intentionnellement **non exécutable** tant que le programme n'est pas
complété. Les dimensions, zones de vol bas et limites de 210 s sont celles du
monde et de son oracle natif, non celles de ce fichier.

### Mission partielle, à construire par l'élève

Sur un seul côté, imaginer comment distinguer une ouverture franchissable,
un portique fermé et une lecture qui ne permet **pas** de décider. Montrer
la suite de **mesures**, les **comparaisons**, puis l'**action** justifiée.
Déterminer à quel moment un franchissement peut réellement être compté :
voir un H ou entrer dedans ne suffit pas. Produire sur papier un schéma
décisionnel, puis le construire avec les blocs déjà disponibles, sans ouvrir
les 232/389 blocs des témoins experts. La stratégie de parcours complet,
les deux virages, la mémoire et les trois poses restent à concevoir ensuite.

Le professeur donne les mêmes acquis et le même temps aux élèves. Pour
provoquer la discussion, proposer des **mesures hypothétiques**, sans annoncer
leur classe : (avant=.35, bas=.70), (.35,.35), (.35,.50), puis les frontières
(.25,.55) et (.35,.43). Demander quelle information serait nécessaire avant
d'autoriser une descente ; distinguer un modèle de mesure de la dynamique
réelle du drone. Les nombres ne constituent pas un oracle ou des seuils
certifiés par des essais natifs.

L'élève doit pouvoir expliquer pourquoi une lecture ambiguë ne vaut pas
permission de franchir, localiser une erreur volontaire de comparaison en
pas-à-pas, la corriger, relancer et retrouver son travail par Save/Open.
Relever pour chaque élève : décisions produites sans aide, demandes d'aide,
erreur diagnostiquée, justification de la correction, résultat de la
réouverture et transfert à une observation de capteur hors Grand Prix. **Ne
pas transformer ces observations en score automatique.**

## Vérification falsifiable de l'artefact

```sh
bash tools/prepare_runtime_v2.sh
node experiments/grand-prix-pupil-observation/verify.js
python3 tools/blockly/measure_wbb.py \
  experiments/grand-prix-pupil-observation/Grand-Prix-U-demarrage-incomplet.wbb
```

Le vérificateur utilise Blockly réel, le profil U et le validateur de projet
partagé : le starter doit être ouvrable mais `ast=null` (incomplet), la
compilation directe doit refuser l'absence de LAND ; en mémoire seulement, un
LAND est ajouté pour vérifier édition/préflight/Save/Open logique. Ce
mini-programme décoller-atterrir ne réalise **aucun Grand Prix**. Le test
n'exerce ni dialogue de fichier du système d'exploitation, ni Webots,
ni moteur d'oracle, ni RESET, ni autorité LAND à 210000 ms. Le test natif complet
des vrais programmes élèves et la revue indépendante V5 restent indispensables.

Aucun bloc nouveau n'est ajouté : les primitives génériques existantes
(détection, condition, variables, procédures) sont suffisantes pour essayer
ce premier travail. La preuve de réutilisabilité d'une éventuelle future
primitive sur une **autre situation** demeure une condition préalable à
son adoption.

Comparaison structurelle des stratégies historiques :
[PR #804](https://github.com/djibian/webeeblocks/pull/804).
Contrat de la mission : [#587](https://github.com/djibian/webeeblocks/issues/587).
Distinguer la faisabilité technique de l'acceptation pédagogique personnelle.
