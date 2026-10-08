"""
Reparacion de texto de PDFs con fuente subset sin tabla ToUnicode.

Varios manuales de Haceb embeben la fuente sin el mapa ToUnicode, asi que los
extractores (pypdf, pymupdf) devuelven los codigos crudos de glifo en vez del
texto. El cifrado resulta ser un desplazamiento fijo de +29 sobre todo el
juego de caracteres, espacios y puntuacion incluidos:

    real = extraido + 29

    'H' -> 'e'      'Q' -> 'n'      '6' -> 'S'      '9' -> 'V'
    '\\x03' -> ' '   '\\x0b' -> '('

Por eso los fragmentos danados se ven como una sola palabra larga: el espacio
quedo convertido en el caracter de control 0x03. Ese 0x03 es justamente la
firma que permite detectarlos sin ambiguedad, porque el texto sano nunca lo
contiene.

Las vocales acentuadas y las ligaduras viven fuera del rango desplazado y
necesitan tabla propia (ver ACENTOS).
"""

from __future__ import annotations

import re

SHIFT = 29

# Caracteres que no siguen el desplazamiento: acentos y ligaduras tipograficas.
# Derivados de los manuales reales de Haceb.
ACENTOS = {
    "i": "á", "u": "é", "t": "í", "y": "ó", "z": "ú",
    "x": "ñ", "|": "ü",
    "À": "fi", "Á": "fl", "Â": "ff",
    "ﬁ": "fi", "ﬂ": "fl",
}

# La firma del cifrado: el espacio convertido en control 0x03.
MARCA = "\x03"

# Un fragmento cifrado es una tirada de caracteres desplazables que contiene al
# menos un 0x03. Dos exclusiones importantes en el juego de caracteres:
#   - el espacio real (0x20) nunca aparece dentro de un fragmento cifrado,
#     porque alli seria 0x03; sirve entonces como frontera natural.
#   - \t \n \r son saltos reales del documento, no caracteres cifrados
#     (0x0b y 0x0c si lo son: se traducen a '(' y ')').
CUERPO = r"[\x02-\x08\x0b\x0c\x0e-\x1f\x21-\x7eÀ-Âﬁﬂ]"
CIFRADO = re.compile(rf"{CUERPO}*\x03{CUERPO}*")


def _shift(texto: str) -> str:
    salida = []
    for ch in texto:
        if ch in ACENTOS:
            salida.append(ACENTOS[ch])
            continue
        code = ord(ch) + SHIFT
        salida.append(chr(code) if 0x20 <= code <= 0x7E else ch)
    return "".join(salida)


# Simbolos que quedan fuera del desplazamiento porque viven en subsets de
# fuente distintos segun la pagina. Son decorativos o unidades.
SUELTOS = {"\x84": "•", "\x94": "≤", "\x95": "≥"}

# 0x83 es ambiguo: grado cuando sigue a un numero, vinneta al inicio de item.
_GRADO = re.compile(r"(?<=[0-9])\x83")


def _simbolos(texto: str) -> str:
    texto = _GRADO.sub("°", texto)
    texto = texto.replace("\x83", "•")
    for k, v in SUELTOS.items():
        texto = texto.replace(k, v)
    return texto


def reparar(texto: str) -> str:
    """Devuelve el texto con los fragmentos cifrados traducidos a espanol."""
    if MARCA in texto:
        texto = CIFRADO.sub(lambda m: _shift(m.group(0)), texto)
    return _simbolos(texto)


def stats(texto: str) -> dict:
    """Metricas para reportar durante la ingesta."""
    fragmentos = CIFRADO.findall(texto)
    return {
        "fragmentos": len(fragmentos),
        "caracteres": sum(len(f) for f in fragmentos),
        "cifrado": bool(fragmentos),
    }


def residuos(texto: str) -> dict[str, int]:
    """Caracteres raros que quedaron tras reparar: sirven para completar ACENTOS."""
    from collections import Counter
    sobra = Counter(
        ch for ch in texto
        if ord(ch) > 0x7E and ch not in "áéíóúñüÁÉÍÓÚÑÜ¿¡°±ºª€•—–’“”…\xa0"
    )
    return dict(sobra.most_common(12))


if __name__ == "__main__":
    pruebas = [
        "HQ\x03OD\x03SRVLFLyQ\x03PiV\x03IUtR\x03UHIULJHUDGRU",
        "\x0b9HU\x03ÀJXUDV\x0322\x03\\\x0323\x0c",
        "6L\x03D\x03ORV\x03\x14\x18\x03GtDV\x03GH\x03KDEHU\x03UHDOL]DGR",
        "El condensador esta poco ventilado. COMPARTIMIENTO INFERIOR",
    ]
    for p in pruebas:
        print(f"  IN : {p!r}")
        print(f"  OUT: {reparar(p)}\n")
