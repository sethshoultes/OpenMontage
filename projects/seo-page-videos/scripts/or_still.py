"""One concept still from OpenRouter (an allowed image route), in the page videos' flat editorial vector style.

Usage: or_still.py <out.png> "<what the still shows>" [--palette warm|cool] [--model google/gemini-3-pro-image]
Reads OPENROUTER_API_KEY from the environment (source ~/.config/dev-secrets/secrets.env first). Writes a 16:9 PNG, checked non-empty.
"""
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

STYLE = ("Bold flat editorial vector illustration, razor-sharp hard edges, crisp thin outlines, high contrast. "
         "Palette: ground #17110c (warm near-black), art in cream #f1e6d6, accent orange #ff6b2c. Flat solid ground, "
         "art centred and large (about 60 to 70 percent of the frame width), nothing touching an edge. "
         "No glow, haze, gradients, soft shadows or textures. No people, no faces, no logos, no brand marks, no text or letters "
         "unless the description asks for a specific word. 16:9 landscape.")


def main(out, what, model):
    key = os.environ["OPENROUTER_API_KEY"]
    body = {"model": model, "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": "16:9", "image_size": "2K"},
            "messages": [{"role": "user", "content": f"{STYLE}\n\nSubject: {what}"}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    msg = r["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        sys.exit(f"no image in the reply: {str(msg)[:300]}")
    url = imgs[0]["image_url"]["url"]
    data = base64.b64decode(re.sub(r"^data:image/[a-z]+;base64,", "", url))
    Path(out).write_bytes(data)
    assert Path(out).stat().st_size > 10000, "image is empty or too small"
    print("ok", out, len(data), "bytes", model, "cost", r.get("usage", {}).get("cost"))


if __name__ == "__main__":
    a = sys.argv[1:]
    model = "google/gemini-3-pro-image"
    if "--model" in a:
        i = a.index("--model")
        model = a[i + 1]
        del a[i:i + 2]
    if len(a) != 2:
        sys.exit(__doc__)
    main(a[0], a[1], model)
