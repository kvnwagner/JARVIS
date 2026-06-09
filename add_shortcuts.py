from pathlib import Path

p = Path("api/app.py")
c = p.read_text(encoding="utf-8")

shortcuts = """
SHORTCUTS = {
    "abre youtube":     ("webbrowser", "https://youtube.com"),
    "abre facebook":    ("webbrowser", "https://facebook.com"),
    "abre gmail":       ("webbrowser", "https://mail.google.com"),
    "abre instagram":   ("webbrowser", "https://instagram.com"),
    "abre disney":      ("webbrowser", "https://www.disneyplus.com"),
    "abre netflix":     ("webbrowser", "https://www.netflix.com"),
    "abre prime video": ("webbrowser", "https://www.primevideo.com"),
    "abre documentos":  ("startfile",  r"C:\\\\Users\\\\qandr\\\\Documents"),
    "abre descargas":   ("startfile",  r"C:\\\\Users\\\\qandr\\\\Downloads"),
    "abre escritorio":  ("startfile",  r"C:\\\\Users\\\\qandr\\\\Desktop"),
}

def _handle_shortcut(message: str):
    import webbrowser, os
    low = message.strip().lower()
    if low in SHORTCUTS:
        kind, target = SHORTCUTS[low]
        if kind == "webbrowser":
            webbrowser.open(target)
            return f"Abriendo {target}"
        elif kind == "startfile":
            os.startfile(target)
            return f"Abriendo carpeta"
    if low.startswith("busca ") or low.startswith("buscar "):
        import urllib.parse
        q = message[7:].strip() if low.startswith("buscar ") else message[6:].strip()
        webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(q))
        return f"Buscando {q} en Google"
    if low.startswith("youtube "):
        import urllib.parse
        q = message[8:].strip()
        webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))
        return f"Buscando {q} en YouTube"
    return None

"""

marker = "def process_chat(message: str) -> ChatResponse:"
new_c = c.replace(marker, shortcuts + marker)

# Patch process_chat to check shortcuts first
old_flow = """    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail=\"Mensaje vacio.\")
    if not llm:
        raise HTTPException(status_code=503, detail=\"LLM no configurado. Verifica tu .env\")"""

new_flow = """    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail=\"Mensaje vacio.\")
    shortcut_result = _handle_shortcut(clean_message)
    if shortcut_result:
        return ChatResponse(response=shortcut_result, tool_used=None, success=True)
    if not llm:
        raise HTTPException(status_code=503, detail=\"LLM no configurado. Verifica tu .env\")"""

new_c = new_c.replace(old_flow, new_flow)
p.write_text(new_c, encoding="utf-8")
print("api/app.py actualizado")

