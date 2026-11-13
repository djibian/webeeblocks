# Grand Prix variable — expérimentation Windows R2025a

**Statut : expérimental / qualification humaine et GUI NON ACQUISES.**
Ce ZIP est indépendant du Grand Prix U historique. Il contient Blockly 13.2.1,
le vrai pilote natif grand_prix_route_flight, le vrai évaluateur
grand_prix_route_evaluator sous la politique de scène classroom-static-v1
de la PR #970, les douze parcours canoniques et trois fréquences
d'affichage Webots natives. Il n'autorise aucun vol réel.

## Installation et intégrité

Installer **Webots R2025a** officiel séparément et Google Chrome local.
Le ZIP embarque ses contrôleurs compilés, Blockly et un Python isolé ;
il ne contient pas le moteur Webots et n'exige ni Python, Git, Node, npm
ni Internet pour l'usage normal sur le poste Windows.

1. Contrôler le SHA256 du ZIP avec Get-FileHash, comparer au fichier
   WebeeBlocks-Grand-Prix-Variable-Windows-R2025a.zip.sha256.
2. Décompresser dans un dossier local accessible en écriture, de préférence
   sans synchronisation réseau. Ne pas mélanger avec une installation U
   historique ou la release Windows de classe.
3. Vérifier SOURCE_SHA, PR970_SHA, COMPOSITION.json, COURSES.json et
   MANIFEST.sha256 avant l'essai.
4. Fermer toute autre instance Webots, puis lancer Lancer-Grand-Prix.cmd.
   Choisir un parcours **0 à 11**, puis **60, 30 ou 25 FPS**. Valeurs par
   défaut : parcours 5, fréquence native 60 FPS.
   Alternative PowerShell : lancer Lancer-Grand-Prix.ps1 -Index 5 -Fps 30,
   ou définir WEBEEBLOCKS_GP_INDEX et WEBEEBLOCKS_GP_FPS puis utiliser
   Launch-WebeeBlocks.cmd.

**Attention :** le choix des FPS fixe seulement le plafond de rafraîchissement
3D WorldInfo.FPS en mode Webots « Real-time ». Il ne constitue pas
une mesure des FPS effectivement affichés et **ne change jamais**
basicTimeStep 8 ms, la résolution 100 %, la physique, les capteurs, le
pilote ou les oracles. Ne pas activer d'options de rendu dégradé.

## Vérification de compatibilité du lanceur

Le double-clic sur \`Lancer-Grand-Prix.cmd\` utilise le **Windows PowerShell
5.1 natif**, sans installer PowerShell 7. La CI exécute le véritable mode
\`-ValidateOnly\` dans PowerShell 5.1 : copie de session isolée, écriture de
la perspective native, réécriture HTML/HTTP local, présence du Python embarqué
et nettoyage. Ce contrôle ne lance ni Webots graphique ni Chrome, et ne
constitue donc pas une validation GUI ou de fluidité.


## Parcours élève et reprises

Attendre **PRÊT** dans Blockly, puis cliquer « Démarrer une activité » et
choisir Activites/08-grand-prix-variable.wbb. Ce fichier est un **départ
vide modifiable**, pas une solution experte ni une réussite attestée.
Construire et enregistrer un programme personnel avec « Enregistrer sous »,
le rouvrir avec « Ouvrir », et relancer **ce même fichier** sur les douze
parcours : son profil/AST ne contient ni graine, ni H, ni coordonnées cachées.
Le charger n'atteste pas qu'il résout tous les parcours.

Pour comparer les parcours, **fermer Webots et relancer** le programme depuis
le même ZIP avec un autre numéro ; un nouveau monde implique un nouvel
évaluateur et une nouvelle attestation complète. Utiliser STOP / RESET
puis un second vol dans un même monde sans modifier la géométrie.
La scène est réputée statique jusqu'au prochain changement/rechargement
d'activité : **l'édition manuelle de la scène dans Webots invalide le test** ;
elle n'est pas détectée comme une tricherie. Vérifier refus de collision,
trajectoire, altitude, franchissement, atterrissage et LAND à 210 s.
La sécurité et les préflights du Crazyflie physique restent distincts.

## Comparaison sur le portable Windows personnel

Documenter **OS Windows, CPU, GPU, RAM, pilote graphique, OpenGL réellement
utilisé**, Webots R2025a et navigateur. Le script de collecte passif déjà
existant windows_host_inventory.ps1 peut aider sur un checkout Git ;
ne jamais publier d'identifiants personnels.

Ordre : parcours **5, puis 0 et 11**, puis les douze configurations en
conservant le même programme .wbb. Pour chaque monde : **60 → 30 → 25 FPS**,
caméra, fenêtre et résolution native **100 %** identiques, mode Real-time.
Si possible **trois essais appariés alternés** par configuration, sans changer
le programme, les capteurs ni la géométrie. Relever séparément chargement et
vol stabilisé :

- durée simulée et murale (sim/wall), FPS **réellement affichés** et contexte ;
- pauses step(8), tick évaluateur, cycle p50/p95/p99/max (avec traces) ;
- Blockly PRÊT, Pas à pas, Continuer, STOP, RESET, deuxième décollage ;
- Save As, Save, Open du **même .wbb**, capteurs et changement de parcours ;
- verdicts natifs, déclenchement des oracles, LAND à 210 s et éventuels gels.

Seuils **indicatifs et non éliminatoires isolément** selon #914 :
vitesse ≥0,95×, 25–30 FPS réellement visibles, p99 ≤25 ms et
maximum ≤80 ms hors chargements explicités. Mesurer les écarts ;
ne pas annoncer de PASS si le produit reste inutilisable.

## Époque cryptographique native Windows

Dans le pilote de la **route seulement** compilé pour Windows, chaque
nouvelle tentative obtient un identifiant aléatoire de 128 bits auprès du
fournisseur cryptographique de Windows via `BCryptGenRandom` (CNG). En cas
d'échec, aucun identifiant n'est délivré, donc aucun décollage n'est autorisé.
Cette adaptation remplace uniquement le test `std::random_device::entropy()`
qui vaut 0 avec le MinGW de Webots R2025a ; elle ne modifie ni le générateur
Linux, ni le Runtime partagé, ni le protocole de validation ou les oracles.
Le simple succès d'une création d'identifiant n'atteste pas un vol réussi.

## Preuves, provenance et limites

La CI Windows propre à cette PR assemble le ZIP sur windows-2022 avec
Webots officiel épinglé, vérifie l'extraction et tente des sondes
**sans GUI** dans le vrai moteur Windows sur 5, 0, 11 :
READY, TAKEOFF, LAND, RESET, deuxième essai et refus dynamique.
Une CI échouée ou active demeure non qualifiée ; ses traces sont
nécessaires au diagnostic. Une CI native verte ne prouve ni la fluidité
3D sur le portable, ni la latence Blockly, ni Save/Open réel.

SOURCE_SHA : HEAD exact de cette PR. PR970_SHA : SHA épinglé de #970.
COMPOSITION.json : dépendances, versions et SHA du pilote.
MANIFEST.sha256 : intégrité de tous les fichiers du paquet extrait.
ZIP reproductible seulement à **octets de dépendances et outils identiques**.

**V5 :** le seul TEST_REQUIRED admis passe par le mécanisme GitHub
préexistant après preuve déterministe et déduplication. Aucun checkpoint
ni notification ne découle d'une construction Draft. Aucune fusion
ni autorisation de vol réel.
