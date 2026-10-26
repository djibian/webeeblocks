# Atelier pédagogique : construire et déboguer un Grand Prix protégé

**Version expérimentale contrôlée** : `main@17671d18723c858ea873311a545d8c65b97b877e` + WBB [`1bc106f9`](https://github.com/djibian/webeeblocks/commit/1bc106f99d58ca12d2a05239dbdaaddda9dd396b), **232 blocs / 10 variables / 3 procédures / 17 conditions / 34 comparaisons**. Le programme conservé sur `main` et #703 Draft restent inchangés. Pas d'acceptation pédagogique personnelle.

## Construire par fonctions visibles

**A. Déterminer quand croire les capteurs.** `observer et décider` possède des lectures `avant` et `bas`. Un H ouvert exige `bas > avant + 0,30 m`, puis le refus explicite si `H passé=1`. Un H final fermé n'est admissible que sur le troisième côté ET si `bas` est dans `avant ±0,08 m`. Tout autre résultat est une anomalie `état=2`. Faire prédire sans lancer : (3,0.35,0.70, Hpassé0) => ouvert ; (3,0.35,0.35, Hpassé1) => fermé ; (3,0.35,0.50, Hpassé0) => anomalie ; (3,0.35,0.70, Hpassé1) => anomalie. Ces quatre cas sont vérifiés sur les blocs réels.

**B. Traverser une seule fois un H par côté.** Dans `franchir et confirmer le H`, trouver la lecture gauche/droite et la validation de la géométrie, puis les MOVEs 0,20+0,40+0,20 et la lecture arrière avant `portes += 1 ; H passé = 1`. L'élève doit expliquer les deux mémoires distinctes : nombre total H `portes` et H compté **sur ce seul côté** `H passé`. Revenir sur un écho du même H ne doit jamais incrémenter une seconde fois.

**C. Compter l'avancement du côté.** Le programme parcourt trois côtés avec deux virages et compte des décimètres de **déplacements commandés acquittés**, non une mesure de position. Expliquer les états `0=explorer`, `1=fin du côté/arrivée`, `2=anomalie`, et la raison d'arrêter avec un état anormal. Ne pas présenter le compteur comme GPS/odométrie.

**D. Choisir la pose.** Dans `approcher le H fermé et poser`, expliquer la garde `1≤portes≤3` et le choix `1→centre`, `2→gauche`, `3→droite`. Le LAND normal est visible ; la commande de sécurité forcée à **210000 ms** appartient au superviseur indépendant et ne doit pas être contournée par l'élève.

**E. Modifier, déboguer et réouvrir.** Depuis un éditeur Blockly lancé sur Webots R2025a, modifier à la souris le seuil `0,30→0,31`, sauvegarder `.wbb`, fermer/réouvrir via le **vrai dialogue OS**, vérifier que le code reste éditable, puis revenir à 0,30. En pas-à-pas, retrouver la comparaison H ouvert, l'erreur `bas=0,50` pour `avant=0,35`, l'incrément après lecture arrière, le drapeau par côté et la décision d'atterrissage. Exécuter chaque configuration, RESET puis nouvelle admission, en regardant l'oracle et la durée Webots, pas seulement la couleur du bouton.

## Preuve contradictoire indispensable et critères humains

La [contre-épreuve réellement interprétée 40397383095](https://github.com/djibian/webeeblocks/actions/runs/40397383095) avec échos répétés donne 1 passage avant virage pour l'ancien WBB 232, 3 pour le 222 ; ce sont des capteurs **synthétiques**, pas un phénomène démontré dans le monde nominal. Le candidat protégé doit revenir à 1. Les 7 positifs, 8 négatifs, RESET et LAND exact 210 secondes sont exécutés séparément sur le vrai Webots et le monde intégré. Aucune modification des oracles n'est autorisée pour le succès.

Faire exécuter A–E à des collégiens **en cachant le programme terminé pendant la phase de construction**, puis recueillir blocages, nombre d'aides, explication sans assistance, temps pour retrouver une erreur, capacité à déboguer un cas inédit et sauvegarde OS. Un test robotisé qui retrouve un ID ou modifie un champ ne prouve **pas** ces aptitudes. La navigation par trois procédures aide à organiser le travail, mais la réduction intrinsèque du nombre de comparaisons n'est pas démontrée. La décision d'acceptation pédagogique appartient exclusivement au propriétaire.
