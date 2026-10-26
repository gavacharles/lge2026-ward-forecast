"""Forecast LGE 2026 (4 Nov 2026) ward winners and municipal party strength.

Inputs: 2026 ward->VD delimitation (scrape_wards2026.py), 2024 NPE and 2021 LGE results
(build_data.py), backtest error sizes/coefficients (backtest.py), polls (config/polls_2026.json).
"""
import json

import numpy as np
import pandas as pd

import model as M
from paths import CONFIG, INTERIM, OUTPUTS

PARTIES = M.MAJORS
COLS = PARTIES + ["OTH"]
NEW_OR_UNSTABLE = {"MK", "ASA", "PA"}  # too little 2016-2021 history: use pooled coefficients


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


def main(n_sims=2000):
    votes, other = M.load()
    polls = json.load(open(CONFIG / "polls_2026.json"))
    bt = json.load(open(OUTPUTS / "backtest_2021.json"))["params"]

    map26 = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str)
    wards = map26.drop_duplicates("ward").set_index("ward")[["province", "municipality", "muni"]]

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

    sm = M.StructuralModel()
    sm.pooled = np.array(bt["pooled"])
    sm.coef = {p: np.array(c) for p, c in bt["coef"].items() if p not in NEW_OR_UNSTABLE}
    S = sm.predict(X_npe, X_lge_adj, COLS)

    # 1) national level from polls (named parties; OTH keeps its modelled level)
    nat = poll_targets(polls["national"], aggregate_all(S, weight))
    S = M.calibrate(S, weight, nat, COLS)

    # 2) metros: move towards metro polls by their weight
    is_metro = np.zeros(len(S), bool)
    muni_scale = {}
    for code, mp in polls["metros"].items():
        msk = (wards.muni == code).values
        if not msk.any():
            continue
        is_metro |= msk
        cur = aggregate_all(S, weight, msk)
        w = mp["weight"]
        poll = poll_targets(mp["shares"], cur)
        tgt = {p: float(np.exp(w * np.log(v) + (1 - w) * np.log(max(cur[p], 1e-6)))) for p, v in poll.items()}
        S = M.calibrate(S, weight, tgt, COLS, mask=msk)
        muni_scale[code] = 1 - 0.4 * w

    # 3) everything outside polled metros absorbs the rest of the national target
    W = weight.values
    metro_votes = (S.values[is_metro] * W[is_metro, None]).sum(0)
    rest_w = W[~is_metro].sum()
    rest_tgt = {p: max((nat[p] * W.sum() - metro_votes[COLS.index(p)]) / rest_w, 0.001) for p in nat}
    S = M.calibrate(S, weight, rest_tgt, COLS, mask=~is_metro)

    probs, mstats = M.simulate(S, weight, wards.muni, prev_local, polls["national_sd_logit"],
                               bt["sd_muni"], bt["sd_ward"], n=n_sims,
                               muni_sd_scale=pd.Series(muni_scale))
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
    out["runner_up"] = win.runner_up
    out["margin_pts"] = (win.margin * 100).round(1)
    out["winner_2021_est"] = prev_winner
    out["flip"] = out.favourite != out.winner_2021_est
    out["rating"] = pd.cut(out.win_prob, [0, .6, .75, .9, 1.01], labels=["Toss-up", "Lean", "Likely", "Safe"])
    out["expected_votes"] = weight.round(0)
    out["history_coverage"] = ((cov_npe + cov_lge) / 2).round(2)
    out = out.reset_index().sort_values(["province", "muni", "ward"])

    ms = mstats["share"].mul(100).round(1).add_prefix("share_")
    ml = mstats["p_largest"].round(3).add_prefix("p_largest_")
    mm = mstats["p_majority"].round(3).add_prefix("p_majority_")
    names = wards.drop_duplicates("muni").set_index("muni")[["province", "municipality"]]
    exp_w = named.groupby(wards.muni.values).sum().round(1).add_prefix("exp_wards_")
    muni = names.join([ms, ml, mm, exp_w])
    muni["n_wards"] = wards.groupby("muni").size()
    muni["largest_party"] = mstats["p_largest"].idxmax(axis=1)
    muni["p_largest"] = mstats["p_largest"].max(axis=1).round(3)
    maj = mstats["p_majority"]
    muni["majority_party"] = maj.idxmax(axis=1).where(maj.max(axis=1) > 0.5, "Hung (no majority)")
    muni["p_majority"] = maj.max(axis=1).round(3)
    muni = muni.reset_index().rename(columns={"index": "muni"})

    OUTPUTS.mkdir(exist_ok=True)
    out.to_csv(OUTPUTS / "ward_forecast_2026.csv", index=False)
    muni.to_csv(OUTPUTS / "municipality_forecast_2026.csv", index=False)

    nat_out = (S.mul(weight, axis=0).sum() / weight.sum() * 100).round(1)
    print("National (ward ballot) %:", nat_out.to_dict())
    print("Wards:", len(out), "| favourites:", out.favourite.value_counts().head(12).to_dict())
    print("Expected wards (sum of probs):", named.sum().round(0).to_dict())
    print("Ratings:", out.rating.value_counts().to_dict(), "| flips vs 2021:", int(out.flip.sum()))
    print(muni[muni.muni.isin(list(polls["metros"]))][["muni", "largest_party", "p_largest", "majority_party",
                                                       "p_majority", "share_ANC", "share_DA", "share_MK",
                                                       "share_EFF"]].to_string(index=False))


if __name__ == "__main__":
    main()
