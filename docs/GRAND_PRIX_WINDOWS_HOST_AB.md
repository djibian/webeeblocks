# Grand Prix Windows — comparaison passive A/B du moteur Webots (#914)

Ce diagnostic **ne lance pas Webots** et n'autorise aucun test humain. Il compare
uniquement les données CPU, RAM et threads du PID moteur réellement capturées
par `capture_windows_host.ps1`, après validation de la provenance des sources,
du binaire `webots-bin.exe`, du parcours, de l'équipement et des mesures brutes.
Il ne mesure ni vitesse simulée, ni FPS, ni latence des blocs, ni sûreté.
Ses résultats ne sont **jamais** un PASS du Grand Prix.

## Entrées hors ligne

Préparer les captures en suivant [le protocole de collecte](GRAND_PRIX_WINDOWS_HOST_BENCH.md),
sur **un seul portable Windows** et uniquement dans un cadre d'essai autorisé.
Pour chaque configuration / phase stabilisée, utiliser le même parcours, le
même fichier `.wbb` et des paramètres identiques ; chaque essai produit son
répertoire neuf avec `metadata.json` et `samples.csv`.

Dans le dossier parent des six répertoires, créer `manifest.json` :

~~~json
{
  "schema": 1,
  "course_id": "gp-route-v2-L2000-2500-3000-TGD-s17-H2",
  "declared_host": "portable-reference-local",
  "trials": [
    {"arm": "A", "directory": "reference-A1"},
    {"arm": "B", "directory": "candidate-B1"},
    {"arm": "B", "directory": "candidate-B2"},
    {"arm": "A", "directory": "reference-A2"},
    {"arm": "A", "directory": "reference-A3"},
    {"arm": "B", "directory": "candidate-B3"}
  ]
}
~~~

Chaque bras A utilise `-Variant reference` et chaque bras B
`-Variant candidate`. Une phase exige **au moins 30 secondes de capture
réelle par essai**, avec au moins trois paires alternées AB/BA/AB.
Les répertoires doivent être uniques, relatifs au manifeste et contenir
les sorties brutes du collecteur, sans retouche. Le champ `declared_host`
ne constitue pas une identité matérielle vérifiée.

Depuis la racine WebeeBlocks (Python 3.10+) :

~~~powershell
python .\tools\grand_prix\compare_windows_host_ab.py .\captures\manifest.json > .\host-ab-diagnostic.json
python -m unittest tools.ci.test_grand_prix_windows_host_ab
~~~

La comparaison est en lecture seule. Un manifeste mal formé, des empreintes
manquantes, un lanceur pris pour le moteur, des CSV discontinus, une identité
A ou B changeante, des mesures dupliquées ou du matériel déclaré incompatible
provoquent un refus. Les captures trop courtes renvoient
`INSUFFICIENT_CAPTURE_DURATION` (code retour 2), sans conclure.
Le résultat inclut les SHA-256 des deux fichiers bruts de chaque essai,
les médianes de CPU/RAM/threads et les écarts B–A de chaque paire.

La **mesure réelle de la vitesse simulée et du p99** exige en parallèle les
traces `GP_STEP_WALL_V1` et l'analyse `analyze_step_wall.py` ; les FPS
effectivement affichés, la latence de Blockly, le contexte OpenGL et
l'expérience GUI demeurent distincts. Une sortie de ce comparateur ne remplace
jamais la vérification native RESET/LAND/sécurité ni le `TEST_REQUIRED` officiel.
