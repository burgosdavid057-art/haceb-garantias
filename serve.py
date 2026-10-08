"""Arranca el demo completo.

    python serve.py          ->  http://localhost:5050

Siembra la base si hace falta, para que el demo nunca arranque vacío.
"""

from agent import db
from web.server import app


def precalentar() -> None:
    """Carga el modelo en memoria antes de que llegue el primer usuario.

    Ollama descarga el modelo de RAM tras unos minutos de inactividad y volver a
    cargarlo cuesta ~20 s. Medido: con el modelo frío el primer turno tardó 30 s
    en decidir la herramienta; caliente, 9 s. Sin esto, la persona que abre el
    chat en el demo se come esa diferencia — y es la primera impresión.
    """
    import threading

    def _cargar():
        try:
            from agent import llm
            from openai import OpenAI

            cfg = llm.config_openai()
            OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"], timeout=300) \
                .chat.completions.create(
                    model=cfg["modelo"],
                    messages=[{"role": "user", "content": "ok"}],
                    max_tokens=1)
            print("  modelo listo en memoria\n")
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: no se pudo precalentar el modelo ({type(e).__name__}). "
                  f"¿Está corriendo `ollama serve`?\n")

    threading.Thread(target=_cargar, daemon=True).start()


if __name__ == "__main__":
    db.inicializar()
    if not db.orden_por_numero("SA-373770"):
        from seed import sembrar
        sembrar()

    print("\n  Haceb demo   http://localhost:5050")
    print("  Portal       http://localhost:5050/portal   (asesor / haceb2026)")
    print("  calentando el modelo…")
    precalentar()
    app.run(host="0.0.0.0", port=5050, debug=False)
