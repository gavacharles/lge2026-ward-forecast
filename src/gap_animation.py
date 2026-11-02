"""The gap: ANC and DA vote share in every election since 1994, drawn over time, ending on the 2026 forecast.

Local elections: 2000 all ballots and 2006 PR ballot (published totals); 2011-2021 ward ballot from the IEC results.
Writes content/animation/the_gap.mp4 and the_gap_final.png (the last frame, as a still).
"""
import json

import imageio.v2 as iio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd

from paths import INTERIM, OUTPUTS, PROJECT

OUT = PROJECT / "content" / "animation"
FPS, W, H = 24, 1280, 720
BG, INK, MUTED, GRID = "#0f1419", "#f2f5f4", "#a7b1b8", "#2a3440"
ANC, DA = "#2fbf6f", "#5b96ee"
NATIONAL = {1994: (62.65, 1.73), 1999: (66.35, 9.56), 2004: (69.69, 12.37), 2009: (65.90, 16.66), 2014: (62.15, 22.23),
            2019: (57.50, 20.77), 2024: (40.18, 21.81)}
LOCAL = {2000: (59.4, 22.1), 2006: (65.7, 16.3)}
CALLOUTS = [(2004, "ANC peak: 69.7%", 69.7, 2004, 76), (2024, "ANC loses its national\nmajority: 40.2%", 40.2, 2025, 56)]


def series():
    v = pd.read_parquet(INTERIM / "vd_votes.parquet")
    local = dict(LOCAL)
    for y in (2011, 2016, 2021):
        t = v[v.election == f"lge{y}_ward"].groupby("party").votes.sum()
        t = t / t.sum() * 100
        local[y] = (float(t.ANC), float(t.DA))
    return NATIONAL, local


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    nat, loc = series()
    s = json.load(open(OUTPUTS / "forecast_summary_2026.json"))
    fc = (s["national_share"]["ANC"], s["national_share"]["DA"])
    iv = s["national_interval_90"]
    years = sorted([*nat, *loc])
    a = np.array([{**nat, **loc}[y][0] for y in years] + [fc[0]])
    d = np.array([{**nat, **loc}[y][1] for y in years] + [fc[1]])
    xs = np.array(years + [2026.0])
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    wr = iio.get_writer(str(OUT / "the_gap.mp4"), fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=8)
    draw_n, end_n = 15 * FPS, 4 * FPS

    def frame(x, end=0.0):
        fig.clf()
        ax = fig.add_axes([0.06, 0.15, 0.82, 0.60], facecolor=BG)
        grid = np.linspace(1994, x, 300)
        ya, yd = np.interp(grid, xs, a), np.interp(grid, xs, d)
        ax.fill_between(grid, yd, ya, color="#ffffff", alpha=0.07, linewidth=0)
        ax.plot(grid, ya, color=ANC, linewidth=3, solid_capstyle="round")
        ax.plot(grid, yd, color=DA, linewidth=3, solid_capstyle="round")
        for yr, (va, vd) in {**nat, **loc}.items():
            if yr <= x:
                local = yr in loc
                for v, c in ((va, ANC), (vd, DA)):
                    ax.scatter([yr], [v], s=46, facecolor=BG if local else c, edgecolor=c, linewidth=1.8, zorder=3)
        # labels and counter step from one real election to the next
        at = int(np.searchsorted(xs, x + 1e-6, side="right") - 1)
        now_a, now_d = float(a[at]), float(d[at])
        lx = min(x + 0.5, 2026.6)
        ax.text(lx, float(np.interp(x, xs, a)) + (1.6 if now_a - now_d < 8 else 0), f"ANC {now_a:.0f}", color=INK, fontsize=15, fontweight="bold", va="center")
        ax.text(lx, float(np.interp(x, xs, d)) - (1.6 if now_a - now_d < 8 else 0), f"DA {now_d:.0f}", color=INK, fontsize=15, fontweight="bold", va="center")
        for yr, txt, y, tx, ty in CALLOUTS:
            al = ease((x - yr) / 2)
            if al > 0:
                ax.annotate(txt, xy=(yr, y), xytext=(tx, ty), color=INK, alpha=al, fontsize=12, ha="center", va="bottom",
                            arrowprops=dict(arrowstyle="-", color=MUTED, alpha=al, linewidth=0.8))
        if end > 0:
            for p, c, off in (("ANC", ANC, -0.14), ("DA", DA, 0.14)):
                ax.plot([2026 + off, 2026 + off], [iv[p]["p05"], iv[p]["p95"]], color=c, linewidth=7, alpha=0.45 * end,
                        solid_capstyle="round")
            ax.scatter([2026, 2026], fc, marker="D", s=90, color=[ANC, DA], edgecolor=BG, linewidth=1.5, zorder=4, alpha=end)
        ax.set_xlim(1993, 2030)
        ax.set_ylim(0, 80)
        ax.set_xticks([1994, 2000, 2006, 2011, 2016, 2021, 2026])
        ax.set_yticks([0, 20, 40, 60])
        ax.tick_params(length=0, colors=MUTED, labelsize=13)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for sp in ax.spines.values():
            sp.set_visible(False)
        fig.text(0.03, 0.925, "The gap", color=INK, fontsize=30, fontfamily="Georgia", va="center")
        fig.text(0.03, 0.855, "ANC and DA vote share (%). Solid dots: national. Open dots: local.",
                 color=MUTED, fontsize=14, va="center")
        label = "Wednesday's forecast" if x >= 2026 else f"{xs[at]:.0f} election"
        fig.text(0.97, 0.945, label, color=MUTED, fontsize=15, va="center", ha="right")
        fig.text(0.97, 0.875, f"ANC lead: {now_a - now_d:.0f} points", color=INK, fontsize=28, fontweight="bold", va="center", ha="right")
        if end > 0:
            ax.text(2026, iv["DA"]["p05"] - 3, "Bars: 90% ranges", color=INK, alpha=end, fontsize=11.5, ha="center", va="top")
        fig.text(0.03, 0.045, "Sources: IEC; 2026 is a forecast from a statistical model, not a poll or result. Local elections: 2000 all ballots, 2006 PR,\n"
                 "2011-2021 ward ballot. 2026: ward ballot. DA in 1994 and 1999 = Democratic Party.", color=MUTED, fontsize=10.5, va="center")
        fig.text(0.97, 0.045, "Credit: Gava Charles", color=INK, fontsize=14, fontweight="bold", va="center", ha="right")
        fig.canvas.draw()
        return np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()

    for k in range(draw_n):
        wr.append_data(frame(1994 + 32 * (k + 1) / draw_n * 0.9999))
    last = None
    for k in range(end_n):
        last = frame(2026.0, ease(k / (FPS * 1.2)))
        wr.append_data(last)
    wr.close()
    iio.imwrite(OUT / "the_gap_final.png", last)
    print("the_gap.mp4", (draw_n + end_n) / FPS, "seconds; gap", round(fc[0] - fc[1], 1))


if __name__ == "__main__":
    main()
