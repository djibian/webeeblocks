# Grand Prix — discrimination directe haut/bas (206 blocs), expérimental

Origine : 18751e6804832d1310cf51a585e9774b87a551ee (véritable WBB 218 blocs). Le monde, les autorités, RESET et oracles sont hérités strictement de #647 `3376e6b886b6c4ebf316276bce5b79efa5b35570`.

## Pourquoi tenter ce changement ?

À proximité d'un obstacle, l'élève mesure `avant = range(front)` en haut, descend, puis mesure `bas = range(front)`. La version 218 cherche ensuite si `bas` est quasiment égal à `avant` à ±0,08 m, **uniquement pour le troisième côté**. Cette tolérance supplémentaire n'est pas une nouvelle idée algorithmique : si la différence n'annonce pas un H ouvert, la seule fermeture attendue par le contrat sur le dernier côté est le H final. L'élève conserve l'observation, la comparaison haut/bas, la décision « passage ouvert / terminal / anomalie », la vérification des montants, la confirmation arrière, le comptage, les virages et le choix de la pose.

Hypothèse alternative entièrement visible : `si bas > avant + 0,30 : essayer et confirmer le H ouvert ; sinon si côté = 3 : approcher le H terminal fermé ; sinon : anomalie`. **Aucun nouveau bloc** ni oracle/graine/coordonnée injectée. La décision peut être contestée par un élève ; elle n'est pas tenue pour correcte par construction.

**Mesure structurelle préliminaire sur le graphe complet généré : 206 blocs, 9 variables**, au lieu de 218/9 ; 30 comparaisons au lieu de 32 et 50 constantes numériques au lieu de 52. Les 17 branches subsistent. Le gain vient de retirer un intervalle de tolérance et une condition imbriquée, pas de réduire artificiellement le flux principal.

## Critères de réfutation

1. Le vrai Blockly doit charger, préflighter, compiler, Save/Open et tracer le même WBB, sans changement du profil.
2. La campagne native **inchangée** doit toujours exiger 7/7 témoins 1–3 H / trois destinations, 8/8 négatifs, les deux deadlines LAND 210000 ms, deux vols séparés par RESET natif, le même AST.
3. Si une configuration classe abusivement un H ouvert comme final, se pose avant le H fermé ou produit un LAND non confirmé, **FAIL du candidat** ; on ne touche ni aux seuils de l'oracle ni aux négatifs.
4. Même si la technique passe, demander une preuve pédagogique de construction, débogage, édition, Save/Open et compréhension de cette distinction par des collégiens. 206 blocs reste considérable. Aucun Ready, GO, PASS humain, TEST_REQUIRED ou fusion sur la seule base de cette expérience.

Le précédent `LEAN_EXPERIMENT.md` conserve l'explication historique de l'étape 218 ; le fichier actif de ce commit est la présente variante 206.
