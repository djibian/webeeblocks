# Windows R2025a — qualification réelle du renouvellement Blockly

Portée : **protocole reproductible, non exécuté** sur une interface Webots Windows
dans cette PR. Les tests Node/PowerShell sur `windows-2022` prouvent seulement
la compatibilité syntaxique, les bornes de délai, le verrouillage simulé et les
dépendances empaquetées. Ils ne prouvent **pas** l'ouverture graphique de Webots.

## Prérequis

- Windows 11 x64, Webots **R2025a**, Chrome et Firefox à jour ; les essais
  par navigateur sont indépendants (ne pas mélanger leurs profils).
- Archive Windows de la **même empreinte SHA que la PR examinée**, générée par
  `tools/build_windows_classroom_release.ps1` et vérifiée par le manifeste SHA256.
  Ne pas tester une archive antérieure.
- Dossier d'extraction utilisateur accessible en écriture, hors Internet pour
  vérifier l'autonomie pédagogique (après installation du navigateur/Webots).
- Consigner navigateur, version, Windows, identifiant de build, SHA, UTC, captures
  d'écran et logs Webots. Ne jamais inclure de données personnelles d'élèves.

## Parcours GUI réel — répéter séparément Chrome puis Firefox

1. Démarrer `Launch-WebeeBlocks.cmd`. Attendre l'état visible **PRÊT**.
   Vérifier que l'URL chargée est `/robot_windows/blockly_v2_<16hex>/blockly_v2_<16hex>.html`
   (empreintes identiques), sur `localhost`.
2. Construire un programme Blockly **non enregistré sur disque**, avec un bloc
   et une variable identifiables ; noter sa structure/AST via les diagnostics
   de test, sans remplacer le programme par un fichier sauvegardé.
3. Exécuter le scénario de collision physique avec obstacle. Le monde doit
   demander une véritable reconstruction ; vérifier que le bouton affiche
   **Reconstruire** et qu'aucune exécution supplémentaire n'est autorisée.
4. Déclencher la reconstruction. Vérifier que l'onglet **existant** renouvelle
   son document, sans interaction manuelle avec Chrome/Firefox, et que le
   programme, ses blocs, variables, profil d'activité et AST sont **identiques**.
5. Exiger la confirmation de **deux RESET stricts distincts** (limite native 5 s,
   stabilité 250 ms), de leurs **deux scènes indépendantes**, du témoin natif
   consommé seulement à la fin, puis du retour à **PRÊT**.
6. **Sans nouveau clic de l'élève**, aucun vol ne doit partir. Cliquer
   explicitement `Lancer le vol`, et constater une seconde collision réelle.
7. Refaire le parcours au moins trois fois à froid, en conservant chaque échec
   et les durées, puis tester sur un ordinateur Windows moins puissant.
8. Négatifs réels : fermer l'ancien navigateur pendant une reconstruction ;
   changer temporairement de profil ; rendre le serveur HTTP inaccessible.
   Aucun de ces cas ne peut être présenté comme récupération réussie ni
   autoriser le drone. Si le programme non enregistré a disparu, le signaler
   explicitement : **le témoin natif n'est pas une sauvegarde Blockly**.
9. Test de concurrence : deux onglets du **même profil** portant le même
   checkpoint ne doivent pas obtenir deux validations natives. Des profils
   distincts ne partagent pas les Web Locks : conserver ce cas comme limite
   tant qu'une exclusion native inter-profils n'est pas démontrée.

## Critères de compte rendu

`PASS` : trois reconstructions avec conservation exacte du projet, fenêtre
opérationnelle, 2 RESET + 2 scènes indépendantes et nouvelle exécution
**explicite** ; aucun vol pendant la reconstruction. `FAIL` : perte du
programme, revalidation tardive d'un document abandonné, double autorisation,
reconnexion bloquée ou timeout sans verrouillage sûr. `UNPROVEN` : logs
incomplets ou Webots GUI non exécuté.

Un succès Node sur runner Windows ne peut pas être substitué à ce contrôle.
Aucune intégration `main` n'est autorisée par ce protocole à lui seul.
