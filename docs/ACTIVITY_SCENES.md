# Sous-scènes de simulation — prototype #587

Le monde de lancement reste `worlds/crazyflie_runtime_v2.wbt`. Le bouton
« Démarrer une activité » et l'ouverture d'un projet sélectionnent la scène avant
de remplacer le workspace. L'activité 1 charge `worlds/scenes/sequence-v1.wbo` ;
les autres profils conservent le monde hérité. Les profils, projets `.wbb`, AST
et oracles de livraison ne changent pas.

La sélection native est limitée à `sequence-v1` / `legacy-v1`, à l'état posé,
immobile, hors effet, sans fail-safe et près de l'origine réinitialisée. Elle
retire les objets et contrôleurs hors activité avant l'import. Les nœuds importés
au démarrage par les évaluateurs 7/8 sont retirés aussi ; leur restauration passe
par le redémarrage des évaluateurs, qui reconstruisent leurs propres objets.
Une importation incomplète ne permet aucun décollage. Le sol, le drone, le WWI
et l'oracle de séquence restent en place ; il n'y a aucun chargement de `.wbt`,
transfert de fichier élève, changement de sauvegarde ou donnée de navigation.

Le damier est un décor plat sans `Solid` ni `boundingObject`, en bord de zone
verte ; il ne crée pas un obstacle horizontal aux hauteurs de vol. Le sol Webots
existant demeure la seule surface physique et texturée sous le drone. Le pad
garde les dimensions utilisées par l'oracle original.

## Vérification falsificatrice

La chaîne `run_progression_sequence_mission.py` vérifie dans Webots R2025a la
sélection, l'absence de l'ancien obstacle dans la mesure avant en vol, le refus
du changement en vol, réussite/reprise/échec de livraison, puis le retour au
monde hérité et tous les cas de précision/collision d'origine. Les tests projet
exigent un ACK avant mutation et conservent le workspace si la préparation échoue.
Les tests des autres activités restent obligatoires et inchangés.

Les actions de fichiers attendent aussi le transport Robot Window et son READY,
y compris avec le sélecteur natif Chrome. Une sélection de scène en cours refuse
une seconde sélection ; seul son ACK OK exact peut confirmer l'identité, et un
ACK retardé après RESET ne la rétablit pas. Si l'application du workspace échoue
après une préparation confirmée, la restauration comprend la scène du profil
précédent. Une erreur de restauration reste attachée à l'erreur causale ; l'UI
conserve alors le veto terminal. Aucun import ambigu n'est automatiquement rejoué.

Le lancement dans un autre monde sans les groupes identifiés peut refuser la
scène épurée : seule la scène de lancement Runtime v2 est couverte. La lisibilité
visuelle, les save/open/reset représentatifs et le comportement réel du modèle
incliné restent à valider ; un test de syntaxe ou une scène transparente ne les
prouve pas. Aucun essai matériel ni vol physique n'est autorisé.

La compilation modifie les entrées générées épinglées de la qualification : la
CI doit préparer le nouveau cache exact en brouillon, observer le digest réel,
puis vérifier ce digest. Un échec de cache n'est ni un échec de mission ni une
autorisation de contourner la vérification. Le dossier physique #157 conserve
ses blocages et ses anciennes preuves ; #70 demeure suspendue.

L'import vérifie aussi les enfants directs : les 18 éléments de la scène de
livraison, puis les cardinalités et références des deux Group historiques
capturées avant leur retrait. Une racine présente avec des enfants manquants,
y compris le Group d'évaluateurs lors de la restauration, garde `ready=false`.
Le test natif injecte ces deux cas, puis vérifie la récupération vers legacy.
Ce contrôle ne constitue pas une validation de fichiers de scène arbitraires :
seuls l'asset versionné et les exports Webots capturés sont pris en charge.
