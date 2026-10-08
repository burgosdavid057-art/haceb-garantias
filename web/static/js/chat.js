/* Widget del asistente Haceb.
 *
 * El desglose de cobertura no se pide como texto al modelo: se dibuja desde el
 * JSON que calculó Python. Si el modelo redacta "quedas cubierto" pero el
 * cálculo dice que el cliente paga $257.249, la tabla muestra la cifra real.
 * Lo que el usuario ve son los números del motor, no los del modelo.
 */
(() => {
  const fab      = document.getElementById('fabBot');
  const chat     = document.getElementById('chat');
  const cuerpo   = document.getElementById('chatCuerpo');
  const form     = document.getElementById('chatForm');
  const texto    = document.getElementById('chatTexto');
  const enviar   = document.getElementById('chatEnviar');
  const clip     = document.getElementById('chatClip');
  const archivo  = document.getElementById('chatArchivo');
  const estado   = document.getElementById('chatEstado');
  const sugeridas = document.getElementById('chatSugerencias');
  if (!fab) return;

  const pesos = v => '$' + Math.round(v).toLocaleString('es-CO');
  const el = (tag, cls, txt) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  };
  const abajo = () => { cuerpo.scrollTop = cuerpo.scrollHeight; };

  function burbuja(txt, quien) {
    const b = el('div', 'burbuja ' + quien, txt);
    cuerpo.appendChild(b);
    abajo();
    return b;
  }

  /* Panel de confianza: qué herramientas se usaron y si el auditor respaldó. */
  function confianza(d) {
    if (!d.herramientas?.length && d.verificado !== false) return;
    const c = el('div', 'confianza' + (d.verificado === false ? ' alerta' : ''));
    const b = el('b');
    if (d.verificado === false) {
      b.appendChild(HacebIconos.nodo('alerta', 12));
      b.append('Sin respaldo completo');
      c.appendChild(b);
      c.append(' — parte de esta respuesta no pudo verificarse contra las fuentes.');
    } else {
      b.appendChild(HacebIconos.nodo('verificado', 12));
      b.append('Verificado');
      c.appendChild(b);
      c.append(' con ' + (d.herramientas?.length || 0) + ' consulta(s) a datos de Haceb');
    }
    (d.herramientas || []).forEach(h => c.appendChild(el('span', 'chip', h)));
    (d.fuentes || []).slice(0, 2).forEach(f =>
      c.appendChild(el('div', null, '· ' + f)));
    cuerpo.appendChild(c);
    abajo();
  }

  /* La tabla de cobertura, línea por línea. El corazón del demo. */
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
    const caja = el('div', 'desglose');
    caja.appendChild(el('div', 'cabeza ' + clase, titulo));

    d.lineas.forEach(l => {
      const fila = el('div', 'linea');
      const dudosa = l.requiere_confirmacion;
      const marca = el('div', 'marca ' + (dudosa ? 'duda' : l.cubierto ? 'si' : 'no'));
      marca.appendChild(HacebIconos.nodo(dudosa ? 'ayuda' : l.cubierto ? 'check' : 'x', 14));
      fila.appendChild(marca);
      const q = el('div', 'qué');
      q.appendChild(el('b', null, l.producto.split('_').slice(-1)[0]));
      q.appendChild(el('span', null, l.motivo));
      fila.appendChild(q);
      fila.appendChild(el('div', 'val' + (l.cubierto ? ' tachado' : ''),
                          pesos(l.total_con_iva)));
      caja.appendChild(fila);
    });

    const t = el('div', 'totales');
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
  function trabajando(si) {
    ocupado = si;
    enviar.disabled = si;
    estado.textContent = si ? 'consultando…' : 'en línea';
    document.getElementById('_esc')?.remove();
    if (si) {
      const e = el('div', 'escribiendo', 'consultando datos de Haceb…');
      e.id = '_esc';
      cuerpo.appendChild(e);
      abajo();
    }
  }

  function pintar(d) {
    burbuja(d.reply || '(sin respuesta)', 'bot');
    desglose(d.dictamen);
    confianza(d);
  }

  /* Nombres de herramienta legibles para el indicador de trabajo. Que el
     usuario vea QUÉ se está consultando antes de que el agente afirme nada. */
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
    burbuja(txt, 'yo');
    sugeridas.style.display = 'none';
    texto.value = '';
    trabajando(true);

    let burbujaBot = null;   // se crea al llegar el primer fragmento de texto
    try {
      const r = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensaje: txt }),
      });

      const lector = r.body.getReader();
      const dec = new TextDecoder();
      let resto = '';

      for (;;) {
        const { value, done } = await lector.read();
        if (done) break;
        resto += dec.decode(value, { stream: true });

        // Los eventos SSE se separan por línea en blanco; el último trozo
        // puede venir cortado a la mitad y se guarda para la vuelta siguiente.
        const partes = resto.split('\n\n');
        resto = partes.pop();

        for (const parte of partes) {
          const linea = parte.split('\n').find(l => l.startsWith('data: '));
          if (!linea) continue;
          const ev = JSON.parse(linea.slice(6));

          if (ev.tipo === 'herramienta') {
            estado.textContent = ETIQUETA_TOOL[ev.dato] || 'consultando…';
            const e = document.getElementById('_esc');
            if (e) e.textContent = estado.textContent;
          } else if (ev.tipo === 'texto') {
            document.getElementById('_esc')?.remove();
            if (!burbujaBot) burbujaBot = burbuja('', 'bot');
            burbujaBot.textContent += ev.dato;
            abajo();
          } else if (ev.tipo === 'fin') {
            document.getElementById('_esc')?.remove();
            // El texto definitivo puede traer el aviso del auditor añadido.
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
    const b = burbuja('', 'yo');
    b.appendChild(HacebIconos.nodo('adjunto', 14));
    b.append(' ' + file.name);
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.style.maxHeight = '180px';
    b.appendChild(img);
    sugeridas.style.display = 'none';
    abajo();

    trabajando(true);
    estado.textContent = 'leyendo tu orden…';
    try {
      const b64 = await new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(fr.result);
        fr.onerror = rej;
        fr.readAsDataURL(file);
      });
      const r = await fetch('/api/chat/imagen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imagen: b64, mime: file.type }),
      });
      pintar(await r.json());
    } catch {
      burbuja('No pude procesar la imagen. ¿La reenvías?', 'bot');
    }
    trabajando(false);
  }

  /* --- Eventos --------------------------------------------------------- */
  fab.addEventListener('click', () => {
    const abierto = chat.classList.toggle('abierto');
    fab.classList.toggle('abierto', abierto);
    if (abierto) {
      texto.focus();
      if (!cuerpo.children.length) {
        burbuja('¡Hola! Soy el asistente de Haceb.\n\nPuedo ayudarte con tu equipo: si algo '
              + 'falla, si está en garantía, cuánto te cubre y cuánto no.\n\n¿Tienes una orden '
              + 'de servicio? Adjúntala con el clip y te digo exactamente qué cubre tu '
              + 'garantía y qué no.', 'bot');
      }
    }
  });

  document.getElementById('chatCerrar').addEventListener('click', () => {
    chat.classList.remove('abierto');
    fab.classList.remove('abierto');
  });

  form.addEventListener('submit', e => { e.preventDefault(); mandar(texto.value.trim()); });
  clip.addEventListener('click', () => archivo.click());
  archivo.addEventListener('change', e => {
    if (e.target.files[0]) mandarImagen(e.target.files[0]);
    e.target.value = '';
  });
  sugeridas.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) mandar(b.dataset.t);
  });

  /* Abrir el chat desde cualquier botón de la página. */
  document.querySelectorAll('[data-abrir-chat]').forEach(b =>
    b.addEventListener('click', () => { if (!chat.classList.contains('abierto')) fab.click(); }));

  /* --- Lo que decide el asesor vuelve al chat del cliente --------------- */

  const TEXTO_ESTADO = {
    'Aprobada':        ['aprobada',  'Tu garantía fue APROBADA'],
    'Rechazada':       ['rechazada', 'Tu solicitud fue rechazada'],
    'Info solicitada': ['info',      'Un asesor necesita más información'],
    'En revisión':     ['revision',  'Un asesor está revisando tu caso'],
  };

  function novedad(n) {
    const [icono, titulo] = TEXTO_ESTADO[n.estado] || ['info', 'Tu caso cambió de estado'];
    let txt = `${titulo}\n\nCaso ${n.ticket}`;
    if (n.nota) txt += `\n\nNota del asesor: ${n.nota}`;
    const b = burbuja('', 'bot');
    b.appendChild(HacebIconos.nodo(icono, 15));
    b.append(' ' + txt);
    // Se abre solo: el cliente no está mirando el chat cuando el asesor decide.
    if (!chat.classList.contains('abierto')) fab.click();
  }

  // El asesor decide en su propia pantalla, así que el chat pregunta cada tanto
  // si hay algo nuevo para este cliente. Sondeo simple y suficiente: es un solo
  // usuario y la alternativa (websockets) es infraestructura que no hace falta.
  // ponytail: polling cada 8 s; si algún día hay muchos clientes, SSE.
  setInterval(async () => {
    try {
      const r = await fetch('/api/novedades');
      const d = await r.json();
      (d.novedades || []).forEach(novedad);
    } catch { /* el servidor se cayó; se reintenta en la siguiente vuelta */ }
  }, 8000);
})();
