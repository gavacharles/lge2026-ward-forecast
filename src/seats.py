"""Council seat allocation (Municipal Structures Act, Schedule 1), simplified.

A council has S seats: half are ward seats, the rest proportional (PR). Each party's total vote is
its ward-ballot plus PR-ballot votes (modelled here as its vote share). Seats are shared out with a
quota (votes / S, floored, + 1) and largest remainders; a party then fills its entitlement with
the wards it won and takes the rest from its PR list. A party that wins more wards than its
entitlement keeps them (overhang) and the remaining seats are re-shared among the others.

Seat counts are not published per council before the election; S = 2 x wards is used
(Johannesburg 270 = 2 x 135, Tshwane 214 = 2 x 107 in 2021; Cape Town is 2 x 116 - 1).
"""
import numpy as np


def allocate(shares, ward_wins, seats):
    """shares: (k,) vote shares; ward_wins: (k,) wards won; returns (k,) seats."""
    shares = np.asarray(shares, float)
    ward_wins = np.asarray(ward_wins, int)
    active = np.ones(len(shares), bool)
    fixed = np.zeros(len(shares), int)
    for _ in range(len(shares)):
        avail = seats - fixed.sum()
        v = np.where(active, shares, 0.0)
        total = v.sum()
        if avail <= 0 or total <= 0:
            break
        quota = np.floor(total * 1e6 / avail) / 1e6 + 1e-9
        ent = np.floor(v / quota).astype(int)
        rem = v / quota - ent
        left = avail - ent.sum()
        if left > 0:
            order = np.argsort(-rem)
            order = order[active[order]][:left]
            ent[order] += 1
        over = active & (ward_wins > ent)
        if not over.any():
            return fixed + np.where(active, ent, 0)
        fixed[over] = ward_wins[over]
        active[over] = False
    return fixed


def majority(seat_row, seats):
    return seat_row > seats / 2
