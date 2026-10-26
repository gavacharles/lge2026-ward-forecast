"""Download IEC results files used by the model (static URLs found via the results portal)."""
import zipfile

import requests

from paths import RAW

LGE = "https://results.elections.org.za/home/LGEPublicReports/{ev}/Downloadable%20Party%20Results/{pr}.csv"
FILES = {
    **{f"lge2021/{p}.csv": LGE.format(ev=1091, pr=p) for p in ["EC", "FS", "GP", "KN", "NP", "MP", "NW", "NC", "WP"]},
    **{f"lge2016/{p}.csv": LGE.format(ev=402, pr=p) for p in ["EC", "FS", "GP", "KN", "NP", "MP", "NW", "NC", "WP"]},
    "npe2024/National.zip": "https://results.elections.org.za/home/NPEPublicReports/1334/National%20Ballot/Downloadable%20Results/National.zip",
    "npe2019/National.zip": "https://www.elections.org.za/content/NPEPublicReports/699/Downloadable%20Results/National.zip",
}
UA = {"User-Agent": "Mozilla/5.0 (research; election-prediction-model)"}


def main():
    for rel, url in FILES.items():
        dest = RAW / rel
        if dest.exists() and dest.stat().st_size > 0:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(dest.with_suffix(".part"), "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        dest.with_suffix(".part").rename(dest)
        if dest.suffix == ".zip":
            zipfile.ZipFile(dest).extractall(dest.parent)
        print("downloaded", rel, dest.stat().st_size)


if __name__ == "__main__":
    main()
