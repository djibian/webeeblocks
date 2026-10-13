# Temps simulé observable par le programme (#587)

Le bloc générique `temps simulé depuis le départ (s)` produit l'expression
AST `{kind:'elapsed_time', unit:'s'}`. Il est numérique, mémorisable et utilisable
avec les comparaisons, opérations et boucles existantes. Le profil doit autoriser
`runtime.elapsedSimulationTime: true` et exposer `webeeblocks_v2_elapsed` dans
sa toolbox. Aucun profil intermédiaire n'est modifié par cet incrément.

Le backend Webots annonce `elapsedSimulationTime: true`. Le préflight de profil
et l'interpréteur inspectent aussi les expressions des branches non prises et
des boucles : l'absence de capacité refuse avant décollage. Le préflight physique
refuse cette expression ; aucun hôte radio, autorisation ni garde physique n'est
modifié. La continuité future exige une qualification indépendante du temps réel.

## Causalité et limites

Le contrôleur initialise l'origine à l'admission native d'un TAKEOFF valide,
avant le mouvement. Une lecture ELAPSED, possible après sa complétion et entre
les actions, renvoie `wb_robot_get_time() - origine`, en secondes. La durée du
décollage est incluse. Aucun horodatage navigateur, latence soustraite, compteur
oracle, position, graine ou score n'intervient. STOP, Reset, échec natif et
atterrissage accompli révoquent la lecture. Un nouveau décollage ouvre une
nouvelle durée ; des identifiants WWI jamais remis à zéro et l'époque locale
rejettent les réponses antérieures après Reset/STOP/nouvelle frontière de vol.
Valeurs non finies/négatives, horloge native rétrograde et réponses non numériques
échouent. L'oracle de mission conserve son origine/fin et sa propre autorité :
cette observation ne constitue jamais un certificat ni un score officiel.

Changer la vitesse Webots ou le CPU ne change pas l'unité de la primitive.
Cela ne prouve pas que le même programme mettra le même temps simulé : le
transport WWI et l'interpréteur navigateur peuvent laisser avancer la simulation
entre deux commandes. La compétition exige encore une mesure de cette influence,
sans correction opportuniste de l'oracle.

## Preuves exécutables

- `node tools/ci/test_runtime_v2_variables.js` : vrai Blockly et sérialisation,
  AST, préflight toutes branches, calcul/variables, valeurs invalides, refus
  physique et réponses tardives. Cette suite compile/exécute également le vrai
  `simulation_clock.h`, aux frontières 120 s et après révocation/reprise.
- `python3 tools/ci/run_progression_sequence_mission.py` : vrai R2025a épinglé,
  contrôleur partagé et WWI de production. Le probe exige l'indisponibilité avant
  takeoff/après LAND et une progression de 0,5–1,5 s pour WAIT 0,5 s ; il répète
  après Reset. La CI doit avoir acquis ces preuves sur le HEAD exact avant GO.

Ce document décrit une capacité générique de simulation, pas l'acceptation du
Grand Prix à tours libres ni la qualification de son barème.
