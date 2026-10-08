/* Bandeja del asesor de garantías.
 *
 * El asesor no ve la conclusión del sistema y ya: ve el desglose línea por
 * línea, con las que el motor NO pudo respaldar marcadas en rojo. La decisión
 * la toma una persona con la evidencia a la vista — el sistema prepara el caso,
 * no lo cierra.
 */
(() => {
  const $ = id => document.getElementById(id);
  const pesos = v => '$' + Math.round(v || 0).toLocaleString('es-CO');
  const el = (tag, cls, txt) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  };
  const clase = e => e.replace(/ /g, '-');

  let filtro = null, seleccionado = null;

  /* --- Ingreso --------------------------------------------------------- */
  $('formIngreso').addEventListener('submit', async e => {
    e.preventDefault();
    const r = await fetch('/api/portal/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario: $('usuario').value, clave: $('clave').value }),
    });
    const d = await r.json();
    if (!d.ok) {
      const err = $('errorIngreso');
      err.textContent = d.motivo;
      err.style.display = 'block';
      return;
    }
    entrar(d.asesor);
  });

  function entrar(asesor) {
    $('ingreso').style.display = 'none';
    $('portal').classList.add('activo');
    $('sesion').style.display = 'flex';
    $('quien').textContent = asesor;
    cargar();
  }

  $('salir').addEventListener('click', async () => {
    await fetch('/api/portal/salir', { method: 'POST' });
    location.reload();
  });

  /* --- Bandeja --------------------------------------------------------- */
  async function cargar() {
    const r = await fetch('/api/casos' + (filtro ? '?estado=' + encodeURIComponent(filtro) : ''));
    if (r.status === 401) return location.reload();
    const d = await r.json();
    pintarKpis(d.resumen);
    pintarFiltros(d.estados);
    pintarLista(d.casos);
  }

  function pintarKpis(res) {
    const k = $('kpis');
    k.innerHTML = '';
    const tarjeta = (n, e, cls) => {
      const c = el('div', 'kpi ' + (cls || ''));
      c.appendChild(el('div', 'n', n));
      c.appendChild(el('div', 'e', e));
      return c;
    };
    k.appendChild(tarjeta(res.total, 'Casos totales'));
    k.appendChild(tarjeta(res.por_estado['Pendiente'], 'Pendientes de revisar', 'pendiente'));
    k.appendChild(tarjeta(res.por_estado['En revisión'], 'En revisión', 'revision'));
    k.appendChild(tarjeta(res.por_estado['Aprobada'], 'Aprobadas', 'aprobada'));
    k.appendChild(tarjeta(res.por_estado['Rechazada'], 'Rechazadas'));
  }

  function pintarFiltros(estados) {
    const f = $('filtros');
    f.innerHTML = '';
    const boton = (etq, val) => {
      const b = el('button', filtro === val ? 'on' : '', etq);
      b.onclick = () => { filtro = val; seleccionado = null; cargar(); };
      return b;
    };
    f.appendChild(boton('Todos', null));
    estados.forEach(e => f.appendChild(boton(e, e)));
  }

  function pintarLista(casos) {
    const l = $('listaCasos');
    l.innerHTML = '';
    if (!casos.length) {
      l.appendChild(el('div', 'vacio', 'No hay casos con ese estado.')).style.padding = '34px 16px';
      return;
    }
    casos.forEach(c => {
      const dud = c.dictamen?.requiere_asesor;
      const n = el('div', 'caso' + (dud ? ' alerta' : '') + (c.ticket === seleccionado ? ' sel' : ''));
      const f1 = el('div', 'fila1');
      f1.appendChild(el('span', 'tk', c.ticket));
      f1.appendChild(el('span', 'pill ' + clase(c.estado), c.estado));
      n.appendChild(f1);
      n.appendChild(el('div', 'pr', c.dictamen?.producto || c.componente || '—'));
      n.appendChild(el('div', 'mt',
        `${c.numero_cita || 's/orden'} · en juego ${pesos(c.dictamen?.paga_cliente_cop)}`));
      n.onclick = () => abrir(c.ticket);
      l.appendChild(n);
    });
  }

  /* --- Detalle --------------------------------------------------------- */
  async function abrir(ticket) {
    seleccionado = ticket;
    document.querySelectorAll('.caso').forEach(n =>
      n.classList.toggle('sel', n.querySelector('.tk').textContent === ticket));

    const r = await fetch('/api/casos/' + ticket);
    const d = await r.json();
    if (!d.ok) return;
    pintarDetalle(d.caso, d.orden, d.equipo);
  }

  const TITULOS = {
    cubierta_total:   'Cubierto por garantía · el cliente no paga',
    cubierta_parcial: 'Cobertura parcial · pieza cubierta, mano de obra al cobro',
    no_cubierta:      'Sin cobertura vigente',
    excluida:         'Excluido de garantía',
    requiere_revision: 'El sistema no pudo respaldar la cobertura · decide el asesor',
  };

  function pintarDetalle(caso, orden, equipo) {
    const d = caso.dictamen || {};
    const n = $('detalle');
    n.innerHTML = '';

    n.appendChild(el('h2', null, caso.ticket + ' · ' + (d.producto || equipo?.producto || '')));
    n.appendChild(el('div', 'sub',
      `Radicado ${caso.creado?.replace('T', ' ')} · canal ${caso.canal} · orden ${caso.numero_cita || '—'}`));

    const bloques = el('div', 'bloques');
    const bloque = (k, v) => {
      const b = el('div', 'bloque');
      b.appendChild(el('div', 'k', k));
      b.appendChild(el('div', 'v', v ?? '—'));
      return b;
    };
    bloques.appendChild(bloque('Cliente', equipo?.cliente));
    bloques.appendChild(bloque('Serie', equipo?.serie));
    bloques.appendChild(bloque('Compra', equipo?.fecha_compra));
    bloques.appendChild(bloque('Antigüedad', d.anios_de_uso != null ? d.anios_de_uso + ' años' : '—'));
    bloques.appendChild(bloque('Teléfono', equipo?.telefono));
    n.appendChild(bloques);

    if (d.veredicto) {
      n.appendChild(el('div', 'veredicto ' + d.veredicto, TITULOS[d.veredicto] || d.veredicto));
    }

    if (d.requiere_asesor) {
      const a = el('div', 'aviso-revision');
      a.appendChild(el('b', null, 'Por qué llegó a tu bandeja: '));
      a.append(d.exclusiones?.length
        ? `el técnico registró ${d.exclusiones.join(', ')}, que es causal de exclusión. Confirma antes de negar.`
        : `${d.lineas_dudosas} línea(s) no se pudieron mapear a una parte nombrada en los términos `
          + `publicados. El sistema no las dio por cubiertas ni por negadas.`);
      n.appendChild(a);
    }

    if (d.texto_garantia) {
      const g = el('div', 'legal');
      g.appendChild(el('b', null, 'Garantía publicada: '));
      g.append(d.texto_garantia);
      g.appendChild(el('div', null,
        `Garantía legal: ${d.anios_garantia_legal} año (cubre pieza y servicio). `
        + `Después, la suplementaria cubre la pieza pero no la mano de obra.`));
      n.appendChild(g);
    }

    if (d.lineas?.length) {
      const t = el('table', 'lineas');
      t.innerHTML = '<thead><tr><th>·</th><th>Concepto</th><th>Tipo</th>'
                  + '<th class="num">Valor</th><th class="num">Asume</th></tr></thead>';
      const tb = el('tbody');
      d.lineas.forEach(l => {
        const tr = el('tr', l.requiere_confirmacion ? 'dudosa' : '');
        const marca = l.requiere_confirmacion ? ['duda', 'ayuda']
                    : l.cubierto ? ['sí', 'check'] : ['no', 'x'];
        const tdMarca = el('td', marca[0]);
        tdMarca.appendChild(HacebIconos.nodo(marca[1], 14));
        tr.appendChild(tdMarca);
        const c = el('td');
        c.appendChild(el('b', null, l.producto));
        c.appendChild(el('div', 'motivo', l.motivo));
        tr.appendChild(c);
        tr.appendChild(el('td', null, l.tipo));
        tr.appendChild(el('td', 'num', pesos(l.total_con_iva)));
        tr.appendChild(el('td', 'num', l.cubierto ? 'Haceb' : 'Cliente'));
        tb.appendChild(tr);
      });
      t.appendChild(tb);
      const tf = el('tfoot');
      const fila = el('tr');
      fila.appendChild(el('td', null, ''));
      fila.appendChild(el('td', null, 'Totales'));
      fila.appendChild(el('td', null, ''));
      fila.appendChild(el('td', 'num', pesos(d.total_orden_cop)));
      fila.appendChild(el('td', 'num', `Haceb ${pesos(d.cubre_haceb_cop)} · Cliente ${pesos(d.paga_cliente_cop)}`));
      tf.appendChild(fila);
      t.appendChild(tf);
      n.appendChild(t);
    }

    if (orden?.observaciones) {
      const o = el('div', 'legal');
      o.appendChild(el('b', null, 'Observaciones del técnico: '));
      o.append(orden.observaciones);
      n.appendChild(o);
    }

    /* --- Acciones --- */
    const acc = el('div', 'acciones-caso');
    if (caso.nota_asesor) {
      const previa = el('div', 'legal');
      previa.appendChild(el('b', null, `Nota de ${caso.asesor}: `));
      previa.append(caso.nota_asesor);
      acc.appendChild(previa);
    }
    const nota = el('textarea');
    nota.placeholder = 'Nota de la decisión (queda registrada con tu usuario)…';
    acc.appendChild(nota);

    const botones = el('div', 'botones');
    const accion = (etq, estado, cls) => {
      const b = el('button', cls, etq);
      b.onclick = async () => {
        const r = await fetch('/api/casos/' + caso.ticket, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ estado, nota: nota.value }),
        });
        const res = await r.json();
        if (res.ok) {
          $('okGuardado').style.display = 'block';
          await cargar();
          abrir(caso.ticket);
        }
      };
      return b;
    };
    botones.appendChild(accion('Aprobar garantía', 'Aprobada', 'b-aprobar'));
    botones.appendChild(accion('Rechazar', 'Rechazada', 'b-rechazar'));
    botones.appendChild(accion('Pedir más información', 'Info solicitada', 'b-info'));
    acc.appendChild(botones);

    const ok = el('div', 'ok-guardado');
    ok.appendChild(HacebIconos.nodo('check', 13));
    ok.append(' Decisión registrada.');
    ok.id = 'okGuardado';
    acc.appendChild(ok);
    n.appendChild(acc);
  }

  /* Si ya hay sesión abierta (recarga), entrar directo. */
  fetch('/api/casos').then(r => r.json()).then(d => { if (d.ok) entrar(d.asesor); });
})();
