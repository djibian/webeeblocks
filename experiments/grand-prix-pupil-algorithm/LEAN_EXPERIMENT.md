# Grand Prix sans murs — variante falsifiable 216 blocs (NE PAS ADOPTER)

**Provenance:** essai isolé dérivé de #647 `995b4b47f2b3e525e263450c11737f5d78dc85dd`, programme source #703 exact `0d82c03e16f1e62044e79ef55ac5e9c6c7b67c81` ; candidate native source `Grand-Prix-sans-murs-algorithme-candidat.wbb` dans CETTE branche uniquement. `#703` et `#647` originaux demeurent inchangés. Mesures faites sur l'arbre Blockly entier, entrées/next/procédures incluses.

## Hypothèse: 232 → **216** blocs, 10 → **9** variables, conditions 17 → 17, comparaisons 34 → **32**, nombres 57 → **52**. Économie nette 16/232 = 6,9 %, insuffisante à elle seule pour établir une faisabilité collégienne.

1. Suppression du drapeau « H passé » par côté. **Hypothèse risquée:** au plus un H ouvert par côté, déjà imposé par le contrat, mais l'absence de *nouvelle lecture* du même H après sortie n'est PAS démontrée; tester tout double comptage sur les traces natives, surtout avec dérive et saturations. L'incrément du nombre de H reste explicite **après** contrôle arrière.
2. La proximité frontale `avant <= 0.40` est vérifiée une fois pour les cas « ouvert probable » (`avant >= 0.30`) et « troisième côté » ; aucune lecture de graine/plan/cible/oracle.
3. Deux commandes latérales de 0,4 + 0,1 m à la pose deviennent une commande 0,5 m ; le trajet simulé et la réponse dynamique **peuvent différer**, donc ne pas inférer un résultat de l'ancienne variante. Le choix explicite centre/gauche/droite selon 1/2/3 portes reste en Blockly.
4. Après `MOVE 0.4` puis `MOVE 0.2`, une seule mise à jour cumulée `distance += 6` décimètres remplace deux mises à jour. **Ce n'est toujours pas de l'odométrie**; la variable compte les demandes acquittées, non la pose réelle. Ne pas masquer des échecs intermédiaires.

Tous les blocs restent Blockly ordinaires : TAKEOFF, RANGE, comparaisons, tests, variables, boucle bornée, procédure éditable, MOVE, TURN, LAND. Les trois côtés, un à trois H, la fermeture finale, les trois destinations, le garde 0/4, les durées et autorités restent inchangés. **Aucun changement** au monde, contrôleur C, oracles, négatifs, limites rouges, RESET, LAND ni limite 210 s.

## Protocole de qualification

```bash
node experiments/grand-prix-pupil-algorithm/build.js
node experiments/grand-prix-pupil-algorithm/verify.js --structural-only
npm ci --prefix plugins/robot_windows/blockly_v2
node experiments/grand-prix-pupil-algorithm/verify.js
python3 tools/blockly/measure_wbb.py experiments/grand-prix-pupil-algorithm/Grand-Prix-sans-murs-algorithme-candidat.wbb
```

Workflow **isolé sur cette seule branche**, jamais dans les PR ni main : qualifier séparément Blockly réel + interpréteur, puis des positifs natifs R2025a seed 0/3/4/15 (`--suite witness --side 2.0`), conserver traces originales d'échec et ne pas contourner RESET. **Aucun succès natif, répétabilité, négatif exhaustif, RESET frais, GUI élève/boîte de dialogue OS ou PASS pédagogique ne peut être revendiqué AVANT observation et analyse des archives.** Les sept PASS de #703 ne s'appliquent pas à cette variante.

Falsification prioritaire : après un H ouvert, observation frontale pourrait conduire à un second passage et compter deux fois. Mesurer H réellement franchis, consignes et poses, contrôle post-H, erreurs terminales, trois arrivées et marge du rayon 0,09. Les deux LAND forcés à 210000 ms et les huit négatifs de #647 demeurent la référence historique à préserver, non des preuves transférées. La difficulté 216 blocs / 9 variables / 8 niveaux est toujours majeure : ne pas annoncer « accessible collégiens » sans construction, pas-à-pas, correction et Save/Open observés chez des élèves puis décision personnelle du propriétaire. Aucun GO indépendant, Ready, merge ni TEST_REQUIRED.
