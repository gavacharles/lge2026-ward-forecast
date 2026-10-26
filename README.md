# LGE 2026 ward forecast (South Africa, 4 Nov 2026)

Predicts the likely winner of each of the 4,485 wards (IEC delimitation for 2026) and each
municipality's party strength, with probabilities.

## Method: structure from history, levels from polls

1. **2026 wards.** `scrape_wards2026.py` reads the IEC results portal (2026 event) to get every
   ward's voting districts (VDs): 23,696 VDs in 4,485 wards (MDB lists 4,488; 3 Free State wards are not
   yet on the portal).
2. **History, re-cut to 2026 wards.** VD-level results of the 2024 national ballot and the 2021
   local ward ballot are summed into the new wards (`build_data.py`, `model.ward_table`). About 97% of
   2026 VDs have 2024 history and 96% have 2021 history; the rest fall back to their municipality.
3. **Structural model.** Per party, in logit space:
   `share_LGE = a + b * share_latest_NPE + c * share_previous_LGE`, fitted on 2021 (2019 NPE + 2016 LGE).
   MK split from the ANC in 2023, so a ward's 2021 ANC local vote is split ANC/MK by the ward's 2024 ratio.
4. **Polls set the levels.** Party levels are shifted so the national total matches the poll average
   (`config/polls_2026.json`); metros with their own polls are pulled towards them (weight 0.25 to 0.7).
   Independents and local parties (OTH) keep the model's level because polls under-measure them.
5. **Uncertainty.** 2,000 simulations with national (poll), municipal and ward-level errors; the
   municipal and ward error sizes come from the backtest. A ward's "local" contender is the
   largest non-major party there in 2021.

## Backtest (forecast 2021 from 2019 + 2016, provinces held out)

| Method | Ward winners correct |
| --- | --- |
| Carry forward the 2016 local winner | 88.8% |
| Carry forward the 2019 national-ballot winner | 89.3% |
| Model, calibrated to the national result | **90.8%** (metros 97.2%) |
| Model, calibrated to each province's result | 91.3% |

Probabilities are reasonably calibrated: see `outputs/backtest_2021_calibration.csv`.
The backtest assumes accurate national polling; real poll error adds uncertainty, which the
forecast simulates (`national_sd_logit`).

## Run

```sh
python3 src/download.py          # IEC files -> $ELECTION_DATA (default ~/ElectionModelData)
python3 src/scrape_wards2026.py  # 2026 ward -> VD map (~20 min, resumable)
python3 src/build_data.py
python3 src/backtest.py
python3 src/forecast_2026.py     # -> outputs/ward_forecast_2026.csv, municipality_forecast_2026.csv
```

Bulk data lives outside OneDrive (`src/paths.py`) because on-demand sync evicts large files.

## Known limits

- **By-elections not used yet.** Since 2024 the IFP has held up against MK in KZN by-elections; the
  model leans on 2024 national results, so it probably overstates MK in IFP heartland wards.
- **Candidates.** It doesn't check which parties field a ward candidate, and it doesn't model
  incumbents or strong independents beyond 2021 results.
- **New parties.** Parties with no 2021/2024 history (such as Unite for Change and Afrika Mayibuye) are in OTH.
- **Turnout.** Uses 2021 turnout patterns. Differential turnout (such as a low 42%) can move close wards.
- **Council control.** Municipal "majority" uses vote share above 50%, which approximates the seat formula.
