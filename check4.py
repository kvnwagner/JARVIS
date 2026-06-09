from pathlib import Path
c = Path("api/app.py").read_text(encoding="utf-8")
idx = c.find("def process_chat")
print("process_chat encontrado:", idx != -1)
idx2 = c.find("clean_message = message.strip()")
print("clean_message encontrado:", idx2 != -1)
if idx != -1:
    print(repr(c[idx:idx+60]))
if idx2 != -1:
    print(repr(c[idx2:idx2+120]))

