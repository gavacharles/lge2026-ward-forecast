"""Download the MDB 2026 ward boundaries (MDB Spatial Knowledge Hub feature service) as GeoJSON.

Geometry is generalised server-side (maxAllowableOffset, in degrees) so the web map stays small.
"""
import json
import sys

import requests

from paths import RAW

URL = "https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/MDB_Wards_2026/FeatureServer/0/query"
PAGE = 1000


def main(offset_deg=0.0004):
    feats = []
    start = 0
    while True:
        r = requests.get(URL, params={
            "where": "1=1", "outFields": "WardID,WardNo,CAT_B,MUNICNAME,Province", "outSR": 4326,
            "maxAllowableOffset": offset_deg, "geometryPrecision": 5, "resultOffset": start,
            "resultRecordCount": PAGE, "orderByFields": "FID", "f": "geojson"}, timeout=300)
        r.raise_for_status()
        page = r.json()["features"]
        feats += page
        if len(page) < PAGE:
            break
        start += PAGE
    out = RAW / "mdb_wards_2026.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"), separators=(",", ":"))
    print(len(feats), "wards ->", out, round(out.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main(*(float(a) for a in sys.argv[1:]))
