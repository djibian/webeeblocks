# Vertical pilot — V5 independent-review dossier (DRAFT, NO MERGE)

**Authority:** evidence only; not a Controller GO, CI Gate, owner authorization,
hardware qualification or an approved pedagogical activity.

## Consolidation V5 — 2026-11-11 : #952 + #955 en une seule PR vers main

**Périmètre et autorité.** PR #955 est retargetée directement vers `main`;
cette intégration inclut les changements #952. Cette note **supplante les
formulations prospectives des sections historiques ci-dessous** (« pas encore de
binaire produit », « n'a pas de tests d'amplitudes intermédiaires », etc.).
Les sections d'origine conservent la provenance #953/#954 et les contre-exemples.
Ceci est un **dossier technique Draft**, ni revue indépendante GO, ni CI Gate
Ready, ni autorisation de fusion ou de vol physique.

### Identité des sources et périmètre de la rationalisation

- `main` au retarget : `d932943215b1f9db49dbe7f0b0115d6a5d599ad6`.
- #952 (contribution intégralement incluse) : `198c48669ac3bcfdd2990486eed8edf2ad0eeee9`.
- #955 avant rationalisation : `71fe82a56a00f04c14bf5b4d691c24ef34203e88`.
- #953 diagnostic : `977e7c33e7c59ea87de0ad684239986a3f84b9d5`;
  #954 diagnostic : `a84d477e31f72c3cd87abfa6191fabaf408450ae`;
  #957 contre-épreuves isolées : `b63e14a8c3ee757ead5b878dd1637bae4cf94dc9`.
- Le nouveau commit ne modifie **aucun** code de pilotage, oracles,
  évaluateur, physique, profils, interactions STOP/RESET/LAND ou échéance.
  Il supprime seulement deux workflows Draft spécifiques à l'ancienne base,
  raccorde le test pur `tools/ci/test_grand_prix_route_vertical_product.py`
  au job existant `grand-prix-prototype` de la suite Runtime canonique
  (`.github/workflows/ci-runtime.yml`) et complète le présent dossier.
  `tools/ci/select_ci.py` possède déjà la sélection
  `tools/ci/*grand_prix*` pour Runtime **et** Webots ; le changement de
  workflow sollicite en outre les vérifications intégrales quand elles sont
  activées. La politique Draft de `CI Gate (Draft)` reste intacte.
- Les anciens workflows `gp-product-native-draft.yml` et
  `route-vertical-product-smoke.yml` ne ciblent que la base #952 et ne sont
  plus utiles au candidat final. Leurs runs, journaux et artefacts GitHub
  restent accessibles et sont cités ci-dessous ; aucun artefact n'est supprimé.
- Distinguer les différences **héritées de #952 par rapport à main** (oracles
  approche H/bande basse, UI du verdict, gouverneur TAKEOFF) des modifications
  du présent commit : « inchangé » signifie **par rapport au HEAD produit #955
  pré-rationalisation**, et ne nie pas les corrections délibérées de #952.

### Preuves natives réutilisables, même produit binaire R2025a

Toutes les preuves de cette section sont circonscrites au binaire de #955 avant
rationalisation, reconstruit de façon identique par les bancs #955/#957.
Binaire `grand_prix_route_flight` SHA-256
`88288e0f14c10e4a5d75ec55d08f9b25f9b35b2310955c16fa1aef24f3894aa8` ;
C généré `runtime_u.c` SHA-256
`9e93b1771989ddbc7ac50977d6fdc0293a3c439a3c48a1101c8ba934a42264ed` ;
évaluateur `be6a520bc3ef25792053457761b6f6f25afbf19526045be1476a8780e14a5e7d` ;
C partagé `45def7bd65ab21956f06fceed8d956c6e763e6b567d04efa0f9b1a8fc9ca0e00`.
Webots R2025a ; physique 8 ms ; échantillonnage contrôleur 32 ms.
La rationalisation est exclusivement CI/documentation : la revue doit
recontrôler le diff du **nouveau HEAD**, elle ne doit pas supposer qu'un
succès CI sur l'ancien HEAD est un `CI Gate` pour celui-ci.

| Provenance | Faits attestés et limitations |
|---|---|
| #953/#954 [run 42878862498](https://github.com/djibian/webeeblocks/actions/runs/42878862498), [artefact 13795080041](https://github.com/djibian/webeeblocks/actions/runs/42878862498/artifacts/13795080041) | Neuf scénarios diagnostics natifs, incluant TAKEOFF, VERTICAL, plafond, H et STOP/RESET/LAND/délai. **Autre composition expérimentale** : ne prouve pas, seule, le binaire produit #955. |
| #955 [run 42911030479](https://github.com/djibian/webeeblocks/actions/runs/42911030479), artefacts [13808321100](https://github.com/djibian/webeeblocks/actions/runs/42911030479/artifacts/13808321100), [13807342942](https://github.com/djibian/webeeblocks/actions/runs/42911030479/artifacts/13807342942), [13806713362](https://github.com/djibian/webeeblocks/actions/runs/42911030479/artifacts/13806713362) | Trois jobs natifs **success** ; 13/13 conditions de scénario bornées : primitives/STOP/RESET/210 s, trois H1/H2/H3 `STATE achieved`, préflight et vrais refus contact/vol bas. Les négatifs ne sont pas des PASS de mission. |
| #955 [smoke 42911030672](https://github.com/djibian/webeeblocks/actions/runs/42911030672), [artefact 13806364157](https://github.com/djibian/webeeblocks/actions/runs/42911030672/artifacts/13806364157) | Recomposition/build binaire produit natif **success** au HEAD pré-rationalisation. |
| #957 [run 42922980181](https://github.com/djibian/webeeblocks/actions/runs/42922980181), artefacts [13811519254](https://github.com/djibian/webeeblocks/actions/runs/42922980181/artifacts/13811519254), [13812742335](https://github.com/djibian/webeeblocks/actions/runs/42922980181/artifacts/13812742335) | Succès natifs : admissions UP .20/.30/.40 et .50 m, refus .40/.50 m près de la frontière, aucun `altitude` physique. **Le workflow complet a échoué** : une attente spéculative de refus à vitesse positive a été réfutée par une admission sûre. Ne pas présenter le run global comme vert. |
| #957 [retest 42923533414](https://github.com/djibian/webeeblocks/actions/runs/42923533414), [artefact 13811809329](https://github.com/djibian/webeeblocks/actions/runs/42923533414/artifacts/13811809329) | Job **success** : vz initial réellement observé +0,063768 m/s, UP .50 admis (zmax=1,019226m) ; vz +0,061911 m/s, UP .50 refusé avant commande ; formule de marge comparée avec écart ≈1,675×10⁻¹⁰m. |
| #957 [run 42924142774](https://github.com/djibian/webeeblocks/actions/runs/42924142774), [artefact 13812913454](https://github.com/djibian/webeeblocks/actions/runs/42924142774/artifacts/13812913454) | Job **failure** : deux préparations VERTICAL down ont généré vz **négatif** −0,05142/−0,13285m/s, pas la vitesse montante recherchée. Aucun dépassement de plafond mesuré (zmax=0,944535/1,039479m). **Couverture positive-vz additionnelle NON démontrée.** |
| #957 [replay, artefact 13812292387](https://github.com/djibian/webeeblocks/actions/runs/42922980181/artifacts/13812292387) | Job **success** : H1 `achieved` puis fermeture `invalid-native-observation` t=61,992s, RESET au sol, anciennes lectures refusées `OUTCOME_UNAVAILABLE` avant et après TAKEOFF #2. Identifiants 1 et 2 distincts ; STOP #2 conduit à LAND indépendant. |

### Réfutations : statut à opposer à toute future revue

1. **#954 ne qualifie pas le binaire produit : RÉSOLU sur le périmètre
   observable** par compilation native et tests directs #955 42911030479 et
   smoke 42911030672, hash produit verrouillé. Un **A/B bit-à-bit avec le
   diagnostic #954** reste facultatif pour une revendication de stricte
   équivalence, qui n'est pas revendiquée ici.
2. **Amplitude d'ascension .10–.50m : RÉSOLU pour les admissions/refus
   instrumentés**, incluant les points intermédiaires et la marge plafond.
   **Vitesse positive : RÉSOLU uniquement pour +0,062…+0,064m/s** en entrée
   d'UP .50, avec décision conforme au garde empirique. La bande `>=+0,10m/s`
   près du plafond **n'est pas démontrée accessible** par les stimuli natifs
   tentés, et n'est pas qualifiée. Une valeur de vz arbitrairement injectée
   n'est pas une contre-épreuve physique. Ne lancer un nouveau banc que si une
   revue identifie un scénario concret, accessible et bloquant, non couvert.
3. **#956 LAND pré-contact/same-tick ACK : RÉSOLU pour les 12 épisodes LAND
   natifs observés à 32 ms**, sans ACK avant toucher ni avant stabilité
   continue de contact >=0,5s. Onze fenêtres échantillonnées 0,512s, une
   0,640s ; rebonds post-touchdown réinitialisent
   `gp_land_contact_since` sans rallumer les moteurs. **Limite :** absence
   de preuve formelle d'un contact ininterrompu entre deux observations 32ms,
   même si la scène physique évolue à 8ms. Ne pas déclarer une continuité
   physique à résolution 8ms.
4. **Succès tardif / RESET : RÉSOLU pour le replay normal natif #957**
   (deux lectures obsolètes refusées, nouvelles admissions distinctes). La
   résistance à une injection malveillante de marqueurs privés ou à une
   course nano-temporelle artificielle n'est pas testée et n'est pas déduite.
5. **STOP, RESET, LAND autonome, échéance 210000ms : CONFIRMÉ pour les
   scénarios #955 ciblés**. Deadline : admission t=3,168s, déclenchement
   t=213,168s ; LAND indépendant confirmé t=217,872s. Refus RESET en vol
   `LANDING_UNCONFIRMED`. La preuve ne couvre pas tous les états du produit.
6. **Oracle/collision/zone basse : aucune relaxation**. Les H1/H2/H3
   réussissent physiquement ; des scénarios de contact `envelope-contact`,
   `low-outside-zone`, `VERTICAL_LIMIT` et `INVALID_TAKEOFF` refusent
   comme attendu. Les corrections #952 des règles pédagogiques restent
   distinctes de la composition verticale #955. Le dossier ne revendique
   ni couverture exhaustive des 12 routes ni PASS d'un Blockly élève.

### Vérification du contrat LAND / plafond et frontières de décision

- Le code route `route_vertical_product.py` n'intercepte que la composition
  native route, vérifie l'unicité des ancres de sécurité et insère
  `gp_route_upward_headroom(vz,dz)` **avant toute mutation active_id**.
  Pour UP positif : marge
  `0.095+0.30*dz+0.064*max(vz,0)+max(vz,0)^2/0.50` ;
  TAKEOFF réserve `0.080` plus les deux termes vitesse.
  C'est un filtre empirique d'admission, **pas une preuve exhaustive de
  sécurité physique**. Plafond oracle `origin_z+1.15` inchangé.
- Le code route impose pour LAND `land_touchdown` ET
  `gp_land_contact_since>=0` ET `now-gp_land_contact_since>=STOP_WINDOW`,
  en plus du test de stabilité au sol préexistant. Tout échantillon de
  `land_has_ground_contact` négatif remet le compteur à −1 ; hors LAND il
  est également réinitialisé. Le branchement terminal conserve
  `if (command == CMD_LAND && land_touchdown)` puis moteurs coupés.
- Les 13 scénarios, les logs et l'étude de contact permettent de défendre
  cette garantie à **résolution 32ms** ; ne pas promettre davantage.
- La taxonomie native distingue refus préventif (`VERTICAL_LIMIT`,
  `INVALID_TAKEOFF`), refus d'oracle physique (`altitude`, `contact`,
  `low-outside-zone`), arrêt autonome et délai. Le code WWI `TIME_LIMIT`
  peut couvrir plusieurs causes : seul le verdict d'oracle authentifié
  et lié à la tentative autorise une présentation de mission non réussie.

### Vérifications V5 restant à faire sur le nouveau HEAD

1. Contrôler le diff complet `main → #955` : #952 bien inclus, source
   produit/physics/oracles non modifiés **par la rationalisation**,
   aucun nouveau workflow de diagnostic, test raccordé à Runtime.
2. Observer les vérifications Draft sur le **nouveau HEAD** et leurs échecs
   éventuels sans les transformer en GO. La suite Runtime canonique est
   généralement `skipped` en Draft ; son nouveau test sera obligatoire
   lorsqu'elle sera sélectionnée en Ready / exécution native appropriée.
   Aucun `CI Gate (Draft)` ne vaut le `CI Gate` de la revue Ready.
3. Revue V5 **indépendante** des négatifs, de la taxonomie, du risque
   positif-vz hors enveloppe démontrée et des limites de contact 8ms ;
   déclarer clairement tout résidu applicable au HEAD exact. L'absence
   de contre-preuve concrète n'autorise pas à inventer un PASS général.
4. Si la revue indépendante donne GO et que le propriétaire autorise
   explicitement l'intégration : nouveau HEAD Ready stable, CI Gate canonique
   successful exact HEAD avec Runtime/Webots appropriés, base strictement
   fraîche, aucune réfutation applicable non résolue, fusion conditionnelle
   éventuelle **par une exécution ultérieure**. Ce dossier n'autorise
   aucune de ces transitions.

---

## Exact provenance

- Integrated prerequisite: PR #952 Draft @ `198c48669ac3bcfdd2990486eed8edf2ad0eeee9`.
- Experimental native bench: PR #954 Draft @ `a84d477e31f72c3cd87abfa6191fabaf408450ae`.
- Native GitHub Actions run **42878862498**, artifact **13795080041**
  (`experiment-953-native-takeoff-r2025a-a84d477e31f72c3cd87abfa6191fabaf408450ae`).
- Downloaded artifact SHA-256:
  `8e9f3af202e0790fd4156c970165693c2231c22a3d2543dc9f43c67b57b645b0`.
- Candidate native evaluator SHA-256:
  `be6a520bc3ef25792053457761b6f6f25afbf19526045be1476a8780e14a5e7d`.
- The fixture world SHA-256 is
  `9b1f4f62841c653b406c6d85401d9990890d5afdec5548c4987b67881801a286`
  across all nine recorded scenarios. 8 ms physics, 32 ms native PID.
- **No claim** that this separate product-composition branch has itself passed
  the exact binary native test: ported behavior MUST be compiled and exercised
  on its own exact HEAD before integration.

## Bounded nine-scenario evidence

| Scenario | Native status | Maximum z (m) | Clearance from z=1.165 m (m) | Motor saturations |
|---|---|---:|---:|---:|
| ceiling | pre-acceptance `VERTICAL_LIMIT` | 1.059425 | .105575 | 0 |
| ceiling_large_ascent | pre-acceptance `VERTICAL_LIMIT` | .842292 | .322708 | 0 |
| ceiling_safe_ascent | upward VERTICAL ACK | 1.038451 | .126549 | 0 |
| ceiling_takeoff | `INVALID_TAKEOFF` for 1.1m, then 1.0m accepted | 1.059425 | .105575 | 0 |
| primitives | TAKEOFF, WAIT, MOVE, VERTICAL, TURN, LAND, RESET, new TAKEOFF, STOP | .730716 | .434284 | 0 |
| route_lh | two open H, two physical L, terminal LAND, `STATE achieved` | .979358 | .185642 | 0 |
| stop | MOVE interrupted by `USER_STOPPED`; native LAND confirmed | .842292 | .322708 | 0 |
| reset | ground RESET + TAKEOFF accepted; airborne RESET `LANDING_UNCONFIRMED` | .842292 | .322708 | 0 |
| deadline | 210000ms after admission, independent LAND confirmed | .852118 | .312882 | 0 |

`index.json` reports all scenario stimuli completed. This is not nine successful
**missions**; expected negative tests are negative, and all reports explicitly
set `full_mission_success_claim=false`.

## Mandatory distinctions: evaluator observation revocations

- STOP/MOVE: `invalid-native-observation` at **8.328s**, then
  `GP_ROUTE_SAFETY_LAND evaluator-unavailable` and native forced LAND
  at **8.352s**; ground ready at **11.616s**. An expected fail-closed path
  after STOP, **not** a positive oracle outcome.
- Regular LAND + RESET: previous attempt `native-context-revoked` at
  **17.160s**; new admitted attempt starts at **18.272s**; second attempt
  closes for inactive context after STOP at **22.440s**.
- Normal L/H course: LAND native ground ready at **77.856s**,
  evaluator `invalid-native-observation` at **78.472s**, and the WWI backend
  subsequently reads `STATE achieved`. No native `GP_U_DEADLINE` in
  that case. This is consistent with the evaluator's documented rule
  that publication-positive is not erased by later ALIVE revocation;
  **independent V5 reviewer MUST verify the exact success-latching order
  and reject stale/unlatched cross-epoch outcomes**.
- RESET from ground: former attempt `invalid-native-observation` at
  **2.184s** before new admission at 3.872s. Must not be counted as valid
  active-flight continuity.
- 210s deadline: evaluator closes explicitly with `reason=time-limit` at
  **213.136s**, exactly 210s after 3.136s admission.
- None of these records justifies suppressing `_close`, weakening an oracle,
  changing the deadline, or translating an observation lapse into success.

## Product change and dependency

One source-locked, route-only composition function:
`tools/grand_prix/route_vertical_product.py`, called only from the
`route_observations` branch of `prepare_u_runtime.py`.

1. Keep the #952 progressive TAKEOFF reference as-is.
2. Reuse the *same* physical native PID and existing attitude/motor mixing;
   shift only the common collective to the measured hover feed-forward +
   bounded integral + measured vz damping across aerial TAKEOFF, IDLE, WAIT,
   MOVE, VERTICAL, TURN, and LAND until touchdown. Never bypass
   `if (command == CMD_LAND && land_touchdown)` motor stop.
3. Before assigning `active_id` or targets, reject TAKEOFF exceeding
   `origin_z+1.15 - headroom(vz,0)`; before accepting VERTICAL up,
   reject target exceeding `origin_z+1.15-headroom(vz,dz)`.
4. `headroom(v,dz) = 0.095 + 0.30*dz + 0.064*max(v,0)
   + max(v,0)^2/(2*0.25)` for positive upward VERTICAL;
   TAKEOFF uses a separate `0.080` base reserve with the same speed terms.
   This is an **empirical guard**, not a formal invariant for all trajectories.
5. Preserve unchanged simulator backend, physical sender, motor clamps,
   existing 8ms/32ms clocks, evaluator/scene/oracles, RESET, STOP, independent
   210000ms LAND and mission success guard. No direct-trajectory or added
   VERTICAL governor is adopted.

## Refutations historiques avant les preuves produit (supplantées par la consolidation ci-dessus)

1. **No exact product-binary native A/B yet.** Benchmark run comes from the
   diagnostic #954 code, not the separated product branch. Compile and compare
   requests, rotor outputs, refusal semantics and postconditions at exact HEAD.
2. **Narrow measured envelope:** only .10 and .30m upward command amplitudes,
   limited near-zero initial vertical velocity; no proof for the full .10–.50m
   exposed Blockly domain, and no positive-vz adversarial native envelope.
   Fail closed on unknown performance; do not enlarge oracle ceiling.
3. **Course breadth:** native `STATE achieved` for reference course index 5
   (`gp-route-v2-L2000-2500-3000-TGD-s105-H2`); no complete evidence
   for all 12 reference courses or 1/3-H alternative turns. Negative
   boundary/contact/progress tests needed. No AST-guided pupil route pass.
4. **Success after revocation:** independent reviewer must prove that
   `STATE achieved` is bound to the same epoch, context and
   ground-confirmed success latched **before** ALIVE revocation.
5. **Error taxonomy:** `VERTICAL_LIMIT` and `INVALID_TAKEOFF` mean native
   preventive refusals; `GP_ROUTE_EVALUATOR_CLOSED reason=altitude`
   means physical oracle breach; `GP_U_DEADLINE` means 210s elapsed.
   `TIME_LIMIT` is an overloaded WWI code and must not be presented as a
   unique cause. A wall-clock `Runtime v2 request timeout` is a transport
   non-response, never an oracle verdict. No generic backend modification
   is authorized solely to improve labels.
6. **Safety regression:** continued STOP, airborne RESET refusal, normal
   ground-confirmed LAND and 210s independent LAND at exact candidate HEAD;
   zero actuator saturation in all valid observed envelopes.
7. **Governance:** remain Draft and NO MERGE until independent V5 review,
   exact HEAD CI Gate for Ready, owner approval and appropriate main freshness.
   No physical Crazyflie flight authorization or classroom PASS is inferred.
