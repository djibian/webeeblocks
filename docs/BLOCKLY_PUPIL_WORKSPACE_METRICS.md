# Mesurer la structure d'un vrai programme élève Blockly

**Objet :** fournir une observation reproductible et bornée du fichier
.wbb réellement éditable par l'élève, pour la décision pédagogique
du 22 octobre 2026 sur #587 (vision produit). Le rapport **ne mesure pas**
à lui seul la difficulté ressentie, l'ergonomie, la compréhension, la
validité des consignes, la réussite Webots ou la sécurité de vol.

Sans installation supplémentaire ni Webots, depuis la racine du dépôt :

    python3 tools/blockly/measure_wbb.py chemin/vers/projet-eleve.wbb
    python3 tools/ci/test_measure_wbb.py

La première commande écrit un JSON stable, sans modifier le projet :
- nombre total de blocs sérialisés instanciés, y compris les corps de procédures,
  blocs d'expressions, blocs détachés et ombres effectivement présentes
  (l'ombre de secours derrière un bloc connecté n'est pas comptée deux fois) ;
- distribution des types, nombre de piles indépendantes, longueur en blocs de
  la chaîne principale commençant par le seul bloc « décoller » de niveau
  supérieur, et longueur maximale d'une chaîne « suivant » ;
- profondeur d'imbrication par entrées Blockly, et profondeur limitée aux
  entrées de corps d'instructions : ce sont deux métriques **structurelles**,
  non une analyse sémantique du nombre de décisions ;
- nombre de définitions et d'appels de procédures, variables déclarées,
  référencées et déclarées mais jamais référencées.

Une chaîne principale absente ou ambiguë est indiquée par null, jamais
choisie artificiellement. Aucun plafond pédagogique n'est dérivé des compteurs ;
les limites d'analyse (5 Mo, 20 000 blocs, 150 niveaux d'entrées imbriquées)
protègent seulement l'outil. Les IDs de blocs dupliqués et structures malformées
sont refusés plutôt que comptés silencieusement. La commande lit les noms de
variables localement et n'envoie rien à un service externe.

**Épreuve réelle réutilisée :** tools/physical/hover_range_comparison.wbb
du dépôt contient cinq blocs effectivement instanciés, quatre dans la chaîne
principale, une variable déclarée et référencée. C'est une preuve du compteur
sur un vrai fichier, **pas** une qualification du programme ou un vol permis.
Les tests vérifient aussi procédures imbriquées, ombres, chaînes de 200 blocs,
validations et refus des données malformées.

**Pour qualifier l'utilisabilité d'un Grand Prix :** joindre le JSON du même
.wbb effectivement sauvegardé et rouvert, un exercice observé
*modifier → exécuter → observer → déboguer → corriger → sauvegarder/ouvrir*,
les problèmes réels de navigation dans Zelos, les décisions conçues par
l'élève, le coût des réglages, et les preuves Webots R2025a multi-configurations
et contre-exemples inchangés. Ces résultats doivent rester séparés :
ni un chiffre faible, ni une CI verte ne remplacent l'acceptation pédagogique
personnelle. Aucune donnée de monde cachée ou oracle n'est lue ici.
