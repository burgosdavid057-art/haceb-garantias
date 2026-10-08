<div align="center">

# Asistente de garantías Haceb

**Un asistente que no responde *"sí, está en garantía"*.**
Responde qué queda cubierto, qué no, y cuánto tienes que pagar, con el desglose línea por línea de tu orden de servicio.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3-000000?style=for-the-badge&logo=flask&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local-000000?style=for-the-badge&logo=ollama&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-FF6B35?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Gemini-opcional-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)
![License](https://img.shields.io/badge/licencia-MIT-green?style=for-the-badge)

</div>

> De una orden real de Haceb: *"el compresor será en garantía pero debe asumir
> el valor de la mano de obra"*. De $575.789, la pieza va cubierta y $257.249 de
> servicio calificado no. Un asistente que contesta "sí, está cubierto" y deja
> que llegue esa cuenta hizo más daño que si no hubiera contestado.

Corre **entero en local**. Ninguna orden de servicio —con nombre, cédula,
teléfono y dirección de una persona— sale de la máquina.

Nació en el hackathon **AgentSprint de ReshapeX** (EAFIT, Medellín, julio de 2026),
construido por el equipo **CAPE**: David Burgos y Juan Pablo Pérez Gil.

---

## Contenido

- [Qué hay aquí](#qué-hay-aquí)
- [La regla que hace todo esto posible](#la-regla-que-hace-todo-esto-posible)
- [Las tres cosas que el sistema se niega a hacer](#las-tres-cosas-que-el-sistema-se-niega-a-hacer)
- [Stack](#stack)
- [Cómo correrlo](#cómo-correrlo)
- [Por qué estos modelos](#por-qué-estos-modelos)
- [Los dos auditores](#los-dos-auditores)
- [Estructura](#estructura)
- [Límites conocidos](#límites-conocidos)
- [Autor](#autor)
- [Licencia](#licencia)

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
           │       modelo de visión lee IDENTIFICADORES
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

## Stack

| Capa | Tecnología |
|---|---|
| Servidor web | Flask 3 (sitio, chat con streaming y portal) |
| Agente | Loop propio con 12 herramientas, cliente `openai` contra el endpoint `/v1` de Ollama |
| Modelos locales | `qwen2.5:7b` (agente, vía `Modelfile`), `gemma3:4b` (visión), `bge-m3` (embeddings), `qwen2.5:3b` (validador opcional) |
| Datos | SQLite (`data/haceb.db`, se siembra con `seed.py`) |
| RAG | Catálogo y manuales públicos de Haceb, BM25 + ChromaDB opcional |
| Alternativas en la nube | Groq o Gemini (`google-genai`), solo si se configuran en `.env` |

## Cómo correrlo

Todo local, con [Ollama](https://ollama.com). Requiere Python 3.10+.

**1. Modelos** (una sola vez):

```bash
ollama serve
ollama pull qwen2.5:7b      # modelo del agente (tool calling)
ollama pull gemma3:4b       # visión: leer la foto de la orden
ollama pull bge-m3          # embeddings del RAG (multilingüe)

ollama create haceb-agente    -f Modelfile             # qwen2.5:7b con ventana de 16384 horneada
ollama create haceb-validador -f Modelfile.validador   # opcional: auditor con modelo (qwen2.5:3b)
```

**2. Entorno y dependencias:**

```bash
cp .env.example .env        # ya apunta a Ollama local; no necesita llaves
pip install -r requirements.txt
```

**3. Base y servidor:**

```bash
python seed.py       # 6 equipos, 6 órdenes de servicio y 3 casos en bandeja
python serve.py      # http://localhost:5050
```

`serve.py` siembra la base por su cuenta si está vacía y precalienta el modelo al
arrancar. El portal del asesor queda en `http://localhost:5050/portal`; las
credenciales de la maqueta se imprimen en consola al iniciar.

Para probar la lectura de fotos hay una orden de ejemplo en
[`data/ejemplo_orden_SA-373770.png`](data/ejemplo_orden_SA-373770.png)
(datos personales ficticios).

**4. RAG sobre los manuales (opcional):**

`data/catalog.json` y `data/manuals/` vienen versionados. Los índices
`data/index/` y `data/chroma/` **no** están en el repo (`.gitignore`): se
regeneran así:

```bash
python ingest.py           # opcional: vuelve a bajar catálogo y manuales públicos
python build_index.py      # vectoriza los pasajes de cada manual → data/index/
python build_vectordb.py   # puebla ChromaDB con esos vectores → data/chroma/
```

Sin estos índices el agente busca por BM25, que basta para el flujo de garantías.

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
| gemma4 (8B) | 4/4 | 6–14 s |
| qwen3.5:9b | 4/4 | 12–23 s |
| qwen2.5:3b | 1/4 | 1–4 s |

Un modelo más pequeño responde rápido pero no dispara las herramientas — y sin
herramientas este agente respondería de memoria, que es justo lo que existe para
evitar. La configuración que trae el repo (`Modelfile` y `.env.example`) usa
**qwen2.5:7b** para el agente, que también dispara 4/4 herramientas, y un modelo
de visión aparte (**gemma3:4b**) para leer las órdenes sin mandar el documento a
ninguna nube. Cambiar de modelo es editar `FROM` en el `Modelfile` y
`OLLAMA_VISION_MODEL` en `.env`.

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

```
haceb-garantias-demo/
├── agent/            # motor de cobertura, herramientas, loop, visión, RAG, validador
├── web/              # server.py + templates/ + static/ (sitio, chat y portal)
├── data/             # catalog.json, manuals/, orden de ejemplo (index/ y chroma/ se generan)
├── evals/            # harness adversarial
├── Modelfile         # agente (qwen2.5:7b, num_ctx 16384)
├── Modelfile.validador
├── seed.py  serve.py  ingest.py  build_index.py  build_vectordb.py
└── test_garantias.py  test_validador.py
```

| Archivo | Qué hace |
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
- Los datos personales de las órdenes (incluida la imagen de ejemplo) son **ficticios**.
- La antigüedad se calcula contra una base de equipos sembrada; en producción
  saldría del sistema de ventas de Haceb.
- El mapeo repuesto → parte cubierta es explícito y corto a propósito. Lo que no
  está, va al asesor. Ampliarlo es cargar el catálogo real de repuestos, no
  cambiar el motor.
- El portal usa credenciales fijas en el código: es una maqueta de acceso, no un
  control de acceso.
- Sin `data/index/` ni `data/chroma/` el RAG funciona por BM25 (ver
  [Cómo correrlo](#cómo-correrlo), paso 4).

## Autor

**David Burgos** — desarrollador full-stack + IA, Medellín.
Proyecto del equipo CAPE junto a Juan Pablo Pérez Gil.

- Portafolio: [davidburgos.dev](https://davidburgos.dev)
- GitHub: [@burgosdavid057-art](https://github.com/burgosdavid057-art)
- LinkedIn: [David Burgos](https://www.linkedin.com/in/david-burgos-ab673433a/)

## Licencia

MIT — ver [LICENSE](LICENSE). Datos de producto y manuales: propiedad de
Industrias Haceb S.A., obtenidos de sus canales públicos. Este prototipo no está
afiliado a Industrias Haceb S.A.
