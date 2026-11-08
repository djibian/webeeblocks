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

## Comparer trois paires A/B sur des traces réellement recueillies

L'outil `tools/grand_prix/compare_render_ab.py` compare les fenêtres brutes
`GP_STEP_WALL_V1` de la **même phase simulée** et du **même CoursePlan**.
Il accepte seulement trois paires au minimum, en ordre AB puis BA puis AB,
sans duplication de pas, RESET dans une phase, trou de mesure, fenêtre partielle
ou couverture simulée différente. Il rapporte les vitesses **limitées aux fenêtres chronométrées** et p99 par essai,
puis les médianes des essais (poids identique de chaque répétition). Il ne change
aucun code d'évaluation, ne lance aucun simulateur et ne décide aucun verdict.

Créer un dossier de mesures contenant `compare.json` et six journaux Webots
distincts (`a1.log`, `b1.log`, `b2.log`, `a2.log`, `a3.log`, `b3.log`).
Choisir `phase_ms` de façon que **tous les journaux** contiennent des fenêtres
complètes contiguës à 8 ms dans cette même phase (au moins 1 s simulée).
Les valeurs ci-dessous sont des **champs de modèle à remplacer** par les
empreintes et l'identité réellement collectées ; ne pas les employer comme
preuves expérimentales.

```json
{
  "schema": 1,
  "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "webots_executable_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "program_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "course": "identifiant CoursePlan exact du journal",
  "host_id": "portable-reference-local",
  "display_mode": "fenetre visible, rendu OpenGL identique, viewport fixe",
  "phase_ms": [3200, 6400],
  "render_fps": {"A": 60, "B": 25},
  "trials": [
    {"arm": "A", "log": "a1.log"},
    {"arm": "B", "log": "b1.log"},
    {"arm": "B", "log": "b2.log"},
    {"arm": "A", "log": "a2.log"},
    {"arm": "A", "log": "a3.log"},
    {"arm": "B", "log": "b3.log"}
  ]
}
```

Puis exécuter `python3 tools/grand_prix/compare_render_ab.py chemin/compare.json`
et archiver le JSON produit **avec les six journaux originaux** et les relevés
hôte / FPS indépendants. `--render-fps 60` ou `--render-fps 25` du lanceur
Linux règle uniquement le budget graphique ; `basicTimeStep=8` reste inchangé.

Les identités SHA, machine, affichage et programme sont **déclarées dans ce
manifeste**, non attestées par les journaux de la sonde. Elles doivent être
contrôlées indépendamment ; les plafonds de rendu déclarés ne sont pas des FPS
visibles mesurés.

Deux vitesses distinctes sont maintenant exposées :

- `speed_in_windows_x` / `median_speed_in_windows_x` additionnent seulement les
  durées des fenêtres de 125 pas. Elles **excluent les pauses entre fenêtres**.
- `speed_observed_envelope_x` / `median_speed_observed_envelope_x` utilisent
  l'horloge monotone de la première acquisition à la fin de la dernière fenêtre
  complète sélectionnée. Elles **incluent les pauses entre fenêtres** et peuvent
  donc révéler un ralentissement invisible aux métriques précédentes.
  `observed_complete_window_phase_ms` donne précisément l'intervalle simulé
  effectivement couvert, potentiellement plus court que `phase_ms` déclaré.

Cette enveloppe ne mesure ni le temps avant sa première fenêtre ni celui après
sa dernière ; elle ne doit jamais être présentée comme le débit intégral de la
phase demandée si sa couverture est partielle. La provenance hôte, l'affichage
réel, la caméra, les FPS visibles et l'interface Blockly restent à contrôler
indépendamment. Aucun calcul de cet analyseur ne constitue à lui seul un gain
produit confirmé, un résultat `>=0,95x`, une acceptation Windows, un passage
des oracles ou une qualification pédagogique.
