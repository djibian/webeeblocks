# Préqualification graphique Grand Prix A1–A7 — Linux et Windows

**Portée : préparation vérifiable, jamais PASS enseignant.** Complète, sans les
remplacer, le contrat pédagogique [#1053](https://github.com/djibian/webeeblocks/issues/1053),
la [matrice A1–A8](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md)
et la [procédure Windows](GRAND_PRIX_A1_A7_WINDOWS_ACCEPTANCE.md).
N'utiliser ni l'ancienne pile #1075, ni son ZIP, ni les anciens mondes A6.

## Admissibilité et preuve initiale

Après l'intégration A7 #1081, `main@3ab44a0a6f2082cf842817f47d5c233b97b0e8f7`
contient **23/23 identifiants admis** en Python et dans le pilote C++ :
A1/V1, A2/V1, A3/V1, A4/V1–V3, A5/V1–V5, A6/V1–V5,
A7/V1–V7. Cette admission est une condition nécessaire mais **pas une
exécution de monde Webots**, un PASS graphique ou un PASS pédagogique.
Les essais doivent être rattachés au nouveau HEAD exact de #1100 ;
aucune preuve historique n'est transférée automatiquement.

Les essais de contrat du run [44920248248](https://github.com/djibian/webeeblocks/actions/runs/44920248248)
ont réussi (Blockly 13.2.1, sept profils, Save As/Save/Open avec transport
**simulé**, six tests du lanceur, rejet de la livraison 6/23).
Cela **ne démontre ni un Robot Window graphique, ni un dialogue natif,
ni un vol, ni la qualité de l'interaction**. L'ancien workflow de Draft
non autorisé a été retiré ; exploiter les suites de la CI existante et
les commandes ci-dessous, sans créer de workflow ou de gate parallèle.

## Linux — essais graphiques reproductibles des seules variantes admises

Sur une machine Linux **avec Webots officiel R2025a, affichage graphique,
ressources Webots complètes et dépendances du dépôt**, dans un checkout
isolé du **SHA à tester** :

```bash
git rev-parse HEAD
export WEBOTS_HOME=/chemin/vers/webots
cat "$WEBOTS_HOME/resources/version.txt"  # doit afficher R2025a
python3 - <<'PY'
from tools.grand_prix.launch_progression_linux import admitted_variants
for activity in range(1, 8):
    print(f"A{activity}: {admitted_variants(activity)}")
PY
python3 -m unittest tools.grand_prix.test_launch_progression_linux
node tools/ci/test_grand_prix_progression_profile.js  # après préparation Blockly 13.2.1
```

Préparer les ressources Blockly **avec `./tools/prepare_runtime_v2.sh`**
avant le test Node (commande produit déjà existante). Le test Node ne
vérifie pas les boîtes de dialogue de l'OS.

Pour chacun des **23 couples A1–A7 admis** (A1/V1, A2/V1, A3/V1,
A4/V1–V3, A5/V1–V5, A6/V1–V5 et A7/V1–V7), exécuter en remplaçant les deux nombres :

```bash
python3 tools/grand_prix/launch_progression_linux.py --activity 4 --variant 2 --webots-home "$WEBOTS_HOME" --preflight-only
python3 tools/grand_prix/launch_progression_linux.py --activity 4 --variant 2 --webots-home "$WEBOTS_HOME"
```

Pour vérifier **les 23 préparations natives** en lot (avec Webots officiel,
sans les confondre avec les tests unitaires qui simulent la préparation),
utiliser ce script dans le checkout du SHA exact. Il échoue dès qu'une
admission attendue manque ou qu'un préflight échoue :

```bash
python3 - <<'PY'
import os
import subprocess
import sys
from tools.grand_prix.launch_progression_linux import admitted_variants

expected = {1: (1,), 2: (1,), 3: (1,), 4: (1, 2, 3),
            5: (1, 2, 3, 4, 5), 6: (1, 2, 3, 4, 5),
            7: (1, 2, 3, 4, 5, 6, 7)}
actual = {a: admitted_variants(a) for a in range(1, 8)}
if actual != expected:
    raise SystemExit(f'Inventaire inattendu, aucune qualification: {actual}')
for a, variants in expected.items():
    for v in variants:
        command = [sys.executable, 'tools/grand_prix/launch_progression_linux.py',
                   '--activity', str(a), '--variant', str(v), '--webots-home',
                   os.environ['WEBOTS_HOME'], '--preflight-only']
        subprocess.run(command, check=True)
        print(f'PREFLIGHT_R2025A A{a}/V{v} OK', flush=True)
for a, v in ((1, 2), (4, 4), (6, 6), (7, 8)):
    refusal = subprocess.run(
        [sys.executable, 'tools/grand_prix/launch_progression_linux.py',
         '--activity', str(a), '--variant', str(v), '--webots-home',
         os.environ['WEBOTS_HOME'], '--preflight-only'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if refusal.returncode == 0:
        raise SystemExit(f'REFUS ABSENT A{a}/V{v}')
    print(f'INVALID_VARIANT_REFUSED A{a}/V{v}', flush=True)
PY
```

Ce lot exige les 23 admissions sur le HEAD testé. Archiver la sortie avec
le SHA, la version Webots et la commande. `--preflight-only` prépare le
monde et compile le contrôleur avec l'installation officielle R2025a,
**sans lancer Webots ni faire avancer une seule tentative physique**.
Ce test ne prouve ni READY, ni interface graphique, ni vol.

Le préflight compile/prépare sans voler ; **seule la seconde commande ouvre
le vrai Webots**. Vérifier successivement la vue 3D native à résolution
intégrale, le Robot Window, le profil et starter vierge de l'activité,
Blockly manipulable, état PRÊT, démarrage, commandes et trace d'oracle,
STOP pendant une action, RESET sans état résiduel, LAND ordinaire, puis
LAND de récupération après une contre-épreuve physique contrôlée.
Conserver les refus natifs (limites, altitude, H, pose, contacts) ; ne
toucher ni aux délais ni aux oracles. Si un bouton est inaccessible ou
que Webots ne s'ouvre pas, noter **NON TESTÉ** ou **FAIL**, sans substituer
une simulation JavaScript ou un test en mode headless.

Effectuer **Enregistrer sous** par le dialogue du navigateur, puis
fermer complètement Webots, calculer `sha256sum fichier-eleve.wbb`,
relancer le même numéro d'activité, utiliser **Ouvrir** sur les mêmes
octets, vérifier les blocs éditables, lancer de nouveau. Pour A4, garder
un seul `.wbb` et exactement son SHA-256 pour V1, V2 et V3 ; étendre
la même exigence séparément aux cinq variantes A5, aux cinq variantes A6 et aux sept variantes A7.
Ne jamais modifier le fichier entre variantes d'une activité. Pour chaque
échec réel, corriger dans Blockly avant la sauvegarde du programme de
référence. Vérifier aussi `--menu` (choix limités aux admissions), le refus d'A7/V8 et des autres variantes invalides. Les préflights automatisés
ne remplacent pas un affichage réel.

## Windows — paquetage admissible, validation distincte

**Ne pas présenter un ZIP comme pédagogiquement qualifié.** La composition
`tools/grand_prix/package_windows_progression.py` exige les **23
admissions** et la géométrie A6 du 20 novembre 2026 **avant toute copie**.
Le protocole `GRAND_PRIX_A1_A7_WINDOWS_ACCEPTANCE.md` ne devient
exécutable qu'avec un paquet construit sur un SHA admis, identifié par
run, artefact et SHA-256, sur un PC Windows réel disposant de Webots
R2025a. Utiliser ses préflights PowerShell 23/23 puis ses dialogues
Save As/Open réels : ne pas promouvoir la fumée WWI native Windows au
rang de preuve graphique.

## Enregistrement indispensable de chaque observation

Conserver pour chaque `(A,V)` : SHA Git complet, version Webots,
OS/build/CPU/GPU/driver, navigateur et profil local/réseau, commande et
horodatage, état READY, capture 3D + Blockly, identité et SHA-256 du
`.wbb` avant/après fermeture, horloge simulée et temps mur, trace
STOP/RESET/LAND, verdict natif et motif, négatif, captures/logs, problème
de dialogue ou de fenêtre arrière-plan, fluidité perçue. Séparer
explicitement **préflight**, **test de contrat**, **vol natif observé**,
**usage GUI** et **jugement pédagogique**.

Chemin de sortie : préflight technique Linux A1–A7 → campagne native
et GUI réelle 23/23 avec négatifs et .wbb inchangés → CI Gate canonique
sur HEAD Ready, revue V5 indépendante, intégration conditionnelle puis
ZIP exact de `main` et checkpoint autorisé → décision humaine #1053.
Aucun PASS_ENSEIGNANT, GO, fusion ou TEST_REQUIRED pendant cette préparation.
