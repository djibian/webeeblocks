# Expérience sur le main intégrant #647 (sans murs) : véritable WBB 222

**Base** : `17671d18723c858ea873311a545d8c65b97b877e` ; programme élève 222 issu du commit figé `cf1d2bfb437735a1554e41e1af1717154e01a520` et de son fichier WBB Git blob `835dbfce603ebb509058d305802a309c84eabc75`. Le monde, les oracles et le contrat proviennent exclusivement du nouveau main.

Projet autonome ordinaire, trois procédures visibles et éditables :
- `observer et décider` : contraste haut/bas ; contradiction => `état=2`, notamment côté 3/haut 0,35/bas 0,50 ;
- `franchir et confirmer le H` : contrôle latéral, mouvement, vérification de la mesure arrière, `portes++` seulement après confirmation ;
- `approcher le H fermé et poser` : contrôle 1–3 et centre/gauche/droite.
Les trois côtés restent programmés dans la boucle principale et les distances comptées représentent des **consignes acquittées, non une odométrie**.

**Qualification native exigée mais non anticipée :** même AST sur `s0,s1,s3,s4,s14,s15,s17` ; huit négatifs exacts ; deuxième admission réussie après RESET ; LAND externe exact à 210000ms sur timeout et timeout-gate ; archives complètes et traces originales, Webots R2025a de `main`.

**Falsification cognitive :** 222 blocs, 9 variables, 17 conditions et 32 comparaisons sont un coût encore important. Une meilleure organisation des blocs (hauteur UI 1,59 viewport vs 1,98 pour 218 en ancienne branche) n'est **pas** à elle seule une forte réduction de complexité conceptuelle. Tester des tâches d'élève (construire l'observation, repérer l'ambiguïté, confirmer derrière, changer un seuil, diagnostiquer, sauvegarder/réouvrir) avec chronométrage, nombre d'aides et contre-exemples. La qualification navigateur headless antérieure ne prouve pas le vrai sélecteur OS ou Webots dans le même processus.

Pas de GO de l'auteur, de PASS pédagogique personnel, de modification du Grand Prix productif, de nouvelle primitive ou d'autorité physique. Expérience isolée ; ne pas intégrer avant V5 Ready + CI Gate exactes + revue indépendante et acceptation pédagogique personnelle.