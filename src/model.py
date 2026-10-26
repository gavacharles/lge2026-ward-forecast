"""Ward-level forecast model for South African local government elections.

Idea: "structure from history, levels from polls".
  1. Aggregate voting-district (VD) results into the target election's wards.
  2. Per party, regress the ward-ballot share (logit) on the ward's most recent national-ballot
     share and its previous local-election ward-ballot share. Coefficients come from the
     2021 backtest (2019 NPE + 2016 LGE -> 2021 LGE).
  3. Shift each party's level (multiplicatively) so the national aggregate matches the polls,
     and pull metros towards their own polls.
  4. Simulate national, municipal and ward-level errors (sizes from the backtest) to get
     win probabilities.
"""
import numpy as np
import pandas as pd

from paths import INTERIM

EPS = 0.002
MAJORS = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def load():
    votes = pd.read_parquet(INTERIM / "vd_votes.parquet")
    other = pd.read_parquet(INTERIM / "vd_other_parties.parquet")
    return votes, other


def ward_table(votes, election, mapping, parties):
    """Party shares per target ward from one election's VD results.

    mapping: DataFrame [vd, ward, muni]. Parties not in `parties` are folded into OTH.
    Wards with no matched VDs fall back to their municipality's share.
    Returns (shares DataFrame indexed by ward, total votes Series, coverage Series).
    """
    v = votes[votes.election == election].copy()
    v["party"] = v.party.where(v.party.isin(parties), "OTH")
    v = v.merge(mapping[["vd", "ward", "muni"]], on="vd", how="inner")
    w = v.pivot_table(index="ward", columns="party", values="votes", aggfunc="sum", fill_value=0)
    w = w.reindex(columns=parties + ["OTH"], fill_value=0)
    tot = w.sum(axis=1)

    m = v.pivot_table(index="muni", columns="party", values="votes", aggfunc="sum", fill_value=0)
    m = m.reindex(columns=parties + ["OTH"], fill_value=0)
    m = m.div(m.sum(axis=1), axis=0)

    wards = mapping.drop_duplicates("ward").set_index("ward")
    shares = w.div(tot.replace(0, np.nan), axis=0).reindex(wards.index)
    missing = shares.isna().any(axis=1)
    shares.loc[missing] = m.reindex(wards.loc[missing, "muni"]).values
    cov = (mapping.assign(hit=mapping.vd.isin(set(v.vd))).groupby("ward").hit.mean()).reindex(wards.index)
    return shares.fillna(0), tot.reindex(wards.index).fillna(0), cov


def top_other(other, election, mapping):
    """Largest non-major party per ward in an election, and its share of all OTH votes."""
    o = other[other.election == election].merge(mapping[["vd", "ward"]], on="vd")
    o = o.groupby(["ward", "party_name"], as_index=False).votes.sum()
    tot = o.groupby("ward").votes.sum()
    top = o.sort_values("votes").groupby("ward").tail(1).set_index("ward")
    return pd.DataFrame({"local_name": top.party_name, "local_frac": (top.votes / tot).fillna(0)})


class StructuralModel:
    """Per-party WLS in logit space: y = a_p + b_p*logit(npe) + c_p*logit(lge_prev)."""

    def fit(self, X_npe, X_lge, Y, weight, parties):
        self.coef = {}
        rows = []
        for p in parties:
            x1, x2, y = logit(X_npe[p].values), logit(X_lge[p].values), logit(Y[p].values)
            A = np.column_stack([np.ones_like(x1), x1, x2])
            sw = np.sqrt(weight.values)
            beta, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
            self.coef[p] = beta
            rows.append((A, y, sw))
        A = np.vstack([r[0] for r in rows])
        y = np.concatenate([r[1] for r in rows])
        sw = np.concatenate([r[2] for r in rows])
        self.pooled, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
        return self

    def predict(self, X_npe, X_lge, parties):
        out = {}
        for p in parties:
            a, b, c = self.coef.get(p, self.pooled)
            out[p] = sigmoid(a + b * logit(X_npe[p].values) + c * logit(X_lge[p].values))
        S = pd.DataFrame(out, index=X_npe.index)
        return S.div(S.sum(axis=1), axis=0)


def calibrate(S, weight, target, parties, mask=None, iters=200):
    """Multiplicative shifts so the vote-weighted aggregate of S over `mask` hits `target`.

    target: dict party -> share (0-1) for a subset of parties; others share the remainder
    in their current proportions (so OTH keeps its modelled level).
    """
    S = S.copy()
    mask = np.ones(len(S), bool) if mask is None else np.asarray(mask)
    w = weight.values[mask]
    tgt = {p: v for p, v in target.items() if p in parties}
    for _ in range(iters):
        agg = (S.values[mask] * w[:, None]).sum(0) / w.sum()
        agg = pd.Series(agg, index=S.columns)
        free = [p for p in S.columns if p not in tgt]
        rest = 1 - sum(tgt.values())
        factor = pd.Series(1.0, index=S.columns)
        for p, v in tgt.items():
            factor[p] = v / max(agg[p], 1e-9)
        if free and agg[free].sum() > 0:
            factor[free] = rest / agg[free].sum()
        sub = S.values[mask] * factor.values
        S.values[mask] = sub / sub.sum(1, keepdims=True)
        if np.abs(factor.values - 1).max() < 1e-6:
            break
    return S


def aggregate(S, weight, groups):
    W = S.mul(weight, axis=0)
    g = W.groupby(groups).sum()
    return g.div(g.sum(axis=1), axis=0)


def winners(S, local, exclude_oth=True):
    """Ward winner treating OTH as one 'local' contender (its largest party's slice)."""
    T = S.copy()
    T["LOCAL"] = T["OTH"] * local.local_frac.reindex(T.index).fillna(0).values
    T = T.drop(columns="OTH")
    order = np.argsort(-T.values, axis=1)
    cols = np.array(T.columns)
    win = cols[order[:, 0]]
    second = cols[order[:, 1]]
    margin = np.take_along_axis(T.values, order[:, :2], 1)
    names = local.local_name.reindex(T.index).fillna("OTHER").values
    win_label = np.where(win == "LOCAL", names, win)
    return pd.DataFrame({"winner": win_label, "runner_up": np.where(second == "LOCAL", names, second),
                         "margin": margin[:, 0] - margin[:, 1]}, index=T.index)


def turnout_betas(shares, turnout, weight):
    """Per party: slope of logit(ward share) on standardised ward turnout (weighted).

    Positive = the party does better where turnout is high, so it gains when turnout is low
    elsewhere. Used to simulate differential turnout."""
    z = (turnout - np.average(turnout, weights=weight)) / np.sqrt(np.cov(turnout, aweights=weight))
    out = {}
    for p in shares.columns:
        y = logit(shares[p].values)
        A = np.column_stack([np.ones_like(z), z])
        sw = np.sqrt(weight.values)
        out[p] = float(np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)[0][1])
    return pd.Series(out)


def simulate(S, weight, muni, local, sd_nat, sd_muni, sd_ward, n=1000, seed=7, muni_sd_scale=None,
             turnout_beta=None, sd_turnout=0.0, council_seats=None, blocs=None, seat_sims=400):
    """Monte Carlo over multiplicative log-errors.

    Each simulation draws: a national error per party (sd_nat: scalar or per-party array, in log
    units), a municipal error per (municipality, party), a ward error per (ward, party) with fat
    tails (t, 5 df), and one differential-turnout shock that moves each party by
    turnout_beta * N(0, sd_turnout). Returns ward win probabilities and municipal statistics; with
    council_seats (Series muni -> seats) it also allocates seats in the first `seat_sims` runs.
    """
    from seats import allocate
    rng = np.random.default_rng(seed)
    parties = list(S.columns)
    k = len(parties)
    base = np.log(np.clip(S.values, 1e-6, 1)).astype(np.float32)
    munis, midx = np.unique(muni.values, return_inverse=True)
    scale = np.ones(len(munis), np.float32)
    if muni_sd_scale is not None:
        scale = muni_sd_scale.reindex(munis).fillna(1).values.astype(np.float32)
    sd_nat = np.broadcast_to(np.asarray(sd_nat, np.float32), (k,))
    tb = np.zeros(k, np.float32) if turnout_beta is None else turnout_beta.reindex(parties).fillna(0).values.astype(np.float32)
    frac = local.local_frac.reindex(S.index).fillna(0).values.astype(np.float32)
    oth = parties.index("OTH")
    labels = parties[:oth] + ["LOCAL"] + parties[oth + 1:]
    wins = np.zeros((len(S), k), np.int32)
    w = weight.values.astype(np.float32)
    largest = np.zeros((len(munis), k), np.int32)
    majority = np.zeros((len(munis), k), np.int32)
    mshare = np.zeros((len(munis), k), np.float64)
    seats_n = None if council_seats is None else council_seats.reindex(munis).values.astype(int)
    seat_sum = np.zeros((len(munis), k))
    seat_largest = np.zeros((len(munis), k))
    seat_major = np.zeros((len(munis), k))
    bloc_major = {b: np.zeros(len(munis)) for b in (blocs or {})}
    bloc_idx = {b: [parties.index(p) for p in ps if p in parties] for b, ps in (blocs or {}).items()}
    for it in range(n):
        e = (rng.normal(0, 1, k).astype(np.float32)[None, :] * sd_nat[None, :]
             + rng.normal(0, 1, (len(munis), k)).astype(np.float32)[midx] * (sd_muni * scale[midx])[:, None]
             + rng.standard_t(5, (len(S), k)).astype(np.float32) * sd_ward
             + np.float32(rng.normal(0, sd_turnout)) * tb[None, :])
        x = np.exp(base + e)
        x /= x.sum(1, keepdims=True)
        # council strength: party vote shares by municipality
        msum = np.zeros((len(munis), k))
        np.add.at(msum, midx, x * w[:, None])
        msum /= msum.sum(1, keepdims=True)
        mshare += msum
        largest[np.arange(len(munis)), msum.argmax(1)] += 1
        majority += msum > 0.5
        y = x.copy()
        y[:, oth] *= frac  # only the largest local party can win the ward
        win = y.argmax(1)
        wins[np.arange(len(S)), win] += 1
        if seats_n is not None and it < seat_sims:
            ww = np.zeros((len(munis), k), int)
            np.add.at(ww, (midx, win), 1)
            for m in range(len(munis)):
                st = allocate(msum[m], ww[m], seats_n[m])
                seat_sum[m] += st
                seat_largest[m, st.argmax()] += 1
                seat_major[m] += st > seats_n[m] / 2
                for b, ix in bloc_idx.items():
                    bloc_major[b][m] += st[ix].sum() > seats_n[m] / 2
    probs = pd.DataFrame(wins / n, index=S.index, columns=labels)
    mstats = {
        "share": pd.DataFrame(mshare / n, index=munis, columns=parties),
        "p_largest": pd.DataFrame(largest / n, index=munis, columns=parties),
        "p_majority": pd.DataFrame(majority / n, index=munis, columns=parties),
    }
    if seats_n is not None:
        ns = min(n, seat_sims)
        mstats["seats"] = pd.DataFrame(seat_sum / ns, index=munis, columns=parties)
        mstats["p_largest_seats"] = pd.DataFrame(seat_largest / ns, index=munis, columns=parties)
        mstats["p_majority_seats"] = pd.DataFrame(seat_major / ns, index=munis, columns=parties)
        mstats["p_bloc_majority"] = pd.DataFrame({b: v / ns for b, v in bloc_major.items()}, index=munis)
    return probs, mstats
