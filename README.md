# LGE 2026 ward forecast (South Africa, 4 Nov 2026)

**Live map:** https://gavacharles.github.io/lge2026-ward-forecast/ · **Methodology and margins of error:** [METHODOLOGY.md](METHODOLOGY.md) · **Full write-up:** [REPORT.md](REPORT.md)

An independent model, not affiliated with the IEC, the Municipal Demarcation Board or any party.
It gives a favourite and a win probability for each of the 4,485 wards, expected council seats and
coalition arithmetic for every municipality, and live updates on election night.

## How it works, in brief

1. Past results (2011–2024) are re-added inside the 2026 wards, one voting district at a time.
2. A per-party model, fitted on the 2016 and 2021 elections, links a ward's latest national result and
   previous local result to its next local result.
3. By-elections since 2024 adjust wards by province and community type. In KwaZulu-Natal outside
   eThekwini (no polls) they also set party levels; a poll-led alternative is published alongside.
4. Parties without a ward candidate (IEC certified lists) get no votes in that ward.
5. Polls set each party's overall level (recency-weighted, corrected for each pollster's lean in 2024).
6. 2,000 simulations give win chances, council seats and coalition odds.
7. On election night a nowcast blends counted voting districts with the forecast.

In backtests the model called 94.2% (2016) and 90.8% (2021) of ward winners correctly, ahead of simple
carry-forward baselines (92.8% and 89.3%). See [REPORT.md](REPORT.md) for methods, results and limits.

## Run it

```sh
pip install -r requirements.txt
python src/pipeline.py                 # backtest -> forecast -> site, from data/interim (about 20 s)
python src/pipeline.py --refresh-data  # re-download IEC results and by-elections first (slow)
python src/update_polls.py             # refresh polls from Wikipedia
python src/nowcast.py replay           # test the election-night nowcast on 2021
python src/nowcast.py live             # election night: pull IEC results and update ward calls
```

Polls are in `config/polls_2026.csv` (from Wikipedia) and `config/polls_2026_extra.csv` (by hand).
Ward candidates are in `config/candidates_2026.csv` (`python src/fetch_candidates.py` re-reads the IEC lists).

## Automation (GitHub Actions)

- **Forecast:** on every change to config, code or data, and daily. Re-runs everything and commits
  the site.
- **Poll update:** daily. Opens a pull request when Wikipedia's poll tables change.
- **Election night:** every 15 minutes, 4–6 November. Runs the live nowcast. `src/election_night.sh`
  is a local backup.

## Data

IEC results portal (results, ward lists, by-elections), MDB Spatial Knowledge Hub (2026 ward
boundaries), and polls from Ipsos, SRF/The Common Sense, SABI/News24 and eNCA/MarkData. Bulk raw data
lives outside the repo (`$ELECTION_DATA`, default `~/ElectionModelData`); the processed tables the model
needs (about 10 MB) are committed in `data/interim`.
