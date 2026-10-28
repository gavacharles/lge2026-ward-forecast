"""How the forecast works: a 3D film of South Africa's 4,485 wards as extruded prisms, in five acts.

  1  The new wards        wards rise from the map; height = expected votes
  2  History, rebuilt     2021 winners re-added inside the 2026 wards sweep in from the west
  3  The 2026 forecast    model, polls, by-elections and candidate lists turn wards to their 2026 favourite
  4  KwaZulu-Natal        poll-led reading, then the published by-election-led reading
  5  2,000 simulations    each frame is one simulated election (toss-ups flicker), then heights settle to
                          the favourite's chance

Dark matte style with a header band (title, subtitle, live counter) and a footer band (sources, credit),
matching the Kampala drainage films. Needs pyvista (run with a Python that has it, e.g.
~/uganda-rainfall-climate/.venv/bin/python src/explainer3d.py).
Outputs content/animation/how_it_works.mp4, how_it_works.gif and how_it_works_acts.png.
"""
import json
import textwrap

import geopandas as gpd
import imageio.v2 as iio
import matplotlib
import numpy as np
import pandas as pd
import pyvista as pv
from PIL import Image, ImageDraw, ImageFont

from paths import OUTPUTS, PROJECT, RAW

pv.OFF_SCREEN = True
OUT = PROJECT / "content" / "animation"
FPS = 15
SRC = ("Ward boundaries: Municipal Demarcation Board 2026 · results, by-elections and certified candidate lists: "
       "IEC · polls: Ipsos, SRF, SABI, MarkData · model: LGE 2026 Ward Forecast")
URL = "gavacharles.github.io/lge2026-ward-forecast"
BG_TOP, BG_BOT = "#1a2233", "#05070b"
COL = {"ANC": "#22a05a", "DA": "#3b7ddd", "MK": "#8a5cc2", "EFF": "#d6334a", "IFP": "#e0a21b", "PA": "#c45a9b",
       "FFP": "#f07f2a", "ASA": "#2fb3a6", "OTH": "#8a8f98"}
SLATE = "#59606b"
TOSS = "#ff3b30"
PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]


def rgb(hex_):
    return np.array([int(hex_[i:i + 2], 16) for i in (1, 3, 5)], float)


def font(sz, bold=False):
    d = matplotlib.get_data_path() + "/fonts/ttf/"
    return ImageFont.truetype(d + ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), sz)


def compose(img, title, sub, count, count_color):
    """Render between a header band (title, subtitle, live counter) and a footer band (sources, credit)."""
    im = Image.fromarray(img)
    W, H = im.size
    head, foot = 112, 46
    can = Image.new("RGB", (W, H + head + foot), "#0f1419")
    can.paste(im, (0, head))
    d = ImageDraw.Draw(can)
    d.text((18, 10), title, font=font(26, True), fill="white")
    d.text((18, 46), sub, font=font(15), fill="#b9c2c9")
    d.text((18, 72), count, font=font(20, True), fill=count_color)
    cr = "Credit: Gava Charles"
    fc = font(17, True)
    cw = d.textlength(cr, font=fc)
    d.text((W - cw - 14, H + head + 12), cr, font=fc, fill="white")
    for i, ln in enumerate(textwrap.wrap(SRC, 150)[:2]):
        d.text((18, H + head + 6 + i * 16), ln, font=font(12), fill="#9aa4ab")
    return can


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def prisms(geoms):
    """One mesh of extruded wards. Returns points (x, y), per-point ward index and top flag, faces, and the
    ward index of every cell (cells: triangulated tops, then side walls)."""
    pts, ward, top, faces, cell_ward = [], [], [], [], []
    n0 = 0
    for w, g in enumerate(geoms):
        for poly in getattr(g, "geoms", [g]):
            ring = np.asarray(poly.exterior.coords)[:-1, :2]
            n = len(ring)
            if n < 3:
                continue
            tri = pv.PolyData(np.c_[ring, np.zeros(n)], faces=np.r_[n, np.arange(n)]).triangulate()
            if tri.n_points != n:
                continue
            t = tri.faces.reshape(-1, 4)[:, 1:]
            pts += [ring, ring]
            ward += [np.full(2 * n, w)]
            top += [np.zeros(n), np.ones(n)]
            for a, b, c in t + n0 + n:  # top face
                faces += [3, a, b, c]
            cell_ward += [w] * len(t)
            for i in range(n):  # side walls
                j = (i + 1) % n
                faces += [4, n0 + i, n0 + j, n0 + n + j, n0 + n + i]
            cell_ward += [w] * n
            n0 += 2 * n
    return (np.vstack(pts), np.concatenate(ward), np.concatenate(top).astype(bool), np.array(faces),
            np.array(cell_ward))


def main():
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    alt = pd.read_csv(OUTPUTS / "ward_forecast_2026_poll_scenario.csv", dtype={"ward": str}).set_index("ward")
    summary = json.load(open(OUTPUTS / "forecast_summary_2026.json"))
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson").set_index("WardID").reindex(w.index)
    g = g.to_crs("ESRI:102022")
    g["geometry"] = g.geometry.simplify(800)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    w, alt = w.loc[g.index], alt.loc[g.index]
    P, pw, ptop, faces, cw = prisms(g.geometry.values)
    xy = P / 1000.0  # km
    xy -= xy.mean(0)
    mesh = pv.PolyData(np.c_[xy, np.zeros(len(xy))], faces)
    nw = len(w)
    kzn = (w.province == "KwaZulu-Natal").values
    cent = np.array([xy[pw == i].mean(0) for i in range(nw)])

    def colour_of(fav):
        return np.array([rgb(COL.get(f, COL["OTH"])) for f in fav])

    c_slate = np.tile(rgb(SLATE), (nw, 1))
    c_2021 = colour_of(w.winner_2021_est)
    c_2026 = colour_of(w.favourite)
    c_poll = colour_of(alt.favourite)
    votes = w.expected_votes.values
    h_votes = 4 + 70 * np.sqrt(votes / votes.max())
    h_prob = 4 + 90 * ((w.win_prob.values - 0.3) / 0.7).clip(0, 1) ** 1.5
    pcols = [c for c in w.columns if c.startswith("p_")]
    probs = w[pcols].values
    probs = probs / probs.sum(1, keepdims=True)
    labels = [c[2:] for c in pcols]
    lab_rgb = np.array([rgb(COL.get(lb, COL["OTH"])) for lb in labels])
    local_rgb = rgb(COL["OTH"])

    p = pv.Plotter(off_screen=True, window_size=(1280, 720))
    p.set_background(BG_BOT, top=BG_TOP)
    p.remove_all_lights()
    p.add_light(pv.Light(position=(1500, -1800, 2500), focal_point=(0, 0, 0), intensity=1.1, light_type="scene light"))
    p.add_light(pv.Light(position=(-2000, 1500, 2000), focal_point=(0, 0, 0), intensity=0.35, light_type="scene light"))
    mesh.cell_data["rgb"] = np.zeros((mesh.n_cells, 3), np.uint8)
    actor = p.add_mesh(mesh, scalars="rgb", rgb=True, ambient=0.28, diffuse=0.85, specular=0.12, show_edges=False)
    mesh = actor.mapper.dataset  # add_mesh may render a copy: update the one on screen
    span = float(np.ptp(xy[:, 0]))

    def cam(az, el, dist, focus=(0.0, 0.0)):
        a, e = np.deg2rad(az), np.deg2rad(el)
        fx, fy = focus
        p.camera.focal_point = (fx, fy, 0)
        p.camera.position = (fx + dist * np.cos(e) * np.cos(a), fy + dist * np.cos(e) * np.sin(a), dist * np.sin(e))
        p.camera.up = (0, 0, 1)
        p.camera.view_angle = 30
        p.camera_set = True  # stop the first render from resetting the view

    def set_state(h, c):
        mesh.points[:, 2] = np.where(ptop, h[pw], 0.0)
        mesh.cell_data["rgb"][:] = np.clip(c[cw], 0, 255).astype(np.uint8)
        mesh.Modified()

    mp4 = iio.get_writer(str(OUT / "how_it_works.mp4"), fps=FPS, quality=8, macro_block_size=8)
    gif, stills = [], {}
    frame_no = {"n": 0}

    def shoot(title, sub, count, colour, still=None):
        p.render()  # screenshot alone does not redraw changed data
        can = compose(p.screenshot(return_img=True), title, sub, count, colour)
        mp4.append_data(np.asarray(can))
        if frame_no["n"] % 4 == 0:
            gif.append(can.resize((640, int(can.height * 640 / can.width)), Image.LANCZOS)
                       .convert("P", palette=Image.ADAPTIVE))
        if still:
            stills[still] = can
        frame_no["n"] += 1

    def lerp(a, b, t):
        return a + (b - a) * t

    tally = lambda fav: "  ·  ".join(f"{p_} {int((fav == p_).sum()):,}" for p_ in ["ANC", "DA", "IFP", "MK"])
    kfocus = tuple(cent[kzn].mean(0))

    # Act 1: the wards rise --------------------------------------------------------------------------------
    T, S = "4,485 new wards", "Municipal Demarcation Board 2026 boundaries. Height = expected votes in each ward."
    order = np.argsort(np.argsort(cent[:, 0]))  # west to east
    for k in range(70):
        t = k / 69
        grow = np.clip(t * 1.6 - order / nw * 0.6, 0, 1)
        grow = grow * grow * (3 - 2 * grow)
        set_state(h_votes * grow, c_slate)
        cam(-100 + 15 * t, 55 - 15 * t, span * (1.6 - 0.25 * t))
        shoot(T, S, f"{int((grow > 0.05).sum()):,} wards  ·  213 councils  ·  8 metros", "#cfd8dc",
              still="1" if k == 69 else None)

    # Act 2: history, rebuilt ------------------------------------------------------------------------------
    T = "History, rebuilt"
    S = "2016, 2021 and 2024 results re-added voting district by voting district inside the new wards."
    for k in range(70):
        t = k / 69
        f = np.clip(t * 1.5 - order / nw * 0.5, 0, 1)[:, None]
        set_state(h_votes, lerp(c_slate, c_2021, f))
        cam(-85 + 5 * t, 42, span * 1.5)
        shown = w.winner_2021_est[(f[:, 0] > 0.5)]
        shoot(T, S, "2021 winners: " + tally(shown.values), "#a5d6a7", still="2" if k == 69 else None)

    # Act 3: the 2026 forecast -----------------------------------------------------------------------------
    T = "The 2026 forecast"
    S = "A per-party model, 29 polls, 218 by-elections and the IEC candidate lists move each ward to its 2026 favourite."
    flips = (w.favourite != w.winner_2021_est).values
    rnd = np.random.default_rng(3).random(nw)
    for k in range(80):
        t = k / 79
        f = np.clip(t * 1.4 - rnd * 0.4, 0, 1)
        bump = np.where(flips, 18 * np.sin(np.pi * f), 0)
        set_state(h_votes + bump, lerp(c_2021, c_2026, f[:, None]))
        cam(-80 + 10 * t, 42 + 6 * t, span * 1.5)
        shoot(T, S, f"wards changing hands since 2021: {int((flips & (f > 0.5)).sum()):,}", "#ffe082",
              still="3" if k == 79 else None)

    # Act 4: KwaZulu-Natal ---------------------------------------------------------------------------------
    T = "KwaZulu-Natal: two readings"
    S = "National polls say MK is near its 2024 level; 35 by-elections since 2024 say it has slipped. We publish both."
    kz = lambda fav: f"IFP {int((fav[kzn] == 'IFP').sum())}  ·  MK {int((fav[kzn] == 'MK').sum())}"
    c_base = c_2026.copy()
    c_base[kzn] = c_poll[kzn]
    for k in range(40):  # fly in, switch KZN to the poll-led reading
        t = ease(k / 39)
        c = c_2026.copy()
        c[kzn] = lerp(c_2026[kzn], c_poll[kzn], t)
        set_state(h_votes, c)
        cam(lerp(-70, -70, t), lerp(48, 38, t), lerp(span * 1.5, span * 0.42, t),
            focus=(lerp(0, kfocus[0], t), lerp(0, kfocus[1], t)))
        shoot(T, S, "Poll-led:  " + kz(alt.favourite.values), "#ce93d8")
    for k in range(25):
        cam(-70 + 6 * k / 24, 38, span * 0.42, focus=kfocus)
        shoot(T, S, "Poll-led:  " + kz(alt.favourite.values), "#ce93d8", still="4a" if k == 24 else None)
    for k in range(50):
        t = ease(k / 49)
        c = c_base.copy()
        c[kzn] = lerp(c_poll[kzn], c_2026[kzn], t)
        set_state(h_votes, c)
        cam(-64 + 10 * k / 49, 38, span * 0.42, focus=kfocus)
        label = "By-election-led (published):  " if t > 0.5 else "Poll-led:  "
        shoot(T, S, label + kz((w.favourite if t > 0.5 else alt.favourite).values),
              "#ffd54f" if t > 0.5 else "#ce93d8", still="4" if k == 49 else None)
    for k in range(15):
        cam(-54, 38, span * 0.42, focus=kfocus)
        shoot(T, S, "By-election-led (published):  " + kz(w.favourite.values), "#ffd54f")

    # Act 5: 2,000 simulations -----------------------------------------------------------------------------
    T = "2,000 simulations"
    S = "Each frame is one simulated election. Steady wards are safe; flickering wards are toss-ups."
    rng = np.random.default_rng(11)
    cum = probs.cumsum(1)
    toss = (w.rating == "Toss-up").values
    for k in range(75):
        t = ease(k / 74)
        draw = (rng.random(nw)[:, None] > cum).sum(1).clip(max=len(labels) - 1)
        c = lab_rgb[draw]
        c[np.array(labels)[draw] == "LOCAL_TOP"] = local_rgb
        cam(lerp(-54, -90, t), lerp(38, 58, t), lerp(span * 0.42, span * 1.6, t),
            focus=(lerp(kfocus[0], 0, t), lerp(kfocus[1], 0, t)))
        set_state(lerp(h_votes, h_prob, t), c)
        sim = int(1 + 1999 * k / 74)
        shoot(T, S, f"simulation {sim:,} of 2,000", "#80deea", still="5" if k == 40 else None)

    # Final: favourites, height = chance; toss-ups glow ---------------------------------------------------
    T = "The forecast"
    S = "Colour = favourite. Height = its chance of winning. Red = toss-up (no party above 60%)."
    for k in range(70):
        t = ease(min(k / 30, 1))
        pulse = 0.5 + 0.5 * np.sin(k / 3)
        c = c_2026.copy()
        c[toss] = lerp(c_2026[toss], rgb(TOSS), t * (0.55 + 0.45 * pulse))
        set_state(h_prob, c)
        cam(-90 + 14 * k / 69, 58 - 6 * k / 69, span * (1.6 - 0.08 * k / 69))
        cnt = tally(w.favourite.values) + f"  ·  toss-ups {int(toss.sum()):,}"
        shoot(T, S, cnt if k < 45 else f"Find your ward:  {URL}", "#ffffff" if k < 45 else "#7fe3ff",
              still="6" if k == 44 else None)

    mp4.close()
    p.close()
    gif[0].save(OUT / "how_it_works.gif", save_all=True, append_images=gif[1:], duration=int(4000 / FPS), loop=0)
    ks = ["1", "2", "3", "4a", "4", "5", "6"]
    W_, H_ = stills[ks[0]].size
    sheet = Image.new("RGB", (W_, H_ * len(ks)), "#0f1419")
    for i, k in enumerate(ks):
        sheet.paste(stills[k], (0, i * H_))
    sheet.save(OUT / "how_it_works_acts.png")
    print("frames", frame_no["n"], "seconds", round(frame_no["n"] / FPS, 1))


if __name__ == "__main__":
    main()
