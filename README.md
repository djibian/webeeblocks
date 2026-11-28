# 🐝 WebeeBlocks

**Apprendre à programmer un drone avec Blockly, en simulation Webots.**

WebeeBlocks est un environnement pédagogique libre, en français, destiné notamment aux élèves de 4e et 3e. L'élève construit un algorithme, le teste, observe le drone, corrige son programme et recommence.

## Commencer

- [Télécharger la version v0.1.0 pour Windows](https://github.com/djibian/webeeblocks/releases/tag/v0.1.0).
- Installer Webots **R2025a**, extraire l'archive et lancer `Lancer-Progression.cmd`.
- Suivre le [guide élève et enseignant](docs/GUIDE_UTILISATEUR.md).

La première version distribuée propose **8 activités Grand Prix, 35 parcours et 8 projets de départ .wbb**. Elle fonctionne sans service Internet pendant l'activité, dans une session scolaire disposant de ses ressources locales. Aucun compte élève ni code textuel.

La release a passé sa qualification automatisée ; la nouvelle acceptation enseignante n'a pas été effectuée. Cette version est **exclusivement destinée à la simulation**.

## Le parcours Grand Prix

| Activité | Apprentissage | Parcours |
| --- | --- | ---: |
| A1 — Parcourir un circuit | Séquences, déplacements | 1 |
| A2 — Franchir un H ouvert | Altitude | 1 |
| A3 — Répéter un trajet | Boucles de répétition | 1 |
| A4 — Observer pour adapter le déplacement | Capteurs et calculs | 3 |
| A5 — Mémoriser le virage | Conditions et variables | 5 |
| A6 — Discriminer un H ouvert | Combiner des observations | 5 |
| A7 — Mini Grand Prix | Boucles conditionnelles et procédures | 7 |
| A8 — Grand Prix autonome | Synthèse des acquis | 12 |

Pour chaque activité, un même programme doit pouvoir résoudre toutes ses variantes. Les règles de sécurité et les résultats de mission sont vérifiés par le simulateur, sans imposer une solution Blockly particulière.

## Développement

- [Vision produit](docs/PRODUCT_VISION.md) et [roadmap](docs/ROADMAP.md).
- [Contrat pédagogique A1–A8](docs/GRAND_PRIX_PEDAGOGICAL_PROGRESSION_1-8.md).
- [Architecture](docs/ARCHITECTURE.md), [contrat V5](AGENTS.md) et [développement](docs/DEVELOPMENT.md).
- [Prévisualisation Linux depuis les sources](docs/GRAND_PRIX_A1_A8_LINUX.md).
- [Historique et preuves](docs/HISTORIQUE.md).

Les anomalies et retours de classe sont à signaler dans les [issues GitHub](https://github.com/djibian/webeeblocks/issues).

Licence GPL-3.0 ; les composants tiers conservent leurs notices respectives.
