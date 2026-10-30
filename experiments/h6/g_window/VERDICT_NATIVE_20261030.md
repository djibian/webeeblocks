# H6 — Falsification native de la suffisance physique de G (2026-10-30)

**Statut : PREUVE NATIVE QUALIFIÉE, périmètre borné. Pas une certification du correctif de production.**

- Branche indépendante : `experiment/h6-g-sufficiency-window-20261030`.
- Commit testé : `2e72ab5ccae5189bc95a4e12917a262a48c2f84b`.
- Source exacte Webots R2025a : `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.
- Workflow natif **réussi** : https://github.com/djibian/webeeblocks/actions/runs/41074430050
- Artefact natif intégral (53 entrées, 52 empreintes internes vérifiées) :
  https://github.com/djibian/webeeblocks/actions/runs/41074430050/artifacts/12985979800
- Archive ZIP SHA-256 :
  `46db6bb01f8b045e603ae6390bf08997bcc419ba701608d2bfc785e26a3b1a27`.
- Oracle machine : `factorial_verdict.json` dans cet artefact ; `errors=[]` et job conclut SUCCESS.

## Question scientifique et verdict

La proposition **« G seul assure l'absence de réintégration des contacts ODE obsolètes après tout RESET Webots accessible » est REFUTÉE**.

Il existe un chemin réel accessible par `Supervisor.simulationResetPhysics()` et par `wb_supervisor_simulation_reset_physics()` pour lequel **G laisse passer quatre contacts obsolètes du tampon courant dans le solveur**, alors qu'un détachement R avant le solveur élimine la rotation physique parasite.

**R nécessaire : PROVEN dans le sens restreint des quatre candidats A/G/R/R+G et pour ce chemin physique**, où G seul ne suffit pas et où le détachement ciblé R est efficace. Ne pas interpréter ce verdict comme la nécessité logique unique de toute implémentation possible, ni comme la qualification d'intégration mémoire/concurrence d'un patch R de production.

## Conditions comparées

Monde synthétique `experiments/h6/g_window/worlds/h6_g_window.wbt` ;
un seul corps dynamique `TARGET`, un sol statique, un vrai contrôleur
Supervisor Python, physique Webots/ODE native, `basicTimeStep=32 ms`,
`optimalThreadCount=1`, `randomSeed=1`.

Le contrôleur laisse se produire les collisions, téléporte `TARGET` loin du
sol, à `[0.31, 0.17, 0.8]`, puis appelle un vrai RESET physique global
ou celui d'un nœud. Les **quatre joints de contact préexistants** sont
observés directement par un plugin physique au point d'entrée du solveur,
avec vitesse angulaire et linéaire initiales nulles.

- **A** : source Webots épinglée sans correction comportementale, plugin observationnel.
- **G** : nettoyage de **tous** les groupes de contacts retirés, même si leur propriétaire est désactivé, réalisé dans les deux chemins `WbOdeContext::emptyEnabledBodyContactJointGroups{1,2}()`. Uniquement `H6_G_CORE=1` ; patch source généré strictement depuis le SHA original par `core_g_patch.py`.
- **R** : détachement des quatre contacts `dJointTypeContact` effectivement attachés à `TARGET` avant l'entrée au solveur (intervention dans le plugin natif, `H6_G_WINDOW_R=1`).
- **R+G** : combinaison exacte des deux commutateurs.

Les huit bras ont été exécutés avec le **même binaire Webots recompilé une fois** depuis le commit épinglé ; les états avant intervention sont identiques, contrôlés par un oracle à tolérance `1e-8`.

### Résultats (norme de vitesse angulaire, rad/s)

| Chemin Webots | A | G | R | R+G | Résultat causal |
| --- | ---: | ---: | ---: | ---: | --- |
| RESET physique global du Supervisor | 0.7430816475286371 | 0.7430816475286371 | 0 | 0 | **G échoue, R est efficace** |
| RESET physique d'un nœud du Supervisor | 0.7430816475286371 | 0 | 0 | 0 | **G suffit dans ce scénario** |

Les traces du **RESET global** au pas 37 montrent :
`enabled=1`, `contacts=4`, `vx=vy=vz=wx=wy=wz=0`
avant intégration dans les quatre bras. Après le pas, A et G ont une
vitesse angulaire de norme `0.7430816475286371 rad/s`, tandis que R et R+G
restent à `0 rad/s`.

Les traces de **RESET de nœud** montrent au pas 37
`enabled=0,contacts=4`. Au pas 38, l'ancienne version A conserve
**les quatre mêmes identifiants de joints** et le corps est réactivé :
la vitesse angulaire parasite est produite. Avec G actif, le groupe
retiré contient `4` contacts du propriétaire désactivé et est nettoyé :
`H6_CORE event=retire group=2 enabled=0 contacts=4 g=1`.
Le pas 38 débute alors avec `contacts=0` et la rotation reste nulle.

## Chaîne d'authentification

Les fichiers sont présents dans l'archive native sous les noms
`core-g-only.patch`, `patch.sha256`, `source-commit-observed.txt`,
`webots_pin.txt`, `webots-bin.sha256`, `physics-sha256.txt`,
`plugin-sha256.txt`, `experiment_sha.txt`, `factorial_verdict.json`,
les huit paires `native.log` / `webots.log`, `flags.txt`,
`exit_code.txt`, et `SHA256SUMS.txt`.

- Source G seule : `src/webots/ode/WbOdeContext.cpp`, diff 1 fichier
  (+19 lignes, -2) : patch SHA-256
  `2363fe37f0aab7938a8ca7379f65582a8d05680a25aa721a3b37e05265ea5359`.
- Binaire compilé : `native-webots/bin/webots-bin`, SHA-256
  `96e62fbc635e32c8ec441624ae0d97e9ac6ec8d30904ebe9544c458a6a6414ba`.
- ODE compilé : `native-webots/lib/webots/libode.so`, SHA-256
  `10084cda3e6f94d17a1b1ffb60e6e0a2bea01d8fd380b596507ae73124486201`.
- Plugin expérimental : SHA-256
  `aa8ffe5bd43a3100f36ef0e1430cbbb8483dcdea247406d81e801056aabed2fe`.

Vérification indépendante de l'archive ZIP : CRC global PASS, 52/52
SHA-256 internes concordants, empreinte externe correspondant à celle
de GitHub Actions. Aucune modification de `main`, des oracles ou des
contrôles négatifs historiques ; aucune fusion.

### Sources statiques indépendantes

Workflow statique (PASS) :
https://github.com/djibian/webeeblocks/actions/runs/41074186547

Le vérificateur `audit_static.py` bloque sur tout commit source autre
que `c6793d8f7...` ou sur une modification des invariants. Il prouve
l'ordonnancement : messages Supervisor -> préphysique -> solveur
-> collisions -> échange des tampons -> nettoyage des anciens groupes.
L'absence d'une preuve physique native multi-thread ou d'un RESET de
monde complet ne doit pas être présentée comme une preuve d'impossibilité.

### Bornes et suites

- Couvert : **Webots R2025a compilé à partir du commit exact**, ODE mono-thread,
  1 monde synthétique, 2 chemins Supervisor, 8 bras, 44 pas par bras.
- Non couvert : multiprogrammation/ODE multithread, autres corps et collisions
  entre deux solides dynamiques, gestion mémoire longue durée,
  course en parallèle, rechargement total du monde, déploiement en production.
- **G ne peut donc pas être retenu comme correction native universelle seule**.
  Pour un RESET physique global, envisager R ou une protection équivalente
  *avant* la prochaine intégration, suivie de la qualification native de la
  sûreté mémoire et de la concurrence. G peut conserver un intérêt distinct
  pour la libération de groupes appartenant à des corps désactivés.
- Le R testé ici est une **intervention physique ciblée dans un plugin**.
  Il ne valide pas à lui seul le patch d'intégration finale `WbSolid` ni
  son comportement sur toutes les architectures.

Références historiques non modifiées :
H6 2x2 : https://github.com/djibian/webeeblocks/actions/runs/41055539892 ;
requalification : https://github.com/djibian/webeeblocks/actions/runs/41058133584 ;
contre-exemple ODE : https://github.com/djibian/webeeblocks/actions/runs/41057225219 .
