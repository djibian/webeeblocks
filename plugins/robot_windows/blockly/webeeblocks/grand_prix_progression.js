(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksGrandPrixProgression = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  const lessons = [
    {
      title: 'Parcourir un circuit',
      mission: 'Suis les trois lignes droites du départ au damier. Tourne aux deux angles et pose le drone entièrement sur le damier, avant le H fermé.',
      blocks: ['webeeblocks_v2_takeoff', 'webeeblocks_v2_move', 'webeeblocks_v2_turn',
        'webeeblocks_v2_speed', 'math_number', 'webeeblocks_v2_land'],
      statements: ['takeoff', 'move', 'turn', 'set_speed', 'land']
    },
    {
      title: 'Franchir un H ouvert',
      mission: 'Franchis le H ouvert sous la traverse, puis pose le drone entièrement sur le damier avant le H fermé.',
      blocks: ['webeeblocks_v2_vertical'],
      statements: ['vertical']
    },
    {
      title: 'Répéter un trajet',
      mission: 'Après le décollage, tourne à gauche pour t’aligner. Traverse les trois H ouverts dans l’ordre, puis pose le drone sur le damier avant le H fermé.',
      blocks: ['controls_repeat_ext'],
      statements: ['repeat']
    },
    {
      title: 'Observer pour adapter le déplacement',
      mission: 'Rejoins le damier situé à gauche avant le H fermé. Ton programme doit y poser le drone sur chacune des trois longueurs de piste.',
      blocks: ['webeeblocks_v2_range', 'math_arithmetic'],
      statements: []
    },
    {
      title: 'Mémoriser le virage',
      mission: 'Suis la piste en passant par son virage en L. Avant le H fermé, pose le drone à droite si le virage était à gauche et à gauche s’il était à droite.',
      blocks: ['logic_compare', 'controls_if', 'variables_set', 'variables_get', 'math_change'],
      statements: ['if', 'set_variable']
    },
    {
      title: 'Discriminer un H ouvert',
      mission: 'Rejoins le damier avant le H fermé. Si la piste comporte un H ouvert, passe dessous. Réutilise le même programme sur les pistes avec et sans H ouvert.',
      blocks: ['logic_operation'],
      statements: []
    },
    {
      title: 'Mini Grand Prix',
      mission: 'Parcours les deux lignes droites et le virage. S’il y a un H ouvert, franchis-le, puis pose le drone sur le damier avant le H fermé. Le même programme doit fonctionner sur les sept pistes.',
      blocks: ['controls_whileUntil', 'procedures_defnoreturn', 'procedures_callnoreturn'],
      statements: ['while', 'call']
    }
  ];

  function profileFor(activity, grandPrix) {
    const lesson = lessons[activity - 1];
    if (!Number.isInteger(activity) || !lesson)
      throw new RangeError('Activité Grand Prix attendue entre 1 et 7');
    if (!grandPrix || grandPrix.id !== 'progression-grand-prix-route-v2')
      throw new TypeError('Profil Grand Prix de référence requis');

    // Select a cumulative subset of the stock blocks, fields and native route
    // limits. The independent native evaluator owns each course and its target.
    const unlocked = lessons.slice(0, activity);
    const toolbox = unlocked.flatMap(stage => stage.blocks);
    const runtime = JSON.parse(JSON.stringify(grandPrix.runtime));
    const moveDirections = activity >= 4 ? runtime.moveDirections : ['forward', 'back'];
    const rangeDirections = activity >= 4 ? runtime.rangeDirections : [];
    const verticalDirections = activity >= 2 ? runtime.verticalDirections : [];
    Object.assign(runtime, {
      allowedStatementKinds: unlocked.flatMap(stage => stage.statements),
      moveDirections, rangeDirections, verticalDirections
    });
    delete runtime.elapsedSimulationTime;

    const fieldOptions = {webeeblocks_v2_move: {DIRECTION: moveDirections}};
    if (activity >= 2) fieldOptions.webeeblocks_v2_vertical = {DIRECTION: verticalDirections};
    if (activity >= 4) fieldOptions.webeeblocks_v2_range = {DIRECTION: rangeDirections};
    if (activity >= 4) fieldOptions.math_arithmetic = {OP: ['ADD', 'MINUS', 'MULTIPLY', 'DIVIDE']};
    if (activity >= 6) fieldOptions.logic_operation = {OP: activity >= 7 ? ['AND', 'OR'] : ['AND']};
    if (activity >= 7) fieldOptions.controls_whileUntil = {MODE: ['WHILE', 'UNTIL']};

    const parameterBounds = JSON.parse(JSON.stringify(grandPrix.parameterBounds));
    if (activity >= 7) {
      parameterBounds.controls_whileUntil = {
        MAX_ITERATIONS: {...runtime.astBounds['while.max_iterations'], step: 1}
      };
    }
    return {
      id: 'progression-grand-prix-a' + activity + '-v1',
      // Stable project identity across hidden variants of the same activity.
      world: 'worlds/grand_prix_progression_a' + activity + '.wbt',
      // The host exposes this lesson's blank editable starter, never A8.
      starterVisible: true,
      brief: {
        visible: true,
        title: activity + ' — ' + lesson.title,
        mission: lesson.mission + ' Reste entre les limites rouges et respecte l’altitude minimale hors des bandes jaunes. Termine en moins de 3 min 30 s.'
      },
      pedagogy: {objective: lesson.title},
      toolbox, parameterBounds, fieldOptions,
      hardware: [...grandPrix.hardware],
      timer: {...grandPrix.timer},
      evaluation: {...grandPrix.evaluation},
      runtime
    };
  }

  return {profileFor};
});
