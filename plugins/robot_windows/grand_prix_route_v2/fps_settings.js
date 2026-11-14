/* Grand Prix-only native render FPS control. Only route firmware may write WorldInfo.FPS. */
(function () {
  'use strict';
  var PREFIX = 'GP_ROUTE_FPS_V1 ';
  var current = 20;
  var state = 'INITIALISATION';
  var pending = null;
  var uncertain = true; // Until a native GET confirms the actual WorldInfo.FPS.
  var nextTimeout = null;
  var mounted = false;
  var toggle, panel, slider, value, status, container;

  function locked() {
    return state !== 'PRÊT' ||
      !window.runtimeBackend || window.runtimeBackend.ready !== true ||
      window.runtimeRunning === true || window.runtimeOutcomePending === true ||
      window.runtimeResetPending === true || window.runtimeStopPending === true ||
      window.runtimeScenePending === true || window.runtimeProjectPending === true ||
      window.runtimeTerminal === true || !!pending || uncertain;
  }
  function update() {
    if (!mounted) return;
    var disabled = locked();
    slider.disabled = disabled;
    container.dataset.locked = disabled ? 'true' : 'false';
    value.textContent = slider.value + ' FPS';
    if (disabled && (state === 'EXÉCUTION' || window.runtimeRunning === true))
      status.textContent = 'Réglage verrouillé pendant le vol.';
    else if (disabled && (state === 'TERMINÉ' || state === 'ERREUR' || window.runtimeTerminal === true))
      status.textContent = 'Réinitialisez le vol pour modifier le rendu.';
    else if (disabled && !pending)
      status.textContent = 'Réglage disponible lorsque la simulation est PRÊTE.';
  }
  function nonce() {
    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') return null;
    var raw = new Uint8Array(16);
    window.crypto.getRandomValues(raw);
    return Array.from(raw, function (n) { return n.toString(16).padStart(2, '0'); }).join('');
  }
  function clearPending() {
    if (nextTimeout !== null) window.clearTimeout(nextTimeout);
    nextTimeout = null;
    pending = null;
  }
  function send(kind, requested) {
    if (!mounted || pending || !window.runtimeBackend || !window.runtimeBackend.ready ||
        !window.runtimeBackend.robotWindow ||
        typeof window.runtimeBackend.robotWindow.send !== 'function') return false;
    if (kind === 'SET' && (locked() || !Number.isInteger(requested) || requested < 1 || requested > 60))
      return false;
    var token = nonce();
    if (!token) {
      status.textContent = 'Connexion sécurisée indisponible.';
      return false;
    }
    pending = {kind: kind, value: requested, nonce: token};
    slider.disabled = true;
    status.textContent = kind === 'SET' ? 'Application du réglage…' : 'Lecture des FPS natifs…';
    var payload = kind === 'GET' ? PREFIX + 'GET nonce=' + token :
      PREFIX + 'SET fps=' + requested + ' nonce=' + token;
    nextTimeout = window.setTimeout(function () {
      if (!pending || pending.nonce !== token) return;
      var failedKind = pending.kind;
      clearPending();
      uncertain = true; // UNKNOWN is not a failed/rolled-back native SET.
      slider.value = String(current);
      if (failedKind === 'SET' && state === 'PRÊT' &&
          window.runtimeBackend && window.runtimeBackend.ready)
        send('GET', null); // Read-only reconciliation, never retry the SET.
      else
        status.textContent = 'Lecture native indisponible ; réglage verrouillé.';
      update();
    }, 12000);
    window.runtimeBackend.robotWindow.send(payload);
    return true;
  }
  function receive(event) {
    if (!mounted || !pending) return;
    var raw = event && event.detail && event.detail.raw;
    var match = typeof raw === 'string'
      ? /^GP_ROUTE_FPS_V1 (APPLIED|CURRENT|REFUSED) nonce=([0-9a-f]{32}) (fps=([1-9]|[1-5][0-9]|60)|reason=([A-Z_]+))$/.exec(raw)
      : null;
    if (!match || match[2] !== pending.nonce) return;
    var expected = pending.kind === 'GET' ? 'CURRENT' : 'APPLIED';
    if (match[1] === 'REFUSED') {
      var refusedKind = pending.kind;
      var reason = match[5];
      clearPending();
      slider.value = String(current);
      if (reason === 'UNCONFIRMED' || refusedKind === 'GET') {
        uncertain = true;
        status.textContent = 'État des FPS à confirmer ; réglage verrouillé.';
        if (reason === 'UNCONFIRMED' && state === 'PRÊT')
          send('GET', null); // The native write may have happened.
      } else {
        uncertain = false; // Explicit native BUSY/INVALID means no write.
        status.textContent = 'Réglage refusé par Webots (' + reason + ').';
      }
      update();
      return;
    }
    if (match[1] !== expected || !match[4]) return;
    var fps = Number(match[4]);
    if (pending.kind === 'SET' && fps !== pending.value) return;
    clearPending();
    uncertain = false;
    current = fps;
    slider.value = String(current);
    update();
    if (!locked()) status.textContent = 'Plafond Webots appliqué : ' + current + ' FPS.';
  }
  function mount() {
    if (mounted) return;
    container = document.getElementById('gpFpsControl');
    toggle = document.getElementById('gpFpsToggle');
    panel = document.getElementById('gpFpsPanel');
    slider = document.getElementById('gpFpsSlider');
    value = document.getElementById('gpFpsValue');
    status = document.getElementById('gpFpsStatus');
    if (!container || !toggle || !panel || !slider || !value || !status) return;
    mounted = true;
    toggle.addEventListener('click', function () {
      panel.hidden = !panel.hidden;
      toggle.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');
      if (!panel.hidden && uncertain && !pending && state === 'PRÊT')
        send('GET', null); // Manual read-only recovery after an unknown result.
      if (!panel.hidden) update();
    });
    document.addEventListener('pointerdown', function (event) {
      if (!panel.hidden && !container.contains(event.target)) {
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.hidden) {
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        toggle.focus();
      }
    });
    slider.addEventListener('input', function () { value.textContent = slider.value + ' FPS'; });
    slider.addEventListener('change', function () {
      var selected = Number(slider.value);
      if (!send('SET', selected)) {
        slider.value = String(current);
        update();
      }
    });
    update();
  }
  window.addEventListener('webeeblocks-gp-fps-response', receive);
  window.addEventListener('webeeblocks-runtime-v2', function (event) {
    state = event && event.detail && event.detail.state || 'INITIALISATION';
    if (!mounted) mount();
    // After first READY or a successful RESET, read the real WorldInfo.FPS.
    if (state === 'PRÊT' && !pending && window.runtimeBackend && window.runtimeBackend.ready)
      send('GET', null);
    update();
  });
  window.addEventListener('webeeblocks-ui-ready', mount);
  if (document.readyState !== 'loading') mount();
  else document.addEventListener('DOMContentLoaded', mount);
})();
