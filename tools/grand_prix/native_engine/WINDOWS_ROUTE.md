# Grand Prix variable R2025a — qualification expérimentale Windows

Extraire les deux ZIP du **même SHA d’assemblage** dans deux dossiers voisins
nommés `Webots-R2025a-experimental` (moteur) et
`WebeeBlocks-Grand-Prix-Windows` (projet). Utiliser un dossier local court et
accessible en écriture. Fermer les autres instances de Webots. Aucun Python,
Node ou Webots global n’est requis. Utiliser un navigateur local configuré
pour ouvrir la fenêtre Blockly de Webots. Si besoin, ouvrir « Fenêtre du robot »
depuis Webots. Attendre PRÊT avant de soumettre le programme Blockly.

Dans le dossier du projet, depuis PowerShell :

```powershell
.\Lancer-Grand-Prix.cmd --course 5 --fps 60 --arm A
.\Lancer-Grand-Prix.cmd --course 5 --fps 60 --arm B
```

A dessine à 100 %, B à 50 % de la largeur et hauteur de la cible 3D.
`--arm budget` ajoute un budget de dessin expérimental à B, à mesurer
séparément. `--fps` fixe le plafond d’affichage (25, 30 ou 60).
La physique conserve 8 ms dans chaque bras. Le lanceur vérifie le manifeste
du moteur et ses empreintes avant exécution. Les contrôleurs natifs du
parcours variable conservent l’autorité de READY, LAND et RESET.

Pour isoler l’effet de l’échelle, effectuer trois paires en ordre A/B, B/A,
A/B sur le même PC et le même pilote graphique. Garder le même fichier
`.wbb` (noter son SHA-256), parcours, plafond, taille de fenêtre et régime
secteur, avec Webots et Blockly visibles. Remettre le parcours à zéro
en fermant et relançant Webots entre les bras. Mesurer le même segment
d’au moins 30 secondes simulées consécutives en vol si le programme le
permet. Un arrêt de sécurité écourte l’essai et doit rester dans les
résultats. Pour établir la fluidité du Grand Prix complet, conserver
aussi un parcours terminé, l’issue native et les actions READY, RESET
et LAND. Relever vitesse, p99 natif, FPS observés et pauses visibles.

Garder les dossiers `traces` bruts (SHA, bras, commande, journal Webots
avec traces du moteur et du pas évaluateur, et fichier Webots
`--log-performance`). Les compteurs de swaps du moteur ne suffisent
pas à prouver un FPS visible. Ce test compare deux réglages du même
moteur. La comparaison officiel/candidat, qui exige deux moteurs
distincts, utilise le protocole
[GRAND_PRIX_WINDOWS_NATIVE_AB](https://github.com/djibian/webeeblocks/blob/main/docs/GRAND_PRIX_WINDOWS_NATIVE_AB.md).
