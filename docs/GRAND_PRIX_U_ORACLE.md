# Oracle comportemental U candidat (#587)

Le module `oracle_u.py` reçoit uniquement des poses, vitesses, contacts,
identité de tentative et signal générique de fin. Il n'inspecte ni blocs,
variables, AST ni capteurs du programme. Aucun score ou tour n'est exposé.

Il vérifie ordre des trois côtés, franchissement orienté et dégagement de
chaque H (panneaux 0,48 m et rayon 0,09 m), collisions de gabarit sur le segment
entre deux observations, basse altitude sur tout le segment observé et pose stable à la destination
centre/gauche/droite. L'échec et le résultat de tentative sont irréversibles.
À 210 000 ms ou après, le temps est prioritaire sur une nouvelle réussite.
Ce module ne commande **aucun LAND** ; cette autorité native est une autre
surface de revue et reste dans le prototype Draft #591.

Les coins sont des zones de passage, pas des points exacts imposés à l'élève.
Le test segment/Box utilise la distance euclidienne ; il ne double pas
l'expansion rectangulaire d'une marge, et accepte un arc sûr qui ne traverse
pas exactement le centre d'un coin.

Hypothèses candidates à qualifier : seuil bas 0,60 m ; bandes ±0,55 m dont
le gabarit doit rester intégralement dans la bande ; décollage limité à 14 cm
du départ et 15 s, non réutilisable après sortie ; finale limitée au troisième
côté, x=0,11–0,86 m avant fermeture et ±0,81 m latéralement ; pose dans ±14 cm
de la cible, vitesses ≤0,12 m/s et stabilité 500 ms. Les cibles sont à 0,70 m
avant fermeture et ±0,50 m dans le sens d'arrivée. Ces valeurs ne sont pas
des marges physiques démontrées. L'exception de LAND forcé relève d'un essai
déjà classé échoué et ne peut recréer une réussite.

```bash
python3 tools/ci/test_grand_prix_u_oracle.py
python3 tools/ci/test_grand_prix_simulation_time.py
```

Treize tests **synthétiques** (les huit anciens sont conservés) : succès 1/2/3 avec différentes cibles ; mauvaise
pose persistante ; limites avant/après bande d'un seul échantillon ; vol bas
hors bande et raccourci ; oscillation partielle sans double compte ; frontière
209,999/210,000/210,001 s ; collision balayée entre deux extrémités libres ;
arc de coin admissible. Les anciennes cinq régressions de temps restent actives
dans le même harness Runtime. Les fixtures sont des géométries explicites
issues du générateur candidat #599, jamais des données fournies au programme.
Le composant s'exécute sans dépendre de #591. Le générateur #599 est désormais intégré sur main.

La composition native expérimentale dans #591 a produit un succès à trois
portes/pose droite sur le premier monde de 2 m, après des réfutations de
trajectoires conservées. Ce fait ne transfère aucune qualification au présent
HEAD autonome, ni aux autres tailles/configurations. La reconnaissance de
fermeture, répétabilité, reset, bruits/saturations, LAND exact et campagne de
taille exigent leurs propres essais natifs. Aucun vol réel, backend physique
ou activité intermédiaire changé. Nouvelle CI et autre revue exigées ;
l'exécution auteure ne délivre aucun GO.

Réparation du NO_GO `6bf9e18bceb0b1af68418fd9527e6f428bd97c18` :
le segment est paramétré et sa portion strictement sous 0,60 m doit être
entièrement couverte par l'union des intervalles de zones autorisées.
Le contrôle analytique conserve les frontières fermées, sans subdivisions
ni tolérance élargissant une bande. Il couvre les entrées/sorties verticales,
les trois orientations, les deux sens, les limites flottantes voisines, les
trous entre bandes et les exceptions bornées de décollage/finale. Le cas
32 ms `(0,370 ; 0 ; 0,6001) → (0,410 ; 0 ; 0,5800)` est désormais refusé
avec `low-outside-zone`. Les segments sûrs qui montent avant la sortie ou
descendent après l'entrée restent autorisés. L'expiration de l'exception de
décollage est contrôlée aussi entre échantillons ; revenir au départ ne la
réactive pas.

La preuve porte sur le segment droit entre observations, comme le contrôle
de collision balayée existant. Elle ne certifie pas une courbe inconnue
entre deux observations ni une trajectoire Webots complète. Les tests natifs
de mouvement et la recomposition de #591 restent des preuves distinctes.
