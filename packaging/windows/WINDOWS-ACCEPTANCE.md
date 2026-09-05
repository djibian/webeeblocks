# Acceptation Windows WebeeBlocks

Statut de référence : **BASELINE CHROME VALIDÉE — MODÈLE DE REVALIDATION**

Cette fiche n’est plus la preuve manquante du support Windows actuel : les gates
réels W1 et W2 consignés dans l’issue #81 ont établi le parcours Chrome sur le
poste de classe le moins puissant. Elle sert à revalider une future release
lorsqu’un changement matériel du produit, du packaging ou de l’environnement
rend cette preuve à nouveau décision-relevante.

## Périmètre de la revendication

Le périmètre actuellement validé est :

- Windows 10/11 64 bits ;
- Webots R2025a ;
- Google Chrome ;
- fonctionnement normal hors ligne après préparation.

**Edge et Firefox ne sont pas couverts par ce verdict.** Firefox same-file reste
suivi par #87. Ne cocher aucun verdict Windows comme preuve implicite de ces
navigateurs.

## Baseline réelle déjà établie

| Élément | Référence validée |
| --- | --- |
| Poste faible | Dell OptiPlex 3050 |
| Windows | Windows 11 |
| CPU | Intel Core i3-7100 |
| RAM | 4 Go |
| GPU | Intel HD Graphics 630 |
| Webots | R2025a |
| Navigateur | Google Chrome |
| W1 | PASS — parcours fonctionnel hors ligne |
| W2 | PASS — stabilité hors ligne 30 min |

Les détails exacts d’artefact, versions et observations restent dans l’issue
#81 ; ne recopiez pas cette ligne comme preuve d’un futur artefact différent.

## Revalidation d’une future release

### Configuration mesurée

| Élément | Valeur |
| --- | --- |
| Date | |
| SHA / artefact exact | |
| Windows (édition/version) | |
| CPU | |
| RAM installée | |
| GPU et pilote | |
| Webots | R2025a |
| Google Chrome | |

### Parcours obligatoire hors ligne

- [ ] extraction dans un chemin contenant des espaces ;
- [ ] double-clic sur `Launch-WebeeBlocks.cmd` ;
- [ ] démarrage de Webots sans action ▶ manuelle ;
- [ ] Robot Window Blockly en français et état `PRÊT` ;
- [ ] exécution normale puis STOP neutre ;
- [ ] mode pas à pas, surlignage, valeur brute capteur et `Continuer` ;
- [ ] workspace et `Ouvrir` cohérents pendant l’exécution ;
- [ ] diagnostic élève corrigeable pour un programme invalide puis relance sans
      reset après correction ;
- [ ] réinitialisation et replay ;
- [ ] `Ouvrir`, `Enregistrer sous`, puis `Enregistrer` avec Chrome ;
- [ ] réouverture du fichier `.wbb` sauvegardé ;
- [ ] réseau coupé pendant tout le parcours après installation.

### Mesures du poste le plus faible

| Mesure | Résultat | Critère |
| --- | --- | --- |
| Double-clic → `PRÊT` | | consigner la durée |
| Facteur temps réel Webots | | utilisable pour la classe |
| CPU Webots + Chrome | | sans saturation durable |
| Mémoire Webots + Chrome | | sans swap |
| Glisser-déposer Blockly | | fluide pendant la simulation |
| Grand programme représentatif | | interaction fluide |
| 30 min run/reset/open/save | | aucune croissance ou panne progressive |

## Verdict de revalidation

- [ ] **ACCEPTÉ** — aucun défaut bloquant observé dans le périmètre Chrome ;
- [ ] **REFUSÉ** — joindre les symptômes, journaux, captures et étapes exactes.

Validé par :

Date :
