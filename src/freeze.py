"""Freeze the final pre-election forecast into frozen/, so it can be scored against the result.

Copies the ward, municipality and summary outputs (and the poll-led KZN scenario) with a manifest of
the time, git commit and SHA-256 of each file. Once frozen/manifest.json exists the daily forecast
workflow stops re-running the forecast, so the published pre-election forecast stays fixed.
The GitHub workflow freeze.yml runs this on the evening of 3 November and tags the commit
`forecast-final`. Run by hand with: python src/freeze.py [--force]
"""
import datetime
import hashlib
import json
import shutil
import subprocess
import sys

from paths import OUTPUTS, PROJECT

FROZEN = PROJECT / "frozen"
FILES = ["ward_forecast_2026.csv", "ward_forecast_2026_poll_scenario.csv", "municipality_forecast_2026.csv",
         "forecast_summary_2026.json", "backtest.json"]


def main(force=False):
    if (FROZEN / "manifest.json").exists() and not force:
        sys.exit("Already frozen (frozen/manifest.json). Use --force to overwrite.")
    FROZEN.mkdir(exist_ok=True)
    files = {}
    for f in FILES:
        shutil.copy(OUTPUTS / f, FROZEN / f)
        files[f] = hashlib.sha256((FROZEN / f).read_bytes()).hexdigest()
    shutil.copy(PROJECT / "docs" / "data" / "forecast.json", FROZEN / "site_forecast.json")
    files["site_forecast.json"] = hashlib.sha256((FROZEN / "site_forecast.json").read_bytes()).hexdigest()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT, capture_output=True, text=True).stdout.strip()
    summary = json.load(open(FROZEN / "forecast_summary_2026.json"))
    manifest = {"frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "git_commit": commit, "polls_as_of": summary["as_of"], "files": files}
    json.dump(manifest, open(FROZEN / "manifest.json", "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main("--force" in sys.argv)
