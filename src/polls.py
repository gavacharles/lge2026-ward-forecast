"""Poll aggregation: recency- and size-weighted averages, corrected for pollster house effects.

- weight = sqrt(sample / 1000) * 0.5 ** (age_days / HALF_LIFE); age = days from fieldwork end to `as_of`
- house effect = SHRINK * (pollster's final 2024 poll - 2024 result), in points, per party;
  pollsters with no 2024 poll, or whose final poll ended more than FINAL_POLL_DAYS before election
  day, get none (an early poll's miss is mostly late movement, e.g. Ipsos 2024 missed MK's surge). Applied to national and metro polls alike.
- uncertainty per party = sqrt(weighted spread across polls^2 + HIST_ERR^2), in points
- metro weight (how far the forecast moves towards a metro's polls) grows with effective sample size

Polls come from config/polls_2026.csv (refreshed from Wikipedia by update_polls.py) plus
config/polls_2026_extra.csv (hand-entered polls Wikipedia lacks). Run directly to print averages.
"""
import json
from datetime import date

import numpy as np
import pandas as pd

from paths import CONFIG

PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]
HALF_LIFE = 30.0     # days
SHRINK = 0.5         # one election of evidence per pollster: keep half the measured lean
HIST_ERR = 2.0       # points: typical error of a final-poll average in SA (2024: ANC +2, MK -1.5)
METRO_K = 800.0      # effective sample at which a metro forecast moves halfway to its polls
FINAL_POLL_DAYS = 21  # only final polls this close to election day measure a pollster's lean


def house_effects():
    f = pd.read_csv(CONFIG / "polls_2024_final.csv", parse_dates=["fieldwork_end"])
    actual = f[f.pollster == "ACTUAL"].iloc[0]
    f = f[(f.pollster != "ACTUAL") & ((actual.fieldwork_end - f.fieldwork_end).dt.days <= FINAL_POLL_DAYS)]
    out = {}
    for r in f.itertuples(index=False):
        out[r.pollster] = {p: SHRINK * (getattr(r, p) - actual[p])
                           for p in PARTIES if p in f.columns and pd.notna(getattr(r, p))}
    return out


def aggregate(as_of=None):
    as_of = pd.Timestamp(as_of or date.today())
    files = [CONFIG / "polls_2026.csv", CONFIG / "polls_2026_extra.csv"]
    polls = pd.concat([pd.read_csv(f, parse_dates=["fieldwork_end"]) for f in files if f.exists()], ignore_index=True)
    polls = polls[polls.fieldwork_end <= as_of]
    he = house_effects()
    age = (as_of - polls.fieldwork_end).dt.days.clip(lower=0)
    polls["decay"] = 0.5 ** (age / HALF_LIFE)
    polls["w"] = np.sqrt(polls["sample"] / 1000) * polls.decay
    for p in PARTIES:
        adj = polls.pollster.map(lambda s: he.get(s, {}).get(p, 0.0))
        polls[p + "_adj"] = polls[p] - adj

    def summarise(g):
        shares, sds = {}, {}
        for p in PARTIES:
            m = g[p + "_adj"].notna()
            if not m.any():
                continue
            w, v = g.loc[m, "w"].values, g.loc[m, p + "_adj"].values
            mean = float(np.average(v, weights=w))
            spread = float(np.sqrt(np.average((v - mean) ** 2, weights=w))) if m.sum() > 1 else HIST_ERR
            shares[p] = round(max(mean, 0.1), 2)
            sds[p] = round(float(np.sqrt(spread ** 2 + HIST_ERR ** 2)), 2)
        n_eff = float((g["sample"] * g.decay).sum())  # interviews, discounted by age
        return shares, sds, n_eff, sorted(set(g.pollster))

    out = {"as_of": as_of.date().isoformat(), "house_effects": he, "metros": {}}
    nat = polls[polls.area == "NAT"]
    out["national"], out["national_sd_pts"], out["national_n_eff"], out["national_pollsters"] = summarise(nat)
    for area, g in polls[polls.area != "NAT"].groupby("area"):
        shares, sds, n_eff, who = summarise(g)
        weight = n_eff / (n_eff + METRO_K)
        out["metros"][area] = {"shares": shares, "sd_pts": sds, "n_eff": round(n_eff),
                               "weight": round(min(max(weight, 0.2), 0.8), 2), "polls": ", ".join(who)}
    return out


def logit_sd(share_pct, sd_pts):
    p = min(max(share_pct / 100, 0.01), 0.99)
    return (sd_pts / 100) / (p * (1 - p))


if __name__ == "__main__":
    print(json.dumps(aggregate(), indent=1))
