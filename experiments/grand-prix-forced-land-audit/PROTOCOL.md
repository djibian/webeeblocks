# Mesure discriminante suivante — protocole préalable, non exécuté

Ce protocole est un résultat de l'analyse des archives, pas une campagne
implicitement lancée. Aucune acquisition native n'a eu lieu dans cet audit.
Il ne rouvre pas A1/B1/B2/A2 de #638.

## Question et hypothèses concurrentes

Attribuer le refus **effectif** du LAND forcé et ordonner les premiers écarts :

- H1 : vraie garde roll/pitch >1,2 rad après évolution dangereuse du corps.
- H2 : mesure consommée invalide ou dt hors domaine ; le message générique
  masque ce sous-prédicat, avant ou indépendamment du seuil d'attitude.
- H3 : timeout >25 s ; il exige un refus après 251,288 s pour le cas historique.
- H4 : la transition MOVE→LAND, l'échelon vertical ou l'échantillonnage crée
  déjà un écart en altitude, avant tout contact.
- H5 : l'impact initial précède le départ du basculement, puis le contrôle ou
  les actionneurs l'amplifient. Plusieurs mécanismes peuvent coexister.

Une seule acquisition observationnelle peut départager H1/H2/H3 et dater les
événements de H4/H5. Elle ne prouve pas à elle seule une causalité nécessaire
ou suffisante du PID, du contact ou du protocole.

## Référence et intervention

Référence source exacte #655 `6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7`,
seed 3, côté 2,00 m, monde sans murs original ; négatif `deadline` inchangé,
vrai Blockly/AST/backend/interpréteur. Les sources générées doivent reproduire
les empreintes de `sources.json` **avant instrumentation**. Retenir ensuite
leurs nouvelles empreintes/binaire effectivement exécutés.
Webots officiel R2025a, archive `c5127fb4206c57a5ae5523f1b7f3da8b670bc8926d9ae08595e139f226f38c38`,
assets `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`, Node 24.19.0,
Blockly 13.2.1, rendu logiciel Mesa, X TCP froid, contrôleurs externes TCP.
Les différences effectives d'environnement doivent être nommées ; ne pas
prétendre une reproduction exacte de tous les états internes du run ancien.

**Aucune intervention de commande.** L'unique ajout admissible est la
télémétrie observationnelle des conditions/entrées/moteurs/contact. Les
gains, historiques, consignes, seuils, critères, deadline et Blockly restent
inchangés. Le coût de journalisation peut déplacer la phase asynchrone ;
ne pas qualifier ce témoin d'identique au run ancien au niveau temporel.

## Préconditions avant toute acquisition

1. Implémenter ce diagnostic dans une branche expérimentale isolée, sans
   muter #655. Vérifier hors Webots son absence d'effet sur les commandes,
   les réponses et les gardes avec le vrai Runtime composé, notamment les
   refus d'attitude, de mesure et de timeout. `instrument.py` et ses neuf
   comparaisons compilées réalisent cette préparation limitée aux traces
   Runtime ; les contacts, la capture indépendante et le coût natif restent
   à qualifier. Leur succès n'anticipe aucun résultat physique.
2. Qualifier hors Webots les frontières de fin/écriture/archivage atomique :
   tous les processus descendants clos, tous les streams fermés ; inventaire
   unique ; source→archive→réouverture byte-identiques. Une erreur arrête la
   préparation. Ne pas corriger les manifestes historiques.
3. Utiliser un journal horodaté indépendant, fermé avant la fin du contrôleur,
   et une fin de capture attestée. Choisir explicitement l'unique dossier de
   scénario ; ne pas sélectionner le premier membre d'un glob indifférencié.
4. Si des vitesses/poussées de rotor sont indispensables à une conclusion,
   qualifier leur observation native **avant** ce cas, en couvrant fastHelix,
   slowHelix et la transition. À défaut, exclure cette conclusion ; le seul
   slowHelix ou les targets moteur ne sont pas des mesures de poussée.
5. Reconstruire main/contrat/HEAD/findings avant publication/lancement. Aucun
   changement de la santé du tronc n'est inféré de cette préparation.

## Variables indispensables

- Temps Webots entier et dt de chaque contrôle de 209 s de mission à fin du
  LAND/refus ; ordre et temps de chaque transition, request ID, action_start,
  active command, stabilité cumulée, état fail-closed.
- Pointeurs/validités et valeurs GPS, RPY IMU et gyro **effectivement lus**,
  vitesses calculées avec leurs deux positions et leur dt ; conserver aussi
  les non-finis sous une représentation non ambiguë.
- Tous les booléens de la garde fatale, séparément, au **même instant** ;
  raison de refus publiée sans réévaluer des capteurs après coup.
- Avant/après PID : consignes vitesse/altitude, erreurs et historique,
  dérivées, intégrateur vertical, assiette demandée, mixage et valeurs API
  signées après clamps ; zéro et frontière d'ACK/refus horodatés.
- Supervisor à 8 ms : pose/matrice/vitesse, points/identités de contacts
  réellement acquis ; ne pas modifier l'oracle. Forces non mesurées restent
  inconnues. Consignes et rotation effective doivent rester distinguées.
- Programme/AST, monde et assets exacts, versions, sources/binaire,
  événements complets, résultats, stderr/stdout, tous exit codes, manifestes.

## Budget et arrêts

**Un seul processus natif de référence au maximum.** Aucun B, ablation,
ajustement de gain, campagne de seeds ni répétition de succès.
Le cas commence au chargement Webots, y compris un crash avant admission.
Budget mural maximum 600 s pour l'ensemble du cas ; terminer après fin LAND
ou refus puis une fenêtre observée de 3 s simulées, ou sur erreur technique.
La capture doit attester cette fenêtre ; un flux tronqué reste refusé.

Arrêt définitif à la première erreur de préparation, acquisition ou preuve,
au refus natif plus sa fenêtre observée, à la limite murale ou après le cas.
Conserver tout cas commencé. Aucun remplacement d'un crash ou d'une capture
incomplète. Aucun RESET, redécollage ou commande corrective expérimentale.

## Critères d'interprétation

Reproduction utile : ordre exactement à 210 000 ms, refus LAND indépendant
et grande inclinaison/retournement observés, avec télémétrie complète et
entrées d'ordre/altitude/vitesse rapportées. Une autre panne reste une autre
observation, jamais présentée comme reproduction du même mécanisme.

H1/H2/H3 se départagent par les booléens conservés, pas par le libellé générique.
Des conditions simultanées doivent toutes être déclarées. Comparer les RPY
consommés à la matrice avec la phase de rafraîchissement explicitée.
Contact, début de divergence et moteurs sont ordonnés selon leurs acquisitions,
sans inventer une force ou une causalité à partir d'une coïncidence temporelle.

Si la référence ne reproduit pas, **NON CONCLUANT sur la correction** ; aucun
deuxième essai pour chercher un succès ou une panne. Si elle reproduit et
localise une cause intervenable, une intervention unique exigera son propre
protocole nouveau, une référence reproduisante et une évaluation de régression.
Ce protocole n'autorise pas à effectuer cette seconde étape implicitement.

L'environnement présent ne dispose ni de Webots ni de Docker. Les préconditions
de support ci-dessus ne sont pas toutes réalisées par cet ajout. **LANCEMENT
NON EFFECTUÉ** ; aucun résultat natif futur ni correction n'est anticipé.
