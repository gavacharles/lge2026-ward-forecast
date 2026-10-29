"""Static visuals for posts (PNG, 1600x900): charts and maps from the forecast outputs.

Writes to content/visuals/. Party colours match the site; every mark is labelled directly, so no
reading depends on colour alone (ANC green vs EFF red is not separable for red-green colour blindness).
"""
import json

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import byelections as BE
from paths import OUTPUTS, PROJECT, RAW

OUT = PROJECT / "content" / "visuals"
COL = {"ANC": "#22a05a", "DA": "#3b7ddd", "MK": "#8a5cc2", "EFF": "#d6334a", "IFP": "#e0a21b", "PA": "#c45a9b",
       "FFP": "#f07f2a", "ASA": "#2fb3a6", "OTH": "#8a8f98"}
NAME = {"FFP": "FF+", "ASA": "ActionSA", "OTH": "Others"}
BG, INK, MUTED, GRID = "#fcfcfb", "#17201c", "#5b6660", "#dde2de"
SOURCE = "LGE 2026 Ward Forecast · gavacharles.github.io/lge2026-ward-forecast · Data: IEC (results, candidate lists 23 Oct), MDB, polls to 15 Oct 2026"
METROS = {"JHB": "Johannesburg", "CPT": "Cape Town", "ETH": "eThekwini", "TSH": "Tshwane", "EKU": "Ekurhuleni",
          "NMA": "N. Mandela Bay", "BUF": "Buffalo City", "MAN": "Mangaung"}

plt.rcParams.update({"font.family": "Avenir Next", "font.size": 13, "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": BG,
                     "axes.facecolor": BG, "savefig.facecolor": BG})


def name(p):
    return NAME.get(p, p)


def frame(title, subtitle):
    fig = plt.figure(figsize=(8, 4.5), dpi=200)
    fig.text(0.04, 0.93, title, fontsize=17, fontfamily="Georgia", ha="left", va="top", color=INK)
    fig.text(0.04, 0.855, subtitle, fontsize=10.5, ha="left", va="top", color=MUTED)
    fig.text(0.04, 0.03, SOURCE, fontsize=7.5, ha="left", color=MUTED)
    return fig


def clean(ax, grid_x=True):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    if grid_x:
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def wards_by_party(nat):
    rows = [r for r in nat if r["party"] != "OTH"] + [r for r in nat if r["party"] == "OTH"]
    rows = sorted(rows, key=lambda r: r["exp"])
    fig = frame("The ANC is favoured in most wards; the DA, MK and IFP split most of the rest",
                "Expected wards won (sum of each ward's win chance), out of 4,485. Label: expected · favoured in")
    ax = fig.add_axes([0.16, 0.12, 0.74, 0.68])
    y = np.arange(len(rows))
    ax.barh(y, [r["exp"] for r in rows], color=[COL[r["party"]] for r in rows], height=0.62)
    for i, r in enumerate(rows):
        ax.text(r["exp"] + 25, i, f"{r['exp']:,.0f} · {r['fav']:,}", va="center", fontsize=10.5, color=INK)
    ax.set_yticks(y, [name(r["party"]) for r in rows])
    ax.set_xlim(0, 2800)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    clean(ax)
    fig.savefig(OUT / "01_wards_by_party.png")
    plt.close(fig)


def metro_seats(m):
    order = ["CPT", "JHB", "TSH", "EKU", "NMA", "ETH", "BUF", "MAN"]
    parts = ["ANC", "DA", "MK", "EFF", "ASA"]
    hung = int((m.loc[order, "p_hung"] > 0.5).sum())
    words = dict(enumerate(["None", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight"]))
    fig = frame(f"{words[hung]} of eight metros are heading for hung councils",
                "Expected council seats, as a share of each council. Dashed line: majority. Only Cape Town is likely to clear it")
    ax = fig.add_axes([0.25, 0.1, 0.71, 0.7])
    for i, code in enumerate(order[::-1]):
        r = m.loc[code]
        left = 0.0
        segs = [(p, r[f"seats_{p}"]) for p in parts]
        segs.append(("OTH", r.council_seats - sum(v for _, v in segs)))
        for p, v in segs:
            share = v / r.council_seats
            ax.barh(i, share, left=left, color=COL[p], height=0.66, edgecolor=BG, linewidth=1)
            if share > 0.075:
                ax.text(left + share / 2, i, f"{ {'OTH': 'Oth', 'ASA': 'ASA'}.get(p, name(p)) } {v:.0f}", ha="center", va="center",
                        fontsize=8.5, color="white", fontweight="bold")
            left += share
    ax.axvline(0.5, color=INK, linestyle=(0, (4, 3)), linewidth=1)
    ax.set_yticks(range(len(order)), [f"{METROS[c]}  ({m.loc[c].council_seats:.0f})" for c in order[::-1]])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    clean(ax, grid_x=False)
    fig.savefig(OUT / "02_metro_seats.png")
    plt.close(fig)


def backtest(bt):
    fig = frame("Tested on 2016 and 2021, the model beat simple rules both times",
                "Share of ward winners called correctly, using only data available before each election")
    ax = fig.add_axes([0.32, 0.13, 0.62, 0.66])
    methods = [("naive_prev_lge", "Previous local winner"), ("naive_npe", "Last national-ballot winner"),
               ("model_byelections", "This model")]
    for j, year in enumerate(["2016", "2021"]):
        for i, (k, lab) in enumerate(methods):
            v = bt[year][k]
            y = j * 4 + i
            c = "#3b7ddd" if k.startswith("model") else "#9aa39e"
            ax.plot([0.85, v], [y, y], color=GRID, linewidth=2, zorder=1)
            ax.scatter(v, y, s=90, color=c, zorder=2, edgecolor=BG, linewidth=1.5)
            ax.text(v + 0.003, y, f"{v:.1%}", va="center", fontsize=10.5,
                    fontweight="bold" if k.startswith("model") else "normal")
        ax.text(0.851, j * 4 + 2.75, year, fontsize=12, fontfamily="Georgia", va="center")
    ax.set_yticks([j * 4 + i for j in range(2) for i in range(3)], [lab for _ in range(2) for _, lab in methods])
    ax.set_xlim(0.85, 0.96)
    ax.set_ylim(-0.7, 7.3)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    clean(ax)
    fig.savefig(OUT / "03_backtest.png")
    plt.close(fig)


def kzn_byelections(summary):
    """Wards favoured in KZN under the published (by-election-led) and poll-led readings."""
    sc = summary["scenarios"]
    parties = ["MK", "IFP", "ANC", "DA"]
    fig = frame("KwaZulu-Natal: polls and by-elections tell different stories",
                f"Wards favoured in KZN. In {summary['kzn_region']['byelections']} by-elections outside eThekwini, "
                "MK has run well behind its 2024 result,\nbut national polls still put it near 2024. "
                "The published forecast follows the by-elections")
    ax = fig.add_axes([0.14, 0.12, 0.8, 0.62])
    y = np.arange(len(parties))
    for k, (key, label, alpha) in enumerate([("byelection", "By-election-led (published)", 1.0),
                                              ("poll", "Poll-led", 0.45)]):
        vals = [sc[key]["kzn"]["favourites"].get(p, 0) for p in parties]
        yy = y + (0.2 if k == 0 else -0.2)
        ax.barh(yy, vals, height=0.38, color=[COL[p] for p in parties], alpha=alpha)
        for v, yv in zip(vals, yy):
            ax.text(v + 6, yv, f"{v} · {label}", va="center", fontsize=10)
    ax.set_yticks(y, [name(p) for p in parties])
    ax.invert_yaxis()
    ax.set_xlim(0, max(sc["poll"]["kzn"]["favourites"].get("MK", 0), 450) * 1.45)
    clean(ax)
    fig.savefig(OUT / "04_kzn_byelections.png")
    plt.close(fig)


def coalitions(m, blocs):
    """Three ways to a majority, per metro: one party alone, ANC + DA, or another coalition (best two shown).
    Each panel is its own chance (they can overlap)."""
    order = ["CPT", "NMA", "MAN", "BUF", "TSH", "EKU", "JHB", "ETH"]
    parties = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]
    others = [b for b, ps in blocs.items() if not {"ANC", "DA"} <= set(ps)]
    short = {"FFP": "FF+", "ASA": "ASA"}
    label = lambda b: ", ".join(short.get(p, p) for p in blocs[b])
    fig = frame("Who can govern? Three ways to a majority in the metros",
                "Chance of a majority of council seats, from the simulations. The panels overlap: where ANC + DA have\n"
                "the numbers, another coalition may too. Arithmetic, not a prediction of which deals get made")
    panels = [("1. One party alone", 0.19, 0.2), ("2. ANC + DA together", 0.42, 0.2), ("3. Best other coalitions", 0.655, 0.31)]
    y = np.arange(len(order))[::-1]
    for t, (title, x0, wd) in enumerate(panels):
        ax = fig.add_axes([x0, 0.1, wd, 0.6])
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(order) - 0.4)
        ax.set_title(title, fontsize=11, loc="left", color=INK, fontweight="bold")
        for yy, c in zip(y, order):
            r = m.loc[c]
            if t < 2:
                ax.barh(yy, 1, color=GRID, height=0.62, alpha=0.5)
            if t == 0:
                p = max(parties, key=lambda q: r[f"p_majority_{q}"])
                v = r[f"p_majority_{p}"]
                ax.barh(yy, v, color=COL[p], height=0.62)
                ax.text(0.03, yy, f"{name(p)} {v:.0%}" if v >= 0.005 else "none", va="center", fontsize=9.5,
                        color="white" if v > 0.35 else INK, fontweight="bold")
            elif t == 1:
                v = r["p_bloc_ANC+DA"]
                ax.barh(yy, v / 2, color=COL["ANC"], height=0.62)
                ax.barh(yy, v / 2, left=v / 2, color=COL["DA"], height=0.62)
                ax.text(0.03, yy, f"{v:.0%}", va="center", fontsize=9.5, color="white" if v > 0.2 else INK,
                        fontweight="bold")
            else:
                best = [b for b in sorted(others, key=lambda b: -r[f"p_bloc_{b}"])[:2] if r[f"p_bloc_{b}"] >= 0.01]
                if not best:
                    ax.text(0.02, yy, "none above 1%", va="center", fontsize=8.5, color=MUTED)
                for j, b in enumerate(best):
                    v = r[f"p_bloc_{b}"]
                    yb = yy + (0.17 if j == 0 else -0.17) * (len(best) > 1)
                    ax.barh(yb, 0.42, color=GRID, height=0.28, alpha=0.5)
                    ax.barh(yb, v * 0.42, color="#5b6b7a" if j == 0 else "#9aa6b2", height=0.28)
                    ax.text(0.44, yb, f"{label(b)} {v:.0%}", va="center", fontsize=8.3, color=INK,
                            fontweight="bold" if j == 0 else "normal")
        ax.set_yticks(y, [METROS[c] for c in order] if t == 0 else [])
        ax.set_xticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
    fig.savefig(OUT / "05_coalitions.png")
    plt.close(fig)


def nowcast():
    r = pd.read_csv(OUTPUTS / "nowcast_replay_2021.csv")
    fig = frame("On election night, every count sharpens the call",
                "2021 replay: share of wards called correctly as voting districts report in random order")
    ax = fig.add_axes([0.1, 0.17, 0.84, 0.6])
    ax.plot(r.reported, r.accuracy, color="#3b7ddd", linewidth=2, marker="o", markersize=7)
    for x, v in zip(r.reported, r.accuracy):
        ax.text(x, v + 0.004, f"{v:.1%}", ha="center", fontsize=10.5)
    ax.set_xlim(-0.03, 0.8)
    ax.set_ylim(0.88, 0.97)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Voting districts reported")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    fig.savefig(OUT / "06_nowcast_replay.png")
    plt.close(fig)


def maps(w):
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson")
    g = g.merge(w, left_on="WardID", right_on="ward", how="left")
    g["fav"] = g.favourite.where(g.favourite.isin(list(COL)), "OTH")
    g = g.to_crs("ESRI:102022")  # Africa Albers equal area

    def base(title, subtitle):
        fig = plt.figure(figsize=(8, 4.5), dpi=200)
        fig.text(0.04, 0.93, title, fontsize=17, fontfamily="Georgia", va="top")
        fig.text(0.04, 0.855, subtitle, fontsize=10.5, va="top", color=MUTED)
        fig.text(0.04, 0.03, SOURCE, fontsize=7.5, color=MUTED)
        ax = fig.add_axes([0.02, 0.07, 0.62, 0.76])
        ax.set_axis_off()
        return fig, ax

    fig, ax = base("Who is favoured in each of South Africa's 4,485 wards",
                   "Colour: forecast favourite. Paler: less certain (under 75% chance)")
    sure = g.win_prob >= 0.75
    for p, c in COL.items():
        s = g[g.fav == p]
        s[sure[s.index]].plot(ax=ax, color=c, linewidth=0)
        s[~sure[s.index]].plot(ax=ax, color=c, alpha=0.45, linewidth=0)
    counts = w.favourite.where(w.favourite.isin(list(COL)), "OTH").value_counts()
    handles = [Patch(color=COL[p], label=f"{name(p)}  {counts.get(p, 0):,}") for p in COL if counts.get(p, 0)]
    fig.legend(handles=handles, loc="center left", bbox_to_anchor=(0.66, 0.47), frameon=False, fontsize=11,
               title="Wards favoured", title_fontsize=11)
    fig.savefig(OUT / "07_map_favourites.png")
    plt.close(fig)

    fig, ax = base(f"{(w.rating == 'Toss-up').sum()} toss-up wards will decide the coalitions",
                   "Wards where no party has more than a 60% chance (red) or 60-75% (orange)")
    g.plot(ax=ax, color="#e6e9e7", linewidth=0)
    g[g.rating == "Lean"].plot(ax=ax, color="#f0a35a", linewidth=0)
    g[g.rating == "Toss-up"].plot(ax=ax, color="#d6334a", linewidth=0)
    by_prov = w[w.rating == "Toss-up"].province.value_counts()
    txt = "\n".join(f"{p}  {n}" for p, n in by_prov.items())
    fig.text(0.68, 0.72, "Toss-ups by province", fontsize=11, fontweight="bold", va="top")
    fig.text(0.68, 0.66, txt, fontsize=10.5, va="top", linespacing=1.5)
    fig.savefig(OUT / "08_map_tossups.png")
    plt.close(fig)

    flips = w.flip
    fig, ax = base(f"{flips.sum():,} wards are forecast to change hands",
                   "Coloured by the new favourite. Grey: same favourite as the estimated 2021 winner")
    g.plot(ax=ax, color="#e6e9e7", linewidth=0)
    for p, c in COL.items():
        s = g[(g.fav == p) & g.flip.fillna(False).astype(bool)]
        if len(s):
            s.plot(ax=ax, color=c, linewidth=0)
    f = w[w.flip]
    top = (f.winner_2021_est.where(f.winner_2021_est.isin(list(COL)), "OTH").map(name) + " to "
           + f.favourite.where(f.favourite.isin(list(COL)), "OTH").map(name)).value_counts().head(6)
    fig.text(0.68, 0.72, "Biggest shifts", fontsize=11, fontweight="bold", va="top")
    fig.text(0.68, 0.66, "\n".join(f"{k}  {v}" for k, v in top.items()), fontsize=10.5, va="top", linespacing=1.5)
    fig.savefig(OUT / "09_map_flips.png")
    plt.close(fig)


# National Assembly results (IEC, official) and local-election PR-ballot shares. 1999 DA = Democratic Party;
# 1994 DA = Democratic Party. 2000 local: combined ballot (only total published); 2006 local: PR ballot;
# 2011-2021 local: PR ballot from the IEC voting-district results used by the model.
HISTORY = {
    "national": {1994: {"ANC": 62.65, "DA": 1.73, "IFP": 10.54},
                 1999: {"ANC": 66.35, "DA": 9.56, "IFP": 8.58},
                 2004: {"ANC": 69.69, "DA": 12.37, "IFP": 6.97},
                 2009: {"ANC": 65.90, "DA": 16.66, "IFP": 4.55},
                 2014: {"ANC": 62.15, "DA": 22.23, "IFP": 2.40, "EFF": 6.35},
                 2019: {"ANC": 57.50, "DA": 20.77, "IFP": 3.38, "EFF": 10.80},
                 2024: {"ANC": 40.18, "DA": 21.81, "IFP": 3.85, "EFF": 9.52, "MK": 14.58}},
    "local": {2000: {"ANC": 59.4, "DA": 22.1, "IFP": 9.1},
              2006: {"ANC": 65.7, "DA": 16.3, "IFP": 7.6},
              2011: {"ANC": 62.93, "DA": 24.08, "IFP": 3.56},
              2016: {"ANC": 54.48, "DA": 27.02, "IFP": 4.27, "EFF": 8.24},
              2021: {"ANC": 46.14, "DA": 21.75, "IFP": 5.85, "EFF": 10.46}},
}


def since_1994(summary):
    """Party vote shares in every national and local election since 1994, with the 2026 forecast."""
    fig = frame("From 69% to under 30%: the ANC since 1994",
                "Vote share (%). Solid line: national elections. Open circles: local elections (PR ballot).\n"
                "2026: forecast ward-ballot share, with 90% range. DA in 1994 and 1999 = Democratic Party")
    ax = fig.add_axes([0.07, 0.11, 0.80, 0.68])
    fc, rng = summary["national_share"], summary["national_interval_90"]
    # label positions, nudged apart so they don't overlap
    ys = sorted(((fc[p], p) for p in ["ANC", "DA", "IFP", "EFF", "MK"]))
    lab, prev = {}, -10.0
    for v, p in ys:
        prev = max(v, prev + 3.6)
        lab[p] = prev
    for p in ["ANC", "DA", "IFP", "EFF", "MK"]:
        nat = sorted((y, v[p]) for y, v in HISTORY["national"].items() if p in v)
        loc = sorted((y, v[p]) for y, v in HISTORY["local"].items() if p in v)
        ax.plot(*zip(*nat), color=COL[p], linewidth=2.2, marker="o", markersize=4, zorder=3)
        if loc:
            ax.plot(*zip(*loc), color=COL[p], linewidth=0, marker="o", markersize=5, markerfacecolor=BG,
                    markeredgewidth=1.4, zorder=3)
        last = max(nat + loc)
        ax.plot([last[0], 2026], [last[1], fc[p]], color=COL[p], linewidth=1.4, linestyle=(0, (2, 2)), zorder=2)
        ax.errorbar(2026, fc[p], yerr=[[fc[p] - rng[p]["p05"]], [rng[p]["p95"] - fc[p]]], color=COL[p], capsize=3,
                    linewidth=1.4, marker="D", markersize=5, zorder=4)
        ax.text(2026.8, lab[p], f"{name(p)} {fc[p]:.0f}", va="center", fontsize=10, color=COL[p], fontweight="bold")
    ax.axvspan(2025.2, 2026.6, color=GRID, alpha=0.45, zorder=0)
    ax.text(2025.9, 74, "2026\nforecast", ha="center", va="top", fontsize=8.5, color=MUTED)
    ax.set_xlim(1993, 2029.5)
    ax.set_ylim(0, 75)
    ax.set_xticks([1994, 1999, 2004, 2009, 2014, 2019, 2024])
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    clean(ax, grid_x=False)
    fig.savefig(OUT / "10_since_1994.png")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.load(open(OUTPUTS / "forecast_summary_2026.json"))
    bt = json.load(open(OUTPUTS / "backtest.json"))["results"]
    site = json.load(open(PROJECT / "docs" / "data" / "forecast.json"))
    m = pd.read_csv(OUTPUTS / "municipality_forecast_2026.csv").set_index("muni")
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str})
    blocs = json.load(open(PROJECT / "config" / "coalitions.json"))
    wards_by_party(site["national"])
    metro_seats(m)
    backtest(bt)
    kzn_byelections(summary)
    since_1994(summary)
    coalitions(m, blocs)
    nowcast()
    maps(w)
    print("visuals ->", OUT)


if __name__ == "__main__":
    main()
