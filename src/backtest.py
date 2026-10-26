"""Backtest: forecast the 2021 LGE ward winners from 2019 NPE + 2016 LGE.

Mirrors the 2026 setup (latest national election + previous local election).
Coefficients are fit leave-one-province-out; party levels are calibrated to the actual
2021 national result (i.e. assumes accurate national polls) - the 'perfect poll' upper
bound is reported next to naive baselines. Also estimates error sizes for the simulation.
"""
import json

import numpy as np
import pandas as pd

import model as M
from paths import INTERIM, OUTPUTS

PARTIES = ["ANC", "DA", "EFF", "IFP", "PA", "FFP"]  # ActionSA (new in 2021) folds into OTH
METRO_PROV = {"BUF": "EC", "NMA": "EC", "MAN": "FS", "EKU": "GT", "JHB": "GT", "TSH": "GT",
              "ETH": "KZN", "CPT": "WC"}


def province(muni):
    if muni in METRO_PROV:
        return METRO_PROV[muni]
    for pre in ("KZN", "LIM", "EC", "FS", "GT", "MP", "NW", "NC", "WC", "DC"):
        if muni.startswith(pre):
            return pre
    return "?"


def robust_sd(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def label_actual(Y, actual_local):
    T = Y.drop(columns="OTH").copy()
    T["LOCAL"] = Y["OTH"] * actual_local.local_frac.reindex(Y.index).fillna(0)
    win = T.idxmax(axis=1)
    names = actual_local.local_name.reindex(Y.index).fillna("OTHER")
    return win.where(win != "LOCAL", names)


def main():
    votes, other = M.load()
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    map21 = meta[meta.election == "lge2021_ward"][["vd", "ward", "muni"]].dropna()
    wards = map21.drop_duplicates("ward").set_index("ward")
    prov = wards.muni.map(province)

    X_npe, _, cov_npe = M.ward_table(votes, "npe2019", map21, PARTIES)
    X_lge, prev_tot, cov_lge = M.ward_table(votes, "lge2016_ward", map21, PARTIES)
    Y, _, _ = M.ward_table(votes, "lge2021_ward", map21, PARTIES)
    weight = prev_tot.where(prev_tot > 0, prev_tot[prev_tot > 0].median())
    cols = PARTIES + ["OTH"]

    # leave-one-province-out structural predictions
    S0 = pd.DataFrame(index=Y.index, columns=cols, dtype=float)
    for pv in prov.unique():
        tr, te = prov != pv, prov == pv
        sm = M.StructuralModel().fit(X_npe[tr], X_lge[tr], Y[tr], weight[tr], cols)
        S0.loc[te] = sm.predict(X_npe[te], X_lge[te], cols).values
    full = M.StructuralModel().fit(X_npe, X_lge, Y, weight, cols)

    national = (Y.mul(weight, axis=0).sum() / weight.sum())
    S1 = M.calibrate(S0, weight, {p: national[p] for p in PARTIES}, cols)

    # 'perfect provincial polls' variant
    S2 = S1.copy()
    for pv in prov.unique():
        msk = (prov == pv).values
        tgt = Y[msk].mul(weight[msk], axis=0).sum() / weight[msk].sum()
        S2 = M.calibrate(S2, weight, {p: tgt[p] for p in PARTIES}, cols, mask=msk)

    local_prev = M.top_other(other, "lge2016_ward", map21)
    local_act = M.top_other(other, "lge2021_ward", map21)
    actual = label_actual(Y, local_act)

    res = {}
    for name, S in [("naive_2016_lge", X_lge), ("naive_2019_npe", X_npe),
                    ("model_national_poll", S1), ("model_provincial_poll", S2)]:
        pred = M.winners(S, local_prev).winner
        res[name] = float((pred == actual).mean())
    metro = wards.muni.isin(METRO_PROV).values
    pred1 = M.winners(S1, local_prev).winner
    res["model_national_poll_metros"] = float((pred1[metro] == actual[metro]).mean())
    res["model_national_poll_non_metros"] = float((pred1[~metro] == actual[~metro]).mean())
    res["mae_share_pts"] = float((S1 - Y).abs()[PARTIES].mean().mean() * 100)

    # error sizes in log-share space (only where a party is a real contender)
    agg_pred = M.aggregate(S1, weight, wards.muni)
    agg_act = M.aggregate(Y, weight, wards.muni)
    e_m = np.log(agg_act / agg_pred).where(agg_act > 0.03)
    sd_muni = robust_sd(e_m.values.ravel())
    e_w = (np.log(Y / S1) - e_m.reindex(wards.muni).set_index(Y.index)).where(Y > 0.03)
    sd_ward = robust_sd(e_w.values.ravel())

    # probability calibration of the simulation (national error = 0: levels were calibrated)
    probs, _ = M.simulate(S1, weight, wards.muni, local_prev, 0.0, sd_muni, sd_ward, n=400)
    p_lab = probs.copy()
    lab = actual.copy()
    is_local = ~actual.isin(cols)
    lab[is_local & (actual == local_prev.local_name.reindex(actual.index))] = "LOCAL"
    p_actual = np.array([p_lab.loc[w, l] if l in p_lab.columns else 0.0 for w, l in lab.items()])
    p_top = probs.max(axis=1)
    hit = (probs.idxmax(axis=1) == lab)
    bins = pd.cut(p_top, [0, .5, .6, .7, .8, .9, .95, 1.0001])
    calib = pd.DataFrame({"pred": p_top, "hit": hit}).groupby(bins, observed=True).agg(
        n=("hit", "size"), mean_pred=("pred", "mean"), observed=("hit", "mean"))
    res["brier_winner"] = float(((1 - p_actual) ** 2).mean())
    res["log_loss_winner"] = float(-np.log(np.clip(p_actual, 1e-3, 1)).mean())

    params = {"sd_muni": sd_muni, "sd_ward": sd_ward,
              "coef": {p: full.coef[p].tolist() for p in cols}, "pooled": full.pooled.tolist(),
              "coverage_npe2019": float(cov_npe.mean()), "coverage_lge2016": float(cov_lge.mean())}
    OUTPUTS.mkdir(exist_ok=True)
    json.dump({"metrics": res, "params": params}, open(OUTPUTS / "backtest_2021.json", "w"), indent=2)
    calib.to_csv(OUTPUTS / "backtest_2021_calibration.csv")
    print(json.dumps(res, indent=2))
    print(json.dumps(params, indent=2))
    print(calib)


if __name__ == "__main__":
    main()
