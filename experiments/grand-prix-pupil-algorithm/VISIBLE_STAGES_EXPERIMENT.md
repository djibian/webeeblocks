# Grand Prix — étapes visibles en procédures Blockly (hypothèse pédagogique, pas adoption)

**Base expérimentale :** commit `2e563fc38e05b7f4f9025a1766a9cc58ea892ef1`, dérivé de la variante 218 de #703/#587 et de la scène #647 avec correctif RESET historique `3376e6b`. Cette branche NE MODIFIE PAS #703, #647 ou main. Toutes les preuves natives antérieures sont propres à leurs HEAD.

## Hypothèse et coût de la proposition

Au lieu d'enlever les comparaisons protectrices du candidat 206, séparer les trois tâches qu'un élève doit expliquer et déboguer :

1. **observer et décider** : lire les mesures haut/bas ; H ouvert si `bas > avant + 0,30`, H fermé seulement sur le troisième côté ET à ±0,08 m de concordance, sinon anomalie `état=2` ;
2. **franchir et confirmer le H** : avancer, corriger latéralement à partir des capteurs, traverser puis vérifier la mesure arrière **avant** `portes++` ;
3. **approcher le H fermé et poser** : distance finale, garde `1 <= portes <= 3`, choix visible centre/gauche/droite.

Ce sont des **procédures Blockly ordinaires éditables**, pas de nouvelles primitives du runtime. Chacune conserve les blocs et tests d'origine, y compris le défaut d'observation ambiguë. La transformation crée deux définitions et deux appels : **218 -> 222 blocs, 9 variables, 17 conditions, 32 comparaisons**. Aucun gain artificiel de taille n'est revendiqué. Les corps extraits restent entièrement accessibles et la logique élève demeure la même ; la vérification structurale compare les sous-arbres complets à ceux de 218. Le nombre de conditions à enseigner n'a PAS diminué : c'est une expérience de **navigation et découpage en tâches**, pas encore la forte simplification attendue.

## Critères de réfutation

- `node verify_modular_stages.js` : égalité exacte du programme principal, conditions d'observation, passages et atterrissage ; aucune suppression de garde.
- `node verify_sensor_ambiguity.js` : `avant=0.35, bas=0.50, côté=3` => anomalie, idem échantillons adversariaux.
- `node verify.js` avec Blockly 13.2.1 de production : préflight, AST/source-map, round-trip Save/Open et négatif.
- `node tools/grand_prix/pupil_workspace_u.js` puis Webots R2025a `--suite all --seed 4 --side 2.0`, même monde/oracles : 7 positifs, 8 négatifs, RESET frais, deux LAND exactement à 210000 ms. Lire les archives, distinguer erreur préflight, physique et de preuve.
- Observer dans la vraie GUI Blockly la disposition en quatre racines, le zoom utile, le nombre de gestes pour trouver les décisions, trois pauses pas-à-pas, édition d'un seuil, sauvegarde/réouverture. Mesurer temps, erreurs et aides avec des novices ; une capture plus compacte ne suffit pas.
- **Fail de l'hypothèse cognitive** si le passage entre trois procédures augmente les allers-retours et n'améliore pas la localisation des tests. Préférer alors la 218 pour sa garde intacte.

**Frontières :** aucun oracle, monde, négatif, RESET, autorité LAND, délai 210 s, activité 2–7, binaire Webots, profil ou seuil de sûreté modifié. Aucune preuve native d'un autre HEAD n'est transférable ; pas de CI Gate Ready, de GO par l'auteur, de notification TEST_REQUIRED, de fusion ni d'acceptation pédagogique personnelle.
