# Grand Prix — mesure non autoritaire du temps des pas (#912)

**Instrument de diagnostic uniquement**, désactivé par défaut. Le chemin officiel
`robot.step(8) → evaluator.tick()` et toutes les décisions de sécurité restent
identiques lorsqu'il est désactivé. Pour un essai de performance isolé, lancer
l'environnement Grand Prix habituel avec
`WEBEEBLOCKS_GP_STEP_WALL_PROBE=1` dans l'environnement du processus Webots.
L'évaluateur émet alors `GP_STEP_WALL_V1 {JSON}` sur sa sortie standard après
chaque fenêtre de 125 pas physiques (1 s simulée), et à l'arrêt normal pour
une fenêtre partielle. Ne pas utiliser ces messages pour READY/ALIVE, le vol,
les capteurs ou les oracles.

Chaque enregistrement contient le cours hôte, l'index de fenêtre, les horloges
simulées, la durée murale complète, la vitesse simulée/murale, et les **durées
brutes monotones en nanosecondes** de `robot.step(8)` et `evaluator.tick()`.
Les p50/p95/p99/max sont recalculables à partir de ces durées. Une régression
ou discontinuité de l'horloge simulée sépare les fenêtres; aucune durée n'est
agrégée entre deux époques. Un défaut de l'instrument désactive uniquement
l'instrument avec un message d'erreur explicite : il n'altère pas la mission.

Pour une comparaison A/B valide, conserver SHA, Webots R2025a, machine,
parcours, programme `.wbb`, mode GUI, fenêtre, réglage de rendu, capteurs et
sécurité constants; alterner l'ordre des essais, viser ≥30 s simulées en phase
stabilisée, retenir les JSON bruts et mesurer **séparément** le FPS réellement
visible, GPU/driver, CPU/RAM par processus et latence Blockly. Les fenêtres
courtes et l'instrument peuvent avoir leur propre surcoût d'écriture; la vitesse
mesurée ne remplace pas une horloge externe. Un taux rapide sans rendu ne prouve
ni une GUI fluide ni une qualification Windows. Ce travail ne mesure pas
encore le rendu Webots et ne constitue pas le A/B ou PASS de #912/#914.
