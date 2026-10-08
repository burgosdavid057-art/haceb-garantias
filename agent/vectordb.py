"""
Base de datos vectorial (Chroma) sobre los manuales de Haceb.

Esta es la pieza que sostiene la promesa "el agente no alucina": las respuestas
sobre uso, fallas y mantenimiento salen de una busqueda semantica en los
manuales oficiales, no de la memoria del modelo.

Se usa Chroma como almacen vectorial persistente. Los vectores son los que ya
calculo build_index.py con gemini-embedding-001; aqui solo se cargan, asi que
poblar la base NO gasta cuota de API. En consulta se embebe solo la pregunta.

    from agent import vectordb
    vectordb.construir()                     # una vez, poblar Chroma
    vectordb.buscar("no enfria", manual)     # en cada consulta
"""

from __future__ import annotations

import json
from pathlib import Path

from . import knowledge

RAIZ = Path(__file__).resolve().parent.parent
CHROMA_DIR = RAIZ / "data" / "chroma"
COLECCION = "manuales_haceb"

_cliente = None
_coleccion = None


def _client():
    global _cliente
    if _cliente is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _cliente = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _cliente


def coleccion():
    global _coleccion
    if _coleccion is None:
        _coleccion = _client().get_or_create_collection(
            COLECCION, metadata={"hnsw:space": "cosine"}
        )
    return _coleccion


def disponible() -> bool:
    """True si la base vectorial ya esta poblada."""
    try:
        return coleccion().count() > 0
    except Exception:
        return False


def construir(verboso: bool = True) -> int:
    """Puebla Chroma con los pasajes + vectores ya calculados. Idempotente."""
    global _coleccion

    # Empezar de cero para que reconstruir no duplique pasajes.
    try:
        _client().delete_collection(COLECCION)
    except Exception:
        pass
    _coleccion = None

    col = coleccion()
    manuales = sorted(
        {p["manual_file"] for p in _catalogo() if p.get("manual_file")}
    )

    total = 0
    for manual in manuales:
        indice = knowledge._ruta_indice(manual)
        if not indice.exists():
            if verboso:
                print(f"  (sin vectores, se omite) {manual}")
            continue

        pasajes, *_ = knowledge._indice(manual)
        vectores = json.loads(indice.read_text(encoding="utf-8"))["vectores"]
        if len(pasajes) != len(vectores):
            if verboso:
                print(f"  ! desajuste en {manual}: {len(pasajes)} vs {len(vectores)}")
            continue

        stem = Path(manual).stem
        col.add(
            ids=[f"{stem}#{i}" for i in range(len(pasajes))],
            embeddings=vectores,
            documents=[p["texto"] for p in pasajes],
            metadatas=[
                {"manual_file": manual, "seccion": p["seccion"] or "(sin encabezado)"}
                for p in pasajes
            ],
        )
        total += len(pasajes)
        if verboso:
            print(f"  + {len(pasajes):>3} pasajes  {stem}")

    if verboso:
        print(f"\n{total} pasajes en la base vectorial ({col.count()} en Chroma)")
    return total


def buscar(pregunta: str, manual_file: str, k: int = 4) -> list[dict]:
    """Consulta semantica sobre UN manual. Vacio si no hay base o falla la API."""
    if not disponible():
        return []
    try:
        q = knowledge.embeber([pregunta], "RETRIEVAL_QUERY")[0]
    except Exception:
        return []  # sin cuota/red: el hibrido cae a BM25 solo

    try:
        r = coleccion().query(
            query_embeddings=[q],
            n_results=k,
            where={"manual_file": manual_file},
        )
    except Exception:
        return []

    docs = (r.get("documents") or [[]])[0]
    metas = (r.get("metadatas") or [[]])[0]
    dist = (r.get("distances") or [[]])[0]
    salida = []
    for doc, meta, d in zip(docs, metas, dist):
        salida.append({
            "texto": doc,
            "seccion": meta.get("seccion", ""),
            "similitud": round(1 - d, 3),  # cosine distance -> similitud
        })
    return salida


def _catalogo():
    from . import catalog
    return catalog.productos()
