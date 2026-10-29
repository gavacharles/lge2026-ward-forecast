# Methodology statement: LGE 2026 ward forecast

*South Africa local government elections, 4 November 2026 · Statement dated 29 October 2026 ·
Live map: <https://gavacharles.github.io/lge2026-ward-forecast/>*

## 1. What this is, and what it is not

This is a **statistical forecast**, not an opinion poll. No one was interviewed for it. It combines
published election results, by-election results, published opinion polls and the IEC's certified
candidate lists into a probability for each party in each of the 4,485 wards. It also estimates
council seats in the 213 municipalities that have wards.

Because there is no survey sample, a survey-style "margin of error" does not apply. Section 5 gives the
forecast's uncertainty instead: ranges from 2,000 simulations, plus error rates measured by re-running
the method on the 2016 and 2021 elections.

| | |
|---|---|
| Author | Independent; not commissioned or paid for by any party, media house, the IEC or the Municipal Demarcation Board |
| Coverage | All 4,485 wards (Municipal Demarcation Board 2026 boundaries), 213 ward-based councils, 8 metros |
| What is forecast | Ward-ballot vote shares, ward winners, council seats, coalition arithmetic |
| Data cut-off | Polls with fieldwork to 15 Oct 2026; by-elections to 24 Jun 2026; candidate lists as supplemented on 23 Oct 2026 |
| Update schedule | Re-run daily and whenever inputs change; on election night every 15 minutes from counted results |
| Code and data | Public: <https://github.com/gavacharles/lge2026-ward-forecast> |

## 2. Data sources

- **Past results:** IEC voting-district results for the 2011, 2016 and 2021 local elections and the 2014,
  2019 and 2024 national elections.
- **2026 wards:** the IEC's list of voting districts in each 2026 ward, and Municipal Demarcation Board
  2026 ward boundaries.
- **By-elections:** IEC ward by-election results; 218 held between the 2024 election and 24 June 2026
  are used.
- **Polls:** 29 published polls (national and metro) from Ipsos, SRF/The Common Sense, SABI Strategy
  Group/News24 and eNCA/MarkData. They are taken from Wikipedia's polling table and the original
  reports. Fieldwork end dates are set to mid-month where only the month is published. Where a sample
  size isn't published, 500 is assumed for metro polls.
- **Candidates:** the IEC certified candidate lists (99,891 ward candidacies, including 569
  independents), as supplemented on 23 October 2026 after the Constitutional Court order in
  *ANC v Electoral Commission*.

## 3. Method

1. **History in the new wards.** Past results are added up, voting district by voting district, inside
   each 2026 ward. 96.5% of voting districts on average match a past result. 265 wards have under 80%
   matched; they fall back partly on municipal averages.
2. **Ward model.** For each party, a regression fitted on the 2016 and 2021 elections links a ward's last
   national-ballot share and last local ward-ballot share to its next local share. MK, ActionSA and the PA
   have too little history and use the average of the other parties' relationships. MK's 2021 baseline
   is the 2021 ANC vote, split by each ward's 2024 ANC:MK ratio.
3. **By-elections.** Swings in by-elections since 2024 adjust wards by province and community type, at a
   quarter of strength (the setting that worked best in the 2016 and 2021 tests).
4. **KwaZulu-Natal outside eThekwini** has no polls, and its by-elections contradict the national polls
   on MK. There, the 35 by-elections act as a regional poll. Their levels are corrected for how far KZN
   by-elections were from the next local result in 2016 and 2021 (for example, the ANC usually runs ahead
   in by-elections), and they carry 78% weight against the model's own estimate. See section 6.
5. **Candidates.** A party with no candidate in a ward gets no votes there. Its share goes to the parties
   that are standing, in proportion.
6. **Polls.** Each party's national level is a poll average. Weight halves every 30 days and grows with
   the square root of sample size. Half of each pollster's 2024 error is removed, using only final polls
   that ended within three weeks of the 2024 election. Independents and local parties ("Other") are
   under-measured by polls, so they are held at their 2021 ward-ballot level (12.4%). Metros with polls
   are pulled towards them by n ÷ (n + 800) of the way, between 0.2 and 0.8. In the published forecast MK
   and the IFP take their national totals from the model, not the polls (see section 6).
7. **Seats.** Council seats follow the Municipal Structures Act formula. Ward and PR votes are combined,
   seats are shared by quota and largest remainders, and ward winners count first, with overhang.
8. **Simulation.** 2,000 simulations each draw a national error per party (sized from the poll spread
   plus 2 points), a municipal error, a fat-tailed ward error and a turnout shock. A ward's win
   probability is how often each party won it in the simulations.

## 4. Assumptions

**Estimated from data:** the ward-model coefficients; the sizes of municipal error (0.23 on the log scale)
and ward error (0.27); how each party's vote moves with turnout; the KZN by-election corrections.

**Tuned on the 2016 and 2021 elections:** by-election strength (a quarter of the measured effect, with
shrinkage of 10 by-elections).

**Set by judgement:** poll half-life (30 days); share of pollster lean removed (half); extra poll error
(2 points); size of the turnout shock (0.25); national error for "Other" (0.15); council size taken as
2 × wards (real councils can be one seat smaller); win-chance labels (toss-up under 60%, lean under 75%,
likely under 90%, safe from 90%). All settings are listed in the code with their values.

## 5. Margins of error

**National vote share (ward ballot), 90% ranges from the simulations:**

| Party | Forecast | 90% range | Poll average (± spread) |
|---|---|---|---|
| ANC | 29.9% | 24–34% | 31.3 ± 2.1 |
| DA | 24.7% | 19–29% | 25.9 ± 2.1 |
| MK | 10.7% | 8–13% | 13.7 ± 2.2 |
| EFF | 8.1% | 5–14% | 8.5 ± 2.9 |
| IFP | 5.1% | 3–8% | 3.7 ± 2.2 |
| ActionSA | 3.7% | 2–8% | 3.9 ± 2.5 |
| FF+ | 3.0% | 2–6% | 3.1 ± 2.0 |
| PA | 2.2% | 1–4% | 2.3 ± 2.0 |
| Independents and others | 12.5% | 10–16% | not polled |

Poll averages are shares of all votes before "Other" is set aside, so they are slightly higher than the
forecast.

**Ward winners.**
- The forecast's own probabilities imply about **84% of ward winners called correctly** (the average of
  the favourites' chances). That is about 740 wrong calls out of 4,485.
- In tests on past elections, with the actual national result standing in for polls, the method called
  **94.2% (2016) and 90.8% (2021)** of ward winners. Simply carrying forward the last result scored 92.8%
  and 89.3%. Those test figures are a best case, because real polls are never exact.
- Average error in a party's ward vote share in those tests: **2.9 points (2016) and 3.3 points (2021)**.

**How far to trust a win chance** (backtest calibration):

| Forecast chance | Favourite actually won (2016 / 2021) |
|---|---|
| 60–70% | 79% / 73% |
| 70–80% | 82% / 81% |
| 80–90% | 91% / 87% |
| 95% and over (about 99% on average) | 98.8% / 97.2% |

Mid-range chances have been too cautious, and "safe" calls slightly too confident: about 1 in 35 safe
wards was lost in 2021.

**Ratings now:** 2,263 safe, 955 likely, 608 lean and 659 toss-up wards.

## 6. Design constraints and limitations

- **KwaZulu-Natal is the main uncertainty.** National polls put MK near its 2024 level (14.6%). In 41 KZN
  by-elections since 2024, MK averaged 24% where a poll-led forecast expects 37%, and the IFP 29% against
  16%. In past cycles KZN by-elections tracked the next local result much more closely: winners matched in
  82–89% of wards, against 44% here. The published forecast follows the by-elections. A poll-led version
  is published alongside it:

  | KwaZulu-Natal | By-election-led (published) | Poll-led |
  |---|---|---|
  | Wards favouring IFP / MK | 402 / 303 | 121 / 658 |
  | Councils where IFP / MK likely largest | 21 / 14 | 5 / 36 |
  | MK national vote | 10.7% | 12.9% |

  This is a judgement, not a tested result. In the 2016 and 2021 tests, where the polls were assumed
  perfect, using by-elections this way slightly lowered KZN accuracy (by 1.5 and 0.4 points). It is used
  here because polls and by-elections disagree far more than before, and MK has no local-election record.
  By-elections have low turnout, so they may understate parties whose voters turn out less, which could
  include MK.
- **Few polls.** Only 6 national polls since January; none newer than mid-October. Buffalo City and
  Mangaung have only small subsamples. Rural areas are polled only as part of national samples.
- **Local effects.** Even with perfect national figures, 5–9% of wards went against the model in past
  tests. Those misses come from local candidates, defections and service-delivery anger, which the model
  can't see.
- **Independents and new parties** are modelled as one "Other" block at its 2021 level. Who the
  candidates are, and their personal following, is not modelled.
- **No census data.** Ward demographics from Census 2022 are not published as data, so "community types"
  are built from voting patterns.
- **Turnout** is not forecast directly. A turnout shock is simulated, but its size is an assumption.
- **Boundaries.** Some 2026 wards cut across old voting districts. Results are assigned by voting
  district, which approximates the new ward boundaries.
- **Seats** use 2 × wards as council size, and district councils are not modelled.
- **Coalitions** show only which party groups would have a majority, not which deals will be made.

## 7. Accountability: scoring the forecast

The final pre-election forecast is frozen at 21:00 on 3 November 2026. It is copied with a manifest of
file fingerprints (SHA-256) and the commit is tagged `forecast-final`, so it can't be changed after
voting starts. Once the IEC declares the results, the frozen forecast is scored against them and the
scorecard is published on the site and in the repository. The scorecard covers:
ward winners against simple baselines; Brier score and calibration; national, provincial and ward vote
shares (including whether results fell inside the 90% ranges); council largest party, majority or hung,
and metro seats; and which KwaZulu-Natal reading, by-election-led or poll-led, was closer. The same
scorer, run on the 2021 backtest, reproduces its published figures (`outputs/scorecard_test2021.md`).

## 8. Independence and corrections

The model, data and every setting are public. Errors can be reported as issues on the GitHub repository.
Changes to the method are recorded in the repository's history. This statement describes the forecast
published on 29 October 2026; numbers on the live site update as inputs change.
