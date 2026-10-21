# Grand Prix sans murs : témoin Blockly expérimental

## Sujet et frontières

Monde exact #647 `4e0e6b21e43c68c19049430b46751c41ccf6ce28`,
empilé sur #641, côté public 2,00 m, couloir 0,60 m, rayon 0,09 m.
Main observé `b478f9dd1854d83345abe13ed20fcf7baeffaca5` ; intégrations
ordinaires suspendues par #637. Aucune modification du monde, de l'oracle,
du Runtime, de RESET, LAND ou de la caméra. Aucun vol réel.

Le dossier ne remplace pas le témoin livré. `workspace.js` construit de vrais
blocs autorisés, préflighte le profil U, compile et exige l'AST exact de
`program.js`, puis vérifie la sauvegarde/réouverture `.wbb`. Le backend et
l'interpréteur sont ceux de production. Le runner expérimental est une copie
bornée du runner natif #647 ; seule l'entrée Node et le répertoire de sortie
changent. Le point d'entrée lance uniquement un témoin sur une configuration.
Les branches historiques du probe ne sont pas des campagnes autorisées.

## Stratégie candidate figée avant nouvelle acquisition

AST SHA-256 (JSON trié compact) :
`b27f65fa1961de2a7b162b11feffcd6c1452769056f10d03e4770c5f32dd5d19`.
Budget préflight 13370 / 20000. Même programme sur tous les essais.

- Mémoriser les décimètres commandés ; tourner après 2,10 m commandés pour
  les deux côtés de longueur publique 2,00 m. L'écart tient compte de l'arrêt
  relatif observé dans le Runtime ; ce n'est pas une lecture de position.
- Approcher chaque H à altitude haute avec `range(front)`, descendre dans
  sa bande, comparer la perception haute/basse, vérifier les deux montants
  latéraux par les capteurs et se recentrer si nécessaire.
- Parcourir le passage bas, remonter, confirmer le panneau derrière avant
  d'incrémenter le compte. Le H terminal est reconnu par une fermeture
  persistante à deux altitudes ; atteindre la distance de pose mesurée,
  choisir centre/gauche/droite par mémoire, puis LAND ordinaire.
- Les graines, positions exactes des H, GPS, polygone, oracle et réponse
  attendue ne sont jamais des entrées du programme.

La commande 2,10 m et les seuils sont des hypothèses expérimentales communes,
pas une garantie de dérive/odométrie universelle. Pas de nouvelle API proposée.

## Observations antérieures perdues — aucune preuve substituée

Avant réinitialisation de l'environnement temporaire, les sorties observées
rapportaient : ancien témoin s3 `off-track`, 28,632 s, x=2,210135586976196,
aucun TURN ; nouveau témoin s3 `achieved`, deux passages, 123,776 s.
Des échos latéraux de H éloignés réfutaient la prédiction de saturation
latérale permanente, sans restaurer le virage historique.

**Les traces complètes ont disparu avant sauvegarde durable. Ces nombres ne
constituent pas une archive native vérifiable.** Deux préparations avaient
aussi échoué (proxy Qt puis readiness) ; le premier vol historique terminé
était refusé globalement par le runner à cause de USER/USERNAME absent,
bien que l'évaluateur ait écrit `off-track`. Aucun PASS n'est récupéré de
ces observations ; ne pas fabriquer leurs fichiers ni leurs manifestes.

L'AST reconstruit est comparé au digest observé ci-dessus et est identique.
L'acquisition repart dans un environnement neuf après cette sauvegarde du
source, parce que les preuves indispensables ont été perdues, non pour
remplacer un négatif. Les nouvelles traces seront archivées après chaque cas.

## Protocole de reprise

1. Un nouvel essai historique s3, sans changement de code : conserver tout
   refus ; arrêter ce contraste au premier résultat interprétable.
2. Nouveau témoin s3 ; si succès, conserver le programme inchangé et tester
   s1/s4 pour les comptes 1/3, puis les autres combinaisons de côtés
   (s0/s14/s15/s17) et les configurations de livraison s2/s5.
3. Arrêter l'extension au premier échec algorithmique, diagnostiquer la trace
   et conserver le candidat/négatif avant toute correction. Les erreurs de
   préparation restent distinctes des réfutations de navigation.
4. Les négatifs géométriques, altitudes, comptage, trois poses et l'autorité
   indépendante à 210 s restent nécessaires. Aucun test spécifique RESET.

Préparation standard : `bash tools/prepare_runtime_v2.sh`, Webots R2025a
avec assets source exacts `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`,
`WEBOTS_HOME` configuré, Node >=22. En environnement supportant AF_UNIX,
le runner natif partagé exécute le contraste historique. Ici utiliser son
option explicite `--native --tcp`, un affichage X TCP froid par cas et USER
défini ; aucune tolérance supplémentaire aux erreurs natives.

Commandes :

```sh
node experiments/grand-prix-no-wall/workspace.js /tmp/witness.wbb
python3 tools/ci/run_grand_prix_u_prototype.py --native --tcp --suite witness --seed 3 --side 2
python3 experiments/grand-prix-no-wall/run_native.py --seed 3
```

`run_native.py` conserve aussi un résultat négatif et retourne alors le
résultat, sans le transformer en succès. Exiger explicitement `achieved`
pour revendiquer une réussite ; erreur/absence de résultat = UNPROVEN.
Ni CI Gate, ni GO indépendant, ni PASS humain ne sont fournis par ce dossier.

## Négatifs distincts préparés après les trois comptes positifs

`negative_program.js`/`negative_workspace.js` construisent aussi de vrais blocs,
préflightent et exigent leur AST exact. Modes séparés : mauvaise pose s3,
vol bas hors bande s3, collision s0, franchissement inverse s0, échéance s3.
Le mode `deadline` oscille à altitude haute sur le premier côté libre jusqu'à
l'interruption indépendante ; après refus TIME_LIMIT, seules des requêtes
inopérantes tardives testent le verrouillage. **Aucun RESET n'est envoyé.**
Les autres capacités et les critères/210000 ms restent inchangés.
Le runner négatif utilise l'argument `--mode`, pas les anciens modes timeout
qui testaient aussi la récupération RESET. Arrêt sur le premier résultat non
interprétable ou non conforme, conservation de tout cas commencé.

Une erreur de préparation Blockly a refusé avant acquisition le déplacement
inverse historique à 0,35 m (pas de champ de 0,10 m) ; le négatif ordinaire
utilise 0,30 m, suffisant seulement si le vrai oracle confirme un passage
entier préalable. Aucun résultat natif n'est déduit de cette préparation.
