"""Scrape ward by-election results from the IEC results portal.

For every by-election date in a municipal term (on or after `since`), downloads each ward's
'Detailed Results' Excel report and parses: ward, date, voting districts, party totals.
Output: $ELECTION_DATA/interim/byelections_<term>.csv (one row per ward-date-party) and
byelection_vds_<term>.csv (ward-date -> VD list). Resumable: raw .xls files are cached.

Terms: 1091 = 2021-26 (forecast), 402 = 2016-21 (2021 backtest), 197 = 2011-16 (2016 backtest).
"""
import csv
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from iec_portal import Portal
from paths import INTERIM, RAW

P = "ctl00$MainContent$"
CACHE = RAW / "byelections"


def portal_at(term, date_id):
    p = Portal("MBE-Results")
    p.postback(P + "ddlMunicipalElections", {P + "ddlMunicipalElections": term})
    p.postback(P + "ddlByelectionDate", {P + "ddlByelectionDate": date_id})
    p.postback(P + "ddlByelectionType", {P + "ddlByelectionType": "1"})
    p.postback(P + "radReports$1", {P + "radReports": "DETAILED_REPORT"})
    return p


def label_date(label):
    return pd.to_datetime(label.replace(" BY-ELECTION", ""), format="%d %b %Y").date().isoformat()


def dates(term, since):
    p = Portal("MBE-Results")
    p.postback(P + "ddlMunicipalElections", {P + "ddlMunicipalElections": term})
    return [(v, t) for v, t in p.selects()[P + "ddlByelectionDate"] if v != "-2" and label_date(t) >= since]


def fetch_date(term, date_id, label, tries=3):
    out = []
    for attempt in range(tries):
        try:
            p = portal_at(term, date_id)
            wards = [(v, t) for v, t in p.selects()[P + "ddlWardsDetailedResults"] if v not in ("-2", "0")]
            for ward, _ in wards:
                f = CACHE / f"{date_id}_{ward}.xls"
                if not (f.exists() and f.stat().st_size > 0):
                    p.postback(P + "ddlWardsDetailedResults", {P + "ddlWardsDetailedResults": ward})
                    a = p.soup.find(id="MainContent_imgbtnEXCELDetailedResultsReport")
                    r = p.s.get(urllib.parse.urljoin(p.url, a["href"]), timeout=180)
                    r.raise_for_status()
                    f.write_bytes(r.content)
                out.append((date_id, label, ward, f))
            return out
        except Exception as e:  # restart the session on any portal hiccup
            err = e
            time.sleep(5 * (attempt + 1))
    print(f"FAILED {label}: {err}", flush=True)
    return out


def parse(path):
    d = pd.read_excel(path, header=None)
    rows = [[v for v in r if pd.notna(v) and str(v).strip() != ""] for r in d.itertuples(index=False)]
    ward, registered, vds, parties = None, None, [], {}
    section, party = None, None
    for vals in rows:
        if not vals:
            continue
        s0 = str(vals[0]).strip()
        if s0 == "Ward:":
            ward = str(vals[1]).strip()
        elif s0.startswith("Total Registered Voters"):
            registered = float(vals[1])
        elif s0 == "Ward Summary":
            section = "summary"
        elif s0 == "Candidate Summary":
            section = "cand"
        elif section == "summary" and re.fullmatch(r"\d{8}", s0):
            vds.append(s0)
        elif section == "cand" and len(vals) >= 3 and not re.fullmatch(r"[\d.]+", str(vals[1])) and s0 != "Total":
            party = " ".join(str(vals[1]).upper().split())
            if party in ("", "NAN"):
                party = "INDEPENDENT"
        elif section == "cand" and s0 == "Total" and party:
            parties[party] = parties.get(party, 0) + float(vals[1])
            party = None
    return ward, registered, vds, parties


def main(term="1091", since="2021-11-02", workers=6):
    CACHE.mkdir(parents=True, exist_ok=True)
    ds = dates(term, since)
    print(len(ds), "by-election dates", flush=True)
    files = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_date, term, v, t): t for v, t in ds}
        for i, f in enumerate(as_completed(futs), 1):
            got = f.result()
            files += got
            print(f"[{i}/{len(ds)}] {futs[f]}: {len(got)} wards", flush=True)
    res, vdrows = [], []
    for date_id, label, ward_id, f in files:
        try:
            ward, reg, vds, parties = parse(f)
        except Exception as e:
            print("parse failed", f.name, e)
            continue
        date = label_date(label)
        for party, v in parties.items():
            res.append((date, ward or ward_id, reg, party, v))
        for vd in vds:
            vdrows.append((date, ward or ward_id, vd))
    with open(INTERIM / f"byelections_{term}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "ward", "registered", "party_name", "votes"])
        w.writerows(res)
    with open(INTERIM / f"byelection_vds_{term}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "ward", "vd"])
        w.writerows(vdrows)
    print(len({(r[0], r[1]) for r in res}), "ward by-elections parsed", flush=True)


if __name__ == "__main__":
    # usage: scrape_byelections.py [term] [since YYYY-MM-DD] [workers]
    a = sys.argv[1:]
    main(a[0] if a else "1091", a[1] if len(a) > 1 else "2021-11-02", int(a[2]) if len(a) > 2 else 6)
