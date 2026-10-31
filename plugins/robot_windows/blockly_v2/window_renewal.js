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
  // Webots R2025a native recovery is typically 15–23 s with the injected
  // 7 s Chrome stall. This 30 s deadline bounds the entire HTTP probe phase,
  // including slow/hung HTTP responses and polling intervals, not merely sleeps.
  var RENEW_DEADLINE_MS = 30000;
  var HTTP_REQUEST_MAX_MS = 1200;
  var POLL_MS = 500;
  var LOCK_WAIT_MAX_MS = 10000;
  var activeController = null;

  function now() {
    // Monotonic clock: wall-clock corrections cannot prolong the deadline.
    return root.performance.now();
  }

  function validCheckpoint(token) {
    if (!/^[0-9a-f]{64}$/.test(token || '')) return false;
    try {
      var raw = root.localStorage.getItem('webeeblocks-world-recovery-v1');
      if (!raw) return false;
      var checkpoint = JSON.parse(raw);
      return checkpoint.version === 3 && checkpoint.token === token;
    } catch (_) { return false; }
  }

  // Never navigate an external URL; the only target is our own current document.
  function validUrl() {
    var location = root.location;
    return /^(https?:)$/.test(location.protocol) &&
      /^\/robot_windows\/(blockly_v2(?:_[0-9a-f]{16})?)\/\1\.html$/.test(location.pathname) &&
      location.hostname === 'localhost';
  }

  function disarm() {
    if (timeout !== null) root.clearTimeout(timeout);
    timeout = null;
    armed = null;
    // An invalidated generation cannot navigate after an already in-flight
    // fetch resolves, even if the browser ignores AbortSignal cancellation.
    if (activeController) activeController.abort();
  }

  async function probeHtml(url, remaining) {
    var controller = new root.AbortController();
    var watchdog = null;
    activeController = controller;
    try {
      // Race the fetch against a real timer. AbortSignal alone does not
      // guarantee settlement when a transport/browser ignores cancellation.
      var result = await Promise.race([
        root.fetch(url, {
          method: 'GET', cache: 'no-store', credentials: 'same-origin',
          redirect: 'error', signal: controller.signal
        }).then(function(response) { return {response: response}; },
                function() { return {error: true}; }),
        new Promise(function(resolve) {
          watchdog = root.setTimeout(function() {
            controller.abort();
            resolve({expired: true});
          }, Math.min(HTTP_REQUEST_MAX_MS, remaining));
        })
      ]);
      return result.response &&
        result.response.ok &&
        (result.response.headers.get('content-type') || '').toLowerCase().includes('text/html');
    } catch (_) {
      return false;
    } finally {
      if (watchdog !== null) root.clearTimeout(watchdog);
      if (activeController === controller) activeController = null;
      controller.abort();
    }
  }

  async function renew() {
    if (started || attempted || navigation || !armed) return;
    started = true;
    attempted = true;
    var token = armed;
    var deadline = now() + RENEW_DEADLINE_MS;
    while (now() < deadline && token === armed && validCheckpoint(token) && validUrl()) {
      var url = root.location.href;
      var html = await probeHtml(url, deadline - now());
      // Validation AFTER every await is indispensable: the user may close the
      // session or the checkpoint may be altered while HTTP is still pending.
      if (token !== armed || !validCheckpoint(token) || !validUrl()) break;
      if (now() >= deadline) break;
      if (html) {
        navigation = true;
        if (typeof root.dispatchEvent === 'function' && typeof root.CustomEvent === 'function')
          root.dispatchEvent(new root.CustomEvent('webeeblocks-window-renewal', {
            detail: {phase: 'same-document-navigation'}
          }));
        root.location.reload(); // Same browser tab, origin and profile.
        return;
      }
      var remaining = deadline - now();
      if (remaining <= 0) break;
      await new Promise(function(resolve) {
        root.setTimeout(resolve, Math.min(POLL_MS, remaining));
      });
    }
    // Failure must NOT clear localStorage, the native witness or unlock Run.
    started = false;
    if (root.document && token === armed) {
      var detail = root.document.getElementById('runtimeDetail');
      if (detail) detail.textContent =
        'Réouverture impossible après 30 secondes : programme conservé, vol interdit. Redémarrez Webots pour rétablir la connexion.';
    }
  }

  // Bound ONLY lock acquisition, NOT the physical operation after acquisition.
  // Abort a queued request after 10 s, then reject independently of whether
  // the browser correctly settles an aborted navigator.locks.request promise.
  // A late grant is checked before touching the native controller.
  async function withRecoveryLock(authorize) {
    if (!root.navigator || !root.navigator.locks ||
        typeof root.navigator.locks.request !== 'function')
      throw new Error('Verrou de reprise partagé indisponible — vol interdit');
    var controller = new root.AbortController();
    var acquiring = true;
    var expired = false;
    var lockDeadline = now() + LOCK_WAIT_MAX_MS;
    var lockTimer = null;
    var expiry = new Promise(function(_, reject) {
      lockTimer = root.setTimeout(function() {
        if (!acquiring) return;
        expired = true;
        controller.abort();
        reject(new Error('Attente du verrou de reprise expirée après 10 secondes — vol interdit'));
      }, LOCK_WAIT_MAX_MS);
    });
    var request;
    try {
      request = root.navigator.locks.request('webeeblocks-recovery-v1',
        {mode: 'exclusive', signal: controller.signal},
        async function() {
          // A suspended tab may run an already-queued lock callback BEFORE
          // its overdue timer task. Reject on monotonic deadline as well.
          if (expired || controller.signal.aborted || now() >= lockDeadline) {
            expired = true;
            controller.abort();
            throw new Error('Verrou de reprise accordé après expiration — vol interdit');
          }
          acquiring = false;
          if (lockTimer !== null) root.clearTimeout(lockTimer);
          lockTimer = null;
          // Once acquired, neither the timeout nor AbortSignal interrupts
          // ongoing strict RESET and independent SCENE attestations.
          return await authorize();
        });
    } catch (error) {
      if (lockTimer !== null) root.clearTimeout(lockTimer);
      throw error;
    }
    try {
      return await Promise.race([request, expiry]);
    } finally {
      if (lockTimer !== null) root.clearTimeout(lockTimer);
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
    disarm: disarm,
    withRecoveryLock: withRecoveryLock
  });
});
