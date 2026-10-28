"""Run the model end to end.

  python src/pipeline.py                 backtest -> forecast -> site (uses processed data only)
  python src/pipeline.py --refresh-data  first re-download IEC results, rescrape new by-elections and
                                         candidate lists, rebuild processed tables and snapshot them
  python src/pipeline.py --snapshot      copy processed tables into the repo's data/interim

The GitHub Action runs the first form with ELECTION_DATA pointing at the repo's data/ folder, so
CI never needs the IEC servers.
"""
import shutil
import sys

import backtest
import build_data
import build_site
import download
import fetch_candidates
import forecast_2026
import scrape_byelections
from paths import INTERIM, PROJECT

SNAPSHOT = ["vd_votes.parquet", "vd_meta.parquet", "vd_other_parties.parquet", "wards2026_vd.csv",
            *[f"{p}_{t}.csv" for p in ("byelections", "byelection_vds") for t in ("1091", "402", "197")]]


def snapshot():
    dest = PROJECT / "data" / "interim"
    if dest.resolve() == INTERIM.resolve():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for f in SNAPSHOT:
        shutil.copy(INTERIM / f, dest / f)
    print("snapshot ->", dest)


def main(args):
    if "--snapshot" in args:
        snapshot()
        return
    if "--refresh-data" in args:
        download.main()
        scrape_byelections.main("1091", "2021-11-02")
        fetch_candidates.main()
        build_data.main()
        snapshot()
    backtest.main()
    forecast_2026.main()
    build_site.main()


if __name__ == "__main__":
    main(sys.argv[1:])
