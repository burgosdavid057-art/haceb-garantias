/* Página dedicada del asistente Haceb (pantalla completa).
   Reusa los mismos endpoints que el widget (/api/chat/stream, /api/chat/imagen)
   pero con su propio DOM, para no interferir con el chat flotante. */
(function () {
  document.body.classList.add('pagina-asistente');   // oculta el widget flotante

  const cuerpo   = document.getElementById('asCuerpo');
  const texto    = document.getElementById('asTexto');
  const enviar   = document.getElementById('asEnviar');
  const estado   = document.getElementById('asEstado');
  const form     = document.getElementById('asForm');
  const clip     = document.getElementById('asClip');
  const archivo  = document.getElementById('asArchivo');
  const bienvenida = cuerpo.querySelector('.as-bienvenida');

  const pesos = v => '$' + Math.round(v).toLocaleString('es-CO');
  const el = (tag, cls, txt) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  };
  const abajo = () => { cuerpo.scrollTop = cuerpo.scrollHeight; };
  const limpiarBienvenida = () => { if (bienvenida) bienvenida.style.display = 'none'; };

  function burbuja(txt, quien) {
    const b = el('div', 'as-burbuja ' + quien, txt);
    cuerpo.appendChild(b);
    abajo();
    return b;
  }

  function confianza(d) {
    if (!d.herramientas?.length && d.verificado !== false) return;
    const c = el('div', 'as-confianza' + (d.verificado === false ? ' alerta' : ''));
    const b = el('b');
    if (d.verificado === false) {
      b.appendChild(HacebIconos.nodo('alerta', 13));
      b.append('Sin respaldo completo');
      c.appendChild(b);
      c.append(' — parte de esta respuesta no pudo verificarse.');
    } else {
      b.appendChild(HacebIconos.nodo('verificado', 13));
      b.append('Verificado');
      c.appendChild(b);
      c.append(' con ' + (d.herramientas?.length || 0) + ' consulta(s) a datos de Haceb');
    }
    (d.herramientas || []).forEach(h => c.appendChild(el('span', 'as-chip', h)));
    cuerpo.appendChild(c);
    abajo();
  }

  const TITULOS = {
    cubierta_total:    ['total',    'Cubierto por garantía'],
    cubierta_parcial:  ['parcial',  'Cobertura parcial'],
    no_cubierta:       ['ninguna',  'Sin cobertura vigente'],
    excluida:          ['ninguna',  'Excluido de garantía'],
    requiere_revision: ['revision', 'Requiere revisión de un asesor'],
  };

  function desglose(d) {
    if (!d?.determinable) return;
    const [clase, titulo] = TITULOS[d.veredicto] || ['ninguna', 'Resultado'];
    const caja = el('div', 'as-desglose');
    caja.appendChild(el('div', 'as-cabeza ' + clase, titulo));
    d.lineas.forEach(l => {
      const fila = el('div', 'as-linea');
      const dudosa = l.requiere_confirmacion;
      const marca = el('div', 'as-marca ' + (dudosa ? 'duda' : l.cubierto ? 'si' : 'no'));
      marca.appendChild(HacebIconos.nodo(dudosa ? 'ayuda' : l.cubierto ? 'check' : 'x', 13));
      fila.appendChild(marca);
      const q = el('div', 'as-que');
      q.appendChild(el('b', null, l.producto.split('_').slice(-1)[0]));
      q.appendChild(el('span', null, l.motivo));
      fila.appendChild(q);
      fila.appendChild(el('div', 'as-val' + (l.cubierto ? ' tachado' : ''),
                          pesos(l.total_con_iva)));
      caja.appendChild(fila);
    });
    const t = el('div', 'as-totales');
    const linea = (etq, val, cls) => {
      const f = el('div', cls);
      f.appendChild(el('span', null, etq));
      f.appendChild(el('span', null, pesos(val)));
      return f;
    };
    t.appendChild(linea('Total del servicio', d.total_orden_cop));
    t.appendChild(linea('Asume Haceb', d.cubre_haceb_cop));
    t.appendChild(linea('Pagas tú', d.paga_cliente_cop, 'pagas'));
    caja.appendChild(t);
    cuerpo.appendChild(caja);
    abajo();
  }

  let ocupado = false;
  function trabajando(si, etiqueta) {
    ocupado = si;
    enviar.disabled = si;
    estado.textContent = si ? (etiqueta || 'consultando…') : 'en línea';
    document.getElementById('_asEsc')?.remove();
    if (si) {
      const e = el('div', 'as-escribiendo', etiqueta || 'consultando datos de Haceb…');
      e.id = '_asEsc';
      cuerpo.appendChild(e);
      abajo();
    }
  }

  const ETIQUETA_TOOL = {
    consultar_orden_servicio: 'revisando tu orden de servicio…',
    radicar_garantia: 'radicando tu solicitud…',
    consultar_caso: 'buscando tu caso…',
    verificar_garantia: 'leyendo los términos de garantía…',
    consultar_manual: 'buscando en el manual oficial…',
    buscar_productos: 'buscando en el catálogo…',
    ficha_tecnica: 'leyendo la ficha técnica…',
    validar_espacio: 'comparando medidas…',
    recomendar_para_espacio: 'viendo cuáles caben…',
    costo_energia: 'calculando el consumo…',
    comparar_costo_total: 'comparando costo total…',
    escalar_a_servicio_tecnico: 'derivando a servicio técnico…',
  };

  async function mandar(txt) {
    if (!txt || ocupado) return;
    limpiarBienvenida();
    burbuja(txt, 'yo');
    texto.value = '';
    trabajando(true);
    let burbujaBot = null;
    try {
      const r = await fetch('/api/chat/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensaje: txt }),
      });
      const lector = r.body.getReader();
      const dec = new TextDecoder();
      let resto = '';
      for (;;) {
        const { value, done } = await lector.read();
        if (done) break;
        resto += dec.decode(value, { stream: true });
        const partes = resto.split('\n\n');
        resto = partes.pop();
        for (const parte of partes) {
          const linea = parte.split('\n').find(l => l.startsWith('data: '));
          if (!linea) continue;
          const ev = JSON.parse(linea.slice(6));
          if (ev.tipo === 'herramienta') {
            const t = ETIQUETA_TOOL[ev.dato] || 'consultando…';
            estado.textContent = t;
            const e = document.getElementById('_asEsc'); if (e) e.textContent = t;
          } else if (ev.tipo === 'texto') {
            document.getElementById('_asEsc')?.remove();
            if (!burbujaBot) burbujaBot = burbuja('', 'bot');
            burbujaBot.textContent += ev.dato;
            abajo();
          } else if (ev.tipo === 'fin') {
            document.getElementById('_asEsc')?.remove();
            if (burbujaBot) burbujaBot.textContent = ev.dato.reply;
            else burbuja(ev.dato.reply || '(sin respuesta)', 'bot');
            desglose(ev.dato.dictamen);
            confianza(ev.dato);
          }
        }
      }
    } catch {
      burbuja('No pude conectar con el asistente. ¿El servidor está corriendo?', 'bot');
    }
    trabajando(false);
    texto.focus();
  }

  async function mandarImagen(file) {
    if (ocupado) return;
    limpiarBienvenida();
    const b = burbuja('', 'yo');
    b.appendChild(HacebIconos.nodo('adjunto', 14));
    b.append(' ' + file.name);
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.className = 'as-img';
    b.appendChild(img);
    trabajando(true, 'leyendo tu orden…');
    try {
      const b64 = await new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(fr.result);
        fr.onerror = rej;
        fr.readAsDataURL(file);
      });
      const r = await fetch('/api/chat/imagen', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imagen: b64, mime: file.type }),
      });
      const d = await r.json();
      burbuja(d.reply || '(sin respuesta)', 'bot');
      desglose(d.dictamen);
      confianza(d);
    } catch {
      burbuja('No pude procesar la imagen. ¿La reenvías?', 'bot');
    }
    trabajando(false);
  }

  /* --- Eventos --- */
  form.addEventListener('submit', e => { e.preventDefault(); mandar(texto.value.trim()); });
  clip.addEventListener('click', () => archivo.click());
  document.getElementById('asSubirOrden')?.addEventListener('click', () => archivo.click());
  archivo.addEventListener('change', e => {
    if (e.target.files[0]) mandarImagen(e.target.files[0]);
    e.target.value = '';
  });
  document.querySelectorAll('.as-accion').forEach(b =>
    b.addEventListener('click', () => mandar(b.dataset.t)));
  document.getElementById('asCasoForm')?.addEventListener('submit', e => {
    e.preventDefault();
    const v = document.getElementById('asCaso').value.trim();
    if (v) mandar('¿Cuál es el estado de mi caso ' + v + '?');
    document.getElementById('asCaso').value = '';
  });

  /* Novedades del asesor (el portal decide → vuelve al chat del cliente). */
  const vistas = new Set();
  async function novedades() {
    try {
      const r = await fetch('/api/novedades');
      const ns = await r.json();
      (ns.novedades || ns || []).forEach(n => {
        const id = n.ticket + n.estado;
        if (vistas.has(id)) return;
        vistas.add(id);
        limpiarBienvenida();
        const b = burbuja('', 'bot');
        b.appendChild(HacebIconos.nodo('campana', 14));
        b.append(' Actualización de tu caso ' + n.ticket + ': ' + n.estado +
                 (n.nota ? ' — ' + n.nota : ''));
      });
    } catch {}
  }
  setInterval(novedades, 8000);
  texto.focus();
})();
