# Grand Prix U : géométrie et perception statique candidates

Décision applicable : tête de #587, contrat intégré par #588. `gp-u-v1`
ajoute un générateur indépendant des anciens gp-v2/v3/v4, sans modifier
leurs sources, preuves ou résultats. Aucun résultat ancien n'est transféré.

## Claim borné

Une traversée de trois côtés consécutifs, deux coins, 1–3 H ouverts
déterministes (au plus un/côté), fermeture terminale pleine largeur.
La géométrie et l'emprise restent identiques pour toutes les graines d'une
même taille. Aucun obstacle bas : murs à 1,30 m et traverses suspendues
entre 0,62 et 1,30 m seulement. Les bandes jaunes sont des `Pose` décoratives
sans collider, deux par H ; les trois cibles vertes sont toujours présentes.
À l'arrivée vers l'ouest, gauche = sud et droite = nord.

Hypothèses explicites : côté 2 m, couloir 1 m, arrivée 1,80 m × 0,95 m,
centre de pose à 0,70 m avant la fermeture, bandes à ±0,55 m du plan,
seuil bas candidat 0,60 m et rayon conservé 0,09 m. Les bandes ne sont
**pas encore qualifiées par des transitions verticales réelles**. Les
tolérances, le dégagement de la troisième porte et les trajectoires restent
à éprouver ; ce composant ne contient aucun oracle de réussite.

Le pas 32 ms ne contient pas l'instant 210,000 s : `210000 % 32 = 16`.
Le nouveau monde utilise **8 ms**, qui contient exactement cet instant,
sans modifier vitesse, lacet, contrôleur partagé ou mondes des activités 1–8.
L'effet dynamique de ce nouveau pas doit encore être testé, il n'est pas
déduit des anciens essais à 32 ms. Le générateur accepte 2–6 m en millimètres
pour la future recherche expérimentale ; aucune taille maximale n'est prouvée.

## Reproduction et portée de la preuve

```bash
python3 tools/ci/test_grand_prix_u_geometry.py
python3 tools/ci/run_grand_prix_u_geometry.py
```

La seconde commande utilise l'image R2025a épinglée par digest et les assets
source `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. Elle est appelée dans
un job Runtime indépendant de la CI canonique, sans nouveau workflow ni
contournement du CI Gate. La séparation évite qu’un échec du nouveau probe
empêche les oracles historiques Runtime/Webots de s’exécuter. Les erreurs, absence de preuve ou version différente
échouent ; logs, mesures, résumé et SHA-256 sont archivés.

Les probes 0/1/3/4/14/15/17 couvrent toutes les combinaisons de côtés et
les comptes 1/2/3. Ils imposent des poses dans Webots : ce sont des
**tests de perception statique, pas des vols, ni des témoins AST**.
Ils vérifient avec les vrais capteurs : obstacle frontal haut à ~0,18 m,
largeur latérale ~0,56 m, retour oblique bas fini plus éloigné de >0,30 m,
fermeture à ~0,68 m depuis chacune des trois cibles. Les tailles/positions
des colliders chargés sont comparées aux données versionnées. Les tests
géométriques négatifs distinguent le gabarit bas libre du gabarit haut
collidant, ainsi que les poses finales libres de la fermeture pleine largeur.

Les sept probes natifs ont été exécutés localement avec le paquet officiel
`webots_2025a_amd64.deb`, rendu Mesa logiciel et voie officielle
`webots-controller --protocol=tcp`. L'environnement interdit les sockets
AF_UNIX : Webots produit un échec explicite du listener local, mais la
connexion TCP externe et les vrais capteurs fonctionnent. Seul ce défaut
diagnostiqué est toléré par l'option explicite `--native --tcp` ; la CI Docker
standard n'a pas cette exemption. Les premiers échecs de préparation
(affichage, IPC) ne sont pas des essais de détectabilité réussis.

## Limites et intégration

Restent à prouver dans des PR séparées : oracle des franchissements orientés,
ordre des côtés, basse altitude et exceptions bornées ; pose stable correcte ;
autorité LAND/interruption à 210 s ; même AST sensoriel sur configurations
adversariales ; transitions, freinage, reset et taille maximale. Aucun score,
bonus, classement, information de monde transmise au programme ou interface
d'activité intermédiaire n'est introduit. Aucune qualification physique.

La CLI `python3 -m tools.grand_prix.layout_u --seed 4 --output monde.wbt`
produit par défaut un monde de géométrie **sans contrôleur de vol**. Il faut
composer explicitement un futur contrôleur/oracle revu avant d'en faire une
activité. Cette exécution ayant écrit le candidat n'en délivre aucun GO.

Réparation du premier candidat : le run 38417571013 a expiré dans Docker
avant de produire les preuves internes. Entrypoint explicite, diagnostic
Python préalable, timeout interne borné, log conservé avant lancement et
arrêt du conteneur par son ID exact sont ajoutés ; ce run reste négatif.
