# Grand Prix U sans murs — hypothèse d'algorithme collégien (NON QUALIFIÉE)

**Statut : Draft expérimental ; ni témoin officiel, ni starter élève, ni PASS natif ou pédagogique.**
Référence de départ : `main@d54f8c98ac6358cfe763d5819b98e0cb532eb4cd`, contrat V5 + #587 (décision du 22/10). Aucune modification des moteurs, des mondes, des oracles, du RESET, du LAND ou du délai de **210,000 s**.

## Ce qui est effectivement livré

- [Vrai projet .wbb éditable](Grand-Prix-sans-murs-algorithme-candidat.wbb), format `webeeblocks-project` v1, profil `progression-grand-prix-u-v1`, blocs Blockly ordinaires seulement.
- [Source reproductible](build.js), déterministe, et [vérificateur](verify.js) de l'arbre sérialisé puis, si Blockly est installé, du véritable chargement / préflight / AST / Save-Open logique.
- **Aucune connaissance de graine, position des H, coordonnées GPS, liste des cibles, état de l'oracle ou numéro de configuration.** Aucun bloc `franchir H`, `compter H`, `choisir arrivée`, et pas de `guarded_move` non intégré (#659).
- Les mêmes blocs sont destinés à toutes les configurations. Cela n'établit PAS leur fonctionnement identique : aucun essai Webots de ce nouveau programme n'est encore probant.

| Mesure de l'arbre Blockly complet | #655 expert sans murs | #702 procédures | Nouveau candidat |
|---|---:|---:|---:|
| Blocs totaux (corps de procédure inclus) | 389 | 395 | **222** |
| Variables déclarées/référencées | 12/11 | 11/11 | **10/10** |
| Procédures (définition / appels) | 0/0 | 3/3 | **1/1** |
| Blocs du flux principal | 15 | 5 | **7** |
| Tests conditionnels Blockly | 25 | 25 | **16** |
| Comparaisons | 46 | 46 | **32** |
| Littéraux numériques (occurrences) | 91 | 91 | **54** |
| Profondeur maximale des corps | 10 (mesure source #587) | non revendiquée | **8** |

Comptage par parcours de **tous** les `inputs` et `next`, identifiants uniques. Le gain 395 → 222 est de **43,8 %** en totalité (pas seulement de l'écran principal), sans vocabulaire spécial. Dix variables, huit niveaux et 18 valeurs littérales distinctes restent lourds : **ce n'est pas une preuve de faisabilité collégien** et les 18 nombres ne sont pas nécessairement 18 paramètres indépendants. Mesurer la compréhension, les corrections et la navigation en classe.

## Algorithme visible et modifiable

Le sens des dix variables est explicite : `côté` (1 à 3), `portes` (nombre de H **confirmés**), `distance` (décimètres de déplacements demandés et acquittés, **pas** la position physique), `H passé` (ne pas recompter un côté), `état` (0 = recherche, 1 = fin de côté, 2 = anomalie / arrêt), `avant` et `bas` (deux observations frontales distinctes), `gauche` / `droite` (échos latéraux locaux entre les montants), `arrière` (vérification après passage).

Le parcours est une répétition de **trois côtés**, avec deux virages décidés par l'élève (`côté < 3`). Sur un côté sans H, progression à altitude haute et virage suivant la distance **commandée** ; aucune paroi latérale ne sert de repère. Une observation frontale rapprochée lance la **procédure Blockly** `observer et décider` : descente en bande supposée, différence entre avant/bas pour distinguer un passage ouvert, observation des montants gauche/droite, correction latérale choisie, franchissement, remontée, confirmation par `range(back)`, puis seulement incrémentation de `portes`. Sur le troisième côté, la fermeture cohérente à deux hauteurs mène à un arrêt avant le H fermé, puis : 1 H = centre, 2 H = déplacement latéral de 0,50 m à gauche, 3 H = 0,50 m à droite, et LAND. Une incohérence définit `état=2`, non un succès.

L'élève conserve donc les décisions **observer → comparer → décider → agir → mémoriser**, le moment de compter et le choix de l'arrivée. La procédure est du Blockly ordinaire **inspectable**, pas une nouvelle capacité native.

### Paramètres et fragilités à démontrer

- **Altitude :** TAKEOFF 0,40 m, puis montée de 0,40 m ; descente/remontée de 0,40 m dans les zones admissibles. La conformité se mesure sur la pose réelle, jamais seulement sur ces commandes.
- **Perception :** proximité avant à 0,30–0,40 m ; discrimination haut/bas +0,30 m ; échos gauche+droite 0,45–0,75 m ; rééquilibrage si écart supérieur à 0,06 m ; confirmation arrière 0,30–0,65 m ; fermeture terminale à ±0,08 m et approche de pose 0,63–0,73 m.
- **Avancement :** pas commandés 0,10 / 0,40 m ; virage sur côtés 1/2 après 2,10 m **commandés**, raffinement des pas après 1,70 m ; garde d'erreur à 2,40 m sur le côté terminal. Ces valeurs peuvent diverger de la position native acquittée.
- **Boucles :** 25 itérations maximales par côté et 6 corrections à l'arrivée, bornes du langage ; aucune supposition de temps réel ou de vitesse n'en est déduite.
- **Réfutation majeure à rechercher :** au milieu d'un côté sans murs, `range(left/right)` peut saturer pour des décalages réels distincts. Elles ne servent ici qu'à proximité des montants ; malgré cela, la stratégie repose sur la précision native des distances **commandées**, des acquittements, des virages et des poses. Ni la marge du rayon 9 cm ni les 210 s ne sont encore garantis. Un H ouvert mal aligné peut produire des échos trompeurs ; les seuils ne constituent **pas** un système de localisation.

## Reproduction (pas de revendication prématurée)

Depuis une copie du dépôt sur ce SHA, avec Node 22+ et Blockly préparé selon le dépôt :

```bash
node experiments/grand-prix-pupil-algorithm/build.js
node experiments/grand-prix-pupil-algorithm/verify.js --structural-only
node experiments/grand-prix-pupil-algorithm/verify.js
python3 tools/blockly/measure_wbb.py experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb
```

Le vérificateur complet est également **ajouté sans supprimer de tests** à `tools/ci/test_runtime_v2_variables.js`. Il reste à observer sa **CI réellement exécutée sur le HEAD exact** : le contrôle structurel réalisé à la génération n'est pas un chargement GUI, et un AST réussi ne constitue pas un vol. Ce script ne remplace jamais les négatifs Webots, la suite native ni un GO indépendant.

## Protocole discriminant Webots R2025a (en attente de monde final)

**Ne jamais substituer le monde à murs de main au monde final demandé.** Lorsque #647/#644/#635 (H fermé composite, bandes, limites rouges *enforced*, scène sans murs, caméra) ont un HEAD final applicable, figer SHA monde, binaire exact, oracle, runtime, projet `.wbb` et digest AST ; exécuter **le même fichier sans l'éditer** sur les configurations 0/1/2/3/4/5/14/15/17 jugées utiles (ou la suite canonique exacte retenue, sans retirer de négatif). Inclure expressément 1/2/3 H et positions sur chacun des trois côtés, côtés sans H, trois poses, erreurs de dérive, saturation latérale, faux H fermés, rétro-franchissement, collision, vol bas hors bande et `wrong-landing` ; conserver tous les **premiers** échecs, y compris non-admission native.

Archiver pour chaque essai : identités et SHA, monde/artefact Webots, AST identique, manifeste et digest, séries de `RANGE`, commandes/`ACK`, cap/altitude, position finale, franchissements, temps simulé, événements d'oracle et verdict. Qualifier séparément les **négatifs complets**, l'indépendance des limites peintes, RESET frais, l'interruption puis commande **LAND à 210000 ms** et sa complétion physique simulée. Aucun ajustement d'oracle, extension de délai ou second programme spécifique à la configuration.

Aucun Webots R2025a n'était exécutable dans l'environnement de cet auteur : **zéro nouvelle réussite native, zéro relecture d'archive native du candidat**. Les cinq réussites archivées de #655 ne sont pas transférables au présent AST, ni au H final composite. La réparabilité LAND #700 intégrée ne suffit pas à qualifier cette variante.

## Essai pédagogique personnel à préparer, PAS demandé maintenant

Partir du starter Grand Prix volontairement vide. **Ouvrir** le `.wbb` de démonstration uniquement pour comparer, pas comme programme donné aux élèves. Demander à l'élève de reconstruire la séquence / les décisions de proximité et d'expliquer la différence `distance` commandée / pose réelle. Faire prédire le cas « côté sans H », localiser le bloc d'incrémentation **après** confirmation arrière, déplacer volontairement un seuil et corriger à partir d'observations et du pas à pas. Effectuer `Démarrer → assembler → Exécuter → observer → RESET → corriger → relancer → Enregistrer sous → Enregistrer → Ouvrir`, et l'annulation d'ouverture ; chronométrer réellement navigation, demandes d'aide et erreurs. Vérifier puis seulement envisager un checkpoint exact préparé par le mécanisme officiel. La progression 2–7 peut être étudiée mais **pas refondue avant PASS personnel du Grand Prix**.

Références : #587, #635, #647, #655, #659, #660, #702 ; aucune auto-revue GO, fusion, `TEST_REQUIRED`, décision pédagogique ni vol.
