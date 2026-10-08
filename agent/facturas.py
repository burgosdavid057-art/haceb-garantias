"""
De la foto de una orden de servicio a un dictamen de garantia.

La regla de diseño que sostiene todo el modulo:

    el modelo de vision NO aporta hechos. Solo aporta IDENTIFICADORES.

Lo que se lee de la imagen (numero de cita, de orden, de recibo, serie) sirve
unicamente para *encontrar* la orden en la base. Los montos, las fechas y las
lineas con las que se calcula la cobertura salen siempre de la base, nunca de
lo que el modelo creyo ver.

El motivo es concreto: un OCR que lee "257.249" como "25.249" cambiaria en un
orden de magnitud lo que se le dice a un cliente que va a pagar. Un numero de
orden mal leido, en cambio, simplemente no encuentra nada — y eso se puede
detectar y preguntar. El error queda visible en vez de silencioso.
"""

from __future__ import annotations

import json
import re

from . import db, garantias, llm

INSTRUCCIONES = """\
Eres un lector de ordenes de servicio de Industrias Haceb. Recibes la foto o el
escaneo de una orden de servicio / factura de servicio tecnico.

Extrae UNICAMENTE los identificadores que veas escritos. No calcules nada, no
interpretes, no completes lo que no se lee. Si un campo no es legible, dejalo
como cadena vacia.

Campos que aparecen en estos documentos:
- "Numero de cita": empieza por SA- (ej. SA-373770)
- "Numero de orden de trabajo": solo digitos (ej. 00371970)
- "No. de recibo": alfanumerico (ej. T209373770)
- "Serie": el serial del equipo (ej. I181298935)
- "Producto Final": el nombre del electrodomestico
- "Cliente": el nombre de la persona

Responde SOLO con JSON valido, sin texto alrededor:
{
  "es_orden_servicio": true|false,
  "numero_cita": "",
  "numero_orden": "",
  "numero_recibo": "",
  "serie": "",
  "producto": "",
  "cliente": "",
  "legible": true|false
}
"""

# Formatos de los identificadores. Se usan para limpiar la lectura del modelo:
# un OCR suele devolver "SA 373770" o "sa-373770" por el mismo numero.
PATRONES = {
    "numero_cita": re.compile(r"\bSA[\s\-]?(\d{5,8})\b", re.I),
    "numero_orden": re.compile(r"\b(\d{7,9})\b"),
    "numero_recibo": re.compile(r"\b(T\d{6,12})\b", re.I),
    "serie": re.compile(r"\b([A-Z]\d{8,12})\b", re.I),
}


def _extraer_json(texto: str) -> dict | None:
    texto = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(), flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _normalizar(campo: str, valor: str) -> str:
    """Deja el identificador en el formato con el que esta guardado en la base."""
    v = (valor or "").strip()
    if not v:
        return ""
    patron = PATRONES.get(campo)
    if not patron:
        return v
    m = patron.search(v)
    if not m:
        return v
    if campo == "numero_cita":
        return f"SA-{m.group(1)}"
    return m.group(1).upper()


def leer(imagen: bytes, mime: str = "image/jpeg") -> dict:
    """Lee la imagen y devuelve solo los identificadores, ya normalizados."""
    crudo = llm.generar_vision(imagen, INSTRUCCIONES, mime=mime)
    datos = _extraer_json(crudo) or {}
    for campo in PATRONES:
        datos[campo] = _normalizar(campo, datos.get(campo, ""))
    return datos


def procesar(imagen: bytes, mime: str = "image/jpeg") -> dict:
    """Foto de una orden -> dictamen de cobertura fundamentado en la base.

    Devuelve siempre `encontrada` para que el que llama sepa si hay dictamen o
    si tiene que pedirle algo mas al cliente.
    """
    if not llm.hay_vision():
        return {
            "encontrada": False,
            "motivo": ("No puedo leer imágenes con el modelo configurado. "
                       "Escríbeme el número de la orden (aparece como SA-...)."),
        }

    try:
        lectura = leer(imagen, mime)
    except Exception as e:  # noqa: BLE001
        return {
            "encontrada": False,
            "motivo": (f"No pude procesar la imagen ({type(e).__name__}). "
                       f"¿Puedes reenviarla o escribirme el número de la orden?"),
        }

    if lectura.get("es_orden_servicio") is False:
        return {
            "encontrada": False,
            "lectura": lectura,
            "motivo": ("Esa imagen no parece una orden de servicio de Haceb. "
                       "Envíame la orden donde aparece el número SA-..."),
        }

    # Los identificadores se prueban en orden de fiabilidad: el numero de cita
    # tiene un formato distintivo, el de orden son digitos sueltos que un OCR
    # confunde con cualquier otra cifra del documento.
    orden = None
    usado = None
    for campo in ("numero_cita", "numero_recibo", "numero_orden"):
        if lectura.get(campo):
            orden = db.orden_por_numero(lectura[campo])
            if orden:
                usado = campo
                break

    # Sin numero legible, la serie identifica el equipo y de ahi su ultima orden.
    if orden is None and lectura.get("serie"):
        ordenes = db.ordenes_de_serie(lectura["serie"])
        if ordenes:
            orden, usado = ordenes[0], "serie"

    if orden is None:
        leidos = {k: v for k, v in lectura.items() if v and k in PATRONES}
        return {
            "encontrada": False,
            "lectura": lectura,
            "motivo": (
                f"Leí la orden pero no la encuentro en el sistema "
                f"({', '.join(f'{k}={v}' for k, v in leidos.items()) or 'no logré leer los números'}). "
                f"Verifica el número o escríbemelo tal como aparece en el papel."
            ),
        }

    equipo = db.equipo_por_serie(orden["serie"])
    if not equipo:
        return {
            "encontrada": False,
            "lectura": lectura,
            "motivo": (f"Encontré la orden {orden['numero_cita']} pero no el equipo "
                       f"asociado (serie {orden['serie']}). Lo reviso con un asesor."),
        }

    dictamen = garantias.evaluar(orden, equipo)
    return {
        "encontrada": True,
        "identificada_por": usado,
        "lectura": lectura,
        "orden": orden,
        "equipo": equipo,
        "dictamen": dictamen,
        "resumen": garantias.resumen_humano(dictamen),
        "fuente": (f"orden de servicio {orden['numero_cita']} · "
                   f"garantía publicada de {equipo['producto']}"),
    }
