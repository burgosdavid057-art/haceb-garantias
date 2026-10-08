"""
Backend del agente sobre el protocolo OpenAI.

Sirve para cualquier motor que hable ese protocolo:
  - Groq  (nube gratuita, cuota generosa)
  - Ollama (modelo local en la Mac del equipo: sin cuota, sin costo, datos
            que no salen de la red local)

Reusa exactamente las mismas herramientas (agent/tools.py), el mismo prompt de
sistema y la misma clase Traza que el camino Gemini, para que el comportamiento
—y la regla de fundamentacion— sean identicos sin importar el motor.
"""

from __future__ import annotations

import json

from . import llm, tools
from .declarations import herramientas_openai
from .loop import INSTRUCCIONES, MAX_PASOS, Traza

_cliente_cache: dict[str, object] = {}


def _cliente():
    cfg = llm.config_openai()
    clave = cfg["base_url"] + "|" + cfg["api_key"][:8]
    if clave not in _cliente_cache:
        from openai import OpenAI

        _cliente_cache[clave] = OpenAI(
            base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=120.0
        )
    return _cliente_cache[clave], cfg["modelo"]


def _extra(cfg: dict) -> dict:
    """Opciones que Ollama acepta por fuera del estandar OpenAI (ventana de
    contexto). Vacio para Groq, que no las necesita."""
    if cfg.get("proveedor") == "ollama" and cfg.get("num_ctx"):
        return {"extra_body": {"options": {"num_ctx": cfg["num_ctx"]}}}
    return {}


import re

# Intencion explicita de radicar/formalizar un reclamo de garantia. Se exige un
# verbo claro para no crear un caso cada vez que alguien solo pregunta por su
# orden: radicar tiene efecto (deja un caso en la bandeja del asesor).
_INTENCION_RADICAR = re.compile(
    r"\b(radic\w*|formaliz\w*|reclam\w*|escal\w*|"
    r"abr[ei]\w*\s+(un\s+|el\s+|mi\s+)?(caso|solicitud|reclamo)|"
    r"registr\w*\s+(el\s+|mi\s+)?(caso|reclamo|solicitud)|"
    r"present\w*\s+(el\s+|un\s+|mi\s+)?(reclamo|garant\w+))",
    re.I,
)


def _preproceso_orden(mensaje: str, mensajes: list, traza: Traza) -> bool:
    """Router deterministico para ordenes de servicio.

    Los modelos locales pequeños no eligen de forma fiable la herramienta
    correcta cuando el cliente da un numero de orden (SA-...). Como el desglose
    de cobertura y la radicacion son las funciones estrella, no se dejan al azar
    del modelo: si el mensaje trae un numero de orden se llama la herramienta y
    se inyecta el resultado como un tool-call ya resuelto, para que el modelo
    solo redacte.

    Dos caminos, segun la intencion del mensaje:
      - "quiero radicar / formalizar / reclamar SA-..."  -> radicar_garantia
        (deja el caso en la bandeja del asesor y devuelve el ticket).
      - cualquier otra mencion de la orden                -> consultar_orden_servicio
        (solo el desglose de cobertura, sin efecto).
    """
    m = re.search(r"\bSA[-\s]?(\d{4,})\b", mensaje, re.I)
    if not m:
        return False
    numero = "SA-" + m.group(1)

    if _INTENCION_RADICAR.search(mensaje):
        resultado = tools.radicar_garantia(numero)
        if resultado.get("radicado"):
            nombre, args = "radicar_garantia", {"numero_orden": numero}
        else:
            # No se pudo radicar (orden no hallada o no evaluable): cae al
            # camino de consulta para que el modelo explique con la evidencia.
            resultado = tools.consultar_orden_servicio(numero)
            if not resultado.get("encontrada"):
                return False
            nombre, args = "consultar_orden_servicio", {"numero": numero}
    else:
        resultado = tools.consultar_orden_servicio(numero)
        if not resultado.get("encontrada"):
            return False
        nombre, args = "consultar_orden_servicio", {"numero": numero}

    traza.registrar(nombre, args, resultado)
    tcid = "call_" + nombre + "_auto"
    mensajes.append({
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": tcid, "type": "function",
            "function": {"name": nombre, "arguments": json.dumps(args)},
        }],
    })
    mensajes.append({
        "role": "tool",
        "tool_call_id": tcid,
        "content": json.dumps(resultado, ensure_ascii=False, default=str),
    })
    return True


def _mensajes_iniciales(historial, mensaje):
    # historial es una lista de mensajes estilo OpenAI (dicts). Si viene vacio o
    # de otro backend (Content de Gemini), arrancamos limpio con el system.
    ok = isinstance(historial, list) and all(isinstance(m, dict) for m in (historial or []))
    if historial and ok:
        mensajes = list(historial)
    else:
        mensajes = [{"role": "system", "content": INSTRUCCIONES}]
    mensajes.append({"role": "user", "content": mensaje})
    return mensajes


def responder(mensaje: str, historial: list | None = None) -> tuple[str, Traza, list]:
    """Loop de tool calling estilo OpenAI. Mismo contrato que loop.responder."""
    cliente, modelo = _cliente()
    extra = _extra(llm.config_openai())
    mensajes = _mensajes_iniciales(historial, mensaje)
    herramientas = herramientas_openai()
    traza = Traza()
    _preproceso_orden(mensaje, mensajes, traza)  # fuerza el desglose si hay orden

    for _ in range(MAX_PASOS):
        resp = cliente.chat.completions.create(
            model=modelo,
            messages=mensajes,
            tools=herramientas,
            tool_choice="auto",
            temperature=0.2,
            **extra,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            texto = (msg.content or "").strip() or (
                "No pude generar una respuesta. Intenta reformular la pregunta."
            )
            mensajes.append({"role": "assistant", "content": texto})
            return texto, traza, mensajes

        # El modelo pidio herramientas: registrar el turno del asistente y correrlas.
        mensajes.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            try:
                argumentos = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            resultado = tools.ejecutar(tc.function.name, argumentos)
            traza.registrar(tc.function.name, argumentos, resultado)
            mensajes.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })

    return (
        "Me enrede consultando la informacion y prefiero no adivinar. "
        "Reformula la pregunta o pide hablar con servicio tecnico.",
        traza,
        mensajes,
    )


def responder_stream(mensaje: str, historial: list | None = None):
    """Igual que `responder`, pero va emitiendo lo que pasa mientras pasa.

    Emite tuplas (tipo, dato):
        ("herramienta", nombre)      antes de ejecutar cada herramienta
        ("texto", fragmento)         la respuesta final, a medida que se genera
        ("fin", (texto, traza, mensajes))

    El tiempo total no baja, pero la espera percibida sí: con el modelo local un
    turno tarda ~25 s y sin esto la pantalla está muerta todo ese rato. Además
    deja ver al agente trabajar, que es justo lo que hay que mostrar — qué
    herramienta consultó antes de afirmar nada.
    """
    cliente, modelo = _cliente()
    extra = _extra(llm.config_openai())
    mensajes = _mensajes_iniciales(historial, mensaje)
    herramientas = herramientas_openai()
    traza = Traza()
    _preproceso_orden(mensaje, mensajes, traza)  # fuerza el desglose si hay orden

    for _ in range(MAX_PASOS):
        flujo = cliente.chat.completions.create(
            model=modelo, messages=mensajes, tools=herramientas,
            tool_choice="auto", temperature=0.2, stream=True, **extra,
        )

        texto_parcial = []
        # Los tool_calls llegan troceados: el nombre en un chunk y los argumentos
        # repartidos entre varios. Se acumulan por índice hasta cerrar el turno.
        pendientes: dict[int, dict] = {}

        for chunk in flujo:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if getattr(delta, "content", None):
                texto_parcial.append(delta.content)
                yield "texto", delta.content

            for tc in (getattr(delta, "tool_calls", None) or []):
                acc = pendientes.setdefault(
                    tc.index, {"id": "", "nombre": "", "argumentos": ""})
                if tc.id:
                    acc["id"] = tc.id
                if tc.function and tc.function.name:
                    acc["nombre"] = tc.function.name
                if tc.function and tc.function.arguments:
                    acc["argumentos"] += tc.function.arguments

        texto = "".join(texto_parcial).strip()

        if not pendientes:
            texto = texto or "No pude generar una respuesta. Intenta reformular la pregunta."
            mensajes.append({"role": "assistant", "content": texto})
            yield "fin", (texto, traza, mensajes)
            return

        mensajes.append({
            "role": "assistant",
            "content": texto,
            "tool_calls": [
                {"id": a["id"], "type": "function",
                 "function": {"name": a["nombre"], "arguments": a["argumentos"]}}
                for a in pendientes.values()
            ],
        })
        for a in pendientes.values():
            yield "herramienta", a["nombre"]
            try:
                argumentos = json.loads(a["argumentos"] or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            resultado = tools.ejecutar(a["nombre"], argumentos)
            traza.registrar(a["nombre"], argumentos, resultado)
            mensajes.append({
                "role": "tool", "tool_call_id": a["id"],
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })

    yield "fin", (
        "Me enrede consultando la informacion y prefiero no adivinar. "
        "Reformula la pregunta o pide hablar con servicio tecnico.",
        traza, mensajes,
    )


INSTRUCCIONES_VALIDADOR = None  # se importa perezosamente para evitar ciclos


def validar(respuesta: str, evidencia_json: str) -> dict:
    """Validador sobre el mismo motor OpenAI. Devuelve el mismo dict que
    agent.validator.validar, con la misma regla de reconciliacion."""
    from .validator import INSTRUCCIONES as INSTR_VAL, _extraer_json

    if not evidencia_json or evidencia_json == "[]":
        # Sin herramientas = respuesta conversacional (saludo, aclaracion o
        # rechazo de tema fuera de alcance). No hay datos de producto que auditar.
        return {
            "verificado": True,
            "fundamentada": True,
            "afirmaciones_sin_respaldo": [],
            "explicacion": "Respuesta conversacional, sin datos de producto que verificar.",
        }

    cliente, _ = _cliente()
    contenido = (
        f"EVIDENCIA (salida de las herramientas):\n{evidencia_json}\n\n"
        f"RESPUESTA a auditar:\n{respuesta}"
    )
    try:
        resp = cliente.chat.completions.create(
            model=llm.modelo_validador(),
            messages=[
                {"role": "system", "content": INSTR_VAL},
                {"role": "user", "content": contenido},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            **_extra(llm.config_openai()),
        )
        datos = _extraer_json(resp.choices[0].message.content or "")
    except Exception as e:  # noqa: BLE001
        return {
            "verificado": False,
            "fundamentada": None,
            "afirmaciones_sin_respaldo": [],
            "explicacion": f"No se pudo validar ({type(e).__name__}).",
        }

    if not isinstance(datos, dict) or "fundamentada" not in datos:
        return {
            "verificado": False,
            "fundamentada": None,
            "afirmaciones_sin_respaldo": [],
            "explicacion": "El validador no devolvio un dictamen legible.",
        }

    sin_respaldo = datos.get("afirmaciones_sin_respaldo") or []
    fundamentada = bool(datos.get("fundamentada"))
    if not fundamentada and not sin_respaldo:
        fundamentada = True
        explicacion = "Sin afirmaciones sin respaldo identificadas."
    else:
        explicacion = datos.get("explicacion", "")

    return {
        "verificado": True,
        "fundamentada": fundamentada,
        "afirmaciones_sin_respaldo": sin_respaldo,
        "explicacion": explicacion,
    }
