"""Four charts for the pre-election story, in content/story/. Run after forecast_2026.py and whatif.py.

  s1  100 simulated elections: who finishes first in each metro
  s2  the range of ward totals across all 2,000 simulations
  s3  what if the polls are wrong by 3 points
  s4  how each ingredient changes the answer
  s5  ANC and DA in each metro, 2021 to 2026
  s6  map of the wards going from ANC to DA
Party colours match the site. Values are labelled directly, so nothing depends on colour alone.
"""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from paths import OUTPUTS, PROJECT

OUT = PROJECT / "content" / "story"
COL = {"ANC": "#22a05a", "DA": "#3b7ddd", "MK": "#8a5cc2", "EFF": "#d6334a", "IFP": "#e0a21b", "PA": "#c45a9b",
       "FFP": "#f07f2a", "ASA": "#2fb3a6", "OTH": "#8a8f98"}
NAME = {"FFP": "FF+", "ASA": "ActionSA", "OTH": "Local", "LOCAL": "Local"}
METROS = {"JHB": "Johannesburg", "TSH": "Tshwane", "EKU": "Ekurhuleni", "CPT": "Cape Town", "ETH": "eThekwini",
          "NMA": "Nelson Mandela Bay", "BUF": "Buffalo City", "MAN": "Mangaung"}
BG, INK, MUTED, GRID = "#ffffff", "#17201c", "#5b6660", "#e3e6e3"
CREDIT = "Credit: Gava Charles · LGE 2026 Ward Forecast, a statistical model, not a poll · gavacharles.github.io/lge2026-ward-forecast"
plt.rcParams.update({"font.family": "Avenir Next", "font.size": 12, "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": INK, "axes.edgecolor": GRID, "figure.facecolor": BG,
                     "axes.facecolor": BG, "savefig.facecolor": BG})


def frame(title, sub, size=(10, 6.25)):
    fig = plt.figure(figsize=size, dpi=160)
    h = size[1]
    fig.text(0.035, 1 - 0.3 / h, title, fontsize=20, fontfamily="Georgia", va="top")
    fig.text(0.035, 1 - 0.78 / h, sub, fontsize=12, color=MUTED, va="top", linespacing=1.35)
    fig.text(0.035, 0.14 / h, CREDIT, fontsize=8.5, color=MUTED)
    return fig


def quiet(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)


def round_to_100(share):
    """Largest-remainder rounding, so each metro has exactly 100 dots."""
    raw = share * 100
    n = np.floor(raw).astype(int)
    for k in (raw - n).sort_values(ascending=False).index[: 100 - n.sum()]:
        n[k] += 1
    return n[n > 0].sort_values(ascending=False)


def s1_hundred():
    L = pd.read_csv(OUTPUTS / "sim_metro_largest_2026.csv")
    m = pd.read_csv(OUTPUTS / "municipality_forecast_2026.csv").set_index("muni")
    fig = frame("In 100 simulated elections, who finishes first?",
                "Each dot is one simulated election, coloured by the party with the most council seats. "
                "Below: how often a party\nwins a majority on its own. Most dots agreeing does not mean that party governs.",
                (10, 7.6))
    handles = [plt.Rectangle((0, 0), 1, 1, color=COL[p]) for p in ["DA", "ANC", "MK", "ASA", "EFF"]]
    fig.legend(handles, ["DA", "ANC", "MK", "ActionSA", "EFF"], ncol=5, loc="upper left", bbox_to_anchor=(0.03, 0.84),
               frameon=False, fontsize=10.5, handlelength=1, columnspacing=1.4)
    for i, (c, label) in enumerate(METROS.items()):
        x0 = 0.035 + (i % 4) * 0.2425
        y0 = 0.5 - (i // 4) * 0.38
        ax = fig.add_axes([x0, y0, 0.19, 0.25])
        n = round_to_100(L[c].value_counts(normalize=True))
        cols = [COL[p] for p, k in n.items() for _ in range(k)]
        gx, gy = np.meshgrid(np.arange(10), np.arange(10)[::-1])
        ax.scatter(gx.ravel(), gy.ravel(), s=62, c=cols, linewidths=0)
        ax.set_xlim(-0.6, 9.6)
        ax.set_ylim(-0.6, 9.6)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.text(x0, y0 + 0.258, label, fontsize=13, fontweight="bold", va="bottom")
        top = " · ".join(f"{NAME.get(p, p)} {k}" for p, k in n.items())
        fig.text(x0, y0 - 0.008, top, fontsize=10, va="top")
        maj = (1 - m.at[c, "p_hung"]) * 100
        fig.text(x0, y0 - 0.04, f"Majority: {maj:.0f} in 100" if maj >= 0.5 else "Majority: under 1 in 100", fontsize=10,
                 va="top", color=MUTED)
    fig.savefig(OUT / "s1_100_simulated_elections.png")
    plt.close(fig)


def s2_range():
    T = pd.read_csv(OUTPUTS / "sim_ward_totals_2026.csv")
    half = 2243
    fig = frame("The ANC could win half the wards on 29% of the vote",
                "Wards won across 2,000 simulations. The ANC wins more than half of all wards in "
                f"{(T.ANC >= half).mean():.0%} of them. "
                "The DA never out-wins\nit. "
                f"MK beats the IFP in {(T.MK > T.IFP).mean():.0%}, even though the IFP is favoured in more wards.")
    parties = ["ANC", "DA", "MK", "IFP"]
    bins = np.arange(0, 3001, 40)
    for r, p in enumerate(parties):
        ax = fig.add_axes([0.13, 0.625 - r * 0.172, 0.62, 0.15])
        ax.hist(T[p], bins=bins, color=COL[p], rwidth=0.88)
        ax.set_xlim(0, 3000)
        ax.set_yticks([])
        ax.axvline(half, color=INK, linewidth=1, linestyle=(0, (3, 3)))
        quiet(ax)
        ax.spines["bottom"].set_visible(True)
        ax.set_xticks(range(0, 3001, 500) if r == 3 else [])
        if r == 3:
            ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
            ax.set_xlabel("Wards won")
        if r == 0:
            ax.text(half - 700, ax.get_ylim()[1] * 0.92, "Half of all wards", ha="right", va="top", fontsize=10.5)
            ax.annotate("", xy=(half - 15, ax.get_ylim()[1] * 0.85), xytext=(half - 690, ax.get_ylim()[1] * 0.85),
                        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
        lo, md, hi = np.percentile(T[p], [5, 50, 95])
        fig.text(0.035, 0.625 - r * 0.172 + 0.05, NAME.get(p, p), fontsize=14, fontweight="bold")
        fig.text(0.77, 0.625 - r * 0.172 + 0.085, f"Median {md:,.0f}", fontsize=12, fontweight="bold")
        fig.text(0.77, 0.625 - r * 0.172 + 0.045, f"9 in 10 runs: {lo:,.0f} to {hi:,.0f}", fontsize=11, color=MUTED)
    fig.savefig(OUT / "s2_range_of_outcomes.png")
    plt.close(fig)


def s3_whatif():
    W = json.load(open(OUTPUTS / "whatif_2026.json"))["whatif"]
    rows = ["ANC +3", "ANC -3", "As published", "DA +3", "DA -3"]
    label = {"ANC +3": "Polls underrate ANC by 3", "ANC -3": "Polls overrate ANC by 3", "As published": "As published",
             "DA +3": "Polls underrate DA by 3", "DA -3": "Polls overrate DA by 3"}
    base = W["As published"]
    fig = frame("If the polls miss by 3 points, the metros stay hung",
                "Wards favoured if national and metro polls are off by 3 points for one party. Each panel spans 800 wards, "
                "so the\nmovements compare directly. The dashed line is the published forecast. KZN by-election levels are held.")
    parties = ["ANC", "DA", "MK", "IFP"]
    y = np.arange(len(rows))[::-1]
    for j, p in enumerate(parties):
        ax = fig.add_axes([0.235 + j * 0.122, 0.1, 0.108, 0.63])
        b = base["wards_favoured"][p]
        ax.set_xlim(b - 400, b + 400)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.axvline(b, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
        for yy, r in zip(y, rows):
            v = W[r]["wards_favoured"][p]
            ax.plot([b, v], [yy, yy], color=COL[p], linewidth=2, solid_capstyle="round")
            ax.scatter([v], [yy], s=70, color=COL[p], zorder=3, edgecolor=BG, linewidth=1.5)
            ax.text(b, yy + 0.27, f"{v:,}", ha="center", va="center", fontsize=10.5, fontweight="bold" if r == "As published" else "normal",
                    bbox=dict(facecolor=BG, edgecolor="none", pad=1.5), zorder=4)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(NAME.get(p, p), fontsize=13, fontweight="bold", loc="center")
        quiet(ax)
    for yy, r in zip(y, rows):
        yf = 0.1 + 0.63 * (yy + 0.6) / len(rows)
        fig.text(0.035, yf, label[r], fontsize=11.5, va="center", fontweight="bold" if r == "As published" else "normal")
        changes = [METROS[c] for c, v in W[r]["metros"].items() if v["largest"] != base["metros"][c]["largest"]]
        msg = "First place changes: " + ", ".join(changes) if changes else "No metro changes first place"
        hung = sum(v["p_hung"] > 0.5 for v in W[r]["metros"].values())
        fig.text(0.735, yf + 0.018, f"{hung} of 8 metros hung", fontsize=10.5, va="center", fontweight="bold")
        fig.text(0.735, yf - 0.022, msg if r != "As published" else "Baseline", fontsize=9.5, va="center", color=MUTED)
    fig.savefig(OUT / "s3_if_the_polls_are_wrong.png")
    plt.close(fig)


def s4_ingredients():
    I = json.load(open(OUTPUTS / "whatif_2026.json"))["ingredients"]
    order = list(I)
    label = {order[0]: "Past results only", order[1]: "+ polls", order[2]: "+ by-election swing\nand candidate lists",
             order[3]: "+ KZN by-elections\nas a regional poll\n(published)"}
    fig = frame("Polls shrink the IFP. KwaZulu-Natal's by-elections bring it back",
                "Wards favoured as each ingredient is added. Past results alone give the IFP 334, close to the 328 it won on "
                "the new\nboundaries. National polls cut it to 144. MK moves the other way.")
    ax = fig.add_axes([0.21, 0.1, 0.75, 0.68])
    parties = ["ANC", "DA", "MK", "IFP", "EFF"]
    y = np.arange(len(order))[::-1]
    for yy, k in zip(y, order):
        left = 0
        wf = I[k]["wards_favoured"]
        for p in parties + ["rest"]:
            v = 4485 - sum(wf.values()) if p == "rest" else wf[p]
            ax.barh(yy, v - 12, left=left, color=COL.get(p, COL["OTH"]), height=0.58)
            if v >= 130:
                ax.text(left + (v - 12) / 2, yy, f"{NAME.get(p, p)} {v:,}" if v >= 350 else f"{v:,}", ha="center", va="center",
                        fontsize=10.5 if v >= 350 else 9.5, fontweight="bold", color=INK if p == "IFP" else "white")
            left += v
    ax.set_yticks(y, [label[k] for k in order], fontsize=11.5)
    ax.set_xlim(0, 4485)
    ax.set_xticks([])
    quiet(ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COL[p]) for p in parties] + [plt.Rectangle((0, 0), 1, 1, color=COL["OTH"])]
    ax.legend(handles, [NAME.get(p, p) for p in parties] + ["All others"], ncol=6, loc="lower center",
              bbox_to_anchor=(0.45, -0.1), frameon=False, fontsize=10.5, handlelength=1, columnspacing=1.2)
    fig.savefig(OUT / "s4_ingredients.png")
    plt.close(fig)


def s5_metro_slopes():
    """ANC and DA vote share per metro, 2021 result to 2026 forecast, with the 2026 poll average marked."""
    import polls as POLLS
    from paths import INTERIM
    v = pd.read_parquet(INTERIM / "vd_votes.parquet")
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    e = "lge2021_ward"
    x = v[v.election == e].merge(meta[meta.election == e][["vd", "muni"]], on="vd")
    t21 = x.pivot_table(index="muni", columns="party", values="votes", aggfunc="sum")
    t21 = t21.div(t21.sum(axis=1), axis=0) * 100
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv")
    polls = POLLS.aggregate(json.load(open(OUTPUTS / "forecast_summary_2026.json"))["as_of"])["metros"]
    fig = frame("The ANC falls in all eight metros. The DA rises in six",
                "Vote share (%), 2021 ward-ballot result to 2026 forecast. Open circles: 2026 poll average, before about 12% is set\n"
                "aside for independents and local parties. Polls have Ekurhuleni and Nelson Mandela Bay closer than the forecast.", (10, 7.4))
    for i, (c, label) in enumerate(METROS.items()):
        ax = fig.add_axes([0.08 + (i % 4) * 0.2375, 0.44 - (i // 4) * 0.37, 0.155, 0.255])
        d = w[w.muni == c]
        now = {p: float((d[f"share_{p}"] * d.expected_votes).sum() / d.expected_votes.sum()) for p in ["ANC", "DA"]}
        for p in ["ANC", "DA"]:
            then = float(t21.at[c, p])
            ax.plot([0, 1], [then, now[p]], color=COL[p], linewidth=2.5, solid_capstyle="round")
            ax.scatter([0, 1], [then, now[p]], s=52, color=COL[p], zorder=3, edgecolor=BG, linewidth=1.2)
            q = polls[c]["shares"].get(p)
            if q is not None:
                ax.scatter([1.3], [q], s=48, facecolor=BG, edgecolor=COL[p], linewidth=1.8, zorder=3)
        a0, d0 = float(t21.at[c, "ANC"]), float(t21.at[c, "DA"])
        lift = 2.4 if abs(a0 - d0) < 5 else 0
        ax.text(-0.09, a0 + (lift if a0 >= d0 else -lift), f"ANC {a0:.0f}", ha="right", va="center", fontsize=10)
        ax.text(-0.09, d0 + (lift if d0 > a0 else -lift), f"DA {d0:.0f}", ha="right", va="center", fontsize=10)
        lift = 2.4 if abs(now["ANC"] - now["DA"]) < 5 else 0
        ax.text(1.07, now["ANC"] + (lift if now["ANC"] >= now["DA"] else -lift), f"{now['ANC']:.0f}", ha="left", va="center", fontsize=10, fontweight="bold")
        ax.text(1.07, now["DA"] + (lift if now["DA"] > now["ANC"] else -lift), f"{now['DA']:.0f}", ha="left", va="center", fontsize=10, fontweight="bold")
        ax.set_xlim(-0.05, 1.42)
        ax.set_ylim(0, 65)
        ax.set_xticks([0, 1], ["2021", "2026"], fontsize=10)
        ax.set_yticks([])
        quiet(ax)
        ax.spines["bottom"].set_visible(True)
        fig.text(0.035 + (i % 4) * 0.2375, 0.705 - (i // 4) * 0.37, label, fontsize=12.5, fontweight="bold")
    handles = [plt.Line2D([], [], color=COL["ANC"], marker="o", linewidth=2.5), plt.Line2D([], [], color=COL["DA"], marker="o", linewidth=2.5),
               plt.Line2D([], [], color=MUTED, marker="o", markerfacecolor=BG, linewidth=0)]
    fig.legend(handles, ["ANC", "DA", "2026 poll average"], ncol=3, loc="upper left", bbox_to_anchor=(0.03, 0.8), frameon=False, fontsize=10.5)
    fig.savefig(OUT / "s5_metro_slopes.png")
    plt.close(fig)


def s6_anc_to_da_map():
    """Wards forecast to go from ANC to DA since 2021."""
    import geopandas as gpd
    from paths import RAW
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    g = gpd.read_file(RAW / "mdb_wards_2026.geojson").set_index("WardID").to_crs("ESRI:102022")
    g["geometry"] = g.geometry.simplify(500)
    f = w[(w.winner_2021_est == "ANC") & (w.favourite == "DA")]
    back = int(((w.winner_2021_est == "DA") & (w.favourite == "ANC")).sum())
    votes = f.expected_votes.sum() / w.expected_votes.sum()
    toss = f.rating == "Toss-up"
    fig = frame(f"ANC to DA: {len(f)} wards. DA to ANC: {back}",
                f"Wards forecast to change from ANC to DA since 2021. They fill much of the map but hold only about {votes:.0%} of expected\n"
                "votes, because big rural wards hold few voters. 2021 winners are estimates on the 2026 boundaries.")
    ax = fig.add_axes([0.02, 0.05, 0.66, 0.73])
    g.plot(ax=ax, color="#e9ecea", edgecolor="#ffffff", linewidth=0.1)
    g.loc[f.index[~toss]].plot(ax=ax, color=COL["DA"], edgecolor="#ffffff", linewidth=0.1)
    g.loc[f.index[toss]].plot(ax=ax, color="#a9c6f2", edgecolor="#ffffff", linewidth=0.1)
    ax.axis("off")
    x = 0.7
    handles = [plt.Rectangle((0, 0), 1, 1, color=COL["DA"]), plt.Rectangle((0, 0), 1, 1, color="#a9c6f2"), plt.Rectangle((0, 0), 1, 1, color="#e9ecea")]
    fig.legend(handles, [f"DA favoured, chance 60%+ ({(~toss).sum()})", f"Toss-up, chance under 60% ({toss.sum()})", "All other wards"],
               loc="upper left", bbox_to_anchor=(x - 0.01, 0.76), frameon=False, fontsize=10.5, handlelength=1)
    fig.text(x, 0.53, "Where they are", fontsize=12.5, fontweight="bold")
    for i, (prov, n) in enumerate(f.province.value_counts().items()):
        fig.text(x, 0.49 - i * 0.04, prov, fontsize=11)
        fig.text(x + 0.25, 0.49 - i * 0.04, f"{n}", fontsize=11, ha="right", fontweight="bold")
    fig.savefig(OUT / "s6_anc_to_da_map.png")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s1_hundred()
    s2_range()
    s3_whatif()
    s4_ingredients()
    s5_metro_slopes()
    s6_anc_to_da_map()
    print("story charts ->", OUT)


if __name__ == "__main__":
    main()
