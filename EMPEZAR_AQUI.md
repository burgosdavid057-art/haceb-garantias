# Empezar aquí 👋

Esto es el **asistente de garantías Haceb**: una maqueta del sitio de Haceb con
un chatbot que revisa garantías a partir de la orden de servicio, y un portal
interno donde un asesor decide los casos que el sistema no puede resolver solo.

Todo corre **en tu máquina**. No hay que pagar API ni pedir llaves a nadie.

**Tiempo de instalación: ~20 minutos**, casi todo esperando la descarga del
modelo. Sigue los pasos en orden.

---

## 0. Conseguir el proyecto

Repositorio (privado): **https://github.com/JuanP30/haceb-garantias-demo**

```bash
git clone https://github.com/JuanP30/haceb-garantias-demo.git
cd haceb-garantias-demo
```

Si en vez del repositorio recibiste un **ZIP**, descomprímelo y entra a la
carpeta. Es lo mismo, pero con el `.env` ya incluido.

> Necesitas que te den acceso al repositorio. Si `git clone` te pide usuario y
> contraseña o dice *"Repository not found"*, pídele a Juan que te agregue como
> colaborador.

---

## 1. Requisitos

| | Cómo verificar | Si no lo tienes |
|---|---|---|
| **Python 3.11+** | `python3 --version` | [python.org/downloads](https://www.python.org/downloads/) |
| **Ollama** | `ollama --version` | [ollama.com/download](https://ollama.com/download) |
| **~12 GB de disco** | | para los modelos |
| **16 GB de RAM** | | con 8 GB va a ir muy lento |

> **Mac con chip M1/M2/M3/M4/M5:** funciona tal cual.
> **Windows:** funciona, pero usa `python` en vez de `python3` y
> `.venv\Scripts\activate` en vez de `source .venv/bin/activate`.

---

## 2. Instalación

Abre una terminal **dentro de esta carpeta** y corre esto en orden.

### 2.1 Entorno de Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> Si el ZIP traía una carpeta `.venv`, **bórrala primero**: los entornos de
> Python no se pueden copiar entre máquinas.

### 2.2 Descargar los modelos

Esto es lo que más tarda (~9 GB). Déjalo corriendo:

```bash
ollama pull gemma4
ollama pull bge-m3
```

### 2.3 Crear los modelos del proyecto ⚠️ NO TE SALTES ESTE PASO

```bash
ollama create haceb-agente    -f Modelfile
ollama create haceb-validador -f Modelfile.validador
```

**Por qué importa:** estos `Modelfile` hornean la ventana de contexto (16.384
tokens). Ollama **ignora** ese parámetro cuando se manda desde el código —lo
probamos, está documentado en el `Modelfile`—, así que sin este paso el modelo
carga con 4.096, se queda sin espacio a mitad de camino y **el chat responde
vacío**. Desde afuera parece que el bot no entiende nada.

### 2.4 La configuración

Si **clonaste el repositorio**, crea tu archivo de configuración:

```bash
cp .env.example .env
```

Si recibiste el proyecto **por ZIP**, el `.env` ya viene incluido y puedes
saltarte esto. (No lleva ninguna clave: solo dice qué modelo local usar. Por eso
no está en el repositorio.)

### 2.5 Crear la base de datos

```bash
python seed.py
```

Siembra 6 equipos, 6 órdenes de servicio y 3 casos esperando en la bandeja del
asesor. Puedes volver a correrlo cuando quieras para dejar todo como al
principio.

---

## 3. Verificar que quedó bien

```bash
python test_garantias.py
python test_validador.py
```

Los dos tienen que decir **TODO OK**. Corren en un segundo y no usan el modelo:
si fallan, es que algo del código está mal, no la instalación.

---

## 4. Arrancar

```bash
python serve.py
```

Y abre en el navegador:

| | |
|---|---|
| **Sitio + chatbot** | http://localhost:5050 |
| **Portal del asesor** | http://localhost:5050/portal — usuario `asesor`, clave `haceb2026` |
| Una orden de servicio | http://localhost:5050/orden/SA-373770 |

> **La primera pregunta tarda más.** El servidor calienta el modelo al arrancar;
> dale un minuto antes de probar. Después, cada respuesta toma ~20 segundos.

---

## 5. Qué probar (el recorrido del demo)

### El caso estrella

1. Abre http://localhost:5050 y haz clic en el **botón verde del robot**, abajo
   a la derecha. *(Está exactamente donde el sitio real de Haceb tiene el botón
   de WhatsApp.)*
2. Escribe: **"Tengo la orden SA-373770, ¿por qué me cobraron si está en garantía?"**
3. Mira la tabla que aparece:

   | | | |
   |---|---|---|
   | ✕ | Servicio calificado | $257.249 |
   | ✓ | Compresor hermético | ~~$318.540~~ |
   | ? | Fluido refrigerante | $14.226 |
   | ? | Filtro secador | $7.447 |
   | | **Pagas tú** | **$278.922** |

**Lo que hay que entender de esta tabla** (es todo el proyecto): la garantía de
Haceb **no es sí o no**. Su propio texto legal dice *"1 año correspondiente a
garantía legal y 9 años a garantía suplementaria"*, y esas dos no cubren lo
mismo:

- **Año 1 (legal):** cubre la pieza **y** la mano de obra.
- **Año 2 en adelante (suplementaria):** cubre la pieza. **La mano de obra se cobra.**

Por eso el compresor va cubierto y los $257.249 de servicio no. Es exactamente
lo que decía la factura real que originó este proyecto.

Y los dos **`?`** son la parte de la que más orgullosos estamos: el sistema **no
sabe** si el filtro secador cuenta como parte del compresor, y **no lo adivina**.
Lo manda al asesor.

### La foto de la orden

En el chat, haz clic en el **clip 📎** y sube el archivo
`data/ejemplo_orden_SA-373770.png`. El modelo lee la imagen en tu propia máquina
—ningún documento con datos personales sale a internet— y responde lo mismo.

### El portal del asesor

1. Abre http://localhost:5050/portal en otra pestaña e ingresa.
2. Verás 3 casos esperando. Abre el primero.
3. Fíjate en las líneas **marcadas en rojo**: son las que el sistema no pudo
   respaldar. El rojo no se usa para ninguna otra cosa en todo el portal.
4. Escribe una nota y dale **Aprobar garantía**.
5. **Vuelve a la pestaña del chat y espera unos segundos**: al cliente le llega
   la decisión con la nota que escribiste.

---

## 6. Si algo falla

### El chat responde "No pude generar una respuesta"

El modelo se está quedando sin ventana de contexto. Casi seguro te saltaste el
**paso 2.3**. Verifica:

```bash
ollama list | grep haceb
```

Tienen que aparecer `haceb-agente` y `haceb-validador`. Si no están, corre el
paso 2.3.

### "Tuve un problema consultando la información"

Ollama no está corriendo. En otra terminal:

```bash
ollama serve
```

### El puerto 5050 está ocupado

Cambia el número en `serve.py` (última línea) y en `web/server.py`.

> En Mac, el puerto **5000** lo ocupa AirPlay. Por eso usamos 5050.

### Todo va lentísimo

Verifica que no tengas otros modelos cargados: `ollama ps`. Con 16 GB de RAM
solo cabe uno a la vez. `ollama stop <modelo>` libera.

### El chat no encuentra una orden

Los números válidos están sembrados. Estos son:

| Orden | Qué demuestra |
|---|---|
| `SA-373770` | cobertura parcial + dos líneas sin respaldo ← **el caso del demo** |
| `SA-381204` | equipo de meses: cubierto todo, no paga nada |
| `SA-366015` | equipo de 12 años: sin cobertura |
| `SA-379441` | excluido (el técnico anotó variación de voltaje) |
| `SA-384990` | repuesto que no se puede mapear → va al asesor |
| `SA-386712` | motor cubierto 10 años, mano de obra al cobro |

---

## 7. Mapa del proyecto

Si vas a tocar código, esto es lo que hay:

```
agent/
  garantias.py    ← EL CORAZÓN. Decide qué cubre y qué no, línea por línea.
  literalidad.py  ← Guardián: toda cifra del bot debe estar en la evidencia.
  facturas.py     ← Foto de la orden → identificadores → dictamen.
  db.py           ← Equipos, órdenes y casos (SQLite).
  tools.py        ← Las 12 herramientas que el modelo puede llamar.
  loop.py         ← El prompt del agente y el ciclo de razonamiento.
  llm.py          ← Conexión con Ollama.

web/
  server.py       ← Todas las rutas (sitio, chat, portal).
  templates/      ← Las páginas HTML.
  static/         ← CSS y JavaScript.

seed.py           ← Crea los datos de ejemplo.
serve.py          ← Arranca todo.
Modelfile         ← Configuración del modelo (¡importante!).
```

**Documentos:**

- `README.md` — la explicación técnica completa, con las mediciones.
- `PITCH.md` — el guion de 2 minutos para presentar.

---

## 8. Tres reglas de oro

**1. El modelo nunca aporta cifras.**
Cuando el bot lee una foto, lo único que usamos de esa lectura son
*identificadores* (el número de orden, la serie). Los montos salen siempre de la
base de datos. Lo probamos: el modelo leyó mal el nombre del producto y el
resultado siguió siendo correcto. Si algún día alguien hace que los montos
salgan de lo que el modelo "leyó", se rompe la garantía del sistema.

**2. Lo que no se puede respaldar, no se afirma.**
Ni para bien ni para mal. Un repuesto que no se puede mapear a los términos
publicados sale como `requiere_revision` y va al asesor. Decirle a alguien "no
está cubierto" sin fundamento hace tanto daño como decirle que sí.

**3. Nunca le preguntamos al cliente cuántos años tiene el equipo.**
Sale de la fecha de compra registrada para esa serie. Esa era una falla real de
la versión anterior: le creía al cliente y calculaba la garantía sobre un dato
que nadie había verificado.

---

## 9. Qué falta / ideas para seguir

- **Correr el harness de evaluación completo:** `python -m evals.run`. Son ~35
  preguntas adversariales (incluidas 5 nuevas sobre órdenes de servicio) y da un
  número medido de alucinaciones para cerrar el pitch. Tarda un rato porque usa
  el modelo en cada pregunta.
- **Pulir el clon visual:** falta el footer completo de Haceb, el menú
  desplegable de categorías y la ficha de producto.
- **Más órdenes sembradas:** hoy son 6. Con más variedad el jurado puede probar
  sin caer siempre en el mismo caso.
- **Índice del RAG:** los manuales funcionan por búsqueda de texto (BM25). Para
  búsqueda semántica: `python ingest.py && python build_index.py &&
  python build_vectordb.py`.
- **Ampliar el mapeo repuesto → parte cubierta** (`SINONIMOS` en
  `agent/garantias.py`): mientras menos entradas, más casos van al asesor. Es a
  propósito, pero con el catálogo real de repuestos de Haceb se resolverían
  solos muchos más.

---

## 10. Cosas que ya probamos (para que no las repitas)

| Idea | Qué pasó |
|---|---|
| **WhatsApp como canal** | Funcionaba, pero automatizarlo de forma no oficial arriesga que baneen el número. El canal no era el problema; el problema era que la respuesta fuera correcta. |
| **Un modelo pequeño (qwen2.5:3b) para el chat** | Falla 3 de cada 4 llamadas a herramientas. Sin herramientas el bot responde de memoria, que es justo lo que hay que evitar. |
| **Un modelo pequeño como auditor** | Aprobó **las tres** alucinaciones de la prueba en 1,4 s. Un auditor rápido que aprueba todo no es un auditor. |
| **Un segundo modelo auditando cada respuesta** | Acierta 5/5 pero tarda entre 26 y 86 segundos, y esa espera se le suma al usuario: dos minutos por pregunta. Por eso el guardián es Python puro (0,03 ms). |
| **Pasar `num_ctx` desde el código** | Ollama lo ignora por el endpoint `/v1`. Hay que hornearlo en el `Modelfile`. |
| **El "Copiloto de Producción"** | Se descartó, pero sigue en la rama `copiloto-produccion` por si sirve algo. |

---

## Preguntas

Todo lo técnico está en `README.md`. Lo del pitch, en `PITCH.md`.

Si algo no arranca, lo más probable es que sea el **paso 2.3** (crear los modelos
con los Modelfile). En serio.
