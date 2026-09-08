(function() {
  'use strict';

  var labels = Object.freeze({
    off: 'éteinte',
    red: 'rouge',
    green: 'verte',
    blue: 'bleue',
    yellow: 'jaune',
    white: 'blanche'
  });
  var swatches = Object.freeze({
    off: 'transparent',
    red: '#ef4444',
    green: '#22c55e',
    blue: '#3b82f6',
    yellow: '#eab308',
    white: '#ffffff'
  });

  function render(color) {
    if (!Object.prototype.hasOwnProperty.call(labels, color))
      throw new Error('unsupported observable Color LED state: ' + color);
    var text = document.getElementById('debugLight');
    var swatch = document.getElementById('debugLightSwatch');
    if (!text || !swatch) throw new Error('Color LED observability surface unavailable');
    text.textContent = labels[color];
    swatch.dataset.color = color;
    swatch.style.backgroundColor = swatches[color];
  }

  if (!window.WebeeBlocksExecutionObserver || typeof window.WebeeBlocksExecutionObserver.create !== 'function')
    throw new Error('execution observer unavailable for Color LED observability');

  var originalCreate = window.WebeeBlocksExecutionObserver.create;
  window.WebeeBlocksExecutionObserver.create = function(workspace, callbacks) {
    var controller = originalCreate(workspace, callbacks);
    if (!controller || !controller.hooks || typeof controller.hooks.onLight !== 'function')
      throw new Error('execution observer light hook unavailable');
    var originalOnLight = controller.hooks.onLight;
    controller.hooks.onLight = async function(context) {
      await originalOnLight(context);
      if (!context || typeof context.color !== 'string')
        throw new Error('applied Color LED observation missing color');
      render(context.color);
      window.dispatchEvent(new CustomEvent('webeeblocks-debug-light', {detail: {
        path: context.path || null,
        color: context.color
      }}));
    };
    return controller;
  };

  window.addEventListener('webeeblocks-runtime-v2-reset', function() { render('off'); });
})();
