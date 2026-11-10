# lge2026-ward-forecast

Python model, automation and static site for an independent ward-level forecast of South Africa's 4 November 2026 local government elections. Not affiliated with the IEC, the Municipal Demarcation Board or any party.

Live map: https://gavacharles.github.io/lge2026-ward-forecast/ · Method: [METHODOLOGY.md](METHODOLOGY.md) · Write-up: [REPORT.md](REPORT.md)

## What the code does

It rebuilds past results (2011–2024) inside the 2026 wards by voting district, fits a per-party model on the 2016 and 2021 elections, adjusts with by-elections and polls, removes parties without a ward candidate, and runs 2,000 simulations for ward win probabilities, council seats and coalition odds. On election night a nowcast blends counted voting districts with the forecast.

## Layout

| Path | What it is |
|---|---|
| `src/` | Pipeline, download, backtest, forecast, nowcast, freeze, scoring and site-build scripts |
| `config/` | Polls (`polls_2026.csv` from Wikipedia, `polls_2026_extra.csv` by hand), ward candidates, coalitions |
| `data/interim/` | Processed tables the model needs (about 10 MB) |
| `outputs/` | Forecast, nowcast, backtest and scorecard outputs |
| `frozen/` | The locked final pre-election forecast |
| `docs/` | The GitHub Pages site (`index.html`, `app.js`, `style.css`, data files) |
| `.github/workflows/` | Forecast, polls, freeze, election-night and scoring workflows |

## Running

```sh
pip install -r requirements.txt
python src/pipeline.py                 # backtest -> forecast -> site, from data/interim (about 20 s)
python src/pipeline.py --refresh-data  # re-download IEC results and by-elections first (slow)
python src/update_polls.py             # refresh polls from Wikipedia
python src/fetch_candidates.py         # re-read the IEC candidate lists
python src/nowcast.py replay           # test the election-night nowcast on 2021
python src/nowcast.py live             # election night: pull IEC results and update ward calls
python src/freeze.py                   # lock the final forecast in frozen/
python src/score.py 2026               # score frozen/ against declared results
python src/score.py test2021           # check the scorer on the 2021 backtest
```

## Automation (GitHub Actions)

- **Forecast:** on every change to config, code or data, and daily; re-runs everything and commits the site.
- **Polls:** daily; opens a pull request when Wikipedia's poll tables change.
- **Freeze:** 21:00 SAST on 3 November; copies the final forecast to `frozen/`, tags `forecast-final` and stops further changes.
- **Election night:** every 15 minutes, 4–6 November; runs the live nowcast (`src/election_night.sh` is a local backup).
- **Score:** run by hand once results are declared.

## Data

IEC results portal (results, ward lists, by-elections), MDB Spatial Knowledge Hub (2026 ward boundaries) and published polls. Bulk raw data lives outside the repository (`$ELECTION_DATA`, default `~/ElectionModelData`); the processed tables are committed in `data/interim`.
