from pathlib import Path

p = Path("api/app.py")
c = p.read_text(encoding="utf-8")

old = """@app.post("/tts/speak")
def tts_speak(req: dict):
    from voice.tts import JarvisTTS
    try:
        tts = JarvisTTS()
        text = req.get("text", "")
        if text:
            tts.speak_async(text)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/tts/stop")
def tts_stop():
    return {"ok": True}"""

new = """_tts_instance = None

def _get_tts():
    global _tts_instance
    if _tts_instance is None:
        from voice.tts import JarvisTTS
        _tts_instance = JarvisTTS()
    return _tts_instance

@app.post("/tts/speak")
def tts_speak(req: dict):
    try:
        text = req.get("text", "")
        if text:
            _get_tts().speak_async(text)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/tts/stop")
def tts_stop():
    try:
        _get_tts().stop()
    except Exception:
        pass
    return {"ok": True}"""

new_c = c.replace(old, new)
p.write_text(new_c, encoding="utf-8")
print("patch aplicado:", "_tts_instance" in new_c)

