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
