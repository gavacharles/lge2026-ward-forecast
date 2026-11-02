"""What-if and ingredient runs for the story: outputs/whatif_2026.json. Neither changes the published forecast.

What if the polls are wrong: the ANC or DA gains or loses 3 points in the national and metro poll averages,
the other parties scaling so the total holds. The KZN by-election level is left as it is.
Ingredients: history only; plus polls; plus by-election swing and candidate lists (the poll-led version); plus
KZN by-elections as a regional poll (published).
Usage: python src/whatif.py [as_of]
"""
import json
import sys
from datetime import date

import forecast_2026 as F
from paths import OUTPUTS

SHOW = ["ANC", "DA", "IFP", "MK", "EFF"]
METROS = F.METROS


def shift(party, pts):
    def mod(poll):
        def move(shares, delta):
            old = shares[party]
            new = max(old + delta, 0.1)
            others = sum(v for p, v in shares.items() if p != party)
            scale = (others - (new - old)) / others
            return {p: (new if p == party else v * scale) for p, v in shares.items()}
        national_old = poll["national"][party]
        ratio = max(national_old + pts, 0.1) / national_old
        poll["national"] = move(poll["national"], pts)
        for m in poll["metros"].values():
            if party in m["shares"]:
                m["shares"] = move(m["shares"], m["shares"][party] * (ratio - 1))
        return poll
    return mod


def summarise(out, muni, s):
    favs = out.favourite.value_counts()
    m = muni.set_index("muni")
    return {"national": {p: s["national_share"][p] for p in SHOW},
            "wards_favoured": {p: int(favs.get(p, 0)) for p in SHOW},
            "expected_wards": {p: float(s["expected_wards"].get(p, 0)) for p in SHOW},
            "tossups": int((out.rating == "Toss-up").sum()),
            "metros": {c: {"largest": m.at[c, "largest_party"], "p_largest": float(m.at[c, "p_largest"]),
                           "p_hung": float(m.at[c, "p_hung"])} for c in METROS},
            "hung_councils": int((m.p_hung > 0.5).sum())}


def main(as_of=None):
    as_of = as_of or date.today().isoformat()
    res = {"as_of": as_of, "whatif": {}, "ingredients": {}}
    for label, kw in [("As published", {}), ("ANC +3", {"poll_mod": shift("ANC", 3)}), ("ANC -3", {"poll_mod": shift("ANC", -3)}),
                      ("DA +3", {"poll_mod": shift("DA", 3)}), ("DA -3", {"poll_mod": shift("DA", -3)})]:
        out, muni, s, _ = F.run(2000, as_of, "byelection", **kw)
        res["whatif"][label] = summarise(out, muni, s)
        print(label, res["whatif"][label]["wards_favoured"], flush=True)
    for label, kw in [("History only", dict(scenario="poll", use_polls=False, use_byelections=False, use_candidates=False)),
                      ("+ polls", dict(scenario="poll", use_byelections=False, use_candidates=False)),
                      ("+ by-election swing, candidates", dict(scenario="poll")),
                      ("+ KZN by-elections (published)", dict(scenario="byelection"))]:
        out, muni, s, _ = F.run(2000, as_of, **kw)
        res["ingredients"][label] = summarise(out, muni, s)
        print(label, res["ingredients"][label]["wards_favoured"], flush=True)
    json.dump(res, open(OUTPUTS / "whatif_2026.json", "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:2])
