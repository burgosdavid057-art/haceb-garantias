"""
Chequeo del motor de cobertura. Corre sin modelo y sin red.

    python test_garantias.py

Cada caso sembrado cae en una rama distinta del motor. Si alguien toca
garantias.py y rompe una, aqui se ve.
"""

from agent import db, garantias

# numero de cita -> (veredicto, paga el cliente, requiere asesor)
#
# Los montos salen de sumar las lineas que NO quedan cubiertas. En SA-373770 el
# cliente paga la mano de obra ($257.249) mas el refrigerante y el filtro
# secador ($21.673): son insumos que no se pueden mapear al "compresor", asi que
# el motor no los da por cubiertos. Es lo mismo que hizo la orden real, donde
# solo el compresor entro por garantia.
ESPERADO = {
    "SA-373770": ("requiere_revision", 278922.37, True),   # compresor sí; insumos al asesor
    "SA-381204": ("cubierta_total",         0.0, False),   # dentro del año legal
    "SA-366015": ("no_cubierta",       355649.14, False),  # 11.8 años: nada alcanza
    "SA-379441": ("excluida",          547149.14, True),   # variación de voltaje
    "SA-384990": ("requiere_revision", 433749.14, True),   # damper no mapeable -> asesor
    "SA-386712": ("cubierta_parcial",  257249.14, False),  # motor 10 años, servicio al cobro
}


def main() -> None:
    fallos = 0
    for cita, (veredicto, paga, asesor) in ESPERADO.items():
        orden = db.orden_por_numero(cita)
        assert orden, f"{cita}: no está sembrada. Corre primero: python seed.py"
        equipo = db.equipo_por_serie(orden["serie"])
        assert equipo, f"{cita}: la serie {orden['serie']} no tiene equipo"

        d = garantias.evaluar(orden, equipo)
        ok = (d["veredicto"] == veredicto
              and abs(d["paga_cliente_cop"] - paga) < 1
              and d["requiere_asesor"] == asesor)
        fallos += not ok
        print(f"  {'OK' if ok else 'XX'} {cita}  {d['veredicto']:<17}"
              f" cliente=${d['paga_cliente_cop']:>12,.0f}  haceb=${d['cubre_haceb_cop']:>12,.0f}"
              f"  asesor={d['requiere_asesor']}")
        if not ok:
            print(f"       esperaba {veredicto} / cliente=${paga:,.0f} / asesor={asesor}")
        print(f"       {garantias.resumen_humano(d)}")

    # La regla que da sentido al motor: pasado el año legal, la mano de obra se
    # cobra aunque la pieza esté cubierta.
    d = garantias.evaluar(db.orden_por_numero("SA-373770"),
                          db.equipo_por_serie("I181298935"))
    servicio = [l for l in d["lineas"] if l["tipo"] == "mano de obra"][0]
    compresor = [l for l in d["lineas"] if "COMPRESOR" in l["producto"]][0]
    assert compresor["cubierto"] and not servicio["cubierto"], \
        "la pieza debe ir cubierta y la mano de obra al cobro"
    assert not d["en_periodo_legal"], "4 años de uso no están en el período legal"

    print(f"\n{'TODO OK' if not fallos else f'{fallos} CASO(S) MAL'}"
          f" — {len(ESPERADO)} casos evaluados")
    raise SystemExit(1 if fallos else 0)


if __name__ == "__main__":
    main()
