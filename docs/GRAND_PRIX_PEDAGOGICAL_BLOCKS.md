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
Le nouvel incrément de [procédures élèves](BLOCKLY_PROCEDURES.md) étend ce
contrat : une pile principale et des définitions Blockly séparées, sans
paramètres, appels acycliques bornés et observables, simulation seulement.
Il ne gère encore ni les choix par cas, ni le déplacement surveillé.

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

## Procédures — premier incrément implémenté, qualification bornée

Définition/appel Blockly, renommage, préflight anti-récursion, budget, restrictions
de profil/backend, source map et Save/Open : voir [le contrat et le démonstrateur](BLOCKLY_PROCEDURES.md).
La sortie terminale et la progression mesurée restent séparées et non implémentées.

## Incréments suivants — non implémentés

1. **Qualification des procédures** : CI canonique Ready exacte, revue indépendante
   et composition native du futur franchissement, sans confondre le démonstrateur
   générique avec le programme Grand Prix.
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
