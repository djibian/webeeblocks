# Grand Prix U — fermeture Windows de l'évaluateur

Ce paquet technique prépare la livraison scolaire de #587. Il contient CPython
3.12.10 embarqué x64, l'évaluateur observable U et ses trois modules de géométrie,
oracle et temps **inchangés**, un point d'entrée isolé et leurs empreintes.
La licence Python est conservée dans `runtime/python/LICENSE.txt`.
Ce n'est pas encore une application élève ni un lanceur Grand Prix installé.

Construction sur Windows :

```powershell
./tools/grand_prix/build_windows_evaluator.ps1 -OutputDirectory 'ci-artifacts/gp-evaluator'
```

Le téléchargement de construction provient uniquement de Python.org ; SHA-256
et taille sont épinglés avant extraction/exécution. Une archive existante
incorrecte échoue sans nouveau téléchargement. `-PythonArchive` permet une
construction avec l'archive préalablement acquise. Aucun téléchargement,
installation Python, pip ou dépendance Internet n'est requis à l'exécution.

Pour composer ce support avec un futur paquet Grand Prix, conserver sa structure
`runtime/`, `tools/` et `controllers/`, et définir **dans l'environnement du
processus Webots** `WEBEEBLOCKS_GP_PYTHON` au chemin absolu de
`runtime/python/python.exe`. Le `runtime.ini` de l'évaluateur sélectionne
explicitement cet exécutable. `WEBOTS_HOME` désigne l'installation R2025a.
Le bootstrap ajoute uniquement la racine du paquet et l'API Python de cette
installation aux chemins isolés de CPython. `PYTHONPATH`, site-packages et le
Python par défaut du poste ne fournissent aucun module au contrôleur.

Les sources officielles R2025a fondent cette composition :
[Python](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/using-python.md),
[résolution du runtime.ini](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/control/WbController.cpp),
[sélection de l'interpréteur](https://github.com/cyberbotics/webots/blob/R2025a/src/webots/control/WbLanguageTools.cpp),
[chargement de Controller.dll](https://github.com/cyberbotics/webots/blob/R2025a/lib/controller/python/controller/wb.py).
Distribution officielle : [CPython 3.12.10](https://www.python.org/downloads/release/python-31210/).

La CI Windows extrait le ZIP depuis un chemin contenant des espaces, vérifie
chaque empreinte et l'identité des sources, puis exécute le vrai Python embarqué
avec un environnement Python parasite et un PATH limité aux bibliothèques
Webots/Windows. Elle exige les imports réels de l'API R2025a et de l'oracle, puis
l'entrée du véritable évaluateur dans libController jusqu'au refus attendu de
la connexion IPC absente. Ce refus prouve le chargement natif, **pas** le
démarrage d'une scène, une mission réussie ou une campagne graphique Windows.

Restent distincts : composition native `grand_prix_u_flight`, géométries/assets,
Robot Window et fichiers `.wbb`, lancement élève, remplacement de l'entrepôt dans
la progression active, essais de mission et acceptation personnelle. Aucun oracle,
seuil, LAND à 210 s, droit physique ou checkpoint n'est modifié par ce support.
