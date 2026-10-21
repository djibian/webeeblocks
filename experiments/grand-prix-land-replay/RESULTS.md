# LAND #638 — impact, réaction du PID et limite de preuve

## Verdict borné au 21 octobre 2026

**Défaut natif non résolu. Aucune correction produit causalement validée.**
Le rejeu établit une cause précise des **commandes d'assiette et de leur
mixage** après impact : la dérivée de l'erreur de vitesse horizontale dans
le PID produit une forte alternance de consignes. Il ne démontre pas que
cette réaction est la cause nécessaire ou suffisante de l'excursion physique.
Les forces/impulsions et les vitesses effectives des actionneurs ne sont pas
dans ces archives. Aucun correctif spéculatif n'est proposé à l'intégration.

Cette analyse réutilise deux ZIP natifs existants. Elle ne lance aucune
acquisition Webots, ne modifie aucun contrôleur de production et n'étudie
pas RESET_TIMEOUT. L'absence locale de Webots/Docker interdit de prétendre
avoir exécuté une contre-épreuve physique avant/après.

## Sources et reproduction

Les ZIP originaux ont été téléchargés, leur SHA-256 recalculé, leur CRC
vérifié, puis chaque entrée des quatre manifestes de scénario contrôlée.

| Source native R2025a | HEAD exact | ZIP SHA-256 |
| --- | --- | --- |
| [run 39301132293](https://github.com/djibian/webeeblocks/actions/runs/39301132293), artefact 12212133156, échec seed 14 | `2a7b4cc6c98f5e03a50dda4d23d136e68f39a2c6` | `71a4430fb849d06774521ee602126292741d91f5706d79db2c1092a2c48d36ae` |
| [run 39311714756](https://github.com/djibian/webeeblocks/actions/runs/39311714756), artefact 12216162199, trois poses seed 14 réussies | `149c0b61b48f335eb4cb925113ccc03afce80cca` | `52129f0936a6168d0d7a895cb2110d80b08b750be046099f5285f23e502094f7` |

`data/` conserve les logs, événements, mondes, layouts, résultats, diagnostics
et manifestes originaux des quatre scénarios. Les CSV natifs sont des
**extraits contigus**, avec leur en-tête original, depuis 32 ms avant la
première trace LAND jusqu'à 512 ms après la dernière trace. `sources.json`
donne les scénarios, SHA des sources et offsets d'octets exacts ;
`sha256.json` protège les octets retenus. Les manifestes originaux portent
sur les fichiers complets, pas sur nos extraits. Les ZIP restent les archives
complètes de référence. Les vues résumées `campaign-success.json` et
`landing-contrast.json` viennent du second ZIP sans réécriture.

Depuis la racine du dépôt, avec Python et un compilateur C :

```sh
python3 experiments/grand-prix-land-replay/verify.py
# Facultatif : revérifier aussi les ZIP complets et chaque tranche d'octets.
python3 experiments/grand-prix-land-replay/verify.py \
  --original-zip /chemin/gp638-fail-complete.zip \
  --original-zip /chemin/gp638-success.zip
```

Le vérificateur compile **le vrai `pid_controller.c` du dépôt** avec un
petit pont C. Le PID et son en-tête sont identiques entre les deux HEAD
natifs et `main@b478f9dd1854d83345abe13ed20fcf7baeffaca5`. Les gains, la
transformation de vitesse et la branche LAND de ces Runtime sont également
inchangés ; le fichier Runtime complet diffère par des diagnostics RESET
distincts, sans lesquels aucune identité globale n'est prétendue. Les
SHA-256 des sources locales sont imposés avant le rejeu. Les gains du pont
ont été confrontés à ces sources et aux commandes natives.
Chaque observation LAND fournit attitude, altitude et vitesse monde. La
transformation monde→corps est celle du contrôleur. Les deux premiers pas
amorcent l'historique PID non retenu ; les suivants comparent les consignes
d'assiette et les composantes roulis/tangage du mixage aux commandes natives.

L'intégrateur vertical et le taux de lacet antérieurs ne sont **pas reconstruits** :
le rejeu ne valide ni poussée collective ni couple de lacet. Les composantes
roulis/tangage se séparent algébriquement du collectif/lacet tant que les quatre
commandes sont non écrêtées. Deux pas écrêtés après la collision sont donc
explicitement exclus de l'inversion, sans effacer les observations.

Résultat obtenu : **285 pas comparés** (63/74/74/74), erreur absolue maximale
de rejeu **2,17 × 10⁻⁷**, sous la borne de vérification 10⁻⁵ tenant compte des
arrondis décimaux des traces. Les trois réussites disposent en plus des
champs `actual_velocity_body` et `attitude_cmd`, qui sont directement
recoupés. Le même AST SHA-256 est retrouvé dans les quatre événements programme :
`89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d`.

## Ce que les données établissent

Les heures suivantes sont les temps **absolus Webots**, pas la durée de mission.

| Seed 14 | Premier contact | Contacts initiaux | Erreur XY à la cible | Vitesse verticale native au toucher | Maximum vitesse XY après contact, jusqu'au stop | Résultat natif |
| --- | --- | --- | --- | --- | --- | --- |
| Échec historique | 174,360 s | 1, puis 3 au pas suivant | 5,151 cm | −0,45316 m/s | 2,16815 m/s | `envelope-contact` |
| Flat | 196,000 s | 4 | 4,865 cm | −0,45056 m/s | 0,00218 m/s | `achieved` |
| Damier A | 201,984 s | 4 | 6,346 cm | −0,45140 m/s | 0,00218 m/s | `achieved` |
| Damier B | 199,328 s | 4 | 5,154 cm | −0,45095 m/s | 0,00218 m/s | `achieved` |

L'échec ne commence donc pas par une erreur de destination ou une grande
vitesse horizontale à l'arrivée. Au premier toucher historique, la vitesse
XY native vaut environ 0,00123 m/s. L'impulsion latérale et le roulis
apparaissent ensuite, avec une topologie de contacts différente. Une
descente proche de −0,45 m/s et un rebond existent aussi dans les réussites :
ce contraste ne suffit pas à attribuer la panne au seul taux de descente.

Le contrôleur travaille normalement à 32 ms, tandis que l'observateur natif
échantillonne à 8 ms. Il calcule une vitesse GPS moyenne sur son propre pas :
la vitesse native instantanée au même timestamp n'est pas cette entrée PID.
À 174,368 s, la vitesse corporelle utilisée vaut environ +0,03803 m/s,
alors que la vitesse latérale monde native est déjà proche de −0,1483 m/s.
Mélanger ces deux mesures ferait produire un faux rejeu.

### Mécanisme de commande identifié par le vrai PID

Pour LAND, les consignes de vitesse horizontale sont nulles. Le régulateur
calcule, sans borne finale sur la consigne d'assiette :

`roll_cmd = −2 × constrain(vy_error, −1, 1) − 0,5 × Δvy_error / dt`

La borne sur le terme proportionnel ne borne pas le terme dérivé ni leur
somme. La boucle d'attitude applique ensuite sa propre dérivée de l'erreur.

| Temps | Roulis mesuré | Consigne de roulis rejouée | Composante roulis du mixage natif/rejoué | Consigne si seule la dérivée de vitesse est mise à zéro dans le rejeu |
| --- | --- | --- | --- | --- |
| 174,368 s | −4,489° | +37,091° | +2,63608 | +4,358° |
| 174,400 s | +2,436° | −89,965° | −7,80751 | −6,345° |
| 174,432 s | +7,634° | −4,314° | +4,28375 | −6,114° |

Le signe et l'amplitude des commandes archivées sont ainsi expliqués par
les mesures effectivement consommées et le code, sans invoquer une commande
Blockly cachée. L'intervention « dérivée de vitesse nulle » est un
**contre-factuel de calcul à entrées figées**, pas un essai de vol : les
états imposés seraient différents en boucle fermée. Elle n'autorise ni
la suppression du gain ni un écrêtage choisi après coup.

Dans le FAIL, avant même le verdict de collision, la consigne interne de
roulis atteint environ 292°. Après le choc terminal, le calcul peut dépasser
2 000° ; ces valeurs sont des **consignes internes**, pas l'attitude physique.
Le roulis physique observé culmine à environ 42,05°. Les réussites restent
à environ 0,056° physiques après contact et 1,83° demandés sur la fenêtre
rejouée après amorçage. Ce contraste localise une amplification à examiner,
mais ne fournit pas une expérience où seul ce mécanisme changerait.

### LAND, contact, moteurs, ACK et résultat sont distincts

Sur le FAIL, l'ordre à zéro et la frontière d'ACK tracés `phase=stop` arrivent
à **175,456 s**, après le refus natif à **175,336 s**, avec une vitesse monde
XY d'environ **0,92508 m/s**. Le prédicat LAND n'exige que l'altitude et VZ
durant 0,5 s, puis commande zéro et répond OK. C'est une permission de
confirmer LAND en mouvement horizontal, ici effectivement observée.
Cette confirmation ne constitue pas une preuve de pose stable.

Les quatre valeurs `motors` sont les **consignes signées envoyées aux API**,
pas une mesure de rotation effective, de poussée ou de couple. Même
`phase=stop` horodate la commande zéro et l'ACK dans le Runtime ; il ne
prouve pas l'extinction instantanée des actionneurs. `completion_ms` reste
le marqueur de fin observé ultérieurement par l'évaluateur. Aucun ancien
`completion_ms` n'est réinterprété comme un instant moteur.

L'oracle utilise la pose/vitesse et les contacts natifs, avec la cible,
les franchissements et sa fenêtre stationnaire propres. Il refuse donc
correctement l'excursion malgré l'ACK. Renforcer le seul ACK n'annulerait
pas l'excursion déjà survenue. L'oracle ne consulte ni l'AST ni le diagnostic
PID ; les mesures ne fournissent aucune nouvelle autorité de pilotage.

## Négatifs et frontières inchangés

Aucun fichier de production, oracle, stratégie, cible, tolérance, dimension,
collision, physique ou mécanisme d'autorité n'est modifié par ce dossier.
Le vérificateur conserve et contrôle les huit résultats négatifs du run
39311714756 : programme court, mauvaise pose, vol bas hors zone, collision,
retour arrière, mesure indisponible et les deux expirations à 210,000 s.
Cette vérification de résultats archivés ne réexécute pas les négatifs et
ne revendique pas une nouvelle CI. Le FAIL natif antérieur reste opposable.

Les mondes Flat et Damier A sont identiques après retrait des seules lignes
des cellules ; l'AST est identique. Les trois réussites ne constituent pas
une réparation avant/après et ne lèvent pas le NO_GO de #638.

## État GitHub et interférences reconstruits

`main` examiné : **b478f9dd1854d83345abe13ed20fcf7baeffaca5**.
Blobs du contrat V5, de la vision et de la roadmap relus/revalidés :
`c1b0078103507e7b0132af948b34a5cbd7b5950a`,
`df0b3b8591562f13f879db5c3f5ab78286b84cde`,
`e8c4e246df15f223728f94743c958374176fccac`.
La santé du tronc n'est pas rétablie selon les preuves durables #637 :
aucune intégration ordinaire n'est permise. Aucun travail RESET n'a été
effectué par cette analyse.

| PR | État / HEAD observé | Preuve et dépendance pertinente pour LAND |
| --- | --- | --- |
| [#638](https://github.com/djibian/webeeblocks/pull/638) | Draft, `149c0b61b48f335eb4cb925113ccc03afce80cca` | Run 39311714756 success **Draft** ; NO_GO propriétaire 5574571532 sur `024f3c6b3130398736b2e1a2c2afee0e26101b4d` non résolu ; réfutation native seed 14 toujours pertinente. Corps de PR encore centré sur l'ancien diagnostic 2a7 : les discussions et le HEAD actuel prévalent. |
| [#643](https://github.com/djibian/webeeblocks/pull/643) | Ready, `afa9ab4fd77739c3791bf9bbb22f787f8619451b` | Run 39263935202 success, GO propriétaire borné aux repères visuels ; même générateur/test de géométrie. Pas de dépendance démontrée pour rejouer le PID. |
| [#644](https://github.com/djibian/webeeblocks/pull/644) | Ready, `db1220828b893a582a308630a5ac19bae138a969` | Dernier run 39275628686 success, GO géométrique ; changement de colliders du terminal, donc nouvelle qualification native lors de la convergence. Pas de preuve que cela réparerait LAND. |
| [#646](https://github.com/djibian/webeeblocks/pull/646) | Draft, `3d6ecd6b6b502af8b2f642cfb192f158116d4db7` | Run Draft 39275776688 success ; NO_GO de crash natif sur c3326e0 encore pertinent. Partage du générateur et du runner ; aucune raison de l'empiler avec cette analyse. |
| [#647](https://github.com/djibian/webeeblocks/pull/647) | Draft, `4e0e6b21e43c68c19049430b46751c41ccf6ce28` | Empilée sur #641, pas de run canonique de ce HEAD observé ; couloir 0,60 m et retrait des murs changent le domaine physique/perception, non la cause prouvée de LAND. Le témoin actuel dépend des échos des murs. |

Les HEAD, branches et candidats existants sont préservés. Aucun candidat
reconstruit avec les autres corrections n'est nécessaire pour cette analyse
des archives. La réussite de chaque tranche isolée ne se transfère pas au
monde convergé ni à un nouvel HEAD.

## Blocage réel et preuve indispensable avant une réparation

Il reste à distinguer l'impulsion initiale du contact, son amplification
par l'asservissement et l'effet réellement appliqué par les actionneurs.
Une contre-épreuve native **en boucle fermée** doit réfuter une hypothèse
précise, avec un contrôle qui exerce réellement le défaut, une seule
intervention à la couche responsable et des états/chronologies comparables.
Un contraste dont les deux variantes réussissent sans exercer la panne
ne démontre pas sa résolution. Le rejeu PID à états imposés ne remplace
pas cette preuve et ne peut produire une trajectoire « corrigée ».

Une correction ensuite justifiée devra conserver le même Blockly/AST,
les configurations inconnues, les trois cibles et dimensions, les négatifs,
l'oracle indépendant et l'ordre LAND souverain exactement à 210 s. Elle
devra fournir preuves natives avant/après, HEAD Ready stable, CI Gate
canonique complète et revue indépendante résolvant les réfutations. Cette
exécution, auteur du dossier, ne signe aucun GO sur son propre ajout.

L'acceptation pédagogique reste celle d'un **nouvel artefact exact** après
convergence des demandes #635 : H fermé lisible, damiers, trajectoire blanche,
limites rouges effectivement évaluées, largeur/marges, sol et caméra.
Le même `.wbb` doit réussir les configurations 1/2/5, et le parcours complet
Start/simulation/observation/debug/Save/Open doit être personnellement vérifié.
Le FAIL #635 reste inchangé. Aucun PASS pédagogique, TEST_REQUIRED, travail
sur 2–7 ou vol réel n'est revendiqué ni autorisé.
