# Grand Prix — comparaison A/B native R2025a, hors ligne (#914)

`tools/grand_prix/compare_native_ab.py` compare deux moteurs `webots-bin.exe` réellement distincts, à partir de journaux natifs originaux `GP_STEP_WALL_V1` et de deux inventaires Windows R2025a. Il ne lance rien et ne remplace ni un essai graphique, ni la décision d'acceptation, ni le collecteur passif CPU/RAM de #943.

## Protocole d'acquisition

Sur le même portable Windows et avec la même révision WebeeBlocks, le même programme `.wbb`, les mêmes monde, CoursePlan, GPU/pilote, résolution, fenêtre et FPS déclarés (25, 30 ou 60), relever chaque empreinte de l'**exécutable moteur** `msys64/mingw64/bin/webots-bin.exe` avec `windows_host_inventory.ps1`. Ne pas hacher le lanceur `webots.exe` ou `webotsw.exe` à la place du moteur. Garder l'inventaire JSON de chaque bras et sa version source exacte. L'inventaire prouve les octets sur disque, **pas** le PID effectivement exécuté. La continuité entre PID, moteur, programme et journal doit être vérifiée séparément.

Produire six journaux **originaux** de 30 secondes simulées consécutives au minimum, en ordre A/B, B/A, A/B (trois paires). Ne pas modifier les résumés natifs des pas de 8 ms ni synthétiser les pauses, réinitialisations ou événements GUI. Conserver les fichiers bruts. Placer les journaux et les deux inventaires à côté du manifeste.

## Manifeste illustratif `manifest.json`

```json
{
  "schema": 1,
  "source_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "program_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "course": "route-5",
  "host_id": "portable-declare",
  "display_mode": "fenetre visible, meme resolution et GPU",
  "render_fps": 25,
  "phase_ms": [8000, 38000],
  "inventories": {"A": "reference.json", "B": "candidate.json"},
  "trials": [
    {"arm": "A", "log": "A1.log"}, {"arm": "B", "log": "B1.log"},
    {"arm": "B", "log": "B2.log"}, {"arm": "A", "log": "A2.log"},
    {"arm": "A", "log": "A3.log"}, {"arm": "B", "log": "B3.log"}
  ]
}
```

Remplacer toutes les valeurs fictives par les SHA, parcours, phase et chemins réellement observés. Exécuter à la racine du dépôt :

```bash
python3 -m tools.grand_prix.compare_native_ab /chemin/manifest.json
python3 -m unittest tools.ci.test_grand_prix_compare_native_ab
```

Le comparateur refuse un moteur identique entre A et B, un inventaire incomplet ou incompatible, des paires non alternées, les journaux dupliqués, les phases trop courtes ou différentes, et les résumés non concordants avec les durées brutes. Il fournit des médianes diagnostiques de vitesse monotone entre fenêtres complètes et de p99 pas/cycle.

**Limites impératives** : le SHA du moteur réellement chargé, l'identité de machine, la charge système, le FPS visible, les latences Blockly, le PASS de sûreté READY/RESET/LAND et la cible produit ≥0,95× ne sont pas démontrés par ce seul calcul. La vitesse d'enveloppe n'inclut pas les délais extérieurs aux premières/dernières fenêtres complètes ; aucun résultat ne crée une autorité de vol ni un checkpoint humain.
