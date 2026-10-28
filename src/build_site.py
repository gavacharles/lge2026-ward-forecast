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
    summary = json.load(open(OUTPUTS / "forecast_summary_2026.json"))
    polls = summary["polls"]
    bt = json.load(open(OUTPUTS / "backtest.json"))
    blocs = json.load(open(CONFIG / "coalitions.json"))
    nowcast_f = OUTPUTS / "nowcast_2026.csv"
    nowcast = pd.read_csv(nowcast_f, dtype={"ward": str}).set_index("ward") if nowcast_f.exists() else None

    wards = {}
    for r in w.itertuples(index=False):
        wards[r.ward] = {
            "m": r.muni, "n": int(r.ward_no), "f": r.favourite, "p": float(r.win_prob), "r": r.rating,
            "u": r.runner_up, "g": float(r.margin_pts), "w21": r.winner_2021_est,
            "s": [float(getattr(r, f"share_{p}")) for p in PARTIES],
            "c": float(r.history_coverage), "k": r.community if isinstance(r.community, str) else None,
        }
        if nowcast is not None and r.ward in nowcast.index:
            n = nowcast.loc[r.ward]
            wards[r.ward]["live"] = {"f": n.favourite, "p": float(n.win_prob), "rep": float(n.reported_share_of_votes),
                                     "s": [float(n[f"share_{p}"]) for p in PARTIES]}
    bloc_p = m.set_index("muni")
    munis = {}
    for r in m.itertuples(index=False):
        munis[r.muni] = {
            "name": nice_name(r.municipality), "prov": r.province, "wards": int(r.n_wards),
            "seats": int(r.council_seats), "largest": r.largest_party, "pl": float(r.p_largest),
            "maj": r.majority_party if not r.majority_party.startswith("Hung") else None, "pm": float(r.p_majority),
            "hung": float(r.p_hung),
            "s": [float(getattr(r, f"share_{p}")) for p in PARTIES],
            "st": [float(getattr(r, f"seats_{p}")) for p in PARTIES],
            "ew": [float(getattr(r, f"exp_wards_{p}")) for p in PARTIES if p != "OTH"],
            "bl": {b: float(bloc_p.at[r.muni, f"p_bloc_{b}"]) for b in blocs},
        }
    wt = w.expected_votes
    interval = summary.get("national_interval_90", {})
    national = []
    for p in PARTIES:
        fav = int((w.favourite == p).sum()) if p != "OTH" else int((~w.favourite.isin(PARTIES)).sum())
        exp = float(w[f"p_{p}"].sum() if p != "OTH" else w["p_LOCAL_TOP"].sum())
        national.append({"party": p, "share": round(float((w[f"share_{p}"] * wt).sum() / wt.sum()), 1),
                         "poll": polls["national"].get(p), "poll_sd": polls["national_sd_pts"].get(p),
                         "fav": fav, "exp": round(exp, 1),
                         "lo": interval.get(p, {}).get("p05"), "hi": interval.get(p, {}).get("p95")})
    hist_f = RAW.parent / "interim" / "vd_votes.parquet"
    hist = pd.read_parquet(hist_f)
    for e, key in [("lge2021_ward", "lge21"), ("npe2024", "npe24")]:
        t = hist[hist.election == e].groupby("party").votes.sum()
        t = t / t.sum() * 100
        for row in national:
            row[key] = round(float(t[row["party"]]), 1) if row["party"] in t else None

    out = {
        "generated": datetime.date.today().isoformat(),
        "election_date": "2026-11-04",
        "parties": PARTIES,
        "blocs": blocs,
        "ratings": w.rating.value_counts().to_dict(),
        "flips": int(w.flip.sum()),
        "national": national,
        "polls": {"as_of": polls["as_of"], "pollsters": polls["national_pollsters"],
                  "metros": {k: {"weight": v["weight"], "polls": v["polls"]} for k, v in polls["metros"].items()}},
        "byelections_used": summary["byelections_used"],
        "scenarios": summary.get("scenarios"),
        "kzn_region": {k: summary["kzn_region"][k] for k in ("byelections", "weight")} if summary.get("kzn_region") else None,
        "expected_correct": summary.get("expected_correct_calls"),
        "candidates": summary.get("used_candidate_list", False),
        "backtest": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in bt["results"].items()},
        "live": nowcast is not None,
        "munis": munis,
        "wards": wards,
    }
    json.dump(out, open(DOCS / "forecast.json", "w"), separators=(",", ":"), allow_nan=False)
    topo = RAW / "wards_topo.json"
    if topo.exists():
        shutil.copy(topo, DOCS / "wards.topo.json")
    print("forecast.json", round((DOCS / "forecast.json").stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
