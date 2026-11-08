# Grand Prix — rendu comparatif A/B expérimental (#912)

Cette procédure compare **uniquement la cadence de rendu 3D de Webots
R2025a**, sans changer la physique à 125 Hz (`basicTimeStep 8`), les
contrôleurs, les capteurs, les collisions, l'évaluateur, les oracles ni le
`LAND` natif indépendant à 210000 ms. Aucun résultat de performance, test
GUI, ni acceptation pédagogique n'est attesté par cette documentation ou
par les tests unitaires du lanceur.

## Référence reproductible

À partir d'un checkout au **SHA exact du candidat**, sur le même poste Linux
graphique et une installation officielle Webots R2025a complète, préparer
une seule fois les ressources et noter Webots, navigateur, CPU/GPU,
pilote OpenGL, RAM, résolution/viewport, identifiant de parcours, SHA256
du fichier `.wbb` utilisé et mode de rendu matériel/logiciel.

```sh
export WEBOTS_HOME=/usr/local/webots  # adapter
python3 tools/grand_prix/launch_linux.py --index 5 --preflight-only
python3 tools/grand_prix/launch_linux.py --index 5
# Fin de l'essai témoin : fermer Webots avant tout autre lancement.
python3 tools/grand_prix/launch_linux.py --index 5 --render-fps 60
python3 tools/grand_prix/launch_linux.py --index 5 --render-fps 30
python3 tools/grand_prix/launch_linux.py --index 5 --render-fps 25
```

`--render-fps` ne modifie qu'un champ `WorldInfo.FPS` ajouté au monde
temporaire **variable**. Sans option, le monde produit reste strictement
inchangé : il est l'armature témoin. Le contrôle refuse des valeurs autres que
25, 30 et 60, les ancres WorldInfo inattendues et l'ancien U. Un plafond de
FPS n'est **ni** une mesure des images réellement affichées **ni** une
garantie de vitesse de simulation.

## Mesure A/B à réaliser avant toute conclusion

- Fixer le **même** matériel, configuration OpenGL, taille de fenêtre et
  `.wbb` inchangé sur le même parcours (`--index 5` en premier). Conserver
  le même programme et les mêmes actions/timings sur chaque répétition ;
  aucune solution gagnante n'est requise. Mesurer un run témoin sans option et
  les plafonds 60/30/25 en alternant l'ordre, **au moins trois répétitions**
  par bras ; écarter explicitement le temps d'installation/compilation.
- Séparer les phases **PRÊT, vol, tentative close, RESET / nouvelle
  admission**. Pour chaque phase stabilisée, viser au moins 30 secondes si
  elle est disponible, en conservant durée simulée et durée murale ;
  `vitesse = secondes simulées / secondes murales`. Relever également le
  multiplicateur Webots, le nombre d'images réellement visibles/s, CPU par
  processus, GPU/driver, RAM et réactivité de Blockly.
- Si une instrumentation fiable du pas de physique est disponible, relever
  p50/p95/p99/max de la durée de `step(8)` et le délai UI ; à défaut,
  mentionner **NON MESURÉ**, ne pas inventer un p99. La variation de vitesse
  du monde, pas le FPS seul, est le critère d'optimisation.
- Tester avec une **vraie Robot Window** les interactions
  Pas à pas/Continuer, STOP/RESET, deuxième décollage et fichiers
  Enregistrer sous → Enregistrer → Ouvrir le même `.wbb`.
  Le FAIL humain historique #905 du mode Pas à pas reste distinct :
  ne pas déclarer un PASS sur la seule base de l'A/B de rendu.
- Répéter ensuite au minimum sur les parcours 0 et 11 sans affaiblir les
  négatifs. Conserver les erreurs et journaux natifs, y compris READY/ALIVE,
  CONTACT, RESET et LAND. Aucune limitation de sécurité n'est modifiée.

L'objectif produit de #912/#914 est une vitesse stabilisée **≥0,95×**,
un p99 de pas **≤25 ms**, un maximum cible **≤80 ms** hors chargement et
une vue réellement lisible ~25–30 FPS **sur le portable Windows de
référence**, qui exigera son artefact/protocole exact et son propre
checkpoint de confiance. Cette A/B Linux n'atteste pas l'objectif Windows.

**Interprétation :** un plafond FPS dont les résultats n'améliorent pas le
temps simulé/mural reste une hypothèse écartée ; conserver les mesures
négatives. L'absence de données A/B réelles vaut `UNPROVEN`, pas un gain.

## Analyse automatisée des journaux (préparation, sans PASS)

Activer `WEBEEBLOCKS_GP_STEP_WALL_PROBE=1` pour chaque essai de référence et
chaque essai `--render-fps 25` (ou 30/60), puis conserver **la sortie brute**
de l'évaluateur, incluant `GP_STEP_WALL_V1`. Le script
`tools/grand_prix/analyze_render_ab.py` compare six essais ou plus : au moins
trois paires adjacentes A/B, avec ordres AB et BA, au même SHA et sur le même
poste. Il vérifie les empreintes déclarées, le parcours, la continuité de
l'horloge physique 8 ms, les données brutes de p99, et refuse toute fenêtre
incomplète ou moins de 30 s simulées par essai et phase choisie.

Créer un `runs.json` local (les logs restent dans le même dossier) :

~~~json
{
  "schema": "webeeblocks.gp-render-ab-v1",
  "common": {
    "source_sha": "<40 caractères hexadécimaux>",
    "webots_sha256": "<64 caractères hexadécimaux>",
    "wbb_sha256": "<64 caractères hexadécimaux>",
    "host_token": "poste-local-A",
    "course_id": "<identifiant CoursePlan exact>",
    "viewport": "1280x720", "renderer": "OpenGL logiciel ou matériel vérifié",
    "browser": "version et navigateur vérifiés", "phase": "flight",
    "physical_step_ms": 8, "gui_visible": true
  },
  "candidate_fps": 25,
  "trials": [
    {"pair": 1, "arm": "reference", "render_fps": null, "log": "A1.log", "first_window": 5, "last_window": 34},
    {"pair": 1, "arm": "candidate", "render_fps": 25, "log": "B1.log", "first_window": 5, "last_window": 34}
  ]
}
~~~

L'exemple ne donne que la première paire : ajouter les paires 2 et 3, avec
l'ordre BA puis AB, avant d'exécuter :

~~~sh
python3 tools/grand_prix/analyze_render_ab.py preuves/runs.json > preuves/rapport.json
python3 -m unittest tools.ci.test_grand_prix_render_ab
~~~

Les conditions communes sont **déclarées, non attestées automatiquement** ;
`first_window` et `last_window` doivent désigner uniquement la phase stabilisée.
Le résultat donne des vitesses **internes aux fenêtres instrumentées**, des
quantiles bruts de pas et des différences appariées, avec SHA-256 de chaque log.
Les pauses entre fenêtres, le FPS effectivement affiché, la latence Blockly,
les processus GPU et le temps mural externe ne sont pas mesurés. Ce rapport
**n'est jamais un PASS de fluidité graphique, de sécurité ni de Windows**.
