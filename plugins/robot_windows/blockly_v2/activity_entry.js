(function() {
  'use strict';

  var catalog = null;
  var loading = false;
  var controlsLocked = false;

  function controls() {
    return {
      shell: document.getElementById('activityStarterControls'),
      select: document.getElementById('activityStarter'),
      start: document.getElementById('activityStart')
    };
  }

  function setControlsDisabled() {
    var ui = controls();
    if (!ui.select || !ui.start) return;
    ui.select.disabled = controlsLocked || loading;
    ui.start.disabled = controlsLocked || loading || !ui.select.value;
  }

  function profileFor(activityId) {
    return WebeeBlocksActivityProfiles.resolveById(
      WebeeBlocksActivities.DOCUMENT,
      activityId,
      WebeeBlocksActivities.BLOCK_CATALOG
    );
  }

  function validateCatalog(value) {
    if (!value || value.version !== 1 || !Array.isArray(value.starters) || !value.starters.length)
      throw new Error('invalid progression starter manifest');
    var files = Object.create(null);
    var ids = Object.create(null);
    var entries = value.starters.map(function(entry) {
      if (!entry || typeof entry.file !== 'string' || typeof entry.activityId !== 'string')
        throw new Error('invalid progression starter entry');
      if (!/^\d{2}-[a-z0-9-]+\.wbb$/.test(entry.file))
        throw new Error('invalid progression starter filename: ' + entry.file);
      if (!/^progression-[a-z0-9-]+-v1$/.test(entry.activityId))
        throw new Error('invalid progression activity id: ' + entry.activityId);
      if (files[entry.file] || ids[entry.activityId])
        throw new Error('duplicate progression starter entry');
      files[entry.file] = true;
      ids[entry.activityId] = true;
      var profile = profileFor(entry.activityId);
      if (!profile.brief || profile.brief.visible !== true)
        throw new Error('progression starter has no visible activity brief: ' + entry.activityId);
      if (!runtimeProfile || profile.world !== runtimeProfile.world)
        throw new Error('progression starter is incompatible with the current Webots world: ' + entry.activityId);
      return {file: entry.file, activityId: entry.activityId, title: profile.brief.title};
    });
    return entries;
  }

  async function loadCatalog() {
    var response = await fetch(new URL('activities/progression/index.json', window.location.href).href, {cache: 'no-store'});
    if (!response.ok) throw new Error('progression starter manifest unavailable: HTTP ' + response.status);
    return validateCatalog(await response.json());
  }

  function renderCatalog(entries) {
    var ui = controls();
    if (!ui.shell || !ui.select || !ui.start) return;
    while (ui.select.options.length > 1) ui.select.remove(1);
    entries.forEach(function(entry) {
      var option = document.createElement('option');
      option.value = entry.file;
      option.textContent = entry.title;
      option.dataset.activityId = entry.activityId;
      ui.select.appendChild(option);
    });
    ui.shell.hidden = false;
    ui.select.addEventListener('change', setControlsDisabled);
    ui.start.addEventListener('click', startSelected);
    setControlsDisabled();
  }

  async function startSelected() {
    if (loading || controlsLocked || !catalog || typeof window.WebeeBlocksStartActivityTemplate !== 'function') return;
    var ui = controls();
    var selected = catalog.find(function(entry) { return entry.file === ui.select.value; });
    if (!selected) return;
    loading = true;
    setControlsDisabled();
    try {
      var response = await fetch(new URL('activities/progression/' + selected.file, window.location.href).href, {cache: 'no-store'});
      if (!response.ok) throw new Error('activity starter unavailable: HTTP ' + response.status);
      var text = await response.text();
      var result = await window.WebeeBlocksStartActivityTemplate(text, selected.file);
      if (result) {
        ui.select.value = '';
        window.dispatchEvent(new CustomEvent('webeeblocks-activity-started', {
          detail: {activityId: selected.activityId, starter: selected.file}
        }));
      }
    } catch (error) {
      console.error('WebeeBlocks activity starter failed', error);
      window.dispatchEvent(new CustomEvent('webeeblocks-activity-starter-diagnostic', {
        detail: {technicalMessage: error && error.message ? error.message : String(error)}
      }));
    } finally {
      loading = false;
      setControlsDisabled();
    }
  }

  async function initialize() {
    if (catalog || typeof window.WebeeBlocksStartActivityTemplate !== 'function') return;
    try {
      catalog = await loadCatalog();
      renderCatalog(catalog);
    } catch (error) {
      // The generic development Robot Window may run without the packaged
      // classroom starter bundle. Keep that path intact and expose the chooser
      // only when the deterministic release bundle is actually present.
      console.warn('WebeeBlocks classroom progression starters unavailable', error);
    }
  }

  window.addEventListener('webeeblocks-project-files-ready', initialize);
  window.addEventListener('webeeblocks-project-controls', function(event) {
    controlsLocked = !!(event && event.detail && event.detail.locked);
    setControlsDisabled();
  });
  if (window.WebeeBlocksProjectManager) initialize();
})();
