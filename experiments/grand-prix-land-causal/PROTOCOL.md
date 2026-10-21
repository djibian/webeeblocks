# LAND #638 — protocole natif borné, avant acquisition

Date : 21 octobre 2026. Diagnostic de simulation, aucun correctif produit.

## Hypothèse et réfutation

H : après une impulsion de contact, la dérivée de l'erreur de vitesse du PID
entretient une alternance d'assiette qui amplifie le déplacement latéral.
Alternative : cette dérivée explique les commandes, mais son ablation ne réduit
pas l'excursion physique, notamment à cause du contact et des actionneurs lents.

A conserve le contrôleur/PID de #638. B neutralise **uniquement** la différence
d'erreur de vitesse horizontale, au premier échantillon de contrôle observant
un contact au sol pendant LAND et aux suivants. On assigne l'erreur courante à
son historique immédiatement avant l'appel du vrai PID C. Les gains, historique
d'assiette, intégrateur vertical et toutes les conditions LAND restent intacts.
Ce choix est une ablation causale du mécanisme identifié dans a765396, pas une
proposition de réglage ou de correction sûre. Avant contact, le code de commande
est identique. La détection et les observations supplémentaires sont communes.

## Domaine et budget immuables

Référence exacte : `149c0b61b48f335eb4cb925113ccc03afce80cca` (#638),
seed 14, côté 2 m, damiers présents, même témoin Blockly/AST, collisions,
cibles et oracle inchangés. Pas d'empilement d'autres PR produit.
Image R2025a `sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099`,
assets `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`.

**Au plus quatre processus natifs : A1, B1, B2, A2, une fois chacun.**
Appariements A1/B1 et A2/B2 ; ordre inversé pour le second.
Aucune injection de force, téléportation expérimentale, substitution de
mesure ou modification du programme. Aucune campagne RESET ni suite #637.
Arrêt définitif au premier échec technique/preuve indispensable manquante,
ou après ces quatre processus. Un résultat physique négatif reste une donnée
et ne provoque ni retry ni changement du protocole. Chaque essai conserve
le budget de 600 s murales du pilote existant ; budget global 2100 s.

## Observations

Conserver les fichiers natifs complets, contacts XYZ/vitesse/orientation à 8 ms,
mesures GPS corporelles réellement consommées à 32 ms, erreur et dérivée avant
ablation, ablation effective, assiette demandée, mixage et moteurs après clamps,
instant stop/ACK et verdict de l'oracle. La fin du programme n'est pas le stop.
Observer aussi trois secondes simulées après le stop, sans commander les moteurs.

Ajouter une lecture des rotations des quatre slowHelix internes du PROTO à
chaque pas natif, sans modifier leurs champs. Ce sont des états cinématiques,
pas des consignes API. Source officielle R2025a : WbMotor::runKinematicControl
limite ici l'accélération à 30 rad/s² ; WbPropeller::prePhysicsStep avance
l'hélice et applique les forces selon currentVelocity. Après validation de la
continuité/chronologie des rotations, la loi du modèle permet de dériver la
poussée `4e-5 * omega²` et le couple `2.4e-6 * omega*abs(omega)`.
Cela ne mesure pas directement les impulsions de contact. Un état d'hélice
absent, figé malgré le vol, ambigu ou non fini rend la preuve de forces
indisponible ; ne pas lui substituer la vitesse cible moteur.

Le feedback moteur public n'est pas une solution supposée : bien que
WbRotationalMotor::computeFeedback traite Propeller, WbMotor::enableMotorFeedback
refuse l'absence de joint. Aucune extension ABI ou mutation du simulateur.

## Critères fixés

Défaut exercé : après un premier contact proche de la cible (erreur XY <= 0,10 m,
vitesse XY <= 0,02 m/s), déplacement XY > 0,10 m ou vitesse XY > 0,20 m/s,
avec rejet natif `wrong-landing` ou `envelope-contact`.

Une paire n'est comparable que si les erreurs relatives à la cible au premier
contact diffèrent de <= 0,02 m, les vitesses XY de <= 0,02 m/s, VZ de <= 0,03 m/s,
roll/pitch de <= 1 degré, et le nombre initial de contacts est identique.
Conserver et signaler les paires non comparables ; aucune égalité des états
internes du solveur n'est prétendue.

Soutien borné à H : les deux A exercent le défaut, les deux paires sont
comparables, les deux B activent l'ablation et obtiennent une pose `achieved`,
avec vitesse post-contact <= 0,05 m/s et déplacement post-contact <= 0,03 m,
et les forces dérivées sont valides. Une seule paire est un indice, pas une
validation suffisante. Si un A ne reproduit pas le défaut : **NON CONCLUANT**
pour cette paire, même si B réussit. Si B conserve l'excursion : H non soutenue
dans cet essai. L'absence d'excursion des deux variantes n'est pas une réparation.

Les déplacements/descente avant contact doivent rester conformes et sont
archivés ; toute régression est conservée. Ce domaine ne qualifie pas les autres
seeds, négatifs, précision globale ni le vol normal universel. Une correction
ultérieure exigerait nouvelle preuve avant/après, tous les négatifs et 210 s,
CI Gate exacte Ready et revue indépendante résolvant les NO_GO de #638.

## Autorité

Main observé `b478f9dd1854d83345abe13ed20fcf7baeffaca5` ; V5/vision/roadmap
`c1b0078103507e7b0132af948b34a5cbd7b5950a` /
`df0b3b8591562f13f879db5c3f5ab78286b84cde` /
`e8c4e246df15f223728f94743c958374176fccac`.
#637 reste ouvert et les intégrations ordinaires suspendues. #638 reste Draft,
HEAD 149c0b6, NO_GO 5574571532 et FAIL seed 14 maintenus.
La branche expérimentale et son workflow push-only ne sont pas une CI Gate,
ne modifient pas #638 et n'autorisent aucun GO, fusion, PASS pédagogique,
TEST_REQUIRED, refonte 2–7 ni vol réel.
