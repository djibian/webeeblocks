# Grand Prix 8 — protocole de construction et de débogage en classe (expérimental)

**Sujet exact :** `main@17671d18723c858ea873311a545d8c65b97b877e`, vrai projet .wbb de 222 blocs au blob `835dbfce603ebb509058d305802a309c84eabc75`, candidat `5db5128896bfcb1986b1ca830adae79418ae929f`. Aucune acceptation pédagogique enregistrée. L'activité 1 déjà acceptée n'établit pas que les acquis 2–7 ont été enseignés : ne pas supposer cette progression.

## Ce qu'un élève doit concevoir, plutôt que seulement ouvrir

1. **Décomposer le problème à l'oral et sur papier :** trois côtés en U, deux virages, 1–3 H ouverts inconnus, H final fermé, puis une des trois poses. Énoncer pourquoi une absence de H sur un côté n'est pas une erreur et pourquoi une commande de MOVE acquittée n'est pas une mesure de position.
2. **Construire la décision capteur :** dessiner la table des trois sorties « H ouvert », « H fermé probable seulement sur côté 3 », « observation incohérente ». Identifier les lectures `avant` et `bas` puis reconstruire le `si/sinon` dans une zone de travail **avec les blocs Blockly génériques seulement**. Faire prédire les résultats `(côté, avant, bas)=(3,0.35,0.35)→fermé`, `(3,0.35,0.70)→ouvert`, `(3,0.35,0.50)→anomalie`, `(3,0.35,0.20)→anomalie`, `(1,0.35,0.35)→anomalie`. La preuve exécutable `verify_sensor_ambiguity.js` utilise les expressions du **vrai WBB** ; ne jamais supprimer la concordance ±0.08 m pour gagner des blocs.
3. **Construire le franchissement :** mesurer les échos gauche/droite localement au H, refuser la géométrie invraisemblable, corriger latéralement si nécessaire ; mouvement découpé conforme au préflight ; vérifier l'écho arrière 0.30–0.65 m **avant** `portes += 1`. Demander à un autre élève de montrer précisément quel bloc interdit le double comptage et ce qui se passerait si un capteur arrière mentait.
4. **Construire la navigation et la destination :** répéter trois côtés, utiliser `côté`, `distance` (décimètres **commandés**, pas odométrie) et `état` (0 explorer, 1 fin, 2 anomalie), respecter les virages ; à la fermeture validée, `portes=1→centre`, `2→gauche`, `3→droite` ; 0 ou 4 => anomalie. Ces codes d'état sont une **charge pédagogique résiduelle**, pas des symboles autodocumentés.
5. **Diagnostiquer en situation réelle :** retrouver sans aide la comparaison `bas > avant +0.30`, modifier au clavier un seul seuil 0.30→0.31, Save As→vider→Open et constater la persistance ; isoler en pas-à-pas la décision incohérente et l'incrément après la mesure arrière, réaliser RESET puis une seconde mission. Distinguer le LAND normal écrit par l'élève du LAND **forcé exactement 210 s** par le superviseur ; ne jamais demander à l'élève de contourner ou simuler cette autorité.

## Travail de groupe / mesure de l'autonomie

Pour chaque module et chaque participant, conserver une feuille de constat contenant : concepts expliqués sans lire le code ; blocs reconstruits sans copie ; localisation de la cause d'une mesure incohérente ; seuil modifié et remis ; résultat de Save/Open via **vraie boîte OS** ; repères de pas-à-pas ; réalisation des trois destinations ; questions/hints nécessaires ; erreurs de branchement ; capacité à transférer la méthode sur un cas nouveau. Conserver le premier essai incorrect et la correction, sans masquer l'erreur par le test automatique.

**Discriminant central :** réussir à **expliquer, reconstruire et réparer** la logique après avoir masqué la solution de référence, pas retrouver les bons blocs d'un programme déjà terminé avec un script. Une capture ou une réduction de hauteur ne suffit pas. Les décisions explicites restent 17 conditions / 32 comparaisons / 9 variables avec des tests de passage et de cohérence ; le gain documenté est principalement l'organisation en trois procédures, **pas la réduction du raisonnement intrinsèque**. Un élève en difficulté sur le débogage garde la réfutation pédagogique ouverte, même avec 16/16 natifs.

## Ce que prouvent les essais machine et ce qu'ils ne prouvent pas

Le script `probe_browser_ui.mjs` utilise la **vraie page Blockly + le vrai Chromium** ; son édition 0.30→0.31 se fait par clic+saisie réels. Il observe les IDs, 4 racines, géométrie, zoom, Save/Open et 3 pauses. Mais le transport de fichier et le RobotWindow sont **injectés** : pas de vrai picker Windows/Linux, pas de Webots relié au GUI ni de performance d'élève. L'autre workflow contrôle séparément le même WBB dans le vrai R2025a sur `main`, 7 positifs/8 négatifs/RESET/210000ms, sans mélanger ces niveaux de preuve.

## Décision

La vraie acceptation pédagogique est **réservée au propriétaire** sur un artefact exact, après exécution de tâches de ce protocole (ou une meilleure grille acceptée par lui). Aucun GO V5 de l'auteur, aucune PR Ready, aucune fusion de ce laboratoire, aucun TEST_REQUIRED ni vol physique.
