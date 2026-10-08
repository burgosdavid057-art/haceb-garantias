"""
Siembra la base del demo: equipos vendidos y ordenes de servicio.

    python seed.py

Las ordenes reproducen la estructura de una orden de servicio real de Haceb
(informacion de la cita, orden de trabajo, recibo de caja con codigos SAP y
observaciones del tecnico), pero TODOS los datos personales son ficticios.

Los seis casos estan elegidos para que cada uno caiga en una rama distinta del
motor de cobertura. Si el motor se rompe, alguno de estos deja de cuadrar.
"""

from __future__ import annotations

import json

from agent import db

# (serie, referencia, producto, fecha_compra, cliente, documento, telefono, correo,
#  direccion, ciudad)
EQUIPOS = [
    ("I181298935", "9003123", "Nevera Haceb No Frost 404 Litros Manija Integrada Gris",
     "2022-03-14", "Nataly Restrepo Álvarez", "43128877", "3015921106",
     "nrestrepo@example.com", "Cra 74 # 45-12 Apto 302", "Medellín"),
    ("H2402118740", "9003548", "Nevera Haceb No Frost 311 Litros Inverter Manija Integrada",
     "2026-02-02", "Carlos Betancur Ruiz", "71554390", "3106442218",
     "cbetancur@example.com", "Calle 30 # 80-44", "Medellín"),
    ("G1310044521", "9002739", "Nevera Haceb Frost 220 Litros Manija Integrada Titanio",
     "2014-06-20", "Gloria Mesa Ocampo", "32118904", "3204471903",
     "gmesa@example.com", "Cra 50 # 12-08", "Envigado"),
    ("L2201773310", "9002779", "Lavadora Haceb IVY 19 Kilogramos Panel Digital Negra",
     "2023-08-09", "Andrés Quintero Vélez", "1017229540", "3123398871",
     "aquintero@example.com", "Calle 9 Sur # 43-21", "Sabaneta"),
    ("H2108990233", "9003189", "Nevera Haceb No Frost 448 Litros Inverter Manija Integrada",
     "2021-11-30", "Diana Ospina Cardona", "43990112", "3018876540",
     "dospina@example.com", "Cra 65 # 98-17", "Bello"),
    ("L2405661200", "7704353431537", "Lavadora ZOÜ 20 Kilogramos Haceb Digital",
     "2024-05-18", "Julián Arango Posada", "70884412", "3145520098",
     "jarango@example.com", "Calle 48 # 70-90", "Itagüí"),
]

SERVICIO = {"codigo_sap": "0000002", "producto": "0000002_SERVICIO CALIFICADO",
            "cantidad": 1.75, "descuento": 0.0, "total_con_iva": 257249.14}

ORDENES = [
    # 1. El caso de la factura real: compresor cubierto, mano de obra al cobro.
    dict(numero_cita="SA-373770", numero_orden="00371970", numero_recibo="T209373770",
         serie="I181298935", fecha="2026-05-12", tecnico="Pedro José Muñoz Movilla",
         codigo_seguridad="AR-400203", bodega="T209", tipo_trabajo="LLEVAR REPUESTO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="AL COBRO",
         observaciones=(
             "SE REVISA NEVERA Y SE ENCUENTRA COMPRESOR AISLADO POR LO TANTO NO REALIZABA SU "
             "PROCESO. EN ESTE CASO SE LE INFORMA A USUARIO QUE EL COMPRESOR SERA EN GARANTIA "
             "PERO DEBE ASUMIR EL VALOR DE LA MANO DE OBRA. USUARIO ACEPTA Y SE PROCEDE A "
             "REALIZAR INTERVENCION. SE VERIFICA FUNCIONAMIENTO Y QUEDA FUNCIONAL."),
         lineas=[
             SERVICIO,
             {"codigo_sap": "2006684", "producto": "2006684_COMPRESOR HERMETICO R-600 1/4 HP",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 318540.00},
             {"codigo_sap": "3007231", "producto": "3007231_FLUIDO REFRIGERANTE R-600",
              "cantidad": 0.26, "descuento": 0.0, "total_con_iva": 14226.21},
             {"codigo_sap": "1007982", "producto": "1007982_FILTRO SECADOR TRES BOCAS DELTA 20",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 7447.02},
         ]),
    # 2. Dentro del primer año: la garantia legal cubre TODO, servicio incluido.
    dict(numero_cita="SA-381204", numero_orden="00382551", numero_recibo="T118381204",
         serie="H2402118740", fecha="2026-06-28", tecnico="Luis Fernando Cárdenas",
         codigo_seguridad="AR-411890", bodega="T118", tipo_trabajo="REPARACION EN SITIO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="GARANTIA",
         observaciones=("SE ATIENDE FALLA DE NO ENFRIAMIENTO. SE DIAGNOSTICA TERMOSTATO "
                        "DEFECTUOSO DE FABRICA. SE CAMBIA Y SE VERIFICA FUNCIONAMIENTO."),
         lineas=[
             dict(SERVICIO, cantidad=1.0, total_con_iva=147000.00),
             {"codigo_sap": "2004410", "producto": "2004410_TERMOSTATO CONTROL NEVERA NF",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 62300.00},
         ]),
    # 3. Equipo de 12 años: ninguna cobertura vigente.
    dict(numero_cita="SA-366015", numero_orden="00366780", numero_recibo="T204366015",
         serie="G1310044521", fecha="2026-04-03", tecnico="Marta Lucía Zapata",
         codigo_seguridad="AR-388120", bodega="T204", tipo_trabajo="LLEVAR REPUESTO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="AL COBRO",
         observaciones=("EQUIPO CON 12 AÑOS DE USO. SE ENCUENTRA MOTOVENTILADOR BLOQUEADO Y "
                        "DESGASTE NORMAL POR ANTIGUEDAD. SE REEMPLAZA."),
         lineas=[
             SERVICIO,
             {"codigo_sap": "2003117", "producto": "2003117_MOTOVENTILADOR EVAPORADOR 220V",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 98400.00},
         ]),
    # 4. Excluida: el tecnico dejo constancia de variacion de voltaje.
    dict(numero_cita="SA-379441", numero_orden="00380102", numero_recibo="T209379441",
         serie="L2201773310", fecha="2026-06-11", tecnico="Jhon Édison Ramírez",
         codigo_seguridad="AR-405677", bodega="T209", tipo_trabajo="LLEVAR REPUESTO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="AL COBRO",
         observaciones=("SE REVISA LAVADORA Y SE ENCUENTRA TARJETA ELECTRONICA QUEMADA POR "
                        "VARIACION DE VOLTAJE EN LA RED DEL INMUEBLE. SE INFORMA AL USUARIO QUE "
                        "NO APLICA GARANTIA POR CAUSA EXTERNA. USUARIO ACEPTA REPARACION."),
         lineas=[
             SERVICIO,
             {"codigo_sap": "2007790", "producto": "2007790_TARJETA ELECTRONICA PRINCIPAL IVY",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 289900.00},
         ]),
    # 5. Repuesto que NO se puede mapear al texto legal: va al asesor, no se asume.
    dict(numero_cita="SA-384990", numero_orden="00385330", numero_recibo="T118384990",
         serie="H2108990233", fecha="2026-07-09", tecnico="Sandra Milena Gil",
         codigo_seguridad="AR-419002", bodega="T118", tipo_trabajo="LLEVAR REPUESTO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="AL COBRO",
         observaciones=("USUARIO REPORTA RUIDO. SE ENCUENTRA DAÑO EN CONJUNTO DAMPER Y SE "
                        "REEMPLAZA. SE VERIFICA FUNCIONAMIENTO Y QUEDA OPERANDO."),
         lineas=[
             SERVICIO,
             {"codigo_sap": "2009551", "producto": "2009551_CONJUNTO DAMPER MOTORIZADO NF448",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 176500.00},
         ]),
    # 6. Lavadora de 2 años: el motor tiene 10 años de cobertura, el servicio no.
    dict(numero_cita="SA-386712", numero_orden="00387004", numero_recibo="T204386712",
         serie="L2405661200", fecha="2026-07-21", tecnico="Óscar Iván Loaiza",
         codigo_seguridad="AR-421338", bodega="T204", tipo_trabajo="LLEVAR REPUESTO",
         estado_resultado="SERVICIO REPARACIÓN EN DOMICILIO", estado_cumplimiento="AL COBRO",
         observaciones=("LAVADORA NO CENTRIFUGA. SE DIAGNOSTICA MOTOR DE LAVADO CON DEVANADO "
                        "ABIERTO. SE REEMPLAZA MOTOR Y SE VERIFICA CICLO COMPLETO."),
         lineas=[
             SERVICIO,
             {"codigo_sap": "2008120", "producto": "2008120_MOTOR DE LAVADO 20KG ZOU",
              "cantidad": 1.0, "descuento": 0.0, "total_con_iva": 412800.00},
         ]),
]


# Casos que ya esperan al asesor cuando arranca el demo. Una bandeja vacía no
# demuestra nada, y estos tres son justo los que obligan a decidir a una
# persona: dos con repuestos que el motor no pudo mapear y uno con causal de
# exclusión escrita por el técnico.
CASOS_INICIALES = [
    ("SA-384990", "El equipo hace un ruido fuerte desde que vino el técnico.", "Pendiente"),
    ("SA-379441", "No estoy de acuerdo, la lavadora falló sola.", "Pendiente"),
    ("SA-373770", "Me cobraron la mano de obra y el compresor estaba en garantía.", "En revisión"),
]


def sembrar() -> None:
    db.inicializar()
    with db.conectar() as con:
        con.execute("DELETE FROM casos")
        con.execute("DELETE FROM ordenes")
        con.execute("DELETE FROM equipos")
        con.executemany(
            "INSERT INTO equipos (serie, referencia, producto, fecha_compra, cliente,"
            " documento, telefono, correo, direccion, ciudad)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)", EQUIPOS)
        for o in ORDENES:
            lineas = o.pop("lineas")
            o["total"] = round(sum(l["total_con_iva"] for l in lineas), 2)
            o["lineas_json"] = json.dumps(lineas, ensure_ascii=False)
            columnas = ", ".join(o)
            con.execute(
                f"INSERT INTO ordenes ({columnas}) VALUES ({', '.join('?' * len(o))})",
                tuple(o.values()))
            o["lineas"] = lineas

    from agent import garantias

    for cita, descripcion, estado in CASOS_INICIALES:
        orden = db.orden_por_numero(cita)
        equipo = db.equipo_por_serie(orden["serie"])
        dictamen = garantias.evaluar(orden, equipo)
        db.crear_caso(
            serie=equipo["serie"], numero_cita=cita, descripcion=descripcion,
            estado=estado, dictamen=dictamen,
            componente=", ".join(l["producto"].split("_")[-1].title()
                                 for l in dictamen["lineas"] if l["tipo"] == "repuesto"),
        )

    print(f"{len(EQUIPOS)} equipos, {len(ORDENES)} órdenes y "
          f"{len(CASOS_INICIALES)} casos sembrados en {db.BD}")


if __name__ == "__main__":
    sembrar()
