"""Animated tour of the live site: headless Chrome screenshots of link states, captioned and
cross-faded into content/animation/dashboard.mp4 (H.264, for X) and dashboard.gif.

Needs Google Chrome, Pillow, numpy and imageio + imageio-ffmpeg (MP4 is skipped without them).
Usage: python src/animate.py
"""
import functools
import http.server
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from paths import PROJECT

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = PROJECT / "content" / "animation"
W, H = 1280, 720
FPS, HOLD, FADE = 24, 2.6, 0.5
SCENES = [
    ("", "4,485 wards. One forecast for 4 November."),
    ("section=map-section", "Each ward coloured by its favourite. Paler means less certain."),
    ("view=rating&section=map-section", "Red wards are toss-ups: no party above a 60% chance."),
    ("view=flip&section=map-section", "1,232 wards are forecast to change hands since 2021."),
    ("view=share&party=MK&prov=KwaZulu-Natal&section=map-section", "MK's strength is concentrated in KwaZulu-Natal."),
    ("view=fav&muni=ETH&section=map-section", "eThekwini: MK is favoured to be the largest party."),
    ("muni=JHB&ward=79800092&section=map-section", "Johannesburg ward 92: a coin flip between the DA and ANC."),
    ("muni=CPT&section=map-section", "Cape Town: the only metro likely to keep a majority."),
    ("section=metros", "Seat-by-seat: seven of eight metros look hung."),
    ("section=coalitions", "Who can govern with whom: the coalition maths."),
    ("section=backtest", "Tested on 2016 and 2021: it beat simple rules both times."),
]
FONT = "/System/Library/Fonts/Avenir Next.ttc"


def serve(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def shoot(url, path):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                    "--virtual-time-budget=25000", f"--screenshot={path}", url],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def caption(img, text):
    img = img.convert("RGB").resize((W, H))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, H - 78, W, H], fill=(15, 95, 115, 235))
    try:
        f = ImageFont.truetype(FONT, 30, index=1)
        s = ImageFont.truetype(FONT, 16)
    except OSError:
        f = s = ImageFont.load_default()
    d.text((32, H - 62), text, font=f, fill="white")
    d.text((W - 32, H - 26), "gavacharles.github.io/lge2026-ward-forecast", font=s, fill=(220, 235, 240), anchor="rs")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = serve(PROJECT / "docs")
    base = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
    stills = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (state, text) in enumerate(SCENES):
            p = Path(tmp) / f"s{i}.png"
            shoot(base + (f"#{state}" if state else ""), p)
            img = caption(Image.open(p), text)
            img.save(OUT / f"scene_{i:02d}.png")
            stills.append(np.asarray(img))
    httpd.shutdown()

    frames = []
    for i, a in enumerate(stills):
        frames += [a] * int(HOLD * FPS)
        b = stills[(i + 1) % len(stills)]
        for k in range(1, int(FADE * FPS) + 1):
            t = k / (FADE * FPS)
            frames.append((a * (1 - t) + b * t).astype(np.uint8))
    try:
        import imageio.v2 as imageio
        with imageio.get_writer(OUT / "dashboard.mp4", fps=FPS, codec="libx264", quality=8,
                                pixelformat="yuv420p", macro_block_size=16) as wr:
            for fr in frames:
                wr.append_data(fr)
        print("wrote", OUT / "dashboard.mp4")
    except ImportError:
        print("imageio not installed: skipping MP4")
    gif = [Image.fromarray(f).resize((W * 3 // 4, H * 3 // 4)) for f in frames[:: 3]]
    gif[0].save(OUT / "dashboard.gif", save_all=True, append_images=gif[1:], duration=int(3000 / FPS), loop=0,
                optimize=True)
    print("wrote", OUT / "dashboard.gif", len(frames) / FPS, "seconds")


if __name__ == "__main__":
    main()
