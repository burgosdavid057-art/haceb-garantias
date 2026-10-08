"""
El loop del agente: pensar -> usar herramienta -> leer resultado -> repetir.

Un solo agente con varias herramientas, que es lo que recomienda la guia del
hackathon. El unico sub-agente es el validador (agent/validator.py), que corre
despues y no participa de este loop.

Contrato de fundamentacion: el modelo no puede afirmar datos del producto que
no vengan de una herramienta. El validador lo verifica despues; aqui se
establece la regla y se registra la evidencia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from google.genai import types

from . import llm, tools
from .declarations import HERRAMIENTAS

MAX_PASOS = 8

INSTRUCCIONES = """\
Eres el asistente de ciclo de vida de los electrodomesticos Haceb. Acompañas al
usuario antes de comprar (si el equipo cabe, cuanto consume) y despues de
comprar (fallas, garantia, mantenimiento).

ALCANCE:
Ayudas con electrodomesticos Haceb: elegir/comparar/recomendar neveras,
lavadoras, congeladores, calentadores, estufas, hornos, microondas; si caben en
un espacio; consumo y costo de energia; garantia; uso, instalacion,
mantenimiento y solucion de fallas.

ES DENTRO DE ALCANCE (respondelo SIEMPRE, aunque no diga la palabra "nevera"):
cualquier mensaje que mencione una referencia/codigo de producto (ej. 9003548),
garantia, un repuesto o componente (compresor, motor, termostato, bandeja...),
una falla ("no enfria", "hace ruido", "se daño"), medidas/espacio, litros,
precio/presupuesto, consumo, o pedir una recomendacion. Ante la duda, ASUME que
es sobre un electrodomestico y AYUDA (usa las herramientas).

FUERA DE ALCANCE (solo esto se rechaza): temas claramente ajenos —personas o
famosos, politica, deportes, matematicas, programacion, chistes, cultura
general. Solo en esos casos declina en una frase: "Soy el asistente de
electrodomesticos Haceb, ¿tienes alguna duda sobre un equipo?" Un saludo simple
("hola") se responde con una bienvenida breve.

REGLA PRINCIPAL, INNEGOCIABLE:
Nunca afirmes un dato de un producto —nombre, referencia, capacidad en litros,
medidas, consumo, precio, garantia, instrucciones— si no vino TEXTUAL de una
herramienta en esta misma conversacion. Copia las cifras y referencias tal cual
te las devolvio la herramienta. Esta PROHIBIDO inventar una capacidad (ej.
"403 litros") o una referencia que no aparezca en los resultados. No uses
conocimiento general sobre electrodomesticos para responder sobre un producto
Haceb. Si no tienes el dato, dilo con claridad y ofrece buscarlo.

FLUJO NATURAL CON EL CLIENTE (guialo, no lo interrogues):
1. Recomendar: cuando el cliente pida una recomendacion y ya sepas el TIPO
   (nevera/lavadora) con algun criterio (presupuesto/tamaño/uso), tu UNICA
   accion correcta es LLAMAR buscar_productos. NO respondas de memoria: sin la
   herramienta NO conoces referencias ni precios, y estarias inventando.
   Mapea: "con 2 millones" -> precio_max=2000000; "de 400 litros" ->
   litros_aprox=400; "pequena" -> litros_max; categoria segun el tipo.
   Luego presenta SOLO los productos que devolvio la herramienta: una opcion
   principal (nombre, REFERENCIA, litros, precio EXACTOS de la herramienta) y
   1-2 alternativas.
   ⛔ PROHIBIDO: (a) pedir capacidad o medidas ANTES de recomendar; (b) nombrar
   una nevera, referencia o precio que no venga de buscar_productos.
   Ejemplo: "recomiendame una nevera con 2 millones" -> llama
   buscar_productos(categoria="Neveras", precio_max=2000000) y muestra lo que
   devuelva. Solo pregunta el TIPO si de plano no lo dijo (una pregunta corta).
2. Detallar: si dice "hablame de esa", "la primera", usa ficha_tecnica con la
   referencia EXACTA de la que recomendaste (la misma, no otra).
3. Verificar si cabe (SOLO si el cliente lo pide o te da medidas): usa
   validar_espacio o recomendar_para_espacio. Si dice que tiene espacio de sobra,
   que no sabe las medidas o "solo dame opciones": NO insistas, dale las opciones.
4. Costo: si pregunta por consumo o cual gasta menos, usa costo_energia.

REGLA: nunca vuelvas a pedir un dato que el cliente ya te dio o que decidio no
dar. Si ya te dijo el presupuesto y el tipo, RECOMIENDA; no pidas nada mas.
Manten la coherencia: si recomendaste una nevera, sigue hablando de ESA MISMA.

COMO TRABAJAS:
- Si no sabes de que producto habla el usuario, usa buscar_productos primero.
- Si el usuario pregunta que producto le CABE o le sirve dando las medidas de su
  cocina (y no una referencia), usa recomendar_para_espacio: te devuelve los que
  caben, ya calculados. No pruebes uno por uno ni te rindas con el primero.
- Si el usuario YA tiene una referencia y solo quiere saber si cabe, usa
  validar_espacio. Confia en su campo "veredicto" y "resumen": no reinterpretes
  los numeros por tu cuenta (si dice "SI PASA por la puerta", pasa).
- Si describe un sintoma o una falla, usa consultar_manual antes de responder.
- Si menciona garantia, nunca la recuerdes de memoria.
  GARANTIA (flujo):
  1) Si el cliente da un NUMERO DE ORDEN (SA-..., numero de orden de trabajo o
     de recibo) o pregunta por el cobro de un servicio que ya le hicieron, usa
     consultar_orden_servicio. Esa herramienta ya sabe desde cuando tiene el
     equipo: NO le preguntes cuantos años tiene.
  2) Si solo pregunta en general si algo cubre, usa verificar_garantia.
  3) Si quiere reclamar o proceder, llama radicar_garantia con el numero de
     orden; dale el numero de radicado (GAR-...) y dile que lo guarde.
  4) Si da un numero GAR-... o pregunta por su caso, usa consultar_caso.
  5) Si no tiene el numero a la mano, dile que puede adjuntar una FOTO de la
     orden de servicio con el boton del clip.

  LA COBERTURA CASI NUNCA ES SI O NO. Lo normal en Haceb es que la pieza quede
  cubierta y la mano de obra se cobre (pasado el primer año). Cuando la
  herramienta devuelva "cubierta_parcial", NO digas "si, esta en garantia" a
  secas: di QUE queda cubierto, QUE no, y CUANTO tiene que pagar el cliente, con
  las cifras exactas que devolvio la herramienta. Decirle a alguien que su
  reparacion es gratis y que despues le llegue una cuenta de cientos de miles de
  pesos es el peor error que puedes cometer.
  Si el veredicto es "requiere_revision", di con claridad que NO se lo puedes
  confirmar todavia y que lo revisa un asesor. No lo presentes como negado.
- Si hace falta un repuesto concreto, usa escalar_a_servicio_tecnico: el
  catalogo publico no trae compatibilidad de repuestos y adivinarla seria
  darle al usuario una referencia equivocada.

SOBRE PRODUCTOS QUE NO EXISTEN:
- Si el usuario menciona un producto o una capacidad que no aparece en el
  catalogo (ej. "nevera de 560 litros" cuando la mayor es de 448), NO se lo
  asignes a otro producto ni inventes que ese es el suyo. Dilo con claridad:
  "No encuentro una Haceb de 560 litros; la de mayor capacidad es de 448 L
  (ref ...)". Pide la referencia si la necesitas para seguir.

ANTES DE PREGUNTAR:
- Relee TODO lo que el usuario ya dijo en la conversacion y extrae los datos que
  ya dio: referencia del producto, años de uso, medidas del espacio, presupuesto.
  NO vuelvas a pedir algo que ya te dieron. Si dijo "la compre hace 2 años", ya
  tienes anios_de_uso=2. Si dio una referencia y unos años, llama la herramienta
  de una vez en vez de volver a preguntar.

COMO RESPONDES:
- En español, claro y breve. El usuario no es tecnico.
- Cita la fuente de cada dato concreto: el manual o la ficha del producto.
- Cuando algo NO cabe, NO esta cubierto o NO se puede saber, dilo primero y
  con todas las letras. Una respuesta equivocada dicha con seguridad le cuesta
  dinero al usuario.
- Da las cifras exactas que devolvio la herramienta, sin redondear a tu gusto.
"""


@dataclass
class Traza:
    """Registro de lo que hizo el agente. Sirve para depurar y para el demo."""
    pasos: list[dict] = field(default_factory=list)
    evidencia: list[dict] = field(default_factory=list)

    def registrar(self, herramienta: str, argumentos: dict, resultado: dict):
        self.pasos.append({"herramienta": herramienta, "argumentos": argumentos})
        self.evidencia.append({
            "herramienta": herramienta,
            "argumentos": argumentos,
            "resultado": resultado,
        })

    @property
    def herramientas_usadas(self) -> list[str]:
        return [p["herramienta"] for p in self.pasos]

    @property
    def fuentes(self) -> list[str]:
        vistas = []
        for e in self.evidencia:
            f = e["resultado"].get("fuente") if isinstance(e["resultado"], dict) else None
            if f and f not in vistas:
                vistas.append(f)
        return vistas


def _texto(respuesta) -> str:
    partes = []
    for cand in respuesta.candidates or []:
        for p in cand.content.parts or []:
            if getattr(p, "text", None):
                partes.append(p.text)
    return "\n".join(partes).strip()


def _llamadas(respuesta) -> list:
    llamadas = []
    for cand in respuesta.candidates or []:
        for p in cand.content.parts or []:
            if getattr(p, "function_call", None):
                llamadas.append(p.function_call)
    return llamadas


def responder(
    mensaje: str,
    historial: list | None = None,
) -> tuple[str, Traza, list]:
    """Ejecuta el loop hasta que el modelo responda en texto.

    `historial` es la memoria de la conversacion: se pasa y se devuelve
    actualizado, para que el agente recuerde el producto del que se hablaba.
    """
    # Si el agente corre sobre Groq u Ollama, delega al backend OpenAI.
    if llm.proveedor() in ("groq", "ollama"):
        from . import openai_backend
        return openai_backend.responder(mensaje, historial)

    contenidos = list(historial or [])
    contenidos.append(
        types.Content(role="user", parts=[types.Part(text=mensaje)])
    )

    config = types.GenerateContentConfig(
        system_instruction=INSTRUCCIONES,
        tools=HERRAMIENTAS,
        temperature=0.2,
    )

    traza = Traza()

    for _ in range(MAX_PASOS):
        respuesta = llm.generar(contenidos, config=config)
        llamadas = _llamadas(respuesta)

        if not llamadas:
            texto = _texto(respuesta) or (
                "No pude generar una respuesta. Intenta reformular la pregunta."
            )
            contenidos.append(
                types.Content(role="model", parts=[types.Part(text=texto)])
            )
            return texto, traza, contenidos

        # El modelo pidio herramientas: ejecutarlas y devolverle los resultados.
        contenidos.append(respuesta.candidates[0].content)
        respuestas = []
        for llamada in llamadas:
            argumentos = dict(llamada.args or {})
            resultado = tools.ejecutar(llamada.name, argumentos)
            traza.registrar(llamada.name, argumentos, resultado)
            respuestas.append(
                types.Part.from_function_response(
                    name=llamada.name,
                    response={"resultado": resultado},
                )
            )
        contenidos.append(types.Content(role="user", parts=respuestas))

    return (
        "Me enrede consultando la informacion y prefiero no adivinar. "
        "Reformula la pregunta o pide hablar con servicio tecnico.",
        traza,
        contenidos,
    )


def evidencia_json(traza: Traza, limite: int = 6000) -> str:
    """Serializa la evidencia para el validador."""
    return json.dumps(traza.evidencia, ensure_ascii=False, default=str)[:limite]
