# Qualification expérimentale de pilotage Grand Prix : chaîne causale et architecture minimale

**État :** diagnostic technique et protocole de falsification. **Aucun GO de fidélité ni PASS pédagogique/physique.**
**Référence de base :** main `d932943215b1f9db49dbe7f0b0115d6a5d599ad6`.
**Branche expérimentale :** dérivée de la PR Draft #952 HEAD `198c48669ac3bcfdd2990486eed8edf2ad0eeee9`.
**Données :** issue #951 (journaux humains #940 et #952) et code versionné. Ni nouveau vol réel ni nouveau relevé Webots R2025a dans cet audit.
**Exclusions :** #637 et #665.

## 1. Ce qui est démontré et ce qui ne l'est pas

- Sur #952 HEAD antérieur `9f68b6c2...`, TAKEOFF 0,8 m a causé un premier refus d'altitude avec `origin_z=0.015`, `actual_z=1.168029`, `vz=+0.502242`, `ceiling_z=1.165`. L'écart à la consigne `origin_z+0.8=0.815` atteint **+0.353029 m au premier refus**, tout en montant. Le plafond de sécurité est franchi de **0.003029 m**. Le maximum après refus est inconnu. Ce témoin prouve une transitoire non maîtrisée, non sa cause interne (intégrale, dérivée, moteur ou inertie).
- Avec le gouverneur continu de `#952@198c4866...`, un TAKEOFF direct 0,8 m puis 1,0 m a produit un acquittement sans premier refus `altitude`. Ce n'est ni une mesure de `z_max`, ni une preuve d'amortissement ni une preuve de fidélité au matériel. Le propriétaire signale une longue attente au sol sans chronométrage.
- Les deux LAND ordinaires à la base de ces programmes artificiels sont interrompus par `low-outside-zone` à **15008 ms** après l'admission, à l'expiration de l'exception basse du départ. Ce n'est pas la deadline indépendante de **210000 ms**, et ne réfute pas le succès technique du TAKEOFF reconnu. Respecter ces règles sans les modifier.
- Lors d'autres essais Linux, l'approche haute devant H est permise ; une collision balayée sur les vraies Box reste refusée. Le centre à `z<0.62` hors bandes/exception échoue, et la descente entre lignes jaunes exige que le **rayon complet de 0.09 m** reste entre les lignes `±0.55 m` (centre longitudinal `±0.46 m`). Aucun garde n'est à détendre.
- **Aucune trajectoire t/z/vz ou sortie moteur native à 32 ms** n'est encore conservée. Les résultats C synthétiques de #952 ne représentent ni la physique de Webots, ni le firmware.

## 2. Chaîne de commande effective dans la simulation

`Blockly -> AST -> preflight -> interprète -> requêtes Runtime v2 -> contrôleur Webots -> PID -> mixer -> rotors -> dynamique du PROTO -> GPS/IMU Webots`.

Sources sur main : `controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c`,
`controllers/crazyflie_square/pid_controller.c`,
`worlds/protos/QualificationCrazyflieR2025a.proto`,
`tools/grand_prix/prepare_u_runtime.py`.

- Le Runtime générique réalise `TAKEOFF` par un saut immédiat de `target_z` ; `VERTICAL` aussi. `MOVE` position-cible + vitesse locale ; `TURN` lacet relatif + régulateur de taux ; `LAND` pente de référence en deux portions. Ce sont des sémantiques dynamiques différentes de celles du firmware.
- PID vertical Webots : `u_z = 48 + 10 clamp(e_z,-1,1) + 5 (e_z-e_z_prec)/dt + 5 integral(e_z dt)`, sans borne explicite de l'intégrale et avec dérivée sur **erreur de position**. Les mélangeurs de roulis/tangage/lacet s'additionnent, puis chaque vitesse rotor est saturée dans `[0,600]`.
- Modèle Webots épinglé : `m = 0.05 kg`, quatre coefficients propulsifs de valeur absolue `4e-5`. En approximation statique idéale, les quatre rotors demandent `omega_hover=sqrt(0.05*9.81/(4*4e-5))=55.37`, mais le terme fixe du PID vaut 48. Avec une erreur plafonnée à `0.14 m` par le gouverneur de #952, la seule action P vaut `+1.4`. Une intégrale de `+5.97` de commande pourrait demander environ `8.5 s` à `0.7` unité/s **en approximation au sol**. Ceci est une hypothèse réfutable, pas un délai mesuré ni une valeur matérielle.
- Le gouverneur expérimental #952 borne la référence (vitesse 0.32 m/s, accélération et décélération 0.55 m/s², avance sur altitude observée max 0.14 m), freine en anticipant `vz` et n'ajoute aucune nouvelle poussée. Il peut donc atténuer le dépassement mais aussi exposer un défaut de sustentation initiale. **Le seul gouverneur n'est pas établi comme la solution.**

## 3. Commandes et estimation du matériel réel

Firmware officiel `bitcraze/crazyflie-firmware@54f31e243a0b28b67efef5ba20dbb6d9890a5478`, version 2026.08. Sources `src/modules/src/crtp_commander_high_level.c`, `src/modules/src/planner.c`, `src/modules/src/pptraj.c`, `src/deck/drivers/src/flowdeck_v1v2.c`, `src/modules/src/stabilizer.c`. Adaptateurs WebeeBlocks : `tools/physical/takeoff_command.py`, `landing_command.py`, `high_level_semantics.py`, `high_level_timing.py`, `setpoint_hl_transport.py`.

| Primitive | Réalisation actuelle dans Webots | Commande réelle autorisée dans WebeeBlocks |
| --- | --- | --- |
| TAKEOFF(h) | Gouverneur local de z (#952), PID vertical et moteur Webots | Commande 9 `TAKEOFF_WITH_VELOCITY` : altitude ABSOLUE issue de l'AST, conservation du lacet courant, vitesse moyenne de 0.5 m/s ; firmware appelle `plan_takeoff` |
| MOVE(d) | `target_{x,y}` basé sur le lacet observé, régulation XY locale | Commande 12 `GO_TO_2` relative dans le monde, yaw frais vérifié, profil rest-to-rest ; durée bornée par la vitesse du programme |
| VERTICAL(d) | Saut de référence `target_z`, PID local | Commande 12 `GO_TO_2`, `dz` relatif, durée dédiée |
| TURN(a) | Consigne de lacet relatif et taux borné local | Commande 12 `GO_TO_2`, `dyaw` relatif, durée dédiée |
| LAND | Profil Webots 0.40 puis 0.15 m/s et observation sol | Commande 10 `LAND_WITH_VELOCITY`, distance descendante relative, lacet courant, vitesse moyenne de 0.5 m/s et clôture par superviseur |

Les commandes 9 et 10 construisent leurs durées en fonction de la distance et de la vitesse demandée et réutilisent `plan_takeoff` / `plan_land`. `GO_TO_2` normal utilise un profil polynomial lisse septième ordre (repos aux extrémités), dont le pic de vitesse vaut `35/16` fois la vitesse moyenne pour la loi normalisée. La voie de communication distingue **acquittement de réception**, preuve de trajectoire en cours, et observation de fin de mouvement ; elle n'est pas équivalente aux tests de tolérances du simulateur.

La référence réelle n'est **pas** le GPS Webots : Flow Deck V2 = flux optique `PMW3901` et capteur de distance inférieure `VL53L1x`, fusionnés avec IMU/baromètre dans l'EKF (configuration épinglée estimateur=2, contrôleur PID=1). Le flux est local/relatif et dépend de la texture, de la lumière, du mouvement, de l'échelle donnée par la hauteur et de la qualité de surface. Le code épinglé ne soumet les observations de flow au filtre que si `currentMotion.motion == 0xB0`. Distance ToF vers **la surface sous l'engin** et altitude du repère du monde ne sont pas synonymes ; à la transition d'une surface de hauteur différente ou quand le ToF devient invalide, z estimé peut diverger de z véritable. La position XY n'a pas d'ancrage absolu par Flow V2 seul ; dérive et incertitudes doivent être représentées, non escamotées. Le Multi-ranger est un capteur d'obstacles séparé, pas une localisation absolue.

Le commit firmware épinglé présente aussi un problème TIM7 connu (prescaler donnant un rythme nominal `84/85`) documenté dans
`experiments/crazyflie-ukf-surface-range/X3_PRELPF_TIMING_OBSERVER.md` et discuté upstream. Sa contribution effective à un écart de décollage ici **n'est pas démontrée**. Toute transposition de cadences/timestamps doit confirmer l'horloge réellement utilisée.

## 4. Instrumentation proposée sur branche expérimentale

Activée **uniquement** pour la composition Grand Prix route par `WBB_GP_TAKEOFF_TRACE=1`, désactivée par défaut. Les traces stdout sont postérieures au tick courant, n'affectent pas le PID, les commandes, la physique ni les oracles. Ne pas activer dans un profil de performance ; le coût I/O est réel si la trace est activée.

`GP_ROUTE_TAKEOFF_TRACE_BEGIN` fixe tentative / instant / origine / cible ; `...SAMPLE` à chaque tick de 32 ms enregistre `t,dt,z,z0,vz,ref,target,error,p,i,d,u,m1..m4,ground_contact,phase` ; `...ACK` marque la confirmation native de TAKEOFF. `m1..m4` sont les **vitesses effectivement demandées** à l'API rotor après saturation, pas une mesure indépendante des rotations mécaniques ou de la poussée. `u` est la commande collective non saturée reconstruite par moyenne des 4 sorties du mixer.

Le parseur `tools/grand_prix/analyze_takeoff_trace.py` donne maximum de z réellement observé, dépassement observé (borne inférieure du pic éventuel), vitesse verticale max, première élévation **proxy** de 2 cm et 0.03 m/s (ne démontre pas le décollement physique de toutes les surfaces de contact), première commande moteur atteignant l'ordre de grandeur statique du hover (autre proxy), latence ACK, fenêtre de stabilité verticale observée de 0.5 s (`|z-z_target| <= 0.05` et `|vz|<0.15`), dérivée/intégrale maximales, trous d'échantillonnage et résidu `u - (48+P+I+D)`.

**Contact / délai de soulèvement :** la trace échantillonne aussi, sans autorité, `ground_contact=1/0/-1` via les contacts superviseur Webots, en classant comme contact au sol uniquement les points dont `z <= origin_z` (cohérent avec l'observateur de contact déjà présent). Le parseur publie le premier passage **observé** `1→0` et sa date, avec une incertitude minimale d'un pas de commande (32 ms) ; il n'invente pas de perte de contact si aucun premier contact n'a été observé, si les contacts sont indisponibles ou si la trace s'arrête trop tôt. Cette détection par hauteur de point de contact n'identifie pas chaque surface par un ID physique : un test natif doit confirmer son interprétation dans la scène initiale sans obstacle. Le proxy d'élévation de 2 cm reste distinct. Les forces de contact et la poussée effective restent non mesurées. Aucune absence d'ACK n'est transformée en échec définitif : le parseur rend `TRACE_CENSORED_NO_ACK`.

La commande d'analyse est :
`python3 tools/grand_prix/analyze_takeoff_trace.py /chemin/journal.log --output /chemin/diagnostic.json`.

## 5. Options de conception et décision minimale

| Solution | Bénéfice démontrable à tester | Risque / limite | Verdict provisoire |
| --- | --- | --- | --- |
| A. Retoucher uniquement le PID Webots | Réduire retard / oscillation si compensation de sustentation, antiwindup et dérivée sur mesure corrigent les courbes | Ne reproduit pas la trajectoire lisse de commandes physiques ; gains globaux risquent d'affecter d'autres activités | **Candidat de correction locale**, pas solution complète |
| B. Trajectoires de référence bornées **et** contrôleur vertical stabilisé | Alignement sémantique des commandes 9/10/12, limites cinématiques, décélération explicite, PID minimal conservé | Le gouverneur seul #952 montre un retard ; nécessite qualification rotor / contrôle, et profils séparés VERTICAL / MOVE / TURN / LAND | **Recommandation minimale à falsifier en premier** |
| C. Réutilisation sélective `planner/pptraj` de Bitcraze | Réduit le risque d'une approximation différente du planificateur firmware, référence testable avec fixtures | Adaptation unités/cadences, API embarquée, maintenance et licence GPL ; ne résout ni sustentation Webots ni EKF / ToF | **Option conditionnelle**, seulement si B ne permet pas la fidélité requise |
| D. Porter l'intégralité du firmware et de l'EKF | Potentiellement alignement interne très fin | Très forte complexité, simulation capteurs IMU/flow/range, ordonnanceur temps réel, coûts de CI et de performances | **Non justifié** pour les objectifs scolaires actuels |

Choix proposé : **conserver le moteur physique Webots, conserver les primitives Blockly/AST et la chaîne de sécurité, séparer une politique commune de mouvements (« intention / contrainte / réussite ») de ses réalisations; tester d'abord profilage + adaptation locale de poussée (sans toucher aux règles).** Ne pas généraliser les gains ou répliquer le firmware avant A/B probantes.

## 6. Découpage durable des responsabilités (aucune implémentation complète ici)

1. **Intention Blockly & AST :** `TAKEOFF(h), MOVE(direction,d), VERTICAL(direction,d), TURN(angle), LAND` + bornes, repères, sémantique de distance et ordre de commandes, sans connaissance de mission ni de moteur.
2. **Contrat de mouvement et observabilité :** signification exacte de la cible (relative/absolue ; monde/corps), hypothèses d'estimation, critères de terminaison, vitesse admissible, timestamps et niveaux de preuve. On peut partager spécification/tests mais **pas prétendre partager le même PID physique et Webots**.
3. **Adaptateur simulation :** génération de référence compatible avec la famille de commandes physiques ; contrôle rotor propre au modèle Webots, conservant stabilité et moteur physique ; estimation simulée éventuellement dégradée par expériences ciblées, jamais en mélangeant le GPS vérité et la mesure élève.
4. **Adaptateur matériel :** construction actuelle commandes 9/10/12 et suivi de l'estimateur/état firmware, avec garanties de provenance, acquittement, fraîcheur et complétion actuellement établies. Aucun bypass, aucun nouveau droit de vol.
5. **Autorité de sécurité / mission :** oracles géométriques et temporels indépendants, fail-closed, LAND irréversible et RESET validé. **Elle peut rejeter une trajectoire pourtant conforme au contrôle**. Verdict pédagogique séparé du transport `TIME_LIMIT`.

Cette séparation est une **frontière d'interface proposée**, pas une demande de créer cinq nouveaux frameworks ou de migrer tout le dépôt.

## 7. Critères mesurables et migration Pareto

**Critères de non-régression non négociables :** plafond exact `origin_z+1.15`, vol bas `z<.62` hors bandes interdit, rayon .09 et lignes ±.55 inchangés, aucun contact réel/capsule balayée accepté, RESET strict, LAND indépendant à 210000ms et révocation immédiate, aucune mission réussie inventée, limite action native et exact-HEAD CI/indépendant GO V5. Pas de réduction des essais négatifs.

**Indicateurs d'ingénierie proposés, non contrats déjà approuvés :**
- `z(t)` / `z_ref(t)`, altitude max relative, dépassement max cible, vitesse au dépassement, énergie/temps de régime, saturation moteurs, P/I/D et intégrateur. Le plafond prime sur une moyenne, surtout vers `h=1.15 m` où un dépassement ne dispose d'aucune réserve.
- `t_lift` mesuré par contacts lorsque disponible, sinon proxy explicitement nommé ; `t_ACK`, stabilisation verticale de 0.5 s avec les tolérances native `0.05 m / 0.15 m/s`, stabilité XY/lacet pour ACK complet, pas de faux `OK` hors tolérances.
- MOVE : vitesse commandée / effective, dérive latérale, position finale et arrêt ; VERTICAL : écart et rebond z ; TURN : vitesse et dépassement yaw ; LAND : point de poser, vitesse d'impact, perte de poussée au contact et tenue au sol.
- Reproductibilité : traces A/B appariées sur même PROTO, même route/index, même source, même cadence native 32 ms, même premier état après RESET, mêmes programmes, runs nominaux et négatifs. Comparer en particulier TAKEOFF `0.2/0.5/0.8/1.0/1.15` et `0.5+UP0.3`. Les programmes `TAKEOFF; LAND` sont des diagnostics de pilotage, **pas** des tentatives valides du Grand Prix (règle de vol bas).
- Avant de parler de **fidélité au Crazyflie réel**, demander dans une qualification physique **séparément autorisée** un jeu de données de télémétrie réelle dans un domaine de vol approuvé et réellement comparable ; la seule réussite Webots ne démontre pas cette fidélité. Ni cette PR ni ces tests ne sollicitent un vol.

**Migration à faible risque :** (1) figer et publier le diagnostic instrumenté sans changer le comportement → (2) exécuter en CI/simulation native des A/B appariés et classifier l'échec (poussée initiale, intégrale, suivi du profil, erreur estimateur) → (3) si les données le justifient, petite PR Grand Prix séparée pour feed-forward modèle + anti-windup/dérivée sur mesure ou profil compatible firmware, tests négatifs inchangés → (4) réutilisation éventuelle du planificateur Bitcraze uniquement avec gain mesuré, licence et limites de maintenance évaluées → (5) extension unitaire aux autres primitives selon données, **aucune refonte globale par anticipation**.

## Conditions de décision

Cette note n'établit **aucun résultat natif nouvellement observé**. Sans courbe/capture R2025a appariée, le verdict strict sur **l'architecture de contrôle optimale** demeure **PROVISIONNEL / INSUFFICIENT_EVIDENCE**. La voie « gouverneur de trajectoire + PID de simulation corrigé + sécurité indépendante » est la meilleure **hypothèse minimale** au regard du code et des symptômes, non une garantie démontrée.
