"""Turn raw IEC downloads into tidy voting-district (VD) level tables.

Output: $ELECTION_DATA/interim/vd_votes.parquet with one row per (election, vd, party_group)
and interim/vd_meta.parquet with VD -> municipality / 2016 & 2021 ward.
"""
import pandas as pd

from paths import INTERIM, RAW

PROVS = ["EC", "FS", "GP", "KN", "NP", "MP", "NW", "NC", "WP"]

PARTY_GROUPS = {
    "AFRICAN NATIONAL CONGRESS": "ANC",
    "DEMOCRATIC ALLIANCE": "DA",
    "UMKHONTO WESIZWE": "MK",
    "UMKHONTO WESIZWE PARTY": "MK",
    "ECONOMIC FREEDOM FIGHTERS": "EFF",
    "INKATHA FREEDOM PARTY": "IFP",
    "PATRIOTIC ALLIANCE": "PA",
    "VRYHEIDSFRONT PLUS": "FFP",
    "FREEDOM FRONT PLUS": "FFP",
    "ACTIONSA": "ASA",
}
PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA", "OTH"]


def group(name):
    return PARTY_GROUPS.get(" ".join(str(name).upper().split()), "OTH")


def muni_code(s):
    return s.str.split(" - ").str[0].str.strip()


def load_lge(folder, election):
    frames = []
    for pr in PROVS:
        d = pd.read_csv(RAW / folder / f"{pr}.csv", encoding="utf-8-sig", low_memory=False)
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d = d[d.BallotType.isin(["Ward", "PR"])]
    d["ward"] = d.Ward.astype(str).str.extract(r"(\d+)")[0]
    out = pd.DataFrame({
        "election": election + "_" + d.BallotType.str.lower(),
        "vd": d.VotingDistrict.astype(str),
        "muni": muni_code(d.Municipality),
        "ward": d.ward,
        "registered": d.RegisteredVoters,
        "party": d.PartyName.map(group),
        "party_name": d.PartyName.str.upper().str.split().str.join(" "),
        "votes": d.TotalValidVotes,
    })
    return out


def load_npe(path, election, cols, encoding="utf-8-sig"):
    vd, muni, reg, party, votes = cols
    d = pd.read_csv(path, encoding=encoding, low_memory=False, usecols=[vd, muni, reg, party, votes])
    return pd.DataFrame({
        "election": election,
        "vd": d[vd].astype(str),
        "muni": muni_code(d[muni]),
        "ward": None,
        "registered": d[reg],
        "party": d[party].map(group),
        "party_name": d[party].str.upper().str.split().str.join(" "),
        "votes": d[votes],
    })


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    parts = [
        load_lge("lge2016", "lge2016"),
        load_lge("lge2021", "lge2021"),
        load_npe(RAW / "npe2019" / "699.csv", "npe2019",
                 ["VD Number", "Municipality", "Registered Population", "sPartName", "Party Votes"], encoding="latin-1"),
        load_npe(RAW / "npe2024" / "National.csv", "npe2024",
                 ["VD_Number", "Municipality", "Registered_Population", "sPartyName", "Party_Votes"]),
    ]
    raw = pd.concat(parts, ignore_index=True)
    raw["votes"] = pd.to_numeric(raw.votes, errors="coerce").fillna(0)
    raw["registered"] = pd.to_numeric(raw.registered, errors="coerce")

    # Largest non-major party per (election, ward-or-vd): used to label "OTH" winners.
    oth = (raw[raw.party == "OTH"].groupby(["election", "vd", "party_name"], as_index=False).votes.sum())
    oth.to_parquet(INTERIM / "vd_other_parties.parquet", index=False)

    votes = raw.groupby(["election", "vd", "party"], as_index=False).votes.sum()
    votes.to_parquet(INTERIM / "vd_votes.parquet", index=False)

    meta = (raw.drop_duplicates(["election", "vd"])[["election", "vd", "muni", "ward", "registered"]])
    meta.to_parquet(INTERIM / "vd_meta.parquet", index=False)

    tot = votes.groupby(["election", "party"]).votes.sum().unstack()
    print((tot.div(tot.sum(axis=1), axis=0) * 100).round(2))
    print(meta.groupby("election").vd.nunique())


if __name__ == "__main__":
    main()
