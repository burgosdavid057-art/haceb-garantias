"""
Ingesta del catalogo publico de Haceb (VTEX) + manuales de usuario.

Genera:
    data/catalog.json      -> productos normalizados con especificaciones tecnicas
    data/manuals/<ref>.txt -> texto plano del manual digital de cada producto

Solo usa la libreria estandar: se puede correr sin instalar nada.

    python ingest.py
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import fontfix

# --- Configuracion -----------------------------------------------------------

API = "https://www.haceb.com/api/catalog_system/pub/products/search"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Corte vertical: las categorias donde la cobertura de datos es ~85% en
# manual + consumo energetico + garantia + dimensiones a la vez.
CATEGORIES = {
    "Neveras": "C:/8/9/",
    "Congeladores": "C:/8/11/",
    "Lavadoras": "C:/1/2/",
    "Lavadora Secadora": "C:/1/3/",
}

DATA = Path(__file__).parent / "data"
MANUALS = DATA / "manuals"

# Especificaciones que nos interesan, con el nombre que usa la API de Haceb.
SPECS = [
    "Referencia", "Codigo", "Código", "EAN",
    "Ancho", "Alto", "Profundo", "Peso",
    "Capacidad bruta En Litros", "Capacidad neta en litros",
    "Capacidad neta congelador", "Capacidad neta refrigerador",
    "Capacidad de lavado",
    "Consumo Energía", "Clasificación energetica", "Tipo consumo energético",
    "Garantía", "Color", "Material", "Tipo de Refrigeración",
    "Tipo de producto", "Cantidad Puertas", "Dispensador de Agua",
    "Fabricador De Hielo", "Panel de Control", "País de origen",
    "Característica a destacar", "Descripción corta",
]


# --- Utilidades --------------------------------------------------------------

def safe_url(url: str) -> str:
    """Los manuales de Haceb traen espacios sin codificar y a veces sin esquema."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, parts.query, parts.fragment)
    )


def fetch(url: str, mode: str = "json", retries: int = 3):
    """GET con reintentos. mode: 'json' | 'text' | 'bytes'."""
    req = urllib.request.Request(
        safe_url(url),
        headers={"User-Agent": UA, "Accept": "application/json,text/html,*/*"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            if mode == "bytes":
                return raw
            text = raw.decode("utf-8", errors="replace")
            return json.loads(text) if mode == "json" else text
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                print(f"    ! fallo: {type(e).__name__}")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def pdf_to_text(data: bytes) -> str:
    """Extrae texto de un PDF en memoria y repara las fuentes sin ToUnicode."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print("    ! falta pypdf: pip install pypdf")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        paginas = [(p.extract_text() or "") for p in reader.pages]
    except Exception as e:
        print(f"    ! pdf ilegible: {type(e).__name__}")
        return ""
    texto = "\n\n".join(t.strip() for t in paginas if t.strip())
    # Varios manuales embeben la fuente sin tabla ToUnicode: el texto sale
    # desplazado +29 y hay que revertirlo o el RAG indexa basura.
    texto = fontfix.reparar(texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


class _TextExtractor(HTMLParser):
    """Extrae texto legible de un HTML, descartando script/style."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        raw = " ".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.text()


def first(value):
    """La API devuelve las specs como listas de un elemento."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip()).strip("-").lower()
    return s[:80] or "sin-referencia"


# --- Normalizacion -----------------------------------------------------------

def normalize(p: dict, category: str) -> dict:
    """Convierte un producto crudo de VTEX en un registro limpio."""
    specs = {}
    for key in SPECS:
        if key in p:
            v = first(p[key])
            if v not in (None, "", "No aplica"):
                specs[key] = str(v).strip()

    item = (p.get("items") or [{}])[0]
    offer = ((item.get("sellers") or [{}])[0].get("commertialOffer") or {})

    return {
        "id": str(p.get("productId", "")),
        "referencia": str(p.get("productReference") or ""),
        "nombre": p.get("productName", ""),
        "categoria": category,
        "url": p.get("link", ""),
        "precio": offer.get("Price"),
        "disponible": bool(offer.get("AvailableQuantity")),
        "ean": item.get("ean") or specs.get("EAN"),
        "specs": specs,
        "manual_url": first(p.get("Manual de uso link")),
        "certificado_url": first(p.get("Certificado")),
        "descripcion": html_to_text(p.get("description") or "")[:1200],
    }


def parse_dim(value: str | None) -> float | None:
    """'185,6 Cm' -> 185.6 ; '67 Kg' -> 67.0"""
    if not value:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(value))
    return float(m.group(1).replace(",", ".")) if m else None


def enrich(rec: dict) -> dict:
    """Agrega campos numericos derivados, para que las herramientas no parseen texto."""
    s = rec["specs"]
    rec["dim_cm"] = {
        "ancho": parse_dim(s.get("Ancho")),
        "alto": parse_dim(s.get("Alto")),
        "profundo": parse_dim(s.get("Profundo")),
    }
    rec["peso_kg"] = parse_dim(s.get("Peso"))
    rec["consumo_kwh_mes"] = parse_dim(s.get("Consumo Energía"))
    rec["clase_energetica"] = s.get("Clasificación energetica") or s.get(
        "Tipo consumo energético"
    )
    return rec


# --- Proceso principal -------------------------------------------------------

def collect_products() -> list[dict]:
    productos: list[dict] = []
    vistos: set[str] = set()

    for nombre, path in CATEGORIES.items():
        print(f"  [{nombre}]")
        desde = 0
        while True:
            url = f"{API}?fq={path}&_from={desde}&_to={desde + 49}"
            lote = fetch(url)
            if not lote:
                break
            for p in lote:
                pid = str(p.get("productId"))
                if pid in vistos:
                    continue
                vistos.add(pid)
                productos.append(enrich(normalize(p, nombre)))
            print(f"    +{len(lote)} (total {len(productos)})")
            if len(lote) < 50:
                break
            desde += 50
            time.sleep(0.4)
    return productos


def manual_filename(url: str) -> str:
    """Nombre estable a partir de la URL: varios productos comparten manual."""
    base = urllib.parse.unquote(url.split("?")[0].rstrip("/").split("/")[-1])
    base = re.sub(r"\.(pdf|html?)$", "", base, flags=re.I)
    corto = hashlib.sha1(url.encode()).hexdigest()[:6]
    return f"{slug(base)}-{corto}.txt"


def download_manuals(productos: list[dict]) -> None:
    """Descarga cada manual una sola vez (PDF o HTML) y lo guarda como texto."""
    MANUALS.mkdir(parents=True, exist_ok=True)
    con_manual = [p for p in productos if p.get("manual_url")]

    # Varios productos apuntan al mismo manual -> descargar por URL unica.
    por_url: dict[str, list[dict]] = {}
    for p in con_manual:
        por_url.setdefault(p["manual_url"], []).append(p)

    print(f"  {len(con_manual)} productos con manual · {len(por_url)} manuales unicos")

    for i, (url, prods) in enumerate(por_url.items(), 1):
        nombre = manual_filename(url)
        destino = MANUALS / nombre
        es_pdf = ".pdf" in url.lower()

        if destino.exists() and destino.stat().st_size > 500:
            print(f"    [{i}/{len(por_url)}] cache  {nombre}")
            for p in prods:
                p["manual_file"] = f"data/manuals/{nombre}"
            continue

        try:
            if es_pdf:
                data = fetch(url, mode="bytes")
                texto = pdf_to_text(data) if data else ""
            else:
                html = fetch(url, mode="text")
                texto = html_to_text(html) if html else ""
        except Exception as e:
            # Un manual roto no puede tumbar la ingesta completa.
            print(f"    [{i}/{len(por_url)}] error  {type(e).__name__}")
            texto = ""

        if len(texto) < 400:
            print(f"    [{i}/{len(por_url)}] vacio  {nombre} ({len(texto)} chars)")
            for p in prods:
                p["manual_file"] = None
            continue

        modelos = ", ".join(sorted({p["referencia"] for p in prods if p["referencia"]}))
        encabezado = (
            f"MANUAL DE USUARIO HACEB\n"
            f"Aplica a las referencias: {modelos or 'n/d'}\n"
            f"Productos: {'; '.join(p['nombre'] for p in prods[:5])}\n"
            f"Fuente: {url}\n"
            f"{'=' * 70}\n\n"
        )
        destino.write_text(encabezado + texto, encoding="utf-8")
        tipo = "pdf " if es_pdf else "html"
        print(f"    [{i}/{len(por_url)}] ok {tipo} {nombre} ({len(texto):,} chars)")
        for p in prods:
            p["manual_file"] = f"data/manuals/{nombre}"
        time.sleep(0.3)


def report(productos: list[dict]) -> None:
    n = len(productos)
    def pct(cond):
        c = sum(1 for p in productos if cond(p))
        return f"{c}/{n} ({100 * c // max(n, 1)}%)"

    print("\n  Cobertura de datos:")
    print(f"    manual descargado   {pct(lambda p: p.get('manual_file'))}")
    print(f"    consumo kWh/mes     {pct(lambda p: p.get('consumo_kwh_mes'))}")
    print(f"    garantia            {pct(lambda p: p['specs'].get('Garantía'))}")
    print(f"    dimensiones         {pct(lambda p: all(p['dim_cm'].values()))}")
    print(f"    certificado         {pct(lambda p: p.get('certificado_url'))}")
    print(f"    precio              {pct(lambda p: p.get('precio'))}")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    print("\n1. Catalogo (API publica VTEX de Haceb)")
    productos = collect_products()
    if not productos:
        print("  No se obtuvo ningun producto. Revisa la conexion.")
        return

    print("\n2. Manuales de usuario")
    download_manuals(productos)

    salida = DATA / "catalog.json"
    salida.write_text(
        json.dumps(productos, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n3. Guardado: {salida.relative_to(Path.cwd())} ({len(productos)} productos)")
    report(productos)
    print()


if __name__ == "__main__":
    main()
