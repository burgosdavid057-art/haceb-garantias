"""
Servidor unico del demo: sitio publico, chat del agente y portal del asesor.

    python -m web.server        ->  http://localhost:5050

Tres superficies, un solo proceso:

    /                 portada (clon visual)
    /servicios        catalogo de servicios (clon visual)
    /portal           bandeja del asesor de garantias
    /api/chat         el agente, con memoria por sesion
    /api/chat/imagen  foto de una orden de servicio -> dictamen
    /api/casos        lectura y actualizacion de la bandeja

El sitio publico es una MAQUETA: reproduce el aspecto de haceb.com para que el
demo se vea en su contexto real, pero solo el chat y el portal hacen algo.
Los botones de compra no llevan a ninguna parte a proposito.
"""

from __future__ import annotations

import base64
import json
import secrets

from flask import Flask, Response, jsonify, render_template, request, session

from agent import db, facturas, garantias, loop, validator

app = Flask(__name__)
# El demo corre en local; la sesion solo separa conversaciones entre pestañas.
app.secret_key = secrets.token_hex(16)

# Memoria de conversacion por sesion del navegador. En produccion iria a la
# base; para el demo, en memoria del proceso basta.
_memoria: dict[str, list] = {}

# Credenciales del portal. Es una maqueta: el control de acceso real lo daria
# el directorio corporativo de Haceb, no un dict.
# ponytail: usuario quemado a proposito, no hay gestion de cuentas en un demo.
ASESORES = {"asesor": "haceb2026", "juliana": "haceb2026"}


# --- Sitio publico -------------------------------------------------------

@app.get("/")
def portada():
    return render_template("index.html", activo="inicio")


@app.get("/servicios")
def servicios():
    return render_template("servicios.html", activo="servicios")


@app.get("/asistente")
def asistente():
    """Página dedicada, a pantalla completa, para contactar al asistente."""
    return render_template("asistente.html", activo="asistente")


@app.get("/orden/<numero>")
def ver_orden(numero: str):
    """Render de una orden de servicio, con el mismo aspecto del papel.

    Sirve para dos cosas: que el cliente vea su orden, y para producir las
    imagenes de prueba que se suben al chat durante el demo.
    """
    orden = db.orden_por_numero(numero)
    if not orden:
        return render_template("404.html", numero=numero), 404
    equipo = db.equipo_por_serie(orden["serie"])
    return render_template("orden.html", orden=orden, equipo=equipo)


# --- API del chat --------------------------------------------------------

def _sesion() -> str:
    if "sid" not in session:
        session["sid"] = secrets.token_hex(8)
    return session["sid"]


def _desglose_de(traza) -> dict | None:
    """Recupera el desglose completo de la orden que tocó el agente.

    Al modelo se le manda una vista compacta del dictamen (ver
    tools.consultar_orden_servicio), así que aquí se recalcula el completo
    desde la base. Es puro Python, sin modelo: el mismo cálculo da el mismo
    resultado, y la tabla que ve el cliente no depende de lo que el modelo
    haya decidido repetir.
    """
    for e in reversed(traza.evidencia):
        if e["herramienta"] not in ("consultar_orden_servicio", "radicar_garantia"):
            continue
        cita = (e["resultado"] or {}).get("numero_cita") or e["argumentos"].get("numero_orden")
        orden = db.orden_por_numero(cita or "")
        if not orden:
            continue
        equipo = db.equipo_por_serie(orden["serie"])
        if equipo:
            return garantias.evaluar(orden, equipo)
    return None


def _responder(texto: str) -> dict:
    """Corre el agente conservando la memoria de esta sesion."""
    sid = _sesion()
    historial = _memoria.get(sid, [])
    respuesta, traza, historial = loop.responder(texto, historial)
    _memoria[sid] = historial

    dictamen = validator.validar(respuesta, loop.evidencia_json(traza))
    return {
        "reply": validator.aplicar(respuesta, dictamen),
        "herramientas": traza.herramientas_usadas,
        "fuentes": traza.fuentes,
        "dictamen": _desglose_de(traza),
        "verificado": bool(dictamen.get("verificado") and dictamen.get("fundamentada")),
        "sin_respaldo": dictamen.get("afirmaciones_sin_respaldo") or [],
    }


@app.post("/api/chat")
def api_chat():
    datos = request.get_json(silent=True) or {}
    texto = (datos.get("mensaje") or "").strip()

    if not texto:
        return jsonify(reply="Cuéntame qué necesitas con tu electrodoméstico Haceb.")

    if texto.lower() in ("reiniciar", "reset", "/reset"):
        _memoria.pop(_sesion(), None)
        return jsonify(reply="Listo, empezamos de nuevo. ¿En qué te ayudo?")

    try:
        return jsonify(**_responder(texto))
    except Exception as e:  # noqa: BLE001
        app.logger.exception("fallo del agente")
        return jsonify(
            reply="Tuve un problema consultando la información. Intenta de nuevo.",
            error=type(e).__name__,
        ), 200


@app.post("/api/chat/stream")
def api_chat_stream():
    """El mismo agente, emitiendo lo que hace mientras lo hace (SSE).

    El tiempo total no cambia —el modelo local tarda lo que tarda— pero el
    usuario ve la primera palabra a los pocos segundos en vez de mirar una
    pantalla muerta 25 segundos. Y de paso ve QUÉ herramienta se consultó antes
    de que el agente afirme nada, que es el punto del proyecto.
    """
    from agent import openai_backend

    datos = request.get_json(silent=True) or {}
    texto = (datos.get("mensaje") or "").strip()
    sid = _sesion()

    def evento(tipo: str, dato) -> str:
        return f"data: {json.dumps({'tipo': tipo, 'dato': dato}, ensure_ascii=False)}\n\n"

    def generar():
        if not texto:
            yield evento("fin", {"reply": "Cuéntame qué necesitas con tu equipo Haceb."})
            return
        if texto.lower() in ("reiniciar", "reset", "/reset"):
            _memoria.pop(sid, None)
            yield evento("fin", {"reply": "Listo, empezamos de nuevo. ¿En qué te ayudo?"})
            return

        try:
            historial = _memoria.get(sid, [])
            for tipo, dato in openai_backend.responder_stream(texto, historial):
                if tipo in ("texto", "herramienta"):
                    yield evento(tipo, dato)
                    continue

                respuesta, traza, historial = dato
                _memoria[sid] = historial
                # El caso recién radicado se ata a esta sesión, para poder
                # devolverle aquí mismo la decisión del asesor.
                for e in traza.evidencia:
                    tk = (e["resultado"] or {}).get("ticket")
                    if e["herramienta"] == "radicar_garantia" and tk:
                        db.marcar_sesion(tk, sid)

                dictamen = validator.validar(respuesta, loop.evidencia_json(traza))
                yield evento("fin", {
                    "reply": validator.aplicar(respuesta, dictamen),
                    "herramientas": traza.herramientas_usadas,
                    "fuentes": traza.fuentes,
                    "dictamen": _desglose_de(traza),
                    "verificado": bool(dictamen.get("verificado")
                                       and dictamen.get("fundamentada")),
                    "sin_respaldo": dictamen.get("afirmaciones_sin_respaldo") or [],
                })
        except Exception as e:  # noqa: BLE001
            app.logger.exception("fallo del agente (stream)")
            yield evento("fin", {
                "reply": "Tuve un problema consultando la información. Intenta de nuevo.",
                "error": type(e).__name__,
            })

    return Response(generar(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/novedades")
def api_novedades():
    """Decisiones del asesor que este cliente todavía no ha visto en su chat."""
    novedades = db.novedades_de_sesion(session.get("sid", ""))
    return jsonify(novedades=[{
        "ticket": c["ticket"],
        "estado": c["estado"],
        "nota": c["nota_asesor"],
        "asesor": c["asesor"],
        "dictamen": c["dictamen"],
    } for c in novedades])


@app.post("/api/chat/imagen")
def api_chat_imagen():
    """Foto de una orden de servicio -> dictamen de cobertura.

    La lectura corre en el modelo local, asi que la imagen de un documento con
    datos personales no sale de la maquina.
    """
    datos = request.get_json(silent=True) or {}
    b64 = (datos.get("imagen") or "").split(",")[-1]
    if not b64:
        return jsonify(reply="No recibí la imagen. ¿La puedes adjuntar de nuevo?")

    try:
        crudo = base64.b64decode(b64)
    except Exception:
        return jsonify(reply="La imagen llegó dañada. ¿La puedes reenviar?")

    resultado = facturas.procesar(crudo, datos.get("mime") or "image/jpeg")

    if not resultado.get("encontrada"):
        return jsonify(reply=resultado["motivo"], lectura=resultado.get("lectura"),
                       verificado=True)

    dictamen = resultado["dictamen"]
    orden = resultado["orden"]
    # La respuesta al cliente se arma con las cifras de la base, no con lo que
    # el modelo leyo en la foto: la lectura solo sirvio para encontrar la orden.
    return jsonify(
        reply=(f"Encontré tu orden {orden['numero_cita']} "
               f"({resultado['equipo']['producto']}).\n\n{resultado['resumen']}"),
        dictamen=dictamen,
        orden_numero=orden["numero_cita"],
        lectura=resultado.get("lectura"),
        identificada_por=resultado.get("identificada_por"),
        fuentes=[resultado["fuente"]],
        herramientas=["leer_orden_servicio", "evaluar_cobertura"],
        verificado=True,
    )


# --- Portal del asesor ---------------------------------------------------

@app.get("/portal")
def portal():
    return render_template("portal.html")


@app.post("/api/portal/login")
def portal_login():
    datos = request.get_json(silent=True) or {}
    usuario = (datos.get("usuario") or "").strip().lower()
    if ASESORES.get(usuario) == (datos.get("clave") or ""):
        session["asesor"] = usuario
        return jsonify(ok=True, asesor=usuario)
    return jsonify(ok=False, motivo="Usuario o clave incorrectos."), 401


@app.post("/api/portal/salir")
def portal_salir():
    session.pop("asesor", None)
    return jsonify(ok=True)


def _asesor() -> str | None:
    return session.get("asesor")


@app.get("/api/casos")
def api_casos():
    if not _asesor():
        return jsonify(ok=False, motivo="Sesión no iniciada."), 401
    estado = request.args.get("estado") or None
    return jsonify(
        ok=True,
        asesor=_asesor(),
        resumen=db.resumen_bandeja(),
        casos=db.listar_casos(estado),
        estados=list(db.ESTADOS),
    )


@app.get("/api/casos/<ticket>")
def api_caso(ticket: str):
    if not _asesor():
        return jsonify(ok=False, motivo="Sesión no iniciada."), 401
    caso = db.caso_por_ticket(ticket)
    if not caso:
        return jsonify(ok=False, motivo="No existe ese caso."), 404
    orden = db.orden_por_numero(caso["numero_cita"] or "")
    equipo = db.equipo_por_serie(caso["serie"] or "")
    return jsonify(ok=True, caso=caso, orden=orden, equipo=equipo)


@app.post("/api/casos/<ticket>")
def api_caso_actualizar(ticket: str):
    if not _asesor():
        return jsonify(ok=False, motivo="Sesión no iniciada."), 401
    datos = request.get_json(silent=True) or {}
    try:
        caso = db.actualizar_caso(
            ticket, datos.get("estado", ""), _asesor(), (datos.get("nota") or "").strip())
    except ValueError as e:
        return jsonify(ok=False, motivo=str(e)), 400
    if not caso:
        return jsonify(ok=False, motivo="No existe ese caso."), 404
    return jsonify(ok=True, caso=caso)


@app.get("/api/salud")
def salud():
    from agent import llm

    return jsonify(
        servicio="Haceb · agente de garantías",
        proveedor=llm.proveedor(),
        modelo=llm.config_openai().get("modelo") if llm.proveedor() != "gemini" else llm.MODELO,
        vision=llm.hay_vision(),
        bandeja=db.resumen_bandeja(),
    )


if __name__ == "__main__":
    db.inicializar()
    print("Demo Haceb en http://localhost:5050  ·  portal en /portal")
    app.run(host="0.0.0.0", port=5050, debug=False)
