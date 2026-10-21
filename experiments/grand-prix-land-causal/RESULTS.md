# LAND #638 — expérience arrêtée, aucune réparation démontrée

## Verdict du 21 octobre 2026

**NON CONCLUANT sur l'amplification physique par la dérivée du PID.**
Le premier contrôle A n'a pas reproduit le défaut. Un défaut du harnais a
ensuite interrompu le protocole, conformément à sa règle d'arrêt. **B1, B2 et
A2 n'ont pas été exécutés. Aucun correctif produit n'est justifié ni préparé
pour intégration.** Les résultats ne lèvent aucune réfutation de #638.

## Provenance et conservation

Protocole préenregistré dans
[`3c1cd33c6d0e8aca42c038591e8366e7dc736355`](https://github.com/djibian/webeeblocks/commit/3c1cd33c6d0e8aca42c038591e8366e7dc736355),
branche `experiment/638-land-causal-20261021`, avant le lancement push-only.
Le [run 39568761023](https://github.com/djibian/webeeblocks/actions/runs/39568761023),
tentative 1, job 119117401548, est **completed/failure**. Il n'est pas un
`CI Gate`, et ne participe pas à une décision Ready.

Archive originale : [artefact 12329814708](https://github.com/djibian/webeeblocks/actions/runs/39568761023/artifacts/12329814708),
14 494 523 octets, SHA-256 recalculé
`62e4df7850591afbdfb636aafd426aeb75394d2337ffc735f2813b4163c549c4`.
CRC ZIP et les 9 entrées du manifeste racine et 11 du manifeste de scénario
ont été vérifiés. Toutes correspondent. Le pilote a bien conservé le premier
cas commencé et l'échec technique ; aucun cas de remplacement n'a été lancé.

Référence produit exacte : #638 à
`149c0b61b48f335eb4cb925113ccc03afce80cca`. Même seed 14, damiers, collisions,
cible (0,7 ; 1,5), témoin ordinaire et AST
`89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d`.
Le vrai PID C est inchangé. A ajoute les observations communes, sans ablation
ni modification des commandes ; leur coût peut modifier la chronologie
asynchrone. L'image Docker et les assets sont ceux fixés dans PROTOCOL.md.

`evidence/` conserve logs complets, événements, monde, résultats, diagnostics,
sources réellement compilées et manifestes originaux. Les trois grands flux
sont des **extraits contigus**, jamais présentés comme des fichiers complets.
`sources.json` précise sources, empreintes, offsets d'octets et en-têtes ;
`sha256.json` protège les octets retenus. Le ZIP complet conserve aussi la
référence tar, le binaire et les flux complets. Les manifestes originaux portent
sur ces fichiers complets, pas sur les extraits. Le workflow expérimental est
retiré de cette branche d'évidence pour qu'une publication du résultat ne
déclenche aucune nouvelle acquisition.

Vérification hors simulation :

```sh
python3 experiments/grand-prix-land-causal/verify_evidence.py
python3 experiments/grand-prix-land-causal/verify_evidence.py --original-zip /chemin/land-causal-39568761023.zip
```

## Observation native A1

Le même programme réussit deux franchissements puis sa pose : `achieved`,
150,784 s de mission. Les temps ci-dessous sont les temps absolus Webots.

| Observation | Valeur native conservée |
| --- | --- |
| Début LAND | 163,968 s |
| Premier contact | 165,016 s ; quatre contacts |
| Position au toucher | (0,657380 ; 1,522718 ; 0,014939) m |
| Erreur XY à la cible au toucher | 4,8297 cm |
| Vitesse XY / VZ au toucher | 0,00122944 / −0,451755 m/s |
| Vitesse XY maximale après contact dans la fenêtre retenue | 0,00352974 m/s |
| Déplacement XY maximal depuis le toucher | 1,03912 mm |
| Roulis physique maximal après contact | 0,136132° |
| Commande zéro moteur et frontière ACK LAND | 166,368 s |
| Vitesse XY à cette frontière | environ 0,00037686 m/s |
| Dernière observation native | 168,376 s |
| Fenêtre réellement conservée après stop | 2,008 s, contre 3 s exigées |

Ce résultat est un témoin négatif de reproduction du défaut, **pas une
contre-épreuve corrigée**. Il ne contredit pas le FAIL historique seed 14
à contacts 1 puis 3, ni le NO_GO historique sur la mauvaise pose seed 3.

## Deux limites techniques distinctes

**1. Le harnais a choisi un fichier comme dossier.**
`stop_with_coast` construit `list(runner.OUT.glob('*'))` puis choisit le premier
élément. `started.json`, créé avant le lancement natif, satisfait ce glob.
Le harnais tente donc de lire `started.json/webots.log` et échoue avec
`NotADirectoryError` au moment d'observer la fenêtre post-ACK. L'erreur est
documentée dans `technical-failure.json` et `docker.log`. Elle provient du
support expérimental, pas du contrôleur ni de Webots. Le triage minimal serait
de sélectionner explicitement l'unique dossier de scénario. **Cette réparation
ne donne pas permission de relancer les acquisitions arrêtées par le protocole.**

**2. Une seule représentation d'hélice ne mesure pas toute sa rotation.**
La relecture hors simulation de `native-rotors.csv` par le vérificateur
prévu refuse la reconstruction : première discontinuité à 17,800 s. À
17,792 s, la différence de rotation du slowHelix donne environ 49,92 rad/s
en valeur absolue ; le champ se fige au pas suivant. La vitesse zéro déduite
violerait la limite d'accélération de 30 rad/s². Ce refus doit être conservé.

Le [code officiel R2025a exact](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/nodes/WbPropeller.cpp)
explique la limite de mesure : `updateHelix` choisit fastHelix au-dessus de
50 rad/s, puis `prePhysicsStep` met à jour **mHelix**, la représentation active.
Le slowHelix seul ne suit donc plus la rotation quand fastHelix est actif.
Le champ figé ne prouve pas que le rotor physique s'arrête. Il est interdit
d'en déduire vitesse réelle, poussée nulle ou force post-ACK. **Les forces
effectivement appliquées et les impulsions de contact restent non mesurées.**

Une future observation devrait qualifier les deux représentations et leur
transition, ou utiliser une autre voie native prouvée, avant de lancer une
nouvelle expérience de régulation. Les tests synthétiques d'angle passés avant
la campagne ne couvraient pas ce changement de représentation ; leur succès
ne qualifiait pas cette mesure native. Aucune campagne supplémentaire n'est
lancée pour contourner ces deux refus.

## Chaîne causale : ce qui est établi et ce qui manque

| Maillon | Conclusion applicable |
| --- | --- |
| Contact et impulsion initiale | L'archive historique observe une impulsion latérale après contact ; A1 touche avec quatre contacts et reste stable. La force du contact et sa cause ne sont pas identifiées. |
| Vitesse consommée | Vitesse GPS corporelle au pas réel de contrôle de 32 ms ; distincte de la vitesse native à 8 ms. Les deux sont conservées. |
| Erreur et dérivée | Les nouvelles traces les séparent. L'ablation B prévue n'a jamais été activée ; aucune donnée B n'existe. |
| Assiette et mixage | Le vrai rejeu C au commit a765396 établit le rôle de la dérivée sur les commandes historiques (+37° puis −90°), pas sur une trajectoire corrigée. |
| Consignes moteur | Mesures des appels API après clamps ; elles ne sont pas assimilées à des vitesses de rotor ni à une poussée. |
| Forces et réaction du corps | La réaction du corps A1 est faible ; la tentative de reconstruire la poussée à partir du slowHelix est invalide. L'amplification physique par le PID reste indéterminée. |
| Arrêt et ACK | La frontière 166,368 s vient de phase=stop. Elle ne prouve pas l'extinction instantanée ; 2,008 s seulement sont observées ensuite. |
| Oracle | A1 est accepté correctement dans sa fenêtre ; le refus historique `envelope-contact` reste opposable. Aucun seuil n'est changé. |

Les observations déjà acquises dans #638 et
[a765396](https://github.com/djibian/webeeblocks/blob/a7653962129d64234e1ecb7ad55467fa97d5dede/experiments/grand-prix-land-replay/RESULTS.md)
restent la base : approche correcte, impulsion post-contact, grandes commandes
PID, mais aucune attribution physique suffisante. La nouvelle expérience
ajoute un contrôle sans défaut et deux limites du support ; elle ne démontre
ni correction ni réfutation générale du mécanisme suspect.

## Correction, régressions et état d'intégration

Aucun changement de contrôleur produit, PID, gains, RESET, Blockly, cibles,
zones de pose, oracle ou autorité 210 s. L'ablation expérimentale n'a pas été
exécutée ; ses effets sur vol normal, descente et stabilisation sont donc
**non évalués**. Aucun avant/après physique, CI Gate Ready ou GO indépendant
n'est revendiqué. Les négatifs historiques, dont les deux time-limit à
210,000 s, restent conservés dans a765396 ; ils ne sont pas réexécutés ici.

Reconstruction : main `b478f9dd1854d83345abe13ed20fcf7baeffaca5` ; blobs V5,
vision et roadmap `c1b0078103507e7b0132af948b34a5cbd7b5950a`,
`df0b3b8591562f13f879db5c3f5ab78286b84cde`,
`e8c4e246df15f223728f94743c958374176fccac`, inchangés.
#638 reste **ouverte Draft**, HEAD exact
`149c0b61b48f335eb4cb925113ccc03afce80cca`, base GitHub observée
`72a6f5a5d1478d37c562c5c6be4ab3afd07d4214`.
Le succès Draft 39311714756 n'est pas une CI Gate Ready ; le NO_GO propriétaire
5574571532 et le FAIL natif seed 14 restent non résolus. #638 n'est pas modifiée.
#637 reste un blocage distinct de santé du tronc ; aucune investigation ou
modification RESET n'a été menée et aucune intégration ordinaire n'est permise.

Avant un correctif intégrable : mesure d'actionneurs native qualifiée, contrôle
qui exerce réellement la panne, intervention unique et comparaison physique
suffisante ; validation des déplacements, descente, contact et stabilisation,
précision et négatifs inchangés, autorité indépendante 210 s ; puis candidat
Ready stable sur base admissible, CI Gate canonique exacte et revue indépendante
résolvant chaque réfutation applicable. L'auteur de ce dossier ne signe pas son
propre GO. Aucun PASS pédagogique, TEST_REQUIRED, travail sur caméra/navigation
sans murs/activités 2–7, ni autorisation de vol réel.
