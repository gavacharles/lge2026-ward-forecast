"""Export forecast outputs to docs/ (the GitHub Pages site).

docs/data/forecast.json  compact ward/municipality/national tables
docs/data/wards.topo.json  MDB 2026 ward boundaries (made by fetch_boundaries.py + topojson CLI)
"""
import datetime
import json
import shutil

import pandas as pd

from paths import CONFIG, OUTPUTS, PROJECT, RAW

PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA", "OTH"]
DOCS = PROJECT / "docs" / "data"


def nice_name(s):
    name = s.split(" - ", 1)[-1].title()
    for w in ("Of", "And", "The"):
        name = name.replace(f" {w} ", f" {w.lower()} ")
    return name


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    w = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str})
    m = pd.read_csv(OUTPUTS / "municipality_forecast_2026.csv")
    polls = json.load(open(CONFIG / "polls_2026.json"))
    bt = json.load(open(OUTPUTS / "backtest_2021.json"))["metrics"]

    wards = {}
    for r in w.itertuples(index=False):
        wards[r.ward] = {
            "m": r.muni, "n": int(r.ward_no), "f": r.favourite, "p": float(r.win_prob), "r": r.rating,
            "u": r.runner_up, "g": float(r.margin_pts), "w21": r.winner_2021_est,
            "s": [float(getattr(r, f"share_{p}")) for p in PARTIES],
            "c": float(r.history_coverage),
        }
    munis = {}
    for r in m.itertuples(index=False):
        munis[r.muni] = {
            "name": nice_name(r.municipality), "prov": r.province, "wards": int(r.n_wards),
            "largest": r.largest_party, "pl": float(r.p_largest),
            "maj": r.majority_party if not r.majority_party.startswith("Hung") else None, "pm": float(r.p_majority),
            "s": [float(getattr(r, f"share_{p}")) for p in PARTIES],
            "ew": [float(getattr(r, f"exp_wards_{p}")) for p in PARTIES if p != "OTH"],
        }
    wt = w.expected_votes
    national = []
    for p in PARTIES:
        fav = int((w.favourite == p).sum()) if p != "OTH" else int((~w.favourite.isin(PARTIES)).sum())
        exp = float(w[f"p_{p}"].sum() if p != "OTH" else w["p_LOCAL_TOP"].sum())
        national.append({"party": p, "share": round(float((w[f"share_{p}"] * wt).sum() / wt.sum()), 1),
                         "poll": polls["national"].get(p), "fav": fav, "exp": round(exp, 1)})
    # history for the share table (from the summary built for the dashboard, recomputed here)
    hist = pd.read_parquet(RAW.parent / "interim" / "vd_votes.parquet")
    for e, key in [("lge2021_ward", "lge21"), ("npe2024", "npe24")]:
        t = hist[hist.election == e].groupby("party").votes.sum()
        t = t / t.sum() * 100
        for row in national:
            row[key] = round(float(t[row["party"]]), 1) if row["party"] in t else None

    out = {
        "generated": datetime.date.today().isoformat(),
        "election_date": "2026-11-04",
        "parties": PARTIES,
        "ratings": w.rating.value_counts().to_dict(),
        "flips": int(w.flip.sum()),
        "national": national,
        "metro_polls": {k: {"weight": v["weight"], "polls": v["polls"]} for k, v in polls["metros"].items()},
        "backtest": {k: round(v, 4) for k, v in bt.items()},
        "munis": munis,
        "wards": wards,
    }
    json.dump(out, open(DOCS / "forecast.json", "w"), separators=(",", ":"))
    shutil.copy(RAW / "wards_topo.json", DOCS / "wards.topo.json")
    print("forecast.json", round((DOCS / "forecast.json").stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
