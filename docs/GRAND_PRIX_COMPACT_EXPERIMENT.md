# Expérience : trois côtés avec 53 blocs et deux variables

Ce candidat d'ingénierie est un vrai programme Blockly, **pas encore un Grand
Prix qualifié**. Il n'est ni le projet initial élève ni une nouvelle activité.
Les règles, monde, oracle, autorité à 210 secondes, RESET, LAND et contrôleur
restent inchangés. Aucune acceptation pédagogique ou physique n'en découle.

**Révision courante : 53 blocs, 2 variables, 0 procédure, profondeur 3, budget 2881.**
Le programme initial à 47 blocs est conservé dans `compact_u_47_initial.wbb`.
Les sections initiales ci-dessous décrivent cette première expérience ; la
réfutation native et la révision sont détaillées à la fin.

## Composition et état de qualification

Base main lue intégralement : `b478f9dd1854d83345abe13ed20fcf7baeffaca5`.
L'expérience compose explicitement #659 `ebbd5ab824c3c4658fabd7821d62da1cff7d42c4`
et #657 `476f300fb60bb38e60bed14c57b2b9567feaa304`. Le merge local conserve
les deux parents ; ses trois résolutions réunissent le catalogue UNTIL/guarded,
leurs deux chemins de source map et les contraintes de profil, sans doublonner
la capacité while. Les tests respectifs ont été réexécutés.

#658 `b2aa555bd3d424bdea3eebfd278ba13a1059f3c7` a été examinée : les procédures
restent utiles pour décomposer, mais aucune procédure n'est nécessaire à cette
première stratégie compacte. Empiler sa nouvelle sémantique n'est donc pas
justifié ici. Ce choix n'abandonne ni ne réfute ses autres usages.

Au relevé du 22 octobre, aucun GO indépendant applicable n'était publié sur ces
trois HEAD. #657 avait des jobs annulés, #658 un échec APT `Hash Sum mismatch`
(job 119711538342, run 39744813125), #659 un échec d'observabilité
`STEP_CONTINUE_DONE` absent après l'enveloppe hôte de 65 s (job 119712713763,
run 39745163601). Ce dernier chemin hérité est traité par #657 : l'expérience
réutilise son correctif exact de 125 s et son contrôle bash, sans nouvelle
augmentation. Ni les échecs externes ni les jobs réussis ne constituent une
CI Gate verte. Ne pas relancer aveuglément ces candidats.

#637 demeure ouvert et les intégrations ordinaires suspendues. L'auteur de
cette composition ne peut fournir son GO. Toute intégration des dépendances
changera la reconstruction nécessaire et pourra imposer un rebase et de
nouvelles preuves sur le HEAD résultant.

## Algorithme effectivement construit

Fichier : `tools/blockly/compact_u_demo.wbb`, générateur sans argument de monde :
`node tools/blockly/compact_u_demo.js`.

1. Décoller à 0,40 m puis monter de 0,40 m ; initialiser le compteur de H.
2. Répéter trois fois : remettre la distance commandée à zéro ; rechercher
   jusqu'à 1,20 m commandés par avances surveillées de 0,10 m, seuil 0,35 m.
   Si ce seuil est atteint, descendre, avancer de 0,40 puis 0,30 m avec leurs
   incréments explicites, remonter et ajouter un H au compteur.
3. Après cette recherche, si la distance frontale dépasse 0,90 m, compléter
   jusqu'à 2 m commandés et tourner à gauche de 90°. Sinon conserver le cap.
   Le même corps s'applique aux trois répétitions ; pas de variable de côté.
4. Approcher au maximum de 0,40 m avec arrêt au seuil frontal de 0,70 m.
   Deux H : décaler de 0,50 m à gauche ; trois : 0,50 m à droite ; puis atterrir.

L'élève écrit ces choix. Aucun bloc ne connaît H, côté, coin, arrivée, graine,
géométrie cachée, cible ou oracle. La détection frontale est une observation
actuelle ; le programme ne lit pas le monde. **La stratégie a néanmoins des
hypothèses géométriques fortes** : côté public de 2 m et domaine actuel de
placement des H. La recherche à 1,20 m et le discriminant 0,90 m doivent être
compréhensibles à partir d'informations publiques et non découverts par lecture
de graines cachées. L'acceptation de cette présentation reste à décider.

Le compteur H indique ici la fin des blocs de franchissement ; seul l'oracle
indépendant établit le franchissement réel. La reconnaissance d'un H fermé
inattendu n'est pas implémentée dans le corps : cette stratégie n'est pas un
contrôleur d'évitement pour des mondes arbitraires. Le terminal normal n'est
pas rencontré dans la boucle de recherche.

## Mesures reproductibles

`node tools/ci/test_compact_u_project.js` utilise les vrais blocs Blockly 13.2.1,
le profil, le compilateur, le validateur de projet, la réouverture et la source map.

| Programme reconstruit | Blocs réels | Variables du workspace | Procédures | Imbrication de corps | Budget statique |
|---|---:|---:|---:|---:|---:|
| Témoin courant `witness_workspace_u.js` | 265 | 11 | 0 | non recalculée ici | 16620 historique |
| Nouveau candidat | 47 | 2 utilisées | 0 | 3 | 2627 |

265 a été recompté en rechargeant le projet du constructeur courant puis par
`getAllBlocks(false).length`. Ne pas reprendre sans mesure l'ancien chiffre de
389, lié à un autre état. Le gain observé est de 218 blocs, environ 82 %.
Les nombres/comparaisons/incréments sont inclus. Les deux variables automatiques
inutilisées créées par Blockly sont supprimées avant sauvegarde.
Les trois niveaux sont : répétition → jusqu'à → branche du déplacement
surveillé ; les expressions de comparaison ne sont pas des corps imbriqués.

Pas de nouvelle primitive dans cette expérience. L'UNTIL de #657 retire le
paramètre technique de limite visible et le guarded de #659 retire les lectures
et incréments répétés de l'approche. Une procédure aurait ajouté définition et
appel sans retirer de duplication de franchissement dans ce programme.

## Preuves idéales, limites et contre-exemples

Commande : `python3 tools/ci/probe_compact_u_model.py`.
Le générateur est énuméré jusqu'aux **99 dispositions distinctes** possibles
(quatre positions sur chacun des deux premiers côtés, trois sur le troisième,
présence/absence, au moins un H). Un seul AST, identique pour chaque cas, est
exécuté par l'interpréteur partagé. Seul le faux backend de capteurs reçoit les
boîtes du monde ; il fait des rayons géométriques saturés à 2 m. Les trajectoires
idéales sont relues par `oracle_u.Attempt` **inchangé**.

- Nominal : 99/99 `achieved`.
- Déplacements tous multipliés par 0,98, puis séparément 1,02 : 99/99 chacun.
- Erreur systématique de virage −1°, puis séparément +1° : 99/99 chacun.
- Contre-épreuves seeds 0/1/4, avec −10 % ou +10 %, ou −5° ou +5° : aucun
  succès. Mauvaise pose, vol bas hors zone, contact et dépassement de limite
  de boucle apparaissent. Les résultats sont conservés dans
  `evidence/compact-u/ideal-model.json` et `stress-model.json` ; les grandes
  perturbations ne sont ni des erreurs mesurées du contrôleur ni des bornes.

Ces 495 résultats favorables ne sont **pas** 495 vols, ni une probabilité de
succès, ni une marge physique. Mouvement linéaire idéal, attitude nulle,
absence de dérive verticale, retour ACK synthétique, observation axiale idéale,
temps artificiel et récupération non modélisée : aucun temps de vol ou deadline
native n'est qualifié. Les perturbations n'ont pas été combinées. Un modèle
plus défavorable peut encore réfuter la stratégie.

L'ACK et la somme des distances restent des commandes, pas une odométrie.
Le modèle réfute l'idée qu'il suffirait d'avoir des ACK pour garantir ce parcours.
Inversement, il montre qu'une nouvelle primitive d'odométrie n'est pas une
prérequis logique pour **essayer** un programme compact sur ce domaine.

## Expérience native préparée

`python3 tools/ci/run_grand_prix_u_prototype.py --suite compact --seed 0`
utilise le vrai `.wbb` construit, WWI, le contrôleur R2025a et l'oracle actuel.
La suite complète commence par le même AST compact sur seeds 0/1/4 (un/deux/trois
H), puis conserve toutes les expériences et tous les négatifs historiques.
Tout refus, erreur, collision, vol bas interdit, mauvaise pose ou échéance
échoue ; aucun résultat partiel ne devient un succès. Les digests des deux
témoins distincts sont contrôlés séparément.

Webots et Docker sont absents localement : **aucun PASS natif anticipé**.
Le coût accru de la suite doit lui aussi être observé, sans étendre les limites
par défaut. Le premier résultat utile est la trajectoire réelle de ce programme,
particulièrement les erreurs cumulées aux virages et le dégagement du H avant
remontée. Ensuite seulement : décider si quelques corrections de stratégie
suffisent ou si une primitive de progression relative est nécessaire.


## Réfutation native du 47 et révision à 53 blocs

La première CI Draft du candidat `32d43f6aa02a8b29e781b327faa2878f06cf146c`,
run **39747548232**, échoue correctement : même AST compact de digest canonique
`bbf02491224d37ae124a5386139ebfcffd42aa136e74dde1678f7dabb1cf3d3c` :

| Seed / nombre H | Résultat | Temps Webots |
|---|---|---:|
| 0 / 1 | achieved | 161,472 s |
| 1 / 2 | achieved | 161,888 s |
| 4 / 3 | wrong-landing, trois passages | 157,096 s |

ZIP **12412760249**, 8 722 707 octets, SHA256
`453ba042d3b23113e215f4d031b22fa3bcdefd70cb8c0a18b4544b14cc061a30`,
CRC vérifié. Les manifestes s0 et s4 vérifient tous leurs fichiers (9/8).
Le manifeste s1 a un écart sur `webots.log` après clôture ; les huit autres
fichiers vérifient, y compris traces, événements et résultats. Ce défaut de
capture ne doit pas être masqué ; le nouveau résultat doit être vérifié de
nouveau. La clôture/provenance des écrivains fait déjà l'objet de #656 : aucun
nouveau support parallèle n'est créé ici.

Le s4 est déjà décalé avant la pose : dans la trajectoire haute, y est environ
1,872 m avant le déplacement droit de 0,50 m, puis environ 2,340 m au début de
la descente. La pose stable vaut `(0,6558814953 ; 2,3421117189)` pour cible
`(0,7 ; 2,5)`, tolérance inchangée de 0,14 m. Le déplacement pendant LAND est
millimétrique, pas la source de l'écart de près de 0,16 m. Les traces ne donnent
pas l'horodatage interne exact de requête LAND ; on ne l'invente pas.
Le verdict n'est pas converti en PASS et aucune compensation de glissement,
retouche de cible ou modification de LAND n'est effectuée.

La correction est algorithmique et observable : remplacer chacun des deux
translations latérales fixes par « jusqu'à distance du côté choisi ≤ 0,40 m,
avancer de 0,10 m vers ce côté ». L'élève mesure à nouveau au lieu de supposer
la position de départ. Les boîtes de la zone terminale sont publiques ; cette
révision **dépend des parois latérales présentes dans le monde courant**.
Elle ne qualifie pas le monde sans murs demandé dans #635 : si ce repère est
retiré, il faut revoir cette stratégie et sa preuve. Cette dépendance rend
indispensable de comparer ensuite un recalage générique réellement disponible
sur le futur monde, plutôt que de figer cette solution comme finale.

Le nouveau `.wbb` compte **53 blocs**, deux variables utilisées, aucune
procédure, trois niveaux de corps, budget **2881/20000**. Les deux boucles
latérales restent bornées à 25 par le même UNTIL générique. Aucun nouveau bloc
ou accès caché. Le gain reste de 212 blocs, soit **80 %** face aux 265 du témoin
courant. Le 47 est plus court mais **réfuté**, le 53 n'est pas anticipé qualifié.

L'examen de #658 a aussi fourni une réparation étroite et réutilisée de la
source map : reconnaître les opérandes d'arithmétique et les DELTA de
`math_change`, y compris à l'intérieur du guarded. Le test compact vérifie
maintenant ces IDs, au-delà des seuls IDs des instructions ; aucun changement
de sémantique d'exécution ni ajout de procédure n'est nécessaire.

Probe réelle Grand Prix/Blockly/Zelos, Chromium 153.0.8010.0 : Save As/Open,
AST et IDs de source map préservés, 53 blocs, deux variables, zéro erreur JS.
Transport et sélecteurs sont injectés ; **aucune exécution de vol** n'est faite.
La pile initiale de 47 mesurait 1752 unités Blockly de haut et nécessitait encore
un défilement à l'échelle minimale de 0,55 dans 1600×1000. Le nombre de blocs
ne suffit donc pas à établir la lisibilité en classe. Une procédure pourra
être réévaluée pour sa mise en page et sa décomposition, même sans gain de
nombre de blocs. Le probe reproductible est `tools/ci/probe_compact_u_ui.mjs` ;
variables d'environnement identiques à la probe guarded d'origine.
