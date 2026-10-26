# Grand Prix .wbb (218 blocs) — requalification après RESET, expérimentation seulement

Base immuable du monde et de l'autorité native : #647 `3376e6b886b6c4ebf316276bce5b79efa5b35570` (correctif d'acquittement LAND et RESET).
Programme collégien expérimental : Git blob `3bca44a6b758b93ca913f867c17458cf17d18f96`, SHA-256 `a9d0eeefa3c5d40411726bdbe67a54f0783da266146ae8f3d5e24352e70bc18c`, 218 blocs, 9 variables.
Le présent commit ne modifie que des ressources expérimentales ; les mondes, l'oracle, les limites rouges, les contrôles négatifs et les 210 secondes restent ceux du HEAD de #647.

## Hypothèse à réfuter
La variante 218 doit reproduire sur le monde corrigé les 7 succès (seeds 0/1/3/4/14/15/17), les 8 refus négatifs, les deux LAND forcés à exactement 210000 ms, puis deux exécutions du même AST séparées par RESET natif réellement acquitté.

Le workflow distinct `.github/workflows/gp218-reset-native-v5-20261026.yml` appelle le script **inchangé** `python3 tools/ci/run_grand_prix_u_prototype.py --suite all --seed 4 --side 2.0`. Chaque résultat exige des archives natives individuelles, la provenance Webots R2025a, des logs LAND/RESET et l'AST identique. Toute erreur ou omission reste une réfutation et ne peut être assimilée à PASS. L'authenticité des traces, les issues, les marges, les refus et le second vol doivent être inspectés, pas seulement le statut de la CI.

Cette qualification ne peut **pas** fournir seule un PASS pédagogique : 218 blocs, 9 variables, 17 conditions, 8 niveaux de corps et la navigation complexe mesurée dans Chrome restent à confronter à de vrais collégiens (construction, modifications, erreurs, pas à pas, Save/Open avec sélecteur OS). Aucun GO de l'auteur ni fusion ou TEST_REQUIRED n'est autorisé.
