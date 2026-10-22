# Grand Prix — architecture pédagogique Blockly

**Décision du propriétaire, 21 octobre 2026 :** les élèves doivent concevoir
le programme final eux-mêmes. Le témoin expérimental de la PR #655
(389 blocs, onze variables métier) n'est pas la solution à distribuer.

## Programme cible

- **Deux variables** : `nombre_H` (passages confirmés) et `position`
  (progression sur le côté courant, remise à zéro à chaque côté).
  Une somme de distances commandées/acquittées n'est **pas** une
  mesure de position XY et ne doit pas être présentée ainsi.
- **Une boucle `répéter 3 fois`** pour les côtés. L'élève choisit les
  mouvements et calcule `position`, aucun bloc « parcourir un côté ».
- **Une procédure Blockly élève réutilisable comme cible**,
  définie et modifiée avec des blocs ordinaires dans le .wbb.
  L'élève construit le traitement d'obstacle et le franchissement.
- **Pas de bloc magique** qui fournit ouvert/fermé, numéro de porte,
  nombre de H franchis, fin du circuit ou bonne pose. Le capteur
  et des comparaisons numériques fondent les décisions de l'élève.
- **Répéter jusqu'à sans limite numérique visible**, mais boucle
  techniquement bornée et contrôlée avant et pendant exécution.
- **Atterrissage choisi** : 1 H centre, 2 H gauche 0,50 m,
  3 H droite 0,50 m; un cas invalide n'est jamais un PASS.
- Les règles de #587 restent inchangées : trois côtés/deux virages,
  1–3 H ouverts cachés, un H terminal fermé détecté par observation,
  vol bas limité aux bandes, échec irréversible et LAND de sécurité
  exactement à 210 secondes. Aucun vol réel n'est autorisé.

## Endroits du dépôt à modifier

`crazyflie_v2.js` définit les blocs. `activities.js` et
`grand_prix_u/setup.js` exposent les primitives selon le profil.
`semantic_ast.js` compile; `activity_contract.js` valide
blocs, capacités et bornes; `interpreter.js` exécute; le backend
fournit les commandes/senseurs. `project_files.js` garantit
Save/Open .wbb, `execution_observer.js` relie les pas aux blocs.

Le compilateur actuel exige un unique programme connecté, avec
takeoff en première instruction et LAND à la fin, jamais imbriqué.
Il ne gère ni les procédures élèves, ni les choix par cas,
ni un déplacement surveillé comme instruction.

## Première réalisation (cette branche)

Bloc `webeeblocks_v2_until` :
« répéter jusqu'à [condition] » sans compteur éditable, abaissé
sur le `while UNTIL` **existant**, `max_iterations:25`.
Pas de boucle illimitée, pas de changement de Runtime ni d'oracle.
Le bloc historique `controls_whileUntil` et ses bornes
personnalisées sérialisées restent disponibles et inchangés.
25 est une valeur conservatrice à qualifier : elle ne prouve
pas la faisabilité du futur programme élève. Les tests ajoutés
couvrent compilation/Save-Open et exposition du profil.

## Incréments suivants — non implémentés

1. **Procédures Blockly** : définir/appeler dans le même .wbb,
   préflight anti-récursion, signature et définition présentes,
   budget conservateur, source map, debug et Save/Open.
2. **Déplacement surveillé** : avancer au plus de D mètres
   tant que capteur et seuil choisis le permettent; pas bornés,
   tests NaN/saturation, échec fermé sur mesure non fiable,
   aucune lecture de scène/oracle. Mise à jour facultative de
   `position` seulement à partir de déplacements acquittés,
   jamais d'un GPS fictif; pas de double comptage sous H.
3. **Équilibrage latéral** et **placement à distance d'obstacle** :
   algorithmes de régulation génériques bornés avec tolérance
   élève, sans H reconnu automatiquement ni sécurité affaiblie.
4. **Selon 1/2/3/autre** : sélection générique, sans connaissance
   du compte réel fourni par le système.
5. **Sortie sûre de boucle/arrivée** : le H fermé doit conduire,
   lors du troisième côté, au LAND final de niveau principal,
   sans troisième virage. Distinction entre échec, interruption
   et fin normale nécessaire; interface/AST encore à spécifier.
6. **.wbb témoin élève et qualification** : un seul programme
   sur configurations cachées 1/2/3 H, négatifs inchangés,
   Webots R2025a natif, CI V5 exacte, contre-revue indépendante
   et acceptation pédagogique humaine.

**Statut : architecture pédagogique, non programme final qualifié.**
`main` demeure concerné par l'issue santé #637 :
pas de fusion ordinaire pendant ce blocage.

## Réparation CI du 22 octobre 2026

`student-ui` échouait avant Webots sur son contrôle de style : le nouvel UNTIL
ajoutait un second `control_blocks`. Il utilise maintenant `loop_blocks`, déjà
défini dans le thème ; le test construit un vrai bloc et vérifie son style.
L'assertion du workflow reste inchangée.

L'archive native du run 39691800807, artefact 12388398411 (ZIP 5 244 octets,
SHA256 `296c75759dd84974ebbb4710760c5aac82fd64dfee8b8ed952b3f505aa8df1c3`,
CRC des cinq membres vérifiés), montre une interruption hôte : exit 124,
aucune erreur navigateur, séquence de sept pauses correcte, MOVE 10 acquitté,
LAND 11 envoyé à 23:15:37.183 UTC sans réponse avant la coupure à 23:15:42.
Continue avait commencé à 23:15:13.903 : moins de 29 s de son attente de 60 s
avaient été disponibles. Aucun nouvel UNTIL n'est utilisé dans ce scénario.
Le harnais, le workflow natif, l'interpréteur et le contrôleur C concernés sont
identiques à main b478f9d. Cela démontre la troncature, pas la réussite future
de LAND ni l'absence de toute lenteur native.

L'enveloppe hôte devient 125 s = les 65 s déjà accordées au démarrage/pas +
les 60 s déjà autorisées à Continue. Aucun délai de requête produit, de contrôleur,
de RESET ou d'oracle ne change. Un test conserve 65 s comme contre-exemple et
contrôle cette relation. Le succès exige toujours les événements émis après le
véritable état TERMINÉ et la trace native LAND ; aucune complétion synthétique.
La nouvelle CI Ready exacte doit encore vérifier la complétion native.
