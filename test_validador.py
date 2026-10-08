"""
Chequeo de los dos auditores: ¿atrapan una cifra inventada y dejan pasar una
respuesta correcta?

    python test_validador.py          # el que esté activo (VALIDADOR en .env)
    python test_validador.py llm      # fuerza el auditor con modelo (lento)

Importa porque el auditor es lo último entre una alucinación y el cliente. Un
auditor rápido que aprueba todo no es un auditor: es latencia decorativa —
medido, qwen2.5:3b aprobó las tres alucinaciones de esta tabla en 1.4 s.

Resultado medido en este M5/16GB:

    literalidad (Python)   4/5   0.03 ms
    gemma4 (LLM)           5/5   26-86 s

El caso que el guardián determinista NO atrapa está marcado abajo y es una
limitación conocida, no un descuido: la cifra que dice es correcta, lo invertido
es la afirmación. Contra eso juega el desglose en pantalla, que se dibuja desde
el cálculo de Python y no desde el texto del modelo.
"""

import json
import sys
import time

EVIDENCIA = json.dumps([{
    "herramienta": "consultar_orden_servicio",
    "argumentos": {"numero": "SA-373770"},
    "resultado": {
        "numero_cita": "SA-373770",
        "producto": "Nevera Haceb No Frost 404 Litros Manija Integrada Gris",
        "anios_de_uso": 4.16,
        "veredicto": "cubierta_parcial",
        "cubre_haceb_cop": 318540.0,
        "paga_cliente_cop": 257249.14,
        "total_orden_cop": 575789.14,
        "garantia_publicada": "10 años* en el compresor y 1 años en los demás componentes",
    },
}], ensure_ascii=False)

# (nombre, debe_aprobar, respuesta, lo_atrapa_el_deterministico)
CASOS = [
    ("cifra correcta", True,
     "El compresor queda cubierto: Haceb asume $318.540 y tú asumes $257.249 "
     "de mano de obra. El equipo tiene 4.16 años.", True),
    ("mismo número con otro formato", True,
     "Haceb cubre $318,540 COP y usted paga 257249 pesos.", True),
    ("CIFRA INVENTADA", False,
     "Tu equipo está cubierto: Haceb asume $318.540 y tú solo pagas $45.000.", True),
    ("GARANTÍA INVENTADA", False,
     "Tu nevera tiene 15 años de garantía en el compresor, así que no pagas nada.", True),
    # Cualitativo: todas las cifras existen en la evidencia, lo invertido es la
    # afirmación. Solo el auditor con modelo lo ve.
    ("VEREDICTO INVERTIDO", False,
     "El compresor NO está cubierto por la garantía, debes asumir los $575.789 completos.",
     False),
]


def main() -> None:
    usar_llm = "llm" in sys.argv
    if usar_llm:
        from agent import openai_backend
        auditar, etiqueta = (
            lambda r, e: openai_backend.validar(r, e), "auditor con modelo (LLM)")
    else:
        from agent import literalidad
        auditar, etiqueta = literalidad.verificar, "guardián de literalidad (Python)"

    print(f"{etiqueta}\n")
    fallos = 0
    for nombre, debe_aprobar, respuesta, deterministico in CASOS:
        t = time.time()
        d = auditar(respuesta, EVIDENCIA)
        seg = time.time() - t
        aprobo = bool(d.get("verificado") and d.get("fundamentada"))
        # Al guardián determinista no se le exige el caso cualitativo.
        esperado = debe_aprobar if (usar_llm or deterministico) else True
        ok = aprobo == esperado
        fallos += not ok
        nota = "" if (usar_llm or deterministico) else "  (limitación conocida: cualitativo)"
        print(f"  {'OK' if ok else 'XX'} {nombre:<32} "
              f"{seg*1000:8.2f}ms  aprobó={aprobo}{nota}")
        if not ok:
            print(f"       esperaba aprobó={esperado} · {d.get('explicacion','')[:90]}")

    print(f"\n{'TODO OK' if not fallos else f'{fallos} FALLO(S)'} — {len(CASOS)} casos")
    raise SystemExit(1 if fallos else 0)


if __name__ == "__main__":
    main()
