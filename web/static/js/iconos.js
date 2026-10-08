/* Íconos SVG (línea, trazo 1.9, currentColor) para el contenido que el chat
   genera en caliente. Sustituyen a los emojis de los mensajes: mismo peso
   visual, sin depender de la fuente de emoji del sistema operativo y con un
   trazo coherente en todo el producto. Estilo Lucide/Heroicons. */
(function () {
  const TRAZOS = {
    check:      '<path d="M20 6 9 17l-5-5"/>',
    x:          '<path d="M18 6 6 18M6 6l12 12"/>',
    ayuda:      '<circle cx="12" cy="12" r="9"/><path d="M9.2 9.2a3 3 0 0 1 5.5 1.1c0 1.8-2.7 2.4-2.7 4"/><path d="M12 17h.01"/>',
    verificado: '<path d="M12 2 4 5v6c0 5 3.4 8.6 8 10 4.6-1.4 8-5 8-10V5z"/><path d="M9 12l2 2 4-4"/>',
    alerta:     '<path d="M12 3 2 20h20z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
    adjunto:    '<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 6"/>',
    campana:    '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    aprobada:   '<circle cx="12" cy="12" r="9"/><path d="M8.4 12.4l2.5 2.5 4.7-5.2"/>',
    rechazada:  '<circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/>',
    info:       '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
    revision:   '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  };

  /* Devuelve el string <svg…>. Insertar via innerHTML de un elemento HTML
     (no SVG) garantiza que el parser lo cree en el namespace correcto. */
  function html(nombre, tam) {
    const t = TRAZOS[nombre] || '';
    const s = tam || 16;
    return '<svg viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="none" ' +
           'stroke="currentColor" stroke-width="1.9" stroke-linecap="round" ' +
           'stroke-linejoin="round" aria-hidden="true">' + t + '</svg>';
  }

  /* Devuelve un nodo <svg> listo para appendChild. */
  function nodo(nombre, tam) {
    const cont = document.createElement('span');
    cont.innerHTML = html(nombre, tam);
    return cont.firstElementChild;
  }

  window.HacebIconos = { html, nodo };
})();
