# Grand Prix Windows — comparaison A/B des captures passives du moteur

Périmètre de #914. Ce banc **n'exécute pas Webots** et n'atteste ni la fluidité ni la sécurité. Il compare exclusivement les compteurs de ressources du **véritable moteur `webots-bin.exe`**, fournis par `tools/grand_prix/capture_windows_host.ps1`. Son rôle est de détecter des captures inutilisables et de produire un bilan CPU/RAM descriptif avant les essais natifs, GUI et utilisateur.

## Acquisition (même portable, préparation hors ligne)

1. Identifier `Get-Process -Name webots-bin` et le répertoire Webots R2025a **qui contient ce processus**. Noter séparément la version OpenGL affichée par Webots : elle n'est pas attestée par ce collecteur.
2. Capturer trois paires A/B en alternant l'ordre **référence–candidat, candidat–référence, référence–candidat**, avec les mêmes conditions observables (configuration, programme, fenêtre, navigateur, rendu, durée, cadence et phase). Utiliser une **nouvelle sortie** par essai. Ne jamais choisir un PID de `webots.exe`/`webotsw.exe`.
3. Pour chaque bras, conserver le même binaire moteur (SHA-256) pendant les trois répétitions ; les deux bras doivent avoir des binaires distincts. L'identité source WebeeBlocks peut différer entre référence et candidat, mais doit rester constante **au sein de chaque bras**. Ne pas déduire la machine réelle de son seul inventaire.
4. Collecter au moins **30 secondes par essai** (30 s murales de capture ne prouvent pas 30 s de phase simulée stabilisée). Conserver les six dossiers `metadata.json` et `samples.csv`. Le collecteur ne lit ni le temps de simulation, ni les commandes, ni les FPS réellement affichées.

Exemple indicatif de capture dans PowerShell, **en remplaçant tous les paramètres réels** (voir `docs/GRAND_PRIX_WINDOWS_HOST_BENCH.md`) :

```powershell
./tools/grand_prix/capture_windows_host.ps1 -SourceSha '<SHA_40>' `
  -CourseId '<IDENTIFIANT_ROUTE>' -Variant reference `
  -WebotsProcessId <PID_MOTEUR> -WebotsHome '<R2025a_REFERENCE>' `
  -OutputDirectory './captures/ref1' -DurationSeconds 30 -SamplePeriodMs 500
```

## Analyse hors ligne

Dans le dossier parent des six captures, créer `manifest.json` :

```json
{
  "schema": 1,
  "host_id": "portable-personnel-declare-non-atteste",
  "phase": "parcours 5, meme programme, vol stabilise declare",
  "trials": [
    {"variant": "reference", "directory": "ref1"},
    {"variant": "candidate", "directory": "cand1"},
    {"variant": "candidate", "directory": "cand2"},
    {"variant": "reference", "directory": "ref2"},
    {"variant": "reference", "directory": "ref3"},
    {"variant": "candidate", "directory": "cand3"}
  ]
}
```

Depuis la racine de WebeeBlocks :

```bash
python3 tools/grand_prix/compare_windows_host_ab.py /chemin/vers/manifest.json
python3 -m unittest tools.ci.test_grand_prix_compare_windows_host_ab
```

L'analyseur refuse les paires mal formées, les copies exactes de captures, le moteur manquant ou remplacé, les identités source/moteur instables au sein d'un bras, les différences matérielles **déclarées**, les parcours/durées/cadences non comparables et les compteurs malformés. Il émet par bras la médiane des moyennes CPU (% d'un cœur) et la médiane des maxima mémoire, avec chaque essai conservé séparément. Il ne transforme jamais un gain CPU/RAM en **PASS**, ne mesure ni vitesse simulée/murale, ni p99 des pas physiques, ni rendu réel/latence Blockly. Une machine identique, une phase réellement appariée et une source de mesure honnête restent des assertions de l'opérateur, non une provenance cryptographiquement établie. Le protocole Windows complet et les seuils d'acceptation de #914 restent à qualifier séparément.

La moyenne CPU est **pondérée par la durée des intervalles observés** et les pourcentages sont recoupés avec les compteurs CPU cumulés. L'analyseur refuse les grandes interruptions de cadence, les intervalles manquants et une origine temporelle incohérente, plutôt que de masquer une capture instable derrière 30 s nominales. Le contrôle est limité à la cohérence de ces fichiers : il ne garantit pas l'absence de falsification concertée des métadonnées, ni l'identité effective du matériel ou la stabilité de la phase de simulation.
