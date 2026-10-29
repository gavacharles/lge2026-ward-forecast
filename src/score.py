"""Score a frozen forecast against the final result.

  python src/score.py 2026       frozen/ forecast vs the IEC's final 2026 results (downloaded to raw/lge2026/)
  python src/score.py test2021   the 2021 backtest forecast vs the 2021 result (checks this scorer: its ward
                                 accuracy must match outputs/backtest.json)

Scores, each against simple baselines where they exist:
  ward winners      share called; carry forward the previous local winner; carry forward the national leader
  probabilities     Brier score and log loss of the actual winner's probability; calibration by bins
  vote shares       national (and whether inside the 90% range), by province, by ward
  councils          largest party, majority or hung, metro seats, which coalitions have a majority
  KwaZulu-Natal     by-election-led (published) vs poll-led scenario (2026 only)
Writes outputs/scorecard_<label>.md and .json.
"""
import json
import sys

import numpy as np
import pandas as pd

import model as M
from paths import INTERIM, OUTPUTS, PROJECT, RAW

PARTIES = M.MAJORS
COLS = PARTIES + ["OTH"]
METROS = ["BUF", "NMA", "MAN", "EKU", "JHB", "TSH", "ETH", "CPT"]
PROV_NAMES = {"EC": "Eastern Cape", "FS": "Free State", "GT": "Gauteng", "KZN": "KwaZulu-Natal", "LIM": "Limpopo",
              "MP": "Mpumalanga", "NW": "North West", "NC": "Northern Cape", "WC": "Western Cape"}
FROZEN = PROJECT / "frozen"


# ---------- actual results: one row per (ballot, vd, ward, muni, label) ----------

def results_2026():
    """IEC final results (same files as the live feed, complete once results are declared)."""
    import build_data
    from nowcast import LIVE_URL, PROVS
    import requests
    folder = RAW / "lge2026"
    folder.mkdir(parents=True, exist_ok=True)
    for pr in PROVS:
        f = folder / f"{pr}.csv"
        if not f.exists():
            r = requests.get(LIVE_URL.format(pr=pr), headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
            r.raise_for_status()
            f.write_bytes(r.content)
    d = build_data.load_lge("lge2026", "lge2026")
    d["votes"] = pd.to_numeric(d.votes, errors="coerce").fillna(0)
    return pd.DataFrame({"ballot": d.election.str.split("_").str[1], "vd": d.vd, "ward": d.ward, "muni": d.muni,
                         "label": d.party.where(d.party.isin(PARTIES), d.party_name), "votes": d.votes})


def results_interim(prefix):
    """A past local election from the processed tables (OTH split back into named parties)."""
    votes, other = M.load()
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    rows = []
    for ballot in ("ward", "pr"):
        e = f"{prefix}_{ballot}"
        geo = meta[meta.election == e][["vd", "ward", "muni"]]
        v = votes[(votes.election == e) & (votes.party != "OTH")].rename(columns={"party": "label"})
        o = other[other.election == e].rename(columns={"party_name": "label"})
        both = pd.concat([v[["vd", "label", "votes"]], o[["vd", "label", "votes"]]]).merge(geo, on="vd")
        rows.append(both.assign(ballot=ballot))
    return pd.concat(rows, ignore_index=True)


def actual_tables(R, wards_fc, munis_fc):
    """Ward winners and shares, municipal shares and seats, national shares, from result rows."""
    w = R[R.ballot == "ward"]
    by = w.groupby(["ward", "label"]).votes.sum()
    winner = by.groupby(level=0).idxmax().map(lambda t: t[1])
    code = w.label.where(w.label.isin(PARTIES), "OTH")
    ws = w.assign(code=code).pivot_table(index="ward", columns="code", values="votes", aggfunc="sum", fill_value=0)
    ws = ws.reindex(columns=COLS, fill_value=0)
    ward_votes = ws.sum(axis=1)
    ws = ws.div(ward_votes.replace(0, np.nan), axis=0)
    nat = ws.mul(ward_votes, axis=0).sum() / ward_votes.sum()
    # councils: ward + PR votes combined, seats by the same formula the forecast uses
    from seats import allocate
    allc = R.assign(code=R.label.where(R.label.isin(PARTIES), "OTH"))
    ms = allc.pivot_table(index="muni", columns="code", values="votes", aggfunc="sum", fill_value=0)
    ms = ms.reindex(columns=COLS, fill_value=0)
    ms = ms.div(ms.sum(axis=1), axis=0)
    wmuni = w.drop_duplicates("ward").set_index("ward").muni
    seats = {}
    for m in ms.index.intersection(munis_fc.index):
        wins = winner[wmuni[wmuni == m].index.intersection(winner.index)]
        ww = np.array([(wins == p).sum() for p in COLS])
        seats[m] = allocate(ms.loc[m].values, ww, int(munis_fc.at[m, "council_seats"]))
    seats = pd.DataFrame(seats, index=COLS).T
    return dict(winner=winner, shares=ws, votes=ward_votes, national=nat, muni_shares=ms, seats=seats)


# ---------- forecasts in a common shape ----------

def forecast_2026():
    if not (FROZEN / "manifest.json").exists():
        sys.exit("No frozen forecast: run `python src/freeze.py` before results come in.")
    w = pd.read_csv(FROZEN / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    m = pd.read_csv(FROZEN / "municipality_forecast_2026.csv").set_index("muni")
    s = json.load(open(FROZEN / "forecast_summary_2026.json"))
    alt_f = FROZEN / "ward_forecast_2026_poll_scenario.csv"
    alt = pd.read_csv(alt_f, dtype={"ward": str}).set_index("ward") if alt_f.exists() else None
    votes, _ = M.load()
    map26 = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str)
    X_npe, _, _ = M.ward_table(votes, "npe2024", map26, PARTIES)
    w["base_prev_local"] = w.winner_2021_est
    w["base_national"] = X_npe[PARTIES].idxmax(axis=1).reindex(w.index)
    w["local_top"] = w.local_top_party_2021
    return w, m, s, alt


def forecast_test2021():
    """Rebuild the 2021 backtest forecast (same settings as outputs/backtest.json) in the 2026 file shape."""
    import backtest as B
    votes, other = M.load()
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    params = json.load(open(OUTPUTS / "backtest.json"))["params"]
    blocs = json.load(open(PROJECT / "config" / "coalitions.json"))
    c = B.prepare("2021", B.CYCLES["2021"], votes, other, meta)
    S = B.forecast_variant(c, params["alpha"], params["k_shrink"])
    muni = c["wards"].muni
    seats_n = muni.groupby(muni).size() * 2
    probs, ms = M.simulate(S, c["weight"], muni, c["local_prev"], 0.0, params["sd_muni"], params["sd_ward"], n=400,
                           turnout_beta=M.turnout_betas(c["X_lge"], c["turnout"], c["weight"]),
                           sd_turnout=params["sd_turnout"], council_seats=seats_n, blocs=blocs, seat_sims=200)
    named = probs.rename(columns={"LOCAL": "LOCAL_TOP"})
    local = c["local_prev"].local_name.reindex(S.index).fillna("OTHER")
    fav = named.idxmax(axis=1)
    w = pd.DataFrame(index=S.index)
    w["muni"] = muni
    w["province"] = c["prov"].map(PROV_NAMES)
    w["favourite"] = fav.where(fav != "LOCAL_TOP", local)
    w["win_prob"] = named.max(axis=1)
    for col in named.columns:
        w[f"p_{col}"] = named[col]
    for p in S.columns:
        w[f"share_{p}"] = S[p] * 100
    w["expected_votes"] = c["weight"]
    w["local_top"] = local
    w["base_prev_local"] = M.winners(c["X_lge"], c["local_prev"]).winner
    w["base_national"] = c["X_npe"][c["cfg"]["parties"]].idxmax(axis=1)
    m = pd.DataFrame(index=ms["seats"].index)
    for p in S.columns:
        m[f"seats_{p}"] = ms["seats"][p]
        m[f"share_{p}"] = ms["share"][p] * 100
    m["council_seats"] = seats_n
    m["largest_party"] = ms["p_largest_seats"].idxmax(axis=1)
    m["p_largest"] = ms["p_largest_seats"].max(axis=1)
    maj = ms["p_majority_seats"]
    m["p_hung"] = (1 - maj.sum(axis=1)).clip(0, 1)
    for b in blocs:
        m[f"p_bloc_{b}"] = ms["p_bloc_majority"][b]
    inter = ms["national_interval"]
    s = {"national_share": (S.mul(c["weight"], axis=0).sum() / c["weight"].sum() * 100).reindex(COLS, fill_value=0).to_dict(),
         "national_interval_90": (inter * 100).to_dict()}
    for p in COLS:  # parties that did not stand in 2021 (MK, ActionSA in most places) get zeros
        for frame_, col in ((w, f"share_{p}"), (w, f"p_{p}"), (m, f"seats_{p}"), (m, f"share_{p}")):
            if col not in frame_:
                frame_[col] = 0.0
    return w, m, s, None


# ---------- scoring ----------

def p_of_actual(w, actual):
    out = []
    for ward, lab in actual.items():
        r = w.loc[ward]
        if f"p_{lab}" in r.index:
            out.append(r[f"p_{lab}"])
        elif lab == r.local_top:
            out.append(r.get("p_LOCAL_TOP", 0.0))
        else:
            out.append(0.0)
    return np.array(out, float)


def score(w, m, s, alt, A, label):
    blocs = json.load(open(PROJECT / "config" / "coalitions.json"))
    idx = w.index.intersection(A["winner"].index)
    w, act = w.loc[idx], A["winner"].loc[idx]
    hit = w.favourite == act
    p_act = p_of_actual(w, act)
    res = {"label": label, "wards_scored": int(len(idx)), "wards_in_forecast": int(len(w)),
           "ward_accuracy": float(hit.mean()),
           "baseline_prev_local": float((w.base_prev_local == act).mean()),
           "baseline_national_leader": float((w.base_national == act).mean()),
           "expected_accuracy": float(w.win_prob.mean()),
           "brier": float(((1 - p_act) ** 2).mean()),
           "log_loss": float(-np.log(np.clip(p_act, 1e-3, 1)).mean())}
    bins = pd.cut(w.win_prob, [0, .5, .6, .7, .8, .9, .95, 1.0001])
    cal = pd.DataFrame({"pred": w.win_prob, "hit": hit}).groupby(bins, observed=True).agg(
        wards=("hit", "size"), forecast=("pred", "mean"), won=("hit", "mean"))
    res["calibration"] = {str(k): {kk: round(float(vv), 3) for kk, vv in v.items()} for k, v in cal.iterrows()}
    res["by_rating"] = {r: float(hit[w.rating == r].mean()) for r in ["Safe", "Likely", "Lean", "Toss-up"]
                        if "rating" in w and (w.rating == r).any()}
    # vote shares
    nat_fc, nat_act = s["national_share"], A["national"] * 100
    iv = s.get("national_interval_90", {})
    res["national"] = {p: {"forecast": round(nat_fc[p], 1), "actual": round(float(nat_act[p]), 1),
                           "error": round(nat_fc[p] - float(nat_act[p]), 1),
                           "in_90": (iv[p]["p05"] <= nat_act[p] <= iv[p]["p95"]) if p in iv else None} for p in COLS}
    sh_fc = w[[f"share_{p}" for p in COLS]].set_axis(COLS, axis=1) / 100
    sh_act = A["shares"].reindex(idx)[COLS]
    res["ward_share_mae_pts"] = {p: round(float((sh_fc[p] - sh_act[p]).abs().mean() * 100), 1) for p in COLS}
    wt = w.expected_votes
    pv = {}
    for prov, g in w.groupby("province"):
        f = sh_fc.loc[g.index].mul(wt[g.index], axis=0).sum() / wt[g.index].sum()
        av = A["votes"].reindex(g.index).fillna(0)
        a = sh_act.loc[g.index].mul(av, axis=0).sum() / av.sum()
        err = ((f - a)[PARTIES] * 100).round(1)
        big = err.abs().idxmax()
        pv[prov] = {"biggest_miss": [big, float(err[big])],
                    **{p: [round(float(f[p] * 100), 1), round(float(a[p] * 100), 1)] for p in ["ANC", "DA", "MK", "IFP", "EFF"]}}
    res["provinces"] = pv
    # councils
    mi = m.index.intersection(A["seats"].index)
    seats_act = A["seats"].loc[mi]
    half = m.loc[mi, "council_seats"] / 2
    largest_act = seats_act.idxmax(axis=1)
    hung_act = ~(seats_act.max(axis=1) > half)
    res["councils"] = {"scored": int(len(mi)),
                       "largest_party_correct": float((m.loc[mi, "largest_party"] == largest_act).mean()),
                       "hung_status_correct": float(((m.loc[mi, "p_hung"] > 0.5) == hung_act).mean())}
    metros = {}
    for c in [x for x in METROS if x in mi]:
        sa = seats_act.loc[c]
        metros[c] = {"largest": [m.at[c, "largest_party"], largest_act[c]], "hung": [round(float(m.at[c, "p_hung"]), 2), bool(hung_act[c])],
                     "seats": {p: [round(float(m.at[c, f"seats_{p}"]), 1), int(sa[p])] for p in ["ANC", "DA", "MK", "EFF", "IFP"]},
                     "blocs": {b: [round(float(m.at[c, f"p_bloc_{b}"]), 2), bool(sa[[p for p in ps if p in COLS]].sum() > half[c])]
                               for b, ps in blocs.items() if f"p_bloc_{b}" in m}}
    res["metros"] = metros
    # KZN scenarios
    if alt is not None:
        k = w.province == "KwaZulu-Natal"
        reg = k & (w.muni != "ETH")
        alt_hit = alt.reindex(idx).favourite == act
        res["kzn"] = {"published_byelection_led": float(hit[k].mean()), "poll_led": float(alt_hit[k].mean()),
                      "outside_ethekwini": {"published_byelection_led": float(hit[reg].mean()),
                                            "poll_led": float(alt_hit[reg].mean())}}
    return res


def report(r):
    pct = lambda v: f"{v:.1%}"
    L = [f"# Scorecard: {r['label']}", "",
         f"Wards scored: {r['wards_scored']:,} of {r['wards_in_forecast']:,}.", "",
         "## Ward winners", "", "| Method | Called correctly |", "|---|---|",
         f"| **This forecast** | **{pct(r['ward_accuracy'])}** |",
         f"| Carry forward the previous local winner | {pct(r['baseline_prev_local'])} |",
         f"| Carry forward the last national-ballot leader | {pct(r['baseline_national_leader'])} |",
         f"| What the forecast expected (average favourite chance) | {pct(r['expected_accuracy'])} |", "",
         f"Brier score {r['brier']:.3f} · log loss {r['log_loss']:.3f} (lower is better).", ""]
    if r.get("by_rating"):
        L += ["By rating: " + " · ".join(f"{k} {pct(v)}" for k, v in r["by_rating"].items()), ""]
    L += ["## Calibration", "", "| Forecast chance | Wards | Average forecast | Favourite won |", "|---|---|---|---|"]
    L += [f"| {k} | {v['wards']:.0f} | {pct(v['forecast'])} | {pct(v['won'])} |" for k, v in r["calibration"].items()]
    L += ["", "## National vote share (ward ballot)", "", "| Party | Forecast | Actual | Error | Inside 90% range |",
          "|---|---|---|---|---|"]
    L += [f"| {p} | {v['forecast']} | {v['actual']} | {v['error']:+.1f} | {'' if v['in_90'] is None else ('yes' if v['in_90'] else 'no')} |"
          for p, v in r["national"].items()]
    L += ["", "Average ward-level error (points): " + ", ".join(f"{p} {v}" for p, v in r["ward_share_mae_pts"].items()), "",
          "## Provinces", "", "| Province | Biggest miss (pts) | ANC fc / actual | DA | MK | IFP |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {v['biggest_miss'][0]} {v['biggest_miss'][1]:+.1f} | {v['ANC'][0]} / {v['ANC'][1]} | {v['DA'][0]} / {v['DA'][1]} | {v['MK'][0]} / {v['MK'][1]} | {v['IFP'][0]} / {v['IFP'][1]} |"
          for k, v in r["provinces"].items()]
    c = r["councils"]
    L += ["", "## Councils", "", f"{c['scored']} councils: largest party right in {pct(c['largest_party_correct'])}, "
          f"majority-or-hung right in {pct(c['hung_status_correct'])} (seats from the same formula as the forecast).", "",
          "| Metro | Largest (fc / actual) | Hung (fc chance / actual) | Seats ANC | DA | MK |", "|---|---|---|---|---|---|"]
    for k, v in r["metros"].items():
        s = v["seats"]
        L.append(f"| {k} | {v['largest'][0]} / {v['largest'][1]} | {v['hung'][0]:.0%} / {'hung' if v['hung'][1] else 'majority'} | "
                 f"{s['ANC'][0]} / {s['ANC'][1]} | {s['DA'][0]} / {s['DA'][1]} | {s['MK'][0]} / {s['MK'][1]} |")
    if "kzn" in r:
        k = r["kzn"]
        L += ["", "## KwaZulu-Natal: which reading was right?", "", "| Ward winners called | By-election-led (published) | Poll-led |",
              "|---|---|---|", f"| All KZN | {pct(k['published_byelection_led'])} | {pct(k['poll_led'])} |",
              f"| Outside eThekwini | {pct(k['outside_ethekwini']['published_byelection_led'])} | {pct(k['outside_ethekwini']['poll_led'])} |"]
    return "\n".join(L) + "\n"


def main(which):
    if which == "test2021":
        w, m, s, alt = forecast_test2021()
        R = results_interim("lge2021")
    elif which == "2026":
        w, m, s, alt = forecast_2026()
        R = results_2026()
    else:
        sys.exit(__doc__)
    A = actual_tables(R, w, m)
    r = score(w, m, s, alt, A, which)
    json.dump(r, open(OUTPUTS / f"scorecard_{which}.json", "w"), indent=1, default=str)
    (OUTPUTS / f"scorecard_{which}.md").write_text(report(r))
    print(report(r))
    if which == "test2021":
        bt = json.load(open(OUTPUTS / "backtest.json"))["results"]["2021"]["model_byelections"]
        print(f"check: scorer {r['ward_accuracy']:.4f} vs backtest {bt:.4f} (the scorer counts the simulations' "
              "favourite, the backtest the largest forecast share, so a few toss-ups can differ)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
