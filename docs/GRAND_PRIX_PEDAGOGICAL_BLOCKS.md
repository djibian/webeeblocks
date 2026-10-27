# Grand Prix — architecture pédagogique Blockly

## Protocole prioritaire de conception élève (préparé, NON ACTIVÉ)

**Décision du propriétaire du 27 octobre 2026 : d'abord résoudre les défauts
techniques transversaux ; ne pas relancer le Grand Prix pour l'instant.**
Ce protocole ne remet pas en route les expériences ni les activités 2–7,
et ne constitue pas un nouveau bloc, oracle ou test humain autorisé.

À la reprise, ne plus optimiser uniquement la variante experte qui passe
Webots. Explorer **au moins deux familles algorithmiques réellement distinctes**
et accepter une remise à plat plutôt que des seuils modifiés ou des procédures
renommées. Décrire explicitement les décisions que prend l'élève, les
opérations répétitives bas niveau déléguées et ce qui reste observable.

### Comparaison structurée sur les vrais fichiers .wbb

```sh
python3 tools/blockly/compare_wbb.py chemin/candidat-A.wbb chemin/candidat-B.wbb
python3 tools/ci/test_measure_wbb.py
```

Le résultat JSON identifie chaque **fichier réel par SHA-256**, ses blocs
(total et familles), variables effectivement référencées, nombre de **blocs
SI**, nombre d'**emplacements de tests SI** (y compris chaque « sinon si »,
même vide), présence d'un **sinon** et **gardes de boucles WHILE/UNTIL**
séparément. `conditional_test_slots` additionne les emplacements de tests SI
et les gardes de boucle, sans prétendre compter les décisions cognitives de
l'élève, les chemins exécutés, les comparaisons réelles ou la difficulté.
Une boucle à itérations fixes `repeat` est comptée séparément, **pas**
comme garde conditionnelle. Le rapport indique aussi comparaisons, littéraux
numériques, lectures de capteur, mouvements, mises à jour de variables,
profondeur, longueur du flux principal et **différences avec le premier fichier**.
Les blocs conditionnels complexes ne sont pas équivalents : comparaison,
connecteurs logiques, branches et boucles gardées restent des indicateurs
**distincts**. Les `extraState` Blockly valides décrivent les sockets non
raccordés d'un « sinon si / sinon », et n'en démontrent pas l'utilisation.
Un comparatif ne fait **aucun** classement pédagogique automatique :
ces indicateurs sont des *indices structurels*, pas des capacités d'élève.
Consigner à part les constantes réellement indépendantes à régler, la
répartition des procédures dans l'éditeur et les décisions redondantes.

Deux références historiques utiles **sans équivalence de qualification** :
#660 (67 blocs, 3 variables ; ancienne géométrie, repères latéraux avec murs,
stratégie non qualifiée sur la piste actuelle sans murs) et #703/#705
(232–234 blocs, 10–11 variables ; 16 cas natifs avec les oracles inchangés).
Une réduction de blocs n'efface ni une navigation impossible sans repère,
ni une mesure ambiguë, ni la charge de construire le programme.

### Critères avant d'affirmer « plus simple pour les élèves »

Comparer les approches **avec les mêmes prérequis, temps, consignes et aides** ;
contrebalancer l'ordre d'évaluation si les élèves voient les deux.
La tâche de construction ne doit **pas** commencer avec le .wbb fini,
ni offrir de solution automatique.

- **Concevoir** : expliquer avec leurs mots comment les observations et la
  mémoire suffisent à sélectionner une action ; donner un contre-exemple.
- **Construire** : assembler sans modèle intégral une section non triviale
  comprenant capteur, décision, mémoire et action ; enregistrer la fréquence
  et la nature des aides, les erreurs et le temps de réalisation.
- **Expliquer/déboguer** : reconnaître une lecture ambiguë, localiser la
  condition ou le compteur fautif grâce aux vrais pas Blockly, modifier,
  observer puis corriger et relancer sans indices donnant la solution.
- **Persister** : vrai Save/Save As/Open sur le poste scolaire ; vérifier
  l'identité du .wbb rouvert. Un sélecteur de fichiers simulé ne suffit pas.
- **Transférer** : réutiliser l'idée dans une situation nouvelle et
  pédagogiquement distincte, pas seulement reproduire le Grand Prix.

Publier séparément : (A) fichier et métriques structurelles, (B) tests du
langage/éditeur, (C) preuves natives et négatifs, (D) observation humaine
de construction et d'explication. **Seul D, avec la décision personnelle du
propriétaire et les autres obligations satisfaites, peut soutenir une
acceptation pédagogique**. Zéro seuil arbitraire de blocs, variable ou
profondeur ; pas de PASS, TEST_REQUIRED ou autorisation de vol implicites.

### Filtre pour de nouvelles primitives génériques

Chaque proposition de bloc doit répondre à six questions avant développement :

1. **Difficulté récurrente** : quelle manipulation technique de bas niveau
   encombre au moins deux problèmes d'apprentissage indépendants ?
2. **Généricité** : quels paramètres et capteurs publics l'élève choisit-il,
   sans identité de H, coin, destination, graine, monde ou verdict d'oracle ?
3. **Décision élève** : quelles mesures, comparaisons, choix et hypothèses
   restent visibles, explicables, modifiables et exécutables pas à pas ?
4. **Limites** : quelles bornes, retours saturés/invalides, garanties
   physiques *non acquises* et contre-exemples doivent échouer fermés ?
5. **Réutilisation** : quel deuxième petit .wbb sur une **autre activité**
   démontre la valeur du même bloc, sans adaptation secrète au Grand Prix ?
6. **Gain réel** : quelle opération intellectuelle ou erreur de manipulation
   disparaît, quelles dépendances apparaissent, et qu'en disent les
   élèves ? Les seules économies de blocs ne suffisent pas.

Pistes **à évaluer, pas à implémenter pendant la pause** : approche surveillée
(#659, garde/arrêt bornés et écart commande-déplacement à résoudre),
régulation latérale générique (l'absence de murs interdit d'inventer un
repère au sol à partir de télémètres), sélection explicite selon plusieurs
cas, et sortie sûre d'une recherche sans esquiver le LAND final.
Le « franchir un H », « arriver à gauche » ou « compter un H » déterminé
automatiquement sont des **blocs magiques refusés**. Le vocabulaire ne
doit pas remplacer la réflexion algorithmique.


**Décision du propriétaire, 21 octobre 2026 :** les élèves doivent concevoir
le programme final eux-mêmes. Le témoin expérimental de la PR #655
(389 blocs, onze variables métier) n'est pas la solution à distribuer.

## Hypothèses de programme élève à comparer — non prescriptives

La décision plus récente du propriétaire du **22 octobre 2026** sur #587,
désormais intégrée à `docs/PRODUCT_VISION.md` et `docs/ROADMAP.md` par #661,
remplace toute lecture normative des formes envisagées le 21 octobre.
Le programme final **n'a ni quota imposé de blocs, variables ou procédures,
ni forme de boucle/AST prescrite**. Comparer les stratégies sur un vrai
`.wbb` modifiable : charge cognitive, décisions réellement laissées à
l'élève, lisibilité du fil principal, imbrication, réglages, observation,
débogage et Save/Open, puis capacité des activités précédentes à enseigner
progressivement les concepts nécessaires. Le compte de blocs seul ne suffit pas.

- **Hypothèse : deux variables**, `nombre_H` (passages confirmés) et
  `position` (progression nominale remise à zéro par côté). Une somme de
  distances commandées/acquittées n'est **pas** une mesure de position XY ;
  une stratégie mieux observable, avec plus ou moins de variables, reste
  admissible si elle respecte le contrat du Grand Prix.
- **Hypothèse : une boucle `répéter 3 fois`** pour factoriser les côtés.
  D'autres boucles et décompositions sont acceptables ; le bloc générique
  « parcourir un côté » n'est pas requis et ne doit pas masquer la stratégie.
- **Hypothèse : une procédure Blockly réutilisable**, que l'élève définit
  et modifie avec des blocs ordinaires. Une solution sans procédure, ou
  avec plusieurs procédures, peut être pédagogiquement meilleure.
  Dans tous les cas, l'élève reste auteur du franchissement.
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

## Bloc « répéter jusqu'à » intégré

Bloc `webeeblocks_v2_until` :
« répéter jusqu'à [condition] » sans compteur éditable, abaissé
sur le `while UNTIL` **existant**, `max_iterations:25`.
Pas de boucle illimitée, pas de changement de Runtime ni d'oracle.
Le bloc historique `controls_whileUntil` et ses bornes
personnalisées sérialisées restent disponibles et inchangés.
25 est une valeur conservatrice à qualifier : elle ne prouve
pas la faisabilité du futur programme élève. Les tests intégrés
couvrent compilation/Save-Open et exposition du profil.

## Procédures — premier incrément intégré et qualification logicielle bornée

Définition/appel Blockly, renommage, préflight anti-récursion, budget, restrictions
de profil/backend, source map et Save/Open : voir [le contrat et le démonstrateur](BLOCKLY_PROCEDURES.md).
La sortie terminale et une estimation de progression physiquement mesurée restent
séparées et non implémentées. L'intégration de #658 (CI canonique
39941857392, 43 jobs et vrai CI Gate réussis, revue indépendante sur le HEAD
95a344ace42e93a86054e64c43e286957716b5bc) ne qualifie ni un programme
élève Grand Prix complet ni son acceptabilité pédagogique personnelle.

## Pistes techniques historiques — non prescrites

Cette liste décrit des options ou qualifications encore absentes de cette
tranche ; elle n'impose ni algorithme cible ni ordre d'intégration.
La décision pédagogique du 22 octobre et les preuves d'ergonomie du .wbb
élève guident leur sélection conformément au contrat V5.

1. **Composition et qualification du programme élève** : les procédures
   génériques ont été intégrées avec #658, mais restent à éprouver dans un
   unique `.wbb` élève franchissant les H cachés en natif, avec les négatifs
   inchangés et l'acceptation pédagogique distincte. Le démonstrateur
   générique n'est pas une solution du Grand Prix.
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
Les défauts natifs #637 (RESET_TIMEOUT) et #665 (SIGSEGV avant READY) restent
ouverts. Le contrat V5 §4 impose une preuve de non-interférence propre à chaque
candidat ; le statut ouvert d'une issue ne crée pas à lui seul de veto global,
mais toute interaction critique non levée interdit la fusion concernée.

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
L'enveloppe est désormais intégrée par #658 avec CI canonique Ready exacte
réussie sur le HEAD source précité ; cette qualification ponctuelle ne prouve
ni la disparition des défaillances natives intermittentes #637/#665 ni le PASS
pédagogique du Grand Prix.
