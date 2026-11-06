"""Short X videos (1280x720, H.264) and final-frame stills about how the forecast did, in content/posts/x_visuals/.
Run after score.py 2026. Same dark style as x1_the_gap.mp4.

  x8_receipts       what the final forecast said vs what happened
  x9_simple_rule    in close wards, a simple rule beat the model
  x10_upsets        97 wards won by someone the model gave no chance
  x11_party_tilt    too generous to the DA, too stingy to the ANC
  x12_ward_totals   vote shares in range; the ANC's ward total broke out
  x13_calibration   were the chances honest?
  x14_actionsa      ActionSA: the right number of wards in the wrong places, and double the seats in two metros
"""
import imageio.v2 as iio
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import score_charts as SC
from paths import PROJECT

OUT = PROJECT / "content" / "posts" / "x_visuals"
FPS, W, H = 24, 1280, 720
BG, INK, MUTED, GRID, PANEL = "#0f1419", "#f2f5f4", "#a7b1b8", "#2a3440", "#1a222b"
ACCENT = "#ff8a50"   # "my model" / "missed"
GOOD, BAD, MIXED = "#7fd4a0", "#ff8a8a", "#f5c66b"   # verdicts always carry a symbol and a word too
HANDLE = "LGE 2026 Ward Forecast · gavacharles.github.io/lge2026-ward-forecast"


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def seg(t, a, b):
    """Progress of t through the window [a, b], eased."""
    return ease((t - a) / (b - a))


def head(fig, title, sub, a=1.0):
    fig.text(0.05, 0.93, title, fontsize=27, fontfamily="Georgia", color=INK, va="top", alpha=a)
    if sub:
        fig.text(0.05, 0.85, sub, fontsize=14.5, color=MUTED, va="top", alpha=a, linespacing=1.4)
    fig.text(0.05, 0.035, HANDLE, fontsize=11, color=MUTED)


def axes(fig, rect, grid="x"):
    ax = fig.add_axes(rect, facecolor=BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=MUTED, labelsize=12.5)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return ax


def render(name, dur, draw, hold=3.0):
    """Draw frames for dur seconds (t from 0 to 1), hold the last, write <name>.mp4 and <name>.png."""
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    wr = iio.get_writer(str(OUT / f"{name}.mp4"), fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p",
                        macro_block_size=8)
    n = int(dur * FPS)
    for i in range(n):
        fig.clf()
        fig.set_facecolor(BG)
        draw(fig, i / (n - 1))
        fig.canvas.draw()
        frame = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        wr.append_data(frame)
    for _ in range(int(hold * FPS)):
        wr.append_data(frame)
    wr.close()
    iio.imwrite(OUT / f"{name}.png", frame)
    plt.close(fig)
    print(f"{name}: {dur + hold:.0f}s")


# ---------- x8: receipts ----------

def receipts_rows(D):
    w, card = D["w"], D["card"]
    sim = D["sim"]
    m = pd.read_csv(SC.FROZEN / "municipality_forecast_2026.csv").set_index("muni")
    won = w.act_c.value_counts()
    n = len(w)
    metros = card["metros"]
    metros_right = sum(v["largest"][0] == v["largest"][1] and (v["hung"][0] > 0.5) == v["hung"][1] for v in metros.values())
    big3 = all(metros[c]["largest"][1] == "DA" for c in ("JHB", "TSH", "EKU"))
    nat = card["national"]["ANC"]
    return [
        ("ANC wins over half the wards", f"{(sim.ANC > sim.sum(axis=1) / 2).mean():.0%} chance",
         f"{won['ANC']:,} of {n:,} ({won['ANC'] / n:.0%})", "right" if won["ANC"] > n / 2 else "wrong"),
        ("DA wins more wards than the ANC", f"0 of {len(sim):,} simulations", f"ANC {won['ANC']:,}, DA {won['DA']:,}",
         "right" if won["ANC"] > won["DA"] else "wrong"),
        ("DA first in Joburg, Tshwane, Ekurhuleni",
         " · ".join(f"{m.at[c, 'p_largest']:.0%}" for c in ("JHB", "TSH", "EKU")), "All three" if big3 else "Not all",
         "right" if big3 else "wrong"),
        ("7 metros hung, Cape Town keeps a majority", "8 metro calls", f"{metros_right} of 8 right",
         "right" if metros_right == 8 else "mixed"),
        ("ANC vote share about 29%", f"{nat['forecast']}%", f"{nat['actual']}%, inside the range", "mixed"),
        ("IFP favoured in 410 wards", "the by-election call", f"Won {won['IFP']:,}", "wrong"),
        ("DA wins about 1,100 wards", f"{D['sim'].DA.mean():,.0f} expected", f"Won {won['DA']:,}", "wrong"),
        (f"ActionSA wins about {D['sim'].ASA.mean():,.0f} wards", f"{D['sim'].ASA.mean():,.0f} expected",
         f"Won {won['ASA']:,}, in the wrong wards", "mixed"),
    ]


def x8_receipts(D):
    rows = receipts_rows(D)
    style = {"right": ("✓", "Right", GOOD), "mixed": ("≈", "Close", MIXED), "wrong": ("✗", "Missed", BAD)}
    tally = {v: sum(r[3] == v for r in rows) for v in ("right", "mixed", "wrong")}

    def draw(fig, t):
        head(fig, "What I said vs what happened",
             f"My final forecast, frozen the night before the vote, against the IEC results. "
             f"{tally['right']} right, {tally['mixed']} close, {tally['wrong']} missed.",
             a=seg(t, 0, 0.08))
        top, step = 0.72, 0.08
        for x, lab in ((0.05, "THE FORECAST SAID"), (0.45, "HOW SURE"), (0.625, "WHAT HAPPENED")):
            fig.text(x, top + 0.045, lab, fontsize=10.5, color=MUTED, alpha=seg(t, 0.05, 0.12), fontweight="bold")
        for i, (claim, conf, result, verdict) in enumerate(rows):
            y = top - i * step
            a = seg(t, 0.1 + i * 0.09, 0.16 + i * 0.09)      # the claim appears
            b = seg(t, 0.15 + i * 0.09, 0.2 + i * 0.09)       # then the verdict
            fig.text(0.05, y, claim, fontsize=15.5, color=INK, va="center", alpha=a)
            fig.text(0.45, y, conf, fontsize=13, color=MUTED, va="center", alpha=a)
            fig.text(0.625, y, result, fontsize=14, color=INK, va="center", alpha=b)
            sym, word, c = style[verdict]
            fig.text(0.875, y, sym, fontsize=20, color=c, va="center", ha="center", alpha=b, fontfamily="DejaVu Sans",
                     fontweight="bold")
            fig.text(0.9, y, word, fontsize=14, color=c, va="center", alpha=b, fontweight="bold")
            if i < len(rows) - 1:
                fig.add_artist(plt.Line2D([0.05, 0.95], [y - step / 2] * 2, color=GRID, linewidth=0.8, alpha=a))

    render("x8_receipts", 9.0, draw, hold=4.0)


# ---------- x9: the simple rule ----------

def x9_simple_rule(D):
    w = D["w"]
    rows = [(r, w.rating == r) for r in ["Safe", "Likely", "Lean", "Toss-up"]]
    vals = [(lab, int(k.sum()), w.hit[k].mean(), w.base_national_hit[k].mean()) for lab, k in rows]
    tu = vals[-1]

    def draw(fig, t):
        head(fig, "In close wards, a simple rule beat my model",
             "Share of ward winners called correctly. The simple rule: pick whoever led the ward on the 2024 national ballot.",
             a=seg(t, 0, 0.08))
        ax = axes(fig, [0.2, 0.13, 0.62, 0.6])
        n = len(vals)
        g = seg(t, 0.1, 0.45)
        for i, (lab, cnt, mine, rule) in enumerate(vals):
            y = n - 1 - i
            a = seg(t, 0.06 + i * 0.03, 0.12 + i * 0.03)
            m_x, r_x = 0.5 + (mine - 0.5) * g, 0.5 + (rule - 0.5) * g
            ax.plot([m_x, r_x], [y, y], color=GRID, linewidth=4, alpha=a, zorder=1)
            ax.scatter(r_x, y, s=230, facecolor=BG, edgecolor=INK, linewidth=2.5, zorder=3, alpha=a)
            ax.scatter(m_x, y, s=230, color=ACCENT, edgecolor=BG, linewidth=2, zorder=4, alpha=a)
            if g >= 1:
                lift = 0.32
                ax.text(mine, y + lift, f"{mine:.0%}", ha="center", fontsize=13, color=ACCENT, fontweight="bold")
                ax.text(rule, y - lift - 0.05, f"{rule:.0%}", ha="center", va="top", fontsize=13, color=INK)
        ax.set_yticks(range(n))
        ax.set_yticklabels([f"{lab}  ({cnt:,} wards)" for lab, cnt, _, _ in vals][::-1], color=INK, fontsize=14)
        ax.set_xlim(0.45, 1.0)
        ax.set_ylim(-0.7, n - 0.4)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        # legend, direct
        la = seg(t, 0.08, 0.15)
        fig.text(0.2, 0.775, "●", color=ACCENT, fontsize=18, fontfamily="DejaVu Sans", alpha=la, va="center")
        fig.text(0.222, 0.775, "My model", color=INK, fontsize=13.5, alpha=la, va="center")
        fig.text(0.34, 0.775, "○", color=INK, fontsize=18, fontfamily="DejaVu Sans", alpha=la, va="center")
        fig.text(0.362, 0.775, "Simple rule", color=INK, fontsize=13.5, alpha=la, va="center")
        c = seg(t, 0.55, 0.68)
        fig.text(0.84, 0.3, "Toss-ups:", fontsize=15, color=MUTED, alpha=c)
        fig.text(0.84, 0.225, f"me {tu[2]:.0%}", fontsize=24, color=ACCENT, fontfamily="Georgia", alpha=c)
        fig.text(0.84, 0.155, f"rule {tu[3]:.0%}", fontsize=24, color=INK, fontfamily="Georgia", alpha=c)
        fig.text(0.84, 0.1, "a coin toss vs. a\nplain old shortcut", fontsize=11.5, color=MUTED, alpha=c, va="top")

    render("x9_simple_rule", 8.0, draw, hold=4.0)


# ---------- x10: the upsets ----------

def upset_groups(w):
    z = w[w.p_actual < 0.001]
    named = {"SOUTH AFRICAN COMMUNIST PARTY": "SACP", "INDEPENDENT": "Independent candidates",
             "UNITED DEMOCRATIC MOVEMENT": "UDM", "AFRICAN CONTENT MOVEMENT": "African Content Movement",
             "AFRICAN TRANSFORMATION MOVEMENT": "ATM", "SERVICE DELIVERY PARTY": "Service Delivery Party"}
    tracked = set(SC.S.PARTIES)
    grp = z.actual.map(lambda a: named.get(a, "Parties the model tracks" if a in tracked else "OTHER"))
    other = z.actual[grp == "OTHER"]
    grp = grp.replace("OTHER", f"{other.nunique()} other small & local parties")
    counts = grp.value_counts()
    tracked_lab = "Parties the model tracks"
    order = [g for g in counts.index if g != tracked_lab] + ([tracked_lab] if tracked_lab in counts else [])
    return len(z), [(g, int(counts[g])) for g in order]


def x10_upsets(D):
    total, groups = upset_groups(D["w"])
    sacp = dict(groups).get("SACP", 0)

    def draw(fig, t):
        head(fig, f"{total} wards went to someone my model gave no chance",
             f"Each square is one ward whose winner had a 0% forecast chance. Top of the list: the SACP, standing on its own\n"
             f"for the first time, took {sacp} wards. My model never gave it a column of its own.", a=seg(t, 0, 0.08))
        top, step, size, gap, x0 = 0.66, 0.068, 0.0135, 0.0035, 0.37
        shown = int(round(seg(t, 0.1, 0.75) * total))
        k = 0
        for i, (g, c) in enumerate(groups):
            y = top - i * step
            a = seg(t, 0.08 + i * 0.02, 0.14 + i * 0.02)
            fig.text(x0 - 0.02, y, g, fontsize=14, color=INK, ha="right", va="center", alpha=a)
            for j in range(c):
                on = k < shown
                k += 1
                if not on:
                    continue
                colr = MUTED if g == "Parties the model tracks" else ACCENT
                fig.add_artist(plt.Rectangle((x0 + j * (size + gap), y - 0.0215), size, 0.043, color=colr,
                                             transform=fig.transFigure))
            if k <= shown:
                fig.text(x0 + c * (size + gap) + 0.008, y, f"{c}", fontsize=14, color=INK, va="center", fontweight="bold")
        # the grey row is explained, so colour is not doing the work alone
        fig.text(0.05, 0.1, "Grey: the model tracks these parties but gave the winner 0% in that ward.", fontsize=11.5,
                 color=MUTED, alpha=seg(t, 0.75, 0.85))

    render("x10_upsets", 8.5, draw, hold=4.0)


# ---------- x11: party tilt ----------

def x11_party_tilt(D):
    w = D["w"].copy()
    w["grp"] = w.fav_c.where(w.fav_c.isin(["ANC", "DA", "IFP", "MK"]), "SMALL")
    g = w.groupby("grp").agg(wards=("hit", "size"), exp=("win_prob", "sum"), got=("hit", "sum")).loc[["ANC", "DA", "IFP", "MK", "SMALL"]]

    def draw(fig, t):
        head(fig, "My model was too kind to the DA",
             "Wards grouped by the favoured party. Hollow: how many the favourite was expected to win. Filled: how many it won.",
             a=seg(t, 0, 0.08))
        ax = axes(fig, [0.24, 0.13, 0.5, 0.62])
        n = len(g)
        mv = seg(t, 0.3, 0.6)
        for i, (p, r) in enumerate(g.iterrows()):
            y = n - 1 - i
            a = seg(t, 0.08 + i * 0.04, 0.16 + i * 0.04)
            c = SC.COL.get(p, SC.COL["LOCAL"])
            e, o = r.exp / r.wards, r.got / r.wards
            x = e + (o - e) * mv
            ax.plot([e, x], [y, y], color=GRID, linewidth=4, zorder=1, alpha=a)
            ax.scatter(e, y, s=230, facecolor=BG, edgecolor=c, linewidth=2.5, zorder=3, alpha=a)
            ax.scatter(x, y, s=230, color=c, edgecolor=BG, linewidth=2, zorder=4, alpha=a * (1 if mv > 0 else 0))
            if mv >= 1:
                d = r.got - r.exp
                big = abs(d) >= 50
                fig.text(0.76, 0.13 + (y + 0.5) / (n + 0.1) * 0.62 - 0.005, f"{d:+,.0f} wards", fontsize=16 if big else 13.5,
                         color=INK if big else MUTED, fontweight="bold" if big else "normal", va="center",
                         fontfamily="Georgia" if big else None)
        ax.set_yticks(range(n))
        ax.set_yticklabels([f"{'Small & local' if p == 'SMALL' else SC.nm(p)} favoured ({int(r.wards):,})" for p, r in g.iterrows()][::-1],
                           color=INK, fontsize=13.5)
        ax.set_xlim(0.15, 1.0)
        ax.set_ylim(-0.6, n - 0.4)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
        ax.set_xlabel("Share of these wards the favourite won", color=MUTED, fontsize=12)

    render("x11_party_tilt", 8.0, draw, hold=4.0)


# ---------- x12, x13: reuse the scorecard drawings ----------

def x12_ward_totals(D):
    _, seats = SC.toplines(D)
    out = [SC.nm(r["p"]) for r in seats if not (r["lo90"] <= r["actual"] <= r["hi90"])]
    anc = next(r for r in seats if r["p"] == "ANC")

    def draw(fig, t):
        head(fig, f"The ANC won more wards than {anc['pct']:.0%} of my simulated elections",
             f"Grey: the 80% and 90% ranges of wards won (of 4,485). Tick: forecast. Dot: result.\n"
             f"Vote shares all landed inside their ranges. Wards won did not for {' and '.join(out)}.",
             a=seg(t, 0, 0.08))
        ax = axes(fig, [0.16, 0.1, 0.62, 0.62])
        SC.draw_ranges(ax, seats, "", t=seg(t, 0.08, 0.4), dot_t=seg(t, 0.45, 0.7), dark=True)
        for lab in ax.get_yticklabels():
            lab.set_color(INK)
            lab.set_fontsize(13.5)
        ax.set_xlim(0, 3000)

    render("x12_ward_totals", 8.0, draw, hold=4.0)


def x13_calibration(D):
    g = SC.calibration(D["w"])

    def draw(fig, t):
        head(fig, "When I said 85%, it happened 81% of the time",
             "Wards grouped by the favourite's forecast chance. On the dashed line, the chances were honest.", a=seg(t, 0, 0.08))
        ax = fig.add_axes([0.1, 0.12, 0.62, 0.66], facecolor=BG)
        SC.draw_calibration(ax, g, t=seg(t, 0.08, 0.65), dark=True)
        a = seg(t, 0.72, 0.85)
        fig.text(0.76, 0.62, f"Expected {g.exp.sum():,.0f}\nfavourites to win", fontsize=15, color=MUTED, alpha=a)
        fig.text(0.76, 0.47, f"{g.got.sum():,.0f} won", fontsize=30, color=INK, fontfamily="Georgia", alpha=a)
        fig.text(0.76, 0.4, "honest at the extremes,\na bit overconfident\nin the middle", fontsize=13, color=MUTED, alpha=a,
                 va="top")

    render("x13_calibration", 8.0, draw, hold=4.0)


# ---------- x14: ActionSA ----------

def x14_actionsa(D):
    w, card = D["w"], D["card"]
    asa = SC.COL["ASA"]
    metros = [("TSH", "Tshwane"), ("EKU", "Ekurhuleni"), ("JHB", "Johannesburg")]
    seats = [(name, *card["metros"][c]["seats"]["ASA"]) for c, name in metros]
    won = w[w.act_c == "ASA"]
    by_fav = won.fav_c.value_counts()
    picked = int(by_fav.get("ASA", 0))
    gp = card["provinces"]["Gauteng"]["ASA"]

    def draw(fig, t):
        head(fig, "ActionSA doubled its forecast seats in Tshwane and Ekurhuleni",
             f"My model had ActionSA on {gp[0]}% in Gauteng. It got {gp[1]}%. The ward total was close "
             f"({D['sim'].ASA.mean():.0f} expected, {len(won)} won),\nbut it won them in the wrong places: "
             f"only {picked} of its {len(won)} wards were ones I had it favoured to win.", a=seg(t, 0, 0.08))
        # left: council seats, forecast (hollow) to result (filled)
        fig.text(0.05, 0.71, "Council seats: forecast and result", fontsize=14, color=INK, fontweight="bold", alpha=seg(t, 0.05, 0.12))
        ax = axes(fig, [0.17, 0.14, 0.33, 0.52])
        mv = seg(t, 0.2, 0.5)
        n = len(seats)
        for i, (name, f, a) in enumerate(seats):
            y = n - 1 - i
            al = seg(t, 0.08 + i * 0.04, 0.16 + i * 0.04)
            x = f + (a - f) * mv
            ax.plot([f, x], [y, y], color=GRID, linewidth=4, alpha=al, zorder=1)
            ax.scatter(f, y, s=260, facecolor=BG, edgecolor=asa, linewidth=2.5, zorder=3, alpha=al)
            if mv > 0:
                ax.scatter(x, y, s=260, color=asa, edgecolor=BG, linewidth=2, zorder=4)
            if mv >= 1:
                ax.text(f, y + 0.3, f"{int(f + 0.5)}", ha="center", fontsize=12.5, color=MUTED)
                ax.text(a, y + 0.3, f"{a}", ha="center", fontsize=15, color=INK, fontweight="bold")
        ax.set_yticks(range(n))
        ax.set_yticklabels([s_[0] for s_ in seats][::-1], color=INK, fontsize=14)
        ax.set_xlim(0, 60)
        ax.set_ylim(-0.6, n - 0.2)
        # right: one square per ward ActionSA won, filled if the model had it favoured there
        fig.text(0.58, 0.71, f"The {len(won)} wards ActionSA won", fontsize=14, color=INK, fontweight="bold", alpha=seg(t, 0.05, 0.12))
        order = [("ASA", "I had ActionSA favoured"), ("ANC", "I had the ANC favoured"), ("DA", "I had the DA favoured"),
                 ("EFF", "I had the EFF favoured")]
        shown = int(round(seg(t, 0.45, 0.8) * len(won)))
        k, size, gap, per_row, x0, y0 = 0, 0.0215, 0.006, 12, 0.58, 0.62
        for code, lab in order:
            for _ in range(int(by_fav.get(code, 0))):
                if k < shown:
                    r_, c_ = divmod(k, per_row)
                    filled = code == "ASA"
                    fig.add_artist(plt.Rectangle((x0 + c_ * (size + gap), y0 - r_ * (size * 1.78 + gap) - size * 1.78),
                                                 size, size * 1.78, transform=fig.transFigure,
                                                 facecolor=asa if filled else BG, edgecolor=asa, linewidth=1.6))
                k += 1
        lg = seg(t, 0.8, 0.9)
        ly = 0.25
        fig.add_artist(plt.Rectangle((0.58, ly - 0.012), 0.016, 0.028, transform=fig.transFigure, color=asa, alpha=lg))
        fig.text(0.602, ly, f"{picked}: wards I had ActionSA favoured to win", fontsize=13, color=INK, va="center", alpha=lg)
        fig.add_artist(plt.Rectangle((0.58, ly - 0.072), 0.016, 0.028, transform=fig.transFigure, facecolor=BG,
                                     edgecolor=asa, linewidth=1.6, alpha=lg))
        others = ", ".join(f"{SC.nm(c)} {int(by_fav[c])}" for c in ("ANC", "DA", "EFF") if by_fav.get(c, 0))
        fig.text(0.602, ly - 0.06, f"{len(won) - picked}: I had someone else favoured ({others})", fontsize=13, color=INK,
                 va="center", alpha=lg)

    render("x14_actionsa", 9.0, draw, hold=4.0)


def main(only=()):
    """python src/x_scorecard.py [x10 x12 ...] renders only the named clips."""
    OUT.mkdir(parents=True, exist_ok=True)
    D = SC.load()
    for f in (x8_receipts, x9_simple_rule, x10_upsets, x11_party_tilt, x12_ward_totals, x13_calibration, x14_actionsa):
        if not only or f.__name__.split("_")[0] in only:
            f(D)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
