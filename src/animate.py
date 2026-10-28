"""Animated tour of the live site: headless Chrome screenshots of link states, captioned and
cross-faded into content/animation/dashboard.mp4 (H.264, for X) and dashboard.gif.

Needs Google Chrome, Selenium, Pillow, numpy and imageio + imageio-ffmpeg (MP4 is skipped without them).
Usage: python src/animate.py
"""
import functools
import json
import http.server
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from selenium.webdriver.support.ui import WebDriverWait

from paths import OUTPUTS, PROJECT

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = PROJECT / "content" / "animation"
W, H = 1280, 720
FPS, HOLD, FADE = 24, 2.6, 0.5
NAMES = {"FFP": "FF+", "ASA": "ActionSA"}


def scenes():
    """(link state, caption) pairs, with numbers read from the current forecast outputs."""
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str})
    m = pd.read_csv(OUTPUTS / "municipality_forecast_2026.csv").set_index("muni")
    s = json.load(open(OUTPUTS / "forecast_summary_2026.json"))
    kzn = s["scenarios"]
    toss = int((w.rating == "Toss-up").sum())
    # closest Johannesburg ward: lowest favourite chance
    j = w[w.muni == "JHB"].sort_values("win_prob").iloc[0]
    top = sorted(((j[f"share_{p}"], NAMES.get(p, p)) for p in ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]),
                 reverse=True)[:3]
    race = (f"{top[0][1]}, {top[1][1]} and {top[2][1]} within {top[0][0] - top[2][0]:.0f} points"
            if top[0][0] - top[2][0] < 5 else f"{top[0][1]} {top[0][0]:.0f}%, {top[1][1]} {top[1][0]:.0f}%")
    metros = ["BUF", "NMA", "MAN", "EKU", "JHB", "TSH", "ETH", "CPT"]
    hung = int((m.loc[metros, "p_hung"] > 0.5).sum())
    eth = m.loc["ETH"]
    cpt = m.loc["CPT"]
    return [
        ("", f"{len(w):,} wards. One forecast for 4 November."),
        ("section=map-section", "Each ward coloured by its favourite. Paler means less certain."),
        ("view=rating&section=map-section", f"{toss:,} wards are toss-ups: no party above a 60% chance."),
        ("view=flip&section=map-section", f"{int(w.flip.sum()):,} wards are forecast to change hands since 2021."),
        ("view=share&party=MK&prov=KwaZulu-Natal&section=map-section",
         f"KZN: IFP favoured in {kzn['byelection']['kzn']['favourites'].get('IFP', 0)} wards. "
         f"On polls alone, MK in {kzn['poll']['kzn']['favourites'].get('MK', 0)}."),
        ("section=kzn", "Polls and by-elections disagree in KZN. We publish both."),
        ("view=fav&muni=ETH&section=map-section",
         f"eThekwini: {NAMES.get(eth.largest_party, eth.largest_party)} is favoured to be the largest party "
         f"({eth.p_largest:.0%})."),
        (f"muni=JHB&ward={j.ward}&section=map-section", f"Johannesburg ward {int(j.ward_no)}: {race}."),
        ("muni=CPT&section=map-section", f"Cape Town: {cpt.majority_party} keeps a majority in {cpt.p_majority:.0%} of runs."
         if cpt.p_majority > 0.5 else "Cape Town: no party is likely to have a majority."),
        ("section=metros", f"Seat by seat: {hung} of 8 metros look hung."),
        ("section=coalitions", "Who can govern with whom: the coalition maths."),
        ("section=backtest", "Tested on 2016 and 2021: it beat simple rules both times."),
    ]
FONT = "/System/Library/Fonts/Avenir Next.ttc"


def serve(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def browser():
    from selenium import webdriver
    opts = webdriver.ChromeOptions()
    opts.binary_location = CHROME
    for a in ("--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}"):
        opts.add_argument(a)
    drv = webdriver.Chrome(options=opts)
    drv.set_window_size(W, H)
    return drv


def shoot(drv, url, path):
    # Headless --screenshot leaves scrolled-to sections unpainted, so drive a real page instead.
    drv.get("about:blank")
    drv.get(url)
    WebDriverWait(drv, 30).until(lambda d: d.execute_script(
        "return document.querySelectorAll('#bt h3').length > 0"))
    time.sleep(2.5)  # map tiles and fly-to animations
    drv.execute_script("window.dispatchEvent(new HashChangeEvent('hashchange'))")
    time.sleep(1.5)
    drv.save_screenshot(str(path))


def caption(img, text):
    img = img.convert("RGB").resize((W, H))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, H - 78, W, H], fill=(15, 95, 115, 235))
    try:
        size = 30
        f = ImageFont.truetype(FONT, size, index=1)
        while d.textlength(text, font=f) > W - 420 and size > 20:  # keep clear of the URL
            size -= 1
            f = ImageFont.truetype(FONT, size, index=1)
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
    drv = browser()
    with tempfile.TemporaryDirectory() as tmp:
        for i, (state, text) in enumerate(scenes()):
            p = Path(tmp) / f"s{i}.png"
            shoot(drv, base + (f"#{state}" if state else ""), p)
            img = caption(Image.open(p), text)
            img.save(OUT / f"scene_{i:02d}.png")
            stills.append(np.asarray(img))
    drv.quit()
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
