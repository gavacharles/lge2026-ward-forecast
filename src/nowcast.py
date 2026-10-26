"""Election-night nowcast: update ward forecasts as voting districts (VDs) report.

For each ward the forecast shares are spread to its VDs using the VDs' own profile in the last
national election. As VDs report:
  1. reported VDs count as they are;
  2. the swing of reported VDs against their prior, r = log(actual / prior), is averaged per
     municipality (shrunk towards the province, then towards zero) and applied to the VDs still out;
  3. turnout in unreported VDs follows the reported VDs' turnout against 2021 in that municipality;
  4. the remaining uncertainty shrinks with the share of the ward's expected votes still out.

Usage:
  python nowcast.py live     # pull the IEC 2026 results files, write outputs/nowcast_2026.csv
  python nowcast.py replay   # test on 2021: reveal 10-75% of VDs at random, score ward calls
"""
import json
import sys

import numpy as np
import pandas as pd
import requests

import byelections as BE
import model as M
from paths import INTERIM, OUTPUTS, RAW

K_MUNI = 3.0   # shrinkage, in units of a typical VD's votes
LIVE_URL = "https://results.elections.org.za/home/LGEPublicReports/1887/Downloadable%20Party%20Results/{pr}.csv"
PROVS = ["EC", "FS", "GP", "KN", "NP", "MP", "NW", "NC", "WP"]


def vd_prior(S, mapping, votes, baseline, parties):
    """VD-level prior shares: ward forecast x (VD baseline share / ward baseline share)."""
    cols = parties + ["OTH"]
    v = votes[votes.election == baseline].merge(mapping[["vd", "ward"]], on="vd")
    v["party"] = v.party.where(v.party.isin(parties), "OTH")
    vd = v.pivot_table(index="vd", columns="party", values="votes", aggfunc="sum", fill_value=0).reindex(columns=cols, fill_value=0)
    vd = vd.div(vd.sum(axis=1).replace(0, np.nan), axis=0)
    wd = v.pivot_table(index="ward", columns="party", values="votes", aggfunc="sum", fill_value=0).reindex(columns=cols, fill_value=0)
    wd = wd.div(wd.sum(axis=1).replace(0, np.nan), axis=0)
    m = mapping.set_index("vd")
    ward_of = m.ward.reindex(vd.index)
    ratio = (vd.values + 0.01) / (wd.reindex(ward_of.values).values + 0.01)
    prior = S.reindex(ward_of.values)[cols].values * ratio
    prior = pd.DataFrame(prior / prior.sum(1, keepdims=True), index=vd.index, columns=cols)
    missing = mapping[~mapping.vd.isin(prior.index)]
    if len(missing):
        prior = pd.concat([prior, pd.DataFrame(S.reindex(missing.ward)[cols].values, index=missing.vd, columns=cols)])
    return prior


def nowcast(S, mapping, prior, exp_votes, observed, local, sd_muni, sd_ward, n=500, seed=11):
    """observed: DataFrame index vd, columns = parties + OTH (votes). Returns ward table."""
    cols = list(prior.columns)
    rng = np.random.default_rng(seed)
    m = mapping.drop_duplicates("vd").set_index("vd")
    obs = observed.reindex(columns=cols, fill_value=0)
    obs = obs[obs.index.isin(m.index) & (obs.sum(axis=1) > 0)]
    rep = m.index.isin(obs.index)
    sh = obs.div(obs.sum(axis=1), axis=0)
    pr = prior.reindex(obs.index)
    ok = (sh >= 0.02) | (pr >= 0.02)
    r = np.log(np.clip(sh, 0.005, 1) / np.clip(pr, 0.005, 1)).where(ok, 0.0)
    w = obs.sum(axis=1)
    k = K_MUNI * (w.median() if len(w) else 1)
    muni = m.muni.reindex(obs.index)
    prov = muni.map(BE.province_of)
    rw = r.mul(w, axis=0)
    e_prov = rw.groupby(prov).sum().div(w.groupby(prov).sum() + k, axis=0)
    resid = r - e_prov.reindex(prov.values).values
    e_muni = resid.mul(w, axis=0).groupby(muni).sum().div(w.groupby(muni).sum() + k, axis=0)
    turnout = (w.groupby(muni).sum() / exp_votes.reindex(obs.index).groupby(muni).sum()).clip(0.3, 3)

    out_vd = m.index[~rep]
    om = m.loc[out_vd, "muni"]
    e = (e_prov.reindex(om.map(BE.province_of).values).fillna(0).values
         + e_muni.reindex(om.values).fillna(0).values)
    x = prior.reindex(out_vd).values * np.exp(e)
    x /= x.sum(1, keepdims=True)
    ev = exp_votes.reindex(out_vd).fillna(exp_votes.median()).values * turnout.reindex(om.values).fillna(1).values

    wards = m.ward
    known = obs.groupby(wards.reindex(obs.index).values).sum().reindex(columns=cols)
    unk = pd.DataFrame(x * ev[:, None], index=out_vd, columns=cols).groupby(wards.reindex(out_vd).values).sum()
    allw = S.index
    K = known.reindex(allw).fillna(0)
    U = unk.reindex(allw).fillna(0)
    tot_k, tot_u = K.sum(axis=1), U.sum(axis=1)
    frac_out = (tot_u / (tot_k + tot_u)).fillna(1)
    muni_w = m.drop_duplicates("ward").set_index("ward").muni.reindex(allw)
    frac_muni_out = frac_out.groupby(muni_w.values).transform("mean")

    frac = local.local_frac.reindex(allw).fillna(0).values
    oth = cols.index("OTH")
    wins = np.zeros((len(allw), len(cols)))
    munis, midx = np.unique(muni_w.values, return_inverse=True)
    base_u = np.log(np.clip(U.values / np.maximum(tot_u.values[:, None], 1e-9), 1e-6, 1))
    for _ in range(n):
        noise = (rng.normal(0, 1, (len(munis), len(cols)))[midx] * (sd_muni * frac_muni_out.values)[:, None]
                 + rng.standard_t(5, (len(allw), len(cols))) * (sd_ward * np.sqrt(frac_out.values))[:, None])
        u = np.exp(base_u + noise)
        u = u / u.sum(1, keepdims=True) * tot_u.values[:, None]
        y = K.values + u
        y[:, oth] *= frac
        wins[np.arange(len(allw)), y.argmax(1)] += 1
    labels = cols[:oth] + ["LOCAL"] + cols[oth + 1:]
    probs = pd.DataFrame(wins / n, index=allw, columns=labels)
    est = (K + U)
    est = est.div(est.sum(axis=1), axis=0)
    names = local.local_name.reindex(allw).fillna("OTHER")
    fav = probs.idxmax(axis=1)
    return pd.DataFrame({
        "favourite": fav.where(fav != "LOCAL", names), "win_prob": probs.max(axis=1).round(3),
        "reported_share_of_votes": (1 - frac_out).round(3),
        **{f"share_{p}": (est[p] * 100).round(1) for p in cols},
    }, index=allw)


def replay(fracs=(0.1, 0.25, 0.5, 0.75), seed=3):
    """Pretend 2021 results arrive VD by VD (random order); score ward calls against the result."""
    import backtest as B
    votes, other = M.load()
    meta = pd.read_parquet(INTERIM / "vd_meta.parquet")
    bt = json.load(open(OUTPUTS / "backtest.json"))["params"]
    c = B.prepare("2021", B.CYCLES["2021"], votes, other, meta)
    S = B.forecast_variant(c, bt["alpha"], bt["k_shrink"])
    P = c["cfg"]["parties"]
    cols = P + ["OTH"]
    mapping = c["mapping"]
    prior = vd_prior(S, mapping, votes, "npe2019", P)
    t = votes[votes.election == "lge2021_ward"].copy()
    t["party"] = t.party.where(t.party.isin(P), "OTH")
    actual_vd = t.pivot_table(index="vd", columns="party", values="votes", aggfunc="sum", fill_value=0).reindex(columns=cols, fill_value=0)
    p16 = votes[votes.election == "lge2016_ward"].groupby("vd").votes.sum()
    exp_votes = p16.reindex(mapping.vd.values).fillna(p16.median())
    exp_votes.index = mapping.vd.values
    rng = np.random.default_rng(seed)
    order = rng.permutation(actual_vd.index.values)
    res = [{"reported": 0.0, "accuracy": B.accuracy(c, S)}]
    for f in fracs:
        obs = actual_vd.loc[order[: int(f * len(order))]]
        nc = nowcast(S, mapping, prior, exp_votes, obs, c["local_prev"], bt["sd_muni"], bt["sd_ward"], n=200)
        acc = float((nc.favourite == c["actual"].reindex(nc.index)).mean())
        res.append({"reported": f, "accuracy": acc})
        print(f"{f:.0%} of VDs reported: {acc:.1%} of wards called correctly", flush=True)
    pd.DataFrame(res).to_csv(OUTPUTS / "nowcast_replay_2021.csv", index=False)
    return res


def fetch_live():
    from build_data import group
    frames = []
    for pr in PROVS:
        r = requests.get(LIVE_URL.format(pr=pr), headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
        if r.status_code != 200:
            continue
        f = RAW / "live2026" / f"{pr}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
        frames.append(pd.read_csv(f, encoding="utf-8-sig", low_memory=False))
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True)
    d = d[d.BallotType == "Ward"]
    d["party"] = d.PartyName.map(group)
    return d.pivot_table(index=d.VotingDistrict.astype(str), columns="party", values="TotalValidVotes",
                         aggfunc="sum", fill_value=0)


def live():
    obs = fetch_live()
    if obs is None or obs.values.sum() == 0:
        print("No 2026 results published yet.")
        return
    votes, other = M.load()
    bt = json.load(open(OUTPUTS / "backtest.json"))["params"]
    fc = pd.read_csv(OUTPUTS / "ward_forecast_2026.csv", dtype={"ward": str}).set_index("ward")
    cols = M.MAJORS + ["OTH"]
    S = fc[[f"share_{p}" for p in cols]].div(100)
    S.columns = cols
    mapping = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str)
    prior = vd_prior(S, mapping, votes, "npe2024", M.MAJORS)
    p21 = votes[votes.election == "lge2021_ward"].groupby("vd").votes.sum()
    exp_votes = p21.reindex(mapping.vd.values).fillna(p21.median())
    exp_votes.index = mapping.vd.values
    local = M.top_other(other, "lge2021_ward", mapping)
    nc = nowcast(S, mapping, prior, exp_votes, obs, local, bt["sd_muni"], bt["sd_ward"])
    nc.to_csv(OUTPUTS / "nowcast_2026.csv")
    print(f"{(obs.sum(axis=1) > 0).sum()} VDs reported; wards called: {nc.favourite.value_counts().head(6).to_dict()}")


if __name__ == "__main__":
    {"live": live, "replay": replay}[sys.argv[1] if len(sys.argv) > 1 else "replay"]()
