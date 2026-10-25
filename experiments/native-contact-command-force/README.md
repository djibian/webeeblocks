# #637 — premier basculement LAND historique retrouvé quantitativement

**Résultat : un seul pas natif R2025a, sans retour PID, retrouve le premier
basculement du FAIL #686 à la précision des traces.** La géométrie cylindre/plan,
l'état entrant archivé et la force/couple prédits par les commandes juste avant
contact suffisent à expliquer ce premier pas. La variation de hauteur amont,
la continuation complète et RESET restent des questions distinctes. Ce travail
n'est pas un correctif, un GO intégrateur ni une restauration de main.

## Hypothèse éprouvée

Le [premier essai sans moteur](https://github.com/djibian/webeeblocks/blob/4078589bdb096b058ad054c484c9811dfdee3698/experiments/native-contact-intervention/README.md)
établissait une suffisance mécanique réduite, avec un tangage de 0.565 rad,
contre 0.421 rad dans le FAIL historique. Il manquait la poussée de ce pas.
Il serait incorrect d'assimiler automatiquement commande et vitesse interne.

Une information déjà archivée permet toutefois une hypothèse réfutable :
**pendant cette fenêtre, les vitesses moteurs atteignent leurs consignes.**
Avec le PROTO R2025a, les quatre poussées sont `4e-5 * vitesse²`, les bras
`(±0.031, ±0.031, 0.008) m` et les couples de réaction suivent
`-2.4e-6 * vitesse * abs(vitesse)`. Aucun coefficient n'est ajusté aux sorties.

1. Avant le contact, comparer la force ainsi prédite au bilan indépendant
   `Fz = m * ((VZ_suivant - VZ_actuel)/0.032 + 9.81)` sur deux pas libres.
2. Appliquer ensuite au cylindre la force et le couple calculés à partir des
   commandes **12.448 s**, puis comparer son état après un pas au vrai
   **12.480 s**, sans PID et sans utiliser cet état de sortie pour régler le modèle.
3. Refaire les trois interventions Z et le contrôle sans sol du premier essai.

Le protocole physique a été fixé localement avant acquisition :
`f93a18c9144713597f8d431745d6a9c46663c89abeb62ed1b5603c13f2195ebe`.
Il ne s'agit pas d'une préinscription indépendante publiée avant acquisition.
Force imposée dans le repère corps : `(0,0,0.5148176996599595) N` ; couple
`(0,0.0000004943505389735092,0) N m`. Ces valeurs sont **prédites sous
l'hypothèse de suivi des consignes**, pas mesurées dans des moteurs internes.

## Résultats natifs et contrôle indépendant

Les deux pas libres historiques donnent des résidus de poussée prédite versus
inférée de **−1.42e-11 N et +3.25e-10 N**, compatibles avec l'arrondi des
journaux. Cela étaye le suivi des cibles dans cette fenêtre, sans en faire
une règle universelle de Webots.

| État après le premier contact | FAIL historique | Fixture native, forces fixées |
|---|---:|---:|
| X (m) | 0.181797755 | 0.181797754460 |
| Z (m) | 0.003564344 | 0.003564344603 |
| VX (m/s) | 0.200691171 | 0.200691170618 |
| VZ (m/s) | −0.357977512 | −0.357977512410 |
| Tangage (rad) | 0.420592622 | 0.420592622676 |
| Vitesse angulaire Y (rad/s) | 13.357210749 | 13.357210760177 |

Le résidu maximal de position est **6.03e-10 m**, de vitesse linéaire
**4.11e-10 m/s**, de tangage **6.76e-10 rad** et de vitesse angulaire
**1.12e-8 rad/s**. Ces chiffres décrivent un accord numérique, pas une
tolérance produit ou une précision physique du drone réel.

| Intervention fixée | Contacts d'entrée | Tangage après 32 ms | ωY après (rad/s) |
|---|---:|---:|---:|
| Z historique | 1 | **0.420592622676** | **13.357210760177** |
| Z +186.368 µm | 0 | −0.000493452420 | 0.000308080636 |
| Z −46 µm | 4 | −0.000500799359 | 0.000078488786 |
| Z historique, sans plan | 0 | −0.000493452420 | 0.000308080636 |

Le témoin sans plan retrouve séparément l'accélération et l'accélération
angulaire attendues de la force/couple imposés, avec un résidu de vitesse
verticale ~1.1e-16 m/s. Le cas haut a les mêmes vitesses/orientations. Le
contact unique est donc discriminant avec la poussée représentative de cette
fenêtre aussi, sans PID actif. Les impulsions nettes du rapport sont inférées
par bilan après soustraction de la gravité **et** de la force/couple imposés ;
aucune force individuelle de joint ODE n'est prétendue mesurée.

## Portée causale

Ce résultat explique quantitativement la transition historique
`contact unique excentré -> forte vitesse angulaire/pitch -> vitesse latérale`
du premier pas, avec les coefficients R2025a et sans modification du PID.
Il ne faut plus demander une nouvelle collecte simplement pour savoir si
le contact peut produire ce premier basculement : cette question est désormais
étayée par l'intervention et l'accord avec l'archive.

Le calcul suppose le suivi des moteurs, soutenu par les deux pas libres et la
prédiction du pas de contact. L'accord ne constitue pas une observation directe
de quatre vitesses internes ni une preuve logique d'unicité du mécanisme.
Il ne tranche pas l'amplification ensuite par PID/moteurs, l'origine de la
phase verticale différente entre PASS/FAIL, la stabilité de toutes les poses
ou le RESET historique. Pas d'attribution à un choix aléatoire d'ODE pour des
états identiques : les états de hauteur sont réellement différents.

La frontière de correction à éprouver devient **la dynamique d'approche et de
contact de LAND**, puis sa continuation : le contrôleur actuel demande
directement `desired.altitude=origin_z` et le FAIL arrive à environ
−0.6203 m/s au premier contact. Ce constat n'autorise pas à choisir une nouvelle
vitesse/trajectoire de descente sans qualification. Comparer des approches
contrôlées et leur énergie de contact, puis l'amplification avec/sans feedback,
en conservant les critères terminaux, les négatifs et les délais. Un décalage
micrométrique de Z, une pénétration forcée, un collider opportuniste ou un
assouplissement de l'oracle ne seraient pas une réparation démontrée.

## Reproduction, intégrité et refus conservés

La base opérationnelle reste `main@f5435a8d28b7a2dfae2f50f896aa40a246a4858b`,
avec les mêmes blobs V5/vision/roadmap que le premier essai. Cette branche
prolonge son commit d'évidence `4078589bdb096b058ad054c484c9811dfdee3698`,
pas une intégration produit. Elle réutilise son runner figé (SHA256
`f02ca1cc65e9571dba8e8cde6ac4aaed9e0b4211c51abf020dcb6eb1aa19caa2`),
sa validation géométrique et les mêmes paramètres/binaires/installations.
Le nouveau contrôleur impose seulement une force/couple et un pas. L'archive
historique complète est conservée, SHA256
`c86dc896ffa8c605568b5dfac7ad86f070d4a49f44f08eef64160f93024b5178`,
CRC ZIP revérifié. Les scripts de relecture ne modifient aucun original.

```sh
python3 experiments/native-contact-command-force/run.py \
  --webots-home /absolute/path/to/webots \
  --xvfb /absolute/path/to/Xvfb \
  --output /absolute/path/to/new-output-directory
python3 experiments/native-contact-command-force/analyze.py
python3 experiments/native-contact-command-force/test_evidence.py
python3 experiments/native-contact-intervention/test_evidence.py
```

L'acquisition exploitable **03** est également scellée en tar.gz **dans la même
invocation**, après fermeture des producteurs, puis relue et comparée au
manifeste. SHA256 du tar.gz original :
`9ba5c5a3fda348f4d989230eff9082eadd6c29b0dbc6e8a29d656161afa4c979`.
Sa copie extraite conservée est vérifiée avant toute analyse ; sa présence
ne remplace pas la vérification du tar original. Les checks se fondent sur
les observations natives avant/après, les mondes et les deux témoins libres,
pas sur le seul marqueur de complétion. **5 tests supplémentaires**, en plus des
7 précédents, conservent les refus ci-dessous ; aucun GO indépendant auteur.

Deux acquisitions antérieures restent explicitement **refusées** :

- **01, protocole mal appliqué et capture incomplète.** Le wrapper Python
  officiel R2025a `Node.addTorque` appelle en réalité
  `wb_supervisor_node_add_force` avec un tableau de quatre doubles. Le contrôle
  sans plan expose la petite force Y indue et l'absence d'accélération angulaire
  attendue. Le nouveau probe appelle directement la fonction C documentée
  `wb_supervisor_node_add_torque`, avec types explicites ; l'installation Webots
  n'est pas modifiée. L'ancien script réellement exécuté est conservé.
  Source primaire : [node.py R2025a](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/lib/controller/python/controller/node.py),
  SHA256 local `99f15f49ae7b8d50d4c80f790895e0dd53c192099110f3485c70d5a2b492d724`.
  Ce défaut du support Python ne peut expliquer le LAND produit écrit en C.
- **02, capture incomplète après protocole corrigé.** La vérification a trouvé
  les deux logs du dernier cas différents de leurs empreintes de capture,
  alors que les JSON natifs sont présents. 01 présente aussi une incohérence
  d'inventaire. Les originaux et anciens manifestes sont conservés, jamais
  rescellés ni qualifiés comme archives complètes. La cause de la modification
  tardive reste non démontrée ; des opérations de fichiers avaient été
  intercalées pendant les sessions asynchrones. Pour 03, aucune commande de
  fichiers n'est intercalée pendant le runner ; le scellement et la relecture
  sont faits avant son retour. C'est un changement du support de capture,
  pas un ajustement de la physique pour obtenir un résultat favorable.

La première étude sans forces est indépendante du wrapper `addTorque` et
reste vérifiée par ses tests. Les refus 01/02 n'ont pas disparu derrière le
succès 03. Les manifestes d'intégrité ne sont pas des attestations indépendantes.
La CI canonique, les NO_GO exacts, #637/#665, le FAIL pédagogique #635 et les
gates physiques restent applicables ; aucun TEST_REQUIRED ni vol n'est autorisé.
