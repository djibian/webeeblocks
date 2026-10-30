// Recovery-only renewal of the *existing* Webots Robot Window document.
// No browser spawning, privileged IPC, CDP, port, profile manipulation or daemon.
// Every new incarnation still requires the independent native recovery witness,
// two strict RESETs and two scene attestations before it enables Run.
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory;
  else root.WebeeBlocksWindowRenewal = factory(root);
})(typeof window !== 'undefined' ? window : this, function(root) {
  'use strict';
  var armed = null;
  var started = false;
  var attempted = false;
  var navigation = false;
  var timeout = null;
  var MAX_CHECKS = 24; // At most 12 seconds of HTTP read-only probes.
  var intervalMs = 500;

  function validCheckpoint(token) {
    if (!/^[0-9a-f]{64}$/.test(token || '')) return false;
    try {
      var raw = root.localStorage.getItem('webeeblocks-world-recovery-v1');
      if (!raw) return false;
      var checkpoint = JSON.parse(raw);
      return checkpoint.version === 2 && checkpoint.token === token;
    } catch (_) { return false; }
  }

  // Never navigate an external URL; the only target is our own current document.
  function validUrl() {
    var location = root.location;
    return /^(https?:)$/.test(location.protocol) &&
      /\/robot_windows\/[^/]+\/[^/]+\.html$/.test(location.pathname) &&
      location.hostname === 'localhost';
  }

  function disarm() {
    if (timeout !== null) root.clearTimeout(timeout);
    timeout = null;
    armed = null;
    started = false;
    attempted = false;
  }

  async function renew() {
    if (started || attempted || navigation || !armed) return;
    started = true;
    attempted = true;
    var token = armed;
    for (var check = 0; check < MAX_CHECKS; ++check) {
      if (token !== armed || !validCheckpoint(token) || !validUrl()) break;
      try {
        // HTTP availability merely permits an attempt to create a document.
        // It is NEVER interpreted as Webots READY, scene/RESET or flight authority.
        var controller = new root.AbortController();
        var watchdog = root.setTimeout(function() { controller.abort(); }, 1200);
        var response;
        try {
          response = await root.fetch(root.location.href, {
            method: 'GET', cache: 'no-store', credentials: 'same-origin',
            redirect: 'error', signal: controller.signal
          });
        } finally { root.clearTimeout(watchdog); }
        if (response.ok && (response.headers.get('content-type') || '').toLowerCase().includes('text/html')) {
          navigation = true;
          if (typeof root.dispatchEvent === 'function' && typeof root.CustomEvent === 'function')
            root.dispatchEvent(new root.CustomEvent('webeeblocks-window-renewal', {
              detail: {phase: 'same-document-navigation'}
            }));
          root.location.reload(); // *same browser tab, same origin and profile*
          return;
        }
      } catch (_) {
        // The world may be between incarnations. Keep Run disabled.
      }
      await new Promise(function(resolve) { root.setTimeout(resolve, intervalMs); });
    }
    // Never clear the checkpoint or native witness on failure.
    // The old UI is already locked by rebuildSimulation().
    started = false;
    if (root.document) {
      var detail = root.document.getElementById('runtimeDetail');
      if (detail) detail.textContent =
        'Réouverture impossible : programme conservé, vol interdit. Redémarrez Webots pour rétablir la connexion.';
    }
  }

  return Object.freeze({
    arm: function(token) {
      if (armed || started || attempted || navigation || !validUrl() || !validCheckpoint(token))
        return false;
      armed = token;
      return true;
    },
    begin: function() {
      if (!armed) return false;
      // This is a fail-safe fallback if Webots does not close its WWI socket.
      // It triggers *navigation only*; it can never attest successful recovery.
      timeout = root.setTimeout(renew, 5000);
      return true;
    },
    onTransportClose: function() {
      if (!armed || !validCheckpoint(armed)) return false;
      if (timeout !== null) root.clearTimeout(timeout);
      timeout = null;
      renew();
      return true; // Do NOT close the browser tab during this world reload.
    },
    disarm: disarm
  });
});
