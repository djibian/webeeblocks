# WebeeBlocks — Roadmap produit

La [vision](PRODUCT_VISION.md) fixe le cap, la [matrice A1–A8](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md) le contrat des activités. Les issues, PR, checks et preuves GitHub font foi pour l'état d'exécution. Cette roadmap exprime les résultats attendus, pas une file de tâches ni un état de Controllers.

## Référence : v0.1.0 — 28 novembre 2026

La [première release](https://github.com/djibian/webeeblocks/releases/tag/v0.1.0) distribue le Grand Prix unifié : 8 activités, 35 mondes, 8 amorces .wbb, lanceur Windows, Webots officiel R2025a externe, physique 8 ms et rendu par défaut 20 FPS.

- Source exacte `4733e346de4da05b680ffd7633df06bbdca13d32` ; [qualification de confiance 46187586250](https://github.com/djibian/webeeblocks/actions/runs/46187586250) : 54 jobs réussis, 3 hors profil, 35 préflights, 4 essais natifs Windows, 267 fichiers vérifiés. Ces preuves restent limitées à leurs oracles et à leur sujet.
- [#1114](https://github.com/djibian/webeeblocks/issues/1114#issuecomment-7223603624) : FAIL enseignant sur `b004a32af852641196dd2559dc50e31f8ef31de2`, dont 34/35 parcours nominaux réussis. Les corrections D1–D4 sont intégrées ; aucun transfert de PASS.
- [#1132](https://github.com/djibian/webeeblocks/issues/1132#issuecomment-7245759591) : NOT_NEEDED pour cette demande précise, exception propriétaire de première publication ; le nouveau test enseignant reste non effectué (UNPROVEN). Ni acceptation scolaire complète ni qualification réelle. Le ZIP et ses documents d'origine restent inchangés.

## Priorité : fiabilité et usage scolaire

| Résultat attendu | Critère de sortie |
| --- | --- |
| Boucle erreur → STOP → RESET → reprise (#587, #1053) | Distinguer erreur de programme, échec de mission et incident technique ; conserver le projet ; refus avant décollage si nécessaire ; arrêt et LAND indépendants, acquittement et tentative fraîche avant reprise. Vérifier les négatifs, pertes d'autorité, rebond, recul conditionnel et absence de reprises dangereuses. |
| Robustesse native et diagnostic (#637, #665, #1065) | Réévaluer les incidents anciens sur le Grand Prix livré ; isoler la cause lorsque possible, préserver les traces et refus. Ne terminer que les diagnostics susceptibles de changer une décision ou réparer un comportement ; abandonner les autres avec preuves conservées. Un run vert ne réfute pas seul un défaut intermittent. |
| Parcours scolaire A1–A8 (#587, #1053) | Exécution, pas à pas, mesures, modification, Save/Open même fichier, changements de parcours et projets incomplets sur des postes représentatifs ; un .wbb par activité sur toutes ses variantes, vrais oracles et négatifs ; observation de l'autonomie de construction et de correction, sans corrigé imposé. Une qualification enseignante ultérieure ne doit pas être confondue avec la publication déjà effectuée. |
| Performance (#914) | Conserver scène statique attestée et rendu Webots à pleine résolution, 20 FPS par défaut et sélecteur. Exploiter les mesures existantes ; mesurer sim/wall, FPS effectifs, latences et réactivité quand cela apporte une décision. Les anciennes cibles 0,95×, p99 25 ms, max 80 ms sont des repères non éliminatoires, pas des préconditions de fusion. Le choix 20 FPS supersède la recherche 60/30/25, sans prétendre à une mesure quantitative acquise. |

Le Grand Prix A1–A8 est la référence de livraison : les anciennes activités, les essais U, les autres paquets Windows et les PASS W1/W2/#481/#619/#632 ne valent que pour leur sujet. Ne pas recréer de prérequis de démarrage séquentiel A1/A8 → A2–A7. L'interface native Webots + Robot Window et Blockly/Zelos sont retenus. #476 est clos dans le périmètre hors ligne scolaire redéfini ; #800 est un FAIL historique du paquet privé M2, non une dépendance de la release actuelle.

## Ensuite : matériel réel indépendant

**#157 — première exécution limitée et sûre d'un même .wbb en simulation et sur le Crazyflie.** Le vocabulaire simulé et le sous-ensemble logiciel à hôte de confiance sont établis pour les besoins actuellement justifiés. Pas de nouvelle couverture spéculative. Exiger une preuve représentative du témoin simple sur sol uniforme, avec capacité/decks, fraîcheur, autorité enseignant, session/effets/watchdog, refus et récupération, firmware/configuration vérifiables, marges et énergie mesurées. Les preuves déterministes ne qualifient pas le matériel.

Les échecs #554/#566 et les observations stationnaires #572 restent scoped ; le FAIL procédural #572 ne supprime pas ses 200 mesures archivées et n'établit pas la disponibilité sous poussée. Avant une nouvelle demande motorisée, vérifier les réparations causales, la préparation et les preuves réellement indispensables ; aucune répétition identique par défaut. Voir [audit #554](PHYSICAL_FAIL_554_AUDIT.md), [archive #572](evidence/checkpoint-572/README.md), [baseline physique](../tools/physical/PHYSICAL_FLIGHT_BASELINE.md) et [diagnostic front](../tools/physical/FRONT_RANGE_DIAGNOSTIC.md). Préserver la séparation époque radio/session alimentée ; toute ambiguïté du watchdog exige la récupération de confiance hors vol puis une nouvelle observation et autorisation. Le disarm stock ne constitue pas un verrou durable.

**#72 — activité finale physique optionnelle.** Dépend d'une progression pédagogique exploitable et de la qualification #157 du domaine exact, pas de #70 sur sol uniforme. Le même programme validé en simulation s'exécute sans adaptation cachée avec autorisation enseignant ; ne pas détailler le circuit physique avant ces preuves.

**#70 — recherche Lab optionnelle.** Altitude monde indépendante des variations de surface, IMU/baromètre, profondeur Flow locale ; pas de suivi de terrain, compensation de table connue, référence plafond ou matériel de positionnement supplémentaire. Préserver les résultats et réfutations S3/X3 ; X3 historique ne bloque ni #157 ni #72 sur sol uniforme. N'engager qu'un travail qui réduit une incertitude indispensable du domaine complet calibration→récupération, d'abord par sources/modèles/replay. Pas de retuning opportuniste ni de vol déduit d'une caractérisation props-off. Voir [décision scientifique](C_PHYSICAL_FEASIBILITY_DECISION_2026-10-10.md) et [historique](HISTORIQUE.md).

## Règles de progression

Respecter [AGENTS.md](../AGENTS.md) : résultat utile borné, PR isolée, exact HEAD, CI Gate, revue indépendante et intégration conditionnelle. Les défauts non résolus sont évalués selon leur applicabilité et leur interférence, pas par un veto global ni par oubli. Le mécanisme de checkpoint existant est le seul chemin vers TEST_REQUIRED ; une demande humaine seulement si indispensable ou requise pour l'acceptation de l'artefact exact, un seul test ouvert. Aucune autorisation de vol réel ou de publication future implicite.

Les décisions, preuves et anciens détails du graphe restent accessibles via [HISTORIQUE.md](HISTORIQUE.md). Ne pas dupliquer ici l'état GitHub ou les contrats techniques.
