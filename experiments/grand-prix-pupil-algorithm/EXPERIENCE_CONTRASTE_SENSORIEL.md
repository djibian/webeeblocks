# Expérience de simplification : un contraste sensoriel explicite

**Statut : hypothèse ouverte, sans GO, Ready ni acceptation pédagogique.** Source : WBB 234 qualifié 16/16 sur main intégré sans murs `17671d18` ; présent candidat distinct, non substitué à #703.

## Un raisonnement à éprouver
1. À altitude haute, mémoriser `avant`. Descendre et observer `bas`.
2. Calculer `écart ← bas − avant` (m), puis distinguer : **ouvert** si `écart > 0,30` avec `H passé = 0` ; **fermé** si `−0,08 ≤ écart ≤ 0,08` ET troisième côté ; **anomalie** dans les autres cas.
3. Si ouvert, conserver intégralement contrôles latéraux, lecture `bas > 0,60`, passage complet, lecture arrière, comptage seulement après confirmation, verrou `H passé = 1`. Si fermé, compter 1–3 puis poser centre/gauche/droite. Aucun accès aux secrets du monde ou de l'oracle.

**Mesures avant Webots** : 232 blocs (234 auparavant), **11 variables** (10), 17 conditions, 34 comparaisons, 5 calculs arithmétiques (7), 4 procédures. Les deux blocs gagnés et les opérations réduites ne sont **pas** un PASS cognitif : la nouvelle variable peut même accroître la difficulté. Testons si trois plages fixes du même écart sont réellement plus simples à expliquer, construire et déboguer que des bornes mobiles dépendant de `avant`.

## Falsification
Le vrai WBB doit passer Blockly 13.2.1, préflight AST, source-map, Save/Open logique, pas-à-pas et budget ; les cas bas 0,35 (fermé) / 0,50 (ambigu) / 0,70 (ouvert) avec avant 0,35, l'écho ouvert répété avec `H passé=1`, compte après arrière et négatif sans H. Exécuter sur vrai Webots R2025a **les 16 cas inchangés** de `tools/ci/run_grand_prix_u_prototype.py --suite all --seed 4 --side 2.0`, comprenant sept positifs, huit négatifs, deux admissions RESET et LAND forcé au pas de 210000 ms. Inspecter archives, journaux et empreintes, y compris caméra. Aucune modification de sécurité, oracle, monde, terrain, runtime ou contrat.
Le test Chromium du WBB non déplacé doit vérifier cinq racines sans recouvrement, clic de seuil 0,30→0,31, Save/Open et pas à pas. Ses stubs OS/backend ne prouvent pas un vrai sélecteur ni une vraie liaison Webots.

## Comparaison humaine A/B préenregistrée
Deux groupes d'élèves de prérequis comparables, ordres **234→contraste** et **contraste→234** contrebalancés, activités 1–7 réellement apprises au préalable (condition non actuellement acceptée). Même mission, durée, aides disponibles ; consigner les aides, erreurs et l'effet d'ordre. Ne pas confondre ouvrir un WBB complet avec le construire.
Épreuves observables : construire/expliquer le classement ouvert-fermé-ambigu à partir de capteurs et du cas `avant=0,35, bas=0,50` ; retrouver le comptage après confirmation arrière et le verrou anti-répétition ; localiser et éditer au clic 0,30→0,31 puis diagnostiquer une anomalie en pas-à-pas ; sauver et rouvrir par **vraie boîte OS** ; refaire sans modèle la section centrale ; diagnostiquer un échec de destination sans toucher à l'oracle.
Mesurer **réussite sans aide**, temps jusqu'à localisation/correction, nombre et nature des erreurs, qualité de l'explication et construction indépendante. Une amélioration ergonomique seule ou une diminution de blocs ne valide rien. L'acceptation reste une décision **personnelle explicite du propriétaire** sur un artefact exact, séparée de CI et GO V5.
Aucun TEST_REQUIRED automatique avant profil checkpoint réellement préparé et éligible.
