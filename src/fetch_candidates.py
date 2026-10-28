"""Ward candidates for LGE 2026 from the IEC's certified candidate lists -> config/candidates_2026.csv.

The IEC publishes the lists as one PDF per province (latest: as supplemented on 23 Oct 2026 after the
Constitutional Court order in ANC v IEC). Ward candidates are the rows whose "Ward / List order"
column holds an 8-digit ward ID; PR list rows are skipped. Output: one row per (ward, party), with
party grouped into the model's codes (others keep their name).

Usage: python src/fetch_candidates.py
"""
import re
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import quote

import pandas as pd
import pypdf
import requests

from build_data import group
from paths import CONFIG, INTERIM, RAW

BASE = "https://www.elections.org.za/pw/Documents/Candidate Lists/LGE2026/LGE2026 Supplementary List 23102026/"
FILES = {p: f"Supplementary list {p} 23102026.pdf" for p in ("EC", "FS", "GP", "KZN", "LP", "NC", "NW", "WC")}
FILES["MP"] = "Supplemenrary list MP 23102026.pdf"  # sic, as published
ROW = re.compile(r"^(\S+) - (.*?)(\d{8})(\d{6}\*{4}\d{2}\*)")
OUT = RAW / "candidates"


def download(prov):
    f = OUT / f"{prov}.pdf"
    if not f.exists():
        r = requests.get(BASE.replace(" ", "%20") + quote(FILES[prov]), timeout=300,
                         headers={"User-Agent": "Mozilla/5.0 (research; lge2026-ward-forecast)"})
        r.raise_for_status()
        f.write_bytes(r.content)
    return f


def muni_names():
    w = pd.read_csv(INTERIM / "wards2026_vd.csv", dtype=str, usecols=["municipality"]).drop_duplicates()
    return {m.split(" - ", 1)[0]: m.split(" - ", 1)[1] for m in w.municipality}


def parse(path):
    """(ward, party) rows. The PDF text often glues the municipality name to the party name
    ("City of JohannesburgDEMOCRATIC ALLIANCE"), so the known name is stripped, ignoring case."""
    names = muni_names()
    rows = []
    for page in pypdf.PdfReader(path).pages:
        for line in (page.extract_text() or "").splitlines():
            m = ROW.match(line)
            if not m:
                continue
            rest = m.group(2)
            name = names.get(m.group(1), "")
            if name and rest.lower().startswith(name.lower()):
                party = rest[len(name):]
            else:  # fall back: party names are upper case, municipality names are not
                words = rest.split()
                i = len(words)
                while i > 0 and words[i - 1] == words[i - 1].upper():
                    i -= 1
                party = " ".join(words[i:])
            rows.append((m.group(3), " ".join(party.split())))
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [download(p) for p in FILES]
    with ProcessPoolExecutor() as ex:
        rows = [r for part in ex.map(parse, paths) for r in part]
    c = pd.DataFrame(rows, columns=["ward", "party_name"]).drop_duplicates()
    # "VRYHEIDSFRONT PLUS | FREEDOM FRONT PLUS" -> "VRYHEIDSFRONT PLUS"
    code = c.party_name.str.split(" | ", regex=False).str[0].map(group)
    c["party"] = code.where(code.isin(["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]), c.party_name)
    c = c[["ward", "party", "party_name"]].sort_values(["ward", "party"])
    c.to_csv(CONFIG / "candidates_2026.csv", index=False)
    print(len(c), "ward candidacies in", c.ward.nunique(), "wards;", c.party_name.nunique(), "parties")
    print(c.groupby("party").ward.nunique().sort_values(ascending=False).head(12).to_string())


if __name__ == "__main__":
    main()
