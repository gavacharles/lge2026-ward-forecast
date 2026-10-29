"""Then and now: past elections side by side with the 2026 forecast, as 3D ward prisms.

Left: ward winners in the 2011, 2016 and 2021 local elections (ward ballot) and the 2024 national election,
re-added voting district by voting district inside the 2026 wards (estimates on the new boundaries).
Right: the 2026 forecast favourite. Height = the winner's vote share in both panels. One camera, linked.
Same dark style, legend band and credit as explainer3d.py. Run with a Python that has pyvista:
  ~/uganda-rainfall-climate/.venv/bin/python src/compare3d.py
Outputs content/animation/then_and_now.mp4, then_and_now.gif and then_and_now_stills.png.
"""
import textwrap

import geopandas as gpd
import imageio.v2 as iio
import numpy as np
import pandas as pd
import pyvista as pv
from PIL import Image, ImageDraw

import model as M
from explainer3d import BG_BOT, BG_TOP, COL, LEGEND, OUT, URL, ease, font, prisms, rgb
from paths import INTERIM, OUTPUTS, RAW

pv.OFF_SCREEN = True
FPS = 15
W, H = 1920, 800
SRC = ("Ward boundaries: Municipal Demarcation Board 2026 · results: IEC voting-district results, re-added inside "
       "the 2026 wards (estimates on new boundaries) · 2026: LGE 2026 Ward Forecast")
PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]
PAST = [("lge2011_ward", "2011", "local elections"), ("lge2016_ward", "2016", "local elections"),
        ("lge2021_ward", "2021", "local elections"), ("npe2024", "2024", "national election")]
TALLY = ["ANC", "DA", "IFP", "MK", "EFF"]


def past_winners(index):
    """Winner and winning share per 2026 ward for each past election."""
    votes, other = M.load()
    map26 = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str)
    out = {}
    for e, _, _ in PAST:
        S, _, _ = M.ward_table(votes, e, map26, PARTIES)
        local = M.top_other(other, e, map26)
        win = M.winners(S, local)
        T = S.drop(columns="OTH").assign(LOCAL=S.OTH * local.local_frac.reindex(S.index).fillna(0))
        code = win.winner.where(win.winner.isin(PARTIES), "OTH")
        out[e] = pd.DataFrame({"party": code, "share": T.max(axis=1)}).reindex(index)
    return out


FOUNDED = {"EFF": 2013, "MK": 2023}


def tally(party, year=2026):
    return "   ".join(f"{p} " + (f"{int((party == p).sum()):,}" if year > FOUNDED.get(p, 0) else "–") for p in TALLY)


def compose(img, left, right, lcount, rcount):
    """Header (title, two panel labels with counters), legend band, footer (sources, credit)."""
    im = Image.fromarray(img)
    head, leg, foot = 170, 52, 58
    can = Image.new("RGB", (W, H + head + leg + foot), "#0f1419")
    can.paste(im, (0, head))
    d = ImageDraw.Draw(can)
    d.text((26, 14), "South Africa's 4,485 wards: then and now", font=font(34, True), fill="white")
    d.text((26, 60), "Colour = winning party. Height = winner's vote share. Past results re-added inside the 2026 "
                     "boundaries. Big rural wards look large but hold few voters.", font=font(20), fill="#c5cdd3")
    for x, (label, sub), count, col in [(26, left, lcount, "#e6ebef"), (W // 2 + 26, right, rcount, "#ffe082")]:
        d.text((x, 98), label, font=font(28, True), fill=col)
        lw = d.textlength(label, font=font(28, True))
        d.text((x + lw + 14, 106), sub, font=font(18), fill="#9aa4ab")
        d.text((x, 134), count, font=font(22, True), fill="#e6ebef")
    d.line([(W // 2, head + 20), (W // 2, head + H - 20)], fill="#2a3440", width=2)
    fl = font(20, True)
    widths = [28 + 10 + d.textlength(lb, font=fl) + 30 for _, lb in LEGEND]
    x = (W - sum(widths) + 30) / 2
    y = H + head + 13
    for (code, lb), wd in zip(LEGEND, widths):
        d.rounded_rectangle([x, y + 1, x + 28, y + 27], radius=4, fill=COL[code])
        d.text((x + 38, y + 2), lb, font=fl, fill="#e6ebef")
        x += wd
    yf = H + head + leg
    d.line([(26, yf), (W - 26, yf)], fill="#26303a", width=1)
    cr = "Credit: Gava Charles"
    fcr = font(22, True)
    d.text((W - d.textlength(cr, font=fcr) - 22, yf + 16), cr, font=fcr, fill="white")
    for i, ln in enumerate(textwrap.wrap(SRC, 150)[:2]):
        d.text((26, yf + 8 + i * 21), ln, font=font(15), fill="#a7b1b8")
    return can


def main():
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson").set_index("WardID").reindex(w.index).to_crs("ESRI:102022")
    g["geometry"] = g.geometry.simplify(800)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    w = w.loc[g.index]
    past = past_winners(w.index)
    P, pw, ptop, faces, cw = prisms(g.geometry.values)
    xy = P / 1000.0
    xy -= xy.mean(0)

    fav = w.favourite.where(w.favourite.isin(PARTIES), "OTH")
    share26 = w[[f"share_{p}" for p in PARTIES + ["OTH"]]].max(axis=1).values / 100

    def colours(party):
        return np.array([rgb(COL.get(p, COL["OTH"])) for p in party])

    def heights(share):
        return 3 + 85 * ((np.nan_to_num(share, nan=0.3) - 0.2) / 0.8).clip(0, 1)

    states = [(colours(past[e].party.values), heights(past[e].share.values)) for e, _, _ in PAST]
    right = (colours(fav.values), heights(share26))

    p = pv.Plotter(off_screen=True, window_size=(W, H), shape=(1, 2), border=False)
    meshes = []
    for col in (0, 1):
        p.subplot(0, col)
        p.set_background(BG_BOT, top=BG_TOP)
        p.remove_all_lights()
        p.add_light(pv.Light(position=(1500, -1800, 2500), focal_point=(0, 0, 0), intensity=1.1,
                             light_type="scene light"))
        p.add_light(pv.Light(position=(-2000, 1500, 2000), focal_point=(0, 0, 0), intensity=0.35,
                             light_type="scene light"))
        m = pv.PolyData(np.c_[xy, np.zeros(len(xy))], faces)
        m.cell_data["rgb"] = np.zeros((m.n_cells, 3), np.uint8)
        actor = p.add_mesh(m, scalars="rgb", rgb=True, ambient=0.28, diffuse=0.85, specular=0.12)
        meshes.append(actor.mapper.dataset)
    p.link_views()
    span = float(np.ptp(xy[:, 0]))

    def cam(az, el, dist):
        a, e = np.deg2rad(az), np.deg2rad(el)
        p.subplot(0, 0)
        fx, fy = -70, -40
        p.camera.focal_point = (fx, fy, 0)
        p.camera.position = (fx + dist * np.cos(e) * np.cos(a), fy + dist * np.cos(e) * np.sin(a), dist * np.sin(e))
        p.camera.up = (0, 0, 1)
        p.camera.view_angle = 30
        p.camera_set = True

    def set_state(mesh, c, h):
        mesh.points[:, 2] = np.where(ptop, h[pw], 0.0)
        mesh.cell_data["rgb"][:] = np.clip(c[cw], 0, 255).astype(np.uint8)
        mesh.Modified()

    mp4 = iio.get_writer(str(OUT / "then_and_now.mp4"), fps=FPS, quality=7, macro_block_size=8)
    gif, stills, n = [], [], {"k": 0}
    rlabel = ("2026", "forecast favourite")
    rcount = tally(fav.values)

    def shoot(left, lcount, still=False):
        p.render()
        can = compose(p.screenshot(return_img=True), left, rlabel, lcount, rcount)
        mp4.append_data(np.asarray(can))
        if n["k"] % 4 == 0:
            gif.append(can.resize((800, int(can.height * 800 / can.width)), Image.LANCZOS)
                       .convert("P", palette=Image.ADAPTIVE))
        if still:
            stills.append(can)
        n["k"] += 1

    total = 0
    nframes = 40 + len(PAST) * 52 + (len(PAST) - 1) * 22 + 30
    orbit = lambda: cam(-100 + 30 * total / nframes, 52 - 10 * total / nframes, span * (1.95 - 0.12 * total / nframes))
    c0, h0 = states[0]
    for k in range(40):  # both maps rise
        t = ease(k / 39)
        set_state(meshes[0], c0, h0 * t)
        set_state(meshes[1], right[0], right[1] * t)
        orbit()
        shoot((PAST[0][1], PAST[0][2]), tally(past[PAST[0][0]].party.values, int(PAST[0][1])))
        total += 1
    for i, (e, yr, kind) in enumerate(PAST):
        c, h = states[i]
        for k in range(52):  # hold
            set_state(meshes[0], c, h)
            set_state(meshes[1], *right)
            orbit()
            shoot((yr, kind), tally(past[e].party.values, int(yr)), still=(k == 40))
            total += 1
        if i + 1 < len(PAST):  # morph to the next election
            c1, h1 = states[i + 1]
            e1, yr1, kind1 = PAST[i + 1]
            for k in range(22):
                t = ease(k / 21)
                set_state(meshes[0], c + (c1 - c) * t, h + (h1 - h) * t)
                orbit()
                lab, cnt = (((yr1, kind1), tally(past[e1].party.values, int(yr1))) if t > 0.5
                            else ((yr, kind), tally(past[e].party.values, int(yr))))
                shoot(lab, cnt)
                total += 1
    for k in range(30):  # end card
        orbit()
        shoot((PAST[-1][1], PAST[-1][2]), f"Find your ward:  {URL}")
        total += 1
    mp4.close()
    p.close()
    gif[0].save(OUT / "then_and_now.gif", save_all=True, append_images=gif[1:], duration=int(4000 / FPS), loop=0)
    sheet = Image.new("RGB", (stills[0].width, stills[0].height * len(stills)), "#0f1419")
    for i, s in enumerate(stills):
        sheet.paste(s, (0, i * s.height))
    sheet.save(OUT / "then_and_now_stills.png")
    print("frames", n["k"], "seconds", round(n["k"] / FPS, 1))


if __name__ == "__main__":
    main()
