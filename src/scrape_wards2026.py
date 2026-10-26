"""Scrape the 2026 ward -> voting district (VD) delimitation from the IEC results portal.

Uses the 2026 LGE 'Results Summary' report dropdowns (Province -> Municipality -> Ward -> VD).
Writes one CSV per municipality to $ELECTION_DATA/interim/wards2026/ so the job can resume.
"""
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from iec_portal import Portal
from paths import INTERIM

EVENT_2026 = "1887"
P = "ctl00$MainContent$"
OUT = INTERIM / "wards2026"
PROVINCES = {"1": "Eastern Cape", "2": "Free State", "3": "Gauteng", "4": "KwaZulu-Natal",
             "5": "Mpumalanga", "6": "Northern Cape", "7": "Limpopo", "8": "North West",
             "9": "Western Cape"}


def portal_at_province(prov):
    p = Portal()
    p.postback(P + "ddlElections", {P + "ddlElections": EVENT_2026})
    p.postback(P + "radReports$1", {P + "radReports": "22"})
    p.postback(P + "ddlResultsSummaryProvinces", {P + "ddlResultsSummaryProvinces": prov})
    return p


def real_options(p, name):
    return [(v, t) for v, t in p.selects()[P + name] if v not in ("0", "-1", "-2")]


def scrape_muni(prov, muni_val, muni_name, tries=4):
    out = OUT / f"{muni_val.replace('~', '_')}.csv"
    if out.exists():
        return muni_name, "cached"
    for attempt in range(tries):
        try:
            p = portal_at_province(prov)
            p.postback(P + "ddlResultsSummaryMunicipalities", {P + "ddlResultsSummaryMunicipalities": muni_val})
            rows = []
            for ward, _ in real_options(p, "ddlResultsSummaryWards"):
                p.postback(P + "ddlResultsSummaryWards", {P + "ddlResultsSummaryWards": ward})
                for vd, _ in real_options(p, "ddlResultsSummaryVDs"):
                    rows.append((PROVINCES[prov], muni_name, ward, vd))
            if not rows:
                raise RuntimeError("no rows")
            tmp = out.with_suffix(".tmp")
            with open(tmp, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["province", "municipality", "ward", "vd"])
                w.writerows(rows)
            tmp.rename(out)
            return muni_name, f"{len({r[2] for r in rows})} wards, {len(rows)} VDs"
        except Exception as e:  # network hiccups / viewstate errors: start over
            err = e
            time.sleep(5 * (attempt + 1))
    return muni_name, f"FAILED: {err}"


def main(workers=6):
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for prov in PROVINCES:
        p = portal_at_province(prov)
        for val, name in real_options(p, "ddlResultsSummaryMunicipalities"):
            if not val.endswith("~3"):  # district councils have no wards
                jobs.append((prov, val, name))
    print(f"{len(jobs)} municipalities", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(scrape_muni, *j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            name, status = f.result()
            print(f"[{i}/{len(jobs)}] {name}: {status}", flush=True)
    combine()


def combine():
    import pandas as pd
    d = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(OUT.glob("*.csv"))], ignore_index=True)
    d["muni"] = d.municipality.str.split(" - ").str[0]
    d.to_csv(INTERIM / "wards2026_vd.csv", index=False)
    print(f"{d.ward.nunique()} wards, {len(d)} VDs -> {INTERIM / 'wards2026_vd.csv'}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
