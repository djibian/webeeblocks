(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksActivities = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  var BLOCK_CATALOG = Object.freeze({
    webeeblocks_takeoff: { category: 'flight' },
    webeeblocks_forward: { category: 'flight' },
    webeeblocks_turn: { category: 'flight' },
    webeeblocks_land: { category: 'flight' },
    webeeblocks_v2_takeoff: { category: 'flight' },
    webeeblocks_v2_land: { category: 'flight' },
    webeeblocks_v2_move: { category: 'flight' },
    webeeblocks_v2_vertical: { category: 'flight' },
    webeeblocks_v2_turn: { category: 'flight' },
    webeeblocks_v2_wait: { category: 'control' },
    webeeblocks_v2_speed: { category: 'flight' },
    webeeblocks_v2_light: { category: 'flight' },
    webeeblocks_v2_range: { category: 'sensor' },
    webeeblocks_v2_elapsed: { category: 'sensor' },
    procedures_defnoreturn: { category: 'procedure' },
    procedures_callnoreturn: { category: 'procedure' },
    controls_if: { category: 'control' },
    controls_repeat_ext: { category: 'control' },
    controls_whileUntil: { category: 'control' },
    webeeblocks_v2_until: { category: 'control' },
    logic_compare: { category: 'operator' },
    logic_operation: { category: 'operator' },
    math_number: { category: 'operator' },
    math_arithmetic: { category: 'operator' },
    variables_set: { category: 'variable' },
    variables_get: { category: 'variable' },
    math_change: { category: 'variable' }
  });
  var DOCUMENT = Object.freeze({
    version: 1,
    activities: [
      {
        id: 'progression-sequence-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '1 — Prendre son envol en 3D',
          mission: 'Depuis la zone bleue, rejoins le damier vert décalé et pose le drone entièrement dessus, immobile. Tu peux régler la hauteur de décollage et les distances de déplacement.'
        },
        pedagogy: { objective: 'Transférer une séquence connue en 2D au vol 3D : repérer deux axes horizontaux, régler une altitude de décollage simple et les distances, sans condition ni boucle.' },
        toolbox: [ 'webeeblocks_v2_takeoff', 'webeeblocks_v2_move', 'webeeblocks_v2_land' ],
        parameterBounds: {},
        fieldOptions: { webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left' ] } },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-sequence-3d-v1' },
        runtime: {
          scene: 'sequence-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'land' ],
          rangeDirections: [  ],
          moveDirections: [ 'forward', 'left' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.4, max: 0.8 },
            'move.distance_m': { min: 0.1, max: 0.5 }
          }
        }
      },
      {
        // New pupil mission ID. Archived .wbb files keep their old ID and oracle.
        id: 'progression-altitude-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '2 — Maîtriser l’altitude',
          mission: 'Depuis la zone bleue sous l’auvent, franchis l’obstacle sans toucher le toit ni les parois, puis pose le drone entièrement sur le damier vert. Tu peux ajuster la hauteur de décollage, les distances et la vitesse.'
        },
        pedagogy: {
          objective: 'Découvrir le déplacement vertical relatif pendant le vol : quitter le départ à basse altitude puis monter pour franchir un obstacle. Le verdict dépend du vol réel simulé, non de la forme du programme.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff', 'webeeblocks_v2_move',
          'webeeblocks_v2_vertical', 'webeeblocks_v2_speed', 'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_speed: { SPEED: { min: 0.1, max: 0.25, step: 0.01 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward' ] },
          webeeblocks_v2_vertical: { DIRECTION: [ 'up' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-altitude-3d-v1' },
        runtime: {
          scene: 'altitude-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'vertical', 'set_speed', 'land' ],
          rangeDirections: [],
          moveDirections: [ 'forward' ],
          verticalDirections: [ 'up' ],
          astBounds: {
            'takeoff.height_m': { min: 0.4, max: 0.8 },
            'move.distance_m': { min: 0.1, max: 1.2 },
            'vertical.distance_m': { min: 0.1, max: 0.8 },
            'set_speed.speed_m_s': { min: 0.1, max: 0.25 }
          }
        }
      },
      {
        // Historical Activity 2 remains loadable with Open but not Start.
        starterVisible: false,
        id: 'progression-precise-movement-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '2 — Livrer le colis fragile',
          mission: 'Un colis fragile doit être déposé sur la petite zone de livraison située à gauche du couloir. Fais terminer le drone posé et immobile entièrement dans cette zone, sans toucher l’obstacle rouge.'
        },
        pedagogy: {
          objective: 'Choisir et ajuster les paramètres de déplacement pour obtenir un déplacement précis en réutilisant une séquence ordonnée.'
        },
        toolbox: [ 'webeeblocks_v2_takeoff', 'webeeblocks_v2_move', 'webeeblocks_v2_land' ],
        parameterBounds: {},
        fieldOptions: { webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left' ] } },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-precise-movement-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'land' ],
          rangeDirections: [  ],
          moveDirections: [ 'forward', 'left' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 0.5 },
            'move.distance_m': { min: 0.1, max: 0.6 }
          }
        }
      },
      {
        // Native A3 scene and oracle are already attested independently.
        // Leave the student starter empty: no example algorithm or secret state.
        id: 'progression-orientation-3d-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '3 — S’orienter et organiser son trajet',
          mission: 'Parcours les balises A, B et C dans l’ordre, en respectant le cap indiqué et les hauteurs du circuit, puis pose le drone entièrement et immobile sur le damier.'
        },
        pedagogy: {
          objective: 'Comprendre la rotation relative et les déplacements dans le repère local, puis identifier un motif de trajet utile à répéter.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff', 'webeeblocks_v2_speed',
          'webeeblocks_v2_move', 'webeeblocks_v2_turn',
          'webeeblocks_v2_vertical', 'controls_repeat_ext',
          'math_number', 'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_speed: { SPEED: { min: 0.10, max: 0.16, step: 0.01 } },
          webeeblocks_v2_turn: { ANGLE: { min: 90, max: 90, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward' ] },
          webeeblocks_v2_turn: { DIRECTION: [ 'left', 'right' ] },
          webeeblocks_v2_vertical: { DIRECTION: [ 'up', 'down' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-orientation-3d-v1' },
        runtime: {
          scene: 'orientation-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'set_speed', 'move', 'turn', 'vertical', 'repeat', 'land' ],
          rangeDirections: [  ],
          moveDirections: [ 'forward' ],
          verticalDirections: [ 'up', 'down' ],
          astBounds: {
            'takeoff.height_m': { min: 0.60, max: 0.66 },
            'move.distance_m': { min: 0.20, max: 0.50 },
            'vertical.distance_m': { min: 0.10, max: 0.20 },
            'turn.angle_deg_abs': { min: 90, max: 90 },
            'repeat.count': { min: 1, max: 3 },
            'set_speed.speed_m_s': { min: 0.10, max: 0.16 }
          }
        }
      },
      {
        // Historical Activity 3 must remain reopenable, never displayed as #3.
        starterVisible: false,
        id: 'progression-repeat-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '3 — Inspecter trois balises',
          mission: 'Trois balises identiques doivent être inspectées avant le retour de l’équipe. Fais passer le drone dans les trois zones d’inspection, dans l’ordre, puis termine posé dans la zone d’arrivée, sans toucher l’obstacle rouge.'
        },
        pedagogy: {
          objective: 'Identifier un motif identique de déplacements paramétrés et l’exprimer avec une répétition en réutilisant les acquis des activités 1 et 2.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'controls_repeat_ext',
          'math_number',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: 1, max: 10, step: 1 } }
        },
        fieldOptions: { webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left' ] } },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-repeat-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'repeat', 'land' ],
          rangeDirections: [  ],
          moveDirections: [ 'forward', 'left' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 0.5 },
            'move.distance_m': { min: 0.1, max: 0.6 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        // New classroom Activity 4; native A/B variants share this pupil ID.
        // The teacher's scene selection is session-only and never stored in .wbb.
        id: 'progression-decision-h-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '4 — Observer pour décider',
          mission: 'Deux parcours présentent des obstacles différents. Depuis la zone bleue, rejoins le damier vert en franchissant le passage sans collision puis pose le drone immobile. Ton même programme doit réussir sur les deux parcours.'
        },
        pedagogy: {
          objective: 'Mesurer une distance réelle, comparer une valeur à un seuil et prendre une décision SI/SINON pendant le vol, en réutilisant les mouvements et orientations précédents.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff', 'webeeblocks_v2_speed',
          'webeeblocks_v2_move', 'webeeblocks_v2_vertical',
          'webeeblocks_v2_turn', 'controls_repeat_ext',
          'webeeblocks_v2_range', 'controls_if', 'logic_compare',
          'math_number', 'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_speed: { SPEED: { min: 0.1, max: 0.1, step: 0.1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward' ] },
          webeeblocks_v2_vertical: { DIRECTION: [ 'up', 'down' ] },
          webeeblocks_v2_turn: { DIRECTION: [ 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-decision-h-v1' },
        runtime: {
          scene: 'decision-h-a-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'set_speed', 'move', 'vertical', 'turn', 'repeat', 'if', 'land' ],
          rangeDirections: [ 'front' ],
          moveDirections: [ 'forward' ],
          verticalDirections: [ 'up', 'down' ],
          astBounds: {
            'takeoff.height_m': { min: 0.50, max: 0.50 },
            'move.distance_m': { min: 0.1, max: 0.8 },
            'vertical.distance_m': { min: 0.1, max: 0.35 },
            'turn.angle_deg_abs': { min: 90, max: 90 },
            'repeat.count': { min: 1, max: 3 },
            'set_speed.speed_m_s': { min: 0.1, max: 0.1 }
          }
        }
      },
      {
        // Historical Activity 4 is still openable by ID but no longer in Start.
        starterVisible: false,
        id: 'progression-simple-decision-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '4 — Franchir une porte mobile',
          mission: 'Une porte mobile protège l’accès à la zone de livraison. Après la zone bleue de contrôle, deux passages sont balisés et la porte en ferme un au départ. Fais franchir au drone le passage resté ouvert puis rejoindre la zone d’arrivée et terminer posé, sans toucher la porte ni les obstacles, quelle que soit la position de la porte.'
        },
        pedagogy: {
          objective: 'Mesurer la distance devant le drone au point de décision, la comparer à un seuil et choisir un itinéraire avec une condition simple en réutilisant les paramètres de déplacement.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'webeeblocks_v2_range',
          'controls_if',
          'logic_compare',
          'math_number',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: 1, max: 2, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-simple-decision-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'if', 'land' ],
          rangeDirections: [ 'front' ],
          moveDirections: [ 'forward', 'left' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 1.2 }
          }
        }
      },
      {
        id: 'progression-reactive-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '5 — Traverser les rangées',
          mission: 'Le drone doit traverser plusieurs rangées de l’entrepôt pour rejoindre la zone de livraison. Des colis peuvent bloquer certaines rangées. Fais-le avancer jusqu’à la zone d’arrivée et terminer posé sans toucher de colis, même si les blocages ne sont pas les mêmes d’une rangée à l’autre.'
        },
        pedagogy: {
          objective: 'Répéter un cycle de mesure, décision et déplacement afin de réobserver la situation avant chaque rangée, en réutilisant les acquis des activités précédentes.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'controls_repeat_ext',
          'math_number',
          'webeeblocks_v2_range',
          'controls_if',
          'logic_compare',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: 1, max: 10, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-reactive-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'repeat', 'if', 'land' ],
          rangeDirections: [ 'front' ],
          moveDirections: [ 'forward', 'left' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 1.2 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        id: 'progression-combined-decisions-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '6 — Choisir une sortie sûre au carrefour',
          mission: 'À chaque carrefour de l’entrepôt, plusieurs passages peuvent être libres ou occupés. Fais rejoindre au drone la zone de sortie puis termine posé, sans entrer dans un passage bloqué ni toucher un obstacle.'
        },
        pedagogy: {
          objective: 'Acquérir plusieurs distances directionnelles et combiner des comparaisons et conditions afin que le déplacement choisi dépende de plusieurs observations de l’environnement.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'controls_repeat_ext',
          'math_number',
          'webeeblocks_v2_range',
          'controls_if',
          'logic_compare',
          'logic_operation',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: 1, max: 10, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front', 'left', 'right' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-combined-decisions-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'repeat', 'if', 'land' ],
          rangeDirections: [ 'front', 'left', 'right' ],
          moveDirections: [ 'forward', 'left', 'right' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 1.2 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        // A6 draft contract is intentionally NOT selectable by pupils until
        // genuine Webots scene switching, native observer and learner Save/Open
        // have independent evidence. Never distribute the private CI solution.
        starterVisible: false,
        id: 'progression-count-h-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '6 — Compter pour choisir',
          mission: 'Sur la ligne droite, franchis les H ouverts dans l’ordre, compte ceux réellement franchis puis pose entièrement le drone sur la bonne zone parmi trois. Réussis les trois parcours sans modifier ton projet.'
        },
        pedagogy: {
          objective: 'Réemployer mesures, boucle, condition et variable pour retenir le nombre de franchissements et choisir une destination.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff', 'webeeblocks_v2_speed',
          'webeeblocks_v2_move', 'webeeblocks_v2_range',
          'controls_whileUntil', 'controls_if', 'logic_compare',
          'logic_operation', 'math_number', 'math_arithmetic',
          'variables_set', 'variables_get', 'math_change', 'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_speed: { SPEED: { min: 0.2, max: 0.2, step: 0.1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front', 'up' ] },
          math_arithmetic: { OP: [ 'ADD', 'MINUS' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-count-h-v1' },
        runtime: {
          scene: 'count-h-1-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'set_speed', 'move',
            'while', 'if', 'set_variable', 'land' ],
          rangeDirections: [ 'front', 'up' ],
          moveDirections: [ 'forward', 'left', 'right' ],
          verticalDirections: [],
          maxSteps: 20000,
          astBounds: {
            'takeoff.height_m': { min: 0.40, max: 0.40 },
            'move.distance_m': { min: 0.01, max: 0.70 },
            'move.forward.distance_m': { min: 0.01, max: 0.70 },
            'move.lateral.distance_m': { min: 0.01, max: 0.60 },
            'while.max_iterations': { min: 1, max: 80 },
            'set_speed.speed_m_s': { min: 0.20, max: 0.20 }
          }
        }
      },
      {
        // Public A7, distinct from the historical memory exercise; one unchanged
        // pupil project is used in both strictly native-attested L/R worlds.
        id: 'progression-mini-grand-prix-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '7 — Mini Grand Prix',
          mission: 'Depuis la zone bleue, franchis le H ouvert sans contact, négocie le virage à angle droit puis pose entièrement le drone sur le damier avant le H fermé. Fais réussir les parcours gauche et droite avec un seul programme enregistré, sans le modifier.'
        },
        pedagogy: {
          objective: 'Réinvestir déplacements 3D, rotations, observations, conditions, boucles et mémoire dans une mission autonome sans fournir l’algorithme solution.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff', 'webeeblocks_v2_speed',
          'webeeblocks_v2_vertical', 'webeeblocks_v2_move',
          'webeeblocks_v2_turn', 'webeeblocks_v2_range',
          'controls_repeat_ext', 'controls_if', 'logic_compare',
          'logic_operation', 'math_number', 'math_arithmetic',
          'variables_set', 'variables_get', 'math_change',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_speed: { SPEED: { min: 0.1, max: 0.1, step: 0.1 } }
        },
        fieldOptions: {
          webeeblocks_v2_vertical: { DIRECTION: [ 'up', 'down' ] },
          webeeblocks_v2_move: { DIRECTION: [ 'forward' ] },
          webeeblocks_v2_turn: { DIRECTION: [ 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front', 'left', 'right' ] },
          math_arithmetic: { OP: [ 'ADD', 'MINUS', 'MULTIPLY', 'DIVIDE' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-mini-grand-prix-v1' },
        runtime: {
          scene: 'mini-grand-prix-l-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'set_speed', 'vertical',
            'move', 'turn', 'repeat', 'if', 'set_variable', 'land' ],
          rangeDirections: [ 'front', 'left', 'right' ],
          moveDirections: [ 'forward' ],
          verticalDirections: [ 'up', 'down' ],
          astBounds: {
            'takeoff.height_m': { min: 0.50, max: 0.50 },
            'move.distance_m': { min: 0.15, max: 0.80 },
            'vertical.distance_m': { min: 0.10, max: 0.35 },
            'set_speed.speed_m_s': { min: 0.1, max: 0.1 },
            'turn.angle_deg_abs': { min: 90, max: 90 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        // Historical A7 remains loadable, but not in the student's Start menu.
        starterVisible: false,
        id: 'progression-memory-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '7 — Acheminer le colis selon son gabarit',
          mission: 'Au quai de départ, le drone peut mesurer le gabarit du colis grâce au panneau de référence placé devant lui. Une fois parti, ce panneau ne sera plus visible. Plus loin, deux zones de tri doivent être franchies en choisissant à chaque fois le passage adapté au colis, puis le drone doit terminer posé dans la bonne zone de livraison.',
          cue: 'Une variable sera utile pour mémoriser la mesure faite au quai de départ.'
        },
        pedagogy: {
          objective: 'Capturer une mesure à un instant identifiable, la mémoriser puis réutiliser la valeur mémorisée dans au moins deux décisions ultérieures lorsque l’information d’origine n’est plus directement observable.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'controls_repeat_ext',
          'math_number',
          'math_arithmetic',
          'webeeblocks_v2_range',
          'controls_if',
          'logic_compare',
          'logic_operation',
          'variables_set',
          'variables_get',
          'math_change',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: -10, max: 10, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front', 'left', 'right' ] },
          math_arithmetic: { OP: [ 'ADD', 'MINUS', 'MULTIPLY', 'DIVIDE' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-memory-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'repeat', 'if', 'set_variable', 'land' ],
          rangeDirections: [ 'front', 'left', 'right' ],
          moveDirections: [ 'forward', 'left', 'right' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 1.2 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        id: 'progression-autonomous-strategy-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: '8 — Assurer une livraison autonome complète',
          mission: 'Prends en charge le colis au quai de départ, puis fais rejoindre au drone la bonne zone de livraison en autonomie. Le trajet peut comporter des passages occupés et plusieurs choix de route. Les informations disponibles au départ et pendant le trajet doivent lui permettre de choisir une stratégie adaptée. Termine posé dans la zone correspondant au colis, sans toucher d’obstacle.'
        },
        pedagogy: {
          objective: 'Concevoir, tester et affiner une stratégie autonome en sélectionnant et combinant les mécanismes acquis dans les activités précédentes selon leur utilité.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'controls_repeat_ext',
          'math_number',
          'math_arithmetic',
          'webeeblocks_v2_range',
          'controls_if',
          'logic_compare',
          'logic_operation',
          'variables_set',
          'variables_get',
          'math_change',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {

          math_number: { NUM: { min: -10, max: 10, step: 1 } }
        },
        fieldOptions: {
          webeeblocks_v2_move: { DIRECTION: [ 'forward', 'left', 'right' ] },
          webeeblocks_v2_range: { DIRECTION: [ 'front', 'left', 'right' ] },
          math_arithmetic: { OP: [ 'ADD', 'MINUS', 'MULTIPLY', 'DIVIDE' ] }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'mission-state-v1', oracle: 'progression-autonomous-strategy-v1' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'repeat', 'if', 'set_variable', 'land' ],
          rangeDirections: [ 'front', 'left', 'right' ],
          moveDirections: [ 'forward', 'left', 'right' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 0.5, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 1.2 },
            'repeat.count': { min: 1, max: 10 }
          }
        }
      },
      {
        id: 'obstacle-time-trial-v1',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: 'Défi Crazyflie — contre-la-montre',
          goal: 'Franchis les deux portes dans l’ordre, évite l’obstacle puis atterris. Quand ton parcours réussit, améliore ton temps.'
        },
        toolbox: [
          'webeeblocks_takeoff',
          'webeeblocks_forward',
          'webeeblocks_turn',
          'webeeblocks_land'
        ],
        parameterBounds: {
          webeeblocks_forward: { DISTANCE: { min: 0.1, max: 2.0, step: 0.1 } },
          webeeblocks_turn: { ANGLE: { min: -90, max: 135, step: 1 } }
        },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2' ],
        timer: { enabled: true },
        evaluation: { type: 'ordered-gates-no-collision' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'mission-v1',
          allowedStatementKinds: [ 'takeoff', 'move', 'turn', 'land' ],
          rangeDirections: [  ],
          moveDirections: [ 'forward' ],
          verticalDirections: [  ],
          astBounds: {
            'takeoff.height_m': { min: 1.0, max: 1.0 },
            'move.distance_m': { min: 0.1, max: 2.0 },
            'turn.angle_deg_abs': { min: 1, max: 135 }
          }
        }
      },
      {
        id: 'reactive-obstacle-v2',
        world: 'worlds/crazyflie_runtime_obstacle.wbt',
        brief: {
          visible: true,
          title: 'Crazyflie — comportement réactif',
          goal: 'Observe les distances pendant le vol et décide du déplacement à exécuter.'
        },
        toolbox: [
          'webeeblocks_v2_takeoff',
          'webeeblocks_v2_move',
          'webeeblocks_v2_vertical',
          'webeeblocks_v2_turn',
          'webeeblocks_v2_wait',
          'webeeblocks_v2_speed',
          'webeeblocks_v2_light',
          'webeeblocks_v2_range',
          'controls_if',
          'controls_repeat_ext',
          'logic_compare',
          'logic_operation',
          'math_number',
          'math_arithmetic',
          'variables_set',
          'variables_get',
          'math_change',
          'webeeblocks_v2_land'
        ],
        parameterBounds: {
          webeeblocks_v2_turn: { ANGLE: { min: 1, max: 179, step: 1 } },
          webeeblocks_v2_wait: { SECONDS: { min: 0.1, max: 5.0, step: 0.1 } },
          webeeblocks_v2_speed: { SPEED: { min: 0.1, max: 0.35, step: 0.05 } }
        },
        fieldOptions: { math_arithmetic: { OP: [ 'ADD', 'MINUS', 'MULTIPLY', 'DIVIDE' ] } },
        hardware: [ 'crazyflie-2.1', 'flow-deck-v2', 'multi-ranger-deck', 'color-led-deck' ],
        timer: { enabled: false },
        evaluation: { type: 'reactive-runtime' },
        runtime: {
          scene: 'legacy-v1',
          mode: 'ast-v1',
          allowedStatementKinds: [
            'takeoff',
            'move',
            'vertical',
            'turn',
            'wait',
            'set_speed',
            'set_light',
            'if',
            'repeat',
            'set_variable',
            'land'
          ],
          rangeDirections: [ 'front', 'back', 'left', 'right', 'up' ],
          moveDirections: [ 'forward', 'back', 'left', 'right' ],
          verticalDirections: [ 'up', 'down' ],
          astBounds: {
            'takeoff.height_m': { min: 0.2, max: 1.5 },
            'move.distance_m': { min: 0.1, max: 2.0 },
            'vertical.distance_m': { min: 0.1, max: 0.8 },
            'turn.angle_deg_abs': { min: 1, max: 179 },
            'wait.seconds': { min: 0.1, max: 5.0 },
            'set_speed.speed_m_s': { min: 0.1, max: 0.35 },
            'repeat.count': { min: 1, max: 20 }
          }
        }
      }
    ]
  });
  function getProfile(id) { var matches = DOCUMENT.activities.filter(function(profile) { return profile.id === id; }); if (matches.length !== 1) throw new Error('unknown activity: ' + id); return JSON.parse(JSON.stringify(matches[0])); }
  return {BLOCK_CATALOG:BLOCK_CATALOG,DOCUMENT:DOCUMENT,getProfile:getProfile};
});
