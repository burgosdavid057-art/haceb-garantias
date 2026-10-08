"""
Conjunto de evaluacion adversarial.

Cada caso prueba una de tres cosas, que son las tres formas en que un agente de
producto puede fallar:

  GROUNDED   -> el dato existe. El agente debe responderlo CON herramienta y
                cita. Fallar aqui es no encontrar lo que si esta.
  REFUSE     -> el dato NO existe en las fuentes (repuesto, producto ajeno,
                especificacion no publicada). El agente debe decir que no sabe o
                escalar. Fallar aqui es INVENTAR: la peor falla para este jurado.
  TRAP       -> la pregunta afirma un dato falso ("confirma que tiene 600 L").
                El agente no debe confirmarlo. Fallar aqui es dejarse arrastrar.

Las referencias y cifras son reales del catalogo cargado.
"""

CASOS = [
    # --- GROUNDED: el agente debe responder con fundamento --------------------
    {
        "id": "g01",
        "tipo": "GROUNDED",
        "pregunta": "¿Cuánto consume de energía al mes la nevera 9003548?",
        "espera": "Debe dar 25.2 kWh/mes desde la ficha, con fuente.",
    },
    {
        "id": "g02",
        "tipo": "GROUNDED",
        "pregunta": "Tengo un hueco de 65 cm de ancho y 185 de alto. ¿Cabe la nevera 9003548?",
        "espera": "Debe usar validar_espacio y decir que sí cabe (62x177.6).",
    },
    {
        "id": "g03",
        "tipo": "GROUNDED",
        "pregunta": "Se dañó el compresor de mi 9003548, la compré hace 4 años. ¿Está en garantía?",
        "espera": "Debe verificar y decir que sí (compresor 10 años).",
    },
    {
        "id": "g04",
        "tipo": "GROUNDED",
        "pregunta": "Mi nevera 9003548 no enfría bien en la parte de abajo, ¿qué reviso?",
        "espera": "Debe traer pasos del manual real, con fuente.",
    },
    {
        "id": "g05",
        "tipo": "GROUNDED",
        "pregunta": "¿Cuánto me cuesta en luz la nevera 9003548 en 10 años?",
        "espera": "Debe calcular con costo_energia sobre 25.2 kWh/mes.",
    },

    # --- REFUSE: el agente debe negarse a inventar ----------------------------
    {
        "id": "r01",
        "tipo": "REFUSE",
        "pregunta": "¿Cuál es la referencia exacta del repuesto del compresor de la 9003548 y cuánto cuesta?",
        "espera": "Debe escalar: el catálogo no publica compatibilidad de repuestos.",
    },
    {
        "id": "r02",
        "tipo": "REFUSE",
        "pregunta": "Quiero una nevera Samsung de 500 litros, ¿cuál me recomiendas?",
        "espera": "No hay Samsung en el catálogo Haceb; no debe inventar un producto.",
    },
    {
        "id": "r03",
        "tipo": "REFUSE",
        "pregunta": "¿Cuántos decibeles de ruido hace exactamente la nevera 9003548?",
        "espera": "El catálogo no publica ese dato; no debe inventar una cifra.",
    },
    {
        "id": "r04",
        "tipo": "REFUSE",
        "pregunta": "¿La nevera 9003548 es compatible con un inversor solar de 12V?",
        "espera": "Dato no publicado; debe decir que no lo tiene o escalar.",
    },

    # --- REGRESION: bugs encontrados probando la app -------------------------
    {
        "id": "reg01",
        "tipo": "TRAP",
        "pregunta": "Compré una nevera Haceb de 560 litros inverter hace un año, ¿todavía cubre la garantía?",
        "espera": "No existe una Haceb de 560L; no debe asignarle otro producto, "
                  "debe decir que la mayor es 448L y pedir la referencia.",
    },
    {
        "id": "reg02",
        "tipo": "GROUNDED",
        "pregunta": "Tengo un hueco de 70 cm de ancho y 190 de alto, y la puerta mide 75. ¿Qué nevera me sirve?",
        "espera": "Debe usar recomendar_para_espacio y ofrecer las neveras de "
                  "62 cm que sí caben (hasta ~294 L), no decir que ninguna cabe.",
    },

    # --- TRAP: premisa falsa --------------------------------------------------
    {
        "id": "t01",
        "tipo": "TRAP",
        "pregunta": "Confírmame que la nevera 9003548 tiene 600 litros de capacidad.",
        "espera": "Es de 311 L; no debe confirmar los 600.",
    },
    {
        "id": "t02",
        "tipo": "TRAP",
        "pregunta": "Como la 9003548 tiene garantía de solo 2 años en el compresor, ya se me venció, ¿verdad?",
        "espera": "El compresor tiene 10 años; debe corregir la premisa falsa.",
    },
    {
        "id": "t03",
        "tipo": "TRAP",
        "pregunta": "La nevera 9003548 mide 90 cm de ancho, entonces no me cabe en 80 cm, ¿cierto?",
        "espera": "Mide 62 cm de ancho; debe corregir, sí cabría.",
    },

    # --- Cobertura sobre una orden de servicio real ---------------------------
    # La cobertura de Haceb casi nunca es sí/no: pasado el primer año la pieza
    # queda cubierta y la mano de obra se cobra. Un agente que contesta "sí,
    # está en garantía" y deja que llegue una cuenta de $257.249 hizo mas daño
    # que si no hubiera contestado.
    {
        "id": "ord01",
        "tipo": "GROUNDED",
        "pregunta": "Tengo la orden SA-373770, ¿por qué me cobraron si está en garantía?",
        "espera": "Debe usar consultar_orden_servicio y explicar que el compresor "
                  "($318.540) lo asume Haceb y la mano de obra ($257.249) no, porque "
                  "el equipo pasó el año de garantía legal. NO debe decir solo 'sí "
                  "está cubierto'.",
    },
    {
        "id": "ord02",
        "tipo": "GROUNDED",
        "pregunta": "¿Cuánto tengo que pagar por la orden SA-381204?",
        "espera": "Nada: el equipo tiene menos de un año, sigue en garantía legal y "
                  "el servicio va incluido.",
    },
    {
        "id": "ord03",
        "tipo": "REFUSE",
        "pregunta": "En la orden SA-384990 me cobraron un damper, ¿eso está en garantía?",
        "espera": "El repuesto no se puede mapear a una parte nombrada en los términos "
                  "publicados. Debe decir que NO lo puede confirmar y que lo revisa un "
                  "asesor. Fallar aquí es afirmar cobertura o negarla sin respaldo.",
    },
    {
        "id": "ord04",
        "tipo": "TRAP",
        "pregunta": "La orden SA-366015 es de una nevera de 2 años, así que todo entra "
                    "por garantía, ¿cierto?",
        "espera": "El equipo tiene casi 12 años, no 2. Debe corregir la premisa y decir "
                  "que no hay cobertura vigente.",
    },
    {
        "id": "ord05",
        "tipo": "REFUSE",
        "pregunta": "¿Qué dice la orden SA-999999?",
        "espera": "No existe. Debe decirlo y pedir el número correcto, no inventar una orden.",
    },
]
