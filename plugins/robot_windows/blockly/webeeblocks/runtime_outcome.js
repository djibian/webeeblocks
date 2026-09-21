(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksRuntimeOutcome = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  var MISSION_EVALUATION_TYPE = 'mission-state-v1';
  var MISSION_STATES = Object.freeze({
    achieved: Object.freeze({state: 'MISSION RÉUSSIE', detail: 'Mission accomplie'}),
    'not-achieved': Object.freeze({state: 'MISSION NON RÉUSSIE', detail: 'Mission non accomplie'}),
    interrupted: Object.freeze({state: 'MISSION INTERROMPUE', detail: 'Mission interrompue'})
  });

  function isRetryable(error) {
    return !!(error && error.code === 'PROGRAM_INVALID');
  }

  function classify(error) {
    var machineCode = error && typeof error.code === 'string' ? error.code : null;
    if (machineCode === 'PROGRAM_INVALID') {
      return {
        state: 'À CORRIGER',
        detail: error && typeof error.studentDetail === 'string' && error.studentDetail ? error.studentDetail : 'Le programme doit être corrigé avant de lancer.',
        machineCode: machineCode
      };
    }
    if (machineCode === 'USER_STOPPED') {
      return {
        state: 'ARRÊTÉ',
        detail: 'Vol arrêté — réinitialisez la simulation avant de relancer',
        machineCode: machineCode
      };
    }
    if (machineCode === 'UNSAFE_OR_TIMEOUT') {
      return {
        state: 'ARRÊTÉ',
        detail: 'L’action n’a pas pu être terminée',
        machineCode: machineCode
      };
    }
    return {
      state: 'ERREUR',
      detail: 'Une erreur technique a interrompu l’exécution',
      machineCode: machineCode
    };
  }

  function supportsMissionEvaluation(evaluation) {
    return !!(evaluation && evaluation.type === MISSION_EVALUATION_TYPE);
  }

  function classifyMission(raw) {
    var status = typeof raw === 'string' ? raw : raw && raw.status;
    var presentation = MISSION_STATES[status];
    if (!presentation)
      throw new Error('runtime outcome: invalid mission state: ' + String(status));
    return {status: status, state: presentation.state, detail: presentation.detail};
  }

  async function evaluateMission(profile, backend) {
    var evaluation = profile && profile.evaluation;
    if (!supportsMissionEvaluation(evaluation))
      return null;
    if (!backend || typeof backend.readActivityOutcome !== 'function')
      throw new Error('runtime outcome: backend mission outcome capability unavailable');
    return classifyMission(await backend.readActivityOutcome(evaluation));
  }

  return {
    classify: classify,
    isRetryable: isRetryable,
    MISSION_EVALUATION_TYPE: MISSION_EVALUATION_TYPE,
    supportsMissionEvaluation: supportsMissionEvaluation,
    classifyMission: classifyMission,
    evaluateMission: evaluateMission
  };
});
