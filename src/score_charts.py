"""Charts and an animation of how the frozen 3 Nov forecast did, in content/scorecard/. Run after score.py 2026.

The checks follow the ones US forecasters publish after a midterm (FiveThirtyEight's "How our forecasts performed"):
  sc1  toplines against the forecast ranges: national vote share, and wards won per party
  sc2  calibration: when the forecast said 70%, did the favourite win about 70% of the time?
  sc3  calibration split by the favoured party (FiveThirtyEight found the same kind of lopsidedness in 2022)
  sc4  ward calls against two simple rules, by rating, so easy wards don't flatter the result
  sc5  where the vote-share errors were: ANC and DA by province
  sc6  map of the wards the forecast got wrong
  scorecard.mp4  animated version of sc1 and sc2, plus scorecard_final.png
Also writes outputs/ward_results_vs_forecast_2026.csv (one row per ward: forecast, result, hit).
Parties sit in labelled rows, so colour only repeats the label.
"""
import json
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import score as S  # noqa: E402
from paths import OUTPUTS, PROJECT, RAW  # noqa: E402

warnings.filterwarnings("ignore")
OUT = PROJECT / "content" / "scorecard"
FROZEN = PROJECT / "frozen"
COL = {"ANC": "#22a05a", "DA": "#3b7ddd", "MK": "#8a5cc2", "EFF": "#d6334a", "IFP": "#e0a21b", "PA": "#c45a9b",
       "FFP": "#f07f2a", "ASA": "#2fb3a6", "LOCAL": "#8a8f98", "OTH": "#8a8f98"}
NAME = {"FFP": "FF+", "ASA": "ActionSA", "OTH": "Other", "LOCAL": "Local & small"}
BG, INK, MUTED, GRID = "#ffffff", "#17201c", "#5b6660", "#e3e6e3"
RANGE90, RANGE80 = "#e4e8e5", "#c9d0cb"
ACCENT = "#c2410c"  # one emphasis colour: "this forecast" / "missed"; not a party colour
CREDIT = "Credit: Gava Charles · LGE 2026 Ward Forecast · forecast frozen 3 Nov 2026, scored against IEC results · gavacharles.github.io/lge2026-ward-forecast"
ORDER = ["ANC", "DA", "MK", "IFP", "EFF", "ASA", "FFP", "PA", "LOCAL"]
plt.rcParams.update({"font.family": "Avenir Next", "font.size": 12, "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": BG,
                     "axes.facecolor": BG, "savefig.facecolor": BG})


def nm(p):
    return NAME.get(p, p)


def frame(title, sub, size=(10, 6.25)):
    fig = plt.figure(figsize=size, dpi=160)
    h = size[1]
    fig.text(0.035, 1 - 0.3 / h, title, fontsize=20, fontfamily="Georgia", va="top")
    fig.text(0.035, 1 - 0.78 / h, sub, fontsize=12, color=MUTED, va="top", linespacing=1.35)
    fig.text(0.035, 0.14 / h, CREDIT, fontsize=8.5, color=MUTED)
    return fig


def quiet(ax, grid_axis="x"):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ---------- data ----------

def load():
    w, m, s, alt = S.forecast_2026()
    A = S.actual_tables(S.results_2026(), w, m)
    all_w = w.copy()
    idx = w.index.intersection(A["winner"].index)
    w = w.loc[idx].copy()
    act = A["winner"].loc[idx]
    code = lambda x: x if x in S.PARTIES else "LOCAL"  # noqa: E731
    w["actual"] = act
    w["hit"] = w.favourite == act
    w["fav_c"] = w.favourite.map(code)
    w["act_c"] = act.map(code)
    w["p_actual"] = S.p_of_actual(w, act)
    w["base_national_hit"] = w.base_national == act
    w["base_prev_hit"] = w.base_prev_local == act
    for p in S.COLS:
        w[f"actual_share_{p}"] = (A["shares"].reindex(idx)[p] * 100).round(1)
    keep = ["province", "municipality", "ward_no", "favourite", "win_prob", "rating", "actual", "hit", "p_actual",
            "base_national", "base_national_hit", "base_prev_local", "base_prev_hit"] + \
           [f"share_{p}" for p in S.COLS] + [f"actual_share_{p}" for p in S.COLS]
    w[keep].to_csv(OUTPUTS / "ward_results_vs_forecast_2026.csv")
    unmatched = all_w.drop(idx)
    return dict(w=w, A=A, s=s, unmatched=unmatched, sim=pd.read_csv(FROZEN / "sim_ward_totals_2026.csv"),
                card=json.load(open(OUTPUTS / "scorecard_2026.json")))


def toplines(D):
    """Rows for sc1 and the animation: forecast ranges and the result, for vote share and wards won."""
    iv, fc, nat = D["s"]["national_interval_90"], D["s"]["national_share"], D["A"]["national"] * 100
    vote = []
    for p in [p for p in ORDER if p != "LOCAL"] + ["OTH"]:
        vote.append(dict(p=p, lo90=iv[p]["p05"], hi90=iv[p]["p95"], lo80=None, hi80=None, mid=fc[p], actual=float(nat[p])))
    # wards won: the 78 forecast wards missing from the results are filled with their forecast chances,
    # so the actual totals cover the same 4,485 wards as the simulations
    um = D["unmatched"]
    won = D["w"].act_c.value_counts()
    seats = []
    for p in ORDER:
        col = "p_LOCAL_TOP" if p == "LOCAL" else f"p_{p}"
        q = D["sim"][p].quantile([.05, .1, .5, .9, .95])
        a = won.get(p, 0) + um[col].sum()
        seats.append(dict(p=p, lo90=q[.05], hi90=q[.95], lo80=q[.1], hi80=q[.9], mid=q[.5], actual=float(a),
                          pct=float((D["sim"][p] < a).mean())))
    return vote, seats


def calibration(w):
    bins = [0, .5, .6, .7, .8, .9, .95, 1.0001]
    g = w.groupby(pd.cut(w.win_prob, bins), observed=True).agg(wards=("hit", "size"), forecast=("win_prob", "mean"),
                                                               won=("hit", "mean"), exp=("win_prob", "sum"), got=("hit", "sum"))
    g["label"] = ["Under 50%", "50–60%", "60–70%", "70–80%", "80–90%", "90–95%", "95%+"][: len(g)]
    return g.reset_index(drop=True)


# ---------- static charts ----------

def draw_ranges(ax, rows, unit, t=1.0, dot_t=1.0, dark=False):
    """Forecast range bars (80% darker inside 90%), forecast tick, actual dot. t/dot_t animate growth and the drop-in."""
    r90, r80, ink, muted = (("#26313b", "#3a4652", "#f2f5f4", "#a7b1b8") if dark else (RANGE90, RANGE80, INK, MUTED))
    n = len(rows)
    for i, r in enumerate(rows):
        y = n - 1 - i
        for lo, hi, c, hgt in ((r["lo90"], r["hi90"], r90, 0.5), (r["lo80"], r["hi80"], r80, 0.5)):
            if lo is None:
                continue
            a, b = r["mid"] - (r["mid"] - lo) * t, r["mid"] + (hi - r["mid"]) * t
            ax.barh(y, b - a, left=a, height=hgt, color=c, linewidth=0)
        ax.plot([r["mid"]] * 2, [y - 0.3, y + 0.3], color=ink, linewidth=2, alpha=min(1, t * 2), solid_capstyle="butt")
        if dot_t > 0:
            yy = y + 0.9 * (1 - dot_t) ** 2
            outside = not (r["lo90"] <= r["actual"] <= r["hi90"])
            ax.scatter(r["actual"], yy, s=90, color=COL[r["p"]], edgecolor=BG if not dark else "#0f1419", linewidth=2,
                       zorder=5, alpha=min(1, dot_t * 1.5))
            if dot_t >= 1:
                txt = f"{r['actual']:.1f}{unit}" if unit else f"{r['actual']:,.0f}"
                if outside:
                    txt += "\n   outside 90% range"
                x_txt = max(r["actual"], r["hi90"])
                ax.text(x_txt, y, "   " + txt, va="center", fontsize=10.5,
                        color=(ACCENT if not dark else "#ff8a50") if outside else muted,
                        fontweight="bold" if outside else "normal")
    ax.set_yticks(range(n))
    ax.set_yticklabels([nm(r["p"]) for r in rows][::-1], color=ink)
    ax.set_ylim(-0.7, n - 0.3)


def sc1_toplines(D):
    vote, seats = toplines(D)
    n_in = sum(r["lo90"] <= r["actual"] <= r["hi90"] for r in vote)
    s_out = [nm(r["p"]) for r in seats if not (r["lo90"] <= r["actual"] <= r["hi90"])]
    fig = frame(f"Vote shares landed in range. The ANC's ward total did not",
                f"Grey bars: the forecast's 80% (darker) and 90% ranges. Black tick: the forecast. Dot: the result.\n"
                f"{n_in} of {len(vote)} national vote shares fell inside the 90% range. Wards won fell outside it for {' and '.join(s_out)}.",
                size=(12, 6.8))
    ax1 = fig.add_axes([0.1, 0.12, 0.33, 0.62])
    draw_ranges(ax1, vote, "%")
    quiet(ax1)
    ax1.set_title("National vote share, ward ballot (%)", loc="left", fontsize=12.5, fontweight="bold", pad=10)
    ax1.set_xlim(0, 46)
    ax2 = fig.add_axes([0.58, 0.12, 0.3, 0.62])
    draw_ranges(ax2, seats, "")
    quiet(ax2)
    ax2.set_title("Wards won (of 4,485)", loc="left", fontsize=12.5, fontweight="bold", pad=10)
    ax2.set_xlim(0, 3000)
    fig.text(0.58, 0.04, "78 forecast wards could not be matched to IEC ward IDs;\ntheir forecast chances fill that gap in the actual totals.",
             fontsize=8.5, color=MUTED)
    fig.savefig(OUT / "sc1_toplines.png")
    plt.close(fig)


def draw_calibration(ax, g, t=1.0, dark=False):
    ink, muted, grid = ("#f2f5f4", "#a7b1b8", "#2a3440") if dark else (INK, MUTED, GRID)
    ax.plot([0.3, 1], [0.3, 1], color=muted, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(0.40, 0.56, "perfect calibration", color=muted, fontsize=9.5, ha="left", va="bottom")
    for i, r in g.iterrows():
        k = min(1, max(0, t * len(g) - i))  # bins appear one after another
        if k <= 0:
            continue
        y = r.forecast + (r.won - r.forecast) * k
        ax.plot([r.forecast, r.forecast], [r.forecast, y], color=ACCENT if not dark else "#ff8a50", linewidth=2, alpha=0.6)
        ax.scatter(r.forecast, y, s=30 + r.wards / 6, color=ACCENT if not dark else "#ff8a50", edgecolor=BG if not dark else "#0f1419",
                   linewidth=2, zorder=5)
        if k >= 1:
            ax.text(r.forecast + 0.012, y - 0.008, f"{r.won:.0%} won\n{r.wards:,} wards", fontsize=9, color=muted, va="top")
    ax.set_xlim(0.38, 1.02)
    ax.set_ylim(0.3, 1.04)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=muted)
    ax.grid(color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Forecast chance for the favourite (average within each band)", color=muted)
    ax.set_ylabel("Share of those wards the favourite won", color=muted)


def sc2_calibration(D):
    g = calibration(D["w"])
    exp, got = g.exp.sum(), g.got.sum()
    fig = frame("The chances were mostly honest, and a little overconfident",
                f"Wards grouped by the favourite's forecast chance. On the dashed line the chances were honest; below it, overconfident.\n"
                f"Across all {g.wards.sum():,} wards the forecast expected its favourites to win {exp:,.0f}. They won {got:,.0f}.",
                size=(10, 7))
    ax = fig.add_axes([0.11, 0.1, 0.84, 0.7])
    draw_calibration(ax, g)
    fig.savefig(OUT / "sc2_calibration.png")
    plt.close(fig)


def sc3_by_party(D):
    w = D["w"].copy()
    w["grp"] = w.fav_c.where(w.fav_c.isin(["ANC", "DA", "IFP", "MK"]), "SMALL")
    g = w.groupby("grp").agg(wards=("hit", "size"), exp=("win_prob", "sum"), got=("hit", "sum"))
    g = g.loc[["ANC", "DA", "IFP", "MK", "SMALL"]]
    g["exp_r"], g["got_r"] = g.exp / g.wards, g.got / g.wards
    fig = frame("The forecast was too generous to the DA and too stingy to the ANC",
                "Wards grouped by the favoured party: share the forecast expected it to win (hollow) and share it won (filled).\n"
                "FiveThirtyEight found a similar tilt in 2022: Republican favourites won as expected, Democratic ones won more.",
                size=(10, 5.6))
    ax = fig.add_axes([0.22, 0.12, 0.72, 0.62])
    n = len(g)
    for i, (p, r) in enumerate(g.iterrows()):
        y = n - 1 - i
        c = COL.get(p, COL["LOCAL"])
        ax.plot([r.exp_r, r.got_r], [y, y], color=GRID, linewidth=3, solid_capstyle="round", zorder=1)
        ax.scatter(r.exp_r, y, s=110, facecolor=BG, edgecolor=c, linewidth=2.2, zorder=3)
        ax.scatter(r.got_r, y, s=110, color=c, edgecolor=BG, linewidth=2, zorder=4)
        diff = r.got - r.exp
        right = max(r.exp_r, r.got_r)
        ax.text(right + 0.035, y, f"expected {r.exp:,.0f}, won {r.got:,.0f}  ({diff:+,.0f})", va="center", fontsize=10.5,
                color=INK if abs(diff) >= 50 else MUTED, fontweight="bold" if abs(diff) >= 50 else "normal")
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{'Small & local' if p == 'SMALL' else nm(p)} favoured\n({int(r.wards):,} wards)"
                        for p, r in g.iterrows()][::-1], fontsize=10.5)
    ax.set_xlim(0.0, 1.32)
    ax.set_xticks([0, .25, .5, .75, 1])
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("Share of these wards the favourite won", color=MUTED)
    ax.set_ylim(-0.6, n - 0.4)
    quiet(ax)
    fig.savefig(OUT / "sc3_by_party.png")
    plt.close(fig)


def sc4_simple_rules(D):
    w = D["w"]
    rows = [("All wards", w.index == w.index)] + [(r, w.rating == r) for r in ["Safe", "Likely", "Lean", "Toss-up"]] + \
           [("All but Safe", w.rating != "Safe")]
    fig = frame("In close wards, a simple rule beat the model",
                "Share of ward winners called correctly. 'Safe' wards are easy for any method, so they flatter an overall score;\n"
                "the test is the close ones. Picking each ward's leader on the 2024 national ballot did better in every competitive band.",
                size=(10, 6.2))
    ax = fig.add_axes([0.2, 0.15, 0.74, 0.6])
    n = len(rows)
    marks = [("This forecast", "hit", dict(s=120, color=ACCENT, marker="o", zorder=5)),
             ("2024 national-ballot leader", "base_national_hit", dict(s=110, facecolor=BG, edgecolor=INK, linewidth=2, marker="o", zorder=4)),
             ("2021 local winner", "base_prev_hit", dict(s=80, color=MUTED, marker="D", zorder=3))]
    for i, (lab, k) in enumerate(rows):
        y = n - 1 - i
        vals = [w.loc[k, col].mean() for _, col, _ in marks]
        ax.plot([min(vals), max(vals)], [y, y], color=GRID, linewidth=3, zorder=1)
        for (name, col, kw), v in zip(marks, vals):
            ax.scatter(v, y, **kw)
        ax.text(vals[0], y + 0.3, f"{vals[0]:.0%}", ha="center", fontsize=9.5, color=ACCENT, fontweight="bold")
        ax.text(vals[1], y - 0.42, f"{vals[1]:.0%}", ha="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{lab}\n({k.sum():,} wards)" for lab, k in rows][::-1], fontsize=10.5)
    ax.set_xlim(0.35, 1.0)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(-0.8, n - 0.3)
    quiet(ax)
    handles = [plt.Line2D([], [], linestyle="", markersize=np.sqrt(kw.get("s", 80)) * 0.85, marker=kw["marker"],
                          markerfacecolor=kw.get("color", kw.get("facecolor")), markeredgecolor=kw.get("edgecolor", kw.get("color")),
                          markeredgewidth=kw.get("linewidth", 0)) for _, _, kw in marks]
    fig.legend(handles, [m[0] for m in marks], loc="upper left", bbox_to_anchor=(0.19, 0.8), ncol=3, frameon=False, fontsize=10.5)
    fig.savefig(OUT / "sc4_simple_rules.png")
    plt.close(fig)


def sc5_provinces(D):
    pv = D["card"]["provinces"]
    anc_up = sum(pv[k]["ANC"][1] > pv[k]["ANC"][0] for k in pv)
    da_down = sum(pv[k]["DA"][1] < pv[k]["DA"][0] for k in pv)
    fig = frame(f"The DA fell short of its forecast in {da_down} of {len(pv)} provinces",
                f"Ward-ballot vote share by province: forecast (hollow) and result (filled). The ANC beat its forecast in {anc_up}. Errors that run the\n"
                "same way across many wards are why US forecasters treat one election as nearer one data point than thousands of tests.",
                size=(11, 6.2))
    order = sorted(pv, key=lambda k: pv[k]["ANC"][1] - pv[k]["ANC"][0], reverse=True)
    for j, p in enumerate(["ANC", "DA"]):
        ax = fig.add_axes([0.2 + j * 0.41, 0.1, 0.36, 0.64])
        n = len(order)
        for i, prov in enumerate(order):
            y = n - 1 - i
            f, a = pv[prov][p]
            ax.plot([f, a], [y, y], color=GRID, linewidth=3, zorder=1)
            ax.scatter(f, y, s=80, facecolor=BG, edgecolor=COL[p], linewidth=2, zorder=3)
            ax.scatter(a, y, s=80, color=COL[p], edgecolor=BG, linewidth=1.5, zorder=4)
            d = a - f
            ax.text(max(f, a) + 2.2, y, f"{d:+.1f}", va="center", fontsize=10, color=INK if abs(d) >= 4 else MUTED,
                    fontweight="bold" if abs(d) >= 4 else "normal")
        ax.set_yticks(range(n))
        ax.set_yticklabels(order[::-1] if j == 0 else [""] * n)
        ax.set_xlim(0, 72)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_title(f"{p} share (%), result minus forecast", loc="left", fontsize=12, fontweight="bold", pad=8)
        quiet(ax)
    fig.savefig(OUT / "sc5_provinces.png")
    plt.close(fig)


def sc6_map(D):
    import geopandas as gpd
    w = D["w"]
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson").set_index("WardID").to_crs("ESRI:102022")
    g.index = g.index.astype(str)
    g["geometry"] = g.geometry.simplify(500)
    miss = w[~w.hit]
    strong = miss.index[miss.win_prob >= 0.7]
    weak = miss.index[miss.win_prob < 0.7]
    fig = frame(f"Where the forecast missed: {len(miss):,} of {len(w):,} wards",
                "Dark: the favourite had a 70%+ chance and lost. Light: closer calls that went the other way.\n"
                "Big rural wards fill the map but hold few voters, so the table on the right counts wards, not area.",
                size=(10, 6.6))
    ax = fig.add_axes([0.02, 0.05, 0.64, 0.75])
    g.plot(ax=ax, color="#eceeec", edgecolor="#ffffff", linewidth=0.1)
    g.loc[g.index.intersection(weak)].plot(ax=ax, color="#f2b58f", edgecolor="#ffffff", linewidth=0.1)
    g.loc[g.index.intersection(strong)].plot(ax=ax, color=ACCENT, edgecolor="#ffffff", linewidth=0.1)
    ax.axis("off")
    x = 0.68
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (ACCENT, "#f2b58f", "#eceeec")]
    fig.legend(handles, [f"Missed, favourite at 70%+ ({len(strong)})", f"Missed, closer call ({len(weak)})", "Called correctly"],
               loc="upper left", bbox_to_anchor=(x - 0.01, 0.78), frameon=False, fontsize=10.5, handlelength=1)
    fig.text(x, 0.56, "Misses by province", fontsize=12.5, fontweight="bold")
    fig.text(x + 0.29, 0.56, "miss rate", fontsize=10, ha="right", color=MUTED)
    by = w.groupby("province").hit.agg(["size", "sum"])
    by["miss"] = by["size"] - by["sum"]
    by["rate"] = by.miss / by["size"]
    for i, (prov, r) in enumerate(by.sort_values("rate", ascending=False).iterrows()):
        fig.text(x, 0.52 - i * 0.04, prov, fontsize=11)
        fig.text(x + 0.2, 0.52 - i * 0.04, f"{r.miss:.0f}", fontsize=11, ha="right", fontweight="bold")
        fig.text(x + 0.29, 0.52 - i * 0.04, f"{r.rate:.0%}", fontsize=10, ha="right", color=MUTED)
    fig.savefig(OUT / "sc6_map.png")
    plt.close(fig)


# ---------- animation ----------

def animate(D):
    import imageio.v2 as iio
    FPS, W, H = 24, 1280, 720
    DBG, DINK, DMUTED = "#0f1419", "#f2f5f4", "#a7b1b8"
    vote, seats = toplines(D)
    g = calibration(D["w"])
    card = D["card"]
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=DBG)

    def ease(t):
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def head(title, sub, alpha=1.0):
        fig.text(0.05, 0.93, title, fontsize=26, fontfamily="Georgia", color=DINK, va="top", alpha=alpha)
        fig.text(0.05, 0.855, sub, fontsize=14, color=DMUTED, va="top", alpha=alpha, linespacing=1.4)
        fig.text(0.05, 0.03, "LGE 2026 Ward Forecast · forecast frozen 3 Nov, scored against IEC results", fontsize=10.5, color=DMUTED)

    def dark_axes(rect):
        ax = fig.add_axes(rect, facecolor=DBG)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0, colors=DMUTED, labelsize=12)
        ax.grid(axis="x", color="#2a3440", linewidth=0.8)
        ax.set_axisbelow(True)
        return ax

    def ranges_scene(t, rows, title, sub, unit, xlim):
        head(title, sub, alpha=ease(t * 4))
        ax = dark_axes([0.16, 0.1, 0.66, 0.66])
        draw_ranges(ax, rows, unit, t=ease((t - 0.08) / 0.3), dot_t=ease((t - 0.42) / 0.25), dark=True)
        for lab in ax.get_yticklabels():
            lab.set_color(DINK)
            lab.set_fontsize(13)
        ax.set_xlim(*xlim)

    def calib_scene(t):
        head("Were the chances honest?",
             "Wards grouped by the favourite's forecast chance. On the dashed line, the chances were right.", alpha=ease(t * 4))
        ax = fig.add_axes([0.1, 0.12, 0.62, 0.66], facecolor=DBG)
        draw_calibration(ax, g, t=ease((t - 0.08) / 0.6), dark=True)
        if t > 0.75:
            a = ease((t - 0.75) / 0.15)
            fig.text(0.76, 0.6, f"Expected {g.exp.sum():,.0f}\nfavourites to win", fontsize=15, color=DMUTED, alpha=a)
            fig.text(0.76, 0.45, f"{g.got.sum():,.0f} won", fontsize=30, color=DINK, fontfamily="Georgia", alpha=a)
            fig.text(0.76, 0.38, "slightly overconfident\nin the 60–90% bands", fontsize=13, color=DMUTED, alpha=a)

    def end_scene(t):
        a = ease(t * 3)
        fig.text(0.05, 0.86, "The scorecard", fontsize=28, fontfamily="Georgia", color=DINK, va="top", alpha=a)
        n_in = sum(r["lo90"] <= r["actual"] <= r["hi90"] for r in vote)
        metros_right = sum(v["largest"][0] == v["largest"][1] and (v["hung"][0] > 0.5) == v["hung"][1] for v in card["metros"].values())
        lines = [(f"{card['ward_accuracy']:.1%}", "of ward winners called correctly"),
                 (f"{card['baseline_national_leader']:.1%}", "for the simple rule: the ward's 2024 national-ballot leader"),
                 (f"{n_in} of {len(vote)}", "national vote shares inside the 90% range"),
                 (f"{metros_right} of {len(card['metros'])}", "metros: largest party and hung/majority both right")]
        for i, (big, small) in enumerate(lines):
            k = ease((t - 0.12 - i * 0.12) / 0.15)
            y = 0.68 - i * 0.15
            fig.text(0.05, y, big, fontsize=34, fontfamily="Georgia", color="#ff8a50" if i == 1 else DINK, alpha=k, va="center")
            fig.text(0.3, y, small, fontsize=17, color=DMUTED, alpha=k, va="center")
        fig.text(0.05, 0.03, "LGE 2026 Ward Forecast · gavacharles.github.io/lge2026-ward-forecast", fontsize=10.5, color=DMUTED)

    n_vote_in = sum(r["lo90"] <= r["actual"] <= r["hi90"] for r in vote)
    s_out = [nm(r["p"]) for r in seats if not (r["lo90"] <= r["actual"] <= r["hi90"])]
    scenes = [
        (6.0, lambda t: ranges_scene(t, vote, "Vote shares: inside the range",
                                     f"Grey: the forecast's 80% and 90% ranges. Tick: forecast. Dot: result. {n_vote_in} of {len(vote)} inside.",
                                     "%", (0, 46))),
        (6.5, lambda t: ranges_scene(t, seats, f"Wards won: {' and '.join(s_out)} broke out",
                                     "Same ranges for the number of wards each party wins (of 4,485).", "", (0, 3500))),
        (6.5, calib_scene),
        (6.0, end_scene),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    wr = iio.get_writer(str(OUT / "scorecard.mp4"), fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=8)
    last = None
    for dur, draw in scenes:
        n = int(dur * FPS)
        for i in range(n):
            fig.clf()
            fig.set_facecolor(DBG)
            draw(i / (n - 1) * 1.0)
            fig.canvas.draw()
            last = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
            wr.append_data(last)
    for _ in range(FPS * 2):  # hold the last frame
        wr.append_data(last)
    wr.close()
    iio.imwrite(OUT / "scorecard_final.png", last)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = load()
    sc1_toplines(D)
    sc2_calibration(D)
    sc3_by_party(D)
    sc4_simple_rules(D)
    sc5_provinces(D)
    sc6_map(D)
    animate(D)
    print("scorecard charts ->", OUT)


if __name__ == "__main__":
    main()
