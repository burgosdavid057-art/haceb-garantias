"""
Base de datos local del demo: equipos vendidos, ordenes de servicio y casos.

SQLite porque es stdlib y el demo corre en una sola maquina. Un archivo,
cero servidores que levantar.

Las tres tablas responden a tres preguntas distintas:
  equipos  -> ¿desde cuando tiene el cliente este equipo?   (fecha de compra REAL)
  ordenes  -> ¿que le hizo el tecnico y que se cobro?       (la factura)
  casos    -> ¿que decidio el sistema y que hizo el asesor?  (la bandeja)

`equipos` es la pieza que cierra el hueco de fondo: sin ella habria que creerle
al cliente cuando dice "la compre hace dos años", y la garantia se calcularia
sobre un dato que nadie verifico.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BD = RAIZ / "data" / "haceb.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS equipos (
    serie            TEXT PRIMARY KEY,
    referencia       TEXT NOT NULL,
    producto         TEXT NOT NULL,
    fecha_compra     TEXT NOT NULL,
    cliente          TEXT,
    documento        TEXT,
    telefono         TEXT,
    correo           TEXT,
    direccion        TEXT,
    ciudad           TEXT
);

CREATE TABLE IF NOT EXISTS ordenes (
    numero_cita         TEXT PRIMARY KEY,
    numero_orden        TEXT,
    numero_recibo       TEXT,
    serie               TEXT NOT NULL,
    fecha               TEXT NOT NULL,
    tecnico             TEXT,
    codigo_seguridad    TEXT,
    bodega              TEXT,
    tipo_trabajo        TEXT,
    estado_resultado    TEXT,
    estado_cumplimiento TEXT,
    observaciones       TEXT,
    total               REAL,
    lineas_json         TEXT NOT NULL,
    FOREIGN KEY (serie) REFERENCES equipos(serie)
);

CREATE TABLE IF NOT EXISTS casos (
    ticket        TEXT PRIMARY KEY,
    creado        TEXT NOT NULL,
    serie         TEXT,
    numero_cita   TEXT,
    componente    TEXT,
    descripcion   TEXT,
    canal         TEXT DEFAULT 'chat-web',
    estado        TEXT NOT NULL DEFAULT 'Pendiente',
    dictamen_json TEXT,
    asesor        TEXT,
    nota_asesor   TEXT,
    actualizado   TEXT,
    -- Sesion del navegador que radico el caso. Es lo que permite devolverle al
    -- cliente la decision del asesor en su mismo chat, sin pedirle datos ni
    -- montar cuentas de usuario para un demo.
    sesion        TEXT,
    -- Marca de la ultima decision del asesor que ya se le mostro al cliente.
    avisado       TEXT
);

CREATE INDEX IF NOT EXISTS idx_ordenes_serie ON ordenes(serie);
CREATE INDEX IF NOT EXISTS idx_casos_estado  ON casos(estado);
"""

# Estados que puede tener un caso en la bandeja del asesor. El orden importa:
# es el que se muestra en el portal.
ESTADOS = ("Pendiente", "En revisión", "Aprobada", "Rechazada", "Info solicitada")


def conectar() -> sqlite3.Connection:
    BD.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BD)
    con.row_factory = sqlite3.Row
    # Las escrituras del chat y las del portal ocurren en hilos distintos del
    # mismo proceso Flask; WAL evita que una lectura bloquee una escritura.
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def inicializar() -> None:
    with conectar() as con:
        con.executescript(ESQUEMA)


def _fila(f: sqlite3.Row | None) -> dict | None:
    return dict(f) if f is not None else None


# --- Consultas -----------------------------------------------------------

def equipo_por_serie(serie: str) -> dict | None:
    with conectar() as con:
        f = con.execute(
            "SELECT * FROM equipos WHERE UPPER(serie)=UPPER(?)", (serie.strip(),)
        ).fetchone()
    return _fila(f)


def orden_por_numero(numero: str) -> dict | None:
    """Busca una orden por numero de cita, de orden o de recibo.

    El cliente lee el numero de un papel: no sabe cual de los tres es, y en la
    factura de Haceb aparecen los tres. Se aceptan todos.
    """
    n = (numero or "").strip().upper()
    if not n:
        return None
    with conectar() as con:
        f = con.execute(
            "SELECT * FROM ordenes WHERE UPPER(numero_cita)=? OR UPPER(numero_orden)=?"
            " OR UPPER(numero_recibo)=?",
            (n, n, n),
        ).fetchone()
    orden = _fila(f)
    if orden:
        orden["lineas"] = json.loads(orden.pop("lineas_json"))
    return orden


def ordenes_de_serie(serie: str) -> list[dict]:
    with conectar() as con:
        filas = con.execute(
            "SELECT * FROM ordenes WHERE UPPER(serie)=UPPER(?) ORDER BY fecha DESC",
            (serie.strip(),),
        ).fetchall()
    ordenes = []
    for f in filas:
        o = dict(f)
        o["lineas"] = json.loads(o.pop("lineas_json"))
        ordenes.append(o)
    return ordenes


# --- Casos ---------------------------------------------------------------

def crear_caso(**campos) -> dict:
    import datetime
    import uuid

    ticket = "GAR-" + uuid.uuid4().hex[:6].upper()
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    caso = {
        "ticket": ticket,
        "creado": ahora,
        "actualizado": ahora,
        "estado": campos.pop("estado", "Pendiente"),
        "dictamen_json": json.dumps(campos.pop("dictamen", None), ensure_ascii=False),
        **campos,
    }
    columnas = ", ".join(caso)
    marcas = ", ".join("?" * len(caso))
    with conectar() as con:
        con.execute(f"INSERT INTO casos ({columnas}) VALUES ({marcas})", tuple(caso.values()))
    return caso_por_ticket(ticket)


def caso_por_ticket(ticket: str) -> dict | None:
    with conectar() as con:
        f = con.execute(
            "SELECT * FROM casos WHERE UPPER(ticket)=UPPER(?)", (ticket.strip(),)
        ).fetchone()
    if f is None:
        return None
    caso = dict(f)
    caso["dictamen"] = json.loads(caso.pop("dictamen_json") or "null")
    return caso


def listar_casos(estado: str | None = None) -> list[dict]:
    sql = "SELECT * FROM casos"
    args: tuple = ()
    if estado:
        sql += " WHERE estado=?"
        args = (estado,)
    sql += " ORDER BY creado DESC"
    with conectar() as con:
        filas = con.execute(sql, args).fetchall()
    casos = []
    for f in filas:
        c = dict(f)
        c["dictamen"] = json.loads(c.pop("dictamen_json") or "null")
        casos.append(c)
    return casos


def actualizar_caso(ticket: str, estado: str, asesor: str, nota: str = "") -> dict | None:
    """Cambia el estado de un caso desde la bandeja del asesor.

    Valida el estado contra la lista cerrada: un estado libre desde el front
    dejaria casos invisibles en los filtros del portal.
    """
    import datetime

    if estado not in ESTADOS:
        raise ValueError(f"estado invalido: {estado!r}. Validos: {', '.join(ESTADOS)}")
    with conectar() as con:
        cur = con.execute(
            "UPDATE casos SET estado=?, asesor=?, nota_asesor=?, actualizado=?"
            " WHERE UPPER(ticket)=UPPER(?)",
            (estado, asesor, nota, datetime.datetime.now().isoformat(timespec="seconds"),
             ticket.strip()),
        )
        if cur.rowcount == 0:
            return None
    return caso_por_ticket(ticket)


def marcar_sesion(ticket: str, sesion: str) -> None:
    """Asocia un caso recién radicado con la sesión del navegador que lo creó."""
    with conectar() as con:
        con.execute("UPDATE casos SET sesion=? WHERE UPPER(ticket)=UPPER(?)",
                    (sesion, ticket.strip()))


def novedades_de_sesion(sesion: str) -> list[dict]:
    """Casos de esta sesión con una decisión del asesor que el cliente aún no vio.

    Al devolverlas quedan marcadas como avisadas, para no repetir el mismo aviso
    en cada consulta.
    """
    if not sesion:
        return []
    with conectar() as con:
        filas = con.execute(
            "SELECT * FROM casos WHERE sesion=? AND asesor IS NOT NULL"
            " AND (avisado IS NULL OR avisado <> actualizado)",
            (sesion,),
        ).fetchall()
        novedades = []
        for f in filas:
            c = dict(f)
            c["dictamen"] = json.loads(c.pop("dictamen_json") or "null")
            novedades.append(c)
            con.execute("UPDATE casos SET avisado=? WHERE ticket=?",
                        (c["actualizado"], c["ticket"]))
    return novedades


def resumen_bandeja() -> dict:
    with conectar() as con:
        filas = con.execute(
            "SELECT estado, COUNT(*) n FROM casos GROUP BY estado"
        ).fetchall()
    por_estado = {f["estado"]: f["n"] for f in filas}
    return {
        "total": sum(por_estado.values()),
        "por_estado": {e: por_estado.get(e, 0) for e in ESTADOS},
    }
