from pathlib import Path

p = Path("api/app.py")
c = p.read_text(encoding="utf-8")

shortcuts_code = """
import webbrowser as _wb
import urllib.parse as _up
import os as _os

_SITES = {
    "abre youtube":     "https://youtube.com",
    "abre facebook":    "https://facebook.com",
    "abre gmail":       "https://mail.google.com",
    "abre instagram":   "https://instagram.com",
    "abre disney":      "https://www.disneyplus.com",
    "abre netflix":     "https://www.netflix.com",
    "abre prime video": "https://www.primevideo.com",
}

def _shortcut(msg: str):
    low = msg.strip().lower()
    if low in _SITES:
        _wb.open(_SITES[low])
        return f"Abriendo {_SITES[low]}"
    if low.startswith("busca ") or low.startswith("buscar "):
        q = msg[7:].strip() if low.startswith("buscar ") else msg[6:].strip()
        _wb.open("https://www.google.com/search?q=" + _up.quote(q))
        return f"Buscando {q} en Google"
    if low.startswith("youtube "):
        q = msg[8:].strip()
        _wb.open("https://www.youtube.com/results?search_query=" + _up.quote(q))
        return f"Buscando {q} en YouTube"
    if low == "abre documentos":
        _os.startfile(r"C:\\Users\\qandr\\Documents"); return "Abriendo Documentos"
    if low == "abre descargas":
        _os.startfile(r"C:\\Users\\qandr\\Downloads"); return "Abriendo Descargas"
    if low == "abre escritorio":
        _os.startfile(r"C:\\Users\\qandr\\Desktop"); return "Abriendo Escritorio"
    return None

"""

# Insertar antes de la funcion chat
marker = "@app.post(\"/chat\""
new_c = c.replace(marker, shortcuts_code + marker)

# Patch dentro de la funcion chat: interceptar antes de llegar al LLM
old = "    memory.save_message(req.message, source=\"user\")"
new = """    _sc = _shortcut(req.message)
    if _sc:
        return ChatResponse(response=_sc, tool_used=None, success=True)
    memory.save_message(req.message, source="user")"""

new_c = new_c.replace(old, new)
p.write_text(new_c, encoding="utf-8")

# Verificar
print("shortcut insertado:", "_shortcut" in new_c)
print("patch chat aplicado:", "_sc = _shortcut" in new_c)

