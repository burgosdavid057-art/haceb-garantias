"""Puebla la base vectorial Chroma con los pasajes ya vectorizados.

    python build_vectordb.py

No gasta cuota de API: reutiliza los vectores de data/index/ que produjo
build_index.py. Correr despues de build_index.py.
"""
from agent import vectordb

if __name__ == "__main__":
    print("Poblando base vectorial Chroma...\n")
    vectordb.construir()
