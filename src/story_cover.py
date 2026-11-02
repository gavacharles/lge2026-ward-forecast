"""Substack cover for the story: the 2026 wards as 3D prisms, with ANC-favoured wards lit. 1456 x 1048.

Run with a Python that has pyvista: ~/uganda-rainfall-climate/.venv/bin/python src/story_cover.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import pyvista as pv
from PIL import Image, ImageDraw, ImageFont

from explainer3d import COL, font, prisms, rgb
from paths import OUTPUTS, PROJECT, RAW

pv.OFF_SCREEN = True
GEORGIA = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
W, H = 1456, 1048


def render():
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson").set_index("WardID").reindex(w.index).to_crs("ESRI:102022")
    g["geometry"] = g.geometry.simplify(800)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    w = w.loc[g.index]
    P, pw, ptop, faces, cw = prisms(g.geometry.values)
    xy = P / 1000.0
    xy -= xy.mean(0)
    anc = (w.favourite == "ANC").values
    h = np.where(anc, 12 + 75 * w.win_prob.values, 5.0)
    c = np.where(anc[:, None], rgb(COL["ANC"])[None, :], rgb("#39414b")[None, :])
    mesh = pv.PolyData(np.c_[xy, np.where(ptop, h[pw], 0.0)], faces)
    mesh.cell_data["rgb"] = c[cw].astype(np.uint8)
    p = pv.Plotter(off_screen=True, window_size=(W, 710))
    p.set_background("#0f1419")
    p.remove_all_lights()
    p.add_light(pv.Light(position=(1500, -1800, 2500), focal_point=(0, 0, 0), intensity=1.1, light_type="scene light"))
    p.add_light(pv.Light(position=(-2000, 1500, 2000), focal_point=(0, 0, 0), intensity=0.35, light_type="scene light"))
    p.add_mesh(mesh, scalars="rgb", rgb=True, ambient=0.28, diffuse=0.85, specular=0.12)
    span = float(np.ptp(xy[:, 0]))
    az, el, dist = np.deg2rad(-88), np.deg2rad(50), span * 1.36
    p.camera.focal_point = (-195, -55, 0)
    p.camera.position = (-195 + dist * np.cos(el) * np.cos(az), -55 + dist * np.cos(el) * np.sin(az), dist * np.sin(el))
    p.camera.up = (0, 0, 1)
    p.camera.view_angle = 30
    p.camera_set = True
    p.render()
    img = p.screenshot(return_img=True)
    p.close()
    return Image.fromarray(img), int(anc.sum()), len(w)


def main():
    img, n, total = render()
    can = Image.new("RGB", (W, H), "#0f1419")
    can.paste(img, (0, 268))
    d = ImageDraw.Draw(can)
    head = ImageFont.truetype(GEORGIA, 76)
    d.text((64, 56), "The ANC could win half", font=head, fill="white")
    d.text((64, 142), "the wards on 29% of the vote", font=head, fill="white")
    d.text((66, 248), "South Africa's local elections, 4 November 2026: a ward-by-ward forecast", font=font(25), fill="#c5cdd3")
    y = H - 62
    d.rounded_rectangle([64, y, 94, y + 28], radius=5, fill=COL["ANC"])
    d.text((106, y + 1), f"ANC favoured: {n:,} of {total:,} wards", font=font(23, True), fill="white")
    cr = "Credit: Gava Charles"
    d.text((W - d.textlength(cr, font=font(23, True)) - 54, y + 1), cr, font=font(23, True), fill="white")
    can.save(PROJECT / "content" / "story" / "cover_substack_1456x1048.png")
    print("cover", can.size)


if __name__ == "__main__":
    main()
