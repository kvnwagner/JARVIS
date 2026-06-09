from pathlib import Path
c = Path("api/app.py").read_text(encoding="utf-8")
print("shortcut en app.py:", "_handle_shortcut" in c)
print("SHORTCUTS en app.py:", "SHORTCUTS = {" in c)

