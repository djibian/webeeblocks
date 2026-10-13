# Comptabilité de tours libres — frontière abstraite (#587)

`lap_progress.Progress` comptabilise une séquence ordonnée d'événements déjà
validés par un oracle géométrique : H entièrement franchis dans le bon sens,
coins, retour à la jonction. Le nombre de tours n'est jamais une entrée de
validation. Après un tour complet, le programme peut continuer ou sortir ;
la borne indépendante de 20 tours autorise encore la sortie après le dernier.
Les passages d'un tour inachevé restent provisoires. Sur la ligne finale,
les événements sont uniques, ordonnés et irréversibles. Les états invalides
sont terminaux. Aucune information ne doit remonter de ce module au programme.

Ce module ne reconnaît aucune géométrie, direction, altitude, collision, mesure,
arrivée ou atterrissage : ses tests ne certifient **aucun parcours Webots**.
L'intégration au prototype #591 doit apporter ces preuves, préserver les
contre-exemples et ne jamais appeler `advance` sur un passage partiel.

`candidate_score(passages, secondes_webots, T)` matérialise uniquement la
convention proposée dans #587 : `5 * passages - ceil(max(0, secondes_webots - T))`.
Le **seuil T est obligatoire**, entier en secondes, public, choisi avant l'essai et calibré sur
les durées réelles Webots (T=180 s est un premier scénario, pas une valeur
imposée). Les anciennes régressions à T=120 s sont conservées explicitement.
Les seuils fractionnaires sont refusés, jamais arrondis : la soustraction
binaire 540,032 − 420,032 facturerait sinon 121 s pour exactement 120 s.
Les fractions de durée restent comptées sans epsilon selon la convention
candidate. La construction refuse tout événement non-portique : seuls `h:*` et
`corner:*` sont admis sur la boucle (terminée par `junction`) ; seuls
`final:*` sont admis sur la ligne droite. Les frontières et scores négatifs
sont testés sans tolérance temporelle cachée. La décision
propriétaire actuelle la nomme encore « candidate » ; ce calcul ne constitue
ni la confirmation de cette convention ni un score officiel. Aucun résultat
ne doit être classé sans certification comportementale de l'essai exact.
La comparaison des égalités hors du seuil T reste également non décidée.

Tests : `python3 tools/ci/test_grand_prix_lap_progress.py`, aussi exécutés par
la suite canonique `runtime-v2-core`. Les exemples de rentabilité sont
hypothétiques et identifiés ainsi ; ils ne démontrent aucun avantage expérimental
de la mémoire. La durée et l'intérêt stratégique nécessitent de vrais essais.
