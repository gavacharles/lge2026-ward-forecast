"""Local swing measured in ward by-elections.

For each by-election held after the baseline national election, compare the party shares with
what the same voting districts gave each party in that national election:
    r = log(by-election share / baseline share)
then remove the average r across all by-elections (the national drift, which polls cover), and
estimate what is left by province and by community type within province, shrunk towards zero:
    effect = province part + community-within-province part, each sum(r) / (n + K_SHRINK).
The forecast multiplies a ward's shares by exp(ALPHA * effect) for its province and community type.
ALPHA and K_SHRINK are tuned in the backtests.
"""
import numpy as np
import pandas as pd

from build_data import group
from paths import INTERIM

PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA", "OTH"]
MIN_SHARE = 0.02  # ignore parties below 2% in either result: log ratios of tiny shares are noise
CLIP = 1.0


def province_of(muni):
    metros = {"BUF": "EC", "NMA": "EC", "MAN": "FS", "EKU": "GT", "JHB": "GT", "TSH": "GT", "ETH": "KZN", "CPT": "WC"}
    if muni in metros:
        return metros[muni]
    for pre in ("KZN", "LIM", "EC", "FS", "GT", "MP", "NW", "NC", "WC"):
        if str(muni).startswith(pre):
            return pre
    return "?"


def load(term):
    b = pd.read_csv(INTERIM / f"byelections_{term}.csv", dtype={"ward": str})
    v = pd.read_csv(INTERIM / f"byelection_vds_{term}.csv", dtype={"ward": str, "vd": str})
    b["party"] = b.party_name.map(group)
    return b, v


def residuals(term, since, votes, baseline, parties, communities, vd_muni):
    """One row per (by-election, party): r = log(share / baseline share), national drift removed."""
    b, v = load(term)
    b = b[b.date >= since]
    v = v[v.date >= since]
    b["party"] = b.party.where(b.party.isin(parties), "OTH")
    by = b.pivot_table(index=["date", "ward"], columns="party", values="votes", aggfunc="sum", fill_value=0)
    by = by.reindex(columns=parties + ["OTH"], fill_value=0)
    by = by.div(by.sum(axis=1), axis=0)

    base = votes[votes.election == baseline].merge(v, on="vd")
    base["party"] = base.party.where(base.party.isin(parties), "OTH")
    bs = base.pivot_table(index=["date", "ward"], columns="party", values="votes", aggfunc="sum", fill_value=0)
    bs = bs.reindex(columns=parties + ["OTH"], fill_value=0)
    bs = bs.div(bs.sum(axis=1), axis=0)

    idx = by.index.intersection(bs.index)
    by, bs = by.loc[idx], bs.loc[idx]
    keys = v.drop_duplicates(["date", "ward"]).set_index(["date", "ward"]).loc[idx]
    keys = keys.reset_index()
    keys["key"] = keys.date + "_" + keys.ward
    comm = communities.assign(votes, baseline, v.assign(key=v.date + "_" + v.ward)[["vd", "key"]])
    muni = v.merge(vd_muni, on="vd").drop_duplicates(["date", "ward"]).set_index(["date", "ward"]).muni

    rows = []
    for (date, ward) in idx:
        k = f"{date}_{ward}"
        for p in parties:
            s1, s0 = by.at[(date, ward), p], bs.at[(date, ward), p]
            if s1 < MIN_SHARE and s0 < MIN_SHARE:
                continue
            r = np.clip(np.log(max(s1, 0.005) / max(s0, 0.005)), -CLIP, CLIP)
            rows.append((date, ward, p, r, province_of(muni.get((date, ward), "?")), comm.get(k, -1)))
    r = pd.DataFrame(rows, columns=["date", "ward", "party", "r", "prov", "comm"])
    r["r"] = r.r - r.groupby("party").r.transform("mean")
    return r


def effects(r, k_shrink):
    """Shrunk province and community-within-province effects per party."""
    prov = r.groupby(["prov", "party"]).r.agg(["sum", "count"])
    prov["e"] = prov["sum"] / (prov["count"] + k_shrink)
    r = r.join(prov.e.rename("e_prov"), on=["prov", "party"])
    r["rr"] = r.r - r.e_prov
    pc = r.groupby(["prov", "comm", "party"]).rr.agg(["sum", "count"])
    pc["e"] = pc["sum"] / (pc["count"] + k_shrink)
    return prov.e, pc.e


def ward_adjustment(wards_prov, wards_comm, prov_e, pc_e, parties, alpha):
    """Multiplicative factor per (ward, party) = exp(alpha * (province + community effects))."""
    out = pd.DataFrame(1.0, index=wards_prov.index, columns=parties + ["OTH"])
    for p in parties:
        e = np.zeros(len(out))
        pe = prov_e.xs(p, level="party") if p in prov_e.index.get_level_values("party") else pd.Series(dtype=float)
        e += wards_prov.map(pe).fillna(0).values
        if p in pc_e.index.get_level_values("party"):
            ce = pc_e.xs(p, level="party")
            e += np.array([ce.get((pv, c), 0.0) for pv, c in zip(wards_prov.values, wards_comm.reindex(out.index).values)])
        out[p] = np.exp(alpha * e)
    return out
