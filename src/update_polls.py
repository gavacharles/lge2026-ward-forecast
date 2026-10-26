"""Refresh config/polls_2026.csv from the Wikipedia article's opinion poll tables.

Parses the national and per-metro tables of "2026 South African municipal elections" (wikitext via
the MediaWiki API). Polls Wikipedia lacks (e.g. metro subsamples reported only in the press) live
in config/polls_2026_extra.csv and are kept as they are. Prints what changed; exit code 0 always.
"""
import re
import sys

import pandas as pd
import requests

from paths import CONFIG

API = "https://en.wikipedia.org/w/api.php"
PAGE = "2026_South_African_municipal_elections"
UA = {"User-Agent": "lge2026-ward-forecast/1.0 (https://github.com/gavacharles/lge2026-ward-forecast)"}
AREAS = {"national": "NAT", "johannesburg": "JHB", "ekurhuleni": "EKU", "tshwane": "TSH", "pretoria": "TSH",
         "ethekwini": "ETH", "durban": "ETH", "cape town": "CPT", "nelson mandela": "NMA",
         "buffalo city": "BUF", "mangaung": "MAN"}
HEADER_PARTY = {"ANC": "ANC", "DA": "DA", "MK": "MK", "EFF": "EFF", "IFP": "IFP", "FF+": "FFP",
                "ASA": "ASA", "ACTIONSA": "ASA", "PA": "PA"}
PARTIES = ["ANC", "DA", "MK", "EFF", "IFP", "PA", "FFP", "ASA"]
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
DEFAULT_SAMPLE = {"NAT": 1000}


def clean(cell):
    cell = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    cell = re.sub(r"\{\{Efn.*?\}\}", "", cell, flags=re.S | re.I)
    cell = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", cell)  # [[target|label]] -> label
    if "|" in cell:  # style="..."|value
        cell = cell.split("|")[-1]
    return cell.replace("'''", "").strip()


def pollster_code(s):
    s = s.lower()
    for key, code in [("social research", "SRF"), ("sabi", "SABI"), ("ipsos", "Ipsos"), ("markdata", "MarkData"),
                      ("mark data", "MarkData"), ("atlas", "AtlasIntel"), ("afrobarometer", "Afrobarometer")]:
        if key in s:
            return code
    return s.split("/")[0].strip().title()


def end_date(text):
    t = text.lower().replace("–", "-")
    m = re.findall(r"(\d{1,2})?\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?", t)
    years = re.findall(r"\d{4}", t)
    if not m or not years:
        return None
    day, month, year = m[-1]
    year = int(year or years[-1])
    mo = MONTHS[month]
    if day:
        d = pd.Timestamp(year=year, month=mo, day=int(day))
    else:  # month only ("September - October 2026"): the 15th of the last month, so the date is stable
        d = pd.Timestamp(year=year, month=mo, day=15)
    return d.date().isoformat()


def parse_tables(wikitext):
    rows = []
    sections = re.split(r"\n===\s*(.+?)\s*===\s*\n", wikitext[wikitext.find("Opinion poll"):])
    for title, body in zip(sections[1::2], sections[2::2]):
        area = next((code for key, code in AREAS.items() if key in title.lower()), None)
        if not area or "{|" not in body:
            continue
        table = body[body.find("{|"): body.find("|}")]
        header = [clean(h) for h in re.findall(r"^!(?:[^|\n]*\|)?\s*(.+)$", table, flags=re.M)]
        cols = [HEADER_PARTY[h.upper()] for h in header if h.upper() in HEADER_PARTY]
        for block in table.split("\n|-")[1:]:
            cells = [c for c in re.split(r"\n\|", "\n" + block.strip()) if c.strip()]
            if len(cells) < 3 + len(cols) or cells[0].lstrip().startswith("!"):
                continue
            who = clean(cells[0])
            if "election" in who.lower() or "result" in who.lower():
                continue
            date = end_date(clean(cells[1]))
            n = re.sub(r"[^\d]", "", clean(cells[2]))
            vals = {}
            for p, c in zip(cols, cells[3: 3 + len(cols)]):
                v = re.sub(r"[^\d.]", "", clean(c))
                vals[p] = float(v) if v else None
            if not date:
                continue
            rows.append({"pollster": pollster_code(who), "area": area, "fieldwork_end": date,
                         "sample": int(n) if n else DEFAULT_SAMPLE.get(area, 500),
                         **vals, "source": "Wikipedia opinion polling table" + ("" if n else " (sample not given)")})
    return pd.DataFrame(rows)


def main():
    r = requests.get(API, params={"action": "parse", "page": PAGE, "prop": "wikitext", "format": "json",
                                  "formatversion": 2}, headers=UA, timeout=60)
    r.raise_for_status()
    new = parse_tables(r.json()["parse"]["wikitext"])
    if new.empty:
        print("No poll tables parsed; leaving polls_2026.csv unchanged.")
        return
    new = new.reindex(columns=["pollster", "area", "fieldwork_end", "sample", *PARTIES, "source"])
    new = new.drop_duplicates(["pollster", "area", "fieldwork_end"]).sort_values(["area", "fieldwork_end"], ascending=[True, False])
    f = CONFIG / "polls_2026.csv"
    old = pd.read_csv(f) if f.exists() else new.iloc[:0]
    key = ["pollster", "area", "fieldwork_end"]
    added = new.merge(old[key], on=key, how="left", indicator=True).query("_merge == 'left_only'")
    new.to_csv(f, index=False)
    print(f"{len(new)} polls parsed; {len(added)} new:")
    if len(added):
        print(added[key + ["ANC", "DA", "MK"]].to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
