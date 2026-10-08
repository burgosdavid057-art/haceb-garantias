# Guion del pitch — 2 minutos

> Objetivo: que el jurado se lleve **un momento** y **un número**.
> El número es **$257.249**. El momento es la tabla del desglose.

Quién maneja el demo y quién narra se decide antes. Nadie improvisa.

**Antes de empezar:** `python serve.py`, chat abierto en una pestaña, `/portal`
logueado en otra, y la imagen de la orden lista para arrastrar.

---

## 1. El problema, con la factura en la mano (0:00–0:25)

Se muestra una orden de servicio real de Haceb y se lee la observación del
técnico, textual:

> *"Se le informa a usuario que el compresor será en garantía pero debe asumir
> el valor de la mano de obra."*

> "Esta persona tenía razón en las dos cosas: su compresor **sí** estaba en
> garantía, y **sí** le tocó pagar $257.249. Ahora imaginen que antes de esa
> visita le hubiera preguntado a un chatbot. Le habría dicho *'sí, tu compresor
> tiene 10 años de garantía'* — y habría sido verdad, y habría estado
> completamente equivocado."

## 2. Qué construimos, en una frase (0:25–0:40)

> "Construimos el asistente que **no** contesta sí o no. Contesta qué queda
> cubierto, qué no, y cuánto vas a pagar. Y cuando no lo puede respaldar, no lo
> inventa: se lo pasa a una persona."

## 3. Demo — el momento que se recuerda (0:40–1:40)

Estamos en el sitio de Haceb. En el lugar exacto donde está el botón de
WhatsApp, hay un botón de bot.

1. **La foto.** Se arrastra la foto de la orden al chat.
   > "Nadie se sabe su número de orden. El papel sí lo tiene."

2. **La tabla.** Aparece el desglose:

   | | | |
   |---|---|---|
   | ✕ | Servicio calificado | $257.249 |
   | ✓ | Compresor hermético | ~~$318.540~~ |
   | ? | Fluido refrigerante | $14.226 |
   | ? | Filtro secador | $7.447 |
   | | **Pagas tú** | **$278.922** |

   > "Esto no lo redactó el modelo. Lo calculó Python y se dibujó desde el
   > cálculo. Si el modelo escribiera otra cosa, la tabla lo desmiente."

3. **El clímax — los signos de interrogación.**
   > "Miren estas dos líneas. El sistema **no sabe** si el filtro secador entra
   > como parte del compresor. Y no lo adivina. Podría haber dicho que sí y
   > sonar servicial, o que no y sonar seguro. Hace lo único honesto: dice que
   > no lo puede confirmar y **se lo pasa a un asesor**."

4. **El portal.** Se cambia de pestaña.
   > "Y aquí está ese asesor. El caso le llegó con la orden, la fecha de compra
   > real, el texto legal y las dos líneas dudosas marcadas en rojo. No le
   > llegó una conclusión: le llegó el trabajo hecho para que él decida."

   Se aprueba con una nota. El estado cambia y el cliente puede consultarlo con
   su número GAR-.

## 4. Cómo está construido (1:40–1:55)

> "Todo corre **local**, en esta máquina. Un documento con la cédula, el
> teléfono y la dirección de una persona no sale a ninguna nube.
>
> Y hay una regla que sostiene el resto: **el modelo no aporta hechos**. Lo que
> lee de la foto son identificadores —el número de orden, la serie— y solo
> sirven para *encontrar* la orden. Las cifras salen siempre de la base.
> De hecho, en una prueba el modelo leyó mal el nombre del producto. El
> resultado siguió siendo correcto."

## 5. El número (1:55–2:00)

> "Y no lo afirmamos: lo medimos. Cada cifra que el asistente escribe tiene que
> aparecer en la evidencia de las herramientas. Ese chequeo corre en **0,03
> milisegundos**, sin modelo, y atrapa los montos y los años inventados."

---

## Por qué esto le pega a este jurado

ReshapeX vende *"the knowledge grounding layer for industrial AI"* con
*"route uncertain answers to experts rather than guessing"*. Este proyecto es
esa frase, funcionando:

- **El grounding**: el motor de cobertura lee los términos legales publicados
  por Haceb, no la memoria del modelo.
- **El routing**: `requiere_revision` no es un estado de error, es el producto.
  Lo que no se puede respaldar llega a un humano con la evidencia lista.
- **La medición**: el guardián de literalidad es determinista y se puede correr
  delante de ellos.

No es un chatbot de catálogo. Es la capa que decide **cuándo callarse**.

---

## Preguntas del jurado — respuestas listas

**¿Y si el modelo lee mal la factura?**
Pasó, y está medido: leyó "Nevera Frost 4ra Litros" en vez de "No Frost 404
Litros". El dictamen salió correcto porque el nombre del producto sale de la
base. La lectura solo aporta identificadores; si uno sale mal, no encuentra la
orden y el sistema pregunta. Un monto mal leído se le cobra a alguien; un
número de orden mal leído no hace daño.

**¿Cómo saben que el cliente no miente con la antigüedad?**
No se le pregunta. La fecha de compra sale de la serie del equipo. Ese fue un
hueco real que tenía la versión anterior de esto: le creía al cliente.

**¿Por qué un modelo local y no GPT?**
Por el documento. Una orden de servicio trae nombre, cédula, teléfono y
dirección. Y porque se midió: gemma4 acierta 4 de 4 llamadas a herramientas en
6–14 segundos en esta máquina.

**¿Qué pasa si el catálogo de repuestos crece?**
El mapeo repuesto → parte cubierta es explícito y corto a propósito. Ampliarlo
es cargar el catálogo real de Haceb, no cambiar el motor. Y mientras no esté, lo
que falta va al asesor en vez de resolverse mal.

**¿Qué está mockeado?**
El sitio (es una maqueta visual) y los datos personales (ficticios). El catálogo
son 47 productos reales de la API pública de Haceb con sus textos de garantía
reales — de ahí sale la regla del año legal. El motor, el guardián y el portal
funcionan de verdad.

**¿Por qué descartaron WhatsApp?**
Porque el canal no era el problema. El problema era que la respuesta fuera
correcta. Un botón en la web de Haceb llega al mismo cliente sin arriesgar un
número baneado por automatizar WhatsApp de forma no oficial.

---

## Checklist antes de presentar

- [ ] `ollama list` muestra `haceb-agente`. El primer turno **precalienta** el
      modelo: mandar una pregunta cualquiera 5 minutos antes.
- [ ] `python test_garantias.py` → 6/6.
- [ ] La imagen de la orden lista para arrastrar.
- [ ] `/portal` logueado en la otra pestaña.
- [ ] Ensayado el momento de los `?`. Es el clímax, no se improvisa.
