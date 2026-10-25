# #637 — intervention mécanique native R2025a sans PID ni moteur

**Résultat nouveau : le contact sol suffit à produire une forte rotation en un
pas dans une fixture réduite. La cause complète des FAIL historiques et la
santé de main restent UNPROVEN. Aucun correctif produit ni GO intégrateur.**

L'[audit précédent](https://github.com/djibian/webeeblocks/blob/eccfe5701c2459bc1ae737bcea70bf5004061f27/experiments/runtime-contact-causal-audit/README.md)
avait calculé le manifold et rejoué le PID, mais n'avait pas réalisé
l'intervention dynamique. Ici, le **vrai binaire Webots R2025a** exécute les
quatre cas fixés dans `protocol.json` avant l'acquisition, un seul pas de 32 ms
par processus neuf. Le protocole a l'empreinte
`4a626ae5acb99d3a4b81c2ce83c75f38b195849580ec1894b09f103a78cf76c0`.
Le programme élève, les mondes produit, le PID, RESET/LAND, les oracles, les
tolérances et la CI ne sont pas modifiés.

## Domaine contrôlé

Base exacte : `main@f5435a8d28b7a2dfae2f50f896aa40a246a4858b`.
AGENTS V5 / vision / roadmap : blobs `c00e855a431b1b83382ba333b0db490a8c330e53`,
`121409284eba687941c9f1f195077007c3352855`,
`e150cf29129304e54ce3a2eb7cd8208dbf648876`.

Le corps est le cylindre de collision du PROTO R2025a : rayon 50 mm, hauteur
30 mm, masse 50 g, plan horizontal. Son inertie de cylindre homogène est
explicitement fixée : `Ixx=Iyy=0.000035`, `Izz=0.0000625 kg m²`, centre de
masse nul. Elle correspond à la géométrie homogène automatique du PROTO ; ce
modèle n'est pas une mesure du vrai drone. Aucun propulseur, moteur, contrôleur
produit, damping ajouté, force ou couple appliqué : seulement la gravité.
ERP=0.2, CFM=1e-5, gravité=9.81, seed=1, un thread physique et pas=32 ms,
conformes aux valeurs du monde produit et aux défauts R2025a. Matériaux de
contact par défaut, sans réglage contre le résultat. Les mondes exacts générés
sont retenus, sans PROTO distant ni dépendance de texture.

Position, tangage et vitesse native 6D viennent de l'échantillon FAIL #686
12.448 s, archive 12594851352 du run 40181830007. L'archive originale, lue et
contrôlée dans l'audit précédent, est à nouveau extraite du commit d'évidence ;
sa ligne native est la source des six vitesses. Tous les chiffres sont arrondis
à la précision du journal original. Les trois cas avec sol ne changent que Z ;
le quatrième retire le plan à Z initial identique. Chaque cas commence à t=0,
impose la même vitesse, observe le manifold initial, puis avance de 32 ms et
observe pose/vitesse/contacts. Un processus neuf élimine le partage intentionnel
de contraintes ou d'états moteurs entre cas. Les états hôtes ne sont pas
prétendus intégralement identiques ni rétrospectivement ceux de GitHub Actions.

## Résultat de la première acquisition exploitable

| Cas fixé avant essai | ΔZ | Contacts avant pas | Tangage après 32 ms | ωY après (rad/s) | VX après (m/s) |
|---|---:|---:|---:|---:|---:|
| Contact unique | 0 | 1 | **+0.565194081** | **+18.165069393** | **+0.272928907** |
| Plus haut | +186.368 µm | 0 | −0.000507916 | −0.000143897 | +0.002012302 |
| Plus bas | −46 µm | 4 | −0.000500803 | +0.000078390 | +0.000001184 |
| Sans sol | 0 | 0 | −0.000507916 | −0.000143897 | +0.002012302 |

Les quatre manifolds **avant** le pas concordent avec le calcul géométrique
indépendant, y compris le point historique excentré
`(0.12538319299773018, 0, -0.000005538649022821272)` m. Les contacts après pas
appartiennent à la nouvelle pose : ils ne sont pas les joints qui ont produit
l'impulsion pendant le pas. Le cas sans contact initial termine avec quatre
contacts géométriques, mais sa vitesse est encore celle de la chute libre ;
confondre ces deux instants inverserait l'explication.

Le cas sans sol et le cas plus haut ont les mêmes vitesses/orientations après
le pas ; `VZ=-0.934248214 m/s` correspond à `VZ_initial - 9.81*0.032`.
Le cas contact unique développe une grande rotation et une vitesse latérale
en l'absence de tout feedback. Le cas quatre contacts rebondit avec une
rotation minuscule. **C'est une intervention causale contrôlée dans ce modèle
réduit**, au-delà de la corrélation des archives. Elle démontre que le PID
actif n'est pas nécessaire au déclenchement d'une telle rotation ; elle ne
démontre pas qu'il n'amplifie pas ensuite le FAIL produit.

La balance de quantité de mouvement donne pour le cas unique une impulsion
nette inférée `(0.0135458303, 0, 0.0167887527) N s` et une impulsion angulaire
Y inférée `0.0006357825 N m s`. Ces quantités sont **inférées** des vitesses,
masse, inertie et gravité spécifiées, pas mesurées dans les joints ODE.
La friction et la normale contribuent toutes deux au moment. Aucun
enregistrement direct des forces/impulsions individuelles n'est revendiqué.

## Reproduction et intégrité

Archive Linux officielle :
`https://github.com/cyberbotics/webots/releases/download/R2025a/webots-R2025a-x86-64.tar.bz2`,
SHA256 mesuré `c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`.
`webots-bin` : `c12c65e8680b579d0f33c34be452f100a302bdecc6d9344becf356db4a675a1a`,
identique au binaire de la voie native TCP #651. Extraction avec
`tar --no-same-owner` dans une installation de diagnostic séparée.
Python 3.12 et Xvfb sous Ubuntu 24.04, noyau 6.18.55 ; ce n'est pas le
conteneur Ubuntu 22.04 de la CI canonique.

```sh
python3 experiments/native-contact-intervention/run.py \
  --webots-home /absolute/path/to/webots \
  --xvfb /absolute/path/to/Xvfb \
  --output /absolute/path/to/new-output-directory
python3 experiments/native-contact-intervention/analyze.py \
  experiments/native-contact-intervention/evidence/acquisition-03
python3 experiments/native-contact-intervention/test_evidence.py
```

Le contrôleur utilise le transport TCP externe officiel, car les sockets Unix
sont indisponibles dans cet environnement. Les erreurs `QLocalServer::listen`
restent visibles et ne sont pas des FAIL physiques ; chaque connexion TCP et
observation native est conservée. Le rendu est désactivé pour cette seule
fixture mécanique, sans capteurs ni preuve visuelle. Les logs, mondes, données
brutes, protocole, provenance des scripts et manifeste SHA256 sont retenus.
L'analyse refuse inventaire incomplet/modifié, mauvais protocole, monde changé,
état initial différent, mauvais pas, manifold incompatible ou marqueur absent.
**Sept tests** incluent données natives originales et six corruptions/refus.
L'inventaire prouve une intégrité interne ; il n'est ni signature ni attestation
indépendante du producteur des observations.

Deux tentatives de préparation non exploitables sont conservées séparément :
01, Xvfb ne trouvait pas `/usr/bin/xkbcomp` ; 02, le script s'appelait
`controller.py` et masquait le module Webots. Elles n'ont produit aucune
observation native utilisable et n'ont pas conduit à ajuster le protocole.
Les remèdes concernent le support de lancement (helper XKB, renommage du script),
pas la physique. L'extraction initiale sans `--no-same-owner` avait également
refusé les propriétaires uid/gid du tar ; l'empreinte du binaire final est
contrôlée. Aucun échec expérimental n'a été remplacé par un rejeu réussi.

## Conséquence et frontière suivante

L'hypothèse « une réaction du PID est indispensable pour produire la première
grande rotation » est réfutée **dans la fixture**. Le contact unique à faible
pénétration fournit un mécanisme suffisant, sensible à la phase verticale.
Le +186 µm n'est ni une marge produit ni un correctif ; le −46 µm n'est pas
une recommandation d'enfoncer le robot. Le passage à quatre points conserve
ici le tangage mais fait rebondir : cela ne qualifie aucune pose ni mission.

Le moteur réel du modèle n'est pas présent et sa poussée historique manque.
Le résultat ne reproduit donc pas quantitativement le tangage historique
~0.4206 rad, ne détermine pas l'origine du décalage Z et ne prouve ni
non-déterminisme ODE ni cause commune avec RESET. Ne pas remplacer les
obligations natives par cette fixture.

L'étape discriminante suivante consiste à relever dans une continuation native
du vrai modèle **vitesses internes des moteurs, poussées/couples et état 6D**,
puis à comparer à état entrant complet identique le PID actif et les commandes
gelées. Pour un test intermédiaire mécanique, une force constante explicitement
fixée doit avoir son propre protocole déclaré avant acquisition. Une consigne
moteur n'est toujours pas une poussée. Les contacts/joints doivent être datés
avant/après le pas sans confondre manifold géométrique et impulsion résolue.

Les CI rouges et NO_GO applicables de #686/#693/#698, le timeout de démarrage
#690, le FAIL pédagogique #635 et le RESET historique restent distincts et
non levés. Aucune fusion ordinaire, acceptation pédagogique, notification
TEST_REQUIRED, autorisation matérielle ou vol n'est déduite de ce résultat.
