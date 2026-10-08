# Asistente de garantías Haceb

Un asistente que no responde *"sí, está en garantía"*.

Responde **qué queda cubierto, qué no, y cuánto tienes que pagar** — con el
desglose línea por línea de tu orden de servicio.

> De una orden real de Haceb: *"el compresor será en garantía pero debe asumir
> el valor de la mano de obra"*. De $575.789, la pieza va cubierta y $257.249 de
> servicio calificado no. Un asistente que contesta "sí, está cubierto" y deja
> que llegue esa cuenta hizo más daño que si no hubiera contestado.

Corre **entero en local**. Ninguna orden de servicio —con nombre, cédula,
teléfono y dirección de una persona— sale de la máquina.

---

## Qué hay aquí

Tres superficies sobre un solo servidor Flask:

| | Dónde | Qué es |
|---|---|---|
| Sitio público | `/` y `/servicios` | Maqueta visual de haceb.com. En el lugar exacto del botón de WhatsApp hay un botón de bot. |
| Chat | widget flotante | El agente: garantías, fallas, catálogo. Acepta la **foto** de una orden. Responde en streaming. |
| Portal interno | `/portal` | Bandeja del asesor: los casos que el sistema **no** pudo resolver solo. |

El círculo se cierra: cuando el asesor aprueba, rechaza o pide más información,
la decisión **vuelve al chat del cliente** —con la nota que escribió— sin que el
cliente tenga que preguntar. El caso se ata a la sesión del navegador que lo
radicó; no hay cuentas de usuario en un demo.

```
        cliente                          asesor de Haceb
           │                                    │
    chat en el sitio                      /portal (bandeja)
           │                                    │
           ├── foto de la orden ──┐             │
           │                      ▼             │
           │            gemma4 lee IDENTIFICADORES
           │            (nº de cita, serie) — no hechos
           │                      │             │
           └── nº de orden ───────┤             │
                                  ▼             │
                        ┌──────────────────┐    │
                        │ SQLite: equipos, │    │
                        │ órdenes, casos   │────┘
                        └────────┬─────────┘
                                 ▼
                     motor de cobertura (Python)
                     línea por línea, sin modelo
                                 │
                    ┌────────────┴───────────┐
                    ▼                        ▼
            desglose al cliente     lo que no pudo respaldar
                                    → bandeja del asesor
```

## La regla que hace todo esto posible

Sale del texto legal que Haceb publica en su propio catálogo:

> *"10 años\* en el compresor y 1 años en los demás componentes, \*1 año
> correspondiente a garantía legal y 9 años a garantía suplementaria."*

Esas dos garantías **no cubren lo mismo**:

| | Cubre |
|---|---|
| Garantía **legal** (año 1) | la pieza **y** el servicio |
| Garantía **suplementaria** (año 2+) | la pieza. La mano de obra se cobra |

Por eso una nevera de 4 años con el compresor dañado tiene la pieza cubierta y
el servicio al cobro. No es una excepción: es el caso más frecuente, y es el que
ningún chatbot de catálogo responde bien.

## Las tres cosas que el sistema se niega a hacer

**No le cree al cliente la antigüedad del equipo.** Nadie pregunta "¿hace cuánto
la compraste?". La fecha de compra sale de la serie registrada. Sin eso, la
cobertura se calcularía sobre un dato que nadie verificó.

**No deja que el modelo aporte hechos.** Lo que la visión lee de la foto son
*identificadores* (nº de cita, serie), y solo sirven para **encontrar** la orden.
Los montos con los que se calcula salen siempre de la base. Medido: en una
prueba el modelo leyó "Nevera Frost 4ra Litros" en vez de "No Frost 404 Litros"
y el dictamen salió correcto igual — un identificador mal leído no encuentra
nada y se puede preguntar; un monto mal leído se le cobra a alguien.

**No adivina un repuesto que no puede mapear.** Si "FILTRO SECADOR TRES BOCAS
DELTA 20" no corresponde a ninguna parte nombrada en los términos publicados, el
caso sale como `requiere_revision` y va al asesor — ni cubierto ni negado.
Afirmar "no está cubierto" sin respaldo hace tanto daño como afirmar que sí.

## Cómo se corre

Todo local, con [Ollama](https://ollama.com):

```bash
ollama pull gemma4 && ollama pull bge-m3
ollama create haceb-agente    -f Modelfile
ollama create haceb-validador -f Modelfile.validador

pip install -r requirements.txt
python seed.py       # equipos, órdenes de servicio y casos de ejemplo
python serve.py      # http://localhost:5050
```

Portal del asesor: `/portal` — usuario `asesor`, clave `haceb2026`.

**Chequeos** (los dos primeros corren sin modelo y sin red):

```bash
python test_garantias.py    # 6 casos, uno por rama del motor de cobertura
python test_validador.py    # ¿el guardián atrapa una cifra inventada?
python -m evals.run         # harness adversarial contra el agente (usa modelo)
```

## Por qué estos modelos

Medido en un M5/16GB con las herramientas reales del agente:

| Modelo | Tool calls | Latencia |
|---|---|---|
| **gemma4 (8B)** | **4/4** | **6–14 s** |
| qwen3.5:9b | 4/4 | 12–23 s |
| qwen2.5:3b | 1/4 | 1–4 s |

gemma4 además declara capacidad de visión, que es lo que permite leer las
órdenes sin mandar el documento a ninguna nube. Un modelo más pequeño responde
rápido pero no dispara las herramientas — y sin herramientas este agente
respondería de memoria, que es justo lo que existe para evitar.

**El modelo se precalienta al arrancar.** Ollama lo descarga de RAM tras unos
minutos de inactividad y recargarlo cuesta ~20 s: medido, el primer turno con el
modelo frío tardó 30 s en decidir la herramienta y 9 s caliente. `serve.py` lanza
una llamada trivial al arrancar para que eso no se lo coma quien abra el chat.

Con el modelo caliente y streaming, un turno se ve así: herramienta a los 9 s,
primera palabra en pantalla a los 10,6 s, respuesta completa a los 21 s.

**La ventana de contexto se hornea en un `Modelfile`, no se pasa en la llamada.**
El endpoint `/v1` de Ollama ignora `options`, `think` y `chat_template_kwargs`:
el modelo sigue cargando con 4096. Con 4096 el prompt (7 KB) más los esquemas de
las 12 herramientas ocupan ~3.900 tokens, el razonamiento se come los ~190 que
quedan, y el turno termina con `finish_reason: length` y contenido **vacío**.
Desde afuera parece que el agente no entendió la pregunta.

## Los dos auditores

| | Atrapa | Cuesta |
|---|---|---|
| **Literalidad** (Python, por defecto) | 4/5 — montos y años inventados | **0,03 ms** |
| LLM (`VALIDADOR=llm`) | 5/5 — también lo cualitativo | 26–86 s |

El auditor con modelo corre *después* del agente, así que su latencia se le suma
entera al usuario: dos minutos por turno. El guardián determinista comprueba que
cada cifra de la respuesta esté en la evidencia de las herramientas, y eso cubre
lo que cuesta dinero.

Lo que el determinista no atrapa es una afirmación cualitativa invertida ("NO
está cubierto" cuando sí lo está). Contra eso juega el desglose en pantalla: se
dibuja desde el cálculo de Python, no desde el texto del modelo. Si el modelo
dice lo contrario, la tabla lo desmiente a la vista.

Se probó también un auditor pequeño (qwen2.5:3b, 1,4 s): aprobó las **tres**
alucinaciones de la tabla de prueba. Un auditor rápido que aprueba todo no es un
auditor, es latencia decorativa.

## Estructura

| | |
|---|---|
| [agent/garantias.py](agent/garantias.py) | motor de cobertura línea por línea |
| [agent/literalidad.py](agent/literalidad.py) | guardián: toda cifra debe estar en la evidencia |
| [agent/facturas.py](agent/facturas.py) | foto de la orden → identificadores → dictamen |
| [agent/db.py](agent/db.py) | equipos, órdenes y casos (SQLite) |
| [agent/tools.py](agent/tools.py) | las 12 herramientas del agente |
| [agent/loop.py](agent/loop.py) | el loop y el prompt |
| [web/server.py](web/server.py) | sitio, chat y portal |
| [seed.py](seed.py) | 6 equipos, 6 órdenes, 3 casos en bandeja |

## Límites conocidos

- El sitio público es una **maqueta**: buscador, carrito y filtros no hacen nada.
  Solo el chat y el portal funcionan.
- Los datos personales de las órdenes son **ficticios**.
- La antigüedad se calcula contra una base de equipos sembrada; en producción
  saldría del sistema de ventas de Haceb.
- El mapeo repuesto → parte cubierta es explícito y corto a propósito. Lo que no
  está, va al asesor. Ampliarlo es cargar el catálogo real de repuestos, no
  cambiar el motor.
- El portal usa credenciales quemadas: es una maqueta de acceso, no un control
  de acceso.
- El RAG sobre los manuales necesita `python ingest.py && python build_index.py
  && python build_vectordb.py`. Sin eso funciona por BM25, que basta para el
  flujo de garantías.

## Licencia

MIT — ver [LICENSE](LICENSE). Datos de producto y manuales: propiedad de
Industrias Haceb S.A., obtenidos de sus canales públicos. Este prototipo no está
afiliado a Industrias Haceb S.A.
