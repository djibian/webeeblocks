# Grand Prix — comparaison contradictoire des stratégies Blockly (2 novembre 2026)

**Statut : dossier expérimental reproductible, pas un programme élève accepté.**
Référence : `main@bc76bcbe72f0d3f6c309ac21e1252d924c350c92` (après intégration
documentaire #802), décision du propriétaire
[#587 du 2 novembre](https://github.com/djibian/webeeblocks/issues/587#issuecomment-6588696664),
méthode #711 et `AGENTS.md` V5. Le monde actif est le Grand Prix U **sans
murs latéraux**, côtés de 2 m, limites et H observés avec l'oracle indépendant.
Les deux portes de qualification sont distinctes : performance native dans ce
monde **et** construction/explication/débogage par un collégien.

## Cinq vrais .wbb examinés — provenance exacte

| Sujet | Commit contenant le .wbb | Chemin | Blob Git |
|---|---|---|---|
| #655 : stratégie sans murs détaillée | `00067ba749aa62fd3344e2897a17a160f8e2ed09` | `experiments/grand-prix-no-wall/Grand-Prix-sans-murs-experimental.wbb` | `947c9f67074a4530083426f0dc467fab3b90cce4` |
| #660 : compacte, guidée par murs | `f3453104e53877b26820bbc0e87d197ef1e989a3` | `tools/blockly/compact_u_demo.wbb` | `05d83dde8ff86c9828379e252ea175f34fbd3eaf` |
| #702 : extraction en procédures | `9f7ec06e3b29c8e0c81ae214f6e4bbbd7dfbf78a` | `experiments/grand-prix-pupil-procedures/Grand-Prix-procedures-sans-murs.wbb` | `2281c954bffbf05393ca33570edab864d995e566` |
| #703 : réécriture sans murs, présente dans main | `bc76bcbe72f0d3f6c309ac21e1252d924c350c92` | `experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb` | `02c0cdef8fc7189aa171b584a8160b52e392ba1c` |
| #705 : contraste explicite | `efaf7aaec94efe657b98c70f040c70e612ff70ed` | `experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb` | `211da9c2c53b3701a21136a2eb5ea3d80ad80ce0` |

**Reproduction indépendante** (checkout contenant ces objets Git ; récupérer
explicitement chaque commit via `git fetch origin <SHA>` si absent). Ne jamais
utiliser un nom de branche mobile à la place du commit exact. Depuis la racine
du dépôt :

```sh
mkdir -p /tmp/gp-strategies
git show 00067ba749aa62fd3344e2897a17a160f8e2ed09:experiments/grand-prix-no-wall/Grand-Prix-sans-murs-experimental.wbb > /tmp/gp-strategies/655.wbb
git show f3453104e53877b26820bbc0e87d197ef1e989a3:tools/blockly/compact_u_demo.wbb > /tmp/gp-strategies/660.wbb
git show 9f7ec06e3b29c8e0c81ae214f6e4bbbd7dfbf78a:experiments/grand-prix-pupil-procedures/Grand-Prix-procedures-sans-murs.wbb > /tmp/gp-strategies/702.wbb
git show bc76bcbe72f0d3f6c309ac21e1252d924c350c92:experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb > /tmp/gp-strategies/703.wbb
git show efaf7aaec94efe657b98c70f040c70e612ff70ed:experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb > /tmp/gp-strategies/705.wbb
git hash-object /tmp/gp-strategies/*.wbb
python3 tools/blockly/compare_wbb.py /tmp/gp-strategies/{655,660,702,703,705}.wbb
python3 tools/ci/test_measure_wbb.py
```

Les cinq SHA-1 de `git hash-object` doivent retrouver les cinq blobs ci-dessus
(dans l'ordre alphabétique des noms de fichiers). Le comparateur existant #711
calcule les SHA-256 **des octets réels**, les métriques et les différences,
`automatic_pedagogical_winner: null`. Aucun fichier de solution complète n'est
fourni comme point de départ de l'élève.

## Relevé de structure du graphe Blockly

Recomptage des blocs dans `workspace.blocks`, `inputs` et `next`, selon les
conventions de `tools/blockly/compare_wbb.py` ; valeurs à confronter à la sortie
JSON de la commande précédente (le relevé n'est **pas** une CI du présent HEAD).

| Sujet | Blocs | Variables utilisées | Conditions SI + gardes | Comparaisons | Lectures de distance | Mouvements | Procédures définies | Chaîne principale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| #655 | 389 | 11 | 28 | 46 | 15 | 31 | 0 | 15 |
| #660 | 67 | 3 | 9 | 9 | 5 | 10 | 0 | 11 |
| #702 | 395 | 11 | 28 | 46 | 15 | 31 | 3 | 5 |
| #703 / main | 232 | 10 | 19 | 34 | 7 | 18 | 1 | 7 |
| #705 | 232 | 11 | 19 | 34 | 7 | 18 | 4 | 7 |

Un « test conditionnel » ici désigne un emplacement de `SI` ou une garde
`WHILE/UNTIL`, **pas** une opération cognitive unique. Les comparaisons
booléennes, l'incertitude de mesure, les constantes indépendantes, la navigation
et la complexité cachée dans des procédures doivent être appréciées séparément.
Ne pas transformer ces chiffres en score ni en plafond de conception.

## Stratégies réellement différentes et contre-exemples

1. **#660 — progression commandée et repères latéraux du monde avec murs.**
   Modèle mental court, mais les échos de parois nécessaires disparaissent sur
   la piste actuelle. Une distance commandée ou acquittée ne prouve pas la pose
   XY ni un virage au coin. Les sept réussites historiques sur l'ancienne piste
   avec murs ne se transfèrent pas. À conserver comme *contre-hypothèse*,
   pas comme candidat pédagogique qualifié sur main.
2. **#655 — recherche active des H et des coins sans murs.** Détection à deux
   altitudes, vérification arrière avant comptage, mémoire et atterrissage codé.
   Cinq réussites natives archivées sur le monde expérimental #647 ; preuves
   partielles/crashs sur d'autres cas. 389 blocs et 46 comparaisons : ni
   conception autonome ni fiabilité sur le HEAD actuel démontrées.
3. **#703 — réécriture de la stratégie sans murs, plus factorisée.** Le fichier
   de 232 blocs est réellement présent dans main et la suite actuelle le charge
   comme témoin *expérimental*. Des réussites natives antérieures ne constituent
   pas une campagne homogène reconstituée sur `main@bc76bcbe`.
4. **#705 — variante de classification par différence `bas - avant`.**
   Même architecture de navigation, **pas une troisième famille indépendante**.
   Campagne native historique 16/16 avec négatifs, RESET et 210000 ms sur son
   domaine exact, mais 11 variables au lieu de 10 et les mêmes 19 gardes/34
   comparaisons. Sur les graphes concernés, les écritures `bas > avant+0.30`
   et `bas-avant > 0.30` divergent en IEEE-754 pour `avant=.25, bas=.55`.
   Pour `avant=.35, bas=.43`, la comparaison à `avant ± .08` et le contraste
   peuvent également diverger. **Ne pas effacer l'état « ambigu » pour gagner
   des blocs** ; consulter la contre-épreuve versionnée de #705.
5. **#702 — contrôle négatif d'abstraction.** Les 395 blocs contiennent
   essentiellement les mêmes décisions que #655, seulement déplacées dans
   trois procédures : utile pour mesurer la navigation dans l'éditeur, **pas**
   une nouvelle solution algorithmique.

**Frontière du comparatif :** nous avons mesuré les vrais fichiers ; nous
n'avons **pas exécuté cinq simulations comparatives sur le même HEAD actuel**.
Il est donc incorrect de produire une comparaison de temps, de robustesse ou
un vainqueur natif entre ces lignes. Les succès cités ne sont que des preuves
historiques sur leurs mondes/arbres respectifs.

## Expérience pédagogique discriminante, sans solution distribuée

Sur la piste sans murs : présenter une *tâche partielle* « observer un H et
proposer l'action sûre » à partir du projet initial ordinaire, **sans WBB fini**.
Faire produire par l'élève une trace `mesure haute → mesure basse → comparaison
→ décision → mémoire → action`, puis faire construire les blocs correspondants.
Comparer une stratégie de détection explicite et une stratégie de contraste,
avec aides et prérequis identiques ; ne jamais dévoiler graine, H exact,
destination attendue ni résultat de l'oracle.

Cas de discussion : `(.35,.70)` ouvert plausible, `(.35,.35)` fermé
plausible, `(.35,.50)` ambigu ; confronter aussi `(.25,.55)` et
`(.35,.43)` aux frontières flottantes. L'élève doit justifier le statut
incertain, le verrou de passage, le comptage **après** dégagement arrière et
ce qui empêche une arrivée incorrecte. Mesurer : section construite sans
aide/avec aide, explication et contre-exemple produit, localisation d'un
défaut de seuil ou compteur en pas-à-pas, correction, nouvelle exécution,
**vrai** Save/Open sur poste scolaire, et transfert du raisonnement à une
situation autre que le Grand Prix. Une édition cosmétique d'un WBB préchargé
ne satisfait pas la tâche.

**Aucun bloc inédit retenu** : la généricité *et* la valeur démontrée sur
une deuxième situation ne sont pas établies ; les procédures ordinaires,
capteurs et comparaisons disponibles suffisent à mettre les hypothèses à
l'épreuve. Aucun « franchir H », classement caché ou solution automatique.

## Preuves encore nécessaires avant une adoption

Exécuter sur le **même monde et HEAD actuel**, après préflight de chaque vrai
WBB compatible, les sept configurations positives cachées, huit négatifs,
rejouabilité, franchissement complet, bandes de vol bas, trois poses et limite
de 210 s ; confirmer le RESET natif strict (5 s/250 ms) et **LAND autoritaire
exact à 210000 ms**, y compris complétion. Les candidats qui ne compilent
plus ou dépendent de murs doivent être refusés explicitement, non « réparés »
par un assouplissement d'oracle. Archiver les digests WBB/AST, SHA du monde,
traces et premier échec. Les outils de la CI canonique sont à préserver ;
ne pas écrire de raccourci qui déclare un PASS.

Ensuite seulement comparer de vrais essais de **construction, explication et
débogage par des collégiens** avec les mêmes acquis et consignes. L'acceptation
reste une décision personnelle du propriétaire et la revue d'intégration une
contre-revue indépendante sur HEAD Ready et CI Gate exacte. Aucune conséquence
sur les activités 2–7, les oracles, RESET, LAND, le matériel ou #800.
