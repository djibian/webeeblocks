# Grand Prix U — contrôleur natif Windows

Ce support technique de #587 compile le contrôleur composé `grand_prix_u_flight`
avec le compilateur et Qt du Webots R2025a vérifié par la CI scolaire. Il fournit
un `.exe` Windows, la fermeture `runtime.ini` déjà utilisée par le paquet scolaire,
le SHA source, les empreintes des entrées de composition et un manifeste.
La génération Python intervient seulement sur la machine de construction ; le
contrôleur de vol Windows n'utilise pas Python à l'exécution.

Construction après le paquet scolaire ordinaire :

```powershell
./tools/grand_prix/build_windows_controller.ps1 `
  -WebotsHome $env:WEBOTS_HOME -PythonExe 'C:/build-python/python.exe' `
  -ClassroomPackagePath 'ci-artifacts/windows-release/WebeeBlocks-Windows-R2025a' `
  -OutputDirectory 'ci-artifacts/gp-windows-controller'
```

La CI épingle Python de construction à 3.12.10, conserve la composition courante
du Runtime, l'autorité indépendante, le veto de scène et les oracles. Elle teste
le paquet extrait dans un chemin avec espaces, ses empreintes, ses imports PE
Controller/Qt et son entrée réelle dans libController jusqu'au refus IPC attendu
en l'absence de simulateur connecté. Les mêmes scénarios de pose, angles, RESET,
LAND à 210 s et fournisseurs bloquants sont compilés et exécutés avec la chaîne
Windows, sans supprimer d'assertion ni remplacer un refus par un PASS.

Ces preuves bornées n'établissent pas une mission graphique Windows, un résultat
pédagogique ou une qualification physique. Le paquet ne contient ni monde, ni
Robot Window, ni lanceur élève. Sa composition avec les actifs U et le support
Python de l'évaluateur (#610) reste nécessaire pour la livraison complète.
