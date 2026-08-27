(function(root, factory) {
  if (typeof module === 'object' && module.exports)
    module.exports = factory();
  else
    root.WebeeBlocksRuntimeOutcome = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';

  function classify(error) {
    var machineCode = error && typeof error.code === 'string' ? error.code : null;
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

  return {classify: classify};
});
