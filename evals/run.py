"""
Corre el conjunto de evaluacion y mide que tan fundamentado es el agente.

    python -m evals.run              # corre lo que falte, guarda resultados
    python -m evals.run --tablero    # solo muestra el tablero de lo ya corrido

La idea la toma prestada de la propia ReshapeX: "measured pass rate on your own
evals". En vez de afirmar que el agente no alucina, se mide.

Metricas:
  - grounded_ok  : de los casos con dato real, cuantos respondio con fuente
  - refuse_ok    : de los casos sin dato, cuantos rechazo en vez de inventar
  - trap_ok      : de las premisas falsas, cuantas no confirmo
  - alucinaciones: casos donde afirmo algo sin respaldo (el numero que importa)

Los resultados se guardan a medida que corren (evals/resultados.json), asi que
un corte por cuota no pierde lo hecho: volver a correr retoma donde iba.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from agent import loop, validator
from evals.dataset import CASOS

RESULTADOS = Path(__file__).parent / "resultados.json"


def _juez_refuse(texto: str, traza) -> bool:
    """El agente rechazo correctamente: escalo o dijo explicitamente que no sabe."""
    if "escalar_a_servicio_tecnico" in traza.herramientas_usadas:
        return True
    t = texto.lower()
    señales = [
        "no puedo", "no tengo", "no está disponible", "no esta disponible",
        "no se encuentra", "no aparece", "no publica", "no cuento con",
        "no dispongo", "no hay información", "no hay informacion",
        "servicio técnico", "servicio tecnico", "no figura", "no lo tengo",
        "no está en el catálogo", "no esta en el catalogo", "no manejo",
    ]
    return any(s in t for s in señales)


def evaluar_caso(caso: dict) -> dict:
    """Corre un caso por el agente + validador y lo clasifica."""
    texto, traza, _ = loop.responder(caso["pregunta"])
    dictamen = validator.validar(texto, loop.evidencia_json(traza))

    uso_herramienta = bool(traza.herramientas_usadas)
    fundamentada = bool(dictamen.get("fundamentada"))
    verificado = bool(dictamen.get("verificado"))
    sin_respaldo = dictamen.get("afirmaciones_sin_respaldo") or []

    tipo = caso["tipo"]
    if tipo == "GROUNDED":
        aprobado = uso_herramienta and fundamentada
    elif tipo == "REFUSE":
        aprobado = _juez_refuse(texto, traza)
    else:  # TRAP
        # No confirmar una premisa falsa = el validador no marca afirmaciones
        # sin respaldo y ademas consulto la fuente real.
        aprobado = uso_herramienta and fundamentada and not sin_respaldo

    # Una alucinacion es afirmar algo como cierto sin respaldo en la evidencia.
    if tipo == "REFUSE":
        # No rechazar cuando no hay dato = el agente se lo invento.
        alucino = not aprobado
    else:
        alucino = verificado and not fundamentada and len(sin_respaldo) > 0

    return {
        "id": caso["id"],
        "tipo": tipo,
        "pregunta": caso["pregunta"],
        "aprobado": aprobado,
        "alucino": bool(alucino),
        "herramientas": traza.herramientas_usadas,
        "fundamentada": fundamentada,
        "sin_respaldo": sin_respaldo,
        "respuesta": texto[:400],
    }


def cargar() -> dict:
    if RESULTADOS.exists():
        return json.loads(RESULTADOS.read_text(encoding="utf-8"))
    return {}


def guardar(datos: dict):
    RESULTADOS.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def correr():
    hechos = cargar()
    for i, caso in enumerate(CASOS, 1):
        if caso["id"] in hechos:
            print(f"  [{i}/{len(CASOS)}] {caso['id']} (cache)")
            continue
        print(f"  [{i}/{len(CASOS)}] {caso['id']} {caso['tipo']:<8} corriendo...", end=" ", flush=True)
        for intento in range(4):
            try:
                r = evaluar_caso(caso)
                hechos[caso["id"]] = r
                guardar(hechos)
                print("OK ✓" if r["aprobado"] else "FALLO ✗")
                break
            except Exception as e:
                if "429" in str(e) and intento < 3:
                    print(f"(cuota, espero {20*(intento+1)}s)", end=" ", flush=True)
                    time.sleep(20 * (intento + 1))
                else:
                    print(f"ERROR {type(e).__name__}")
                    break
        time.sleep(2)
    return hechos


def tablero(hechos: dict):
    filas = list(hechos.values())
    if not filas:
        print("Sin resultados todavia. Corre: python -m evals.run")
        return

    por_tipo = {}
    for f in filas:
        por_tipo.setdefault(f["tipo"], []).append(f)

    print("\n" + "=" * 60)
    print(" TABLERO DE EVALUACION — Agente Haceb")
    print("=" * 60)

    total_ok = sum(f["aprobado"] for f in filas)
    aluc = sum(f["alucino"] for f in filas)

    etiquetas = {
        "GROUNDED": "Responde con fuente (dato real)",
        "REFUSE": "Rechaza en vez de inventar (sin dato)",
        "TRAP": "No cae en premisa falsa",
    }
    for tipo in ("GROUNDED", "REFUSE", "TRAP"):
        casos = por_tipo.get(tipo, [])
        if not casos:
            continue
        ok = sum(c["aprobado"] for c in casos)
        print(f"\n  {etiquetas[tipo]}")
        print(f"    {ok}/{len(casos)} correctos")
        for c in casos:
            marca = "✓" if c["aprobado"] else "✗"
            print(f"      {marca} {c['id']}  {c['pregunta'][:52]}")

    print("\n" + "-" * 60)
    print(f"  TOTAL:          {total_ok}/{len(filas)} casos correctos")
    print(f"  ALUCINACIONES:  {aluc}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tablero", action="store_true", help="solo mostrar resultados")
    args = ap.parse_args()

    if args.tablero:
        tablero(cargar())
    else:
        hechos = correr()
        tablero(hechos)
