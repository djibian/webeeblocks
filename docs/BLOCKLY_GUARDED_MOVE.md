# Déplacement surveillé — premier incrément de langage

Ce bloc simplifie une approche technique. Il ne reconnaît ni H, ni coin, ni côté,
ni arrivée et n'interroge aucun oracle ou état caché. Il est exposé uniquement
par le profil expérimental Grand Prix ; les activités 1–8 historiques restent
inchangées. Aucun vol réel n'est autorisé.

## Interface et contrat

```text
avancer au maximum de [0,40] m
    en s'arrêtant si distance devant ≤ [0,35] m
ajouter la distance commandée acquittée à [position]
si le seuil est atteint :
    [blocs décidés par l'élève]
[continuation commune]
```

Première tranche : avance seulement, capteur frontal. Maximum global 0,10–2,00 m,
par multiples de 0,10 m ; maximum du profil U 0,40 m. Seuil 0,25–1,50 m.
Le compteur choisi doit être initialisé et numérique ; ce n'est pas une variable
supplémentaire imposée. Son nom est libre. La mention « commandée acquittée »
dans le bloc définit ce qu'il cumule, même si l'élève le nomme `position`.

1. Préflight intégral : syntaxe, bornes, affectations, corps conditionnel,
   capacités et pire coût d'exécution avant TAKEOFF.
2. Lire une nouvelle distance frontale, sans mouvement préalable.
3. Rejeter les retours non numériques, non finis, négatifs ou > 2,001 m.
   Le retour maximal WWI de 2 m est une **borne saturée**, suffisante pour comparer
   au seuil ≤ 1,50 m ; ce n'est pas une distance exacte. Aucun indisponible physique
   n'est converti en espace libre.
4. Si distance ≤ seuil, exécuter le corps « si le seuil est atteint », puis
   rejoindre la continuation. Ce cas est prioritaire si le maximum est également
   épuisé. Sans seuil atteint et après le dernier pas, rejoindre directement
   la continuation. Aucune variable booléenne de terminaison n'est nécessaire.
5. Sinon, demander un unique MOVE avant de 0,10 m, avec arrêt/complétion ordinaires.
   Jamais plus de 20 demandes, ni plus que le maximum commandé avant le corps
   conditionnel. Les déplacements écrits dans ce corps appartiennent à l'élève
   et sont distincts du maximum d'approche.
6. Seul l'OK attendu (`null` dans l'API WWI) sur la même époque permet d'ajouter
   exactement cette consigne au compteur, une seule fois. Puis relire le capteur,
   y compris après le dernier pas. Aucun mouvement n'est réémis après ambiguïté.
7. Une erreur de mesure/MOVE, un changement d'époque, une annulation ou un budget
   épuisé interrompt l'exécution. Ni corps conditionnel, ni continuation, ni LAND
   normal ne sont fabriqués en cas d'échec. Les codes TIME_LIMIT, USER_STOPPED,
   UNSAFE_OR_TIMEOUT et RESET_CANCELLED se propagent vers les mécanismes existants.
   L'ACK confirmé juste avant une annulation reste comptabilisé ; un ACK tardif
   après RESET ne l'est pas. Cela ne pilote aucune récupération physique nouvelle.

La surveillance est **discrète**, entre mouvements arrêtés. Le seuil peut être
franchi pendant un pas : sous un modèle idéal de paroi fixe, sans erreur ni
surcourse, la distance restante peut approcher seuil − 0,10 m. Le minimum de
0,25 m est une restriction d'ingénierie, **pas une marge de freinage qualifiée**.
Angles, champ du capteur, gabarit, erreur de portée et erreur/surcourse du MOVE
restent à qualifier nativement. Un arrêt sur seuil ne prouve pas une absence de
collision dans tous les mondes. Le bloc ne surveille pas un obstacle mobile
pendant le MOVE. Les règles, collisions et autorités existantes restent actives.

## Architecture et observabilité

Nouveau nœud générique de l'AST v1 :

```json
{"kind":"guarded_move","max_distance_m":0.4,"threshold_m":0.35,
 "progress":{"id":"p","name":"position"},"on_sensor":[]}
```

L'interpréteur partagé possède la boucle, les lectures et le comptage. Il utilise
uniquement MOVE/RANGE existants et un identifiant d'époque de mouvement WWI ;
aucun contrôleur de vol ou canal Grand Prix parallèle. La capacité `guardedMove`
est requise, ainsi que MOVE avant et RANGE frontal. Le préflight physique
rejette explicitement ce nouveau kind, même dans une branche jamais choisie.

Une expansion vers WHILE existant aurait exigé des variables temporaires,
un état de terminaison et une convention de comptage cachés dans l'AST ; elle
compliquerait la source map et risquerait d'autoriser une exécution partielle sur
un backend insuffisant. Le kind explicite permet un refus fermé des anciens
interpréteurs, un budget calculable, une annulation et une époque vérifiées
après chaque attente. Aucun nouveau format `.wbb` n'est nécessaire.

Pour N pas possibles, le pire coût est 1 + (N+1) lectures + N mouvements + N
mises à jour, plus le coût du corps conditionnel. Chaque lecture et MOVE offre
un vrai pas de debug sur le même bloc ; les blocs du corps ont leurs vrais IDs.
Les valeurs de capteur et du compteur utilisent les observateurs existants.
Aucune décision/stratégie interprétée n'est ajoutée à l'interface élève.

## Commande, acquittement et position

| Option | Résultat disponible et limites | Élève / qualification |
|---|---|---|
| A — consignes acquittées | Implémentée. Somme exacte des consignes acceptées dans cette époque, sans mesure de déplacement. Les erreurs XY peuvent s'accumuler et un virage ne les efface pas. | Une variable choisie ; utilisable pour tester une stratégie nominale. Ni terminaison sûre des côtés, ni validité sur configurations inconnues ne sont démontrées. |
| B — estimation de déplacement | WWI n'en fournit aucune. TRACE MOVE conserve la consigne. La référence XY interne du C n'est pas une mesure exposée/qualifiée pour Blockly ; la lui transmettre sans contrat changerait la capacité. | La suite utile est une estimation relative corrélée à chaque commande/complétion, avec fraîcheur, projection et incertitudes, avant de qualifier la somme. Compatibilité réelle à établir séparément. |
| C — capteurs et géométrie publique | Une distance peut guider une approche de paroi visible. Un capteur saturé ou une paroi hors champ ne donne pas une abscisse. Sans H et avec de futures limites au sol, un coin n'est pas nécessairement identifiable par RANGE. | Des observations multiples et hypothèses de géométrie peuvent aider, avec plus de décisions/état. Aucune démonstration générique des trois fins de côté. Aucun accès au plan caché. |
| D — compter des pas / nœud générique | Compter les pas multiplie la même information de commande ; cela ne corrige pas A. La branche de terminaison évite seulement une variable d'état. | Petit résultat logiciel livré ; ni marqueur de monde ajouté, ni bloc de côté, ni odométrie inventée. |

Les essais à capteur constant et ACK OK produisent 0,40 m commandés sans pouvoir
établir le moindre déplacement physique : contre-exemple conservé, pas test
positif de navigation. Le Runtime C possède déjà sa propre terminaison bornée de
MOVE ; son rejet se propage, mais un ACK ne rend pas le JS capable de détecter
une erreur commune de pose ou un obstacle non observé. La limite du nombre de
pas garantit une terminaison **logicielle**, pas un progrès physique.

Le corps de franchissement ne recompte pas l'approche : chaque MOVE ordinaire
écrit par l'élève y reçoit son propre incrément explicite, et uniquement celui-là.
Le test .2 m surveillés + .3 m ordinaire + incrément .3 attend .5, pas .7 ou .8.
Aucune mise à jour implicite des anciens MOVE n'est introduite. Cette convention
reste vulnérable aux erreurs de comptage de l'élève ; une future capacité relative
unifiée devra éviter ce travail sans présenter une consigne comme une mesure.

## Expériences réutilisables et preuves

- `tools/blockly/guarded_approach_demo.wbb` : **7 vrais blocs**, deux approches
  maximales de .4 m, sans stratégie de franchissement.
- `tools/blockly/guarded_single_h_demo.wbb` : **15 vrais blocs**, même approche,
  puis blocs explicites de descente, deux MOVE, leurs deux incréments et remontée
  dans la branche du seuil. Une seule variable. Ni reconnaissance ouvert/fermé,
  ni comptage de H, ni procédure, ni parcours final n'est fourni.
- Le constructeur `guarded_move_demo.js` n'accepte aucun état de scène. Les
  fixtures persistées passent le vrai compilateur et la validation projet.
- `test_runtime_v2_guarded_move.js`, relié à l'entrée CI variables existante :
  compilation, profils/bornes/capacités toutes branches, budget exact et refus
  avant TAKEOFF, échantillons invalides/saturés, égalité/seuil initial/dernier pas,
  ACK ambigu, erreurs, annulation, RESET réel WWI et ACK tardif, source map/debug,
  .wbb et comptage sans doublon ; refus physique.
- Le runner natif existant propose `--suite guarded-approach --seed 0`, puis
  `--suite guarded-single-h --seed 0`. Ces deux cas terminent la suite canonique
  complète, après les seize témoins/négatifs historiques conservés dans leur
  ordre exact (wrong-landing au 4e lancement, s17-witness au 16e). Le test
  `test_grand_prix_guarded_schedule.py` conserve les 18 obligations et cet ordre.
  Ce déplacement restaure un témoin de comparaison : il ne résout pas #665,
  ne prouve pas l'extinction des processus ni l'indépendance des ressources
  des deux derniers lancements. Leur qualification reste à établir avec les
  diagnostics de première défaillance et une revue indépendante applicable.
  Même monde U seed 0 pour les deux ajouts (un H
  ouvert sur la première ligne droite), même contrôleur et même oracle.
  Aucune modification du monde/oracle pour rendre les programmes acceptables.
  L'arrêt partiel se termine délibérément par **wrong-landing** : le résultat
  exigé est 0 puis 1 franchissement, sans autre erreur, et non un Grand Prix réussi.

Les tests locaux JS et d'oracle ont été exécutés. Webots/Docker sont absents du
poste local : la preuve native dépend de la nouvelle CI exacte, aucun PASS natif
n'est anticipé. Les autres CI vertes ne transfèrent aucune qualification au bloc.
L'acceptation ergonomique/pédagogique appartient au propriétaire.

## Gain et prochaine capacité

Une approche explicite minimale exige par pas une condition, une comparaison,
un capteur, un seuil, un MOVE et un incrément avec sa valeur : au moins **7 blocs**
hors conteneur. Quatre pas déroulés demandent donc 28 blocs ; une répétition à
compteur + nombre réduit la duplication, mais il faut encore l'état de sortie
ou le traitement de l'arrêt. Ici **1 bloc** contient les paramètres et le compteur
sélectionné, et accueille les décisions élève dans son corps. Ce gain de 27 blocs
concerne cette comparaison locale déroulée, **pas les 389 blocs du programme
historique** ; aucune réduction exacte de ce dernier n'est démontrée.

L'élève conserve reconnaissance ouvert/fermé, descente, confirmation du passage,
remontée, nombre_H, parcours/virages et choix de pose. Le prochain besoin décisif
est de qualifier une progression relative et ses erreurs sur une ligne, y compris
sans H, puis lors d'un franchissement. La sortie de recherche et les trois côtés
restent des incréments distincts. #637 continue de bloquer les intégrations.

## Première réfutation native conservée

Run 39744104124, artefact 12411100374 : ZIP 691018 octets, SHA256
`a3dfc0e6c7193c3090496dc6df7e7811d093404a17560b114086e6892298bd0e` ;
CRC et manifeste interne vérifiés. L'approche initiale est refusée **altitude**
à +3,376 s, pendant TAKEOFF 0,80 m : z=1,168029 m, origine 0,015 m,
vz=0,502242 m/s, puis pic archivé à 1,265605 m. Aucun RANGE/MOVE du bloc
n'avait encore eu lieu au refus. L'ACK TAKEOFF arrive ensuite ; la macro demande
six pas de 0,10 m et s'arrête à RANGE=0,274550 m. Le défaut de décollage a donc
précédé une approche terminée, mais le verdict irréversible interdit tout PASS.

Le démonstrateur corrigé reprend TAKEOFF 0,40 puis VERTICAL up 0,40 du témoin
natif existant. Aucun PID ni plafond/oracle n'est modifié. Pour le H isolé,
les deux MOVE élève sont de 0,40 puis 0,30 m, avec incréments correspondants,
afin de remonter dans la bande publique après le H (centre ≤ 1,31 m pour seed 0).
Il ne s'agit pas d'une preuve préalable de marge : la nouvelle expérience doit
encore confirmer descente, franchissement et remontée. Les compteurs de blocs
ci-dessus incluent cette montée explicite. Aucun correctif du bloc surveillé
ne résulte de cette réfutation du TAKEOFF expérimental.

Probe Chromium/Zelos exécuté sur le démonstrateur corrigé : Chromium
153.0.8010.0, 15 blocs restaurés après Save As/Open, AST et source map identiques,
29 pas dont lectures/MOVE surveillés et vrais blocs internes, `position = 1.2`,
zéro erreur JavaScript. Transport et dialogues de fichiers injectés, résultat
mission volontairement négatif : ce n'est pas une preuve native/OS/Windows.
Commande reproductible (Playwright, Chromium et assets préparés requis) :

```sh
CHROME_BIN=/chemin/chromium WEBEEBLOCKS_PLAYWRIGHT_MODULE=/chemin/playwright/index.mjs \
node tools/ci/probe_blockly_guarded_move_ui.mjs
```
