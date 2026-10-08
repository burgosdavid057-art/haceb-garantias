"""
Guardián de literalidad: toda cifra que el agente escribe tiene que estar en la
evidencia que devolvieron las herramientas.

Es determinista y corre en microsegundos, sin modelo. Existe porque el otro
validador —un segundo LLM que audita— es correcto pero tarda entre 26 y 86
segundos en esta máquina, y corre DESPUÉS del agente: su latencia se suma
entera a la espera del usuario. Un chat de dos minutos por turno no lo usa
nadie.

Qué atrapa y qué no, dicho sin adornos:

  atrapa   cifras inventadas: montos, años de garantía, capacidades, precios.
           Es el grueso de lo que hace daño — un peso mal dicho es un peso que
           alguien va a pagar.
  no atrapa afirmaciones cualitativas invertidas ("NO está cubierto" cuando sí
           lo está). Para eso está el desglose en pantalla, que se dibuja desde
           el cálculo de Python y no desde el texto del modelo: si el modelo
           dice lo contrario, la tabla lo desmiente a la vista.

No corrige ni reescribe: marca. Lo que no se puede respaldar se muestra como no
respaldado, igual que hace el validador LLM.
"""

from __future__ import annotations

import json
import re

# Cifras del texto: "$ 318.540", "257249", "4.16", "10 años", "1,234,567.89"
NUMERO = re.compile(r"\d[\d.,]*")

# Tolerancia relativa al comparar. Cubre el redondeo con el que se presenta el
# dinero (257249.14 se escribe como 257.249) sin dejar pasar otra cifra.
TOLERANCIA = 0.011

# Números que no vale la pena auditar: aparecen en cualquier redacción
# ("las 2 opciones", "24 horas") y marcarlos solo produciría ruido que enseña a
# ignorar la alerta.
INOCUOS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 24, 30, 60, 100}

# ...salvo cuando son AÑOS: "10 años en el compresor" es el dato con el que el
# cliente decide si reclama o paga. Una cifra pequeña sigue siendo una promesa
# de cobertura, así que estas se auditan aunque estén en la lista de inocuos.
ANIOS = re.compile(r"(\d[\d.,]*)\s*(?:años?|anios?)", re.I)


def _a_numero(txt: str) -> float | None:
    """Convierte '1.234.567,89' o '1,234,567.89' o '318.540' a float.

    El español y el inglés usan el punto y la coma al revés, y en la misma
    conversación aparecen los dos (el catálogo trae floats, el texto los escribe
    con separador de miles). Se decide por cuál va último.
    """
    t = txt.strip().rstrip(".,")
    if not t or not any(c.isdigit() for c in t):
        return None

    tiene_punto, tiene_coma = "." in t, "," in t
    if tiene_punto and tiene_coma:
        # El separador decimal es el que aparece de último.
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif tiene_coma:
        # Coma sola: decimal si deja 1-2 dígitos ("4,16"), miles si deja 3.
        entero, _, resto = t.rpartition(",")
        t = t.replace(",", "." if len(resto) in (1, 2) else "")
    elif tiene_punto:
        entero, _, resto = t.rpartition(".")
        if len(resto) == 3 and entero:
            t = t.replace(".", "")

    try:
        return float(t)
    except ValueError:
        return None


def _numeros_de(objeto) -> set[float]:
    """Todos los números que aparecen en la evidencia, a cualquier profundidad."""
    encontrados: set[float] = set()

    def recorrer(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            encontrados.add(float(o))
        elif isinstance(o, str):
            for m in NUMERO.findall(o):
                v = _a_numero(m)
                if v is not None:
                    encontrados.add(v)
        elif isinstance(o, dict):
            for v in o.values():
                recorrer(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                recorrer(v)

    recorrer(objeto)
    return encontrados


def _cerca(valor: float, candidatos: set[float]) -> bool:
    for c in candidatos:
        if valor == c:
            return True
        escala = max(abs(valor), abs(c), 1.0)
        if abs(valor - c) / escala <= TOLERANCIA:
            return True
    return False


def verificar(respuesta: str, evidencia_json: str) -> dict:
    """Dictamen determinista, con el mismo contrato que validator.validar."""
    if not evidencia_json or evidencia_json == "[]":
        return {
            "verificado": True,
            "fundamentada": True,
            "afirmaciones_sin_respaldo": [],
            "explicacion": "Respuesta conversacional, sin datos de producto que verificar.",
        }

    try:
        evidencia = json.loads(evidencia_json)
    except json.JSONDecodeError:
        # El auditor que no pudo leer la evidencia no avala nada.
        return {
            "verificado": False,
            "fundamentada": None,
            "afirmaciones_sin_respaldo": [],
            "explicacion": "No se pudo leer la evidencia.",
        }

    respaldados = _numeros_de(evidencia)
    # Un total calculado a partir de dos cifras de la evidencia está respaldado
    # aunque no aparezca literal: sumar lo que las herramientas devolvieron es
    # aritmética, no invención.
    base = list(respaldados)[:60]
    for i, a in enumerate(base):
        for b in base[i:]:
            respaldados.add(a + b)
            respaldados.add(abs(a - b))

    # Las cifras seguidas de "años" se auditan siempre; el resto, salvo inocuas.
    en_anios = {m for m in ANIOS.findall(respuesta)}

    sin_respaldo = []
    for bruto in NUMERO.findall(respuesta):
        valor = _a_numero(bruto)
        if valor is None or valor != valor:
            continue
        if valor in INOCUOS and bruto not in en_anios:
            continue
        if not _cerca(valor, respaldados):
            sin_respaldo.append(bruto + (" años" if bruto in en_anios else ""))

    # De-duplicar conservando el orden en que aparecieron.
    vistos, unicos = set(), []
    for s in sin_respaldo:
        if s not in vistos:
            vistos.add(s)
            unicos.append(s)

    return {
        "verificado": True,
        "fundamentada": not unicos,
        "afirmaciones_sin_respaldo": unicos,
        "explicacion": (
            "Todas las cifras aparecen en la evidencia de las herramientas."
            if not unicos else
            f"Estas cifras no aparecen en la evidencia: {', '.join(unicos[:5])}."
        ),
        "metodo": "literalidad determinista",
    }
