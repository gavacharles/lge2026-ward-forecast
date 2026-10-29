"""Forecast LGE 2026 (4 Nov 2026) ward winners, municipal vote shares and council seats.

Inputs: 2026 ward->VD delimitation (scrape_wards2026.py), VD results 2021 LGE and 2024 NPE
(build_data.py), by-elections since the 2024 election (scrape_byelections.py), backtest
coefficients and error sizes (backtest.py), polls (config/polls_2026.csv via polls.py), coalition
blocs (config/coalitions.json) and, if present, ward candidate lists (config/candidates_2026.csv).

Two scenarios differ only in KwaZulu-Natal outside eThekwini, where there are no polls:
  byelection (published)  its by-elections since 2024 act as a regional poll (corrected for how far
                          KZN by-elections were from the next local result in 2016 and 2021), and MK
                          and IFP keep their modelled levels elsewhere instead of being forced to
                          their national poll totals;
  poll                    national polls set every party's level everywhere (the earlier method).
"""
import json
import sys

import numpy as np
import pandas as pd

import byelections as BE
import model as M
import polls as POLLS
from community import CommunityTypes
from paths import CONFIG, INTERIM, OUTPUTS

PARTIES = M.MAJORS
COLS = PARTIES + ["OTH"]
NEW_OR_UNSTABLE = {"MK", "ASA", "PA"}  # too little 2011-2021 history: use pooled coefficients
BYELECTION_SINCE = "2024-05-30"        # MK era: compare with the 2024 national ballot
MAX_SD_LOG = 0.5


def aggregate_all(S, weight, mask=None):
    mask = np.ones(len(S), bool) if mask is None else mask
    w = weight.values[mask]
    return pd.Series((S.values[mask] * w[:, None]).sum(0) / w.sum(), index=S.columns)


def poll_targets(shares_pct, current):
    """Poll shares -> calibration targets. Polls under-measure independents and local parties,
    so the model keeps its own level for OTH and for named parties the poll does not report;
    the polled parties split the remainder in poll proportions."""
    listed = {p: v for p, v in shares_pct.items() if p in COLS}
    unlisted = [p for p in COLS if p not in listed]
    room = 1 - current[unlisted].sum()
    total = sum(listed.values())
    return {p: v / total * room for p, v in listed.items()}


def apply_candidates(S, wards):
    """Drop parties with no ward candidate, if a candidate list is available (ward, party)."""
    f = CONFIG / "candidates_2026.csv"
    if not f.exists():
        return S, False
    c = pd.read_csv(f, dtype=str)
    standing = c.assign(on=1).pivot_table(index="ward", columns="party", values="on", aggfunc="max", fill_value=0)
    standing = standing.reindex(index=S.index, columns=PARTIES).fillna(1)  # unknown ward: assume all stand
    S = S.copy()
    S[PARTIES] = S[PARTIES].values * standing.values
    return S.div(S.sum(axis=1), axis=0), True


def run(n_sims=2000, as_of=None, scenario="byelection"):
    votes, other = M.load()
    poll = POLLS.aggregate(as_of)
    bt = json.load(open(OUTPUTS / "backtest.json"))["params"]
    blocs = json.load(open(CONFIG / "coalitions.json"))
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")

    map26 = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str)
    wards = map26.drop_duplicates("ward").set_index("ward")[["province", "municipality", "muni"]]
    prov = wards.muni.map(BE.province_of)

    X_npe, npe_tot, cov_npe = M.ward_table(votes, "npe2024", map26, PARTIES)
    X_lge, lge_tot, cov_lge = M.ward_table(votes, "lge2021_ward", map26, PARTIES)
    prev_local = M.top_other(other, "lge2021_ward", map26)
    prev_winner = M.winners(X_lge, prev_local).winner

    # MK split from the ANC: carry 2021 ANC local support into ANC/MK by the ward's 2024 ratio
    ratio = (X_npe.ANC / (X_npe.ANC + X_npe.MK)).fillna(1)
    X_lge_adj = X_lge.copy()
    X_lge_adj["MK"] = X_lge.ANC * (1 - ratio)
    X_lge_adj["ANC"] = X_lge.ANC * ratio

    # expected ward-ballot turnout: 2021 votes in the new ward, else 2024 votes scaled to LGE turnout
    lge_npe = lge_tot.sum() / npe_tot.sum()
    weight = lge_tot.where(lge_tot > 0, npe_tot * lge_npe)
    weight = weight.where(weight > 0, weight[weight > 0].median())

    # 1) structural model (coefficients pooled over the 2016 and 2021 backtests)
    sm = M.StructuralModel()
    sm.pooled = np.array(bt["pooled"])
    sm.coef = {p: np.array(c) for p, c in bt["coef"].items() if p not in NEW_OR_UNSTABLE}
    S = sm.predict(X_npe, X_lge_adj, COLS)

    # 2) local swing from by-elections since the 2024 election, by province and community type
    comm = CommunityTypes().fit(votes, "npe2024")
    ward_comm = comm.assign(votes, "npe2024", map26[["vd"]].assign(key=map26.ward))
    vd_muni = meta[meta.election == "npe2024"][["vd", "muni"]]
    resid = BE.residuals("1091", BYELECTION_SINCE, votes, "npe2024", PARTIES, comm, vd_muni)
    pe, ce = BE.effects(resid, bt["k_shrink"])
    adj = BE.ward_adjustment(prov, ward_comm, pe, ce, PARTIES, bt["alpha"])
    S = S * adj[COLS].values
    S = S.div(S.sum(axis=1), axis=0)

    # 3) who is standing (optional input)
    S, used_candidates = apply_candidates(S, wards)

    # 4) national level from polls. Independents and local parties (OTH) are under-measured by
    #    polls, so they hold their 2021 ward-ballot level in the 2026 wards (persistence); the
    #    polled parties share the rest in poll proportions.
    oth_2021 = float((X_lge.OTH * weight).sum() / weight.sum())
    cur = aggregate_all(S, weight)
    cur["OTH"] = oth_2021
    nat = poll_targets(poll["national"], cur)
    nat["OTH"] = oth_2021
    S = M.calibrate(S, weight, nat, COLS)

    # 5) metros: move towards metro polls by their weight
    is_metro = np.zeros(len(S), bool)
    muni_scale = {}
    for code, mp in poll["metros"].items():
        msk = (wards.muni == code).values
        if not msk.any():
            continue
        is_metro |= msk
        cur = aggregate_all(S, weight, msk)
        w = mp["weight"]
        pt = poll_targets(mp["shares"], cur)
        tgt = {p: float(np.exp(w * np.log(v) + (1 - w) * np.log(max(cur[p], 1e-6)))) for p, v in pt.items()}
        S = M.calibrate(S, weight, tgt, COLS, mask=msk)
        muni_scale[code] = 1 - 0.5 * w

    # 5b) KZN outside eThekwini: by-elections as a regional poll (by-election scenario only)
    region = np.zeros(len(S), bool)
    region_info = None
    if scenario == "byelection":
        region = ((prov == "KZN") & (wards.muni != "ETH")).values
        b, _ = BE.load("1091")
        ratio, nb = BE.regional_levels("1091", BYELECTION_SINCE, votes, "npe2024", PARTIES, BE.kzn_region_wards(b.ward))
        bias = pd.Series(bt.get("kzn_byelection_bias", {}), dtype=float).reindex(ratio.index).fillna(1.0)
        wr = weight[region]
        base = X_npe[region].mul(wr, axis=0).sum() / wr.sum()
        cur = aggregate_all(S, weight, region)
        tgt, w_region = BE.region_target(base, ratio * bias, nb, bt["k_shrink"], cur)
        S = M.calibrate(S, weight, tgt, COLS, mask=region)
        region_info = {"byelections": nb, "weight": round(w_region, 2), "ratio": ratio.round(3).to_dict(),
                       "bias": bias.round(3).to_dict(), "before": (cur * 100).round(1).to_dict(),
                       "after": (aggregate_all(S, weight, region) * 100).round(1).to_dict()}

    # 6) everything else absorbs the rest of the national target. In the by-election scenario MK and
    #    IFP (whose levels KZN by-elections contradict) keep their modelled levels here, so their
    #    national totals come out of the model rather than the polls.
    W = weight.values
    fixed = is_metro | region
    fixed_votes = (S.values[fixed] * W[fixed, None]).sum(0)
    rest_w = W[~fixed].sum()
    floating = {"MK", "IFP"} if scenario == "byelection" else set()
    rest_tgt = {p: max((nat[p] * W.sum() - fixed_votes[COLS.index(p)]) / rest_w, 0.001) for p in nat
                if p not in floating}
    if floating:
        rest_cur = aggregate_all(S, weight, ~fixed)
        keep = {p: float(rest_cur[p]) for p in floating}
        scale = (1 - sum(keep.values())) / sum(rest_tgt.values())
        rest_tgt = {p: v * scale for p, v in rest_tgt.items()} | keep
    S = M.calibrate(S, weight, rest_tgt, COLS, mask=~fixed)

    # 7) simulate: poll error per party, municipal and ward surprises, differential turnout, seats
    sd_nat = np.array([min(poll["national_sd_pts"].get(p, POLLS.HIST_ERR) / max(poll["national"].get(p, 2.0), 2.0),
                           MAX_SD_LOG) if p != "OTH" else 0.15 for p in COLS])
    reg = (meta[meta.election == "lge2021_ward"][["vd", "registered"]]
           .merge(map26[["vd", "ward"]], on="vd").groupby("ward").registered.sum())
    turnout = (lge_tot / reg.reindex(lge_tot.index)).clip(0.05, 1).fillna(lge_tot.sum() / reg.sum())
    tbeta = M.turnout_betas(X_lge_adj, turnout, weight)
    council_seats = wards.groupby("muni").size() * 2
    probs, mstats = M.simulate(S, weight, wards.muni, prev_local, sd_nat, bt["sd_muni"], bt["sd_ward"],
                               n=n_sims, muni_sd_scale=pd.Series(muni_scale), turnout_beta=tbeta,
                               sd_turnout=bt["sd_turnout"], council_seats=council_seats, blocs=blocs)

    win = M.winners(S, prev_local)
    local_name = prev_local.local_name.reindex(S.index).fillna("OTHER")
    named = probs.rename(columns={"LOCAL": "LOCAL_TOP"})
    p_win = named.max(axis=1)
    fav = named.idxmax(axis=1)
    fav = fav.where(fav != "LOCAL_TOP", local_name)

    out = wards.copy()
    out["ward_no"] = out.index.str[-3:].astype(int)
    for p in COLS:
        out[f"share_{p}"] = (S[p] * 100).round(1)
    for p in named.columns:
        out[f"p_{p}"] = named[p].round(3)
    out["local_top_party_2021"] = local_name
    out["favourite"] = fav
    out["win_prob"] = p_win.round(3)
    second = pd.Series(np.array(named.columns)[np.argsort(-named.values, axis=1)[:, 1]], index=named.index)
    out["runner_up"] = second.where(second != "LOCAL_TOP", local_name)
    out["margin_pts"] = (win.margin * 100).round(1)
    out["winner_2021_est"] = prev_winner
    out["flip"] = out.favourite != out.winner_2021_est
    out["rating"] = pd.cut(out.win_prob, [0, .6, .75, .9, 1.01], labels=["Toss-up", "Lean", "Likely", "Safe"])
    out["community"] = ward_comm.reindex(out.index).map(dict(enumerate(comm.labels)))
    out["expected_votes"] = weight.round(0)
    out["history_coverage"] = ((cov_npe + cov_lge) / 2).round(2)
    out = out.reset_index().sort_values(["province", "muni", "ward"])

    names = wards.drop_duplicates("muni").set_index("muni")[["province", "municipality"]]
    muni = names.join([
        mstats["share"].mul(100).round(1).add_prefix("share_"),
        mstats["seats"].round(1).add_prefix("seats_"),
        mstats["p_largest_seats"].round(3).add_prefix("p_largest_"),
        mstats["p_majority_seats"].round(3).add_prefix("p_majority_"),
        mstats["p_bloc_majority"].round(3).add_prefix("p_bloc_"),
        mstats["ladder"].round(3).add_prefix("ladder_"),
        named.groupby(wards.muni.values).sum().round(1).add_prefix("exp_wards_"),
    ])
    muni["n_wards"] = wards.groupby("muni").size()
    muni["council_seats"] = council_seats
    pls = mstats["p_largest_seats"]
    muni["largest_party"] = pls.idxmax(axis=1)
    muni["p_largest"] = pls.max(axis=1).round(3)
    maj = mstats["p_majority_seats"]
    muni["majority_party"] = maj.idxmax(axis=1).where(maj.max(axis=1) > 0.5, "Hung (no majority)")
    muni["p_majority"] = maj.max(axis=1).round(3)
    muni["p_hung"] = (1 - maj.sum(axis=1)).clip(0, 1).round(3)
    muni = muni.reset_index().rename(columns={"index": "muni"})

    nat_out = (S.mul(weight, axis=0).sum() / weight.sum() * 100).round(2)
    summary = {
        "as_of": poll["as_of"], "national_share": nat_out.to_dict(), "polls": poll,
        "national_sd_log": dict(zip(COLS, np.round(sd_nat, 3).tolist())),
        "turnout_beta": tbeta.round(3).to_dict(), "byelections_used": int(resid.groupby(["date", "ward"]).ngroups),
        "byelection_province_effects": pe.round(3).unstack().fillna(0).to_dict(orient="index"),
        "communities": comm.labels, "used_candidate_list": used_candidates,
        "wards": int(len(out)), "favourites": out.favourite.value_counts().to_dict(),
        "expected_wards": named.sum().round(1).to_dict(), "ratings": out.rating.value_counts().to_dict(),
        "flips": int(out.flip.sum()), "scenario": scenario, "kzn_region": region_info,
        "national_interval_90": (mstats["national_interval"] * 100).round(1).to_dict(),
        "expected_correct_calls": round(float(out.win_prob.mean()), 3),
    }
    return out, muni, summary, resid


def kzn_summary(out, muni):
    k = out[out.province.str.contains("Natal")]
    reg = k[k.muni != "ETH"]
    m = muni[muni.province.str.contains("Natal")]
    return {"favourites": k.favourite.value_counts().head(6).to_dict(),
            "favourites_outside_ethekwini": reg.favourite.value_counts().head(6).to_dict(),
            "councils_largest": m.largest_party.value_counts().to_dict(),
            "share_outside_ethekwini": {p: round(float((reg[f"share_{p}"] * reg.expected_votes).sum()
                                                       / reg.expected_votes.sum()), 1) for p in COLS}}


def main(n_sims=2000, as_of=None):
    out, muni, summary, resid = run(n_sims, as_of, "byelection")
    alt, alt_muni, alt_summary, _ = run(n_sims, as_of, "poll")
    summary["scenarios"] = {
        "byelection": {"national_share": summary["national_share"], "kzn": kzn_summary(out, muni)},
        "poll": {"national_share": alt_summary["national_share"], "kzn": kzn_summary(alt, alt_muni)},
    }
    OUTPUTS.mkdir(exist_ok=True)
    out.to_csv(OUTPUTS / "ward_forecast_2026.csv", index=False)
    muni.to_csv(OUTPUTS / "municipality_forecast_2026.csv", index=False)
    alt.to_csv(OUTPUTS / "ward_forecast_2026_poll_scenario.csv", index=False)
    resid.to_csv(OUTPUTS / "byelection_residuals_2026.csv", index=False)

    json.dump(summary, open(OUTPUTS / "forecast_summary_2026.json", "w"), indent=1, default=str)

    nat_out = pd.Series(summary["national_share"])
    blocs = json.load(open(CONFIG / "coalitions.json"))
    poll = summary["polls"]
    print("National (ward ballot) %:", nat_out.round(1).to_dict())
    print("KZN region:", summary["kzn_region"])
    print("Scenarios:", json.dumps(summary["scenarios"], indent=1))
    print("Favourites:", out.favourite.value_counts().head(10).to_dict())
    print("Ratings:", out.rating.value_counts().to_dict(), "| flips vs 2021:", int(out.flip.sum()))
    print("By-elections used:", summary["byelections_used"], "| turnout betas:", summary["turnout_beta"])
    cols = ["muni", "largest_party", "p_largest", "majority_party", "p_majority", "seats_ANC", "seats_DA",
            "seats_MK", "seats_EFF", "council_seats"] + [f"p_bloc_{b}" for b in blocs]
    print(muni[muni.muni.isin(list(poll["metros"]))][cols].to_string(index=False))
    print(pd.crosstab(out.province, out.favourite).loc[:, lambda x: x.sum() > 20])


if __name__ == "__main__":
    main(*(sys.argv[1:2] and [int(sys.argv[1])]))
