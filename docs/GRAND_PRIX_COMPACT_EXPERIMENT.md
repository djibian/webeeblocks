# Expérience : trois côtés avec 67 blocs et trois variables

Ce candidat d'ingénierie est un vrai programme Blockly, **pas encore un Grand
Prix qualifié**. Il n'est ni le projet initial élève ni une nouvelle activité.
Les règles, monde, oracle, autorité à 210 secondes, RESET, LAND et contrôleur
restent inchangés. Aucune acceptation pédagogique ou physique n'en découle.

**Révision courante : 67 blocs, 3 variables, 0 procédure, profondeur 3, budget 3153.**
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


## Réfutation du 53 et recentrage commun (63 blocs)

Run Draft **39748644554**, HEAD `de4ddbad5410def4205b37a82fcb9573e251c74e` :
le seed0/1H échoue à `wrong-landing` en 139,944 s, avec un H franchi et aucune
exception du programme. La pose stable vaut `(0,6660587249 ; 1,7849187039)` pour
cible `(0,7 ; 2)`. Cette branche n'exécute aucune des deux nouvelles boucles
latérales. Les consignes acquittées identiques ne garantissent donc pas une
position terminale identique ; ni le succès précédent s0 ni le modèle ±2 %
ne permettent d'ignorer cette réfutation. Aucune cause de timing/PID particulière
n'est attribuée sans preuve.

Archive **12412428083**, SHA256
`bfcfb9cdb460122aa1191d139dc8ef1aa09bbe91a56dd51ea9a6619fcbc214f2`, CRC
vérifié ; les huit fichiers du manifeste du cas vérifient leurs empreintes.
Le 53 est conservé dans `compact_u_53_lateral.wbb` (constructeur avec
`center:false`). Pour reproduire le 47 : `build({lateral:false,center:false})`.

La révision ajoute avant le choix de pose **deux UNTIL ordinaires** : s'éloigner
du côté gauche tant que sa distance est inférieure à 0,80 m, puis du côté droit
selon le même principe, par pas de 0,10 m. L'élève écrit le recentrage à partir
des deux distances ; aucun bloc de centrage ni procédure cachée. Ces deux
boucles s'appliquent à tous les nombres de H. Les deux translations finales
mesurées du 53 restent ensuite inchangées. La zone centrale idéale permet ce
recentrage ; seuls les essais natifs peuvent valider ses observations et sa
stabilité. Aucune nouvelle borne de capteur, de cible ou de temps.

Mesures : **63 blocs, 2 variables, aucune procédure, imbrication 3, budget
3139/20000**. Le gain de nombre de blocs est de 202, soit environ 76 % face
aux 265 du témoin courant. C'est un coût pédagogique supplémentaire justifié
par un échec natif, pas un objectif de chiffre arbitraire.
La suite native prépare maintenant les sept seeds0/1/3/4/14/15/17 pour ce même
AST compact, puis tous les témoins/négatifs historiques. Le coût doit toujours
respecter les enveloppes existantes. Cette révision reste limitée au monde
actuel doté des parois terminales ; elle ne qualifie pas le futur parcours sans
murs. Le recalage observable sans ces parois demeure une question produit ouverte.


## Réfutation du 63 et correction latérale avant le H (69 blocs)

Le run Draft **39749516989**, HEAD `29dcabd0aaea64d3e930010a4fe0765f3b613880`,
établit le même AST63 : seed0 achieved150,272s ; seed1 achieved156,448s ;
seed3 refuse `envelope-contact` à80,952s avant le premier franchissement.
Les quatre seeds suivants ne sont pas exécutés : aucune qualification de leur
trajectoire n'est extrapolée.

ZIP **12412837429**, SHA256
`4f02ca909bb2f663f77817cea44b67830c3b52a55f8a3074a0834b10400ff8ba`, CRC vérifié ;
les manifestes des trois cas vérifient leurs 9/9/8 fichiers. Diagnostic du refus :
position `(1,7959941675 ; 0,6626745842 ; 0,4157484933)`, premier H à `(2 ; 0,95)`
sur le deuxième côté. Le décalage latéral d'environ0,204m dépasse le domaine
central de passage de0,19m (demi-ouverture0,28 moins rayon0,09). Les erreurs de
progression commandée affectent donc aussi le passage, pas seulement la pose.
Le programme continue après ce refus de mission irréversible : ses observations
ultérieures ne constituent jamais une restauration du résultat.

Révision : dans le corps du seuil, avant toute descente, comparer RANGE gauche
et droite. Commander0,10m vers la droite si la gauche est plus proche, sinon
vers la gauche. C'est une **correction bornée d'alignement**, pas un centrage
prouvé pour un état arbitraire ; à égalité, la branche gauche est choisie.
L'élève écrit le SI/SINON et ses deux mouvements. Aucun appel au plan caché,
aucune modification des portiques ou des marges. Le compteur de distance reste
celui des mouvements avant, les translations latérales ne l'incrémentent pas.
La correction utilise les parois actuellement observables à l'approche : sa
validité ne se transfère pas au futur monde sans murs.

L'ancien63 est conservé dans `compact_u_63_arrival.wbb`, constructeur
`build({gateCorrection:false})`. Pour reconstruire les47/53, ajouter également
`gateCorrection:false` aux options décrites précédemment.
Le69 compte deux variables, zéro procédure, **quatre** niveaux de corps :
repeat → UNTIL → guarded → IF d'alignement. Budget3514/20000. Ce coût est explicite ;
le niveau supplémentaire ne doit pas être caché derrière une notion de bloc
magique. Gain196 blocs, environ74 % face au265 courant.

Le modèle69 repasse99/99 dans chacun des cinq domaines idéaux séparés retenus,
preuve conservée dans `evidence/compact-u/ideal-model-69.json`. La page réelle
Zelos repasse la sauvegarde/réouverture et les IDs sans erreur JS
(`ui-69.json`) ; pile2320 unités de haut, largeur853, à zoom minimal0,55 :
le défilement reste nécessaire. L'utilité d'une procédure pour **décomposer et
mettre en page** reste donc à comparer, même si elle augmenterait le nombre de
blocs. Le69 ne reçoit aucun PASS natif anticipé : même sept seeds requis,
toutes les obligations historiques, aucun nouveau délai ni tolérance.


## Le 69 réfute la comparaison latérale près d'un coin ; révision67

Run **39750665195**, HEAD `040ffa91072d46bf8ddbd6d355bf17e6c3a4c68b` :
seed0 achieved144,544s, seed1 achieved156,000s, puis seed3 refuse
`envelope-contact` à112,744s, un H franchi et `UNSAFE_OR_TIMEOUT`. Les quatre
seeds suivants ne sont pas exécutés. Le premier H du seed3 est donc passé,
mais la correction n'est pas suffisante pour le suivant.
Archive **12413865919**, SHA256
`b4e96797c9dac48fe52ee29443df55ad9567bb5588dd4bdc0bed03e8f53c7b10`, CRC vérifié ;
tous les fichiers des trois manifestes9/9/8 vérifient leurs empreintes.

La trace décisive montre RANGE gauche=2 (saturée) et droite=0,659484446 à
l'approche du H du troisième côté ; le programme choisit donc MOVE gauche0,10.
Le refus est localisé à `(1,6813988565 ; 1,7995728319 ; 0,7815278283)`, avant la
traversée du deuxième H. Près du coin, les deux rayons n'observent pas des
surfaces symétriques du même couloir : leur comparaison ne fournit pas son
centre. La disponibilité d'une distance finie n'établit pas cette hypothèse
supplémentaire. Le69 est conservé dans `compact_u_69_gate_correction.wbb`.

**Architecture révisée :** supprimer cette correction latérale approximative.
À la fin des deux premiers côtés, remplacer la terminaison sur2m *commandés*
par une approche **mesurée** : UNTIL distance devant≤0,50m, avances surveillées
ordinaires. Le mur extérieur du monde courant permet de recaler la coordonnée
qui deviendra latérale après le virage. Le compteur de commandes ne prétend
plus établir l'abscisse exacte du coin.

Une troisième variable `côté`, initialisée0 et incrémentée après chaque corps,
distingue les deux virages de l'arrivée : si `côté<2`, terminer l'approche du
coin puis tourner ; lors du troisième passage, rejoindre la pose. Elle évite
le discriminant frontal0,90m devenu fragile lorsque les coins sont recalés.
C'est un compteur élève ordinaire, pas un numéro fourni par le monde. La
répétition de trois côtés reste visible ; ni bloc de côté ni état caché.
Le recentrage terminal du63 et les placements mesurés restent conservés.

Mesures67 : **3 variables utilisées, 0 procédure, imbrication3, budget3153/20000**.
Gain198 blocs, environ75 % face au265. Le choix initial de deux variables et
la tentative de correction locale sont révisés sur preuves, pas maintenus comme
objectifs. Ce programme est plus explicite mais nécessite encore des
recalages sur les murs actuels. Il ne qualifie pas #635 sans murs ; la recherche
initiale jusqu'à1,20m reste également une hypothèse de domaine à justifier
publiquement, pas une garantie pour tous les placements imaginables.

Le modèle67 passe les mêmes99 dispositions dans les cinq domaines idéaux
séparés (`ideal-model-67.json`). Probe Chromium/Zelos :67 blocs, trois variables,
Save As/Open/AST/source map fidèles, zéro erreur, pile2200 unités à0,55
(`ui-67.json`), défilement nécessaire. Aucun PASS natif n'est anticipé.

Reproduction des anciennes versions avec le constructeur courant :
`cornerSensors:false,sideCounter:false` désactive les deux nouveautés du67 ;
ajouter `gateCorrection:true` pour le69, sinonfalse pour le63 ; les options
`lateral:false,center:false` donnent le47, `center:false` seul donne le53.
Ces options définissent des variantes d'algorithme, jamais des entrées de monde.
