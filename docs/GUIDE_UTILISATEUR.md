# WebeeBlocks — Guide élève et enseignant (v0.1.0)

## Installer et ouvrir

1. Installer **Webots R2025a** officiel sur Windows (avec l'aide du responsable informatique si nécessaire) et disposer de Chrome, navigateur de référence.
2. Télécharger [WebeeBlocks v0.1.0](https://github.com/djibian/webeeblocks/releases/tag/v0.1.0). L'enseignant vérifie le SHA-256 du ZIP par rapport à la release, puis extrait l'archive dans un dossier local accessible en écriture. Ne pas lancer depuis le ZIP.
3. Double-cliquer sur **Lancer-Progression.cmd**, choisir l'activité et le parcours, attendre **PRÊT** dans Blockly. Ne pas ouvrir une seconde simulation en parallèle.

Il n'est pas nécessaire d'installer Python, Node.js ou un environnement de programmation. Après préparation, aucun service Internet n'est nécessaire à l'activité. Les fichiers du réseau scolaire restent soumis à sa disponibilité.

## Programmer et tester

- **Démarrer une activité** : partir du projet initial. Lire la mission et assembler les blocs.
- Exécuter normalement ou en **Pas à pas** ; observer le drone, les capteurs (en mètres), les variables et le bloc en cours. Utiliser Continuer pour poursuivre l'exécution.
- Observer le résultat. Modifier le programme, puis **Réinitialiser** si nécessaire avant de le relancer.
- **Enregistrer sous** au premier enregistrement, puis **Enregistrer** pour mettre à jour le même fichier .wbb. **Ouvrir** pour reprendre un fichier existant, même incomplet.

Pour tester un autre parcours : enregistrer le fichier, fermer Webots, relancer la même activité avec une autre variante, ouvrir le même .wbb. Ouvrir un projet ne change pas la scène sélectionnée. Les blocs d'une activité plus avancée peuvent être conservés à l'ouverture mais refusés à l'exécution dans une activité qui ne les propose pas.

## Comprendre les parcours

| Activité | Mission | Parcours |
| --- | --- | ---: |
| A1 | Suivre un circuit et se poser | 1 |
| A2 | Passer sous un H ouvert, puis se poser | 1 |
| A3 | Répéter un trajet comportant trois H ouverts | 1 |
| A4 | Adapter le déplacement à la distance mesurée ; se poser à gauche | 3 |
| A5 | Se poser du côté opposé au virage effectué | 5 |
| A6 | Adapter le programme aux parcours avec ou sans H ouvert | 5 |
| A7 | Réussir deux segments variables avec un virage, avec ou sans H | 7 |
| A8 | Franchir les H ouverts et choisir le damier selon leur nombre : 1 centre, 2 gauche, 3 droite | 12 |

Ne pas franchir le H fermé final. Rester dans les limites rouges ; le vol bas est autorisé dans les zones jaunes autour des H ouverts et lors de la pose terminale au-dessus d'un support vert, après progression valide. Se poser sur le bon damier, au centre, sans collision. La mission doit être terminée avant 210 secondes simulées.

## En cas d'erreur

| Situation | Que faire ? |
| --- | --- |
| Programme à corriger | Lire le message, compléter ou corriger les blocs ; enregistrer même si le programme est incomplet. |
| Mission non réussie | Observer où et pourquoi le drone n'a pas satisfait la mission. Réinitialiser avant un nouvel essai. |
| Vol à interrompre | Utiliser STOP ; attendre la fin de l'arrêt avant RESET. Ne pas enchaîner les clics pour forcer la reprise. |
| Incident technique / RESET non confirmé | Ne pas relancer le vol. Enregistrer le programme si possible, relever le message, demander de l'aide à l'enseignant. Fermer la simulation avant d'en ouvrir une nouvelle. |
| Impossible d'enregistrer | Vérifier que le dossier est accessible en écriture et que le stockage scolaire est disponible. Ne pas supposer que le fichier a été enregistré après un message d'échec. |
| Affichage lent | Le réglage de départ est 20 FPS ; le sélecteur agit sur le rendu, pas sur le pas physique. Signaler à l'enseignant si le problème persiste. |

## Pour l'enseignant

Préparer un poste et faire un essai simple de lancement, arrêt, RESET et sauvegarde/réouverture avant une séance. Distribuer les activités progressivement ; demander le fichier .wbb de l'élève plutôt qu'un corrigé fourni. Pour évaluer l'autonomie, faire expliquer une stratégie, observer son exécution et corriger une erreur. Les résultats de simulation ne sont pas des notes automatiques.

La [matrice pédagogique détaillée](GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md) définit les objectifs et règles exactes. Pour un signalement, noter version, activité/parcours, Windows, navigateur, message exact, étapes, et joindre si possible un projet anonymisé et une capture (sans données d'élèves) dans une [issue](https://github.com/djibian/webeeblocks/issues).

**Limite de la version** : la qualification automatisée v0.1.0 est réussie ; le nouveau test enseignant complet n'a pas été effectué, sur décision propriétaire limitée à cette publication. Le document ACCEPTATION-WINDOWS.md embarqué est un protocole de qualification conservé tel quel, non un guide élève. Aucun vol sur drone réel n'est autorisé.
