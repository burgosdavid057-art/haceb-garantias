"""Precomputa los vectores de todos los manuales. Correr una sola vez.

    python build_index.py
"""
from agent import catalog, knowledge

manuales = sorted({p["manual_file"] for p in catalog.productos() if p.get("manual_file")})
print(f"{len(manuales)} manuales a indexar\n")
total = 0
for i, m in enumerate(manuales, 1):
    try:
        n = knowledge.construir_indice(m)
        total += n
        print(f"  [{i}/{len(manuales)}] {n:>3} pasajes  {m.split('/')[-1]}")
    except Exception as e:
        print(f"  [{i}/{len(manuales)}] ERROR {type(e).__name__}: {str(e)[:80]}")
print(f"\n{total} pasajes vectorizados en data/index/")
