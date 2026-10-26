"""Download IEC results files used by the model (static URLs found via the results portal).

Resumes partial files and checks each against the server's Content-Length: the IEC servers
are slow and long transfers often drop.
"""
import zipfile

import requests

from paths import RAW

PROVS = ["EC", "FS", "GP", "KN", "NP", "MP", "NW", "NC", "WP"]
LGE = "https://results.elections.org.za/home/LGEPublicReports/{ev}/Downloadable%20Party%20Results/{pr}.csv"
FILES = {
    **{f"lge2021/{p}.csv": LGE.format(ev=1091, pr=p) for p in PROVS},
    **{f"lge2016/{p}.csv": LGE.format(ev=402, pr=p) for p in PROVS},
    **{f"lge2011/{p}.csv": LGE.format(ev=197, pr=p) for p in PROVS},
    "npe2024/National.zip": "https://results.elections.org.za/home/NPEPublicReports/1334/National%20Ballot/Downloadable%20Results/National.zip",
    "npe2019/National.zip": "https://www.elections.org.za/content/NPEPublicReports/699/Downloadable%20Results/National.zip",
    "npe2014/National.csv": "https://www.elections.org.za/content/NPEPublicReports/291/Downloadable%20Results/National.csv",
}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"}


def fetch(url, dest, tries=5):
    for _ in range(tries):
        head = requests.head(url, headers=UA, timeout=120, allow_redirects=True)
        size = int(head.headers.get("Content-Length", 0))
        have = dest.stat().st_size if dest.exists() else 0
        if size and have == size:
            return False
        hdr = dict(UA, Range=f"bytes={have}-") if have and size else UA
        try:
            with requests.get(url, headers=hdr, stream=True, timeout=600) as r:
                r.raise_for_status()
                mode = "ab" if r.status_code == 206 else "wb"
                with open(dest, mode) as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        except requests.RequestException:
            continue
        if not size or dest.stat().st_size == size:
            return True
    raise RuntimeError(f"incomplete download: {url}")


def main():
    for rel, url in FILES.items():
        dest = RAW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if fetch(url, dest):
            print("downloaded", rel, dest.stat().st_size)
            if dest.suffix == ".zip":
                zipfile.ZipFile(dest).extractall(dest.parent)


if __name__ == "__main__":
    main()
