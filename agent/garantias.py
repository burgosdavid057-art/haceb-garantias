"""
Motor de cobertura de garantia sobre una orden de servicio real.

Existe porque la pregunta "¿está en garantía?" casi nunca tiene respuesta si/no.
El caso tipico de Haceb es parcial: la pieza va cubierta y la mano de obra se
cobra. Un asistente que contesta "sí, está en garantía" y el cliente recibe una
factura de $282.459 hizo un daño mayor que si no hubiera contestado.

De donde sale la regla — del texto legal que Haceb publica en su propio catalogo:

    "10 años* en el compresor y 1 años en los demás componentes,
     *1 año correspondiente a garantia legal y 9 años a garantia suplementaria."

Esas dos garantias no cubren lo mismo:

    garantia LEGAL (año 1)          -> cubre la pieza Y el servicio.
    garantia SUPLEMENTARIA (año 2+) -> cubre la PIEZA. La mano de obra se cobra.

Por eso una nevera de 4 años con el compresor dañado tiene el compresor cubierto
y el servicio al cobro. No es una excepcion: es el caso mas frecuente.

El motor NO adivina. Si un repuesto de la factura no se puede mapear con
certeza a una parte nombrada en el texto legal, lo marca como
`requiere_confirmacion` y lo manda al asesor, en vez de asumir que esta cubierto.
"""

from __future__ import annotations

import datetime
import re

from . import catalog
from .tools import _parsear_garantia

# Codigo SAP del servicio calificado en las ordenes de Haceb. La mano de obra
# se identifica por codigo cuando esta, y por texto cuando no.
SAP_SERVICIO = "0000002"
PATRON_MANO_OBRA = re.compile(
    r"servicio\s+calificado|mano\s+de\s+obra|visita|diagn[oó]stico|transporte|domicilio",
    re.I,
)

# Sinonimos de taller -> parte nombrada en el texto legal. Solo entradas de las
# que hay certeza; lo que no este aqui NO se asume cubierto.
SINONIMOS = {
    "compresor": ("compresor", "motocompresor", "unidad selladada", "unidad sellada"),
    "motor": ("motor", "motorreductor", "motor de lavado"),
    "tarjetas electronicas": ("tarjeta", "tarjetas", "board", "pcb", "modulo electronico",
                              "panel digital", "display"),
    "panel": ("panel", "panel frontal", "panel digital"),
}

# Causales de exclusion que aparecen escritas por el tecnico en las observaciones.
# Si el tecnico dejo constancia de mal uso, ninguna garantia aplica, sin importar
# la antiguedad del equipo.
EXCLUSIONES = (
    (re.compile(r"mal\s+uso|uso\s+indebido|maltrato", re.I), "mal uso del equipo"),
    (re.compile(r"golpe|ca[ií]da|impacto", re.I), "daño por golpe"),
    (re.compile(r"instalaci[oó]n\s+(?:incorrecta|inadecuada)|mal\s+instalad", re.I),
     "instalación incorrecta"),
    (re.compile(r"variaci[oó]n\s+de\s+voltaje|sobretensi[oó]n|descarga\s+el[eé]ctrica", re.I),
     "variación de voltaje / descarga eléctrica"),
    (re.compile(r"manipulaci[oó]n\s+por\s+(?:terceros|personal\s+no\s+autorizado)|"
                r"t[eé]cnico\s+no\s+autorizado", re.I), "manipulación por terceros"),
    (re.compile(r"falta\s+de\s+mantenimiento|sin\s+mantenimiento", re.I),
     "falta de mantenimiento"),
)


def _anios_legales(texto: str) -> int:
    """Años de garantia LEGAL declarados en el texto (los que cubren servicio).

    Si el texto no distingue legal de suplementaria, se toma la cobertura mas
    corta: es el piso que Haceb da a todos los componentes, y es el periodo en
    el que el servicio va incluido.
    """
    m = re.search(r"(\d+)\s*años?\s+correspondiente[s]?\s+a\s+(?:la\s+)?garant[ií]a\s+legal",
                  texto, re.I)
    if m:
        return int(m.group(1))
    if re.search(r"primer\s+año\s+corresponde\s+a\s+(?:la\s+)?garant[ií]a\s+legal", texto, re.I):
        return 1
    cobertura = _parsear_garantia(texto)
    return min(cobertura.values()) if cobertura else 1


def _anios_transcurridos(fecha_compra: str, hasta: str | None = None) -> float:
    d0 = datetime.date.fromisoformat(fecha_compra[:10])
    d1 = datetime.date.fromisoformat((hasta or datetime.date.today().isoformat())[:10])
    return round((d1 - d0).days / 365.25, 2)


def _es_mano_de_obra(linea: dict) -> bool:
    codigo = str(linea.get("codigo_sap") or "").strip()
    if codigo == SAP_SERVICIO or codigo == "2":
        return True
    return bool(PATRON_MANO_OBRA.search(str(linea.get("producto") or "")))


def _parte_cubierta(descripcion: str, cobertura: dict[str, int]) -> tuple[str, int] | None:
    """Mapea el texto de un repuesto a una parte nombrada en la garantia.

    Devuelve None cuando no hay certeza: el que llama debe tratarlo como
    "requiere confirmacion", nunca como cubierto.
    """
    d = catalog.normaliza(descripcion)
    # 1) la parte aparece nombrada tal cual en el texto legal
    for parte, anios in cobertura.items():
        np = catalog.normaliza(parte)
        if np in ("demas componentes", "componentes", "todos sus componentes",
                  "todos los componentes"):
            continue
        if np and np in d:
            return parte, anios
    # 2) sinonimo de taller de una parte nombrada
    for parte, anios in cobertura.items():
        np = catalog.normaliza(parte)
        for canonica, variantes in SINONIMOS.items():
            if canonica not in np and np not in canonica:
                continue
            if any(catalog.normaliza(v) in d for v in variantes):
                return parte, anios
    return None


def _cajon_por_defecto(cobertura: dict[str, int]) -> tuple[str, int] | None:
    """La clausula "los demas componentes", que cubre lo no nombrado."""
    for parte, anios in cobertura.items():
        n = catalog.normaliza(parte)
        if "demas" in n or "component" in n:
            return parte, anios
    return None


def exclusiones_detectadas(observaciones: str) -> list[str]:
    return [m for patron, m in EXCLUSIONES if patron.search(observaciones or "")]


def evaluar(orden: dict, equipo: dict) -> dict:
    """Dictamina la cobertura de una orden de servicio, linea por linea.

    `orden` viene de db.orden_por_numero (trae `lineas`), `equipo` de
    db.equipo_por_serie (trae `fecha_compra`, que es el dato verificado).
    """
    producto = catalog.por_referencia(equipo["referencia"])
    texto = (producto or {}).get("specs", {}).get("Garantía") if producto else None

    if not texto:
        return {
            "determinable": False,
            "motivo": (
                f"El catálogo no publica los términos de garantía de "
                f"{equipo['producto']}. No se puede dictaminar sin el texto legal."
            ),
            "requiere_asesor": True,
            "fuente": (producto or {}).get("url"),
        }

    cobertura = _parsear_garantia(texto)
    anios_legales = _anios_legales(texto)
    anios_uso = _anios_transcurridos(equipo["fecha_compra"], orden.get("fecha"))
    en_periodo_legal = anios_uso <= anios_legales

    exclusiones = exclusiones_detectadas(orden.get("observaciones", ""))

    lineas, a_cargo_cliente, cubierto_haceb = [], 0.0, 0.0
    for linea in orden.get("lineas", []):
        total = float(linea.get("total_con_iva") or 0)
        descripcion = str(linea.get("producto") or "")
        es_servicio = _es_mano_de_obra(linea)
        detalle = {
            "codigo_sap": linea.get("codigo_sap"),
            "producto": descripcion,
            "cantidad": linea.get("cantidad"),
            "total_con_iva": total,
            "tipo": "mano de obra" if es_servicio else "repuesto",
            "requiere_confirmacion": False,
        }

        if exclusiones:
            detalle.update(
                cubierto=False,
                motivo=f"Excluido de garantía: {exclusiones[0]} (según observaciones del técnico).",
            )
        elif es_servicio:
            # El servicio solo va incluido dentro de la garantia legal.
            if en_periodo_legal:
                detalle.update(
                    cubierto=True,
                    motivo=f"Dentro de la garantía legal ({anios_legales} año): el servicio va incluido.",
                )
            else:
                detalle.update(
                    cubierto=False,
                    motivo=(
                        f"La garantía suplementaria cubre la pieza, no la mano de obra. "
                        f"El equipo tiene {anios_uso:.1f} años y la garantía legal es de "
                        f"{anios_legales} año."
                    ),
                )
        else:
            aplica = _parte_cubierta(descripcion, cobertura)
            if aplica is None:
                cajon = _cajon_por_defecto(cobertura)
                if cajon and anios_uso <= cajon[1]:
                    detalle.update(
                        cubierto=True,
                        cubierto_bajo=cajon[0],
                        cobertura_anios=cajon[1],
                        motivo=f"Cubierto por «{cajon[0]}» ({cajon[1]} año(s)).",
                    )
                elif anios_uso > max(cobertura.values(), default=0):
                    # Ni la cobertura mas larga del producto alcanza esta
                    # antiguedad: da igual a que parte corresponda el repuesto,
                    # no puede estar cubierto. No hay nada que confirmar.
                    detalle.update(
                        cubierto=False,
                        motivo=(
                            f"El equipo tiene {anios_uso:.1f} años y la cobertura más larga "
                            f"de este producto es de {max(cobertura.values())} años: vencida."
                        ),
                    )
                else:
                    # Podria caer dentro de una parte con cobertura vigente, pero
                    # no se puede mapear con certeza. No se asume nada en ninguna
                    # direccion: lo decide una persona.
                    detalle.update(
                        cubierto=False,
                        requiere_confirmacion=True,
                        motivo=(
                            "No se pudo mapear este repuesto a una parte nombrada en los "
                            "términos publicados. Requiere confirmación del asesor."
                        ),
                    )
            else:
                parte, anios = aplica
                cubre = anios_uso <= anios
                detalle.update(
                    cubierto=cubre,
                    cubierto_bajo=parte,
                    cobertura_anios=anios,
                    motivo=(
                        f"«{parte}» tiene {anios} años de cobertura y el equipo tiene "
                        f"{anios_uso:.1f}."
                        if cubre else
                        f"«{parte}» tiene {anios} años de cobertura y el equipo ya tiene "
                        f"{anios_uso:.1f}: vencida."
                    ),
                )

        if detalle["cubierto"]:
            cubierto_haceb += total
        else:
            a_cargo_cliente += total
        lineas.append(detalle)

    dudosas = [l for l in lineas if l["requiere_confirmacion"]]
    total_orden = round(cubierto_haceb + a_cargo_cliente, 2)

    if exclusiones:
        veredicto = "excluida"
    elif a_cargo_cliente == 0 and total_orden > 0:
        veredicto = "cubierta_total"
    elif dudosas:
        # Hay lineas que nadie pudo mapear. Afirmar "no está cubierto" seria
        # una conclusion sin respaldo, igual de dañina que afirmar que sí.
        veredicto = "requiere_revision"
    elif cubierto_haceb == 0:
        veredicto = "no_cubierta"
    else:
        veredicto = "cubierta_parcial"

    return {
        "determinable": True,
        "veredicto": veredicto,
        "producto": equipo["producto"],
        "referencia": equipo["referencia"],
        "serie": equipo["serie"],
        "fecha_compra": equipo["fecha_compra"],
        "fecha_servicio": orden.get("fecha"),
        "anios_de_uso": anios_uso,
        "anios_garantia_legal": anios_legales,
        "en_periodo_legal": en_periodo_legal,
        "cobertura_publicada": cobertura,
        "texto_garantia": texto,
        "exclusiones": exclusiones,
        "lineas": lineas,
        "total_orden_cop": total_orden,
        "cubre_haceb_cop": round(cubierto_haceb, 2),
        "paga_cliente_cop": round(a_cargo_cliente, 2),
        "requiere_asesor": bool(dudosas or exclusiones),
        "lineas_dudosas": len(dudosas),
        "fuente": (producto or {}).get("url") or "catálogo público de Haceb",
    }


def resumen_humano(d: dict) -> str:
    """Una frase honesta con el numero que le importa al cliente."""
    if not d.get("determinable"):
        return d.get("motivo", "No se pudo determinar la cobertura.")

    def pesos(v):
        return "$" + f"{round(v):,}".replace(",", ".")

    if d["veredicto"] == "excluida":
        return (f"El daño quedó excluido de garantía por {d['exclusiones'][0]}, según lo "
                f"que registró el técnico. El costo del servicio es {pesos(d['total_orden_cop'])}.")
    if d["veredicto"] == "cubierta_total":
        return (f"Todo el servicio queda cubierto por la garantía: no tienes que pagar nada. "
                f"El equipo tiene {d['anios_de_uso']:.1f} años y sigue dentro de la garantía "
                f"legal de {d['anios_garantia_legal']} año.")
    if d["veredicto"] == "no_cubierta":
        return (f"El equipo tiene {d['anios_de_uso']:.1f} años y ya no tiene cobertura para "
                f"este caso. El servicio queda en {pesos(d['total_orden_cop'])}.")
    if d["veredicto"] == "requiere_revision":
        dudosos = [l["producto"].split("_")[-1].title()
                   for l in d["lineas"] if l["requiere_confirmacion"]]
        return (
            f"No te puedo confirmar la cobertura todavía: {', '.join(dudosos)} no aparece "
            f"con ese nombre en los términos publicados de tu equipo, y prefiero no "
            f"suponerlo. Paso el caso a un asesor de Haceb para que lo confirme; el valor "
            f"en juego es {pesos(d['paga_cliente_cop'])}."
        )
    piezas = [l["producto"] for l in d["lineas"] if l["cubierto"]]
    return (
        f"Cobertura parcial. Haceb asume {pesos(d['cubre_haceb_cop'])} "
        f"({', '.join(p.split('_')[-1].title() for p in piezas[:3])}) y tú asumes "
        f"{pesos(d['paga_cliente_cop'])}, que corresponden a la mano de obra: el equipo "
        f"tiene {d['anios_de_uso']:.1f} años, y pasado el primer año la garantía cubre la "
        f"pieza pero no el servicio."
    )
