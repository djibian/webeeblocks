# Grand Prix — qualification native R2025a du décollage : A/B de référence

**Statut : EVIDENCE NATIVE / RECOMMANDATION EXPÉRIMENTALE, PAS GO V5.**
Date : 2026-11-10. Cible : PR Draft #953, base PR Draft #952.
Aucun changement du moteur partagé, du backend physique, de l'évaluateur, des
protections ou des oracles. Les candidats ne vivent que dans la PR diagnostique
Draft #954 et sont appliqués au **C généré** du contrôleur route pendant le
build Docker ; ils ne sont pas un correctif produit validé.

## 1. Identités, comparabilité et sources

- PR #952, gouverneur existant : `198c48669ac3bcfdd2990486eed8edf2ad0eeee9`.
- PR #953, instrumentation + stimulus corrigé : branche
  `experiment/951-gp-takeoff-trace-20261110`.
- Témoin Webots R2025a : CI #42837186296, SHA
  `fa91c413e41879d10f48dde1de157a20be960e47`,
  [artefact brut](https://github.com/djibian/webeeblocks/actions/runs/42837186296/artifacts/13774782275).
- A/B natif isolé : CI #42839853978, SHA
  `4cf8f0e9239a78bac3d4e0ad9e7398b1d6cfe574`,
  [artefact brut](https://github.com/djibian/webeeblocks/actions/runs/42839853978/artifacts/13775626574).
- Source des variantes : `tools/grand_prix/isolated_native_takeoff_candidates.py`
  sur la branche *CI seule* `ci/953-native-takeoff-r2025a`,
  PR Draft #954 (interdiction de fusion). Chaque variante produit un binaire
  distinct ; l'évaluateur conserve **exactement** l'empreinte
  `be6a520bc3ef25792053457761b6f6f25afbf19526045be1476a8780e14a5e7d`.
- Tous les essais utilisent le monde `reference_course(5)` de mêmes octets
  (SHA-256 enregistré dans tous les `summary.json`), un nouveau processus
  par hauteur, un contrôleur 32 ms, une physique R2025a 8 ms, l'authentique
  admission WWI, le vrai évaluateur et **les mêmes oracles**.
- Image R2025a épinglée :
  `ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca`.
  Les journaux sont toujours conservés, y compris sur refus.
- L'environnement GitHub a effectivement exécuté les tests et compilé
  Webots. Le workflow CI diagnostique global est **en échec** pour les
  candidats 2 et 3 non qualifiés : un archivage des échecs ne constitue pas
  un Gate vert. Le témoin et le candidat 1 disposent de traces complètes.

## 2. Quatre stratégies testées et conditions

1. **Témoin** : gouverneur #952 (vitesse limite 0,32 m/s, avance max
   0,14 m) et PID d'altitude d'origine.
2. **Candidat minimal** : exactement le même gouverneur, plus une
   correction *collective verticale locale* dans le C généré :
   `u = 55.368085898 + Kp*clip(z_ref-z, ±1) + Ki*clip(integrale, ±0.20)
   - Kd*vz`, où `Kp=10, Ki=5, Kd=5`. La partie
   `55.368085898` est l'estimation **modèle Webots** de la sustentation
   et ne prétend pas être un paramètre physique Bitcraze universel.
   Le PID partagé produit toujours les composantes attitude/XY ; seul
   le collectif moyen est compensé à son mélange de sorties.
3. **Candidat consigne directe** : ce même PID corrigé, référence
   `z_ref = z_target` pour TAKEOFF.
4. **Candidat de forme Bitcraze** : même PID corrigé, `z_ref =
   z0+(z_target-z0)*(35u^4-84u^5+70u^6-20u^7)`,
   `u=clip((t-t_DEBUT)/((z_target-z0)/0.5),0,1)`.
   Il reproduit **une forme nominale de référence**, non le firmware
   complet, son estimation EKF ou un vol réel. Les référentiels sont
   explicitement alignés en hauteur relative à l'origine Webots.

Toutes les variantes conservent les limites natives sur l'altitude et la
fin de mission, la révocation d'autorité, les refus et le LAND de sécurité.

## 3. Mesures natives R2025a (secondes depuis TAKEOFF)

| Variante | H (m) | Perte de contact | Élévation 2 cm | Stabilité verticale | ACK | Dépassement observé | Vz max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gouverneur + PID initial | 0,5 | 8,992 | 9,760 | 11,584 | 12,096 | 0,00 cm | 0,374 m/s |
| Gouverneur + PID initial | 0,8 | 8,992 | 9,760 | 12,160 | 12,672 | 0,00 cm | 0,469 m/s |
| Gouverneur + PID initial | 1,0 | 8,992 | 9,760 | 12,608 | 13,120 | 0,00 cm | 0,475 m/s |
| **Gouverneur + PID corrigé** | **0,5** | **1,856** | **2,112** | **3,712** | **4,224** | **3,65 cm** | **0,389 m/s** |
| **Gouverneur + PID corrigé** | **0,8** | **1,856** | **2,112** | **4,512** | **5,024** | **3,71 cm** | **0,407 m/s** |
| **Gouverneur + PID corrigé** | **1,0** | **1,856** | **2,112** | **5,184** | **5,696** | **4,44 cm** | **0,407 m/s** |
| Directe + PID corrigé | 0,5 | 1,856 | 2,112 | 6,016 | 6,528 | 20,55 cm | 0,654 m/s |
| Directe + PID corrigé | 0,8 | 1,856 | 2,112 | 6,368 | 6,880 | 26,51 cm | 0,983 m/s |
| Directe + PID corrigé | 1,0 | 1,856 | 2,112 | **non observée** | **refus** | **censuré** | 1,203 m/s observés |
| Bitcraze-forme + PID corrigé | 0,5 | 1,856 | 2,112 | 6,016 | 6,528 | 20,55 cm | 0,654 m/s |
| Bitcraze-forme + PID corrigé | 0,8 | 1,856 | 2,112 | 6,368 | 6,880 | 26,51 cm | 0,983 m/s |
| Bitcraze-forme + PID corrigé | 1,0 | 1,856 | 2,112 | **non observée** | **refus** | **censuré** | 1,203 m/s observés |

**Attention à la censure à 1,0 m :** les `maximum_observed_overshoot_m`
des deux candidats refusés (environ 13,54 cm aux derniers
échantillons du contrôleur) ne sont **pas un pic physique**. Le
Supervisor-évaluateur indépendant a enregistré la violation à
`actual_z=1.165891` m, plafond `1.165000` m,
`vz=+0.634271` m/s encore ascendant ; puis
`GP_ROUTE_EVALUATOR_CLOSED reason=altitude` et
`GP_ROUTE_SAFETY_LAND evaluator-unavailable`.
Les erreurs sont donc **réellement refusées**, non étiquetées PASS.

Les correctifs directs et « forme Bitcraze » sont distincts à
l'amorçage (voir `ref` dans chaque CSV). Mais une fois la
référence arrivée à la cible, la réponse verticale enregistrée
devient quasi identique dans cette configuration ; le profil nominal
rapide **ne résout pas la dynamique de suivi**, même avec le collectif
corrigé.

## 4. Diagnostic causal mesuré

Dans les trois TAKEOFF du témoin, la puissance collective commence à
environ 48,09 unités, augmente progressivement avec l'intégrale du PID
et franchit environ 55,38 unités à 8,960 s ; la perte de contact
survient à 8,992 s. Le gouverneur, bornant l'avance de consigne à
0,14 m, réduit l'erreur disponible pendant que l'appareil reste posé.
La compensation de sustentation absente produit alors un long
**délai d'accumulation intégrale**. Les CSV natifs rapprochent
temporellement référence, P/I/D, commande rotor et perte de contact,
sans remplacer la preuve de contact par un seuil d'altitude.

Le candidat minimal conserve le même gouverneur mais supprime
l'essentiel de ce retard : **7,136 s gagnées**, soit environ
**79,36 % de réduction du délai au soulèvement** ; les ACK
sont avancés de 7,872 s (0,5 m), 7,648 s (0,8 m) et
7,424 s (1,0 m). Le dépassement de 3,65–4,44 cm reste
observable et doit figurer comme exigence de qualification future,
pas être effacé des résultats.

**Précision de lecture des canaux PID :** l'instrumentation native
`p/i/d` de la PR #953 décrit les termes du **PID partagé d'origine**,
exécuté avant la compensation, et non la décomposition de la nouvelle
commande corrigée. Pour les trois candidats, la contribution dérivée
**effectivement utilisée** par le correcteur expérimental vaut
`-5 × vz`, sa composante P vaut `p`, sa composante I vaut
`i` après écrêtage de l'intégrateur. Le collectif effectivement
envoyé est `u` (mélange moyen enregistré). La reconstruction
indépendante `u - (55.368085898+p+i-5*vz)` est nulle dans les
résumés natifs, à la précision de la télémétrie. Ne pas présenter
le champ `d` brut comme le D corrigé.

Les références directe et septième ordre **dépassent** les
altitudes de consigne malgré ce PID corrigé et violent le plafond
à 1,0 m ; elles sont moins stables et plus lentes à ACK pour les
deux hauteurs restantes. Cela falsifie, pour ce banc et ces
réglages, l'hypothèse « la correction locale du PID suffit avec
consigne directe » et l'hypothèse « recopier la forme nominale
Bitcraze serait forcément mieux ».

## 5. Décision technique minimale et portée

**Retenir expérimentalement :**
conserver le gouverneur route #952 et ajouter uniquement une
compensation de sustentation **paramétrée par le modèle Webots**,
une limitation d'intégrale et une dérivée sur la vitesse verticale,
dans la couche *spécifique au simulateur*, **sans changer
l'interprète Blockly, les primitives pédagogiques, l'évaluateur,
les protections ou le backend physique**.

**Écarter pour l'instant :** la consigne directe et le
profil nominal Bitcraze rapide comme substituts directs au
gouverneur ; tous deux échouent au garde d'altitude.
Ne pas porter le firmware complet ni initier une refonte.

**Limites :** ces A/B mesurent une unique configuration de monde
route 5 avec trois hauteurs, sur un seul environnement CI Webots
R2025a. La fidélité Flow Deck/EKF, le comportement MOVE,
VERTICAL, TURN, LAND, les 12 mondes, les oracles négatifs sous
la nouvelle commande, la variation des paramètres et le
ressenti sur PC lycée **restent non qualifiés**. Aucune décision
de livraison, de vol matériel, de merge ou de GO V5 n'en découle.

**Conservation des preuves :** les ZIP natifs ci-dessus contiennent
les mondes, SHA binaires/sources/évaluateur, logs pilote/WWI,
traces CSV à 32 ms, témoins contacts, évènements de refus et
résumés, pour reconstruction indépendante des tableaux.


## 6. Qualification native multi-primitives — 10 novembre 2026

**État : preuves Webots R2025a réellement exécutées, pas de qualification produit
ni de GO V5.** Toutes les valeurs suivantes sont extraites des traces de
contrôleur/évaluateur de production, en physique 8 ms, commande 32 ms,
world `reference_course(5)` à octets identiques. Les patchs affectent
**uniquement le C de route généré à la compilation** dans la PR Draft
diagnostique #954 ; jamais le PID partagé, le moteur, l'évaluateur,
les oracles ou le backend physique.

- Témoin compensation TAKEOFF/IDLE : CI
  [42851205014](https://github.com/djibian/webeeblocks/actions/runs/42851205014),
  SHA `7314f03c8fc8563f391177ae1040921ca17f68cf`,
  [archives brutes](https://github.com/djibian/webeeblocks/actions/runs/42851205014/artifacts/13781162035).
- Compensation identique étendue aux phases motorisées
  TAKEOFF, IDLE en vol, WAIT, MOVE, VERTICAL, TURN, LAND :
  CI [42853379059](https://github.com/djibian/webeeblocks/actions/runs/42853379059),
  SHA `0ae80ef73645e9240b767601ffb83a936d8065e6`,
  [archives brutes](https://github.com/djibian/webeeblocks/actions/runs/42853379059/artifacts/13782850286).
- Extension avec, en plus, **gouverneur #952 réinitialisé sur VERTICAL
  montant** : CI
  [42856305849](https://github.com/djibian/webeeblocks/actions/runs/42856305849),
  SHA `b3c28f83be0a8682660c60dc7b4b5f7545f45c7c`,
  [archives brutes](https://github.com/djibian/webeeblocks/actions/runs/42856305849/artifacts/13783296641).

### 6.1 Mesures A/B native : scénario de primitives

Stimulus normal WWI : TAKEOFF(0,8) → WAIT(0,5) → MOVE(forward,0,12)
→ VERTICAL(up,0,10) → TURN(15°) → VERTICAL(down,0,10)
→ WAIT(0,5), puis LAND volontairement **hors de la zone terminale**.
Le LAND est donc **censé être refusé par l'oracle de mission** ;
son refus n'atteste pas une erreur du PID ni une fin de mission réussie.

| Observé | TAKEOFF/IDLE seulement | Compensation toutes phases | Toutes phases + gouverneur VERTICAL montant |
|---|---:|---:|---:|
| Échantillons natifs à 32 ms | 548 | 484 | 502 |
| Altitude minimale après TAKEOFF, m | 0,153 | 0,829 | voir CSV natif du run |
| Vitesse verticale absolue max de la séquence, m/s | 0,717 | 0,530 | 0,523 |
| Saut max collectif entre modes, hors LAND, unités | 15,941 | 1,458 | voir transitions natives |
| Échantillons avec saturation moteurs brute | 1 | 0 | 0 |
| Dernière primitive acquittée | MOVE | WAIT après TURN et VERTICAL descente | WAIT après TURN et VERTICAL descente |
| Autorité finale | low-outside-zone | low-outside-zone au LAND hors cible | low-outside-zone au LAND hors cible |

Le témoin **perd la sustentation dès IDLE→WAIT** (commande
collective +15,94 unités et z jusqu'à 0,153 m, vz −0,717 m/s),
puis passe sous le gabarit de vol bas hors zone et est révoqué.
La compensation étendue stabilise la succession des primitives ;
le témoin et le nouveau bras restent dans le **même monde et les
mêmes protections**.

### 6.2 Tests négatifs indépendants

- Près du plafond natif `origin_z+1.15 = 1.165000 m`,
  TAKEOFF(1,0) puis VERTICAL(up,0,10) :
  *bras TAKEOFF/IDLE*, fermeture à t=16,176 s, z=1,166515 m,
  vz=+0,234873 m/s ;
  *bras toutes phases*, fermeture à t=9,800 s,
  z=1,165090 m, vz=+0,188343 m/s ;
  *bras toutes phases et gouverneur montant*, fermeture à t=10,032 s,
  z=1,165627 m, vz=+0,165941 m/s.
  Les trois refus `altitude` et le LAND de sécurité sont conservés ;
  le dernier bras ne prouve donc **pas** qu'un gouverneur suffit.
  Les altitudes max après refus sont respectivement 1,1954 / 1,2238 /
  1,2141 m (mesures censurées par le contexte de reprise de contrôle).
- STOP normal durant une opération MOVE : la requête STOP est
  acquittée ; l'évaluateur révoque l'ancienne observation native et
  le LAND autonome s'active, pas de faux succès de mission.
  Le maximum de |vz| relevé est 1,203 m/s (témoin) contre
  0,521 m/s (compensation étendue), sans saturation dans ces deux traces.
- **LAND indépendant 210000 ms** : sans aucune requête LAND, le
  contrôleur émet `GP_U_DEADLINE time_ms=213136 command=LAND`
  lorsque la mission commencée à 3,136 s atteint précisément 210 s.
  Le témoin montre `TRACE LAND_TOUCHDOWN time=215.824`.
  Vitesse verticale max absolue : 1,306 m/s (témoin) contre
  0,535 m/s (compensation étendue). Le cas est un **échec contrôlé
  par garde**, jamais une mission achevée.
- RESET alors que le drone est en vol stationnaire : la variante avec
  gouverneur montant reçoit le refus natif `LANDING_UNCONFIRMED`
  après TAKEOFF(0,8) ; aucun RESET fictif, aucune admission post-RESET
  n'est fabriquée.
- Contrat de plafond à clarifier avant toute intégration : le pilote
  accepte aujourd'hui une **cible** VERTICAL jusqu'à
  `origin_z+1.50`, alors que le Supervisor indépendant clôt tout
  vol au-dessus de `origin_z+1.15`. Ne changer **ni** le plafond,
  **ni** les oracles pour rendre la trajectoire acceptable.

### 6.3 Directe vs « forme Bitcraze » : signaux distincts

Sur les traces natives appariées à la même grille de temps et au même
monde des essais initiaux, les deux références ont des **binaires
différents**, des consignes différentes et des commandes moteur
différentes. À 0,5/0,8/1,0 m, la différence maximale `z_ref`
est respectivement **0,50/0,80/1,00 m** et celle de la commande
collective **5,651/8,978/10,957 unités**. À 0,8 m,
l'écart maximal `z` atteint 0,06290 m et celui de `vz`
0,17143 m/s. Des temps d'ACK et refus semblables **ne prouvent
aucune équivalence des lois de commande**.

### 6.4 Décision pour revue V5

**La correction exclusivement TAKEOFF/IDLE est écartée**
comme solution polyvalente, malgré les trois décollages initiaux
réussis : le changement de phase vers WAIT casse la sustentation.

**L'extension de la correction collective à toutes les phases
motorisées est le meilleur candidat minimal établi** par A/B natif.
Ne pas ajouter d'emblée de nouvel ordonnanceur, d'API Blockly,
de modèle EKF ou de moteur partagé. LAND au contact garde
ses moteurs nuls : pas de maintien artificiel de la poussée au sol.

**Aucun des candidats n'est intégrable aujourd'hui** : même avec
gouverneur VERTICAL montant, le plafond est franchi. Une qualification
ultérieure doit démontrer une admission/refus *anticipé et cohérent*
des cibles VERTICAL proches de l'autorité d'altitude, et une
continuité suffisante sur toutes les phases, sans dupliquer ni
affaiblir l'oracle. Le LAND nominal **au but** et le RESET nominal
**depuis un sol confirmé** restent à qualifier séparément.

CI diagnostique globale rouge (échecs natifs conservés), aucune
fusion de #952/#953/#954, aucun changement du moteur partagé ni du
backend physique. Le feu vert produit et le GO V5 nécessitent une
revue indépendante avec preuves exact-HEAD et les non-régressions.
