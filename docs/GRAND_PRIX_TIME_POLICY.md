# Grand Prix — témoin D : mémoire et temps observé
Ce module construit un programme témoin **ordinaire AST**, pas un bloc solution
ni une API de score. Il reprend le témoin de navigation gp-v4 à deux tours de
#591, lit elapsed_time à la première jonction et utilise le compte de H obtenu
par les observations. Il ne reçoit ni graine, position, futur H, score ou état
de l'oracle. Les limites de navigation/altitude/mouvement restent celles du témoin.

Le seuil T est une règle publique donnée avant la tentative. L'estimation
publique du coût de fin F vaut 150 s par défaut : **hypothèse stratégique**,
pas une borne de sécurité et pas une connaissance du nombre de H finaux.
Avec L observé au premier retour, le programme prédit :
- sortie : retard estimé max(0, L + F - T) ;
- un tour de plus : retard estimé max(0, 2L + F - T) ;
- bénéfice du tour : 5 × compte découvert.
Il continue seulement si le bénéfice dépasse le surcoût estimé ; à égalité
estimée, il sort. Au deuxième retour il sort toujours. L inclut les coûts du
premier départ et peut surestimer le coût du tour suivant. La prédiction est
continue : elle n'imite pas exactement la convention candidate ceil de l'oracle.
Le résultat officiel demeure indépendant, et la limite native de 600 s reste
distincte de T et de F. Aucune énergie physique n'est inférée.

`Policy.build(navigation, 180)` commence par le seuil demandé dans #587.
D'autres T publics peuvent être étudiés après calibration, sur la même
configuration pour toutes les politiques comparées. Aucun optimum universel
n'est promis : l'estimation de fin inconnue peut rendre le choix mauvais.

La fixture de navigation est un gel du fichier reference_program_v4.js du
candidat **e8e3e1ae358fdba1ce98447a1b87254c90b36ca7** de #591, conservé
comme entrée explicite du test. Le composant ne dépend pas de la fusion de #591
pour ses imports ou sa CI. En production expérimentale, le vrai module de
navigation lui est passé et tout changement de son contrat de coin échoue.

La primitive générique #592 a été intégrée sous **021dc42f0dc24c54345ef4c2b9fd0cac584c4070**.
Le profil qui utilise D doit autoriser elapsedSimulationTime:true et le bloc
numérique générique ; sinon le préflight refuse avant takeoff. Le test intégré
à la suite elapsed_time préexistante vérifie le vrai interpréteur, les décisions
synthétiques (variation indépendante du compte et du temps), les valeurs
invalides et le budget **19482 ≤ 20000**. Aucune activité intermédiaire,
autorité physique, obligation CI ou mécanisme de checkpoint n'est modifié.

Ces tests **ne prouvent pas la navigation ni un avantage de score en Webots**.
La campagne native de #591 doit confronter D aux politiques fixes et à C après
composition du profil et des règles publiques. Les preuves gp-v2/gp-v3 et la
réfutation native gp-v4 restent historiques ; aucun PASS n'est transféré.
