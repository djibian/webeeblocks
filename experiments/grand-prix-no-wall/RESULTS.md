# Grand Prix sans murs — résultat du 21 octobre 2026

**Conclusion B : stratégie Blockly générique partiellement démontrée.**
L'ancien témoin est réfuté nativement. Un nouveau programme ordinaire réussit
cinq configurations avec preuves complètes, couvrant 1/2/3 H et les trois
poses ; deux autres résultats natifs réussis ont des archives partielles.
Deux chargements Webots ont échoué avant toute tentative. L'ordre indépendant
LAND à exactement 210 s est observé, mais sa complétion native manque et le
runner refuse ce négatif. Aucune capacité manquante n'est démontrée.

## Sujets exacts et intégration

- `main` observé : `b478f9dd1854d83345abe13ed20fcf7baeffaca5`.
- Contrat V5 / vision / roadmap : blobs `c1b0078103507e7b0132af948b34a5cbd7b5950a`,
  `df0b3b8591562f13f879db5c3f5ab78286b84cde`,
  `e8c4e246df15f223728f94743c958374176fccac` ; identités revalidées.
- Monde exact #647 : `4e0e6b21e43c68c19049430b46751c41ccf6ce28`,
  dépendant de #641 `c965bdc1cb39b6ede1f603a875a51a0b5d9cf05e`.
- Programme/compilateur/harness positifs sauvegardés avant reprise native :
  `64969bfee49d0cc9bd0aba7e015280ac229b6a6e` ; protocole négatif sauvegardé
  à `6105ad38481a5b926bfbc12408b509015cacaef9` avant son acquisition.
- AST unique des essais positifs :
  `b27f65fa1961de2a7b162b11feffcd6c1452769056f10d03e4770c5f32dd5d19`.

L'état de santé de main reste non restauré selon #637 : aucune fusion
ordinaire, aucun changement RESET/délais/protections, aucun diagnostic LAND
#638 ou caméra #646, aucun GO auteur, aucun PASS humain, aucun vol réel.
Les PR #638/#641/#643/#644/#646/#647 et leurs HEAD sont préservés.

## Contre-épreuve historique minimale

`--suite witness --seed 3 --side 2`, vrai Webots R2025a et vrai pipeline
Blockly : **`off-track` à 28,632 s**, 0 H, aucun TURN. Le disque de rayon
0,09 m franchit la limite du premier côté. L'ancien programme continue ses
avances puis atteint sa limite de boucle ; cette erreur tardive est conservée.

La prédiction de saturation latérale permanente était trop forte : des H
éloignés produisent quelques échos latéraux. La distance frontale et ces
échos ne déclenchent toujours pas le premier virage. L'échec algorithmique
prévu est donc confirmé avec une perception native plus riche que le modèle.
Archive `evidence/historical-s3.tar.xz`, manifeste interne entièrement vérifié.

Les premières observations avant la pause avaient été perdues ; elles sont
explicitement étiquetées dans README et ne remplacent aucune preuve. La
réacquisition publiée ici conserve ses propres octets et son propre sujet.

## Même programme Blockly dans les mondes inconnus

Le témoin mémorise les déplacements commandés sur les deux côtés publics de
2,00 m, tourne après 2,10 m commandés et se sert des quatre rangers natifs
pour approcher les H, comparer haut/bas, vérifier leurs montants latéraux,
se recentrer, passer, remonter et confirmer le dégagement par le panneau
arrière avant de compter. La fermeture persistante à deux altitudes déclenche
l'approche finale mesurée puis la pose choisie par mémoire.

Ni seed, ni coordonnées de H/GPS, ni réponse attendue de l'oracle n'entrent
dans cet AST. Le Node probe ne pilote pas une trajectoire hors interpréteur :
il construit de vrais blocs autorisés, les préflighte, compile, sauvegarde et
réouvre le `.wbb`, exige l'égalité stricte de l'AST, puis utilise le backend et
l'interpréteur partagés. Budget 13370/20000, 389 blocs dans cet exemple expert.
Le fichier `.wbb` fourni est éditable ; il n'est pas le starter vide élève.

La commande 2,10 m est une hypothèse de compensation des arrêts relatifs,
commune aux configurations testées, pas une garantie universelle d'odométrie.
Le résultat ne qualifie ni un côté plus long ni toutes les 65536 graines.
Le nombre de blocs et la lisibilité en classe demandent encore une évaluation
pédagogique ; une réussite native ne constitue pas cette acceptation.

| Seed | H ouverts sur côtés (0–2) | Temps Webots | Pose | État des preuves |
|---|---|---:|---|---|
| 0 | 0 | 100,544 s | centre | réussite, archive/rejeu vérifiés |
| 2 | 0 | 108,864 s | centre | réussite, archive/rejeu vérifiés |
| 3 | 1, 2 | 123,776 s | gauche | réussite, archive/rejeu vérifiés |
| 4 | 0, 1, 2 | 143,744 s | droite | réussite, archive/rejeu vérifiés |
| 15 | 2 | 102,560 s | centre | réussite, archive/rejeu vérifiés |
| 14 | 0, 2 | 124,064 s | gauche | natif réussi, archive partielle : `node.log` |
| 5 | 0, 1, 2 | 137,664 s | droite | natif réussi, archive partielle : `flight.log` |
| 1 | 0, 1 | — | — | SIGSEGV au chargement, aucune admission |
| 17 | 1 | — | — | SIGSEGV au chargement, aucune admission |

Les numéros de seed ne sont pas assimilés aux noms des lanceurs Windows.
Aucun de ces cas refusés/partiels n'a été relancé pour remplacer son résultat.
Le cas s15 démontre notamment deux virages sans aucun H sur les deux premiers
côtés. La réserve minimale des cinq réussites vérifiées est **66,256 s**.

## Géométrie, altitudes et intégrité

Le monde est byte-comparé à `world_text(generate(seed,2))` avec uniquement la
résolution locale des assets et les contrôleurs TCP externes prévus par le
runner : largeur 0,60 m, aucun mur latéral, H collidants préservés. L'oracle
inchangé contrôle le segment et le disque de 0,09 m, les franchissements
entiers orientés, les bandes basses et les trois côtés avant la pose stable.
Les vraies poses, vitesses et altitudes sont dans chaque `native_trace.csv`.

`verify_native.py` recompile le vrai Blockly, vérifie le manifeste, compare
l'AST, rejoue les poses avec l'oracle sans modifier ses critères et mesure
les marges balayées aux arêtes et colliders. Ce rejeu ne recrée **pas** les
contacts natifs : ils restent une observation propre du Supervisor original.
Sur les cinq succès vérifiés, les marges minimales mesurées sont **0,104152 m**
aux limites et **0,089518 m** aux colliders H, rayon déjà soustrait. Ce sont
des minima des segments observés, pas des bornes physiques universelles.
Les diagnostics JSON conservent les minima exacts de chaque cas et les
événements de dégagement à +0,33 m, avec altitude réelle.

Les archives complètes contiennent les événements capteurs/commandes/variables,
monde, layout, résultats/diagnostics natifs, trace de pose, logs Webots/Node/
contrôleurs, manifeste original et transcript du runner. `archives.json` lie
les tailles/digests et conserve les divergences, sans corriger les anciens
manifestes. Une seconde copie tardive des logs s14, différente, est conservée
séparément. La cause de ces incohérences de capture n'est pas établie ; leur
absence sur cinq cas ne prouve pas que le mécanisme soit réparé.

## Négatif indépendant 210 s : résultat partiel, runner refusé

Un programme Blockly ordinaire distinct oscille à altitude haute sur le côté
libre s3 jusqu'à expiration ; aucune information d'oracle ne pilote ce témoin.
Archive `evidence/negative-deadline.tar.xz`, manifeste interne vérifié :

- admission à **16288 ms**, ordre indépendant **LAND à 226288 ms**,
  soit **210000 ms exactement**, avec interruption de la commande active ;
- résultat `not-achieved / time-limit`, 210,000 s ;
- COMPLETE, FAILURE, MOVE et STOP tardifs : tous refusés `TIME_LIMIT` ;
- **aucun RESET envoyé** ; aucune réussite rétablie ;
- **aucun `TRACE LAND` de complétion** : le runner sort 1,
  `missing independent forced LAND/failure`.

L'ordre à l'instant imposé et le verrouillage sont observés ; la complétion
native de LAND n'est pas démontrée. La campagne négative s'arrête à ce premier
refus conformément au protocole. Les autres négatifs préparés (mauvaise pose,
altitude hors bande, collision, sens inverse) ne sont **pas exécutés**, et ne
sont pas revendiqués qualifiés. Aucune analyse causale LAND n'est menée ici.

## Reproductibilité et limites de livraison

Webots officiel R2025a : archive tar SHA-256
`c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`,
assets `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, Node 24.19.0,
Blockly 13.2.1, rendu Mesa logiciel, affichage X TCP froid par cas et contrôleurs
externes officiels. Les seuls messages AF_UNIX déjà diagnostiqués par le
runner `--tcp` sont exemptés ; les SIGSEGV et autres erreurs restent refusés.
Les paquets X du second environnement sont vérifiés contre les métadonnées
Ubuntu ; une panne 503 du snapshot a nécessité le miroir officiel et Xvfb
`2:21.1.12-1ubuntu1`. Aucun critère de mission n'a été changé.

Préflight `.wbb` et budget positifs ; les cinq programmes négatifs préflightent
aussi. Les 18 tests d'oracle et 4 tests de géométrie inchangés passent. Ces
contrôles locaux ne sont ni CI Gate Ready ni revue indépendante.

Le monde #647 conserve encore le terminal historique : le **H fermé composite
#644**, les marquages #643, les autres corrections visuelles et la livraison
Windows finale doivent être consolidés puis revalidés sur un nouvel exact
HEAD. Le candidat demeure expérimental/Draft, sans remplacement automatique
du témoin enseignant livré. Restent indispensables : preuves complètes des
configurations manquantes/partielles, négatifs natifs, résolution indépendante
du refus LAND dans son chantier, CI canonique Ready et revue indépendante,
puis qualification pédagogique explicite. Aucune nouvelle API n'est justifiée
par cette étude et aucun PASS humain implicite n'en découle.
