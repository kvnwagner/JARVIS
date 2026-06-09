from pathlib import Path

p = Path("api/app.py")
c = p.read_text(encoding="utf-8")

old = """def _shortcut(msg: str):
    low = msg.strip().lower()
    if low in _SITES:"""

new = """def _shortcut(msg: str):
    low = msg.strip().lower()
    # Ignorar prefijos comunes
    for prefix in ["jarvis ", "hey jarvis ", "oye jarvis "]:
        if low.startswith(prefix):
            low = low[len(prefix):]
            break
    if low in _SITES:"""

new_c = c.replace(old, new)
p.write_text(new_c, encoding="utf-8")
print("patch aplicado:", "hey jarvis" in new_c)

