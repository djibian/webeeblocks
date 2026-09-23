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
    // Live-world backends may need an explicit causal boundary between the end
    // of interpreter execution and the world evaluator's terminal observation.
    // Generic/mock backends that already return a terminal result remain valid.
    if (typeof backend.completeActivityMission === 'function')
      await backend.completeActivityMission(evaluation);
    return classifyMission(await backend.readActivityOutcome(evaluation));
  }

  async function readMissionFailure(profile, backend, error) {
    var evaluation = profile && profile.evaluation;
    if (!error || error.code !== 'UNSAFE_OR_TIMEOUT' || !supportsMissionEvaluation(evaluation) ||
        !backend || !backend.capabilities || backend.capabilities.simulationReset !== true ||
        typeof backend.readActivityOutcome !== 'function')
      return null;

    // Prefer an already-latched exact-attempt/exact-oracle world result. This
    // preserves the collision fast path used by existing evaluators and avoids
    // inventing a completion boundary when the world has already decided.
    try {
      var latched = classifyMission(await backend.readActivityOutcome(evaluation));
      return latched.status === 'not-achieved' ? latched : null;
    } catch (outcomeError) {
      // A shared world may contain another evaluator's terminal marker, or the
      // selected evaluator may deliberately wait for the exact oracle completion
      // before publishing. Only those two non-terminal situations may be
      // finalized here. Stale/malformed evidence still fails closed and preserves
      // the original flight error.
      if (!outcomeError || (outcomeError.code !== 'OUTCOME_UNAVAILABLE' && outcomeError.code !== 'OUTCOME_MISMATCH') ||
          typeof backend.completeActivityMission !== 'function')
        return null;
    }

    try {
      // The broker preserves a valid terminal result for this exact attempt and
      // oracle; otherwise COMPLETE names the selected evaluator. The production
      // WWI backend then performs its bounded OUTCOME_UNAVAILABLE settling poll.
      await backend.completeActivityMission(evaluation);
      var completed = classifyMission(await backend.readActivityOutcome(evaluation));
      return completed.status === 'not-achieved' ? completed : null;
    } catch (completionError) {
      return null;
    }
  }

  return {
    classify: classify,
    isRetryable: isRetryable,
    MISSION_EVALUATION_TYPE: MISSION_EVALUATION_TYPE,
    supportsMissionEvaluation: supportsMissionEvaluation,
    classifyMission: classifyMission,
    evaluateMission: evaluateMission,
    readMissionFailure: readMissionFailure
  };
});
