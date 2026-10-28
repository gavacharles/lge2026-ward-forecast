"""Backtests: forecast the 2016 and 2021 LGE ward winners as if it were the eve of each election.

Each cycle mirrors the 2026 setup:
  2021 <- 2019 national ballot + 2016 local ward ballot + by-elections May 2019 - Oct 2021
  2016 <- 2014 national ballot + 2011 local ward ballot + by-elections May 2014 - Jul 2016
Coefficients are fit leave-one-province-out. Party levels are calibrated to the actual national
result (i.e. assumes accurate national polls). The by-election adjustment settings (ALPHA, K) are
tuned across both cycles; error sizes and pooled coefficients for 2026 are saved.

KZN outside eThekwini has no polls, so the 2026 forecast also treats its by-elections as a regional
poll. Here we measure how far that regional by-election level was from the actual result in each
cycle (saved as bias factors for 2026) and score the step with the other cycle's factors.
"""
import itertools
import json

import numpy as np
import pandas as pd

import byelections as BE
import model as M
from community import CommunityTypes
from paths import INTERIM, OUTPUTS

CYCLES = {
    "2021": dict(target="lge2021_ward", npe="npe2019", prev="lge2016_ward", term="402", since="2019-05-09",
                 parties=["ANC", "DA", "EFF", "IFP", "PA", "FFP"]),
    "2016": dict(target="lge2016_ward", npe="npe2014", prev="lge2011_ward", term="197", since="2014-05-08",
                 parties=["ANC", "DA", "EFF", "IFP", "FFP"]),
}
ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]
KS = [5, 10, 20, 40]
METROS = ["BUF", "NMA", "MAN", "EKU", "JHB", "TSH", "ETH", "CPT"]


def robust_sd(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def label_actual(Y, actual_local):
    T = Y.drop(columns="OTH").copy()
    T["LOCAL"] = Y["OTH"] * actual_local.local_frac.reindex(Y.index).fillna(0)
    win = T.idxmax(axis=1)
    names = actual_local.local_name.reindex(Y.index).fillna("OTHER")
    return win.where(win != "LOCAL", names)


def prepare(name, cfg, votes, other, meta):
    mapping = meta[meta.election == cfg["target"]][["vd", "ward", "muni"]].dropna()
    wards = mapping.drop_duplicates("ward").set_index("ward")
    prov = wards.muni.map(BE.province_of)
    P = cfg["parties"]
    cols = P + ["OTH"]
    X_npe, _, _ = M.ward_table(votes, cfg["npe"], mapping, P)
    X_lge, prev_tot, _ = M.ward_table(votes, cfg["prev"], mapping, P)
    Y, _, _ = M.ward_table(votes, cfg["target"], mapping, P)
    weight = prev_tot.where(prev_tot > 0, prev_tot[prev_tot > 0].median())

    comm = CommunityTypes().fit(votes, cfg["npe"])
    ward_comm = comm.assign(votes, cfg["npe"], mapping[["vd"]].assign(key=mapping.ward))
    vd_muni = meta[meta.election == cfg["npe"]][["vd", "muni"]]
    resid = BE.residuals(cfg["term"], cfg["since"], votes, cfg["npe"], P, comm, vd_muni)

    S0 = pd.DataFrame(index=Y.index, columns=cols, dtype=float)
    for pv in prov.unique():
        tr, te = (prov != pv).values, (prov == pv).values
        sm = M.StructuralModel().fit(X_npe[tr], X_lge[tr], Y[tr], weight[tr], cols)
        S0.loc[te] = sm.predict(X_npe[te], X_lge[te], cols).values

    reg = (meta[meta.election == cfg["prev"]][["vd", "registered"]]
           .merge(mapping[["vd", "ward"]], on="vd").groupby("ward").registered.sum())
    turnout = (prev_tot / reg.reindex(prev_tot.index)).clip(0.05, 1).fillna(prev_tot.sum() / reg.sum())
    return dict(
        name=name, cfg=cfg, mapping=mapping, wards=wards, prov=prov, cols=cols, X_npe=X_npe, X_lge=X_lge,
        Y=Y, weight=weight, comm=comm, ward_comm=ward_comm, resid=resid, S0=S0, turnout=turnout,
        national=Y.mul(weight, axis=0).sum() / weight.sum(),
        local_prev=M.top_other(other, cfg["prev"], mapping),
        actual=label_actual(Y, M.top_other(other, cfg["target"], mapping)),
    )


def forecast_variant(c, alpha, k):
    S = c["S0"]
    if alpha > 0:
        pe, ce = BE.effects(c["resid"], k)
        adj = BE.ward_adjustment(c["prov"], c["ward_comm"], pe, ce, c["cfg"]["parties"], alpha)
        S = S * adj[S.columns].values
        S = S.div(S.sum(axis=1), axis=0)
    return M.calibrate(S, c["weight"], {p: c["national"][p] for p in c["cfg"]["parties"]}, c["cols"])


def accuracy(c, S, mask=None):
    pred = M.winners(S, c["local_prev"]).winner
    ok = pred == c["actual"]
    return float(ok[mask].mean() if mask is not None else ok.mean())


def main():
    votes, other = M.load()
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    cycles = {n: prepare(n, cfg, votes, other, meta) for n, cfg in CYCLES.items()}

    # tune the by-election adjustment across both cycles
    grid = []
    for a, k in itertools.product(ALPHAS, KS):
        accs = [accuracy(c, forecast_variant(c, a, k)) for c in cycles.values()]
        grid.append((a, k, *accs, float(np.mean(accs))))
    grid = pd.DataFrame(grid, columns=["alpha", "k", *[f"acc_{n}" for n in cycles], "mean"])
    best = grid.sort_values(["mean", "alpha"], ascending=[False, True]).iloc[0]
    alpha, k = float(best.alpha), int(best.k)

    results, sd_m, sd_w, cal_rows = {}, [], [], []
    for n, c in cycles.items():
        S1 = forecast_variant(c, 0.0, k)
        S2 = forecast_variant(c, alpha, k)
        S3 = S2.copy()
        for pv in c["prov"].unique():
            msk = (c["prov"] == pv).values
            tgt = c["Y"][msk].mul(c["weight"][msk], axis=0).sum() / c["weight"][msk].sum()
            S3 = M.calibrate(S3, c["weight"], {p: tgt[p] for p in c["cfg"]["parties"]}, c["cols"], mask=msk)
        metro = c["wards"].muni.isin(METROS).values
        kzn = (c["prov"] == "KZN").values
        r = {
            "wards": int(len(c["Y"])),
            "byelections_used": int(c["resid"].groupby(["date", "ward"]).ngroups),
            "naive_prev_lge": accuracy(c, c["X_lge"]),
            "naive_npe": accuracy(c, c["X_npe"]),
            "model": accuracy(c, S1),
            "model_byelections": accuracy(c, S2),
            "model_byelections_metros": accuracy(c, S2, metro),
            "model_byelections_non_metros": accuracy(c, S2, ~metro),
            "model_byelections_kzn": accuracy(c, S2, kzn),
            "model_kzn": accuracy(c, S1, kzn),
            "upper_bound_provincial_polls": accuracy(c, S3),
            "mae_share_pts": float((S2 - c["Y"]).abs()[c["cfg"]["parties"]].mean().mean() * 100),
        }
        agg_pred = M.aggregate(S2, c["weight"], c["wards"].muni)
        agg_act = M.aggregate(c["Y"], c["weight"], c["wards"].muni)
        e_m = np.log(agg_act / agg_pred).where(agg_act > 0.03)
        e_w = (np.log(c["Y"] / S2) - e_m.reindex(c["wards"].muni).set_index(c["Y"].index)).where(c["Y"] > 0.03)
        sd_m.append(robust_sd(e_m.values.ravel()))
        sd_w.append(robust_sd(e_w.values.ravel()))
        c["S2"] = S2
        results[n] = r

    # KZN (outside eThekwini): by-elections as a regional poll
    ratios, region = {}, {}
    for n, c in cycles.items():
        cfg = c["cfg"]
        msk = ((c["prov"] == "KZN") & (c["wards"].muni != "ETH")).values
        b, _ = BE.load(cfg["term"])
        ratio, nb = BE.regional_levels(cfg["term"], cfg["since"], votes, cfg["npe"], cfg["parties"],
                                       BE.kzn_region_wards(b.ward))
        wm = c["weight"][msk]
        base = c["X_npe"][msk].mul(wm, axis=0).sum() / wm.sum()
        cur = c["S2"][msk].mul(wm, axis=0).sum() / wm.sum()
        actual = c["Y"][msk].mul(wm, axis=0).sum() / wm.sum()
        target, _ = BE.region_target(base, ratio, nb, 0, cur)
        ratios[n] = (actual / pd.Series(target)).where(actual > 0.01)
        region[n] = dict(msk=msk, base=base, ratio=ratio, n=nb, cur=cur)
    for n, c in cycles.items():
        r = region[n]
        bias = BE.bias_factors({m: v for m, v in ratios.items() if m != n})
        tgt, w = BE.region_target(r["base"], r["ratio"] * bias.reindex(r["ratio"].index).fillna(1), r["n"], k,
                                  r["cur"])
        S4 = M.calibrate(c["S2"], c["weight"], tgt, c["cols"], mask=r["msk"])
        results[n]["kzn_region_byelections_used"] = r["n"]
        results[n]["model_byelections_kzn_region"] = accuracy(c, c["S2"], r["msk"])
        results[n]["model_byelection_level_kzn_region"] = accuracy(c, S4, r["msk"])
    region_bias = BE.bias_factors(ratios)

    sd_muni, sd_ward = float(np.mean(sd_m)), float(np.mean(sd_w))
    tb_all = []
    for n, c in cycles.items():
        tb = M.turnout_betas(c["X_lge"], c["turnout"], c["weight"])
        tb_all.append(tb)
        probs, _ = M.simulate(c["S2"], c["weight"], c["wards"].muni, c["local_prev"], 0.0, sd_muni, sd_ward,
                              n=400, turnout_beta=tb, sd_turnout=0.25)
        lab = c["actual"].copy()
        is_local = ~lab.isin(c["cols"])
        lab[is_local & (lab == c["local_prev"].local_name.reindex(lab.index))] = "LOCAL"
        p_actual = np.array([probs.at[w, l] if l in probs.columns else 0.0 for w, l in lab.items()])
        p_top = probs.max(axis=1)
        hit = probs.idxmax(axis=1) == lab
        results[n]["brier"] = float(((1 - p_actual) ** 2).mean())
        results[n]["log_loss"] = float(-np.log(np.clip(p_actual, 1e-3, 1)).mean())
        bins = pd.cut(p_top, [0, .5, .6, .7, .8, .9, .95, 1.0001])
        cal = pd.DataFrame({"pred": p_top, "hit": hit}).groupby(bins, observed=True).agg(
            n=("hit", "size"), mean_pred=("pred", "mean"), observed=("hit", "mean")).reset_index()
        cal["cycle"] = n
        cal_rows.append(cal)

    # pooled coefficients for 2026 (all parties seen in either cycle)
    coef = {}
    for p in ["ANC", "DA", "EFF", "IFP", "PA", "FFP", "OTH"]:
        Xs, Ls, Ys, Ws = [], [], [], []
        for c in cycles.values():
            if p in c["cols"]:
                Xs.append(c["X_npe"][p]); Ls.append(c["X_lge"][p]); Ys.append(c["Y"][p]); Ws.append(c["weight"])
        sm = M.StructuralModel().fit(pd.concat(Xs).to_frame(p), pd.concat(Ls).to_frame(p),
                                     pd.concat(Ys).to_frame(p), pd.concat(Ws), [p])
        coef[p] = sm.coef[p].tolist()
    allp = [p for p in ["ANC", "DA", "EFF", "IFP", "FFP", "OTH"]]
    X = pd.concat([c["X_npe"][allp] for c in cycles.values()], ignore_index=True)
    L = pd.concat([c["X_lge"][allp] for c in cycles.values()], ignore_index=True)
    Yy = pd.concat([c["Y"][allp] for c in cycles.values()], ignore_index=True)
    W = pd.concat([c["weight"] for c in cycles.values()], ignore_index=True)
    pooled = M.StructuralModel().fit(X, L, Yy, W, allp).pooled.tolist()

    out = {
        "results": results,
        "tuning": grid.round(4).to_dict(orient="records"),
        "params": {"alpha": alpha, "k_shrink": k, "sd_muni": sd_muni, "sd_ward": sd_ward,
                   "sd_turnout": 0.25, "coef": coef, "pooled": pooled,
                   "kzn_byelection_bias": region_bias.round(3).to_dict()},
        "communities": {n: c["comm"].labels for n, c in cycles.items()},
    }
    OUTPUTS.mkdir(exist_ok=True)
    json.dump(out, open(OUTPUTS / "backtest.json", "w"), indent=1)
    pd.concat(cal_rows).to_csv(OUTPUTS / "backtest_calibration.csv", index=False)
    print(json.dumps(results, indent=1))
    print(grid.sort_values("mean", ascending=False).head(8).to_string(index=False))
    print("alpha", alpha, "k", k, "sd_muni", round(sd_muni, 3), "sd_ward", round(sd_ward, 3))


if __name__ == "__main__":
    main()
