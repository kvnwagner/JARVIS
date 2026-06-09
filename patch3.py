from pathlib import Path

p = Path("api/app.py")
c = p.read_text(encoding="utf-8")

old = """_SITES = {
    "abre youtube":     "https://youtube.com",
    "abre facebook":    "https://facebook.com",
    "abre gmail":       "https://mail.google.com",
    "abre instagram":   "https://instagram.com",
    "abre disney":      "https://www.disneyplus.com",
    "abre netflix":     "https://www.netflix.com",
    "abre prime video": "https://www.primevideo.com",
}"""

new = """_SITES = {
    "abre youtube":      "https://youtube.com",
    "abre facebook":     "https://facebook.com",
    "abre gmail":        "https://mail.google.com",
    "abre instagram":    "https://instagram.com",
    "abre disney":       "https://www.disneyplus.com",
    "abre disney plus":  "https://www.disneyplus.com",
    "abre disney+":      "https://www.disneyplus.com",
    "abre netflix":      "https://www.netflix.com",
    "abre prime":        "https://www.primevideo.com",
    "abre prime video":  "https://www.primevideo.com",
    "abre twitch":       "https://www.twitch.tv",
    "abre twitter":      "https://twitter.com",
    "abre x":            "https://twitter.com",
    "abre whatsapp":     "https://web.whatsapp.com",
    "abre reddit":       "https://www.reddit.com",
    "abre linkedin":     "https://www.linkedin.com",
    "abre tiktok":       "https://www.tiktok.com",
}"""

new_c = c.replace(old, new)

# Agregar endpoint TTS si no existe
if "/tts/speak" not in new_c:
    tts_endpoints = """
@app.post("/tts/speak")
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
    return {"ok": True}

"""
    new_c = new_c.replace("@app.post(\"/execute\"", tts_endpoints + "@app.post(\"/execute\"")

p.write_text(new_c, encoding="utf-8")
print("Sites actualizados:", "_SITES" in new_c)
print("TTS endpoint:", "/tts/speak" in new_c)

